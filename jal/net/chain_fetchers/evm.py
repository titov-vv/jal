import json
import logging
from decimal import Decimal
from collections import defaultdict

from PySide6.QtCore import QT_TRANSLATE_NOOP

from jal.constants import AssetLocation, PredefinedAccountType
from jal.data_import.statement import Statement_ImportError, JSF
from jal.data_import.token_filter import TokenCandidate
from jal.db.account import JalAccount
from jal.db.settings import JalSettings
from jal.db.settings_registry import SettingsRegistry, SettingDescriptor
from jal.db.symbol import JalSymbol
from jal.db.address_match import impersonated_target
from jal.db.token_blacklist import normalize_address, is_evm_address
from jal.net.chain_fetchers.fetcher import ChainFetcher
from jal.net.chain_fetchers.protocols import protocol_category, protocol_name, ProtocolCategory
from jal.net.web_request import WebRequest

# This module has no JAL_FETCHER_CLASS on purpose: it is the shared base of the EVM chains, not a selectable chain
# itself. Each concrete chain (Ethereum, Arbitrum, Avalanche, ...) is a thin subclass in its own module that only
# sets the 'chainid', the native coin and - where the chain isn't served by Etherscan - the endpoint to read it from.
# See ethereum.py / arbitrum.py / avalanche.py.

# Etherscan moved to a single V2 endpoint that serves every chain it supports through one 'chainid' parameter and
# one API key. So every chain Etherscan serves shares this root and the same 'ApiKey_Etherscan' key; a chain it
# doesn't (Avalanche, which it serves on a paid tier only) is read from another provider offering the same
# 'module'/'action' surface - see the api_* class attributes below and avalanche.py.
_ETHERSCAN_API_ROOT = "https://api.etherscan.io/v2/api"
_WEI = Decimal('10') ** 18        # 1 coin = 10^18 wei, the unit every native amount is returned in
_NO_TRANSACTIONS = "No transactions found"   # status=0 message that means "empty history", not an error

# Upper end of the block window every 'account' query asks for - i.e. "no upper end at all". It has to stay above the
# height of EVERY chain this fetcher reads, and that is not a formality: the provider enforces 'endblock', and a value
# a chain has already passed closes the window BELOW the sync cursor. The query then answers
# _NO_TRANSACTIONS, which is indistinguishable from an exhausted history - so the fetch reports success, imports
# nothing and leaves the cursor where it was, silently, for as long as the account exists.
_MAX_BLOCK = 999999999999

_METHOD_APPROVE = '0x095ea7b3'    # approve(address,uint256) selector, the one gas-only call worth naming apart


# Raised by the classifier for a transaction whose shape it does not (yet) support - an unregistered exchange, a
# lending/bridge operation, an unfamiliar multi-asset shape. It stops the import at that transaction rather than
# guessing: see _fetch for the halt-and-checkpoint that imports every earlier block and re-tries this one next time.
class _HaltImport(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


# ----------------------------------------------------------------------------------------------------------------------
# Fetches the transaction history of an EVM wallet from an Etherscan-compatible API and turns it into JSF.
#
# Three account endpoints are read and they do not overlap: 'txlist' returns the top-level transactions the wallet
# sent or received (native coin movements and the gas of everything it initiated), 'tokentx' returns ERC-20 token
# movements, and 'txlistinternal' returns the native coin that contracts moved on the wallet's behalf (a swap output,
# a withdrawal). They are tied together by transaction hash, and the fetcher classifies each transaction as a WHOLE:
# all of a hash's legs are gathered, netted per asset, and turned into a single operation (a transfer, a swap, a gas
# fee, a reward), rather than each leg becoming its own transfer. A one-asset-out one-asset-in transaction is a swap
# only when it goes through a known swap router (see the protocol registry); an unknown or deferred shape halts the
# import at that transaction (_fetch) instead of being booked as something misleading.
class EVMFetcher(ChainFetcher):
    chain_id = 0                  # Etherscan V2 'chainid' of this chain
    icon_name = ''
    # Where the history is read from, and under which name a failure is reported. Etherscan's V2 API is the default
    # because it serves most of the chains JAL supports through one root and one key; a chain read from a different
    # provider overrides these three, and that provider's quirks belong to the subclass and must not leak back here.
    api_root = _ETHERSCAN_API_ROOT
    api_name = "Etherscan"
    api_key_setting = "ApiKey_Etherscan"
    # Result paging. 'page_size' is the 'offset' asked for and 'max_pages' bounds a runaway loop on an address with a
    # very long history - but their PRODUCT matters too: a provider may cap how deep a single query may be paged
    # (Routescan refuses page x offset above 10000), so a chain with such a cap sets both together. Running the
    # budget out costs no data, only another fetch - see _note_window_limit().
    page_size = 10000
    max_pages = 20
    # Dust threshold is shared by every EVM chain this fetcher backs whose native coin is ETH (Ethereum, Arbitrum,
    # ...). A chain with a native coin of its own (Avalanche) is worth a different amount per unit and overrides it.
    native_dust_threshold = '0.0000001'

    def __init__(self):
        super().__init__()
        self._new_cursor = ''
        # Block from which this fetch could no longer read the history, see _note_window_limit(). None = it read
        # everything the chain had.
        self._window_limit = None

    # ------------------------------------------------------------------------------------------------------------------
    def _api_key(self) -> str:
        key = JalSettings().getStr(self.api_key_setting).strip()
        if not key:
            raise Statement_ImportError(
                self.tr("API key isn't set - fill it in Settings/Preferences/Blockchain: ") + self.api_name)
        return key

    # The wallet address, lower-cased the way every EVM address is stored and the way Etherscan returns 'from'/'to',
    # so a direct string comparison decides the direction of a transfer.
    def _address(self) -> str:
        return normalize_address(self.location_id, self._account.address())

    def _norm(self, address: str) -> str:
        return normalize_address(self.location_id, address)

    # Executes one paged GET against an 'account' action and returns the 'result' list. Paging is by page number
    # (the API caps 'offset' at page_size), and a short page means the history is exhausted.
    def _get_pages(self, action: str, start_block: int) -> list:
        records = []
        for page in range(1, self.max_pages + 1):
            params = {"chainid": self.chain_id, "module": "account", "action": action,
                      "address": self._account.address(), "startblock": start_block, "endblock": _MAX_BLOCK,
                      "page": page, "offset": self.page_size, "sort": "asc", "apikey": self._api_key()}
            request = WebRequest(WebRequest.GET, self.api_root, params=params)
            self._wait_for(request)
            try:
                answer = json.loads(request.data())
            except (json.JSONDecodeError, TypeError):
                raise Statement_ImportError(self.tr("Unexpected answer from the blockchain API: ")
                                            + f"{self.api_name}: {request.data()}")
            result = answer.get('result', [])
            # status=0 is both "no transactions" (an ordinary empty history) and a real error (a bad key, a rate
            # limit); the two are told apart by the message, since only the error carries a string result.
            if str(answer.get('status', '0')) != '1':
                if answer.get('message', '') == _NO_TRANSACTIONS:
                    break
                raise Statement_ImportError(self.tr("Blockchain API request failed: ")
                                            + f"{self.api_name}: {result or answer}")
            records += result
            self._report_page()
            if len(result) < self.page_size:
                break
        else:
            self._note_window_limit(action, records)
        return records

    # Called when an endpoint used up its whole page budget while its pages were still full: whatever comes after the
    # last record it returned could not be read in THIS fetch, because the provider caps how deep one query may be
    # paged and/or because max_pages stopped the loop.
    #
    # Nothing is lost by that - the cap is per query and 'startblock' opens a fresh window, so the next fetch reads on
    # from where this one stopped. What WOULD lose data is letting the cursor past the point where reading stopped:
    # the three endpoints are paged independently and run out at different blocks, and a cursor taken from the one
    # that reached furthest would jump over records another one never delivered, never to be asked for again. So the
    # lowest block at which any endpoint stopped is remembered and _fetch() imports strictly below it.
    #
    # That block is itself the limit rather than the one after it: reading stopped in the middle of it, so part of it
    # may be missing. (A single block holding a whole budget's worth of records for one address would therefore make
    # no progress at all - it is logged as the incomplete fetch it is, and no cursor is stored.)
    def _note_window_limit(self, action: str, records: list) -> None:
        logging.warning(self.tr("Too many pages returned, the rest is left for the next fetch: ")
                        + f"{self.api_name}/{action}")
        if not records:
            return
        block = self._block_of(records[-1])
        self._window_limit = block if self._window_limit is None else min(self._window_limit, block)

    # Drops the transactions at or above the block where reading stopped (see _note_window_limit), so that the cursor
    # this fetch returns can never point past a transaction it hasn't seen. They are reported as skipped rather than
    # dropped silently, and the next fetch starts at exactly that block.
    def _within_window(self, transactions: list) -> list:
        if self._window_limit is None:
            return transactions
        kept = []
        for tx in transactions:
            if tx['block'] < self._window_limit:
                kept.append(tx)
            else:
                self._skip(self.tr("beyond what one fetch can read - it will be fetched next time"), tx['hash'])
        return kept

    # The cursor is the block number of the last imported transaction; the next fetch starts at the following block.
    # A block is immutable once mined, so everything up to and including the cursor block was already seen in full.
    def _start_block(self) -> int:
        cursor = self._cursor()
        try:
            return int(cursor) + 1
        except (TypeError, ValueError):
            return 0

    # ------------------------------------------------------------------------------------------------------------------
    def _fetch(self) -> str:
        address = self._address()
        if not is_evm_address(address):
            raise Statement_ImportError(self.tr("Not a valid EVM address: ") + address)
        start_block = self._start_block()
        self._window_limit = None
        native = self._get_pages("txlist", start_block)
        tokens = self._get_pages("tokentx", start_block)
        internal = self._get_pages("txlistinternal", start_block)
        transactions = self._within_window(self._group_by_transaction(native, tokens, internal))

        # Transactions are imported in block order. When the classifier meets a shape it can't support it raises
        # _HaltImport: the current block is rolled back whole and the import stops there, keeping every earlier block
        # (which is complete and safe) and parking the cursor just before the halting block. The next fetch resumes
        # from that block and re-tries it - so once the protocol registry or a new operation type catches up, the
        # transaction imports on its own without any manual replay. A block is committed atomically: its operations
        # become safe only once the whole block has classified without a halt.
        last_safe_block = start_block - 1
        checkpoint = self._checkpoint()
        current_block = None
        for tx in transactions:
            if current_block is not None and tx['block'] != current_block:
                last_safe_block = current_block
                checkpoint = self._checkpoint()
            current_block = tx['block']
            try:
                self._classify_transaction(tx)
            except _HaltImport as halt:
                self._restore(checkpoint)   # drop this block's partial operations - it is retried next fetch
                self._skip(self.tr("import stopped at an unsupported transaction (") + halt.reason
                           + self.tr("); it will be retried next time"), tx['hash'])
                return str(last_safe_block) if last_safe_block >= start_block else ''
        latest = current_block if current_block is not None else start_block - 1
        return str(latest) if latest >= start_block else ''

    # Groups the three endpoints' records by transaction hash and returns them ordered by (block, position-in-block),
    # so classification sees whole transactions in the exact order they were mined.
    def _group_by_transaction(self, native: list, tokens: list, internal: list) -> list:
        transactions = {}

        def bucket(record: dict, leg: str) -> None:
            tx_hash = record.get('hash', '')
            tx = transactions.get(tx_hash)
            if tx is None:
                tx = {'hash': tx_hash, 'block': self._block_of(record), 'order': self._index_of(record),
                      'timestamp': self._timestamp_of(record), 'native': [], 'tokens': [], 'internal': []}
                transactions[tx_hash] = tx
            tx[leg].append(record)

        for record in native:
            bucket(record, 'native')
        for record in tokens:
            bucket(record, 'tokens')
        for record in internal:
            bucket(record, 'internal')
        return sorted(transactions.values(), key=lambda t: (t['block'], t['order'], t['hash']))

    # Snapshot of how many operations (and assets) each JSF section holds, used to roll a partially-built block back.
    def _checkpoint(self) -> dict:
        return {section: len(self._data.get(section, [])) for section in
                (JSF.ASSETS, JSF.TRANSFERS, JSF.ASSET_PAYMENTS, JSF.SWAPS, JSF.BRIDGES, JSF.CONVERSIONS)}

    # Discards everything appended since the checkpoint - the operations of the halting block and any asset records it
    # created (a still-unused asset is harmless, but dropping it keeps the statement identical to a clean re-fetch).
    def _restore(self, checkpoint: dict) -> None:
        for section, length in checkpoint.items():
            if section in self._data:
                del self._data[section][length:]

    # ------------------------------------------------------------------------------------------------------------------
    # Classifies a whole transaction into one operation. The wallet's asset movements are netted per asset first, then
    # the shape (what left, what arrived) plus the contract the wallet interacted with decide the operation.
    def _classify_transaction(self, tx: dict) -> None:
        own_record = self._own_record(tx)
        own = own_record is not None
        gas = self._gas_of(own_record) if own else Decimal('0')
        is_error = own and own_record.get('isError', '0') == '1'
        timestamp = tx['timestamp']

        deltas = self._wallet_deltas(tx)
        # Address-poisoning dust is pulled out before anything below looks at 'deltas': it is never part of a
        # swap/lending/bridge shape, and left in it would skew that classification (a real single-asset receive
        # would suddenly look like two assets moving). See _extract_native_dust.
        self._extract_native_dust(deltas, timestamp, tx['hash'])
        self._extract_poisoning_dust(deltas, timestamp, tx['hash'])
        outs = {asset_id: data for asset_id, data in deltas.items() if data['amount'] < 0}
        ins = {asset_id: data for asset_id, data in deltas.items() if data['amount'] > 0}
        contract = self._norm(own_record.get('to', '')) if own else ''
        category = protocol_category(self.location_id, contract)
        protocol = protocol_name(self.location_id, contract)

        # Nothing moved: an approval, a reverted transaction, or a contract call whose only effect was spam we
        # filtered out. If it was the wallet's own transaction its gas is still charged as a GasFee.
        if not outs and not ins:
            if own and gas > Decimal('0'):
                self._add_payment(JSF.PAYMENT_GAS_FEE, timestamp, self._native_asset_id(), gas, tx['hash'],
                                  note=self._gas_note(own_record, is_error))
            return
        contract, category, protocol = self._forwarded_protocol(own, outs, ins, contract, category, protocol)

        if category == ProtocolCategory.LENDING:
            # One asset in, one out - supplying to (or withdrawing from) a lending protocol, wrapping a coin, or
            # staking it: the position is kept, only its shape changes, so it is a basis-preserving Conversion.
            if len(outs) == 1 and len(ins) == 1:
                return self._emit_conversion(timestamp, outs, ins, tx['hash'], gas)
            # A protocol may also just pay out - a reward accrued on the supplied position, delivered with nothing
            # going the other way. That is a real inflow with no counterpart, which is what a StakingReward is.
            if ins and not outs:
                return self._emit_rewards(timestamp, ins, tx['hash'], gas, is_error, own_record)
            raise _HaltImport(self.tr("unrecognized lending/wrap shape"))
        if category == ProtocolCategory.BRIDGE:
            return self._emit_cross_chain_leg(timestamp, deltas, outs, ins, tx['hash'], gas, own_record, is_error,
                                              protocol, contract)
        if category == ProtocolCategory.REWARD:
            if ins and not outs:
                return self._emit_rewards(timestamp, ins, tx['hash'], gas, is_error, own_record)
            raise _HaltImport(self.tr("unrecognized reward-claim shape"))
        if category == ProtocolCategory.CUSTODY:
            # The contract keeps the asset on the wallet's behalf and hands back no receipt token, so nothing about
            # the position changes hands: what leaves is still owned, what comes back was owned all along. Both
            # directions are therefore plain transfers - never income (which is what REWARD would make of a return of
            # the wallet's own money) and never a disposal. The counterparty is an address JAL doesn't know, so the
            # import asks which account it stands for, and the balance lives on in that account. Anything the position
            # earned inside the container is invisible here and stays unrecognized until it is actually claimed.
            if outs and ins:   # something was given back in exchange - that is not custody, don't guess at it
                raise _HaltImport(self.tr("unrecognized custody shape"))
            return self._emit_transfers(timestamp, deltas, tx['hash'], gas, own_record, is_error,
                                        mark=self._custody_mark(protocol))

        swap_shape = len(outs) == 1 and len(ins) == 1
        if category == ProtocolCategory.SWAP:
            if swap_shape:
                return self._emit_swap(timestamp, outs, ins, tx['hash'], gas)
            raise _HaltImport(self.tr("unrecognized swap shape"))
        if category == ProtocolCategory.AGGREGATOR:
            if swap_shape:                                 # both legs on this chain -> a same-chain swap
                return self._emit_swap(timestamp, outs, ins, tx['hash'], gas)
            # a single leg -> one side of a cross-chain move, whose counterpart lives on another chain
            return self._emit_cross_chain_leg(timestamp, deltas, outs, ins, tx['hash'], gas, own_record, is_error,
                                              protocol, contract)

        # A swap the wallet never signed. An intent-based DEX (CoW Protocol, and the same way 1inch Fusion, UniswapX
        # or 0x Settler work) is gasless for the user: the order is signed off-chain and a SOLVER submits the batch
        # that settles it, so the wallet is neither the 'from' nor the 'to' of the transaction and appears only in its
        # token/internal legs. There is no own record, hence no interacted-with contract and no category above - and
        # the transaction would fall through to two plain transfers, which is what it did.
        # The protocol is therefore read off the address the assets actually moved with, and only when BOTH sides
        # moved with that same one: that is what makes the pair one exchange rather than two movements that happen to
        # share a hash. The fee is not lost by taking gas as zero - the wallet paid none, and the protocol's own fee
        # is already inside the amounts the chain reports.
        if not own and swap_shape and self._settling_swap_protocol(outs, ins):
            return self._emit_swap(timestamp, outs, ins, tx['hash'], Decimal('0'))

        # ... and a reward CLAIMED FOR this wallet rather than BY it. Merkl and the other distributors let anyone
        # submit the claim on a recipient's behalf, so the beneficiary may sign nothing and pay no gas: the wallet
        # then appears only in the token leg, exactly as above, and the payout falls through to a plain incoming
        # transfer - a leg no settlement can ever pair, opened at a zero cost basis, with the income never recognized.
        #
        # What makes it readable is the registry entry itself, and only that. A REWARD contract is by definition one
        # that pays out a CLAIMABLE reward - it pays what the recipient earned, whoever presses the button - and the
        # category is decided per address by hand, with the returned-principal cases deliberately kept out of it
        # (stake.link's PriorityPool is CUSTODY and not REWARD for exactly that reason, see protocols.py). So who
        # signed says nothing here that the payer's address doesn't already say, which is as well: the signer is not
        # in what a fetch reads at all - 'txlist' returns only the transactions the wallet is the 'from' or 'to' of,
        # and this one is neither.
        #
        # Gas is taken as zero because the wallet paid none; whoever signed the claim books it on their own account.
        if not own and ins and not outs and self._claimed_reward_protocol(ins):
            return self._emit_rewards(timestamp, ins, tx['hash'], Decimal('0'), is_error, None)

        # From here the contract (if any) is unregistered. A transaction the wallet signed that both spends and
        # receives an asset is a swap/lending/bridge through an unknown contract - it must never be guessed at
        # (reconciliation (a)); likewise an unfamiliar multi-asset shape or an own-initiated pure acquisition (a
        # claim whose cost basis we can't establish) halts, to be revisited once the registry knows the contract.
        if own and swap_shape:
            # Naming the contract lets the user add it to the protocol registry with the right category and re-fetch.
            raise _HaltImport(self.tr("asset exchange through an unregistered contract ") + contract)
        if own and outs and ins:
            raise _HaltImport(self.tr("unrecognized multi-asset transaction"))
        if own and ins and not outs:
            raise _HaltImport(self.tr("incoming asset through an unregistered contract"))

        # What is left is a plain transfer: assets sent out (a payment, a deposit to an exchange) or received from the
        # outside world (an ordinary receive, an airdrop that passed the spam filter).
        self._emit_transfers(timestamp, deltas, tx['hash'], gas, own_record, is_error)

    # Emits the wallet's movements as plain transfers, one per asset. The gas of the wallet's own send rides its
    # outgoing leg, the way a broker's transfer fee does; a transaction that only received pays it as a GasFee.
    #
    # 'mark' is set when a transfer is all this classification can record of something bigger (a custody movement, an
    # arriving bridge leg): it goes in front of the counterparty note, so both the ledger and the account-selection
    # dialog of the import say what the operation still needs - see TransferMark.
    def _emit_transfers(self, timestamp: int, deltas: dict, tx_hash: str, gas: Decimal,
                        own_record, is_error: bool, mark: str = '') -> None:
        remaining_gas = gas
        for asset_id, data in sorted(deltas.items()):
            incoming = data['amount'] > Decimal('0')
            fee = Decimal('0')
            if not incoming and remaining_gas > Decimal('0'):
                fee, remaining_gas = remaining_gas, Decimal('0')
            self._add_transfer(timestamp, asset_id, abs(data['amount']), incoming, tx_hash,
                               note=self._joined_note(mark, data['note']),
                               fee=fee, fee_asset_id=self._native_asset_id() if fee > Decimal('0') else None,
                               counterparty=data['counterparty'] or '')
        if own_record is not None and remaining_gas > Decimal('0'):
            self._add_payment(JSF.PAYMENT_GAS_FEE, timestamp, self._native_asset_id(), remaining_gas, tx_hash,
                              note=self._gas_note(own_record, is_error))

    # ------------------------------------------------------------------------------------------------------------------
    # Resolves a protocol the wallet reached THROUGH a token instead of calling it, as the (contract, category,
    # protocol) the classification should go on with - unchanged when there is nothing to resolve.
    #
    # A transaction is classified by the contract the WALLET CALLED, which is the right question to ask: that contract
    # is what the user chose to deal with, and an address the money merely passed through (a bridge's token pool) says
    # nothing about the operation. But a token implementing ERC-677 transferAndCall() carries the call itself - the
    # wallet calls the TOKEN, the token forwards the coins onwards, and the transaction names the token as the
    # contract it interacted with. Queueing LINK into stake.link's PriorityPool is exactly that, and it is why the
    # answer can't be a registry entry on LINK: LINK is an ordinary coin sent to ordinary addresses every day, while
    # the pool it was forwarded to is a protocol whichever route the coins took to reach it.
    #
    # So when the contract the wallet called is not a protocol JAL knows, where the money ACTUALLY WENT is asked
    # instead - and only in the shape a forwarding call has:
    #   * the wallet signed the transaction (what a contract does to the wallet's tokens on somebody else's
    #     transaction is not a choice of the wallet's, and is read by the rules at the end of the classification);
    #   * assets left and nothing came back - anything given in exchange makes this a trade of some kind, which is
    #     told apart by the contract the user picked and not by an address the coins travelled through;
    #   * every outgoing leg went to one and the same registered address, so there is a single protocol to name.
    # An address that resolves to no registry entry changes nothing, which is the normal case: a plain transfer to
    # somebody's wallet lands here and leaves exactly as it arrived.
    def _forwarded_protocol(self, own: bool, outs: dict, ins: dict, contract: str, category, protocol: str):
        if category is not None or not own or not outs or ins:
            return contract, category, protocol
        destinations = {address for data in outs.values() for address in data['sent_to']}
        if len(destinations) != 1:
            return contract, category, protocol
        destination = destinations.pop()
        forwarded = protocol_category(self.location_id, destination)
        if forwarded is None:
            return contract, category, protocol
        return destination, forwarded, protocol_name(self.location_id, destination)

    # The wallet's net movement per asset in this transaction: incoming amounts positive, outgoing negative, summed
    # across the native, internal and (spam-filtered) token legs. Gas is NOT part of it - it is charged separately.
    # Net-zero assets (a token routed in and back out) are dropped, so only what actually changed hands remains.
    def _wallet_deltas(self, tx: dict) -> dict:
        deltas = defaultdict(lambda: {'amount': Decimal('0'), 'note': '', 'counterparty': None, 'sent_to': set()})
        for record in tx['native'] + tx['internal']:      # native coin, moved directly or by a contract
            signed = self._native_signed_amount(record)
            if signed != Decimal('0'):
                entry = deltas[self._native_asset_id()]
                entry['amount'] += signed
                entry['note'] = entry['note'] or self._counterparty_note(record)
                self._merge_counterparty(entry, self._counterparty_of(record), signed)
        for record in tx['tokens']:
            leg = self._token_leg(record, tx)
            if leg is not None:
                asset_id, signed, note, counterparty = leg
                entry = deltas[asset_id]
                entry['amount'] += signed
                entry['note'] = entry['note'] or note
                self._merge_counterparty(entry, counterparty, signed)
        return {asset_id: data for asset_id, data in deltas.items() if data['amount'] != Decimal('0')}

    # Pulls the native coin's entry out of 'deltas' and records it as a DustAttack payment instead, when it is
    # incoming, below the chain's threshold, and not from a wallet of the user's own - address-poisoning dust, the
    # same shape tron.py and solana.py record. It is still real coin that changed the wallet's balance - unlike a
    # token it carries no contract and can't be a honeypot - so it is imported, just not counted towards the
    # swap/lending/bridge shape the rest of the transaction is classified by (see the call site).
    def _extract_native_dust(self, deltas: dict, timestamp: int, tx_hash: str) -> None:
        native_id = self._native_asset_id()
        entry = deltas.get(native_id)
        if entry is None or entry['amount'] <= Decimal('0'):
            return
        if self._is_native_dust(entry['amount'], self._is_own_address(entry['counterparty'] or '')):
            self._add_payment(JSF.PAYMENT_DUST_ATTACK, timestamp, native_id, entry['amount'], tx_hash,
                              note=entry['note'])
            del deltas[native_id]

    # Pulls out every incoming delta that came from an address minted to be mistaken for one of the user's own, and
    # records it as a DustAttack payment instead - address poisoning, of the kind the native-coin rule above catches
    # by size. Here the size is no help: the token arrives as the GENUINE asset (real USDT, in the wallet this was
    # written for), so it passes the spam filter on the allow-list before its value is ever weighed, and the amount
    # is trivial only by convention rather than by any rule. What gives it away is the sender - see
    # jal/db/address_match.py on why the resemblance can't be an accident.
    #
    # Nothing is blacklisted: the blacklist is keyed by the token's CONTRACT, and the contract here is the real one,
    # so quarantining it would throw away every future transfer of an asset the user holds for real.
    #
    # It is taken out before the transaction is classified for the same reason the native dust is: the coins are
    # real and are imported, but they are nobody's half of anything, and leaving them among the deltas would make a
    # plain receive look like two assets moving and a swap look like three.
    def _extract_poisoning_dust(self, deltas: dict, timestamp: int, tx_hash: str) -> None:
        for asset_id, entry in list(deltas.items()):
            if entry['amount'] <= Decimal('0') or not entry['counterparty']:
                continue
            impersonated = impersonated_target(self.location_id, entry['counterparty'])
            if impersonated is None:
                continue
            self._add_payment(JSF.PAYMENT_DUST_ATTACK, timestamp, asset_id, entry['amount'], tx_hash,
                              note=self.tr("Address poisoning, imitating ") + impersonated['name'])
            del deltas[asset_id]

    # Records the address an asset's movement was with, and clears it as soon as a second one takes part: the delta
    # is a NET amount, so an account may only be put on it when every leg that formed it was with that same address.
    # A cleared counterparty leaves the far side of the transfer unresolved, exactly as an outside address does.
    #
    # 'sent_to' collects the same addresses but from the OUTGOING legs alone, and is never cleared. The two answer
    # different questions: 'counterparty' asks who the whole net movement was with (which nothing can answer once
    # several addresses took part), while 'sent_to' asks where the wallet's money actually went - a question each leg
    # answers for itself, and which stays answerable however many addresses paid something back. See
    # _take_messaging_fee for what needs the difference.
    def _merge_counterparty(self, entry: dict, counterparty: str, signed: Decimal) -> None:
        counterparty = self._norm(counterparty)
        if signed < Decimal('0'):
            entry['sent_to'].add(counterparty)
        if entry['counterparty'] is None:
            entry['counterparty'] = counterparty
        elif entry['counterparty'] != counterparty:
            entry['counterparty'] = ''

    # Signed native amount of a single txlist/internal record for the wallet (+ received, - sent, 0 if unrelated or
    # reverted). Dust is not judged per record - several tiny legs of one transaction could net into a real amount,
    # or vice versa - the net total _wallet_deltas() builds from these is what _extract_native_dust() judges.
    def _native_signed_amount(self, record: dict) -> Decimal:
        if record.get('isError', '0') == '1':
            return Decimal('0')
        amount = self._wei(record.get('value', '0'))
        if amount <= Decimal('0'):
            return Decimal('0')
        address = self._address()
        if self._norm(record.get('to', '')) == address:
            return amount
        if self._norm(record.get('from', '')) == address:
            return -amount
        return Decimal('0')

    # One token leg as (asset_id, signed_amount, note, counterparty), or None when the leg carries nothing importable
    # (a malformed contract, a zero-value event, or a token the spam filter quarantined). The spam policy is unchanged
    # from the per-leg version: provenance decides trust - only a transaction the wallet itself signed is user-driven, so any
    # other event, whichever direction it claims, must face the dust filter (a spoofed 'outgoing' fake-USDT otherwise
    # sails in, because the shared filter never treats an outgoing transfer as dust).
    #
    # Signing the transaction is not the only proof the user chose the token, though: a leg that moved with a
    # REGISTERED swap protocol was chosen too, even when a solver submitted the settlement (see the gasless-swap
    # branch of _classify_transaction - without this a legitimate swap into a thinly-priced token has one of its two
    # legs quarantined as spam, and what is left of the exchange is a lone transfer). A REWARD payer counts for the
    # same reason and would otherwise break the same way: a reward CLAIMED FOR the wallet by somebody else is signed
    # by nobody the filter can see, so a thinly-priced reward token would be quarantined and the claim would come out
    # empty (see _claimed_reward_protocol). It is not a hole a spoofer can use: the registry is curated by hand, and
    # the address checked is the real counterparty of the transfer event rather than anything the token itself claims
    # about its name or ticker.
    def _token_leg(self, record: dict, tx: dict):
        address = self._norm(record.get('contractAddress', ''))
        tx_hash = record.get('hash', '')
        if not is_evm_address(address):
            self._skip(self.tr("token with a malformed contract address"), tx_hash)
            return None
        symbol, name = record.get('tokenSymbol', ''), record.get('tokenName', '')
        incoming = self._norm(record.get('to', '')) == self._address()
        try:
            decimals = int(record.get('tokenDecimal', '0'))
            amount = Decimal(record.get('value', '0')) / (Decimal('10') ** decimals)
        except (ValueError, ArithmeticError):
            self._skip(self.tr("token transfer with an unreadable amount"), tx_hash)
            return None
        if amount <= Decimal('0'):
            self._skip(self.tr("zero-amount token transfer"), tx_hash)
            return None
        initiated = self._own_record(tx) is not None
        counterparty = record.get('from', '') if incoming else record.get('to', '')
        chosen = initiated or protocol_category(self.location_id, counterparty) in (ProtocolCategory.SWAP,
                                                                                   ProtocolCategory.AGGREGATOR,
                                                                                   ProtocolCategory.REWARD)
        candidate = TokenCandidate(location_id=self.location_id, address=address, symbol=symbol, name=name,
                                   incoming=incoming or not initiated, from_swap=chosen, amount=amount,
                                   known_counterparty=self._is_own_address(counterparty),
                                   value=self._value_of(address, amount, self._timestamp_of(record)))
        if not self._filter.accept(candidate):
            self._skip(self.tr("token quarantined as dust/spam"), tx_hash)
            return None
        asset_id = self._token_asset_id(symbol, name, address=address)
        return asset_id, (amount if incoming else -amount), self._counterparty_note(record), counterparty

    # The name of the swap protocol that moved BOTH sides of a transaction the wallet did not sign, or '' when there
    # is none - see the call site for what it is for.
    #
    # Every leg has to name one and the same counterparty: a delta whose counterparty was cleared (several addresses
    # took part in it, see _merge_counterparty) or that names a different address than the other side is not a
    # settlement, and an unregistered address is not a protocol JAL may classify by. Only the two categories that
    # exchange one asset for another on this chain count - a lending or custody contract acting on a wallet that
    # never asked it to is a shape no evidence covers, and it keeps being imported as the plain transfer it is.
    # (A REWARD payer is the one exception, and it is read separately - see _claimed_reward_protocol.)
    def _settling_swap_protocol(self, outs: dict, ins: dict) -> str:
        counterparties = {data['counterparty'] for data in list(outs.values()) + list(ins.values())}
        if len(counterparties) != 1:
            return ''
        address = counterparties.pop() or ''
        if protocol_category(self.location_id, address) not in (ProtocolCategory.SWAP, ProtocolCategory.AGGREGATOR):
            return ''
        return protocol_name(self.location_id, address)

    # The name of the REWARD protocol that paid EVERY incoming leg of a transaction the wallet did not sign, or ''
    # when there is none - see the call site for what it is for.
    #
    # The demand made of the counterparty is the same one above: every leg has to name one and the same address, so
    # a delta whose counterparty was cleared (several addresses took part in it, see _merge_counterparty) names
    # nobody and settles nothing. Two distributors paying into one transaction is left alone rather than guessed at.
    def _claimed_reward_protocol(self, ins: dict) -> str:
        payers = {data['counterparty'] for data in ins.values()}
        if len(payers) != 1:
            return ''
        payer = payers.pop() or ''
        if protocol_category(self.location_id, payer) != ProtocolCategory.REWARD:
            return ''
        return protocol_name(self.location_id, payer)

    # Emits a swap: one asset out, one asset in, gas paid in the native coin as the fee.
    def _emit_swap(self, timestamp: int, outs: dict, ins: dict, tx_hash: str, gas: Decimal) -> None:
        out_asset, out_data = next(iter(outs.items()))
        in_asset, in_data = next(iter(ins.items()))
        self._add_swap(timestamp, out_asset, abs(out_data['amount']), in_asset, in_data['amount'], tx_hash,
                       fee=gas, fee_asset_id=self._native_asset_id() if gas > Decimal('0') else None)

    # Emits one leg of a cross-chain move - the fetched wallet is on a single chain, so it sees only one of them and
    # the two legs are paired later (BridgeMatcher). What the move IS can't be decided here: sending an asset into a
    # bridge/aggregator looks identical whether the same asset comes back on the other chain (a bridge) or another one
    # does (a cross-chain swap), so only the sending leg is recorded as a pending half-bridge and the pairing decides.
    #   * one out, none in -> the sending leg: a pending half-bridge, the gas of the send rides it;
    #   * one in, none out -> the arriving leg: NOTHING here tells what was sent for it (a relayer usually delivers it
    #     as an ordinary receive anyway), so it is imported as a plain incoming transfer, exactly like the relayed
    #     ones, and the user pairs it with its pending sending half by hand.
    # A cross-chain move that both spends and receives on the same chain isn't a shape we recognize, so it halts.
    def _emit_cross_chain_leg(self, timestamp: int, deltas: dict, outs: dict, ins: dict, tx_hash: str, gas: Decimal,
                              own_record, is_error: bool, protocol: str = '', contract: str = '') -> None:
        gas += self._take_messaging_fee(deltas, outs, contract)
        if len(outs) == 1 and not ins:
            asset_id, data = next(iter(outs.items()))
            # The half is already an operation of its own kind, so it needs no mark - but naming the protocol it went
            # through helps the user recognize its counterpart when the matcher offers the candidates.
            self._add_bridge_half(timestamp, asset_id, abs(data['amount']), tx_hash,
                                  note=(self.tr("Sent through ") + protocol) if protocol else '',
                                  fee=gas, fee_asset_id=self._native_asset_id() if gas > Decimal('0') else None)
            return
        if len(ins) == 1 and not outs:
            # Marked as the arriving leg it is: the pending half it belongs to was fetched from another chain (or is
            # not fetched yet), and nothing in this transaction can point at it - only the user can.
            self._emit_transfers(timestamp, deltas, tx_hash, gas, own_record, is_error,
                                 mark=self._bridge_arrival_mark(protocol))
            return
        raise _HaltImport(self.tr("unrecognized cross-chain transaction shape"))

    # Takes the protocol's MESSAGING FEE out of a cross-chain send and returns it, to be charged with the gas.
    #
    # A LayerZero OFT - which is what USDT0 is - is paid for delivering the message in native coin, sent to the very
    # contract the asset is being bridged through, in the same transaction. On the chain that looks like two assets
    # leaving at once, and the shape below would refuse it: "one asset out" is what a crossing is, and the second
    # one would halt the import of every send the wallet ever makes through such a bridge.
    #
    # It is not a second asset crossing, though - nothing of it arrives anywhere. It is a cost of the transfer, the
    # same kind of thing as the gas it is folded into, and charging it that way is what keeps the amount that
    # actually crossed equal to the amount that arrives.
    #
    # Narrow on purpose: only the native coin, only when it went to the very contract being classified by (a native
    # amount to anyone else is a movement of its own), and only when something else left too - a send of nothing but
    # native coin IS the asset being bridged, and taking it as a fee would leave a crossing of nothing.
    #
    # "Went to the contract" is asked of the OUTGOING legs ('sent_to'), not of the delta's net counterparty. The fee
    # is quoted before the transaction runs and the wallet has to cover it in full, so a protocol that settles for
    # less REFUNDS the excess in the same transaction - and a LayerZero OFT pays that refund out of its endpoint,
    # which is not the contract the asset was bridged through. That second address is what a net counterparty cannot
    # survive (_merge_counterparty clears it), and judging by it would refuse every refunded send while accepting the
    # unrefunded one - the same operation, told apart by nothing that concerns the user. What the refund does to the
    # amount needs no handling at all: the delta is already net of it, which is exactly the fee that was really paid.
    def _take_messaging_fee(self, deltas: dict, outs: dict, contract: str) -> Decimal:
        native = self._native_asset_id()
        if not contract or len(outs) < 2 or native not in outs:
            return Decimal('0')
        if outs[native]['sent_to'] != {self._norm(contract)}:
            return Decimal('0')
        fee = abs(outs[native]['amount'])
        del outs[native]
        deltas.pop(native, None)
        return fee

    # Emits a conversion: the position is kept but changes shape (supply/withdraw a lending position, wrap/unwrap,
    # liquid staking). No profit or loss is realized and the quantity is free to differ - a rebasing receipt token
    # folds the yield accrued since the last interaction into the amount it mints or burns. Gas is the fee.
    def _emit_conversion(self, timestamp: int, outs: dict, ins: dict, tx_hash: str, gas: Decimal) -> None:
        out_asset, out_data = next(iter(outs.items()))
        in_asset, in_data = next(iter(ins.items()))
        self._add_conversion(timestamp, out_asset, abs(out_data['amount']), in_asset, in_data['amount'], tx_hash,
                             fee=gas, fee_asset_id=self._native_asset_id() if gas > Decimal('0') else None)

    # Emits claimed rewards as StakingReward payments (each opens a lot at market value, so a reward has a cost
    # basis), plus the claim's gas as a separate GasFee. One claim can pay out in SEVERAL assets at once - a single
    # Merkl claim delivered stkGHO and aEthUSDG together - so each received asset gets a payment of its own.
    def _emit_rewards(self, timestamp: int, ins: dict, tx_hash: str, gas: Decimal,
                      is_error: bool, own_record: dict) -> None:
        for asset_id, data in sorted(ins.items()):
            self._add_payment(JSF.PAYMENT_STAKING_REWARD, timestamp, asset_id, data['amount'], tx_hash,
                              note=self.tr("Reward claim"))
        if gas > Decimal('0'):
            self._add_payment(JSF.PAYMENT_GAS_FEE, timestamp, self._native_asset_id(), gas, tx_hash,
                              note=self._gas_note(own_record, is_error))

    # The wallet's own top-level record of the transaction (from == wallet), or None when the wallet only received or
    # was merely named by an event it never signed. Its presence is what "the wallet initiated this" means, and it
    # carries the gas, the interacted-with contract ('to') and the method selector.
    def _own_record(self, tx: dict):
        for record in tx['native']:
            if self._norm(record.get('from', '')) == self._address():
                return record
        return None

    # Gas the wallet paid for a transaction it initiated: gasUsed * gasPrice, in the native coin.
    def _gas_of(self, record: dict) -> Decimal:
        try:
            return Decimal(record.get('gasUsed', '0')) * Decimal(record.get('gasPrice', '0')) / _WEI
        except (ArithmeticError, TypeError):
            return Decimal('0')

    def _wei(self, value) -> Decimal:
        try:
            return Decimal(value) / _WEI
        except (ArithmeticError, TypeError):
            return Decimal('0')

    def _index_of(self, record: dict) -> int:
        try:
            return int(record.get('transactionIndex', 0))
        except (TypeError, ValueError):
            return 0

    # Describes what the gas was spent on: Etherscan reports a reverted transaction through 'isError', and the
    # method selector tells an approval from any other call (CRYPTO_PATH decision #32).
    def _gas_note(self, record: dict, is_error: bool) -> str:
        if is_error:
            return self.tr("Gas: failed transaction")
        if record.get('methodId', '') == _METHOD_APPROVE:
            return self.tr("Gas: token approval")
        return self.tr("Gas: contract call")

    # ------------------------------------------------------------------------------------------------------------------
    # Value of the transfer in the account currency, or None when the token can't be priced. A token JAL already
    # holds is priced from its stored quotes; a token seen for the first time has none, and None is what tells the
    # filter it can't judge the transfer by value (it then relies on the allow-list and the counterparty instead).
    def _value_of(self, address: str, amount: Decimal, timestamp: int):
        id_type = AssetLocation.address_id_of(self.location_id)
        symbol = JalSymbol.find_by_identifier(id_type, address)
        if not symbol.id():
            return None
        rate = symbol.asset().quote(timestamp, self._account.currency())[1]
        return amount * rate if rate else None

    def _block_of(self, record: dict) -> int:
        try:
            return int(record.get('blockNumber', 0))
        except (TypeError, ValueError):
            return 0

    def _timestamp_of(self, record: dict) -> int:
        # Etherscan reports seconds of true UTC time; JAL stores seconds in its own local-wall-clock convention.
        try:
            seconds = int(record.get('timeStamp', 0))
        except (TypeError, ValueError):
            seconds = 0
        return self._local_timestamp(seconds)

    # The counterparty addresses are put in the note only when the other side is NOT an account JAL already knows:
    # a transfer between two of the user's own wallets needs no address note, while an outside address is worth
    # recording so the user can identify (or later name) the counterparty. Sender is shown first.
    def _counterparty_note(self, record: dict) -> str:
        sender, receiver = record.get('from', ''), record.get('to', '')
        if self._is_known_account(self._counterparty_of(record)):
            return ''
        return f"{sender} → {receiver}"

    # The far side of a record: whichever of its two addresses is not the wallet being fetched
    def _counterparty_of(self, record: dict) -> str:
        sender, receiver = record.get('from', ''), record.get('to', '')
        return sender if self._norm(receiver) == self._address() else receiver

    # True if the address belongs to any wallet account JAL holds (on any chain - an EVM address is shared across
    # EVM chains, and addresses of different chains never collide, so a cross-chain check is safe). That breadth
    # suits a note, which only says whether the address is one of the user's; picking the ACCOUNT a transfer is
    # booked on is a different question, and ChainFetcher._own_wallet answers it for this chain alone.
    def _is_known_account(self, address: str) -> bool:
        address = self._norm(address)
        if not address:
            return False
        for account in JalAccount.get_all_accounts(active_only=True):
            if account.account_type() == PredefinedAccountType.Wallet and \
                    normalize_address(account.chain(), account.address()) == address:
                return True
        return False


SettingsRegistry.register(SettingDescriptor(
    key="DustThreshold_ETH",
    page=QT_TRANSLATE_NOOP("Preferences", "Blockchain"),
    label=QT_TRANSLATE_NOOP("Preferences", "ETH dust threshold"), default=EVMFetcher.native_dust_threshold,
    tooltip=QT_TRANSLATE_NOOP("Preferences",
                              "An incoming ETH transfer below this amount, from an address you never dealt with, "
                              "is recorded as a dust attack instead of an ordinary transfer. Applies to every EVM "
                              "chain whose native coin is ETH (Ethereum, Arbitrum, ...); a chain with a coin of its "
                              "own has a threshold of its own.")))
