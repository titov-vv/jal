from decimal import Decimal
from jal.db.db import JalDB
from jal.constants import Setup, BookAccount


class JalAccount(JalDB):
    def __init__(self, id=0):
        super().__init__()
        self._id = id
        self._data = self._readSQL("SELECT name, currency_id, organization_id, reconciled_on, precision "
                                   "FROM accounts WHERE id=:id", [(":id", self._id)], named=True)
        self._name = self._data['name'] if self._data is not None else None
        self._currency_id = self._data['currency_id'] if self._data is not None else None
        self._organization_id = self._data['organization_id'] if self._data is not None else None
        self._reconciled = int(self._data['reconciled_on']) if self._data is not None else 0
        self._precision = int(self._data['precision']) if self._data is not None else Setup.DEFAULT_ACCOUNT_PRECISION

    def id(self):
        return self._id

    def name(self):
        return self._name

    def currency(self):
        return self._currency_id

    def organization(self):
        return self._organization_id

    def reconciled_at(self):
        return self._reconciled

    def reconcile(self, timestamp):
        _ = self._executeSQL("UPDATE accounts SET reconciled_on=:timestamp WHERE id = :account_id",
                             [(":timestamp", timestamp), (":account_id", self._id)])

    def precision(self):
        return self._precision

    def last_operation_date(self):
        last_timestamp = self._readSQL("SELECT MAX(o.timestamp) FROM operation_sequence AS o "
                                       "LEFT JOIN accounts AS a ON o.account_id=a.id WHERE a.id=:account_id",
                                       [(":account_id", self._id)])
        last_timestamp = 0 if last_timestamp == '' else last_timestamp
        return last_timestamp

    # Return amount of asset accumulated on account at given timestamp
    def get_asset_amount(self, timestamp: int, asset_id: int) -> Decimal:
        value = self._readSQL("SELECT amount_acc FROM ledger "
                              "WHERE account_id=:account_id AND asset_id=:asset_id AND timestamp<=:timestamp "
                              "AND (book_account=:money OR book_account=:assets OR book_account=:liabilities) "
                              "ORDER BY id DESC LIMIT 1",
                              [(":account_id", self._id), (":asset_id", asset_id), (":timestamp", timestamp),
                               (":money", BookAccount.Money), (":assets", BookAccount.Assets),
                               (":liabilities", BookAccount.Liabilities)])
        amount = Decimal(value) if value is not None else Decimal('0')
        return amount

