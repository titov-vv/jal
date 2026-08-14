import json
import logging
from decimal import Decimal

from PySide6.QtCore import QT_TRANSLATE_NOOP

from jal.constants import AssetLocation
from jal.data_import.statement import Statement_ImportError, JSF
from jal.db.settings_registry import SettingsRegistry, SettingDescriptor
from jal.db.token_blacklist import is_bitcoin_address, is_extended_public_key
from jal.net.chain_fetchers.fetcher import ChainFetcher
from jal.net.chain_fetchers.hd_wallet import HDAccount, ScriptType, RECEIVE_BRANCH, CHANGE_BRANCH, \
    preferred_script_type
from jal.net.web_request import WebRequest

JAL_FETCHER_CLASS = "BitcoinFetcher"

# Esplora is the API of the Blockstream block explorer, served publicly by mempool.space as well: keyless, no
# registration, ~10 requests per second. It is the only source this fetcher needs - '/address/{a}/txs' inlines the
# 'prevout' of every input (its address and its value), so the wallet's balance change in a transaction is computed
# from the one answer, with no extra call to resolve what the inputs were.
_API_ROOT = "https://mempool.space/api"
_PAGE_SIZE = 25                    # confirmed transactions per page, as the API documents it
_MAX_PAGES = 100                   # stops a runaway paging loop on an address with a very long history
_MAX_ADDRESSES = 1000              # ... and on a branch whose gap never closes, see _scan_branch()
_SATOSHI = Decimal('100000000')    # 1 BTC = 10^8 satoshi, the unit every amount is reported in

# How many consecutive unused addresses end the scan of a branch. 20 is the BIP44 standard, which is what wallets
# that expose no setting for it (Trezor Suite among them) use: a wallet never leaves a longer hole behind, so an
# address beyond the gap holds nothing. It is a constant rather than a setting on purpose - a value that disagrees
# with the wallet's own would quietly hide part of the history.
_GAP_LIMIT = 20

# Receive addresses probed when the script type of an extended key has to be established, see _script_type(). Index 0
# alone would be enough for every wallet that hands out its addresses in order, and index 1 covers the one that
# skipped the first.
_DETECTION_INDEXES = (0, 1)


# Raised for a transaction whose shape this fetcher does not (yet) support. It stops the import at that transaction
# instead of guessing what it was: everything older keeps its place and the per-address cursors are left pointing at
# the last transaction that did import, so the next fetch resumes exactly there and re-tries this one. Mirrors
# solana.py and evm.py.
class _HaltImport(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


# ----------------------------------------------------------------------------------------------------------------------
# Fetches the transaction history of a Bitcoin wallet from Esplora and turns it into JSF.
#
# Bitcoin is a UTXO chain, and that is the one thing that makes this fetcher different from the account-based ones:
# a transaction has no "from" and no "to". It consumes outputs (its inputs) and creates new ones, several of which
# routinely belong to the wallet itself - the change of a payment comes straight back. So what a transaction did to
# the wallet is decided ONLY by the wallet's own net balance delta across it:
#
#     delta = SUM(outputs paying an address of the wallet) - SUM(inputs spending one)
#
# and the shapes follow from it (decision #75):
#   - the wallet spent nothing (no input of its own)  ->  incoming transfer of the delta; the sender paid the fee
#   - the wallet funded the transaction               ->  outgoing transfer of (-delta - fee), the fee being its own
#   - ... and that amount comes out zero              ->  a move between the wallet's own addresses: only the miner
#                                                         was paid, so it is a GasFee payment and no transfer at all
#
# The wallet's addresses are the second half of the problem. A modern wallet is a key tree, not an address: the
# account holds the extended public key of an HD account and every address of it is derived locally (hd_wallet.py),
# both branches scanned until _GAP_LIMIT consecutive unused addresses. A single plain address is supported as well -
# it is the same code with a one-address set - but it is faithful only for a wallet that never spends, since the
# change of the first payment lands on an address it doesn't know.
class BitcoinFetcher(ChainFetcher):
    location_id = AssetLocation.BTC_BLOCKCHAIN
    native_symbol = 'BTC'
    native_name = "Bitcoin"
    display_symbol = 'BTC'
    icon_name = ''
    # 1000 satoshi - just above the 546 satoshi "standard dust" output that dusting attacks are built from, and far
    # below any payment a person makes on a chain where the fee alone costs more.
    native_dust_threshold = '0.00001'

    def __init__(self):
        super().__init__()
        self.name = self.tr("&Bitcoin")
        self._new_cursor = ''
        self._state = {}       # the sync cursor, parsed: see _load_state()

    # ------------------------------------------------------------------------------------------------------------------
    # The state carried between fetches, kept as JSON in the single SyncCursor slot (decision #12 - an HD wallet's
    # position is not one value):
    #   'script'    - the script type that was confirmed against the chain, so it is established only once
    #   'addresses' - {address: txid} of the NEWEST transaction imported for each address of the wallet that has any.
    #                 It is both the paging cursor of that address and the record of which addresses are in use, so a
    #                 later fetch re-probes only the gap window instead of walking the branch from 0 again.
    def _load_state(self) -> dict:
        stored = self._cursor()
        if not stored:
            return {'script': '', 'addresses': {}}
        try:
            state = json.loads(stored)
            return {'script': state.get('script', ''), 'addresses': dict(state.get('addresses', {}))}
        except (json.JSONDecodeError, TypeError, ValueError):
            # A cursor that can't be read is not a reason to lose the wallet: the scan starts over, and the import
            # deduplicates by transaction hash what it fetches twice.
            logging.warning(self.tr("Unreadable sync position of account ") + self._account.name())
            return {'script': '', 'addresses': {}}

    # ------------------------------------------------------------------------------------------------------------------
    # One GET against Esplora. An answer that isn't JSON is a failure and stops the fetch: WebRequest returns an empty
    # string for every HTTP error, which for the "is this address used" probe below would otherwise be indistinguishable
    # from "no, it isn't" - and a probe that fails silently ends the gap scan early and hides the rest of the wallet.
    def _get(self, endpoint: str):
        request = WebRequest(WebRequest.GET, f"{_API_ROOT}{endpoint}")
        self._wait_for(request)
        # Every request is reported, not only the paged ones: a cold scan of a wallet is dozens of address probes and
        # the user has to see that something is going on during them.
        self._report_page()
        try:
            return json.loads(request.data())
        except (json.JSONDecodeError, TypeError):
            raise Statement_ImportError(self.tr("Unexpected answer from mempool.space: ") + f"{request.data()}")

    # True if anything ever touched this address. The cheapest question the API answers - it is what the gap scan
    # asks about every address it walks past, and the transactions themselves are fetched only for the used ones.
    def _address_is_used(self, address: str) -> bool:
        stats = self._get(f"/address/{address}")
        try:
            return int(stats['chain_stats']['tx_count']) + int(stats['mempool_stats']['tx_count']) > 0
        except (KeyError, TypeError, ValueError):
            raise Statement_ImportError(self.tr("Unexpected address statistics from mempool.space: ") + f"{stats}")

    # Transactions of one address that aren't imported yet, newest first.
    #
    # Esplora returns them newest first, 25 confirmed per page, older pages asked for with '/txs/chain/{last_seen}'
    # (verified against the chain 2026-07-29). Paging therefore walks BACKWARDS in time and stops as soon as it meets
    # 'known_txid' - the newest transaction of this address that a previous fetch imported - since everything past it
    # is already in the ledger.
    def _transactions_of(self, address: str, known_txid: str) -> list:
        collected = []
        last_seen = ''
        for _ in range(_MAX_PAGES):
            endpoint = f"/address/{address}/txs" + (f"/chain/{last_seen}" if last_seen else '')
            page = self._get(endpoint)
            if not isinstance(page, list):
                raise Statement_ImportError(self.tr("Unexpected transaction list from mempool.space: ") + f"{page}")
            if not page:
                break
            for transaction in page:
                if transaction.get('txid', '') == known_txid:
                    return collected
                collected.append(transaction)
            if len(page) < _PAGE_SIZE:
                break
            last_seen = page[-1].get('txid', '')
            if not last_seen:
                break
        else:
            logging.warning(self.tr("Too many pages returned by mempool.space, the history may be incomplete"))
        return collected

    # ------------------------------------------------------------------------------------------------------------------
    def _fetch(self) -> str:
        key = self._account.address()
        self._state = self._load_state()
        if is_extended_public_key(key):
            try:
                wallet = HDAccount(key)
            except ValueError as error:
                raise Statement_ImportError(self.tr("Not a valid Bitcoin extended public key: ") + f"{error}")
            transactions, own = self._scan_wallet(wallet)
        elif is_bitcoin_address(key):
            # A single watched address. Everything below works on a set of the wallet's addresses, and this is a set
            # of one - but a set that can't grow: the change of any payment made from it lands elsewhere, and this
            # fetcher will read that as the whole balance leaving the wallet. Which it is, as far as the address goes.
            own = {key}
            transactions = {x.get('txid', ''): x
                            for x in self._transactions_of(key, self._state['addresses'].get(key, ''))}
        else:
            raise Statement_ImportError(self.tr("Not a valid Bitcoin address or extended public key: ") + key)
        self._import_transactions(transactions, own)
        return json.dumps(self._state)

    # The script type the extended key's addresses are in, confirmed against the chain rather than taken from the
    # key's own prefix (decision #74).
    #
    # SLIP-132 lets an exporter say the script type in the four version bytes of the key (xpub/ypub/zpub), but
    # exporters disagree: a BIP84 account is commonly handed out as a plain 'xpub', whose prefix then claims legacy
    # '1...' addresses while every address of the account is 'bc1q...'. Deriving the wrong form produces perfectly
    # valid addresses belonging to nobody, and the wallet looks empty instead of wrong - so the prefix only decides
    # which form to try FIRST, and the chain decides which one is right. The answer is kept in the sync state, so
    # this costs a few probes once in the wallet's life.
    def _script_type(self, wallet: HDAccount) -> str:
        stored = self._state.get('script', '')
        if stored in ScriptType.ALL:
            return stored
        preferred = preferred_script_type(self._account.address())
        for script_type in [preferred] + [x for x in ScriptType.ALL if x != preferred]:
            for index in _DETECTION_INDEXES:
                if self._address_is_used(wallet.address(RECEIVE_BRANCH, index, script_type)):
                    self._state['script'] = script_type
                    return script_type
        # Nothing of this key has ever been used, whichever form its addresses take - so there is no history to get
        # wrong, and the prefix's own claim is as good an assumption as any. It is deliberately NOT stored: the
        # question is asked again on the next fetch, when the wallet may have been used.
        logging.info(self.tr("This wallet has no transactions yet, its address type could not be confirmed"))
        return preferred

    # Walks both branches of the HD account and returns everything they hold: {txid: transaction} and the set of the
    # wallet's own addresses that are in use - which is what the balance delta of each transaction is computed
    # against. Transactions are collected in a dictionary because one of them commonly touches several addresses of
    # the same wallet (it spends a receive address and pays the change to another), and it must be classified once,
    # as a whole.
    def _scan_wallet(self, wallet: HDAccount) -> tuple:
        script_type = self._script_type(wallet)
        transactions = {}
        own = set()
        for branch in (RECEIVE_BRANCH, CHANGE_BRANCH):
            self._scan_branch(wallet, script_type, branch, transactions, own)
        return transactions, own

    def _scan_branch(self, wallet: HDAccount, script_type: str, branch: int, transactions: dict, own: set) -> None:
        gap = 0
        index = 0
        while gap < _GAP_LIMIT and index < _MAX_ADDRESSES:
            address = wallet.address(branch, index, script_type)
            index += 1
            # An address the previous fetch already found in use is not probed again - it is known to be used, and
            # its transactions have to be asked for anyway.
            if address not in self._state['addresses'] and not self._address_is_used(address):
                gap += 1
                continue
            gap = 0
            own.add(address)
            for transaction in self._transactions_of(address, self._state['addresses'].get(address, '')):
                transactions[transaction.get('txid', '')] = transaction
        if index >= _MAX_ADDRESSES:
            logging.warning(self.tr("Address scan stopped at the limit, the history may be incomplete"))

    # ------------------------------------------------------------------------------------------------------------------
    # Classifies every fetched transaction, oldest first, and records how far the import got.
    def _import_transactions(self, transactions: dict, own: set) -> None:
        for transaction in sorted(transactions.values(), key=self._order_of):
            tx_hash = transaction.get('txid', '')
            if not transaction.get('status', {}).get('confirmed', False):
                # A transaction still in the mempool can be replaced or dropped, and importing it would put an
                # operation in the ledger that may never have happened. It is picked up by the next fetch after the
                # block that confirms it, and until then the cursor stays behind it.
                self._skip(self.tr("transaction is not confirmed yet"), tx_hash)
                continue
            try:
                self._classify(transaction, own)
            except _HaltImport as halt:
                self._skip(self.tr("import stopped at an unsupported transaction (") + halt.reason
                           + self.tr("); it will be retried next time"), tx_hash)
                return
            self._advance_cursors(transaction, own)

    # Chronological order. An unconfirmed transaction has no height yet and sorts last, which is where it belongs -
    # it is the newest thing that happened.
    @staticmethod
    def _order_of(transaction: dict) -> tuple:
        status = transaction.get('status', {})
        height = status.get('block_height') if status.get('confirmed', False) else None
        return (height if height is not None else 2 ** 63, transaction.get('txid', ''))

    # Marks this transaction as the newest imported one for every address of the wallet it touched. Called only
    # after it really has been classified, so that a halt leaves the cursors pointing at the last transaction that
    # made it into the statement (see _HaltImport).
    def _advance_cursors(self, transaction: dict, own: set) -> None:
        for address in self._own_addresses_of(transaction, own):
            self._state['addresses'][address] = transaction.get('txid', '')

    @classmethod
    def _own_addresses_of(cls, transaction: dict, own: set) -> set:
        touched = {cls._spent_output(x).get('scriptpubkey_address', '') for x in transaction.get('vin', [])}
        touched |= {x.get('scriptpubkey_address', '') for x in transaction.get('vout', [])}
        return touched & own

    # The output an input spends, which Esplora inlines into the input itself - that is what makes the wallet delta
    # computable from one answer. It is absent for a coinbase input, and 'null' is what the API puts there, so it is
    # normalized to an empty record rather than trusted to be a dictionary.
    @staticmethod
    def _spent_output(entry: dict) -> dict:
        return entry.get('prevout') or {}

    # ------------------------------------------------------------------------------------------------------------------
    # What this transaction did to the wallet, decided on the wallet's own balance delta - see the class comment.
    def _classify(self, transaction: dict, own: set) -> None:
        tx_hash = transaction.get('txid', '')
        if any(x.get('is_coinbase', False) for x in transaction.get('vin', [])):
            # Newly mined coins are income and not a transfer from anybody, so they need an operation this fetcher
            # doesn't build (nothing in the validated history has this shape). Halting keeps it visible instead of
            # booking it as something it isn't.
            raise _HaltImport(self.tr("coinbase transaction - mined coins are income, not a transfer"))
        timestamp = self._local_timestamp(int(transaction.get('status', {}).get('block_time', 0)))
        fee = self._amount(transaction.get('fee', 0))
        spent = sum(self._amount(self._spent_output(x).get('value', 0)) for x in transaction.get('vin', [])
                    if self._spent_output(x).get('scriptpubkey_address', '') in own)
        received = sum(self._amount(x.get('value', 0)) for x in transaction.get('vout', [])
                       if x.get('scriptpubkey_address', '') in own)
        if spent == Decimal('0'):
            self._incoming(transaction, own, received, timestamp, tx_hash)
        else:
            self._outgoing(transaction, own, spent - received - fee, fee, timestamp, tx_hash)

    # The wallet paid nothing into this transaction, so whatever it received is a payment to it and the fee was the
    # sender's business.
    def _incoming(self, transaction: dict, own: set, amount: Decimal, timestamp: int, tx_hash: str) -> None:
        if amount <= Decimal('0'):
            self._skip(self.tr("transaction that moved nothing of the wallet's"), tx_hash)
            return
        senders = self._external_addresses(transaction.get('vin', []), own, inputs=True)
        counterparty = senders[0] if len(senders) == 1 else ''
        note = self._addresses_note(senders)
        # Address-poisoning dust: a few hundred satoshi sent from an address that mimics one the user really deals
        # with, so that a later copy-paste out of the history pays the attacker. It is real BTC that changed the
        # balance - unlike a spam token it can be nothing else - so it is recorded as a DustAttack payment rather
        # than dropped, just not as an ordinary transfer implying a real counterparty.
        if self._is_native_dust(amount, self._is_own_address(counterparty)):
            self._add_payment(JSF.PAYMENT_DUST_ATTACK, timestamp, self._native_asset_id(), amount, tx_hash, note=note)
            return
        self._add_transfer(timestamp, self._native_asset_id(), amount, True, tx_hash,
                           note=note, counterparty=counterparty)

    # The wallet funded this transaction, so it paid the miner fee, and 'amount' is what is left after the change
    # came back: the sum that really went to somebody else.
    def _outgoing(self, transaction: dict, own: set, amount: Decimal, fee: Decimal,
                  timestamp: int, tx_hash: str) -> None:
        if amount < Decimal('0'):
            # The wallet spent into a transaction that paid it back MORE than it put in plus the fee - it was funded
            # by someone else as well (a collaborative transaction), and who paid which part of it can't be told
            # from the chain. Nothing here can split that fairly, so it stops the import instead of guessing.
            raise _HaltImport(self.tr("transaction funded by the wallet and by somebody else at once"))
        if amount == Decimal('0'):
            # Everything came back to the wallet's own addresses: a consolidation, or a move between its own
            # branches. No asset left the wallet - only the miner was paid.
            self._add_payment(JSF.PAYMENT_GAS_FEE, timestamp, self._native_asset_id(), fee, tx_hash,
                              note=self.tr("Miner fee of a transfer between the wallet's own addresses"))
            return
        receivers = self._external_addresses(transaction.get('vout', []), own, inputs=False)
        counterparty = receivers[0] if len(receivers) == 1 else ''
        asset_id = self._native_asset_id()
        self._add_transfer(timestamp, asset_id, amount, False, tx_hash, note=self._addresses_note(receivers),
                           fee=fee, fee_asset_id=asset_id if fee > Decimal('0') else None, counterparty=counterparty)

    # The addresses of the transaction that are not the wallet's own, in the order they appear and without repeats:
    # the senders when reading its inputs, the receivers when reading its outputs.
    @classmethod
    def _external_addresses(cls, entries: list, own: set, inputs: bool) -> list:
        addresses = []
        for entry in entries:
            address = cls._spent_output(entry).get('scriptpubkey_address', '') if inputs \
                else entry.get('scriptpubkey_address', '')
            if address and address not in own and address not in addresses:
                addresses.append(address)
        return addresses

    # A transaction with exactly one counterparty says so in the transfer's own counterparty_address field, which is
    # what settles the leg later on, so its description stays empty. Several of them can't be put there - a transfer
    # has one far side - and the description is then where they are kept, so that nothing the transaction said is
    # lost. A payment split over many outputs is named by the first few only; the transaction hash is what leads to
    # the full picture.
    def _addresses_note(self, addresses: list) -> str:
        if len(addresses) < 2:
            return ''
        shown = ", ".join(addresses[:3])
        return self.tr("Several addresses: ") + (shown + ", ..." if len(addresses) > 3 else shown)

    # Every value Esplora reports - outputs, inputs and the fee - is an integer number of satoshi. The conversion to
    # the BTC amounts JAL stores happens here and nowhere else, and never through a float.
    @staticmethod
    def _amount(satoshi) -> Decimal:
        try:
            return Decimal(int(satoshi)) / _SATOSHI
        except (TypeError, ValueError, ArithmeticError):
            raise Statement_ImportError(f"Unreadable Bitcoin amount: {satoshi}")


SettingsRegistry.register(SettingDescriptor(
    key="DustThreshold_BTC",
    page=QT_TRANSLATE_NOOP("Preferences", "Blockchain"),
    label=QT_TRANSLATE_NOOP("Preferences", "BTC dust threshold"), default=BitcoinFetcher.native_dust_threshold,
    tooltip=QT_TRANSLATE_NOOP("Preferences",
                              "An incoming BTC transfer below this amount, from an address you never dealt with, "
                              "is recorded as a dust attack instead of an ordinary transfer.")))
