from decimal import Decimal
from jal.db.db import JalDB
from jal.db.asset import JalAsset
from jal.db.peer import JalPeer
import jal.db.operations
import jal.db.closed_trade
from jal.constants import Setup, BookAccount, PredefindedAccountType, PredefinedAsset


class JalAccount(JalDB):
    MONEY_FLOW = 1
    ASSETS_FLOW = 2

    def __init__(self, id: int = 0, data: dict = None, search: bool = False, create: bool = False) -> None:
        super().__init__()
        self._id = id
        if self._valid_data(data, search, create):
            if search:
                self._id = self._find_account(data)
            if create and not self._id:   # If we haven't found peer before and requested to create new record
                similar_id = self.readSQL("SELECT id FROM accounts WHERE :number=number",
                                          [(":number", data['number'])])
                if similar_id:
                    self._id = self._copy_similar_account(similar_id, data)
                else:   # Create new account record
                    if data['type'] == PredefindedAccountType.Investment and data['organization'] is None:
                        data['organization'] = JalPeer(
                            data={'name': self.tr("Bank for account #" + str(data['number']))},
                            search=True, create=True).id()
                    query = self.execSQL(
                        "INSERT INTO accounts (type_id, name, active, number, currency_id, organization_id, precision) "
                        "VALUES(:type, :name, 1, :number, :currency, :organization, :precision)",
                        [(":type", data['type']), (":name", data['name']), (":number", data['number']),
                         (":currency", data['currency']), (":organization", data['organization']),
                         (":precision", data['precision'])], commit=True)
                    self._id = query.lastInsertId()
        self._data = self.readSQL("SELECT type_id, name, number, currency_id, active, organization_id, country_id, "
                                   "reconciled_on, precision FROM accounts WHERE id=:id",
                                  [(":id", self._id)], named=True)
        self._type = self._data['type_id'] if self._data is not None else None
        self._name = self._data['name'] if self._data is not None else ''
        self._number = self._data['number'] if self._data is not None else None
        self._currency_id = self._data['currency_id'] if self._data is not None else None
        self._active = self._data['active'] if self._data is not None else None
        self._organization_id = self._data['organization_id'] if self._data is not None else None
        self._country_id = self._data['country_id'] if self._data is not None else None
        self._reconciled = int(self._data['reconciled_on']) if self._data is not None else 0
        self._precision = int(self._data['precision']) if self._data is not None else Setup.DEFAULT_ACCOUNT_PRECISION

    # Method returns a list of JalAccount objects for accounts of given type (or all if None given)
    # Flag "active_only" allows only active accounts output by default
    @staticmethod
    def get_all_accounts(account_type: int = None, active_only: bool = True) -> list:
        accounts = []
        query = JalDB.execSQL("SELECT id, active FROM accounts WHERE type_id=:type OR :type IS NULL",
                              [(":type", account_type)])
        while query.next():
            account_id, active = JalDB.readSQLrecord(query)
            if active_only and not active:
                continue
            accounts.append(JalAccount(int(account_id)))
        return accounts

    # Returns database id of the account
    def id(self) -> int:
        return self._id

    # Returns type of the account
    def type(self) -> int:
        return self._type

    # Returns name of the account
    def name(self) -> str:
        return self._name

    # Returns number of the account
    def number(self) -> str:
        return self._number

    # Returns currency id of the account
    def currency(self) -> int:
        return self._currency_id

    # Returns True if account is active and False otherwise
    def is_active(self) -> bool:
        if self._active:
            return True
        else:
            return False

    def organization(self) -> int:
        return self._organization_id

    # Returns country id of the account
    def country(self) -> int:
        return self._country_id

    def set_organization(self, peer_id: int) -> None:
        if not peer_id:
            peer_id = None
        _ = self.execSQL("UPDATE accounts SET organization_id=:peer_id WHERE id=:id",
                         [(":id", self._id), (":peer_id", peer_id)])
        self._organization_id = peer_id

    def reconciled_at(self) -> int:
        return self._reconciled

    def reconcile(self, timestamp: int):
        _ = self.execSQL("UPDATE accounts SET reconciled_on=:timestamp WHERE id = :account_id",
                         [(":timestamp", timestamp), (":account_id", self._id)])

    def precision(self) -> int:
        return self._precision

    def last_operation_date(self) -> int:
        last_timestamp = self.readSQL("SELECT MAX(o.timestamp) FROM operation_sequence AS o "
                                       "LEFT JOIN accounts AS a ON o.account_id=a.id WHERE a.id=:account_id",
                                      [(":account_id", self._id)])
        last_timestamp = 0 if last_timestamp == '' else last_timestamp
        return last_timestamp

    # Returns a list of dictionaries {"asset" JalAsset object, "amount": qty of asset, "value" initial asset value}
    # corresponding to assets present on account at given timestamp
    def assets_list(self, timestamp: int) -> list:
        assets = []
        query = self.execSQL(
            "WITH _last_ids AS ("
            "SELECT MAX(id) AS id, asset_id FROM ledger "
            "WHERE account_id=:account_id AND timestamp<=:timestamp GROUP BY asset_id"
            ") "
            "SELECT l.asset_id, amount_acc, value_acc "
            "FROM ledger l JOIN _last_ids d ON l.asset_id=d.asset_id AND l.id=d.id "
            "WHERE amount_acc!='0' AND book_account=:assets",
            [(":account_id", self._id), (":timestamp", timestamp), (":assets", BookAccount.Assets)])
        while query.next():
            try:
                asset_id, amount, value = self.readSQLrecord(query)
            except TypeError:  # Skip if None is returned (i.e. there are no assets)
                continue
            assets.append({"asset": JalAsset(int(asset_id)), "amount": Decimal(amount), "value": Decimal(value)})
        return assets

    # Return amount of asset accumulated on account at given timestamp
    def get_asset_amount(self, timestamp: int, asset_id: int) -> Decimal:
        asset =JalAsset(asset_id)
        if asset.type() == PredefinedAsset.Money:
            money = self.readSQL("SELECT amount_acc FROM ledger "
                                  "WHERE account_id=:account_id AND asset_id=:asset_id AND timestamp<=:timestamp "
                                  "AND book_account=:money ORDER BY id DESC LIMIT 1",
                                 [(":account_id", self._id), (":asset_id", asset_id),
                                   (":timestamp", timestamp), (":money", BookAccount.Money)])
            money = Decimal('0') if money is None else Decimal(money)
            debt = self.readSQL("SELECT amount_acc FROM ledger "
                                  "WHERE account_id=:account_id AND asset_id=:asset_id AND timestamp<=:timestamp "
                                  "AND book_account=:liabilities ORDER BY id DESC LIMIT 1",
                                [(":account_id", self._id), (":asset_id", asset_id),
                                   (":timestamp", timestamp), (":liabilities", BookAccount.Liabilities)])
            debt = Decimal('0') if debt is None else Decimal(debt)
            return money + debt
        else:
            value = self.readSQL("SELECT amount_acc FROM ledger "
                                  "WHERE account_id=:account_id AND asset_id=:asset_id AND timestamp<=:timestamp "
                                  "AND book_account=:assets ORDER BY id DESC LIMIT 1",
                                 [(":account_id", self._id), (":asset_id", asset_id),
                                   (":timestamp", timestamp), (":assets", BookAccount.Assets)])
            amount = Decimal(value) if value is not None else Decimal('0')
            return amount

    # Returns a list of JalClosedTrade objects recorded for the account
    def closed_trades_list(self) -> list:
        trades = []
        query = self.execSQL("SELECT id FROM trades_closed WHERE account_id=:account", [(":account", self._id)])
        while query.next():
            trades.append(jal.db.closed_trade.JalClosedTrade(self.readSQLrecord(query)))
        return trades

    # Returns a list of {"operation": LedgerTransaction, "price": Decimal, "remaining_qty": Decimal}
    # that represents all trades that were opened for given asset on this account
    # LedgerTransaction might be Trade, CorporateAction or Transfer
    # It doesn't take 'timestamp' as a parameter as it always return current open trades, not a retrospective position
    def open_trades_list(self, asset) -> list:
        trades = []
        query = self.execSQL("SELECT op_type, operation_id, price, remaining_qty "
                                 "FROM trades_opened "
                                 "WHERE remaining_qty!='0' AND account_id=:account AND asset_id=:asset",
                             [(":account", self._id), (":asset", asset.id())])
        while query.next():
            op_type, oid, price, qty = self.readSQLrecord(query)
            operation = jal.db.operations.LedgerTransaction().get_operation(op_type, oid,
                                                                            jal.db.operations.Transfer.Incoming)
            trades.append({"operation": operation, "price": Decimal(price), "remaining_qty": Decimal(qty)})
        return trades

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
        id = self.readSQL("SELECT id FROM accounts WHERE number=:account_number AND currency_id=:currency",
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
        query = self.execSQL(
            "INSERT INTO accounts (type_id, name, currency_id, active, number, organization_id, country_id, precision) "
            "SELECT type_id, :name, :currency, active, number, organization_id, country_id, precision "
            "FROM accounts WHERE id=:id", [(":id", similar.id()), (":name", name), (":currency", new_currency.id())])
        return query.lastInsertId()

    # This method is used only in TaxesFlowRus.prepare_flow_report() to get money/asset flow for russian tax report
    # direction is "in" or "out"
    # flow_type: MONEY_FLOW or ASSETS_FLOW to get flow of money or assets value
    def get_flow(self, begin, end, flow_type, direction):
        signs = {'in': +1, 'out': -1}
        sign = signs[direction]
        sql = {
            self.MONEY_FLOW: f"SELECT SUM(:sign*amount) FROM ledger WHERE (:sign*amount)>0 AND (book_account={BookAccount.Money} OR book_account={BookAccount.Liabilities})",
            self.ASSETS_FLOW: f"SELECT SUM(:sign*value) FROM ledger WHERE (:sign*value)>0 AND book_account={BookAccount.Assets} AND op_type!={jal.db.operations.LedgerTransaction.CorporateAction}"
        }
        value = self.readSQL(sql[flow_type] + " AND account_id=:account_id AND timestamp>=:begin AND timestamp<=:end",
                             [(":sign", sign), (":account_id", self._id), (":begin", begin), (":end", end)])
        if value:
            return Decimal(value)
        else:
            return Decimal('0')
