from decimal import Decimal
from jal.db.db import JalDB
from jal.db.asset import JalAsset
from jal.db.peer import JalPeer
import jal.db.operations
import jal.db.closed_trade
from jal.constants import Setup, BookAccount, PredefinedAccountType, PredefinedAsset
from jal.db.country import JalCountry


class JalAccount(JalDB):
    db_cache = []
    MONEY_FLOW = 1
    ASSETS_FLOW = 2

    def __init__(self, account_id: int = 0, data: dict = None, search: bool = False, create: bool = False) -> None:
        super().__init__(cached=True)
        if not JalAccount.db_cache:
            self._fetch_data()
        self._id = account_id
        if self._valid_data(data, search, create):
            if search:
                self._id = self._find_account(data)
            if create and not self._id:   # If we haven't found peer before and requested to create new record
                similar_id = self._read("SELECT id FROM accounts WHERE :number=number", [(":number", data['number'])])
                if similar_id:
                    self._id = self.__copy_similar_account(similar_id, data)
                else:   # Create new account record
                    if data['type'] == PredefinedAccountType.Investment and data['organization'] is None:
                        data['organization'] = JalPeer(
                            data={'name': self.tr("Bank for account #" + str(data['number']))},
                            search=True, create=True).id()
                    query = self._exec(
                        "INSERT INTO accounts (type_id, name, active, number, currency_id, organization_id, "
                        "country_id, precision) "
                        "VALUES(:type, :name, 1, :number, :currency, :organization, "
                        "coalesce((SELECT id FROM countries WHERE code=:country), 0), :precision)",
                        [(":type", data['type']), (":name", data['name']), (":number", data['number']),
                         (":currency", data['currency']), (":organization", data['organization']),
                         (":country", data['country']), (":precision", data['precision'])], commit=True)
                    self._id = query.lastInsertId()
                self._fetch_data(only_self=True)
        self._data = next((x for x in self.db_cache if x['id']==self._id), None)
        self._type = self._data['type_id'] if self._data is not None else None
        self._name = self._data['name'] if self._data is not None else ''
        self._number = self._data['number'] if self._data is not None else None
        self._currency_id = self._data['currency_id'] if self._data is not None else None
        self._active = self._data['active'] if self._data is not None else None
        self._organization_id = self._data['organization_id'] if self._data is not None else ''
        self._organization_id = int(self._organization_id) if self._organization_id else 0
        self._country = JalCountry(self._data['country_id']) if self._data is not None else JalCountry(0)
        self._reconciled = int(self._data['reconciled_on']) if self._data is not None else 0
        self._precision = int(self._data['precision']) if self._data is not None else Setup.DEFAULT_ACCOUNT_PRECISION

    def invalidate_cache(self):
        self._fetch_data()

    # JalAccount maintains single cache available for all instances
    @classmethod
    def class_cache(cls) -> True:
        return True

    def _fetch_data(self, only_self=False):
        if only_self:
            element = next((x for x in self.db_cache if x['id']==self._id), None)
            data = self._read("SELECT * FROM accounts WHERE id=:id", [(":id", self._id)], named=True)
            if data is not None:
                if element is not None:
                    JalAccount.db_cache[JalAccount.db_cache.index(element)] = data
                else:
                    JalAccount.db_cache.append(data)
        else:
            JalAccount.db_cache = []
            query = self._exec("SELECT * FROM accounts ORDER BY id")
            while query.next():
                JalAccount.db_cache.append(self._read_record(query, named=True))

    # Method returns a list of JalAccount objects for accounts of given type (or all if None given)
    # Flag "active_only" allows only active accounts output by default
    @classmethod
    def get_all_accounts(cls, account_type: int = None, active_only: bool = True) -> list:
        accounts = []
        query = cls._exec("SELECT id, active FROM accounts WHERE type_id=:type OR :type IS NULL",
                          [(":type", account_type)])
        while query.next():
            account_id, active = cls._read_record(query, cast=[int, bool])
            if active_only and not active:
                continue
            accounts.append(JalAccount(account_id))
        return accounts

    def dump(self):
        return self._data

    def dump_actions(self):
        actions = []
        query = self._exec("SELECT * FROM actions WHERE account_id=:id", [(":id", self._id)])
        while query.next():
            actions.append(self._read_record(query))
        for action in actions:
            query = self._exec("SELECT * FROM action_details WHERE pid=:id", [(":id", action[0])])
            while query.next():
                action.append(self._read_record(query))
        return actions

    # Returns everything from 'dividends' table associated with current account - used in test cases only
    def dump_dividends(self):
        dividends = []
        query = self._exec("SELECT * FROM dividends WHERE account_id=:id", [(":id", self._id)])
        while query.next():
            dividends.append(self._read_record(query))
        return dividends

    # Returns everything from 'trades' table associated with current account - used in test cases only
    def dump_trades(self):
        trades = []
        query = self._exec("SELECT * FROM trades WHERE account_id=:id", [(":id", self._id)])
        while query.next():
            trades.append(self._read_record(query))
        return trades

    # Returns everything from 'transfers' table associated with current account - used in test cases only
    def dump_transfers(self):
        transfers = []
        query = self._exec(
            "SELECT * FROM transfers WHERE withdrawal_account=:id OR deposit_account=:id OR fee_account=:id",
            [(":id", self._id)])
        while query.next():
            transfers.append(self._read_record(query))
        return transfers

    def dump_corporate_actions(self):
        actions = []
        query = self._exec("SELECT * FROM asset_actions WHERE account_id=:id", [(":id", self._id)])
        while query.next():
            actions.append(self._read_record(query))
        for action in actions:
            query = self._exec("SELECT * FROM action_results WHERE action_id=:id", [(":id", action[0])])
            while query.next():
                action.append(self._read_record(query))
        return actions

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

    # Returns country object for the account
    def country(self) -> JalCountry:
        return self._country

    def set_organization(self, peer_id: int) -> None:
        if not peer_id:
            peer_id = None
        _ = self._exec("UPDATE accounts SET organization_id=:peer_id WHERE id=:id",
                       [(":id", self._id), (":peer_id", peer_id)])
        self._organization_id = peer_id

    def reconciled_at(self) -> int:
        return self._reconciled

    def reconcile(self, timestamp: int):
        _ = self._exec("UPDATE accounts SET reconciled_on=:timestamp WHERE id = :account_id",
                       [(":timestamp", timestamp), (":account_id", self._id)])
        self._fetch_data(only_self=True)

    def precision(self) -> int:
        return self._precision

    def last_operation_date(self) -> int:
        last_timestamp = self._read("SELECT MAX(o.timestamp) FROM operation_sequence AS o "
                                    "LEFT JOIN accounts AS a ON o.account_id=a.id WHERE a.id=:account_id",
                                    [(":account_id", self._id)])
        last_timestamp = 0 if last_timestamp == '' else last_timestamp
        return last_timestamp

    # Returns a list of dictionaries {"asset" JalAsset object, "amount": qty of asset, "value" initial asset value}
    # corresponding to assets present on account at given timestamp
    def assets_list(self, timestamp: int) -> list:
        assets = []
        query = self._exec(
            "WITH _last_ids AS ("
            "SELECT MAX(id) AS id, asset_id FROM ledger "
            "WHERE account_id=:account_id AND timestamp<=:timestamp AND book_account=:assets GROUP BY asset_id"
            ") "
            "SELECT l.asset_id, amount_acc, value_acc "
            "FROM ledger l JOIN _last_ids d ON l.id=d.id "
            "WHERE amount_acc!='0'",
            [(":account_id", self._id), (":timestamp", timestamp), (":assets", BookAccount.Assets)])
        while query.next():
            try:
                asset_id, amount, value = self._read_record(query, cast=[int, Decimal, Decimal])
            except TypeError:  # Skip if None is returned (i.e. there are no assets)
                continue
            assets.append({"asset": JalAsset(asset_id), "amount": amount, "value": value})
        return assets

    # Return amount of asset accumulated on account at given timestamp
    def get_asset_amount(self, timestamp: int, asset_id: int) -> Decimal:
        asset =JalAsset(asset_id)
        if asset.type() == PredefinedAsset.Money:
            money = self._read("SELECT amount_acc FROM ledger "
                               "WHERE account_id=:account_id AND asset_id=:asset_id AND timestamp<=:timestamp "
                               "AND book_account=:money ORDER BY id DESC LIMIT 1",
                               [(":account_id", self._id), (":asset_id", asset_id),
                                (":timestamp", timestamp), (":money", BookAccount.Money)])
            money = Decimal('0') if money is None else Decimal(money)
            debt = self._read("SELECT amount_acc FROM ledger "
                              "WHERE account_id=:account_id AND asset_id=:asset_id AND timestamp<=:timestamp "
                              "AND book_account=:liabilities ORDER BY id DESC LIMIT 1",
                              [(":account_id", self._id), (":asset_id", asset_id),
                               (":timestamp", timestamp), (":liabilities", BookAccount.Liabilities)])
            debt = Decimal('0') if debt is None else Decimal(debt)
            return money + debt
        else:
            value = self._read("SELECT amount_acc FROM ledger "
                               "WHERE account_id=:account_id AND asset_id=:asset_id AND timestamp<=:timestamp "
                               "AND book_account=:assets ORDER BY id DESC LIMIT 1",
                               [(":account_id", self._id), (":asset_id", asset_id),
                                (":timestamp", timestamp), (":assets", BookAccount.Assets)])
            amount = Decimal(value) if value is not None else Decimal('0')
            return amount

    def get_book_turnover(self, book, begin, end) -> Decimal:
        value = self._read("SELECT SUM(amount) FROM ledger WHERE account_id=:account_id AND book_account=:book "
                           "AND timestamp>=:begin AND timestamp<=:end",
                           [(":account_id", self._id), (":book", book), (":begin", begin), (":end", end)])
        value = Decimal(value) if value else Decimal('0')
        return value

    def get_category_turnover(self, category_id, begin, end) -> Decimal:
        value = self._read("SELECT SUM(amount) FROM ledger WHERE account_id=:account_id AND category_id=:category "
                           "AND timestamp>=:begin AND timestamp<=:end",
                           [(":account_id", self._id), (":category", category_id), (":begin", begin), (":end", end)])
        value = Decimal(value) if value else Decimal('0')
        return value

    # Returns a list of JalClosedTrade objects recorded for the account
    def closed_trades_list(self) -> list:
        trades = []
        query = self._exec("SELECT id FROM trades_closed WHERE account_id=:account", [(":account", self._id)])
        while query.next():
            trades.append(jal.db.closed_trade.JalClosedTrade(self._read_record(query, cast=[int])))
        return trades

    # Returns a list of {"operation": LedgerTransaction, "price": Decimal, "remaining_qty": Decimal}
    # that represents all trades that were opened for given asset on this account
    # LedgerTransaction might be Trade, CorporateAction or Transfer
    # It doesn't take 'timestamp' as a parameter as it always return current open trades, not a retrospective position
    def open_trades_list(self, asset) -> list:
        trades = []
        query = self._exec("SELECT op_type, operation_id, price, remaining_qty FROM trades_opened "
                           "WHERE remaining_qty!='0' AND account_id=:account AND asset_id=:asset",
                           [(":account", self._id), (":asset", asset.id())])
        while query.next():
            op_type, oid, price, qty = self._read_record(query, cast=[int, int, Decimal, Decimal])
            operation = jal.db.operations.LedgerTransaction().get_operation(op_type, oid,
                                                                            jal.db.operations.Transfer.Incoming)
            trades.append({"operation": operation, "price": price, "remaining_qty": qty})
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
        data['country'] = data['country'] if 'country' in data else 0
        data['precision'] = data['precision'] if "precision" in data else Setup.DEFAULT_ACCOUNT_PRECISION
        return True

    def _find_account(self, data: dict) -> int:
        id = self._read("SELECT id FROM accounts WHERE number=:account_number AND currency_id=:currency",
                        [(":account_number", data['number']), (":currency", data['currency'])], check_unique=True)
        if id is None:
            return 0
        else:
            return id

    # Creates new account with different based on existing one.
    # Currency is taken from data['currency']. Name is auto-generated in form of AccountNumber.CurrencyName
    def __copy_similar_account(self, similar_id: int, data: dict) -> int:
        similar = JalAccount(similar_id)
        currency = JalAsset(similar.currency())
        new_currency = JalAsset(data['currency'])
        if similar.name()[-len(currency.symbol()):] == currency.symbol():
            name = similar.name()[:-len(currency.symbol())] + new_currency.symbol()
        else:
            name = similar.name() + '.' + new_currency.symbol()
        query = self._exec(
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
        value = self._read(sql[flow_type] + " AND account_id=:account_id AND timestamp>=:begin AND timestamp<=:end",
                           [(":sign", sign), (":account_id", self._id), (":begin", begin), (":end", end)])
        if value:
            return Decimal(value)
        else:
            return Decimal('0')
