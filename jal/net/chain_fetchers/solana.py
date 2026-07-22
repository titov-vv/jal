import json
import logging
from decimal import Decimal
from collections import defaultdict

from jal.constants import AssetLocation, AccountData
from jal.data_import.statement import Statement_ImportError, JSF
from jal.data_import.token_filter import TokenCandidate
from jal.db.settings import JalSettings
from jal.db.symbol import JalSymbol
from jal.db.token_blacklist import is_solana_address
from jal.net.chain_fetchers.fetcher import ChainFetcher
from jal.net.token_lists import TokenListProvider
from jal.net.web_request import WebRequest

JAL_FETCHER_CLASS = "SolanaFetcher"

# Helius 'Enhanced Transactions' returns whole transactions already parsed and enriched, unlike the raw JSON-RPC of a
# plain Solana node - one record per transaction, with every account's balance change resolved. The free plan covers
# 1M credits a month, far beyond what a personal wallet needs.
_API_ROOT = "https://api.helius.xyz/v0/addresses"
_PAGE_SIZE = 100                   # Maximum 'limit' the API accepts
_MAX_PAGES = 100                   # Stops a runaway paging loop on an address with a very long history
_LAMPORTS = Decimal('10') ** 9     # 1 SOL = 10^9 lamports, the unit every native amount is returned in

# The native staking program. Its address is quoted from this project's own fetched history rather than from memory,
# the way every registry address is (CRYPTO_PATH decision #58).
_STAKE_PROGRAM = 'Stake11111111111111111111111111111111111111'

# Helius' semantic labels for what the stake program did. They are used ONLY inside a transaction already proven to
# invoke the stake program, and only to tell its three shapes apart - never to decide what an operation is. The
# transaction's own balance changes decide that; see the note on _classify_transaction.
_STAKE_DEPOSIT = 'STAKE_SOL'         # lamports move from the wallet into a stake account
_STAKE_DEACTIVATE = 'UNSTAKE_SOL'    # the stake stops earning; nothing moves
_STAKE_WITHDRAW = 'WITHDRAW'         # lamports move from a stake account back to the wallet


# Raised for a transaction whose shape this fetcher does not (yet) support. It stops the import at that transaction
# instead of guessing - see _fetch for the halt-and-checkpoint that keeps every earlier transaction and re-tries
# this one on the next fetch. Mirrors evm.py's _HaltImport.
class _HaltImport(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


# ----------------------------------------------------------------------------------------------------------------------
# Fetches the transaction history of a Solana wallet from Helius and turns it into JSF.
#
# Helius labels every transaction with a semantic 'type' (TRANSFER, SWAP, STAKE_SOL, ...) and a 'source' (JUPITER,
# MAYAN_SWIFT_BRIDGE, ...). Those labels are NOT what this fetcher classifies on, because they describe what the
# transaction did as a whole and not what it did to this wallet - a Jupiter swap routed past the wallet arrives as
# type 'UNKNOWN', a token that lands in a newly created account as 'INITIALIZE_ACCOUNT', and a bridge delivery as
# 'SETTLE'. What is authoritative is the same thing evm.py classifies on: the wallet's own NET BALANCE CHANGE across
# the transaction, taken from 'accountData' (its native balance, plus every token account it owns). A transaction
# that moves nothing of the wallet's is skipped no matter how interesting its label is.
#
# Solana makes two things easier than EVM does. The fee is charged to a named 'feePayer', so gas is attributed to the
# wallet only when the wallet really paid it; and one API record is one complete transaction, so a halt rolls back a
# single transaction rather than a whole block.
class SolanaFetcher(ChainFetcher):
    location_id = AssetLocation.SOL_BLOCKCHAIN
    native_symbol = 'SOL'
    native_name = "Solana"
    icon_name = ''

    def __init__(self):
        super().__init__()
        self.name = self.tr("Solana")
        self._lists = TokenListProvider()
        self._new_cursor = ''
        self._stakes = None      # {stake account address: amount staked}, loaded by _fetch - see _process_stake

    # ------------------------------------------------------------------------------------------------------------------
    def _api_key(self) -> str:
        key = JalSettings().getStr("ApiKey_Helius").strip()
        if not key:
            raise Statement_ImportError(
                self.tr("Helius API key isn't set - fill it in Settings/Preferences/Blockchain"))
        return key

    # Reads the wallet's history newest-first and returns it in chronological order. Paging is by 'before' (the
    # signature to continue from), and 'until' stops at the last transaction of the previous fetch, so only what is
    # new is downloaded. Solana has no block-number cursor to compare against - a signature is the only position the
    # API accepts - which is why the cursor is a signature.
    def _get_transactions(self, until: str) -> list:
        address = self._account.address()
        records = []
        before = ''
        for _ in range(_MAX_PAGES):
            params = {"api-key": self._api_key(), "limit": _PAGE_SIZE}
            if before:
                params['before'] = before
            if until:
                params['until'] = until
            request = WebRequest(WebRequest.GET, f"{_API_ROOT}/{address}/transactions", params=params)
            self._wait_for(request)
            try:
                answer = json.loads(request.data())
            except (json.JSONDecodeError, TypeError):
                raise Statement_ImportError(self.tr("Unexpected answer from Helius: ") + f"{request.data()}")
            # An error is reported as an object with a message, a successful call always returns a list
            if isinstance(answer, dict):
                raise Statement_ImportError(self.tr("Helius request failed: ")
                                            + f"{answer.get('error', answer.get('message', answer))}")
            if not answer:
                break
            records += answer
            before = answer[-1].get('signature', '')
            if len(answer) < _PAGE_SIZE or not before:
                break
        else:
            logging.warning(self.tr("Too many pages returned by Helius, the history may be incomplete"))
        records.reverse()      # the API returns newest first; everything below works in chronological order
        return records

    # ------------------------------------------------------------------------------------------------------------------
    def _fetch(self) -> str:
        address = self._account.address()
        if not is_solana_address(address):
            raise Statement_ImportError(self.tr("Not a valid Solana address: ") + address)
        cursor = self._cursor()
        self._stakes = self._load_stakes()
        transactions = self._get_transactions(cursor)

        # Transactions are imported in the order they were confirmed. When the classifier meets a shape it can't
        # support it raises _HaltImport: that transaction is rolled back, the import stops there keeping every
        # earlier one, and the cursor is parked on the last transaction that did import. The next fetch resumes from
        # it and re-tries the halting transaction on its own, so nothing needs a manual replay once this fetcher
        # learns the shape. Unlike EVM there is no block to roll back - a Solana transaction is atomic by itself.
        last_safe = cursor
        for tx in transactions:
            checkpoint = self._checkpoint()
            stakes = dict(self._stakes)
            try:
                self._classify_transaction(tx)
            except _HaltImport as halt:
                self._restore(checkpoint)
                self._stakes = stakes
                self._skip(self.tr("import stopped at an unsupported transaction (") + halt.reason
                           + self.tr("); it will be retried next time"), tx.get('signature', ''))
                return last_safe
            last_safe = tx.get('signature', '') or last_safe
        return last_safe

    # Snapshot of how many operations (and assets) each JSF section holds, used to roll a partial transaction back
    def _checkpoint(self) -> dict:
        return {section: len(self._data.get(section, [])) for section in
                (JSF.ASSETS, JSF.TRANSFERS, JSF.ASSET_PAYMENTS, JSF.SWAPS, JSF.BRIDGES, JSF.CONVERSIONS)}

    def _restore(self, checkpoint: dict) -> None:
        for section, length in checkpoint.items():
            if section in self._data:
                del self._data[section][length:]

    # ------------------------------------------------------------------------------------------------------------------
    # Turns one transaction into one operation, from what it did to this wallet's balances.
    def _classify_transaction(self, tx: dict) -> None:
        timestamp = self._timestamp_of(tx)
        signature = tx.get('signature', '')
        own = tx.get('feePayer', '') == self._account.address()
        gas = self._fee_of(tx) if own else Decimal('0')

        if self._invokes(tx, _STAKE_PROGRAM):
            return self._process_stake(tx, timestamp, signature, gas)

        deltas = self._wallet_deltas(tx)
        outs = {asset_id: data for asset_id, data in deltas.items() if data['amount'] < 0}
        ins = {asset_id: data for asset_id, data in deltas.items() if data['amount'] > 0}

        # Nothing of the wallet's moved. On Solana this is common and mostly not about the wallet at all: an
        # aggregator's routing transaction touches the accounts around it, and the wallet is listed merely because
        # one of its token accounts was read. Only a transaction the wallet itself paid for leaves anything to
        # record - the gas it burned.
        if not outs and not ins:
            if own and gas > Decimal('0'):
                self._add_payment(JSF.PAYMENT_GAS_FEE, timestamp, self._native_asset_id(), gas, signature,
                                  note=self.tr("Gas: contract call"))
            else:
                self._skip(self.tr("transaction that didn't move any of the wallet's assets"), signature)
            return

        # A transaction the wallet signed that both spends and receives is a swap, a deposit into a protocol or a
        # bridge - through a program this fetcher has no registry for. It must never be guessed at (the rule evm.py
        # follows for an unregistered contract), so it halts and waits until this fetcher learns the shape.
        if own and outs and ins:
            raise _HaltImport(self.tr("asset exchange through an unrecognized program"))
        if own and ins and not outs:
            raise _HaltImport(self.tr("incoming asset with no counterpart in a transaction the wallet paid for"))

        # What is left is a plain transfer: assets sent out, or received from the outside world. An arriving asset is
        # deliberately imported as an ordinary incoming transfer even when it is the far leg of a cross-chain move
        # (this wallet's Mayan bridge deliveries are exactly that) - a fetcher cannot tell one from an ordinary
        # receipt, so the user pairs it with its sending half in the matcher instead (CRYPTO_PATH decision #47).
        self._emit_transfers(timestamp, deltas, signature, gas, own)

    # Emits the wallet's movements as plain transfers, one per asset. The gas of an outgoing transaction rides its
    # outgoing leg the way a broker's transfer fee does; a transaction that only received pays it as a GasFee.
    def _emit_transfers(self, timestamp: int, deltas: dict, signature: str, gas: Decimal, own: bool) -> None:
        remaining_gas = gas
        for asset_id, data in sorted(deltas.items()):
            incoming = data['amount'] > Decimal('0')
            fee = Decimal('0')
            if not incoming and remaining_gas > Decimal('0'):
                fee, remaining_gas = remaining_gas, Decimal('0')
            self._add_transfer(timestamp, asset_id, abs(data['amount']), incoming, signature, note=data['note'],
                               fee=fee, fee_asset_id=self._native_asset_id() if fee > Decimal('0') else None)
        if own and remaining_gas > Decimal('0'):
            self._add_payment(JSF.PAYMENT_GAS_FEE, timestamp, self._native_asset_id(), remaining_gas, signature,
                              note=self.tr("Gas: contract call"))

    # ------------------------------------------------------------------------------------------------------------------
    # Native staking. A stake account is an address of its own that holds the wallet's lamports while they earn: the
    # wallet keeps the withdraw authority throughout, so nothing is bought, sold or converted - the coins simply sit
    # somewhere else for a while. That is the container pattern (CRYPTO_PATH #50/#61), so both directions are plain
    # transfers whose counterparty JAL doesn't know, and the import asks which account the stake account stands for.
    #
    # A withdrawal returns MORE than was staked, the difference being the yield earned inside the container. The
    # amount staked into each stake account is therefore remembered between fetches (see _load_stakes), which lets
    # the withdrawal be split into the principal - a transfer back out of the box - and a StakingReward for the rest.
    def _process_stake(self, tx: dict, timestamp: int, signature: str, gas: Decimal) -> None:
        kind = tx.get('type', '')
        if kind == _STAKE_DEACTIVATE:
            # Deactivation only stops the stake from earning; the lamports stay in the stake account and change no
            # hands, so there is nothing to record beyond the gas it cost.
            if gas > Decimal('0'):
                self._add_payment(JSF.PAYMENT_GAS_FEE, timestamp, self._native_asset_id(), gas, signature,
                                  note=self.tr("Gas: unstaking"))
            return
        native = self._native_delta(tx)
        if kind == _STAKE_DEPOSIT and native < Decimal('0'):
            amount = -native
            stake_account = self._counterpart_account(tx, native)
            self._stakes[stake_account] = self._stakes.get(stake_account, Decimal('0')) + amount
            self._add_transfer(timestamp, self._native_asset_id(), amount, False, signature,
                               note=self.tr("Staked to ") + stake_account,
                               fee=gas, fee_asset_id=self._native_asset_id() if gas > Decimal('0') else None)
            return
        if kind == _STAKE_WITHDRAW and native > Decimal('0'):
            withdrawn = native
            stake_account = self._counterpart_account(tx, native)
            staked = self._stakes.get(stake_account)
            if staked is None:
                # The deposit into this stake account happened before JAL started following the wallet, so there is
                # nothing to measure the yield against. The whole amount is booked as a return of principal, never as
                # income: inventing income out of a returned deposit is the one error that must not happen here (#61).
                principal, reward = withdrawn, Decimal('0')
                self._skip(self.tr("stake withdrawal whose deposit predates the sync cursor - yield not separated"),
                           signature)
            else:
                principal = min(withdrawn, staked)
                reward = withdrawn - principal
                remaining = staked - principal
                if remaining > Decimal('0'):
                    self._stakes[stake_account] = remaining
                else:
                    self._stakes.pop(stake_account, None)
            self._add_transfer(timestamp, self._native_asset_id(), principal, True, signature,
                               note=self.tr("Withdrawn from ") + stake_account,
                               fee=gas, fee_asset_id=self._native_asset_id() if gas > Decimal('0') else None)
            if reward > Decimal('0'):
                self._add_payment(JSF.PAYMENT_STAKING_REWARD, timestamp, self._native_asset_id(), reward, signature,
                                  note=self.tr("Staking reward"))
            return
        raise _HaltImport(self.tr("unrecognized staking shape: ") + (kind or self.tr("unlabelled")))

    # The address on the other side of a staking movement: the account whose balance changed by exactly the opposite
    # of the wallet's ('native' is the wallet's own signed change). Matching on the amount rather than on a label
    # keeps this exact even when a transaction touches several accounts, and it is why the gross - fee-free -
    # movement is computed first: the fee is paid to the network and has no counterpart to match against.
    def _counterpart_account(self, tx: dict, native: Decimal) -> str:
        for entry in tx.get('accountData', []):
            if entry.get('account') == self._account.address():
                continue
            if self._lamports(entry.get('nativeBalanceChange', 0)) == -native:
                return entry.get('account', '')
        raise _HaltImport(self.tr("staking transaction with no matching stake account"))

    # The staking state survives between fetches in the account's own data, as one JSON row (the way decision #12
    # keeps Bitcoin's HD state). Amounts are stored as strings so that a Decimal never passes through a float.
    def _load_stakes(self) -> dict:
        stored = self._account.get_data(AccountData.StakeAccounts) or ''
        if not stored:
            return {}
        try:
            return {address: Decimal(amount) for address, amount in json.loads(stored).items()}
        except (json.JSONDecodeError, TypeError, ValueError, ArithmeticError):
            logging.warning(self.tr("Unreadable staking state of account ") + self._account.name())
            return {}

    # Written only once the fetched data has actually reached the database, exactly like the sync cursor: a state
    # saying "this much is staked" must never get ahead of the transfers that put it there.
    def _commit_state(self) -> None:
        if self._stakes is None:      # nothing was fetched, so there is nothing to say about the stake accounts -
            return                    # writing here would erase a state that is still perfectly valid
        self._account.set_data(AccountData.StakeAccounts,
                               json.dumps({address: str(amount) for address, amount in self._stakes.items()}))

    # ------------------------------------------------------------------------------------------------------------------
    # The wallet's net movement per asset in this transaction: incoming positive, outgoing negative. Gas is NOT part
    # of it - it is charged separately - and net-zero assets (a token routed in and straight back out) are dropped.
    def _wallet_deltas(self, tx: dict) -> dict:
        deltas = defaultdict(lambda: {'amount': Decimal('0'), 'note': ''})
        timestamp = self._timestamp_of(tx)
        native = self._native_delta(tx)
        if native != Decimal('0'):
            incoming = native > Decimal('0')
            counterparty = self._native_counterparty(tx, incoming)
            # Address-poisoning dust: a lamport or two sent from an address that imitates one the wallet really uses,
            # so that a later copy-paste out of the history pays the attacker. This wallet receives it in batches
            # blasted at a dozen addresses at once, which is why the native coin is filtered here.
            if incoming and self._is_native_dust(native, timestamp, self._is_own_address(counterparty)):
                self._skip(self.tr("native dust transfer below the threshold"), tx.get('signature', ''))
            else:
                entry = deltas[self._native_asset_id()]
                entry['amount'] += native
                entry['note'] = self._counterparty_note(counterparty, incoming)
        for mint, amount, counterparty in self._token_changes(tx):
            asset_id = self._token_leg(tx, mint, amount, counterparty, timestamp)
            if asset_id is not None:
                entry = deltas[asset_id]
                entry['amount'] += amount
                entry['note'] = entry['note'] or self._counterparty_note(counterparty, amount > Decimal('0'))
        return {asset_id: data for asset_id, data in deltas.items() if data['amount'] != Decimal('0')}

    # The wallet's native balance change, with the fee added back when the wallet paid it. Helius reports the change
    # net of the fee, but a fee is not a movement of assets - it is charged separately, on the operation - and the
    # gross figure is also the one that matches the counterpart account of a staking transfer to the lamport.
    def _native_delta(self, tx: dict) -> Decimal:
        change = Decimal('0')
        for entry in tx.get('accountData', []):
            if entry.get('account') == self._account.address():
                change += self._lamports(entry.get('nativeBalanceChange', 0))
        if tx.get('feePayer', '') == self._account.address():
            change += self._fee_of(tx)
        return change

    # Every token balance change of an account the wallet owns, as (mint, signed amount, counterparty). A token lives
    # in its own account on Solana, so ownership is read from 'userAccount' rather than from the address itself.
    def _token_changes(self, tx: dict) -> list:
        totals = defaultdict(Decimal)
        for entry in tx.get('accountData', []):
            for change in entry.get('tokenBalanceChanges', []):
                if change.get('userAccount', '') != self._account.address():
                    continue
                raw = change.get('rawTokenAmount', {})
                try:
                    amount = Decimal(str(raw.get('tokenAmount', '0'))) / (Decimal('10') ** int(raw.get('decimals', 0)))
                except (ValueError, ArithmeticError):
                    self._skip(self.tr("token transfer with an unreadable amount"), tx.get('signature', ''))
                    continue
                totals[change.get('mint', '')] += amount
        return [(mint, amount, self._token_counterparty(tx, mint, amount > Decimal('0')))
                for mint, amount in totals.items() if amount != Decimal('0')]

    # Applies the spam policy to one token movement and returns the JSF asset id to book it against, or None when the
    # token is quarantined. Nothing is created for a rejected token - no asset, no symbol, no operation - so
    # attacker-chosen names never reach the database.
    def _token_leg(self, tx: dict, mint: str, amount: Decimal, counterparty: str, timestamp: int):
        if not is_solana_address(mint):
            self._skip(self.tr("token with a malformed mint address"), tx.get('signature', ''))
            return None
        symbol, name = self._lists.token_metadata(self.location_id, mint)
        incoming = amount > Decimal('0')
        candidate = TokenCandidate(location_id=self.location_id, address=mint, symbol=symbol, name=name,
                                   incoming=incoming, amount=abs(amount),
                                   known_counterparty=self._is_own_address(counterparty),
                                   value=self._value_of(mint, abs(amount), timestamp))
        if not self._filter.accept(candidate):
            self._skip(self.tr("token quarantined as dust/spam"), tx.get('signature', ''))
            return None
        # A token that passed the filter without being on any list has no name to go by - it was accepted because the
        # wallet itself was involved. The mint is used as its identity, which is honest and traceable; the user may
        # rename the asset afterwards, and the mint address stays its real identifier either way.
        return self._token_asset_id(symbol or mint[:6], name or mint, address=mint)

    # Value of the transfer in the account currency, or None when the token can't be priced. A token JAL already
    # holds is priced from its stored quotes; a token seen for the first time has none, and None is what tells the
    # filter it can't judge the transfer by value (it relies on the allow-list and the counterparty instead).
    def _value_of(self, mint: str, amount: Decimal, timestamp: int):
        symbol = JalSymbol.find_by_identifier(AssetLocation.address_id_of(self.location_id), mint)
        if not symbol.id():
            return None
        rate = symbol.asset().quote(timestamp, self._account.currency())[1]
        return amount * rate if rate else None

    # ------------------------------------------------------------------------------------------------------------------
    @staticmethod
    def _lamports(value) -> Decimal:
        try:
            return Decimal(str(value)) / _LAMPORTS
        except (ValueError, ArithmeticError):
            return Decimal('0')

    def _fee_of(self, tx: dict) -> Decimal:
        return self._lamports(tx.get('fee', 0))

    def _timestamp_of(self, tx: dict) -> int:
        # Helius reports seconds of true UTC time; JAL stores them in its own local-wall-clock convention
        try:
            return self._local_timestamp(int(tx.get('timestamp', 0)))
        except (TypeError, ValueError):
            return 0

    # True if the transaction invoked the given program. Solana lists every instruction with the program that runs
    # it, so this is a fact of the transaction rather than an interpretation of it.
    @staticmethod
    def _invokes(tx: dict, program_id: str) -> bool:
        return any(instruction.get('programId', '') == program_id for instruction in tx.get('instructions', []))

    # The address the native coin came from (or went to). 'nativeTransfers' is a convenience view that some
    # transactions omit even though the balances did change, so an empty result is normal and simply leaves the note
    # without a counterparty.
    def _native_counterparty(self, tx: dict, incoming: bool) -> str:
        address = self._account.address()
        for transfer in tx.get('nativeTransfers', []):
            if incoming and transfer.get('toUserAccount', '') == address:
                return transfer.get('fromUserAccount', '') or ''
            if not incoming and transfer.get('fromUserAccount', '') == address:
                return transfer.get('toUserAccount', '') or ''
        return ''

    def _token_counterparty(self, tx: dict, mint: str, incoming: bool) -> str:
        address = self._account.address()
        for transfer in tx.get('tokenTransfers', []):
            if transfer.get('mint', '') != mint:
                continue
            if incoming and transfer.get('toUserAccount', '') == address:
                return transfer.get('fromUserAccount', '') or ''
            if not incoming and transfer.get('fromUserAccount', '') == address:
                return transfer.get('toUserAccount', '') or ''
        return ''

    # Both sides are shown, sender first, so the note carries the whole movement whichever way it went. A counterparty
    # that is another wallet of the user's own is left out - it says nothing the operation doesn't already show.
    def _counterparty_note(self, counterparty: str, incoming: bool) -> str:
        if not counterparty or self._is_own_address(counterparty):
            return ''
        address = self._account.address()
        return f"{counterparty} → {address}" if incoming else f"{address} → {counterparty}"
