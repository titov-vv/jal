from decimal import Decimal
from jal.db.db import JalDB
from jal.db.asset import JalAsset
from jal.db.peer import JalPeer
from jal.constants import Setup, BookAccount, PredefindedAccountType


class JalAccount(JalDB):
    def __init__(self, id: int = 0, data: dict = None, search: bool = False, create: bool = False) -> None:
        super().__init__()
        self._id = id
        if self._valid_data(data, search, create):
            if search:
                self._id = self._find_account(data)
            if create and not self._id:   # If we haven't found peer before and requested to create new record
                similar_id = self._readSQL("SELECT id FROM accounts WHERE :number=number",
                                           [(":number", data['number'])])
                if similar_id:
                    self._id = self._copy_similar_account(similar_id, data)
                else:   # Create new account record
                    if data['type'] == PredefindedAccountType.Investment and data['organization'] is None:
                        data['organization'] = JalPeer(
                            data={'name': self.tr("Bank for account #" + str(data['number']))},
                            search=True, create=True).id()
                    query = self._executeSQL(
                        "INSERT INTO accounts (type_id, name, active, number, currency_id, organization_id, precision) "
                        "VALUES(:type, :name, 1, :number, :currency, :organization, :precision)",
                        [(":type", data['type']), (":name", data['name']), (":number", data['number']),
                         (":currency", data['currency']), (":organization", data['organization']),
                         (":precision", data['precision'])], commit=True)
                    self._id = query.lastInsertId()
        self._data = self._readSQL("SELECT name, currency_id, organization_id, reconciled_on, precision "
                                   "FROM accounts WHERE id=:id", [(":id", self._id)], named=True)
        self._name = self._data['name'] if self._data is not None else None
        self._currency_id = self._data['currency_id'] if self._data is not None else None
        self._organization_id = self._data['organization_id'] if self._data is not None else None
        self._reconciled = int(self._data['reconciled_on']) if self._data is not None else 0
        self._precision = int(self._data['precision']) if self._data is not None else Setup.DEFAULT_ACCOUNT_PRECISION

    def id(self) -> int:
        return self._id

    def name(self) -> str:
        return self._name

    def currency(self) -> int:
        return self._currency_id

    def organization(self) -> int:
        return self._organization_id

    def set_organization(self, peer_id: int) -> None:
        if not peer_id:
            peer_id = None
        _ = self._executeSQL("UPDATE accounts SET organization_id=:peer_id WHERE id=:id",
                             [(":id", self._id), (":peer_id", peer_id)])
        self._organization_id = peer_id

    def reconciled_at(self) -> int:
        return self._reconciled

    def reconcile(self, timestamp: int):
        _ = self._executeSQL("UPDATE accounts SET reconciled_on=:timestamp WHERE id = :account_id",
                             [(":timestamp", timestamp), (":account_id", self._id)])

    def precision(self) -> int:
        return self._precision

    def last_operation_date(self) -> int:
        last_timestamp = self._readSQL("SELECT MAX(o.timestamp) FROM operation_sequence AS o "
                                       "LEFT JOIN accounts AS a ON o.account_id=a.id WHERE a.id=:account_id",
                                       [(":account_id", self._id)])
        last_timestamp = 0 if last_timestamp == '' else last_timestamp
        return last_timestamp

    # Returns a list of JalAsset objects corresponding to asssets present on account at given timestamp
    def assets_list(self, timestamp: int) -> list:
        assets = []
        query = self._executeSQL(
            "WITH _last_ids AS ("
            "SELECT MAX(id) AS id, asset_id FROM ledger "
            "WHERE account_id=:account_id AND timestamp<=:timestamp GROUP BY asset_id"
            ") "
            "SELECT l.asset_id "
            "FROM ledger l JOIN _last_ids d ON l.asset_id=d.asset_id AND l.id=d.id "
            "WHERE amount_acc!='0' AND book_account=:assets",
            [(":account_id", self._id), (":timestamp", timestamp), (":assets", BookAccount.Assets)])
        while query.next():
            assets.append(JalAsset(int(self._readSQLrecord(query))))
        return assets

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

    def _valid_data(self, data: dict, search: bool = False, create: bool = False) -> bool:
        if data is None:
            return False
        if search and not create:
            if 'number' in data and 'currency' in data:
                return True
            else:
                return False
        if 'type' not in data or 'currency' not in data:
            return False
        if 'name' not in data and "number" not in data:
            return False
        if "name" not in data:
            data['name'] = data['number'] + '.' + JalAsset(data['currency']).symbol()
        data['organization'] = data['organization'] if 'organization' in data else None
        data['precision'] = data['precision'] if "precision" in data else Setup.DEFAULT_ACCOUNT_PRECISION
        return True

    def _find_account(self, data: dict) -> int:
        id = self._readSQL("SELECT id FROM accounts WHERE number=:account_number AND currency_id=:currency",
                           [(":account_number", data['number']), (":currency", data['currency'])], check_unique=True)
        if id is None:
            return 0
        else:
            return id

    # Creates new account with different based on existing one.
    # Currency is taken from data['currency']. Name is auto-generated in form of AccountNumber.CurrencyName
    def _copy_similar_account(self, similar_id: int, data: dict) -> int:
        similar = JalAccount(similar_id)
        currency = JalAsset(similar.currency())
        new_currency = JalAsset(data['currency'])
        if similar.name()[-len(currency.symbol()):] == currency.symbol():
            name = similar.name()[:-len(currency.symbol())] + new_currency.symbol()
        else:
            name = similar.name() + '.' + new_currency.symbol()
        query = self._executeSQL(
            "INSERT INTO accounts (type_id, name, currency_id, active, number, organization_id, country_id, precision) "
            "SELECT type_id, :name, :currency, active, number, organization_id, country_id, precision "
            "FROM accounts WHERE id=:id", [(":id", similar.id()), (":name", name), (":currency", new_currency.id())])
        return query.lastInsertId()
