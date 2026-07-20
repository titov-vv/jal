import logging
from decimal import Decimal

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from jal.constants import AssetLocation, AccountData, PredefinedAccountType
from jal.data_import.statement import Statement, JSF, Statement_ImportError
from jal.db.account import JalAccount
from jal.db.asset import JalAsset


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

    def __init__(self):
        super().__init__()
        self._account = JalAccount(0)
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
        if self._new_cursor:
            self._store_cursor(self._new_cursor)
        return totals

    # ------------------------------------------------------------------------------------------------------------------
    # Helpers shared by the chain implementations

    # Waits for a WebRequest to finish while keeping the application responsive. QThread.wait() would block the GUI
    # thread instead, and a wallet with a long history takes many requests - the window would look frozen for all
    # of them. Mirrors QuoteDownloader._wait_for_event().
    @staticmethod
    def _wait_for(request) -> None:
        while request.isRunning():
            QApplication.processEvents()

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
        transfer = {"id": self._next_id(JSF.TRANSFERS), "account": accounts, "symbol": [symbol_id, symbol_id],
                    "timestamp": timestamp, "withdrawal": amount, "deposit": amount,
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
