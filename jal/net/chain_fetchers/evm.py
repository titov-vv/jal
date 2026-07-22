import json
import logging
from decimal import Decimal
from collections import defaultdict

from jal.constants import AssetLocation, PredefinedAccountType
from jal.data_import.statement import Statement_ImportError, JSF
from jal.data_import.token_filter import TokenCandidate
from jal.db.account import JalAccount
from jal.db.settings import JalSettings
from jal.db.symbol import JalSymbol
from jal.db.token_blacklist import normalize_address, is_evm_address
from jal.net.chain_fetchers.fetcher import ChainFetcher
from jal.net.chain_fetchers.protocols import protocol_category, ProtocolCategory
from jal.net.web_request import WebRequest

# This module has no JAL_FETCHER_CLASS on purpose: it is the shared base of the EVM chains, not a selectable chain
# itself. Each concrete chain (Ethereum, Arbitrum, ...) is a thin subclass in its own module that only sets the
# Etherscan 'chainid' and the native coin - see ethereum.py / arbitrum.py.

# Etherscan moved to a single V2 endpoint that serves every chain it supports through one 'chainid' parameter and
# one API key. So every EVM chain shares this root and the same 'ApiKey_Etherscan' key.
_API_ROOT = "https://api.etherscan.io/v2/api"
_PAGE_SIZE = 10000                # Maximum 'offset' the API accepts
_MAX_PAGES = 20                   # Stops a runaway paging loop on an address with a very long history
_WEI = Decimal('10') ** 18        # 1 coin = 10^18 wei, the unit every native amount is returned in
_NO_TRANSACTIONS = "No transactions found"   # status=0 message that means "empty history", not an error

_METHOD_APPROVE = '0x095ea7b3'    # approve(address,uint256) selector, the one gas-only call worth naming apart


# Raised by the classifier for a transaction whose shape it does not (yet) support - an unregistered exchange, a
# lending/bridge operation, an unfamiliar multi-asset shape. It stops the import at that transaction rather than
# guessing: see _fetch for the halt-and-checkpoint that imports every earlier block and re-tries this one next time.
class _HaltImport(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


# ----------------------------------------------------------------------------------------------------------------------
# Fetches the transaction history of an EVM wallet from Etherscan and turns it into JSF.
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

    def __init__(self):
        super().__init__()
        self._new_cursor = ''

    # ------------------------------------------------------------------------------------------------------------------
    def _api_key(self) -> str:
        key = JalSettings().getStr("ApiKey_Etherscan").strip()
        if not key:
            raise Statement_ImportError(
                self.tr("Etherscan API key isn't set - fill it in Settings/Preferences/Blockchain"))
        return key

    # The wallet address, lower-cased the way every EVM address is stored and the way Etherscan returns 'from'/'to',
    # so a direct string comparison decides the direction of a transfer.
    def _address(self) -> str:
        return normalize_address(self.location_id, self._account.address())

    def _norm(self, address: str) -> str:
        return normalize_address(self.location_id, address)

    # Executes one paged GET against an Etherscan 'account' action and returns the 'result' list. Paging is by page
    # number (the API caps 'offset' at _PAGE_SIZE), and a short page means the history is exhausted.
    def _get_pages(self, action: str, start_block: int) -> list:
        records = []
        for page in range(1, _MAX_PAGES + 1):
            params = {"chainid": self.chain_id, "module": "account", "action": action,
                      "address": self._account.address(), "startblock": start_block, "endblock": 99999999,
                      "page": page, "offset": _PAGE_SIZE, "sort": "asc", "apikey": self._api_key()}
            request = WebRequest(WebRequest.GET, _API_ROOT, params=params)
            self._wait_for(request)
            try:
                answer = json.loads(request.data())
            except (json.JSONDecodeError, TypeError):
                raise Statement_ImportError(self.tr("Unexpected answer from Etherscan: ") + f"{request.data()}")
            result = answer.get('result', [])
            # status=0 is both "no transactions" (an ordinary empty history) and a real error (a bad key, a rate
            # limit); the two are told apart by the message, since only the error carries a string result.
            if str(answer.get('status', '0')) != '1':
                if answer.get('message', '') == _NO_TRANSACTIONS:
                    break
                raise Statement_ImportError(self.tr("Etherscan request failed: ") + f"{result or answer}")
            records += result
            if len(result) < _PAGE_SIZE:
                break
        else:
            logging.warning(self.tr("Too many pages returned by Etherscan, the history may be incomplete"))
        return records

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
        native = self._get_pages("txlist", start_block)
        tokens = self._get_pages("tokentx", start_block)
        internal = self._get_pages("txlistinternal", start_block)
        transactions = self._group_by_transaction(native, tokens, internal)

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
        outs = {asset_id: data for asset_id, data in deltas.items() if data['amount'] < 0}
        ins = {asset_id: data for asset_id, data in deltas.items() if data['amount'] > 0}
        category = protocol_category(self.location_id, self._norm(own_record.get('to', ''))) if own else None

        # Nothing moved: an approval, a reverted transaction, or a contract call whose only effect was spam we
        # filtered out. If it was the wallet's own transaction its gas is still charged as a GasFee.
        if not outs and not ins:
            if own and gas > Decimal('0'):
                self._add_payment(JSF.PAYMENT_GAS_FEE, timestamp, self._native_asset_id(), gas, tx['hash'],
                                  note=self._gas_note(own_record, is_error))
            return

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
            return self._emit_cross_chain_leg(timestamp, deltas, outs, ins, tx['hash'], gas, own_record, is_error)
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
            return self._emit_transfers(timestamp, deltas, tx['hash'], gas, own_record, is_error)

        swap_shape = len(outs) == 1 and len(ins) == 1
        if category == ProtocolCategory.SWAP:
            if swap_shape:
                return self._emit_swap(timestamp, outs, ins, tx['hash'], gas)
            raise _HaltImport(self.tr("unrecognized swap shape"))
        if category == ProtocolCategory.AGGREGATOR:
            if swap_shape:                                 # both legs on this chain -> a same-chain swap
                return self._emit_swap(timestamp, outs, ins, tx['hash'], gas)
            # a single leg -> one side of a cross-chain move, whose counterpart lives on another chain
            return self._emit_cross_chain_leg(timestamp, deltas, outs, ins, tx['hash'], gas, own_record, is_error)

        # From here the contract (if any) is unregistered. A transaction the wallet signed that both spends and
        # receives an asset is a swap/lending/bridge through an unknown contract - it must never be guessed at
        # (reconciliation (a)); likewise an unfamiliar multi-asset shape or an own-initiated pure acquisition (a
        # claim whose cost basis we can't establish) halts, to be revisited once the registry knows the contract.
        if own and swap_shape:
            # Naming the contract lets the user add it to the protocol registry with the right category and re-fetch.
            raise _HaltImport(self.tr("asset exchange through an unregistered contract ")
                              + self._norm(own_record.get('to', '')))
        if own and outs and ins:
            raise _HaltImport(self.tr("unrecognized multi-asset transaction"))
        if own and ins and not outs:
            raise _HaltImport(self.tr("incoming asset through an unregistered contract"))

        # What is left is a plain transfer: assets sent out (a payment, a deposit to an exchange) or received from the
        # outside world (an ordinary receive, an airdrop that passed the spam filter).
        self._emit_transfers(timestamp, deltas, tx['hash'], gas, own_record, is_error)

    # Emits the wallet's movements as plain transfers, one per asset. The gas of the wallet's own send rides its
    # outgoing leg, the way a broker's transfer fee does; a transaction that only received pays it as a GasFee.
    def _emit_transfers(self, timestamp: int, deltas: dict, tx_hash: str, gas: Decimal,
                        own_record, is_error: bool) -> None:
        remaining_gas = gas
        for asset_id, data in sorted(deltas.items()):
            incoming = data['amount'] > Decimal('0')
            fee = Decimal('0')
            if not incoming and remaining_gas > Decimal('0'):
                fee, remaining_gas = remaining_gas, Decimal('0')
            self._add_transfer(timestamp, asset_id, abs(data['amount']), incoming, tx_hash, note=data['note'],
                               fee=fee, fee_asset_id=self._native_asset_id() if fee > Decimal('0') else None)
        if own_record is not None and remaining_gas > Decimal('0'):
            self._add_payment(JSF.PAYMENT_GAS_FEE, timestamp, self._native_asset_id(), remaining_gas, tx_hash,
                              note=self._gas_note(own_record, is_error))

    # The wallet's net movement per asset in this transaction: incoming amounts positive, outgoing negative, summed
    # across the native, internal and (spam-filtered) token legs. Gas is NOT part of it - it is charged separately.
    # Net-zero assets (a token routed in and back out) are dropped, so only what actually changed hands remains.
    def _wallet_deltas(self, tx: dict) -> dict:
        deltas = defaultdict(lambda: {'amount': Decimal('0'), 'note': ''})
        for record in tx['native'] + tx['internal']:      # native coin, moved directly or by a contract
            signed = self._native_signed_amount(record)
            if signed != Decimal('0'):
                entry = deltas[self._native_asset_id()]
                entry['amount'] += signed
                entry['note'] = entry['note'] or self._counterparty_note(record)
        for record in tx['tokens']:
            leg = self._token_leg(record, tx)
            if leg is not None:
                asset_id, signed, note = leg
                entry = deltas[asset_id]
                entry['amount'] += signed
                entry['note'] = entry['note'] or note
        return {asset_id: data for asset_id, data in deltas.items() if data['amount'] != Decimal('0')}

    # Signed native amount of a single txlist/internal record for the wallet (+ received, - sent, 0 if unrelated or
    # reverted). The native coin is never dust-filtered - see the long note that used to live in _process_native:
    # its value can only come from stored quotes a fresh wallet lacks, and a raw amount check would drop a real
    # sub-1-ETH transfer, while native poisoning creates no attacker-named asset.
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

    # One token leg as (asset_id, signed_amount, note), or None when the leg carries nothing importable (a malformed
    # contract, a zero-value event, or a token the spam filter quarantined). The spam policy is unchanged from the
    # per-leg version: provenance decides trust - only a transaction the wallet itself signed is user-driven, so any
    # other event, whichever direction it claims, must face the dust filter (a spoofed 'outgoing' fake-USDT otherwise
    # sails in, because the shared filter never treats an outgoing transfer as dust).
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
        candidate = TokenCandidate(location_id=self.location_id, address=address, symbol=symbol, name=name,
                                   incoming=incoming or not initiated, from_swap=initiated, amount=amount,
                                   known_counterparty=self._is_own_address(counterparty),
                                   value=self._value_of(address, amount, self._timestamp_of(record)))
        if not self._filter.accept(candidate):
            self._skip(self.tr("token quarantined as dust/spam"), tx_hash)
            return None
        asset_id = self._token_asset_id(symbol, name, address=address)
        return asset_id, (amount if incoming else -amount), self._counterparty_note(record)

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
                              own_record, is_error: bool) -> None:
        if len(outs) == 1 and not ins:
            asset_id, data = next(iter(outs.items()))
            self._add_bridge_half(timestamp, asset_id, abs(data['amount']), tx_hash,
                                  fee=gas, fee_asset_id=self._native_asset_id() if gas > Decimal('0') else None)
            return
        if len(ins) == 1 and not outs:
            self._emit_transfers(timestamp, deltas, tx_hash, gas, own_record, is_error)
            return
        raise _HaltImport(self.tr("unrecognized cross-chain transaction shape"))

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
        counterparty = sender if self._norm(receiver) == self._address() else receiver
        if self._is_known_account(counterparty):
            return ''
        return f"{sender} → {receiver}"

    # True if the address belongs to any wallet account JAL holds (on any chain - an EVM address is shared across
    # EVM chains, and addresses of different chains never collide, so a cross-chain check is safe).
    def _is_known_account(self, address: str) -> bool:
        address = self._norm(address)
        if not address:
            return False
        for account in JalAccount.get_all_accounts(active_only=True):
            if account.account_type() == PredefinedAccountType.Wallet and \
                    normalize_address(account.chain(), account.address()) == address:
                return True
        return False
