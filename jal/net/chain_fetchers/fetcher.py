import logging
from datetime import datetime, timezone
from decimal import Decimal

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from jal.constants import AssetLocation, AccountData, PredefinedAccountType, PredefinedAsset
from jal.data_import.statement import Statement, JSF, Statement_ImportError
from jal.data_import.token_filter import TokenFilter
from jal.db.bridge_matcher import BridgeMatcher
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.token_blacklist import normalize_address


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
    location_id = AssetLocation.UNDEFINED
    icon_name = ''
    native_symbol = ''              # Ticker of the chain's native coin, e.g. 'ETH'
    native_name = ''                # Human name of the native coin, e.g. 'Ethereum'

    def __init__(self):
        super().__init__()
        self._account = JalAccount(0)
        self._filter = TokenFilter()
        self._skipped = {}           # {reason: count} of transactions that were recognized but not imported

    # Wallet accounts of this fetcher's chain. The account carries the address to scan and the cursor of the
    # previous fetch, so a fetcher never asks the user where to look.
    @classmethod
    def wallets(cls) -> list:
        accounts = JalAccount.get_all_accounts(active_only=True)
        return [x for x in accounts
                if x.account_type() == PredefinedAccountType.Wallet and x.chain() == cls.location_id]

    # Position of the last completed fetch of this account. Its format is defined by the fetcher that wrote it,
    # so it is never interpreted anywhere else.
    def _cursor(self) -> str:
        return self._account.get_data(AccountData.SyncCursor) or ''

    def _store_cursor(self, cursor: str) -> None:
        self._account.set_data(AccountData.SyncCursor, str(cursor))

    # Records that a transaction was recognized but produced no operation. Nothing is dropped silently: the counts
    # are reported back to the user, so an unsupported kind of transaction is visible instead of just missing.
    def _skip(self, reason: str, tx_hash: str = '') -> None:
        self._skipped[reason] = self._skipped.get(reason, 0) + 1
        logging.debug(f"Transaction is not imported ({reason}): {tx_hash}")

    def skipped(self) -> dict:
        return dict(self._skipped)

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

    # Waits for a WebRequest to finish while keeping the application responsive. QThread.wait() would block the GUI
    # thread instead, and a wallet with a long history takes many requests - the window would look frozen for all
    # of them. Mirrors QuoteDownloader._wait_for_event().
    @staticmethod
    def _wait_for(request) -> None:
        while request.isRunning():
            QApplication.processEvents()

    # Converts a true-UTC epoch (in seconds - every blockchain reports absolute UTC time) into the timestamp
    # convention JAL stores everywhere else: the local wall-clock reading of that instant, kept as a UTC epoch of
    # those digits. JAL displays every timestamp in UTC (see TimestampDelegate), and every other source stores the
    # source's local wall clock this same way - manual entry through now_ts(), and every broker importer, which
    # takes a local time string and stamps it as UTC. A raw UTC epoch would place chain operations an offset away
    # from all of them and from what a block explorer shows in the user's local time. The offset in force at the
    # event's own instant is used, so it stays correct across DST boundaries.
    @staticmethod
    def _local_timestamp(utc_seconds: int) -> int:
        if utc_seconds <= 0:
            return 0
        return int(datetime.fromtimestamp(utc_seconds).replace(tzinfo=timezone.utc).timestamp())

    # The chain's native coin, which has no contract address behind it
    def _native_asset_id(self) -> int:
        return self._token_asset_id(self.native_symbol, self.native_name, address='')

    # Value of a native-coin amount in the account currency, or None when the coin can't be priced at that moment.
    # The native coin carries no contract address, so it is found by ticker - which is safe here, and only here:
    # a ticker is attacker-controlled for a token, but the native coin of a chain is guaranteed by the chain itself.
    def _native_value_of(self, amount: Decimal, timestamp: int):
        asset = JalAsset.find({'symbol': self.native_symbol, 'type': PredefinedAsset.Crypto})
        if not asset.id():
            return None
        rate = asset.quote(timestamp, self._account.currency())[1]
        return amount * rate if rate else None

    # True if an incoming native-coin transfer is address-poisoning dust: a trivial amount sent from an address that
    # mimics one the user really deals with, so that a later copy-paste out of the history pays the attacker instead.
    #
    # The test is on the transfer's VALUE in the account currency, never on the raw coin amount: the dust threshold is
    # a fiat figure ("an airdrop worth less than this"), and comparing a coin count against it means something
    # different on every chain - with the default threshold of 1 it happens to be harmless for TRX yet would quarantine
    # any incoming transfer below 1 ETH or 1 SOL. A coin that can't be priced is imported rather than dropped: an
    # unquotable amount is not evidence of spam, and silently losing a real transfer is far worse than importing dust.
    def _is_native_dust(self, amount: Decimal, timestamp: int, known_counterparty: bool = False) -> bool:
        if known_counterparty:
            return False
        value = self._native_value_of(amount, timestamp)
        if value is None:
            return False
        return value < self._filter.dust_threshold()

    # True if the address is one of the user's own wallets. A transfer between two wallets of the same person is
    # never an unsolicited airdrop, whatever it is worth. Addresses are compared in their stored (normalized) form,
    # so a chain whose addresses are case-insensitive matches regardless of how the API happened to spell them.
    def _is_own_address(self, address: str) -> bool:
        address = normalize_address(self.location_id, address)
        if not address:
            return False
        return any(normalize_address(self.location_id, x.address()) == address for x in self.wallets())

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

    # Adds an asset transfer between the fetched wallet and the outside world. An address that JAL doesn't know
    # is left as account 0, which makes _import_transfers() ask the user which account the assets came from or
    # went to - the same flow a broker statement uses for an unmatched transfer.
    def _add_transfer(self, timestamp: int, asset_id: int, amount: Decimal, incoming: bool,
                      tx_hash: str, note: str = '', fee: Decimal = Decimal('0'), fee_asset_id: int = None) -> None:
        symbol_id = self._single_symbol_of(asset_id)
        # 'account' is [withdrawal, deposit, fee] and 0 means "not known to JAL": the counterparty of an on-chain
        # transfer is an address, so the import asks the user which account it maps to. The gas is always paid by
        # the wallet being fetched, whichever direction the assets move.
        accounts = [0, 1, 1] if incoming else [1, 0, 1]
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
