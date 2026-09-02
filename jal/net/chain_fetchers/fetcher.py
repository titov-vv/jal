import logging
from decimal import Decimal, DecimalException

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from jal.constants import AssetLocation, AccountData, PredefinedAccountType
from jal.data_import.statement import Statement, JSF, Statement_ImportError
from jal.data_import.token_filter import TokenFilter
from jal.db.bridge_matcher import BridgeMatcher
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.settings import JalSettings
from jal.db.token_blacklist import normalize_address


# ----------------------------------------------------------------------------------------------------------------------
# Tags that mark a transfer which stands in for an operation the fetcher could record only in part, so that the ledger
# itself says what is still to be done with it. Several classifications end in "the user finishes this by hand"
# (CRYPTO_PATH #47/#48/#56/#61) and a plain transfer is exactly what they all look like, so without a mark nothing but
# a bare counterparty address distinguished them from an ordinary payment.
#
# The tag is deliberately NOT translated, while the sentence that follows it is: it has to stay the same string in
# every UI language so that the operations list can be filtered on it (and a future automatic matcher can collect its
# candidates by it), whereas the explanation is there to be read by the user.
class TransferMark:
    CUSTODY = '[custody]'    # the asset is held for the wallet elsewhere - merge the legs or convert them
    BRIDGE = '[bridge]'      # one leg of a cross-chain move - merge it with the half on the other chain


# ----------------------------------------------------------------------------------------------------------------------
# Base class of a blockchain transaction fetcher.
#
# A fetcher is a Statement that is filled from an HTTP API instead of a file: it builds the very same JSF structure
# and hands it to match_db_ids() + import_into_db(), so it inherits id matching, asset/symbol creation, the
# interactive "which account did this come from" dialog and the transactional import. Everything a fetcher adds is
# HTTP access and the classification of raw chain data - see CRYPTO_PATH note, section 3.2.
#
# A fetcher is NOT registered in Statements (that registry is file-dialog driven and asks for a filename); it is
# listed in FETCHERS below and reached through Import -> Blockchain.
class ChainFetcher(Statement):
    name = ''                       # Human readable name shown in the menu
    source_timezone = 'UTC'
    location_id = AssetLocation.UNDEFINED
    # Chain logo shown next to the menu item - a file name inside jal/img/ without its 'chain_' prefix.
    # An empty name leaves the menu item without an icon.
    icon_name = ''
    native_symbol = ''              # Ticker of the chain's native coin, e.g. 'ETH'
    native_name = ''                # Human name of the native coin, e.g. 'Ethereum'
    # Short ticker shown in the "fetching page N..." progress label instead of the full chain name (ChainFetchers.
    # load()). Usually the same as native_symbol, but not always: two chains can share a native coin (Arbitrum is
    # also gas-priced in ETH) or a chain may have none to name at all (Hyperliquid), so each fetcher sets its own.
    display_symbol = ''
    # Raw coin amount below which an incoming native-coin transfer is treated as dust, overridden per chain by the
    # user-editable 'DustThreshold_<SYMBOL>' setting - see _native_dust_threshold(). '0' disables the check for a
    # chain that doesn't set its own (nothing is ever below zero), which is the safe default: importing an
    # unclassified transfer as an ordinary one is never wrong, only imprecise.
    native_dust_threshold = '0'
    # Every transfer a fetcher builds carries the hash of the transaction it came from, which identifies the
    # movement no matter which of its two ends was fetched - see Statement._transfers_are_unique_per_transaction.
    _transfers_are_unique_per_transaction = True

    # Emitted once per HTTP page read from the chain's API, carrying the running page count of the current fetch()
    # call. A wallet's history has no known total ahead of time (see _get_pages()-style helpers of each chain), so
    # this is the only progress a fetch can report while it is running - ChainFetchers.load() turns it into the
    # "<ticker>: fetching page N..." status text.
    page_fetched = Signal(int)

    def __init__(self):
        super().__init__()
        self._account = JalAccount(0)
        self._filter = TokenFilter()
        self._counterparty_accounts = {}   # db account id -> statement account id of counterparty wallets
        self._page_count = 0         # pages read from the API so far during the current fetch(), see _report_page()
        self._cancelled = False      # Set by cancel() when the user presses 'Stop' - see _wait_for()

    # Wallet accounts of this fetcher's chain. The account carries the address to scan and the cursor of the
    # previous fetch, so a fetcher never asks the user where to look.
    @classmethod
    def wallets(cls) -> list:
        accounts = JalAccount.get_all_accounts()
        return [x for x in accounts
                if x.account_type() == PredefinedAccountType.Wallet and x.chain() == cls.location_id]

    # Position of the last completed fetch of this account. Its format is defined by the fetcher that wrote it,
    # so it is never interpreted anywhere else.
    def _cursor(self) -> str:
        return self._account.get_data(AccountData.SyncCursor) or ''

    def _store_cursor(self, cursor: str) -> None:
        self._account.set_data(AccountData.SyncCursor, str(cursor))

    # Fetches everything that happened on the account since its stored cursor and builds the JSF structure.
    # Implemented by each chain; must return the new cursor value (or '' to leave the old one untouched).
    def _fetch(self) -> str:
        raise NotImplementedError

    # Fetches one wallet account and returns the assembled statement data. The cursor is advanced only by
    # import_fetched() below, after the data has actually reached the database.
    def fetch(self, account: JalAccount) -> dict:
        if account.chain() != self.location_id:
            raise Statement_ImportError(
                self.tr("Account doesn't belong to this blockchain: ") + f"{account.name()}")
        if not account.address():
            raise Statement_ImportError(self.tr("Wallet account has no address: ") + f"{account.name()}")
        self._account = account
        self._skipped = {}
        self._counterparty_accounts = {}
        self._page_count = 0
        self._data = {JSF.ACCOUNTS: [], JSF.ASSETS: [], JSF.TRANSFERS: [], JSF.ASSET_PAYMENTS: []}
        # The account is known up front - it is the one being fetched - so it is mapped straight onto its db id
        # instead of being matched by number the way a broker statement is.
        self._data[JSF.ACCOUNTS].append({"id": 1, "name": account.name(),
                                         "currency": self.currency_id(JalAsset(account.currency()).symbol())})
        self.set_mapped_id(JSF.ACCOUNTS, 1, account.id())
        self._new_cursor = self._fetch()
        return self._data

    # Stores what fetch() collected and advances the sync cursor. Returns the totals reported by import_into_db().
    def import_fetched(self) -> dict:
        self.validate_format()
        self.match_db_ids()
        totals = self.import_into_db()
        # A fetch can produce the sending leg of a cross-chain move; its arrival is fetched from the other chain as an
        # ordinary incoming transfer, which only the user can recognize as belonging to it (BridgeMatcher). Nothing is
        # paired automatically, so the count still waiting is surfaced next to the skipped-transaction summary.
        pending = len(BridgeMatcher()._pending_halves())
        if pending:
            self._skipped[self.tr("cross-chain transactions awaiting matching")] = pending
        if self._new_cursor:
            self._store_cursor(self._new_cursor)
        self._commit_state()
        return totals

    # Stores whatever else a fetcher must remember between runs, on the same terms as the sync cursor: only after the
    # data has reached the database. A fetcher that carries state across fetches (Solana remembers how much sits in
    # each stake account) must never let it get ahead of the operations that justify it.
    def _commit_state(self) -> None:
        pass

    # ------------------------------------------------------------------------------------------------------------------
    # Helpers shared by the chain implementations

    # Asks a running fetch to stop. It is the only interruption point a fetch has, and deliberately so - see
    # _wait_for() for where it takes effect and ChainFetchers.on_cancel() for who calls it.
    def cancel(self) -> None:
        self._cancelled = True

    # Waits for a WebRequest to finish while keeping the application responsive. A plain QThread.wait() would block
    # the GUI thread for the whole request, and a wallet with a long history takes many of them - the window would
    # look frozen throughout. Waiting in short slices and processing events between them keeps it alive without
    # spinning (see WebRequest.wait()). Mirrors QuoteDownloader._wait_for_event().
    #
    # This is also where a fetch stopped by the user ends, and the reason it may only end here: everything _fetch()
    # does is read the chain and build self._data in memory, so a fetch abandoned between two pages has written
    # nothing anywhere and simply leaves the wallet as it was, to be fetched again from the same cursor next time.
    # The request that was being waited for is not stopped - it can't be - and is left to WebRequest to see out.
    def _wait_for(self, request) -> None:
        while not request.wait():
            QApplication.processEvents()
            if self._cancelled:
                raise KeyboardInterrupt

    # Counts one more page read from the API and reports it via page_fetched - called by each chain's paging helper
    # right after a page comes back, whichever of possibly several endpoints it came from (see the callers).
    def _report_page(self) -> None:
        self._page_count += 1
        self.page_fetched.emit(self._page_count)

    # The chain's native coin, which has no contract address behind it
    def _native_asset_id(self) -> int:
        return self._token_asset_id(self.native_symbol, self.native_name, address='')

    # The per-chain dust threshold in effect: the user-editable 'DustThreshold_<SYMBOL>' setting if it holds a valid
    # number, the chain's built-in default otherwise. Never raises on a hand-edited or missing setting, the same way
    # TokenFilter._configured_threshold() falls back to its own default rather than stopping the application.
    def _native_dust_threshold(self) -> Decimal:
        try:
            return Decimal(JalSettings().getStr(f"DustThreshold_{self.native_symbol}", self.native_dust_threshold))
        except DecimalException:
            return Decimal(self.native_dust_threshold)

    # True if an incoming native-coin transfer is address-poisoning dust: a trivial amount sent from an address that
    # mimics one the user really deals with, so that a later copy-paste out of the history pays the attacker instead.
    #
    # Judged on the RAW COIN AMOUNT against a threshold picked per chain, not on the transfer's fiat value: a value
    # comparison depends on a locally cached price history that a freshly added wallet never has, which used to make
    # the check inert exactly when it mattered most (see the discussion that replaced it - CRYPTO_PATH). A dust
    # verdict no longer drops the transfer either: real native coin can never be a scam contract the way a token can,
    # so it is always imported as an AssetPayment(DustAttack) instead of an ordinary Transfer - see the fetchers that
    # call this.
    def _is_native_dust(self, amount: Decimal, known_counterparty: bool = False) -> bool:
        if known_counterparty:
            return False
        return amount < self._native_dust_threshold()

    # True if the address is one of the user's own wallets. A transfer between two wallets of the same person is
    # never an unsolicited airdrop, whatever it is worth. Addresses are compared in their stored (normalized) form,
    # so a chain whose addresses are case-insensitive matches regardless of how the API happened to spell them.
    def _is_own_address(self, address: str) -> bool:
        address = normalize_address(self.location_id, address)
        if not address:
            return False
        return any(normalize_address(self.location_id, x.address()) == address for x in self.wallets())

    # The account that holds the given address, or None when JAL has no single account for it.
    #
    # Only accounts of THIS chain are considered. That restriction is essential rather than an optimization: one EVM
    # address is commonly registered as several accounts, one per chain, and the assets a transfer moves stay on the
    # chain it happened on. Resolving an Ethereum transfer to the Arbitrum account of the same address would book the
    # coins on the wrong chain.
    # An address that matches several accounts of one chain is left unresolved: nothing here can tell which of them
    # the transfer belongs to, and the import asks the user rather than guessing.
    #
    # It asks JalAccount rather than filtering wallets(), so that a STAKING BOX resolves here as well: the container
    # an asset was staked into has an address of its own, and a movement to it is a movement into the box. wallets()
    # can't answer that - it is the list of accounts a fetch SCANS, and a box must never be scanned: its address is a
    # validator's stake account or a protocol contract holding everybody's money, not a wallet to read a history off.
    def _own_wallet(self, address: str):
        return JalAccount.at_address(self.location_id, address)

    # Statement account id of the wallet the given address belongs to, or 0 when it isn't one JAL knows - which is
    # what makes the import ask the user which account the address stands for.
    #
    # A counterparty that is a wallet of the user's own is put into the statement as an account of its own, already
    # mapped onto its db id, so the transfer names both of its sides. Without this every on-chain transfer between
    # two of the user's wallets asked which account the other end was, although both ends were known all along; and
    # the answer, being the user's pick rather than a property of the transaction, differed between the two fetches
    # that see the same transfer - which is what made them impossible to recognize as one and the same operation.
    #
    # The fetched wallet itself is never returned: a transfer of an account to itself is not a movement of assets,
    # and it must not be turned into one behind the user's back.
    def _counterparty_account(self, address: str) -> int:
        wallet = self._own_wallet(address)
        if wallet is None or wallet.id() == self._account.id():
            return 0
        # A counterparty whose account is kept in another currency is left to the user. An asset transfer between
        # two currencies takes its destination cost basis from 'deposit', which a fetcher cannot know and leaves at
        # 0 - and a 0 there rescales every transferred lot to a zero basis (Transfer.processAssetTransfer). That is
        # a pre-existing hazard of a fetched transfer, reachable today by picking such an account in the dialog; it
        # is not made silent here until the basis can actually be computed (see LONG_TERM_IMPROVEMENTS).
        if wallet.currency() != self._account.currency():
            return 0
        if wallet.id() in self._counterparty_accounts:
            return self._counterparty_accounts[wallet.id()]
        statement_id = self._next_id(JSF.ACCOUNTS)
        self._data[JSF.ACCOUNTS].append({"id": statement_id, "name": wallet.name(),
                                         "currency": self.currency_id(JalAsset(wallet.currency()).symbol())})
        self.set_mapped_id(JSF.ACCOUNTS, statement_id, wallet.id())
        self._counterparty_accounts[wallet.id()] = statement_id
        return statement_id

    # The address of an end that has no account, normalized as the database stores it, or '' when there is none to
    # keep. The fetched wallet's own address is not one: a transaction that pays the address it was sent from names
    # no counterparty at all, and storing it would leave a leg to be settled with the account it is already on.
    def _unresolved_address(self, address: str) -> str:
        address = normalize_address(self.location_id, address)
        if not address or address == normalize_address(self.location_id, self._account.address()):
            return ''
        return address

    # Returns the JSF asset id of a token, creating the asset record if this statement doesn't have it yet.
    # 'address' is empty for the native coin of the chain, which has no contract behind it.
    def _token_asset_id(self, symbol: str, name: str, address: str = '') -> int:
        for asset in self._data[JSF.ASSETS]:
            for record in asset[JSF.SYMBOLS]:
                if record.get('address', '') == address and record.get('location') == self.location_id:
                    return asset['id']
        # The currency is resolved first: currency_id() creates the money asset when the statement doesn't have it
        # yet, and it draws from the same id counter - taking the token's id before that would hand out id twice.
        currency = self.currency_id(JalAsset(self._account.currency()).symbol())
        asset_id = self._next_id(JSF.ASSETS)
        record = {"id": self._next_symbol_id(), "symbol": symbol, "currency": currency,
                  "location": self.location_id}
        if address:
            record['address'] = address
        self._data[JSF.ASSETS].append(
            {"id": asset_id, "type": JSF.ASSET_CRYPTO, "name": name, JSF.SYMBOLS: [record]})
        return asset_id

    # ------------------------------------------------------------------------------------------------------------------
    # Description prefix of a transfer into or out of a container that keeps the asset on the wallet's behalf (a
    # custody protocol, a native staking account): what moved is still owned, so a transfer is what it is, but the
    # position only becomes complete once the user merges the two legs or converts them into what really happened.
    def _custody_mark(self, protocol: str) -> str:
        return self._mark(TransferMark.CUSTODY, protocol,
                          self.tr("held for the wallet - to be merged with its counter-leg or converted"))

    # Description prefix of the ARRIVING leg of a cross-chain move. A fetcher sees one chain only, so this leg is
    # imported as a plain transfer and paired afterwards with the pending sending half fetched from the other chain.
    def _bridge_arrival_mark(self, protocol: str) -> str:
        return self._mark(TransferMark.BRIDGE, protocol,
                          self.tr("arriving leg - to be merged with its pending sending half"))

    # A mark is "<tag> <protocol>: <what has to be done>"; the protocol is left out when it isn't known (an arrival
    # delivered by a relayer names no contract of its own).
    @staticmethod
    def _mark(tag: str, protocol: str, hint: str) -> str:
        return f"{tag} {protocol}: {hint}" if protocol else f"{tag} {hint}"

    # Joins the parts of a description, dropping those that are empty - a counterparty note is empty whenever both
    # ends of the transfer are accounts JAL already knows.
    @staticmethod
    def _joined_note(*parts: str) -> str:
        return '. '.join(part for part in parts if part)

    # Adds an asset transfer between the fetched wallet and the outside world. 'counterparty' is the address at the
    # other end: when it belongs to another wallet of the user's own that account is filled in, otherwise the far
    # side is left as account 0 and the transfer is stored with that end unknown - "money on the way", which the
    # address itself is then what settles. A caller that can't tell which address the movement was with (a netted
    # transaction touching several of them) passes none, and the transfer is handled as it always was.
    def _add_transfer(self, timestamp: int, asset_id: int, amount: Decimal, incoming: bool,
                      tx_hash: str, note: str = '', fee: Decimal = Decimal('0'), fee_asset_id: int = None,
                      counterparty: str = '') -> None:
        symbol_id = self._single_symbol_of(asset_id)
        # 'account' is [withdrawal, deposit, fee] and 0 means "not known to JAL": the counterparty of an on-chain
        # transfer is an address, and one that isn't a wallet of the user's own has no account for the import to
        # use. The gas is always paid by the wallet being fetched, whichever direction the assets move.
        far_side = self._counterparty_account(counterparty)
        accounts = [far_side, 1, 1] if incoming else [1, far_side, 1]
        # The tx hash goes into 'number' because that is the column a Transfer has. Operations designed later for
        # crypto carry a field named 'tx_hash' instead (CRYPTO_PATH decision #31); a Transfer predates that.
        #
        # 'deposit' is left at 0, not set to the transferred amount. For an asset transfer 'withdrawal' carries the
        # quantity for both legs; 'deposit' is the cost basis in the destination account's currency and is read only
        # when the two accounts differ in currency (see Transfer.processAssetTransfer). A fetcher cannot know that
        # basis - the destination account is filled in by the user during import - so it leaves it 0 for the user to
        # complete, matching the pre-crypto behaviour. Setting it to the quantity put a TRX/token count where a
        # currency amount belongs and showed a nonsensical "cost basis" in the widget. See LONG_TERM_IMPROVEMENTS
        # for the open question of computing it automatically where a quote exists.
        transfer = {"id": self._next_id(JSF.TRANSFERS), "account": accounts, "symbol": [symbol_id, symbol_id],
                    "timestamp": timestamp, "withdrawal": amount, "deposit": Decimal('0'),
                    "fee": fee, "number": tx_hash, "description": note}
        # An end with no account keeps the address it has instead. The transaction named it, so it is a fact about
        # the movement and not a guess about it, and it is what lets the leg be settled exactly later on - the note
        # carries the same address as free text, which nothing can match against.
        address = '' if far_side else self._unresolved_address(counterparty)
        if address:
            transfer["counterparty_address"] = address
        if fee > Decimal('0') and fee_asset_id is not None:
            transfer["fee_symbol"] = self._single_symbol_of(fee_asset_id)
        self._data[JSF.TRANSFERS].append(transfer)

    # Adds an asset payment: coins that arrive without being bought (a staking reward) or leave without anything
    # moving in return (gas burned by a transaction that transferred nothing).
    def _add_payment(self, payment_type: str, timestamp: int, asset_id: int, amount: Decimal,
                     tx_hash: str, note: str = '') -> None:
        self._data.setdefault(JSF.ASSET_PAYMENTS, []).append(
            {"id": self._next_id(JSF.ASSET_PAYMENTS), "type": payment_type, "account": 1,
             "symbol": self._single_symbol_of(asset_id), "timestamp": timestamp,
             "amount": amount, "tax": Decimal('0'), "number": tx_hash, "description": note})

    # Adds a swap: one asset is disposed (out) and another acquired (in) in a single on-chain transaction. The gas is
    # burned in the chain's native coin (fee_asset_id) - passed separately from the swapped assets, since it may equal
    # neither of them. The Swap operation realizes P&L on the out asset and opens the in asset at market value.
    def _add_swap(self, timestamp: int, out_asset_id: int, out_qty: Decimal, in_asset_id: int, in_qty: Decimal,
                  tx_hash: str, note: str = '', fee: Decimal = Decimal('0'), fee_asset_id: int = None) -> None:
        swap = {"id": self._next_id(JSF.SWAPS), "account": 1,
                "out_symbol": self._single_symbol_of(out_asset_id), "out_qty": out_qty,
                "in_symbol": self._single_symbol_of(in_asset_id), "in_qty": in_qty,
                "timestamp": timestamp, "tx_hash": tx_hash, "description": note}
        if fee > Decimal('0') and fee_asset_id is not None:
            swap["fee_symbol"] = self._single_symbol_of(fee_asset_id)
            swap["fee_qty"] = fee
        self._data.setdefault(JSF.SWAPS, []).append(swap)

    # Adds a conversion: one asset is exchanged for another on the same account while the cost basis is carried over
    # (wrapping, supplying to or withdrawing from a lending protocol, liquid staking). The record looks like a
    # same-chain swap because the movement does - what differs is that no disposal happens and no profit or loss is
    # realized, so the quantities may differ freely (a rebasing receipt token folds accrued yield into them).
    def _add_conversion(self, timestamp: int, out_asset_id: int, out_qty: Decimal, in_asset_id: int, in_qty: Decimal,
                        tx_hash: str, note: str = '', fee: Decimal = Decimal('0'), fee_asset_id: int = None) -> None:
        conversion = {"id": self._next_id(JSF.CONVERSIONS), "account": 1,
                      "out_symbol": self._single_symbol_of(out_asset_id), "out_qty": out_qty,
                      "in_symbol": self._single_symbol_of(in_asset_id), "in_qty": in_qty,
                      "timestamp": timestamp, "tx_hash": tx_hash, "description": note}
        if fee > Decimal('0') and fee_asset_id is not None:
            conversion["fee_symbol"] = self._single_symbol_of(fee_asset_id)
            conversion["fee_qty"] = fee
        self._data.setdefault(JSF.CONVERSIONS, []).append(conversion)

    # Adds the SENDING leg of a cross-chain move as a pending half-bridge, to be paired afterwards with its arrival -
    # which BridgeMatcher then resolves into a bridge or into an asset-changing cross-chain swap. Only this leg is
    # ever added by a fetcher: it is the one that can be recognized (the wallet's own transaction into a known
    # bridge/aggregator), while an arriving asset is indistinguishable from any other receipt and is imported as a
    # plain transfer instead. Gas rides this leg (the source pays it), like a swap fee.
    def _add_bridge_half(self, timestamp: int, asset_id: int, qty: Decimal,
                         tx_hash: str, note: str = '', fee: Decimal = Decimal('0'), fee_asset_id: int = None) -> None:
        half = {"id": self._next_id(JSF.BRIDGES), "account": 1,
                "symbol": self._single_symbol_of(asset_id), "qty": qty,
                "timestamp": timestamp, "tx_hash": tx_hash, "description": note}
        if fee > Decimal('0') and fee_asset_id is not None:
            half["fee_symbol"] = self._single_symbol_of(fee_asset_id)
            half["fee_qty"] = fee
        self._data.setdefault(JSF.BRIDGES, []).append(half)
