from decimal import Decimal
from jal.db.db import JalDB
from jal.db.asset import JalAsset
import jal.db.operations
import jal.db.closed_trade
from jal.constants import Setup, BookAccount, PredefinedAsset, PredefinedAgents, PredefinedAccountType, AccountData, AssetLocation
from jal.db.country import JalCountry
from jal.db.token_blacklist import normalize_address, is_valid_address
from jal.db.helpers import format_decimal, now_ts, year_begin, year_end
from jal.universal_cache import UniversalCache


class JalAccount(JalDB):
    db_cache = UniversalCache()
    MONEY_FLOW = 1
    ASSETS_FLOW = 2

    _TYPE_ICONS = {
        PredefinedAccountType.Cash: "tag_cash.ico",
        PredefinedAccountType.Bank: "tag_bank.ico",
        PredefinedAccountType.Card: "tag_card.ico",
        PredefinedAccountType.Broker: "tag_investing.ico",
        PredefinedAccountType.Wallet: "tag_wallet.ico",
    }

    def __init__(self, account_id: int = 0) -> None:
        super().__init__(cached=True)
        self._id = account_id
        self._data = self.db_cache.get_data(self._load_account_data, (self._id,))  # Load account data from cache or DB
        self._name = self._data['name'] if self._data is not None else None
        self._currency_id = self._data['currency_id'] if self._data is not None else None
        self._active = self._data['active'] if self._data is not None else None
        self._investing = bool(self._data['investing']) if self._data is not None else False
        self._organization_id = int(self._data['organization_id']) if self._data is not None else PredefinedAgents.Empty
        self._reconciled = int(self._data['reconciled_on']) if self._data is not None else 0
        self._type = int(self._data['account_type']) if self._data is not None else PredefinedAccountType.Cash
        self._apply_account_data()

    # Resolves the fields stored in the 'account_data' table, applying a default when an attribute row is absent
    def _apply_account_data(self) -> None:
        attributes = self._data['data'] if self._data is not None else {}
        self._number = attributes.get(AccountData.Number, None)
        self._country = JalCountry(int(attributes[AccountData.Country])) if AccountData.Country in attributes else JalCountry(0)
        self._precision = int(attributes[AccountData.Precision]) if AccountData.Precision in attributes else Setup.DEFAULT_ACCOUNT_PRECISION
        credit = attributes.get(AccountData.Credit, '0')
        self._credit_limit = Decimal(credit) if credit else Decimal('0')
        self._address = attributes.get(AccountData.Address, '')
        try:
            self._chain = int(attributes[AccountData.Chain])
        except (KeyError, TypeError, ValueError):
            self._chain = AssetLocation.UNDEFINED

    def invalidate_cache(self):
        self.db_cache.clear_cache()

    # JalAccount maintains single cache available for all instances
    @classmethod
    def class_cache(cls) -> True:
        return True

    # Loads a single account row (as a dict) from the DB by its id, or None if there is no such account.
    # The per-account attributes from 'account_data' are attached under the 'data' key as {datatype: value}.
    # Used as the loader function behind the shared UniversalCache (keyed by account id).
    @classmethod
    def _load_account_data(cls, account_id: int) -> dict:
        data = cls._read("SELECT * FROM accounts WHERE id=:id", [(":id", account_id)], named=True)
        if data is None:
            return None
        attributes = {}
        query = cls._exec("SELECT datatype, value FROM account_data WHERE account_id=:id ORDER BY datatype",
                          [(":id", account_id)])
        while query.next():
            datatype, value = cls._read_record(query, cast=[int, str])
            attributes[datatype] = value
        data['data'] = attributes
        return data

    # Returns a JalAccount matching 'number'+'currency' in 'data', or an empty JalAccount (id()==0) if not found
    @classmethod
    def find(cls, data: dict) -> "JalAccount":
        if 'number' not in data or 'currency' not in data:
            return cls(0)
        return cls(cls._find_account(data))

    @classmethod
    def _find_account(cls, data: dict) -> int:
        account_id = cls._read("SELECT a.id FROM accounts a "
                               "JOIN account_data d ON d.account_id=a.id AND d.datatype=:number_type "
                               "WHERE d.value=:account_number AND a.currency_id=:currency",
                               [(":number_type", AccountData.Number),
                                (":account_number", data['number']), (":currency", data['currency'])],
                               check_unique=True)
        return account_id if account_id else 0

    # Method returns a list of JalAccount objects with given filters (combined with AND):
    # investing_only - return only investing accounts (false by default)
    # active_only - return only active accounts (true by default)
    # currency_id - return only accounts with given currency (or all if 0)
    @classmethod
    def get_all_accounts(cls, investing_only: bool = False, active_only: bool = True, currency_id: int = 0) -> list:
        accounts = []
        all_activity = 0 if active_only else 1
        all_types = 0 if investing_only else 1
        sql_txt = "SELECT id FROM accounts WHERE investing >= (1-:all_types) AND active >= (1-:all)"
        sql_parameters = [(":all_types", all_types), (":all", all_activity)]
        if currency_id:
            sql_txt += " AND currency_id=:currency_id"
            sql_parameters += [(":currency_id", currency_id)]
        query = cls._exec(sql_txt, sql_parameters)
        while query.next():
            account_id = cls._read_record(query, cast=[int])
            accounts.append(JalAccount(account_id))
        return accounts

    @classmethod
    def get_taxable_accounts(cls, tax_date: int) -> list:
        accounts = []
        query = cls._exec("SELECT account_id FROM asset_payments WHERE timestamp>=:y_b AND timestamp<=:y_e "
                          "UNION "
                          "SELECT account_id FROM trades WHERE timestamp>=:y_b AND timestamp<=:y_e AND qty<0",
                          [(":y_b", year_begin(tax_date)), (":y_e", year_end(tax_date))])
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
            query = self._exec("SELECT * FROM action_details WHERE pid=:oid", [(":oid", action[0])])
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
            query = self._exec("SELECT * FROM asset_action_results WHERE action_id=:id", [(":id", action[0])])
            while query.next():
                action.append(self._read_record(query))
        return actions

    # Returns database id of the account
    def id(self) -> int:
        return self._id

    # Returns the account type (one of PredefinedAccountType values)
    def account_type(self) -> int:
        return self._type

    # Returns the translated name of the account type
    def type_name(self) -> str:
        return PredefinedAccountType().get_name(self._type)

    # Returns the icon filename (a JalIcon key) for this account's type
    def type_icon(self) -> str:
        return self._TYPE_ICONS.get(self._type, '')

    # Returns the on-chain address of a wallet account ('' if the account has none)
    def address(self) -> str:
        return self._address

    # Returns the blockchain of a wallet account as one of AssetLocation.BLOCKCHAINS (UNDEFINED if not set)
    def chain(self) -> int:
        return self._chain

    # Returns the icon filename (a JalIcon key) for a given account type
    @classmethod
    def get_type_icon(cls, type_id: int) -> str:
        return cls._TYPE_ICONS.get(type_id, '')

    @classmethod
    # Returns account types actually used by accounts, as {type_id(int): type_name(str)}
    def get_all_types(cls) -> dict:
        types = {}
        names = PredefinedAccountType()
        query = cls._exec("SELECT DISTINCT account_type FROM accounts")
        while query.next():
            type_id = cls._read_record(query, cast=[int])
            types[type_id] = names.get_name(type_id)
        return types

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
            peer_id = PredefinedAgents.Empty   # 'organization_id' is NOT NULL DEFAULT (1)
        _ = self._exec("UPDATE accounts SET organization_id=:peer_id WHERE id=:id",
                       [(":id", self._id), (":peer_id", peer_id)])
        self._data = self.db_cache.update_data(self._load_account_data, (self._id,))  # Refresh cached row from DB
        self._organization_id = peer_id

    def reconciled_at(self) -> int:
        return self._reconciled

    def reconcile(self, timestamp: int):
        _ = self._exec("UPDATE accounts SET reconciled_on=:timestamp WHERE id = :account_id",
                       [(":timestamp", timestamp), (":account_id", self._id)])
        self._data = self.db_cache.update_data(self._load_account_data, (self._id,))  # Refresh cached row from DB

    def precision(self) -> int:
        return self._precision

    def credit_limit(self) -> Decimal:
        return self._credit_limit

    # Returns a raw per-account attribute value from 'account_data' (or 'default' if it is not set)
    def get_data(self, datatype: int, default=None):
        if self._data is None:
            return default
        return self._data['data'].get(datatype, default)

    # Writes (or, when 'value' is None, removes) a per-account attribute in 'account_data' and refreshes the cache
    def set_data(self, datatype: int, value) -> None:
        if not self._id:
            return
        if value is None:
            _ = self._exec("DELETE FROM account_data WHERE account_id=:id AND datatype=:datatype",
                           [(":id", self._id), (":datatype", datatype)])
        else:
            _ = self._exec("INSERT OR REPLACE INTO account_data(account_id, datatype, value) "
                           "VALUES(:id, :datatype, :value)",
                           [(":id", self._id), (":datatype", datatype), (":value", str(value))])
        self._data = self.db_cache.update_data(self._load_account_data, (self._id,))  # Refresh cached row from DB
        self._apply_account_data()

    # Returns timestamp of last operation recorded for the account
    # If future=True then include future operations
    def last_operation_date(self, future=False) -> int:
        limit = Setup.MAX_TIMESTAMP if future else now_ts()
        last_timestamp = self._read("SELECT MAX(o.timestamp) FROM operation_sequence AS o "
                                    "LEFT JOIN accounts AS a ON o.account_id=a.id "
                                    "WHERE a.id=:account_id AND o.timestamp<=:now",
                                    [(":account_id", self._id), (":now", limit)])
        last_timestamp = 0 if last_timestamp == '' else last_timestamp
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

    # Returns a list of JalClosedTrade objects recorded for the account which represents normally closed trades
    # 'close_otypes' selects which kinds of closing operation to include; it defaults to Trade only, so tax reports
    # (which don't pass it) stay unchanged. The Deals report passes (Trade, Swap) to also show swap-realized deals.
    def closed_trades_list(self, asset=None, close_otypes=None) -> list:
        if close_otypes is None:
            close_otypes = (jal.db.operations.LedgerTransaction.Trade,)
        otypes = ','.join(str(int(x)) for x in close_otypes)
        trades = []
        if asset is None:
            query = self._exec(f"SELECT id FROM trades_closed WHERE close_otype IN ({otypes}) AND account_id=:account",
                               [(":account", self._id)])
        else:
            query = self._exec(f"SELECT id FROM trades_closed WHERE close_otype IN ({otypes}) AND account_id=:account AND asset_id=:asset",
                               [(":account", self._id), (":asset", asset.id())])
        while query.next():
            trades.append(jal.db.closed_trade.JalClosedTrade(self._read_record(query, cast=[int])))
        return trades

    # Creates a record in 'trades_open' table that manifests current asset position
    # trade - JalOpenTrade that should be stored as open trade (may represent existing position or be a new object)
    # asset - JalAsset for which trade is recorded
    # modified_by - indicate operation that modifies the original position
    # adjustment = (price_adj, qty_adj) - coefficients for price and quantity adjustments for operation
    def open_trade(self, trade, asset, modified_by=None, adjustment=(Decimal('1'), Decimal('1'))):
        operation = trade.open_operation()
        modified_by = operation if modified_by is None else modified_by
        # slice_id carries the slice's stable identity: a trade taken from open_trades_list() (a state change of an
        # existing slice after partial consumption) keeps it; a freshly opened or carried-over slice has None here and
        # the trades_opened_set_slice trigger assigns the new row's own id as its slice identity.
        _ = self._exec(
            "INSERT INTO trades_opened(timestamp, otype, oid, m_otype, m_oid, account_id, asset_id, "
            "price, remaining_qty, c_price, c_qty, slice_id) "
            "VALUES(:timestamp, :otype, :oid, :m_otype, :m_oid, :account_id, :asset_id, :price, "
            ":remaining_qty, :c_price, :c_qty, :slice_id)",
            [(":timestamp", modified_by.timestamp()), (":otype", operation.type()), (":oid", operation.id()),
             (":m_otype", modified_by.type()), (":m_oid", modified_by.id()), (":account_id", self._id),
             (":asset_id", asset.id()), (":price", format_decimal(trade.open_price())),
             (":remaining_qty", format_decimal(trade.open_qty())),
             (":c_price", format_decimal(trade.p_adjustment() * adjustment[0])),
             (":c_qty", format_decimal(trade.q_adjustment() * adjustment[1])),
             (":slice_id", trade.slice_id())])

    # Returns a list of JalOpenTrades that represents all trades that were opened for given asset at given timestamp
    # LedgerTransaction might be Trade, AssetPayment, CorporateAction or Transfer
    # Returns the latest open trades if timestamp is omitted.
    def open_trades_list(self, asset, timestamp=None) -> list:
        if timestamp is None:
            timestamp = Setup.MAX_TIMESTAMP
        trades = []
        # Positions are grouped by slice_id (the slice's stable identity), keeping only the latest state of each
        # slice. Grouping by (otype, oid) instead would merge two independent slices carried over from the same
        # original operation into one bucket and drop all but the newest, silently losing quantity and understating
        # realized P&L. (otype, oid) is still selected, but only to rebuild the opening operation and its cost basis.
        query = self._exec("WITH open_trades_numbered AS "
                           "(SELECT timestamp, otype, oid, price, remaining_qty, c_price, c_qty, slice_id, "
                           "ROW_NUMBER() OVER (PARTITION BY slice_id ORDER BY timestamp DESC, id DESC) AS row_no "
                           "FROM trades_opened WHERE account_id=:account AND asset_id=:asset AND timestamp<=:timestamp) "
                           "SELECT otype, oid, price, remaining_qty, c_price, c_qty, slice_id "
                           "FROM open_trades_numbered WHERE row_no=1 AND remaining_qty!=:zero ",
                           [(":account", self._id), (":asset", asset.id()),
                            (":timestamp", timestamp), (":zero", format_decimal(Decimal('0')))])
        while query.next():
            otype, oid, price, qty, p, q, slice_id = self._read_record(query, cast=[int, int, Decimal, Decimal, Decimal, Decimal, int])
            operation = jal.db.operations.LedgerTransaction().get_operation(otype, oid, jal.db.operations.Transfer.Incoming)
            trades.append(jal.db.closed_trade.JalOpenTrade(operation, price, qty, adjustments=(p, q), slice_id=slice_id))
        # For correct FIFO we take slices in order of their original operation, not last modification. slice_id breaks
        # ties deterministically: slices are assigned ids in replay (chronological) order, so among slices sharing an
        # original operation (a lot split by several carry-overs) the earliest-arrived one is consumed first.
        trades = sorted(trades, key=lambda op: (op.open_operation().timestamp(), op.slice_id()))
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

    # This method is used only in TaxesFlowRus.prepare_flow_report() to get money/asset flow for russian tax report
    # direction is "in" or "out"
    # flow_type: MONEY_FLOW or ASSETS_FLOW to get flow of money or assets value
    def get_flow(self, begin, end, flow_type, direction):
        signs = {'in': +1, 'out': -1}
        sign = signs[direction]
        sql = {
            self.MONEY_FLOW: f"SELECT SUM(:sign*amount) FROM ledger WHERE (:sign*amount)>0 AND (book_account={BookAccount.Money} OR book_account={BookAccount.Liabilities})",
            self.ASSETS_FLOW: f"SELECT SUM(:sign*value) FROM ledger WHERE (:sign*value)>0 AND book_account={BookAccount.Assets} AND otype!={jal.db.operations.LedgerTransaction.CorporateAction}"
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


class JalAccountCreator(JalDB):
    # Creates a new account, or - if an account with the same 'number' already exists under a different
    # currency - clones that account into 'currency_id' instead (name is then derived from the existing
    # account's name with the currency symbol swapped, ignoring 'name' below; see _copy_similar_account()).
    def __init__(self, currency_id: int, number: str, name: str = '', investing: int = 0,
                 organization: int = PredefinedAgents.Empty, country: str = '',
                 precision: int = Setup.DEFAULT_ACCOUNT_PRECISION,
                 account_type: int = PredefinedAccountType.Cash,
                 address: str = '', chain: int = AssetLocation.UNDEFINED) -> None:
        super().__init__(cached=False)
        # Chain and address are checked before anything is written: the account row is inserted and committed
        # below, so a failure raised later would leave a half-created account behind.
        address = self._validated_address(account_type, address, chain)
        similar_id = None
        # Cloning by account number exists for a broker account held in several currencies. A wallet is identified
        # by its address and never by a number, and the clone path doesn't store attributes at all - going through
        # it would produce a wallet without an address, bypassing the mandatory set checked above.
        if number and account_type != PredefinedAccountType.Wallet:
            similar_id = self._read("SELECT account_id FROM account_data WHERE datatype=:number_type AND value=:number",
                                    [(":number_type", AccountData.Number), (":number", number)])
        if similar_id:
            self._id = self._copy_similar_account(similar_id, currency_id)
        else:
            if not name:
                name = number + '.' + JalAsset(currency_id).symbol()
            query = self._exec(
                "INSERT INTO accounts (name, active, investing, currency_id, organization_id, account_type) "
                "VALUES(:name, 1, :investing, :currency, :organization, :account_type)",
                [(":name", name), (":investing", investing), (":currency", currency_id),
                 (":organization", organization), (":account_type", account_type)], commit=True)
            self._id = query.lastInsertId()
            self._store_attributes(number=number, country=country, precision=precision, account_type=account_type,
                                   address=address, chain=chain)
        # Refresh the newly created row in JalAccount's shared cache. A plain JalAccount(self._id) would
        # self-load on a cache miss, but doing it explicitly also overwrites a possibly stale (e.g. None)
        # entry cached for this id before the account existed.
        JalAccount.db_cache.update_data(JalAccount._load_account_data, (self._id,))

    def id(self) -> int:
        return self._id

    # Finalizes staging and returns a normal, cacheable JalAccount for subsequent use.
    def commit(self) -> JalAccount:
        return JalAccount(self._id)

    # Checks the chain/address pair given to the constructor and returns the address in the form it has to be
    # stored in. SQLite compares TEXT case-sensitively, so an address is always kept in the canonical form of its
    # chain - otherwise a lookup by the very same address may fail to find it back.
    # Raises ValueError on anything that can't be stored, before any row is written.
    @staticmethod
    def _validated_address(account_type: int, address: str, chain: int) -> str:
        if account_type == PredefinedAccountType.Wallet:
            # The whole mandatory set of a wallet is checked here and not only in _enforce_mandatory_attributes():
            # that one runs after the account row has been inserted and committed, so relying on it alone would
            # leave a half-created wallet behind whenever it fires.
            if chain not in AssetLocation.BLOCKCHAINS:
                raise ValueError(f"A wallet account requires a blockchain, got '{chain}'")
            if not address:
                raise ValueError("A wallet account requires an address")
        if not address:
            return ''
        address = normalize_address(chain, address)
        if not is_valid_address(chain, address):
            raise ValueError(f"'{address}' is not a valid address of {AssetLocation().get_name(chain)}")
        return address

    # Per-type mandatory attributes, keyed by account type -> [AccountData.* ...]. A wallet is useless without
    # knowing which address on which chain it tracks, and both are needed before any transaction can be fetched.
    _MANDATORY_ATTRIBUTES = {
        PredefinedAccountType.Wallet: [AccountData.Address, AccountData.Chain]
    }

    # Writes the sparse per-account attributes into 'account_data' (only values that differ from their default),
    # then enforces the per-type mandatory minimal set for the import/programmatic creation path.
    def _store_attributes(self, number: str, country: str, precision: int, account_type: int,
                          address: str = '', chain: int = AssetLocation.UNDEFINED) -> None:
        if number:
            self._store_attribute(AccountData.Number, number)
        if country:
            country_id = self._read("SELECT id FROM countries WHERE code=:code", [(":code", country)])
            if country_id:
                self._store_attribute(AccountData.Country, country_id)
        if precision != Setup.DEFAULT_ACCOUNT_PRECISION:
            self._store_attribute(AccountData.Precision, precision)
        if chain != AssetLocation.UNDEFINED:
            self._store_attribute(AccountData.Chain, chain)
        if address:
            self._store_attribute(AccountData.Address, address)
        self._enforce_mandatory_attributes(account_type)

    def _store_attribute(self, datatype: int, value) -> None:
        _ = self._exec("INSERT INTO account_data(account_id, datatype, value) VALUES(:id, :datatype, :value)",
                       [(":id", self._id), (":datatype", datatype), (":value", str(value))])

    # Raises ValueError if the created account lacks an attribute its type requires (e.g. a Wallet without an
    # address). No-op while _MANDATORY_ATTRIBUTES is empty; the crypto steps populate it.
    def _enforce_mandatory_attributes(self, account_type: int) -> None:
        names = AccountData()
        for datatype in self._MANDATORY_ATTRIBUTES.get(account_type, []):
            present = self._read("SELECT id FROM account_data WHERE account_id=:id AND datatype=:datatype",
                                 [(":id", self._id), (":datatype", datatype)])
            if not present:
                raise ValueError(f"Account {self._id} of type {account_type} is missing required attribute "
                                 f"'{names.get_name(datatype)}'")

    # Creates a new account based on 'similar_id', with currency swapped to 'currency_id'.
    # Name is auto-generated by swapping the old currency symbol for the new one in the similar account's name.
    def _copy_similar_account(self, similar_id: int, currency_id: int) -> int:
        similar = JalAccount(similar_id)
        old_currency = JalAsset(similar.currency())
        new_currency = JalAsset(currency_id)
        if similar.name()[-len(old_currency.symbol()):] == old_currency.symbol():
            name = similar.name()[:-len(old_currency.symbol())] + new_currency.symbol()
        else:
            name = similar.name() + '.' + new_currency.symbol()
        query = self._exec(
            "INSERT INTO accounts (name, currency_id, active, investing, organization_id, account_type) "
            "SELECT :name, :currency, active, investing, organization_id, account_type "
            "FROM accounts WHERE id=:id", [(":id", similar.id()), (":name", name), (":currency", new_currency.id())])
        new_id = query.lastInsertId()
        # Clone the source account's per-account attributes (number/credit/country/precision, ...) too
        self._exec("INSERT INTO account_data (account_id, datatype, value) "
                   "SELECT :new_id, datatype, value FROM account_data WHERE account_id=:old_id",
                   [(":new_id", new_id), (":old_id", similar_id)])
        return new_id
