from decimal import Decimal
from jal.db.db import JalDB
from jal.db.asset import JalAsset
import jal.db.operations
import jal.db.closed_trade
from jal.constants import Setup, BookAccount, PredefinedAsset, PredefinedAgents
from jal.db.tag import JalTag
from jal.db.country import JalCountry
from jal.db.helpers import format_decimal, now_ts


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
                    query = self._exec(
                        "INSERT INTO accounts (name, active, investing, number, currency_id, organization_id, "
                        "country_id, precision) "
                        "VALUES(:name, 1, :investing, :number, :currency, :organization, "
                        "coalesce((SELECT id FROM countries WHERE code=:country), 0), :precision)",
                        [(":name", data['name']), (":investing", data['investing']), (":number", data['number']),
                         (":currency", data['currency']), (":organization", data['organization']),
                         (":country", data['country']), (":precision", data['precision'])], commit=True)
                    self._id = query.lastInsertId()
                self._fetch_data(only_self=True)
        self._data = next((x for x in self.db_cache if x['id']==self._id), None)
        self._tag = JalTag(self._data['tag_id']) if self._data is not None else None
        self._name = self._data['name'] if self._data is not None else JalTag(0)
        self._number = self._data['number'] if self._data is not None else None
        self._currency_id = self._data['currency_id'] if self._data is not None else None
        self._active = self._data['active'] if self._data is not None else None
        self._investing = bool(self._data['investing']) if self._data is not None else False
        self._organization_id = int(self._data['organization_id']) if self._data is not None else PredefinedAgents.Empty
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

    # Method returns a list of JalAccount objects with given filters (combined with AND):
    # investing_only - return only investing accounts (false by default)
    # active_only - return only active accounts (true by default)
    @classmethod
    def get_all_accounts(cls, investing_only: bool = False, active_only: bool = True) -> list:
        accounts = []
        all = 0 if active_only else 1
        all_types = 0 if investing_only else 1
        query = cls._exec("SELECT id FROM accounts WHERE investing >= (1-:all_types) AND active >= (1-:all)",
                          [(":all_types", all_types), (":all", all)])
        while query.next():
            account_id = cls._read_record(query, cast=[int])
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

    # Returns everything from 'asset_payments' table associated with current account - used in test cases only
    def dump_asset_payments(self):
        payments = []
        query = self._exec("SELECT * FROM asset_payments WHERE account_id=:id", [(":id", self._id)])
        while query.next():
            payments.append(self._read_record(query))
        return payments

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

    # Returns tag of the account
    def tag(self) -> JalTag:
        return self._tag

    @classmethod
    # Returns a list of tags used for accounts in form {tag_id(int): tag_name(str)}
    def get_all_tags(cls) -> dict:
        tags = {}
        query = cls._exec("SELECT DISTINCT a.tag_id, t.tag FROM accounts a JOIN tags t ON t.id=a.tag_id")
        while query.next():
            tag = cls._read_record(query, cast=[int, str])
            tags[tag[0]] = tag[1]
        return tags

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
        last_timestamp = now_ts() if last_timestamp > now_ts() else last_timestamp  # Skip future operations
        return last_timestamp

    # FIXME This method now looks duplicated with open_trades_list() - need some unification
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

    # Creates a record in 'trades_open' table that manifests current asset position
    def open_trade(self, timestamp, otype, oid, asset, price, qty):
        _ = self._exec(
            "INSERT INTO trades_opened(timestamp, op_type, operation_id, account_id, asset_id, price, remaining_qty) "
            "VALUES(:timestamp, :type, :operation_id, :account_id, :asset_id, :price, :remaining_qty)",
            [(":timestamp", timestamp), (":type", otype), (":operation_id", oid), (":account_id", self._id),
             (":asset_id", asset.id()), (":price", format_decimal(price)), (":remaining_qty", format_decimal(qty))])

    # Returns a list of {"operation": LedgerTransaction, "price": Decimal, "remaining_qty": Decimal}
    # that represents all trades that were opened for given asset on this account at given timestamp
    # LedgerTransaction might be Trade, CorporateAction or Transfer
    # Returns the latest open trades if timestamp is omitted.
    def open_trades_list(self, asset, timestamp=None) -> list:
        if timestamp is None:
            timestamp = Setup.MAX_TIMESTAMP
        trades = []
        query = self._exec("WITH open_trades_numbered AS "
                           "(SELECT timestamp, op_type, operation_id, price, remaining_qty, "
                           "ROW_NUMBER() OVER (PARTITION BY op_type, operation_id ORDER BY timestamp DESC, id DESC) AS row_no "
                           "FROM trades_opened WHERE account_id=:account AND asset_id=:asset AND timestamp<=:timestamp) "
                           "SELECT op_type, operation_id, price, remaining_qty "
                           "FROM open_trades_numbered WHERE row_no=1 AND remaining_qty!=:zero "
                           "ORDER BY timestamp, op_type DESC",
                           [(":account", self._id), (":asset", asset.id()),
                            (":timestamp", timestamp), (":zero", format_decimal(Decimal('0')))])
        while query.next():
            op_type, oid, price, qty = self._read_record(query, cast=[int, int, Decimal, Decimal])
            operation = jal.db.operations.LedgerTransaction().get_operation(op_type, oid, jal.db.operations.Transfer.Incoming)
            trades.append({"operation": operation, "price": price, "remaining_qty": qty})
        return trades

    # Returns amount that was paid for an asset that was hold on the account during time between start_ts and end_ts
    # Asset payment is counted if its ex-date is between start and end or, if ex-date is missing, the timestamp of
    # payment is between start and end timestamps
    def asset_payments_amount(self, asset, start_ts, end_ts) -> Decimal:
        payments = jal.db.operations.AssetPayment.get_list(self._id, asset.id())
        payments = [x for x in payments if (start_ts <= x.ex_date() <= end_ts) or (x.ex_date() == 0 and (start_ts <= x.timestamp() <= end_ts))]
        if payments:
            amount = sum([x.amount(currency_id=self._currency_id) for x in payments])
        else:
            amount = Decimal('0')
        return amount

    def _valid_data(self, data: dict, search: bool = False, create: bool = False) -> bool:
        if data is None:
            return False
        if search and not create:
            if 'number' in data and 'currency' in data:
                return True
            else:
                return False
        if 'currency' not in data:
            return False
        if 'name' not in data and "number" not in data:
            return False
        if "name" not in data:
            data['name'] = data['number'] + '.' + JalAsset(data['currency']).symbol()
        data['investing'] = data['investing'] if 'investing' in data else 0
        data['organization'] = data['organization'] if 'organization' in data else PredefinedAgents.Empty
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
            "INSERT INTO accounts (name, currency_id, active, investing, number, organization_id, country_id, precision) "
            "SELECT :name, :currency, active, investing, number, organization_id, country_id, precision "
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

    # Returns account balance at given timestamp
    def balance(self, timestamp: int) -> Decimal:
        value = Decimal('0')
        assets = self.assets_list(timestamp)
        for asset_data in assets:
            asset = asset_data['asset']
            asset_value = asset_data['amount'] * asset.quote(timestamp, self.currency())[1]
            value += asset_value
        money = self.get_asset_amount(timestamp, self.currency())
        value += money
        return value
