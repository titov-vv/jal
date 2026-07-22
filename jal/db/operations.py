import logging
from decimal import Decimal
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from jal.constants import BookAccount, PredefinedCategory, PredefinedAsset
from jal.db.helpers import format_decimal
from jal.db.db import JalDB
import jal.db.account
from jal.db.asset import JalAsset
from jal.db.symbol import JalSymbol
from jal.db.closed_trade import JalClosedTrade, JalOpenTrade
from jal.widgets.helpers import ts2dt
from jal.widgets.icons import JalIcon


# ----------------------------------------------------------------------------------------------------------------------
# Class to define and handle custom ledger errors
class LedgerError(Exception):
    pass


# ----------------------------------------------------------------------------------------------------------------------
class LedgerTransaction(JalDB):
    NoOpException = 'NoLedgerOperation'
    NA = 0                  # Transaction types - these are aligned with tabs in main window
    IncomeSpending = 1
    AssetPayment = 2
    Trade = 3
    Transfer = 4
    CorporateAction = 5
    Conversion = 6
    Swap = 7
    Bridge = 8
    _db_table = ''   # Table where operation is stored in DB
    _db_fields = {}

    def __init__(self, operation_data=None):
        super().__init__()
        if type(operation_data) == dict:
            oid = self.create_operation(self._db_table, self._db_fields, operation_data)
        else:
            oid = operation_data
        self._oid = oid
        self._otype = 0
        self._oname = ''
        self._subtype = 0
        self._data = None
        self._view_rows = 1    # How many rows it will require operation in QTableView
        self._icon = JalIcon[JalIcon.NONE]
        self._timestamp = 0
        self._account = None
        self._account_name = ''
        self._account_currency = ''
        self._asset = None
        self._peer_id = 0
        self._number = ''
        self._reconciled = False

    def tr(self, text):
        return QApplication.translate("LedgerTransaction", text)

    def dump(self):
        for key in self._data:
            # An operation may hold optional fields that are absent (a pending bridge leg, the receiving leg of a
            # same-chain swap): SQL NULL reads back as '' and has nothing to convert. Skipping it matters because
            # dump() is what builds the text of every LedgerError - it must never raise itself.
            if self._data[key] is None or self._data[key] == '':
                continue
            if 'timestamp' in key:
                self._data[key] = ts2dt(self._data[key])
            if 'account' in key:
                self._data[key] = jal.db.account.JalAccount(self._data[key]).name()
        return str(self._data)

    @staticmethod
    def get_operation(operation_type, oid, opart=0):
        if operation_type == LedgerTransaction.IncomeSpending:
            return IncomeSpending(oid, opart=opart)
        elif operation_type == LedgerTransaction.AssetPayment:
            return AssetPayment(oid, opart=opart)
        elif operation_type == LedgerTransaction.Trade:
            return Trade(oid, opart=opart)
        elif operation_type == LedgerTransaction.Transfer:
            return Transfer(oid, opart)
        elif operation_type == LedgerTransaction.CorporateAction:
            return CorporateAction(oid)
        elif operation_type == LedgerTransaction.Conversion:
            return Conversion(oid, opart=opart)
        elif operation_type == LedgerTransaction.Swap:
            return Swap(oid, opart=opart)
        elif operation_type == LedgerTransaction.Bridge:
            return Bridge(oid, opart=opart)
        else:
            raise ValueError(f"An attempt to select unknown operation type: {operation_type}")

    @staticmethod
    def create_new(operation_type, operation_data):
        if operation_type == LedgerTransaction.IncomeSpending:
            return IncomeSpending(operation_data)
        elif operation_type == LedgerTransaction.AssetPayment:
            return AssetPayment(operation_data)
        elif operation_type == LedgerTransaction.Trade:
            return Trade(operation_data)
        elif operation_type == LedgerTransaction.Transfer:
            return Transfer(operation_data, Transfer.Outgoing)
        elif operation_type == LedgerTransaction.CorporateAction:
            return CorporateAction(operation_data)
        elif operation_type == LedgerTransaction.Conversion:
            return Conversion(operation_data)
        elif operation_type == LedgerTransaction.Swap:
            return Swap(operation_data)
        elif operation_type == LedgerTransaction.Bridge:
            return Bridge(operation_data, Bridge.Outgoing)
        else:
            raise ValueError(f"An attempt to create unknown operation type: {operation_type}")

    # Deletes operation from database
    def delete(self) -> None:
        _ = self._exec(f"DELETE FROM {self._db_table} WHERE oid={self._oid}")
        self._oid = 0
        self._otype = 0
        self._data = None

    # Returns operation id if operation found by operation data, else 0
    def find_operation(self, operation_type: int, operation_data: dict) -> int:
        if operation_type == LedgerTransaction.IncomeSpending:
            table = IncomeSpending._db_table
            fields = IncomeSpending._db_fields
        elif operation_type == LedgerTransaction.AssetPayment:
            table = AssetPayment._db_table
            fields = AssetPayment._db_fields
        elif operation_type == LedgerTransaction.Trade:
            table = Trade._db_table
            fields = Trade._db_fields
        elif operation_type == LedgerTransaction.Transfer:
            table = Transfer._db_table
            fields = Transfer._db_fields
        elif operation_type == LedgerTransaction.CorporateAction:
            table = CorporateAction._db_table
            fields = CorporateAction._db_fields
        elif operation_type == LedgerTransaction.Conversion:
            table = Conversion._db_table
            fields = Conversion._db_fields
        elif operation_type == LedgerTransaction.Swap:
            table = Swap._db_table
            fields = Swap._db_fields
        elif operation_type == LedgerTransaction.Bridge:
            table = Bridge._db_table
            fields = Bridge._db_fields
        else:
            raise ValueError(f"An attempt to create unknown operation type: {operation_type}")
        self.validate_operation_data(table, fields, operation_data)
        return self.locate_operation(table, fields, operation_data)

    # Returns how many rows is required to display operation in QTableView
    def view_rows(self) -> int:
        return self._view_rows

    def _money_total(self, account_id) -> Decimal:
        money = self._read("SELECT amount_acc FROM ledger_totals WHERE otype=:otype AND oid=:oid AND "
                           "account_id = :account_id AND book_account=:book",
                           [(":otype", self._otype), (":oid", self._oid),
                            (":account_id", account_id), (":book", BookAccount.Money)])
        debt = self._read("SELECT amount_acc FROM ledger_totals WHERE otype=:otype AND oid=:oid AND "
                          "account_id = :account_id AND book_account=:book",
                          [(":otype", self._otype), (":oid", self._oid),
                           (":account_id", account_id), (":book", BookAccount.Liabilities)])
        if money is None and debt is None:
            return Decimal('NaN')
        money = Decimal('0') if money is None else Decimal(money)
        debt = Decimal('0') if debt is None else Decimal(debt)
        return money + debt

    def _asset_total(self, account_id, asset_id) -> Decimal:
        amount = self._read("SELECT amount_acc FROM ledger_totals WHERE otype=:otype AND oid=:oid AND "
                            "account_id=:account_id AND asset_id=:asset_id AND book_account=:book",
                            [(":otype", self._otype), (":oid", self._oid), (":account_id", account_id),
                             (":asset_id", asset_id), (":book", BookAccount.Assets)])
        amount = Decimal('NaN') if amount is None else Decimal(amount)
        return amount

    # Performs FIFO deals match in ledger: takes current open positions from 'trades_opened' table and converts
    # them into deals in 'trades_closed' table while supplied qty is enough.
    # deal_sign = +1 if closing deal is Buy operation and -1 if it is Sell operation.
    # qty - quantity of asset that closes previous open positions
    # price is None if we process corporate action or transfer where we keep initial value and don't have profit or loss
    # 'asset'/'account' default to the single asset and account of the operation, which is what every operation
    # dealing in one asset needs. They are given explicitly only when an operation consumes a second asset besides
    # its own - a transfer paying on-chain gas in the native coin of the chain (see Transfer.processAssetFee).
    # record_deals=False consumes the open positions without writing anything into 'trades_closed': the quantity and
    # the cost basis leave the position, but no deal is created and therefore no profit or loss is realized.
    # Returns total qty, value of deals created.
    def _close_deals_fifo(self, deal_sign, qty, asset=None, account=None, record_deals=True):
        if asset is None and account is None:
            assert self._asset.id() == self.asset().id()      # The function works with these assumptions as any operation
            assert self._account.id() == self.account().id()  # takes only one incoming asset and account
        asset = self._asset if asset is None else asset
        account = self._account if account is None else account
        processed_qty = Decimal('0')
        processed_value = Decimal('0')
        open_trades = account.open_trades_list(asset)
        for trade in open_trades:
            remaining_qty = trade.open_qty(adjusted=True)
            next_deal_qty = remaining_qty
            if (processed_qty + next_deal_qty) > qty:  # We can't close full quantity with current operation
                next_deal_qty = qty - processed_qty    # If it happens - just process the remainder of the trade
            trade.set_qty((remaining_qty - next_deal_qty)/trade.q_adjustment())
            account.open_trade(trade, asset, modified_by=self)
            if record_deals:
                JalClosedTrade.create_from_trades(trade, self, (-deal_sign) * next_deal_qty)
            processed_qty += next_deal_qty
            processed_value += (next_deal_qty * trade.open_price(adjusted=True))
            if processed_qty == qty:
                break
        return processed_qty, processed_value

    # Returns a list of JalClosedTrade objects that were closed by calling operation (used in Transfer and CorporateAction)
    def _deals_closed_by_operation(self):
        trades = []
        query = self._exec("SELECT id FROM trades_closed WHERE close_otype=:otype AND close_oid=:oid AND account_id=:account AND asset_id=:asset",
                [(":otype", self._otype), (":oid", self._oid), (":account", self._account.id()), (":asset", self._asset.id())])
        while query.next():
            trades.append(jal.db.closed_trade.JalClosedTrade(self._read_record(query, cast=[int])))
        return trades

    def id(self):
        return self._oid

    def type(self):
        return self._otype

    def subtype(self):
        return self._subtype

    def oid(self):
        return self._oid

    def icon(self) -> QIcon:
        return self._icon

    def name(self):
        return self._oname

    def timestamp(self):
        return self._timestamp

    def account(self):
        return self._account

    def peer(self) -> int:   # Return peer_id of current operation
        return self._peer_id

    def account_name(self):
        if self._account is None:
            return ''
        else:
            return self._account.name()

    def account_id(self):
        return self._account.id()

    # Returns asset object related to the operation
    def asset(self) -> JalAsset:
        return self._asset

    def asset_name(self):   # TODO think about replacement by call to asset.name() but self._asset may be None
        if self._asset is None:
            return ''
        else:
            return self._asset.name()

    def number(self):
        return self._number

    def amount(self):
        return 0

    def description(self, part_only=False) -> str:
        return ''

    def value_change(self, part_only=False) -> list:
        return []

    def value_total(self) -> list:
        return []

    def value_currency(self) -> str:
        return ''

    def reconciled(self) -> bool:
        return self._reconciled

    # If possible assigns given tag to the operation (or all its components)
    def assign_tag(self, tag_id: int):
        pass

    def processLedger(self, ledger):
        raise NotImplementedError(f"processLedger() method is not defined in {type(self).__name__} class")


# ----------------------------------------------------------------------------------------------------------------------
class IncomeSpending(LedgerTransaction):
    _db_table = "actions"
    _db_fields = {
        "timestamp": {"mandatory": True, "validation": False},
        "account_id": {"mandatory": True, "validation": False},
        "peer_id": {"mandatory": True, "validation": False},
        "alt_currency_id": {"mandatory": False, "validation": False},
        "lines": {
            "mandatory": True, "validation": False, "children": True,
            "child_table": "action_details", "child_pid": "pid",
            "child_fields": {
                "pid": {"mandatory": True, "validation": False},    # TODO Check if mandatory requirement is true here and works as expected
                "category_id": {"mandatory": True, "validation": False},
                "tag_id": {"mandatory": False, "validation": False},
                "amount": {"mandatory": True, "validation": False},
                "amount_alt": {"mandatory": False, "validation": False},
                "note": {"mandatory": False, "validation": False}
            }
        }
    }

    def __init__(self, oid=None, opart=None):
        super().__init__(oid)
        self._otype = LedgerTransaction.IncomeSpending
        self._opart = opart
        self._data = self._read("SELECT a.timestamp, a.account_id, a.peer_id, p.name AS peer, "
                                "a.alt_currency_id AS currency FROM actions AS a "
                                "LEFT JOIN agents AS p ON a.peer_id = p.id WHERE a.oid=:oid",
                                [(":oid", self._oid)], named=True)
        if self._data is None:
            raise IndexError(LedgerTransaction.NoOpException)
        self._timestamp = self._data['timestamp']
        self._account = jal.db.account.JalAccount(self._data['account_id'])
        self._account_name = self._account.name()
        self._account_currency = JalAsset(self._account.currency()).symbol()
        self._reconciled = self._account.reconciled_at() >= self._timestamp
        self._peer_id = self._data['peer_id']
        self._peer = self._data['peer']
        self._currency = self._data['currency']
        details_query = self._exec("SELECT d.id, d.category_id, c.name AS category, d.tag_id, t.tag, "
                                   "d.amount, d.amount_alt, d.note FROM action_details AS d "
                                   "LEFT JOIN categories AS c ON c.id=d.category_id "
                                   "LEFT JOIN tags AS t ON t.id=d.tag_id "
                                   "WHERE d.pid= :pid", [(":pid", self._oid)])
        self._details = []
        while details_query.next():
            self._details.append(self._read_record(details_query, named=True))
        self._amount = sum(Decimal(line['amount']) for line in self._details) if self._details else Decimal('0')
        if self._amount < 0:
            self._icon = JalIcon[JalIcon.MINUS]
            self._oname = self.tr("Spending")
        else:
            self._icon = JalIcon[JalIcon.PLUS]
            self._oname = self.tr("Income")
        if self._currency:
            self._view_rows = 2
            self._currency_name = JalAsset(self._currency).symbol()
        self._amount_alt = sum(Decimal(line['amount_alt']) for line in self._details) if self._details else Decimal('0')

    def description(self, part_only=False) -> str:
        if part_only and self._opart is not None:
            return n[0] if (n := [x['note'] for x in self._details if x['id'] == self._opart]) else ''
        description = self._peer
        if self._currency:
            if self._amount_alt == Decimal('0'):
                return description
            try:
                rate = self._amount_alt / self._amount
            except ZeroDivisionError:
                return description
            description += "\n" + self.tr("Rate: ")
            if rate >= 1:
                description += f"{rate:.4f} {self._currency_name}/{self._account_currency}"
            else:
                description += f"{1/rate:.4f} {self._account_currency}/{self._currency_name}"
        return description

    def value_change(self, part_only=False) -> list:
        if part_only and self._opart is not None:
            return [Decimal(x['amount']) for x in self._details if x['id'] == self._opart]
        if self._currency:
            return [self._amount, self._amount_alt]
        else:
            return [self._amount]

    def value_currency(self) -> str:
        if self._currency and not self._opart:
            return f" {self._account_currency}\n {self._currency_name}"
        else:
            return f" {self._account_currency}"

    def value_total(self) -> list:
        total = [self._money_total(self._account.id())]
        if self._currency:
            total.append(None)
        return total

    # Returns a list of income/spending lines in form of
    # {"category_id", "category", "tag_id", "tag", "amount", "amount_alt", "note"}
    def lines(self) -> list:
        return self._details

    def amount(self) -> Decimal:
        return self._amount

    # it assigns tag to all operation details
    def assign_tag(self, tag_id: int):
        self._exec("UPDATE action_details SET tag_id=:tag_id WHERE pid=:pid",
                   [(":tag_id", tag_id), (":pid", self._oid)])

    def processLedger(self, ledger):
        if len(self._details) == 0:
            logging.warning(self.tr("Income/Spending transaction has no details: ") + f" {self.dump()}")
            return
        if self._amount < Decimal('0'):
            credit_taken = ledger.takeCredit(self, self._account.id(), -self._amount)
            ledger.appendTransaction(self, BookAccount.Money, -(-self._amount - credit_taken))
        else:
            credit_returned = ledger.returnCredit(self, self._account.id(), self._amount)
            if credit_returned < self._amount:
                ledger.appendTransaction(self, BookAccount.Money, self._amount - credit_returned)
        for detail in self._details:
            book = BookAccount.Costs if Decimal(detail['amount']) < Decimal('0') else BookAccount.Incomes
            ledger.appendTransaction(self, book, -Decimal(detail['amount']), part=detail['id'],
                                     category=detail['category_id'], peer=self._peer_id, tag=detail['tag_id'])


# ----------------------------------------------------------------------------------------------------------------------
class AssetPayment(LedgerTransaction):
    Dividend = 1
    BondInterest = 2
    StockDividend = 3
    StockVesting = 4
    BondAmortization = 5
    Fee = 6
    GasFee = 7             # Gas burned by a transaction that moved nothing - an approval, a failed call, ...
    StakingReward = 8      # Coins received for staking; lending interest is recorded the same way
    _db_table = "asset_payments"
    _db_fields = {
        "timestamp": {"mandatory": True, "validation": True},
        "ex_date": {"mandatory": False, "validation": False},
        "number": {"mandatory": False, "validation": True, "default": ''},
        "type": {"mandatory": True, "validation": True},
        "account_id": {"mandatory": True, "validation": True},
        "symbol_id": {"mandatory": True, "validation": True},
        "amount": {"mandatory": True, "validation": True},
        "tax": {"mandatory": False, "validation": False},
        "note": {"mandatory": False, "validation": True}
    }
    PART_VALUE = 1
    PART_TAX = 2

    def __init__(self, oid=None, opart=None):
        icons = {
            AssetPayment.Dividend: JalIcon.DIVIDEND,
            AssetPayment.BondInterest: JalIcon.BOND_INTEREST,
            AssetPayment.StockDividend: JalIcon.STOCK_DIVIDEND,
            AssetPayment.StockVesting: JalIcon.STOCK_VESTING,
            AssetPayment.BondAmortization: JalIcon.BOND_AMORTIZATION,
            AssetPayment.Fee: JalIcon.FEE,
            AssetPayment.GasFee: JalIcon.FEE,
            AssetPayment.StakingReward: JalIcon.INTEREST
        }
        self.names = {
            AssetPayment.NA: self.tr("UNDEFINED"),
            AssetPayment.Dividend: self.tr("Dividend"),
            AssetPayment.BondInterest: self.tr("Bond Interest"),
            AssetPayment.StockDividend: self.tr("Stock Dividend"),
            AssetPayment.StockVesting: self.tr("Stock Vesting"),
            AssetPayment.BondAmortization: self.tr("Bond Amortization"),
            AssetPayment.Fee: self.tr("Asset fee/tax"),
            AssetPayment.GasFee: self.tr("Gas fee"),
            AssetPayment.StakingReward: self.tr("Staking reward")
        }
        super().__init__(oid)
        self._otype = LedgerTransaction.AssetPayment
        self._opart = opart
        self._view_rows = 2
        self._data = self._read("SELECT p.type, p.timestamp, p.ex_date, p.number, p.account_id, "
                                "p.symbol_id, p.amount, p.tax, l.amount_acc AS t_qty, p.note AS note "
                                "FROM asset_payments AS p "
                                "LEFT JOIN ledger_totals AS l ON l.otype=p.otype AND l.oid=p.oid "
                                "AND l.book_account = :book_assets WHERE p.oid=:oid",
                                [(":book_assets", BookAccount.Assets), (":oid", self._oid)], named=True)
        if self._data is None:
            raise IndexError(LedgerTransaction.NoOpException)
        self._subtype = self._data['type']
        self._oname = self.names[self._subtype]
        try:
            self._icon = JalIcon[icons[self._subtype]]
        except KeyError:
            assert False, "Unknown dividend type"
        self._timestamp = self._data['timestamp']
        self._ex_date = self._data['ex_date'] if self._data['ex_date'] else 0
        self._account = jal.db.account.JalAccount(self._data['account_id'])
        self._account_name = self._account.name()
        self._account_currency = JalAsset(self._account.currency()).symbol()
        self._reconciled = self._account.reconciled_at() >= self._timestamp
        self._symbol = JalSymbol(self._data['symbol_id'])
        self._asset = self._symbol.asset()
        self._number = self._data['number']
        self._amount = Decimal(self._data['amount'])
        self._tax = Decimal(self._data['tax'])
        self._note = self._data['note']
        self._peer_id = self._account.organization()

    # Returns a list of Dividend objects for given asset, account and subtype
    # if asset_id is 0 - return for all assets, if subtype is 0 - return all types
    # skip_accrued=True - don't include accrued interest in resulting list
    @classmethod
    def get_list(cls, account_id: int, asset_id: int = 0, subtype: int = 0, skip_accrued: bool = False) -> list:
        payments = []
        if skip_accrued:  # Paired trade is matched via asset, not symbol (consistent with Trade.accrued_interest())
            query = "SELECT p.oid FROM asset_payments p LEFT JOIN asset_symbol ps ON p.symbol_id=ps.id "\
                    "LEFT JOIN trades t ON p.account_id=t.account_id "\
                    "AND t.symbol_id IN (SELECT id FROM asset_symbol WHERE asset_id=ps.asset_id) "\
                    "AND p.number=t.number AND t.number!='' "\
                    "WHERE p.account_id=:account AND t.oid IS NULL"
        else:
            query = "SELECT p.oid FROM asset_payments p WHERE p.account_id=:account"
        params = [(":account", account_id)]
        if asset_id:
            query += " AND p.symbol_id IN (SELECT id FROM asset_symbol WHERE asset_id=:asset)"
            params += [(":asset", asset_id)]
        if subtype:
            query += " AND p.type=:type"
            params += [(":type", subtype)]
        query = cls._exec(query, params)
        while query.next():
            payments.append(AssetPayment(cls._read_record(query, cast=[int])))
        return payments

    # Settlement returns timestamp - it is required for stock dividend/vesting
    def settlement(self) -> int:
        return self._timestamp

    # Returns ex-dividend date if it is present for this dividend
    def ex_date(self) -> int:
        return self._ex_date

    # Return price of asset for stock dividend and vesting
    def price(self) -> Decimal:
        if self._subtype == AssetPayment.StakingReward:
            # A reward arrives at a block timestamp, which no daily quote series will ever match exactly, so the
            # last known price is used instead of demanding a quote of that very second. A reward that can't be
            # priced at all opens a lot at zero and would show the whole proceeds as gain when sold, so it is
            # refused rather than silently mis-stating the basis.
            quote_timestamp, price = self._asset.quote(self._timestamp, self._account.currency())
            if not quote_timestamp:
                # Refused rather than opened at a zero basis, which would silently report the whole proceeds as
                # gain when the coins are sold. This is recoverable and needs no re-import: the reward itself is
                # already stored with the right amount, it is only the valuation that is missing, so downloading
                # the quotes and rebuilding the ledger completes it. That also resolves the ordering problem of a
                # first-ever import, where the asset is created by that very import and can have no quotes yet.
                raise ValueError(self.tr("No quote to value a staking reward - download quotes for this asset "
                                         "and rebuild the ledger.") + f" Operation: {self.dump()}")
            return price
        if self._subtype != AssetPayment.StockDividend and self._subtype != AssetPayment.StockVesting:
            return Decimal('0')
        quote_timestamp, price = self._asset.quote(self._timestamp, self._account.currency())
        if quote_timestamp != self._timestamp:
            raise ValueError(self.tr("No stock quote for stock dividend or vesting.") + f" Operation: {self.dump()}")
        return price

    # There are no any fee possible for Dividend
    def fee(self) -> Decimal:
        return Decimal('0')

    def qty(self) -> Decimal:
        return self.amount()

    # Returns amount of dividend:
    # if currency_id = 0 - return unadjusted value of amount assigned to dividend (for example stock number for vesting)
    # if currency is given - then converts dividend amount into given currency
    def amount(self, currency_id: int = 0) -> Decimal:
        if not currency_id:
            return self._amount
        if self._subtype == AssetPayment.StockDividend or self._subtype == AssetPayment.StockVesting:
            timestamp, price = self._asset.quote(self._timestamp, self._account.currency())
            if timestamp != self._timestamp:
                logging.error(self.tr("No price data for stock dividend/vesting: ") + f"{self.dump()}")
            amount = self._amount * price
        elif self._subtype == AssetPayment.StakingReward or self._subtype == AssetPayment.GasFee:
            # A crypto quote is daily, so it never falls on the exact block timestamp the way an exchange quote
            # does for a stock dividend - the last known price is the best available and is not an error.
            timestamp, price = self._asset.quote(self._timestamp, self._account.currency())
            if not timestamp:
                logging.error(self.tr("No price data to value an asset-denominated payment: ") + f"{self.dump()}")
            amount = self._amount * price
        else:
            amount = self._amount
        if currency_id != self._account.currency():
            amount *= JalAsset(self._account.currency()).quote(self._timestamp, currency_id)[1]
        return amount

    # Returns tax of dividend:
    # if currency_id = 0 - return unadjusted value of tax assigned to dividend
    # if currency is given - then converts tax amount into given currency
    def tax(self, currency_id: int = 0) -> Decimal:
        if currency_id and currency_id != self._account.currency():
            return self._tax * JalAsset(self._account.currency()).quote(self._timestamp, currency_id)[1]
        else:
            return self._tax

    def note(self) -> str:
        return self._note

    def description(self, part_only=False) -> str:
        text = self._note if self._note else self.tr("Dividend payment for:") + f" {self._symbol.symbol()} ({self._asset.name()})"
        tax_text = self.tr("Tax: ") + self._asset.country_name()
        if part_only and self._opart is not None:
            if self._opart == self.PART_VALUE:
                return text
            elif self._opart == self.PART_TAX:
                return f"{tax_text} [{text}]"
            else:
                return ''
        text = f"{text}\n{tax_text}" if self._tax else f"{text}\n"
        return text

    def value_change(self, part_only=False) -> list:
        if part_only and self._opart is not None:
            if self._opart == self.PART_VALUE:
                return [self._amount]
            elif self._opart == self.PART_TAX:
                return [-self._tax]
            else:
                return [Decimal('NaN')]
        amount = -self._amount if self._subtype == AssetPayment.GasFee else self._amount
        if self._tax:
            return [amount, -self._tax]
        else:
            return [amount, None]

    def value_currency(self) -> str:
        # The amount of these payments is a quantity of the asset, not a sum of money: shares received as a
        # dividend, coins earned by staking, coins burned as gas
        asset_denominated = (AssetPayment.StockDividend, AssetPayment.StockVesting,
                             AssetPayment.StakingReward, AssetPayment.GasFee)
        if self._subtype in asset_denominated and not self._opart:
            if self._tax:
                return f" {self._symbol.symbol()}\n {self._account_currency}"
            else:
                return f" {self._symbol.symbol()}"
        else:
            return f" {self._account_currency}"

    def value_total(self) -> list:
        balance = []
        amount = self._money_total(self._account.id())
        if self._subtype in (AssetPayment.StockDividend, AssetPayment.StockVesting,
                             AssetPayment.StakingReward, AssetPayment.GasFee):
            qty = self._asset_total(self._account.id(), self._asset.id())
            if qty is None:
                return [Decimal('NaN')]
            balance.append(qty)
        if not amount.is_nan():
            balance.append(amount)
        if len(balance) < 2:
            balance.append(None)
        return balance

    def update_amount(self, amount: Decimal) -> None:
        self._exec("UPDATE asset_payments SET amount=:amount WHERE oid=:oid",
                   [(":oid", self._oid), (":amount", format_decimal(amount))])

    def update_tax(self, new_tax) -> None:   # FIXME method should take Decimal value, not float
        _ = self._exec("UPDATE asset_payments SET tax=:tax WHERE oid=:oid",
                       [(":oid", self._oid), (":tax", new_tax)], commit=True)

    def processLedger(self, ledger):
        if not self._peer_id:
            raise LedgerError(self.tr("Can't process dividend as bank isn't set for investment account: ") + self._account_name)
        if self._subtype == AssetPayment.StockDividend or self._subtype == AssetPayment.StockVesting \
                or self._subtype == AssetPayment.StakingReward:
            self.processStockDividendOrVesting(ledger)
            return
        if self._subtype == AssetPayment.GasFee:
            self.processGasFee(ledger)
            return
        if self._subtype == AssetPayment.BondAmortization:
            self.processBondAmortization(ledger)
            return
        if self._subtype == AssetPayment.Dividend:
            category = PredefinedCategory.Dividends
        elif self._subtype == AssetPayment.BondInterest:
            category = PredefinedCategory.Interest
        elif self._subtype == AssetPayment.Fee:
            category = PredefinedCategory.Fees
        else:
            raise LedgerError(self.tr("Unsupported dividend type.") + f" Operation: {self.dump()}")
        operation_value = (self._amount - self._tax)
        if operation_value > Decimal('0'):
            credit_returned = ledger.returnCredit(self, self._account.id(), operation_value)
            if credit_returned < operation_value:
                ledger.appendTransaction(self, BookAccount.Money, operation_value - credit_returned)
        else:   # This branch is valid for accrued bond interest payments for bond buying trades
            credit_taken = ledger.takeCredit(self, self._account.id(), -operation_value)
            if credit_taken < -operation_value:
                ledger.appendTransaction(self, BookAccount.Money, operation_value + credit_taken)
        if self._amount > Decimal('0'):
            ledger.appendTransaction(self, BookAccount.Incomes, -self._amount, part=self.PART_VALUE, category=category, peer=self._peer_id, tag=self._asset.tag().id())
        else:   # This branch is valid for accrued bond interest payments for bond buying trades
            ledger.appendTransaction(self, BookAccount.Costs, -self._amount, part=self.PART_VALUE, category=category, peer=self._peer_id, tag=self._asset.tag().id())
        if self._tax:
            ledger.appendTransaction(self, BookAccount.Costs, self._tax, part=self.PART_TAX, category=PredefinedCategory.Taxes, peer=self._peer_id, tag=self._asset.tag().id())

    def processStockDividendOrVesting(self, ledger):
        asset_amount = ledger.getAmount(BookAccount.Assets, self._account.id(), self._asset.id())
        if asset_amount < Decimal('0'):
            raise NotImplemented(self.tr("Not supported action: stock dividend or vesting closes short trade.") +
                                 f" Operation: {self.dump()}")
        self._account.open_trade(JalOpenTrade(self, self.price(), self._amount), self._asset)
        ledger.appendTransaction(self, BookAccount.Assets, self._amount,
                                 asset_id=self._asset.id(), value=self._amount * self.price())
        if self._tax:
            ledger.appendTransaction(self, BookAccount.Money, -self._tax)
            ledger.appendTransaction(self, BookAccount.Costs, self._tax,
                                     part=self.PART_TAX, category=PredefinedCategory.Taxes, peer=self._peer_id, tag=self._asset.tag().id())

    # Gas burned by a transaction that moved nothing - a token approval, a contract call, or a transaction that
    # ran out of energy and failed while still costing its fee. The coins leave the wallet exactly as they do for a
    # transfer fee, so the treatment is the same one chosen there: consumed from the open lots in FIFO order and
    # expensed to Costs at their own cost basis, realizing no profit or loss and recording no deal.
    # See Transfer.processAssetFee() for the tax caveat that applies here word for word.
    def processGasFee(self, ledger):
        asset_amount = ledger.getAmount(BookAccount.Assets, self._account.id(), self._asset.id())
        if asset_amount < self._amount:
            raise LedgerError(self.tr("Asset amount is not enough to pay the gas fee. Date: ")
                              + f"{ts2dt(self._timestamp)}, Asset amount: {asset_amount}, "
                              + f"Required: {self._amount}, Operation: {self.dump()}")
        processed_qty, processed_value = self._close_deals_fifo(Decimal('-1.0'), self._amount, record_deals=False)
        if processed_qty < self._amount:
            raise LedgerError(self.tr("Processed asset amount is less than the gas fee. Date: ")
                              + f"{ts2dt(self._timestamp)}, Processed amount: {processed_qty}, "
                              + f"Required: {self._amount}, Operation: {self.dump()}")
        ledger.appendTransaction(self, BookAccount.Assets, -processed_qty,
                                 asset_id=self._asset.id(), value=-processed_value)
        ledger.appendTransaction(self, BookAccount.Costs, processed_value, part=self.PART_VALUE,
                                 category=PredefinedCategory.Fees, peer=self._peer_id, tag=self._asset.tag().id())

    def processBondAmortization(self, ledger):
        operation_value = (self._amount - self._tax)
        assert operation_value > Decimal('0'), "Bond amortization is expected to increase account balance"
        credit_returned = ledger.returnCredit(self, self._account.id(), operation_value)
        if credit_returned < operation_value:
            ledger.appendTransaction(self, BookAccount.Money, operation_value - credit_returned)
        if self._tax:
            ledger.appendTransaction(self, BookAccount.Costs, self._tax,
                                     part=self.PART_TAX, category=PredefinedCategory.Taxes, peer=self._peer_id, tag=self._asset.tag().id())
        ledger.appendTransaction(self, BookAccount.Assets, Decimal('0'), asset_id=self._asset.id(), value=-self._amount)


# ----------------------------------------------------------------------------------------------------------------------
class Trade(LedgerTransaction):
    _db_table = "trades"
    _db_fields = {
        "timestamp": {"mandatory": True, "validation": True},
        "settlement": {"mandatory": False, "validation": False},
        "number": {"mandatory": False, "validation": True, "default": ''},
        "account_id": {"mandatory": True, "validation": True},
        "symbol_id": {"mandatory": True, "validation": True},
        "qty": {"mandatory": True, "validation": True},
        "price": {"mandatory": True, "validation": True},
        "fee": {"mandatory": True, "validation": False},
        "note": {"mandatory": False, "validation": False}
    }
    PART_PROFIT = 1
    PART_FEE = 2

    # operation_data is either an integer to select operation from database or a dict with operation data that is used
    # to create a new operation in database and then select it
    def __init__(self, operation_data=None, opart=None):
        super().__init__(operation_data)
        self._otype = LedgerTransaction.Trade
        self._opart = opart
        self._view_rows = 2
        self._data = self._read("SELECT t.timestamp, t.settlement, t.number, t.account_id, "
                                "t.symbol_id, t.qty, t.price, t.fee, t.note FROM trades AS t "
                                "WHERE t.oid=:oid",
                                [(":oid", self._oid)], named=True)
        self._timestamp = int(self._data['timestamp'])
        self._settlement = int(self._data['settlement'])
        self._account = jal.db.account.JalAccount(self._data['account_id'])
        self._account_name = self._account.name()
        self._account_currency = JalAsset(self._account.currency()).symbol()
        self._reconciled = self._account.reconciled_at() >= self._timestamp
        self._symbol = JalSymbol(self._data['symbol_id'])
        self._asset = self._symbol.asset()
        self._number = self._data['number']
        self._qty = Decimal(self._data['qty'])
        self._price = Decimal(self._data['price'])
        self._fee = Decimal(self._data['fee'])
        self._note = self._data['note']
        self._peer_id = self._broker = self._account.organization()
        if self._qty < Decimal('0'):
            self._icon = JalIcon[JalIcon.SELL]
            self._oname = self.tr("Sell")
        else:
            self._icon = JalIcon[JalIcon.BUY]
            self._oname = self.tr("Buy")
        if self._opart is not None and self._opart == self.PART_PROFIT:
            profit = self._read("SELECT amount FROM ledger WHERE otype=:otype AND oid=:oid AND opart=:opart AND book_account=:book",
                                [(":otype", self._otype), (":oid", self._oid), (":opart", self._opart), (":book", BookAccount.Incomes)])
            try:
                self._profit = -Decimal(profit)
            except:
                self._profit = Decimal('NaN')
        else:
            self._profit = Decimal('NaN')

    def settlement(self) -> int:
        return self._settlement

    def price(self) -> Decimal:
        return self._price

    def update_price(self, price: Decimal) -> None:
        self._exec("UPDATE trades SET price=:price WHERE oid=:oid", [(":oid", self._oid), (":price", format_decimal(price))])

    def qty(self) -> Decimal:
        return self._qty

    def update_qty(self, qty: Decimal) -> None:
        self._exec("UPDATE trades SET qty=:qty WHERE oid=:oid", [(":oid", self._oid), (":qty", format_decimal(qty))])

    def fee(self) -> Decimal:
        return self._fee

    def amount(self) -> Decimal:
        return self._price * self._qty

    def description(self, part_only=False) -> str:
        deal_text = f"{self._qty:+.2f} {self._symbol.symbol()} @ {self._price:.4f}"
        fee_text = f"({self._fee:.2f})"
        text = deal_text + " " + fee_text if self._fee != Decimal('0') else deal_text
        if part_only and self._opart is not None:
            return text
        return text + "\n" + self._note

    def value_change(self, part_only=False) -> list:
        if part_only and self._opart is not None:
            if self._opart == self.PART_FEE:
                return [-self._fee]
            elif self._opart == self.PART_PROFIT:
                return [self._profit]
            else:
                return [Decimal('NaN')]
        return [-(self._price * self._qty), self._qty]

    def value_currency(self) -> str:
        if self._opart:
            return f" {self._account_currency}"
        else:
            return f" {self._account_currency}\n {self._symbol.symbol()}"

    def value_total(self) -> list:
        amount = self._money_total(self._account.id())
        qty = self._asset_total(self._account.id(), self._asset.id())
        if amount is None or qty is None:
            return [Decimal('NaN'), Decimal('NaN')]
        else:
            return [amount, qty]

    # Searches for dividend with type BondInterest that matches trade by timestamp, account, asset and number
    # This dividend represents accrued interest for this operation.
    # Returns value of accrued interest or 0 if such isn't found
    def accrued_interest(self,currency_id: int = 0) -> Decimal:
        oid = self._read("SELECT p.oid FROM asset_payments AS p LEFT JOIN asset_symbol AS s ON p.symbol_id=s.id "
                         "WHERE p.timestamp=:timestamp AND p.account_id=:account "
                         "AND s.asset_id=:asset AND p.number=:number AND p.type=:interest",
                         [(":timestamp", self._timestamp), (":account", self._account.id()), (":number", self._number),
                          (":asset", self._asset.id()), (":interest", AssetPayment.BondInterest)])
        value = AssetPayment(oid).amount() if oid else Decimal('0')
        if currency_id and currency_id != self._account.currency():
            return value * JalAsset(self._account.currency()).quote(self.timestamp(), currency_id)[1]
        else:
            return value

    def processLedger(self, ledger):
        if not self._broker:
            raise LedgerError(self.tr("Can't process trade as bank isn't set for investment account: ") + self._account_name)
        deal_sign = Decimal('1.0').copy_sign(self._qty)  # 1 is buy and -1 is sell operation
        qty = abs(self._qty)
        trade_value = self._price * qty + deal_sign * self._fee
        processed_qty = Decimal('0')
        processed_value = Decimal('0')
        # Get asset amount accumulated before current operation
        asset_amount = ledger.getAmount(BookAccount.Assets, self._account.id(), self._asset.id())
        if ((-deal_sign) * asset_amount) > Decimal('0'):  # Match trade if we have asset that is opposite to operation
            processed_qty, processed_value = self._close_deals_fifo(deal_sign, qty)
        if deal_sign > 0:
            credit_value = ledger.takeCredit(self, self._account.id(), trade_value)
        else:
            credit_value = ledger.returnCredit(self, self._account.id(), trade_value)
        if credit_value < trade_value:
            ledger.appendTransaction(self, BookAccount.Money, (-deal_sign) * (trade_value - credit_value))
        if processed_qty > 0:  # Add result of closed deals
            # decrease (sell operation) or increase (buy operation) amount of assets in ledger
            rounding_error = ledger.appendTransaction(self, BookAccount.Assets, deal_sign * processed_qty,
                                                      asset_id=self._asset.id(), value=deal_sign * processed_value)
            ledger.appendTransaction(self, BookAccount.Incomes,
                                     deal_sign * ((self._price * processed_qty) - processed_value + rounding_error),
                                     part=self.PART_PROFIT, category=PredefinedCategory.Profit, peer=self._broker, tag=self._asset.tag().id())
        if processed_qty < qty:  # We have a reminder that opens a new position
            self._account.open_trade(JalOpenTrade(self, self._price, (qty - processed_qty)), self._asset)
            ledger.appendTransaction(self, BookAccount.Assets, deal_sign * (qty - processed_qty),
                                     asset_id=self._asset.id(), value=deal_sign * (qty - processed_qty) * self._price)
        if self._fee:
            ledger.appendTransaction(self, BookAccount.Costs, self._fee,
                                     part=self.PART_FEE, category=PredefinedCategory.Fees, peer=self._broker, tag=self._asset.tag().id())


# ----------------------------------------------------------------------------------------------------------------------
# On-chain exchange of one asset for another (a DeFi swap). Unlike a SymbolChange/Merger - which preserve cost basis -
# a swap is a genuine disposal: the out asset is FIFO-closed at its market value, the profit/loss is realized, and the
# in asset is opened as a brand new lot at that same market value. The swap-closed deals go to the Deals report but are
# kept out of tax reports until crypto tax treatment is designed (see JalAccount.closed_trades_list(close_otypes=...)).
#
# A CROSS-CHAIN swap (an asset-changing exchange through a bridge/aggregator: A on chain X becomes B on chain Y) is the
# same disposal spread over two accounts and two moments in time, so it processes as two parts:
#   * Swap.Outgoing - disposes the out asset on the source account at its market value, realizes the profit/loss and
#     parks the proceeds in the Transfers book (they are in transit while the exchange is in flight); gas rides here.
#   * Swap.Incoming - drains those proceeds on the destination account (converted with the FX rate of the arrival date
#     if the two accounts differ in currency, as for a bridge) and opens the acquired asset as a new lot at that value.
# So nothing is gained or lost between sending and receiving: the whole result of the exchange is realized at the
# moment of disposal, exactly as in the same-chain case. A same-chain swap keeps a single part (Swap.Whole) and is
# processed by the simpler code path below - no value travels through the Transfers book.
class Swap(LedgerTransaction):
    Whole = 0       # A same-chain swap: disposal and acquisition happen at once, on one account
    Outgoing = -1   # Cross-chain: the disposal leg (source account, source chain)
    Incoming = 1    # Cross-chain: the acquisition leg (destination account, destination chain)
    _db_table = "swaps"
    _db_fields = {
        "timestamp": {"mandatory": True, "validation": True},
        "tx_hash": {"mandatory": False, "validation": True, "default": ''},
        "account_id": {"mandatory": True, "validation": True},
        "out_symbol_id": {"mandatory": True, "validation": True},
        "out_qty": {"mandatory": True, "validation": True},
        "in_timestamp": {"mandatory": False, "validation": True, "default": None},
        "in_account_id": {"mandatory": False, "validation": True, "default": None},
        "in_symbol_id": {"mandatory": True, "validation": True},
        "in_qty": {"mandatory": True, "validation": True},
        "in_tx_hash": {"mandatory": False, "validation": True, "default": ''},
        "fee_symbol_id": {"mandatory": False, "validation": True, "default": None},
        "fee_qty": {"mandatory": False, "validation": True, "default": None},
        "note": {"mandatory": False, "validation": False}
    }
    PART_PROFIT = 1
    PART_FEE = 2

    def __init__(self, operation_data=None, opart=None):
        super().__init__(operation_data)
        self._otype = LedgerTransaction.Swap
        self._data = self._read("SELECT s.timestamp, s.tx_hash, s.account_id, s.out_symbol_id, s.out_qty, "
                                "s.in_timestamp, s.in_account_id, s.in_symbol_id, s.in_qty, s.in_tx_hash, "
                                "s.fee_symbol_id, s.fee_qty, s.note FROM swaps AS s "
                                "WHERE s.oid=:oid", [(":oid", self._oid)], named=True)
        if self._data is None:
            raise IndexError(LedgerTransaction.NoOpException)
        present = lambda v: v is not None and v != ''   # _read() returns '' (not None) for a SQL NULL
        self._account = jal.db.account.JalAccount(self._data['account_id'])
        self._out_symbol = JalSymbol(self._data['out_symbol_id'])
        self._out_asset = self._out_symbol.asset()
        self._out_qty = Decimal(self._data['out_qty'])
        self._in_symbol = JalSymbol(self._data['in_symbol_id'])
        self._in_asset = self._in_symbol.asset()
        self._in_qty = Decimal(self._data['in_qty'])
        # The acquiring leg defaults to the disposing one - that is what makes an ordinary same-chain swap
        self._in_account = jal.db.account.JalAccount(self._data['in_account_id']) \
            if present(self._data['in_account_id']) else self._account
        self._in_timestamp = int(self._data['in_timestamp']) if present(self._data['in_timestamp']) \
            else int(self._data['timestamp'])
        self._cross_chain = self._in_account.id() != self._account.id()
        if not self._cross_chain:
            self._opart = Swap.Whole
        else:   # A leg must be named for a cross-chain swap; default to the one that starts it
            self._opart = Swap.Outgoing if opart is None or opart == Swap.Whole else opart
        assert self._opart in [Swap.Whole, Swap.Outgoing, Swap.Incoming], "Unknown swap part"
        self._fee_symbol = JalSymbol(self._data['fee_symbol_id'])
        self._fee_asset = self._fee_symbol.asset()
        self._fee_qty = Decimal(self._data['fee_qty']) if self._data['fee_qty'] else Decimal('0')
        self._symbol = self._in_symbol if self._opart == Swap.Incoming else self._out_symbol
        # Operation's main asset is the one its part deals in (FIFO closing of the disposal works with the out asset)
        self._asset = self._symbol.asset()
        icons = {Swap.Whole: JalIcon.SWAP, Swap.Outgoing: JalIcon.TRANSFER_ASSET_OUT, Swap.Incoming: JalIcon.TRANSFER_ASSET_IN}
        names = {Swap.Whole: self.tr("Swap"), Swap.Outgoing: self.tr("Outgoing swap"), Swap.Incoming: self.tr("Incoming swap")}
        self._icon = JalIcon[icons[self._opart]]
        self._oname = names[self._opart]
        # Each leg of a cross-chain swap is a transaction of its own chain, so the part decides time, account and hash
        self._timestamp = self._in_timestamp if self._opart == Swap.Incoming else int(self._data['timestamp'])
        self._number = self._data['in_tx_hash'] if self._opart == Swap.Incoming else self._data['tx_hash']
        self._account_name = self.account_name()
        self._account_currency = JalAsset(self._leg_account().currency()).symbol()
        self._reconciled = self._leg_account().reconciled_at() >= self._timestamp
        self._note = self._data['note']
        self._peer_id = self._leg_account().organization()
        if self._opart == Swap.Whole:
            self._view_rows = 3 if self._fee_asset.id() else 2
        elif self._opart == Swap.Outgoing:
            self._view_rows = 2 if self._fee_asset.id() else 1
        else:
            self._view_rows = 1
        self._value = None   # Cached disposal value of the swap in the source account currency

    # The account the current part is booked on (the destination account only for the acquiring leg)
    def _leg_account(self):
        return self._in_account if self._opart == Swap.Incoming else self._account

    # A same-chain swap happens immediately; a cross-chain one is finished when the acquired asset arrives
    def settlement(self) -> int:
        return self._in_timestamp

    def qty(self) -> Decimal:
        return self._in_qty if self._opart == Swap.Incoming else self._out_qty

    def account_name(self):
        if not self._cross_chain:
            return self._account.name()
        if self._opart == Swap.Incoming:
            return f"{self._in_account.name()} <- {self._account.name()}"
        return f"{self._account.name()} -> {self._in_account.name()}"

    def account_id(self):
        return self._leg_account().id()

    # Market value of the swap in the SOURCE account currency: value of the disposed asset with a fallback to the
    # value of the acquired asset if the disposed one has no quotes at all (quoted when it arrives, which is the
    # same moment for a same-chain swap).
    def value(self) -> Decimal:
        if self._value is None:
            _, price = self._out_asset.quote(int(self._data['timestamp']), self._account.currency())
            if price != Decimal('0'):
                self._value = price * self._out_qty
            else:
                _, price = self._in_asset.quote(self._in_timestamp, self._account.currency())
                if price == Decimal('0'):
                    raise LedgerError(self.tr("There are no quotes to value the swap. Date: ")
                                      + f"{ts2dt(self._timestamp)}, Operation: {self.dump()}")
                self._value = price * self._in_qty
        return self._value

    # Unit price of the disposed asset - it is the closing price of the FIFO deals created by the swap
    def price(self) -> Decimal:
        return self.value() / self._out_qty

    def note(self) -> str:
        return self._note

    def description(self, part_only=False) -> str:
        text = f"{self._out_qty} {self._out_symbol.symbol()} -> {self._in_qty} {self._in_symbol.symbol()}"
        if self._fee_asset.id() and self._opart != Swap.Incoming:   # Gas is paid on the source chain only
            text += " " + self.tr("Fee:") + f" {self._fee_qty} {self._fee_symbol.symbol()}"
        if self._note:
            text += "\n" + self._note
        return text

    def value_change(self, part_only=False) -> list:
        if self._opart == Swap.Incoming:
            return [self._in_qty]
        result = [-self._out_qty] if self._cross_chain else [-self._out_qty, self._in_qty]
        if self._fee_asset.id():
            result.append(-self._fee_qty)
        return result

    def value_currency(self) -> str:
        if self._opart == Swap.Incoming:
            return f" {self._in_symbol.symbol()}"
        text = f" {self._out_symbol.symbol()}" if self._cross_chain \
            else f" {self._out_symbol.symbol()}\n {self._in_symbol.symbol()}"
        if self._fee_asset.id():
            text += f"\n {self._fee_symbol.symbol()}"
        return text

    def value_total(self) -> list:
        if self._opart == Swap.Incoming:
            return [self._asset_total(self._in_account.id(), self._in_asset.id())]
        balance = [self._asset_total(self._account.id(), self._out_asset.id())]
        if not self._cross_chain:
            balance.append(self._asset_total(self._account.id(), self._in_asset.id()))
        if self._fee_asset.id():
            balance.append(self._asset_total(self._account.id(), self._fee_asset.id()))
        return balance

    def processLedger(self, ledger):
        # Only the disposing leg books a profit/loss and fees, so only it needs a peer to book them against
        if self._opart != Swap.Incoming and not self._peer_id:
            raise LedgerError(self.tr("Can't process swap as organization isn't set for account: ") + self.account_name())
        if self._out_asset.id() == 0 or self._in_asset.id() == 0:
            raise LedgerError(self.tr("Swap assets aren't set. Operation: ") + self.dump())
        if self._out_asset.id() == self._in_asset.id():
            raise LedgerError(self.tr("Can't process swap of an asset into itself. Operation: ") + self.dump())
        if self._out_qty <= Decimal('0') or self._in_qty <= Decimal('0'):
            raise LedgerError(self.tr("Swap quantities must be positive. Operation: ") + self.dump())
        if self._in_timestamp < int(self._data['timestamp']):
            raise LedgerError(self.tr("Swap can't receive an asset before it was exchanged. Operation: ") + self.dump())
        if self._opart == Swap.Incoming:
            self.processIncoming(ledger)
            return
        self.processOutgoing(ledger)

    # Disposes the out asset at its market value and realizes the profit/loss of the disposal. A same-chain swap opens
    # the acquired asset right here; a cross-chain one parks the proceeds in the Transfers book for its receiving leg.
    def processOutgoing(self, ledger):
        available = ledger.getAmount(BookAccount.Assets, self._account.id(), self._out_asset.id())
        if available < self._out_qty:
            raise LedgerError(self.tr("Asset amount is not enough for swap processing. Date: ")
                              + f"{ts2dt(self._timestamp)}, Asset amount: {available}, "
                              + f"Required: {self._out_qty}, Operation: {self.dump()}")
        value = self.value()
        processed_qty, basis = self._close_deals_fifo(Decimal('-1.0'), self._out_qty, asset=self._out_asset)
        if processed_qty < self._out_qty:
            raise LedgerError(self.tr("Processed asset amount is less than swap amount. Date: ")
                              + f"{ts2dt(self._timestamp)}, Processed amount: {processed_qty}, "
                              + f"Required: {self._out_qty}, Operation: {self.dump()}")
        # Withdraw the disposed asset at its cost basis and realize the profit/loss of the disposal
        rounding_error = ledger.appendTransaction(self, BookAccount.Assets, -self._out_qty,
                                                  asset_id=self._out_asset.id(), value=-basis)
        ledger.appendTransaction(self, BookAccount.Incomes, -(value - basis + rounding_error), part=self.PART_PROFIT,
                                 category=PredefinedCategory.Profit, peer=self._peer_id, tag=self._out_asset.tag().id())
        if self._cross_chain:
            # The proceeds travel to the destination chain as money in transit, drained by the receiving leg
            ledger.appendTransaction(self, BookAccount.Transfers, value)
        else:
            # Deposit the acquired asset as a new open position at the swap-implied cost
            self._account.open_trade(JalOpenTrade(self, value / self._in_qty, self._in_qty), self._in_asset)
            ledger.appendTransaction(self, BookAccount.Assets, self._in_qty, asset_id=self._in_asset.id(), value=value)
        if self._fee_asset.id():
            self._process_swap_fee(ledger)

    # Opens the acquired asset on the destination account, valued at the proceeds the disposing leg parked in transit
    # (converted into the destination account currency if the two accounts are kept in different currencies).
    def processIncoming(self, ledger):
        value = self._read("SELECT amount FROM ledger WHERE book_account=:book_transfers AND otype=:otype AND oid=:id",
                           [(":book_transfers", BookAccount.Transfers), (":otype", self._otype), (":id", self._oid)],
                           check_unique=True)
        if not value:
            raise LedgerError(self.tr("Asset disposal not found for swap.") + f" Operation:  {self.dump()}")
        value = Decimal(value)
        if self._account.currency() == self._in_account.currency():
            rate = Decimal('1')
        else:   # Proceeds are converted into the destination account currency with the FX rate at the arrival time
            rate = JalAsset(self._account.currency()).quote(self._in_timestamp, self._in_account.currency())[1]
            if rate == Decimal('0'):
                raise LedgerError(self.tr("There is no FX rate to convert swap proceeds. Date: ")
                                  + f"{ts2dt(self._in_timestamp)}, Operation: {self.dump()}")
        in_value = rate * value
        ledger.appendTransaction(self, BookAccount.Transfers, -in_value)
        self._in_account.open_trade(JalOpenTrade(self, in_value / self._in_qty, self._in_qty), self._in_asset)
        ledger.appendTransaction(self, BookAccount.Assets, self._in_qty, asset_id=self._in_asset.id(), value=in_value)

    # The gas paid for the swap is disposed at its cost basis to Costs/Fees - the same treatment the standalone
    # GasFee operation gives it, so no profit/loss is realized on the tiny amount of native coin spent on gas.
    # It is always burned on the source chain, so it rides the disposing leg of a cross-chain swap.
    def _process_swap_fee(self, ledger):
        available = ledger.getAmount(BookAccount.Assets, self._account.id(), self._fee_asset.id())
        if available < self._fee_qty:
            raise LedgerError(self.tr("Asset amount is not enough to pay the swap fee. Date: ")
                              + f"{ts2dt(self._timestamp)}, Asset amount: {available}, "
                              + f"Required: {self._fee_qty}, Operation: {self.dump()}")
        processed_qty, processed_value = self._close_deals_fifo(Decimal('-1.0'), self._fee_qty, asset=self._fee_asset,
                                                               account=self._account, record_deals=False)
        if processed_qty < self._fee_qty:
            raise LedgerError(self.tr("Processed asset amount is less than the swap fee. Date: ")
                              + f"{ts2dt(self._timestamp)}, Processed amount: {processed_qty}, "
                              + f"Required: {self._fee_qty}, Operation: {self.dump()}")
        ledger.appendTransaction(self, BookAccount.Assets, -processed_qty,
                                 asset_id=self._fee_asset.id(), value=-processed_value)
        ledger.appendTransaction(self, BookAccount.Costs, processed_value, part=self.PART_FEE,
                                 category=PredefinedCategory.Fees, peer=self._peer_id, tag=self._fee_asset.tag().id())


# ----------------------------------------------------------------------------------------------------------------------
class Transfer(LedgerTransaction):
    Fee = 0
    Outgoing = -1
    Incoming = 1
    _db_table = "transfers"
    _db_fields = {
        "withdrawal_timestamp": {"mandatory": True, "validation": True},
        "withdrawal_account": {"mandatory": True, "validation": True},
        "withdrawal": {"mandatory": True, "validation": True,},
        "deposit_timestamp": {"mandatory": True, "validation": True},
        "deposit_account": {"mandatory": True, "validation": True},
        "deposit": {"mandatory": True, "validation": True},
        "fee_account": {"mandatory": False, "validation": True, "default": None},
        "fee": {"mandatory": False, "validation": True, "default": None},
        "fee_symbol_id": {"mandatory": False, "validation": True, "default": None},
        "number": {"mandatory": False, "validation": True, "default": ''},
        "symbol_id": {"mandatory": False, "validation": True, "default": None},
        "note": {"mandatory": False, "validation": False}
    }

    def __init__(self, oid=None, opart=0):
        assert opart in [Transfer.Outgoing, Transfer.Incoming, Transfer.Fee], "Unknown transfer type"
        icons = {
            (Transfer.Outgoing, True): JalIcon.TRANSFER_OUT,
            (Transfer.Incoming, True): JalIcon.TRANSFER_IN,
            (Transfer.Fee, True): JalIcon.FEE,
            (Transfer.Outgoing, False): JalIcon.TRANSFER_ASSET_OUT,
            (Transfer.Incoming, False): JalIcon.TRANSFER_ASSET_IN,
            (Transfer.Fee, False): JalIcon.FEE,
        }
        self.names = {
            (Transfer.Outgoing, True): self.tr("Outgoing transfer"),
            (Transfer.Incoming, True): self.tr("Incoming transfer"),
            (Transfer.Fee, True): self.tr("Transfer fee"),
            (Transfer.Outgoing, False): self.tr("Outgoing asset transfer"),
            (Transfer.Incoming, False): self.tr("Incoming asset transfer"),
            (Transfer.Fee, False): self.tr("Asset transfer fee"),
        }
        super().__init__(oid)
        self._otype = LedgerTransaction.Transfer
        self._opart = opart
        self._data = self._read("SELECT t.withdrawal_timestamp, t.withdrawal_account, t.withdrawal, "
                                "t.deposit_timestamp, t.deposit_account, t.deposit, t.fee_account, t.fee, "
                                "t.fee_symbol_id, t.symbol_id, t.number, t.note FROM transfers AS t "
                                "WHERE t.oid=:oid",
                                [(":oid", self._oid)], named=True)
        if self._data is None:
            raise IndexError(LedgerTransaction.NoOpException)
        self._withdrawal_account = jal.db.account.JalAccount(self._data['withdrawal_account'])
        self._withdrawal_account_name = self._withdrawal_account.name()
        self._withdrawal_timestamp = int(self._data['withdrawal_timestamp'])
        self._withdrawal = Decimal(self._data['withdrawal'])
        self._withdrawal_currency = JalAsset(self._withdrawal_account.currency()).symbol()
        self._deposit_account = jal.db.account.JalAccount(self._data['deposit_account'])
        self._deposit_account_name = self._deposit_account.name()
        self._deposit = Decimal(self._data['deposit'])
        self._deposit_currency = JalAsset(self._deposit_account.currency()).symbol()
        self._deposit_timestamp = int(self._data['deposit_timestamp'])
        self._fee_account = jal.db.account.JalAccount(self._data['fee_account'])
        self._fee_currency = JalAsset(self._fee_account.currency()).symbol()
        self._fee_account_name = self._fee_account.name()
        self._fee = Decimal(self._data['fee']) if self._data['fee'] else Decimal('0')
        self._symbol = JalSymbol(self._data['symbol_id'])
        self._asset = self._symbol.asset()
        self._fee_symbol = JalSymbol(self._data['fee_symbol_id'])
        self._fee_asset = self._fee_symbol.asset()
        self._number = self._data['number']
        self._account = self._withdrawal_account
        self._note = self._data['note']
        # Icon and name describe the transfer itself, so they are resolved from the transferred asset before the
        # fee part re-points self._asset/_account below
        self._icon = JalIcon[icons[(opart, self._asset.id() == 0)]]
        self._oname = self.names[(opart, self._asset.id() == 0)]
        if self._opart == Transfer.Fee and self._fee_asset.id():
            # A fee paid in an asset is withdrawn from the fee account, not from the account the transfer starts at.
            # FIFO processing and the closed-deal bookkeeping both read account()/asset(), so they must describe the
            # fee here or the gas would be taken out of the transferred asset's position instead.
            self._account = self._fee_account
            self._asset = self._fee_asset
        if self._opart == Transfer.Outgoing:
            self._reconciled = self._withdrawal_account.reconciled_at() >= self._withdrawal_timestamp
        if self._opart == Transfer.Incoming:
            self._reconciled = self._deposit_account.reconciled_at() >= self._deposit_timestamp
        if self._opart == Transfer.Fee:
            self._reconciled = self._fee_account.reconciled_at() >= self._withdrawal_timestamp

    def timestamp(self):
        if self._opart == Transfer.Incoming:
            return self._deposit_timestamp
        else:
            return self._withdrawal_timestamp

    # This is required for compatibility with other asset actions, but it will also allow to get finish time of transfer
    def settlement(self):
        return self._deposit_timestamp

    def account_name(self):
        if self._opart == Transfer.Fee:
            return self._fee_account_name
        elif self._opart == Transfer.Outgoing:
            return self._withdrawal_account_name + " -> " + self._deposit_account_name
        elif self._opart == Transfer.Incoming:
            return self._deposit_account_name + " <- " + self._withdrawal_account_name
        else:
            assert False, "Unknown transfer type"

    def account_id(self):
        if self._opart == Transfer.Fee:
            return self._fee_account.id()
        elif self._opart == Transfer.Outgoing:
            return self._withdrawal_account.id()
        elif self._opart == Transfer.Incoming:
            return self._deposit_account.id()
        else:
            assert False, "Unknown transfer type"

    def description(self, part_only=False) -> str:
        if self._opart == Transfer.Fee:
            note = f" ({self._note})" if self._note else ''
            return self.tr("Transfer fee") + note
        if self._asset.id():
            if self._opart == Transfer.Incoming and self._withdrawal_currency != self._deposit_currency:
                return self._note + " [" + self.tr("Cost basis:") + f" @{self._deposit:.2f} {self._deposit_currency}]"
        else:
            try:
                rate = self._withdrawal / self._deposit
            except ZeroDivisionError:
                rate = Decimal('0')
            if self._withdrawal_currency != self._deposit_currency:
                if rate != Decimal('0'):
                    if rate > Decimal('1.0'):
                        return self._note + f" [1 {self._deposit_currency} = {rate:.4f} {self._withdrawal_currency}]"
                    if rate < Decimal('1.0'):
                        rate = Decimal('1.0') / rate
                        return self._note + f" [{rate:.4f} {self._deposit_currency} = 1 {self._withdrawal_currency}]"
                else:
                    return self._note + " " + self.tr("Error. Zero rate")
        return self._note

    # Price is undefined for transfer but method is required in FIFO processing of asset transfer
    def price(self):
        return None

    def value_change(self, part_only=False) -> list:
        if self._opart == Transfer.Outgoing:
            return [-self._withdrawal]
        elif self._opart == Transfer.Incoming:
            if self._asset.id():
                return [self._withdrawal]  # amount of asset doesn't change and self._deposit contains a cost basis
            else:
                return [self._deposit]
        elif self._opart == Transfer.Fee:
            return [-self._fee]
        else:
            assert False, "Unknown transfer type"

    def value_currency(self) -> str:
        if self._opart == Transfer.Outgoing:
            if self._asset.id():
                return self._symbol.symbol()
            else:
                return self._withdrawal_currency
        elif self._opart == Transfer.Incoming:
            if self._asset.id():
                return self._symbol.symbol()
            else:
                return self._deposit_currency
        elif self._opart == Transfer.Fee:
            return self._fee_symbol.symbol() if self._fee_asset.id() else self._fee_currency
        else:
            assert False, "Unknown transfer type"

    def value_total(self) -> list:
        if self._opart == Transfer.Outgoing:
            if self._asset.id():
                amount = self._asset_total(self._withdrawal_account.id(), self._asset.id())
            else:
                amount = self._money_total(self._withdrawal_account.id())
        elif self._opart == Transfer.Incoming:
            if self._asset.id():
                amount = self._asset_total(self._deposit_account.id(), self._asset.id())
            else:
                amount = self._money_total(self._deposit_account.id())
        elif self._opart == Transfer.Fee:
            if self._fee_asset.id():
                amount = self._asset_total(self._fee_account.id(), self._fee_asset.id())
            else:
                amount = self._money_total(self._fee_account.id())
        else:
            assert False, "Unknown transfer type"
        return [amount]

    def processLedger(self, ledger):
        if self._opart == Transfer.Outgoing:
            if self._asset.id():
                self.processAssetTransfer(ledger)
            else:
                credit_taken = ledger.takeCredit(self, self._withdrawal_account.id(), self._withdrawal)
                ledger.appendTransaction(self, BookAccount.Money, -(self._withdrawal - credit_taken))
                ledger.appendTransaction(self, BookAccount.Transfers, self._withdrawal)
        elif self._opart == Transfer.Fee:
            if not self._fee_account.organization():
                raise LedgerError(self.tr("Can't collect fee from the account '{}' ({}) as organization isn't set for it. Date: {}").format(
                    self._fee_account.name(), self._fee_account.number(), ts2dt(self._withdrawal_timestamp)))
            if self._fee_asset.id():
                self.processAssetFee(ledger)
            else:
                credit_taken = ledger.takeCredit(self, self._fee_account.id(), self._fee)
                ledger.appendTransaction(self, BookAccount.Money, -(self._fee - credit_taken))
                ledger.appendTransaction(self, BookAccount.Costs, self._fee,
                                         category=PredefinedCategory.Fees, peer=self._fee_account.organization())
        elif self._opart == Transfer.Incoming:
            if self._asset.id():
                self.processAssetTransfer(ledger)
            else:
                credit_returned = ledger.returnCredit(self, self._deposit_account.id(), self._deposit)
                if credit_returned < self._deposit:
                    ledger.appendTransaction(self, BookAccount.Money, self._deposit - credit_returned)
                ledger.appendTransaction(self, BookAccount.Transfers, -self._deposit)
        else:
            assert False, "Unknown transfer type"

    # Books a transfer fee that is paid in an asset instead of money - on-chain gas, which is always burned in the
    # native coin of the blockchain (TRX on Tron, ETH on Ethereum/Arbitrum). That coin may or may not be the asset
    # being transferred, so the fee is withdrawn from its own position in the fee account.
    #
    # The spent quantity is taken from the open positions in FIFO order and expensed to Costs at its own cost basis,
    # which makes the value leaving the position equal to the value arriving in Costs - so no profit or loss is
    # realized and no deal is recorded. The remaining position keeps its per-unit cost basis and simply holds fewer
    # units.
    #
    # KNOWN SIMPLIFICATION - several jurisdictions treat *any* disposal of a crypto asset, including spending it on
    # transaction fees, as a realization event that crystallizes capital gain or loss against the asset's cost basis.
    # Among those known at the time of writing: the United States (crypto is property, so every disposition is a
    # taxable event), the United Kingdom, Canada, Australia, Germany (private sale transactions, subject to its
    # one-year holding exemption) and Portugal (gains on holdings held under 365 days). Booking gas at cost basis as
    # done here therefore understates realized gains wherever that treatment applies. This is a deliberate choice to
    # keep gas out of the cost-basis result until crypto tax treatment is designed as its own task; it must be
    # revisited together with the country tax reports, and nothing here should be taken as tax advice.
    def processAssetFee(self, ledger):
        fee_amount = self._fee
        asset_amount = ledger.getAmount(BookAccount.Assets, self._fee_account.id(), self._fee_asset.id())
        if asset_amount < fee_amount:
            raise LedgerError(self.tr("Asset amount is not enough to pay the transfer fee. Date: ")
                              + f"{ts2dt(self._withdrawal_timestamp)}, Asset amount: {asset_amount}, "
                              + f"Required: {fee_amount}, Operation: {self.dump()}")
        # record_deals=False - the fee is an expense, not a deal, so it must not appear in 'trades_closed'. Beyond
        # keeping the Deals report clean this is what makes the fee safe when it is paid in the very asset that is
        # being transferred out of the same account: the incoming leg re-opens the lots the outgoing leg closed and
        # selects them by operation, account and asset, every one of which a fee deal would match too. Measured
        # consequence of recording one (transfer 50 TRX, burn 10 TRX of the same position): the destination ends up
        # with the fee's 10-unit lot in place of the transferred 50, so its ledger balance and its open lots
        # disagree - a corruption of cost basis that stays invisible until something is sold from that account.
        processed_qty, processed_value = self._close_deals_fifo(
            Decimal('-1.0'), fee_amount, asset=self._fee_asset, account=self._fee_account, record_deals=False)
        if processed_qty < fee_amount:
            raise LedgerError(self.tr("Processed asset amount is less than the transfer fee. Date: ")
                              + f"{ts2dt(self._withdrawal_timestamp)}, Processed amount: {processed_qty}, "
                              + f"Required: {fee_amount}, Operation: {self.dump()}")
        ledger.appendTransaction(self, BookAccount.Assets, -processed_qty,
                                 asset_id=self._fee_asset.id(), value=-processed_value)
        ledger.appendTransaction(self, BookAccount.Costs, processed_value,
                                 category=PredefinedCategory.Fees, peer=self._fee_account.organization())

    def processAssetTransfer(self, ledger):
        transfer_amount = self._withdrawal
        if self._opart == Transfer.Outgoing:   # Withdraw asset from source account
            asset_amount = ledger.getAmount(BookAccount.Assets, self._withdrawal_account.id(), self._asset.id())
            if asset_amount < transfer_amount:
                raise LedgerError(self.tr("Asset amount is not enough for asset transfer processing. Date: ")
                                  + f"{ts2dt(self._withdrawal_timestamp)}, Asset amount: {asset_amount}, "
                                  + f"Required: {transfer_amount}, Operation: {self.dump()}")
            processed_qty, processed_value = self._close_deals_fifo(Decimal('-1.0'), transfer_amount)
            if processed_qty < transfer_amount:
                raise LedgerError(self.tr("Processed asset amount is less than transfer amount. Date: ")
                                  + f"{ts2dt(self._withdrawal_timestamp)}, Processed amount: {processed_qty}, "
                                  + f"Required: {transfer_amount}, Operation: {self.dump()}")
            ledger.appendTransaction(self, BookAccount.Assets, -processed_qty, asset_id=self._asset.id(), value=-processed_value)
            ledger.appendTransaction(self, BookAccount.Transfers, transfer_amount, asset_id=self._asset.id(), value=processed_value)
        elif self._opart == Transfer.Incoming:
            transfer_trades = self._deals_closed_by_operation()
            # get initial value of withdrawn asset
            value = self._read("SELECT value FROM ledger "
                               "WHERE book_account=:book_transfers AND otype=:otype AND oid=:id",
                               [(":book_transfers", BookAccount.Transfers), (":otype", self._otype),
                                (":id", self._oid)], check_unique=True)
            if not value:
                raise LedgerError(self.tr("Asset withdrawal not found for transfer.") + f" Operation:  {self.dump()}")
            # A zero withdrawn value is treated like the same-currency case: there is no rate that rescales zero to
            # the destination value, and a zero-cost lot stays zero-cost whatever it is multiplied by. This happens
            # when the asset was received with its cost basis left to be filled in later (e.g. a fetched transfer),
            # and without this guard a single unfilled cost basis divides by zero and aborts the whole ledger rebuild.
            if self._withdrawal_account.currency() == self._deposit_account.currency() or Decimal(value) == 0:
                transfer_value = Decimal(value)
                # Move open trades from previous account to new account
                for trade in transfer_trades:
                    self._deposit_account.open_trade(trade, self._asset, modified_by=self)
            else:
                transfer_value = self._deposit
                rate = transfer_value/Decimal(value)
                # Move open trades from previous account to new and adjust price
                for trade in transfer_trades:
                    self._deposit_account.open_trade(trade, self._asset, modified_by=self, adjustment=(rate, Decimal('1')))
            ledger.appendTransaction(self, BookAccount.Transfers, -transfer_amount, asset_id=self._asset.id(), value=-transfer_value)
            ledger.appendTransaction(self, BookAccount.Assets, transfer_amount, asset_id=self._asset.id(), value=transfer_value)
        else:
            assert False, "Unknown transfer type for asset transfer"


# ----------------------------------------------------------------------------------------------------------------------
class CorporateAction(LedgerTransaction):
    Merger = 1
    SpinOff = 2
    SymbolChange = 3
    Split = 4
    Delisting = 5
    _db_table = "asset_actions"
    _db_fields = {
        "timestamp": {"mandatory": True, "validation": True},
        "number": {"mandatory": False, "validation": True, "default": ''},
        "account_id": {"mandatory": True, "validation": True},
        "type": {"mandatory": True, "validation": True},
        "symbol_id": {"mandatory": True, "validation": True},
        "qty": {"mandatory": True, "validation": True},
        "note": {"mandatory": False, "validation": False},
        "outcome": {
            "mandatory": True, "validation": False, "children": True,
            "child_table": "asset_action_results", "child_pid": "action_id",
            "child_fields": {
                "action_id": {"mandatory": True, "validation": False},    # TODO Check if mandatory requirement is true here and works as expected
                "symbol_id": {"mandatory": True, "validation": False},
                "qty": {"mandatory": True, "validation": False},
                "value_share": {"mandatory": True, "validation": False}
            }
        }
    }

    def __init__(self, oid=None):
        icons = {
            CorporateAction.NA: JalIcon.NONE,
            CorporateAction.Merger: JalIcon.MERGER,
            CorporateAction.SpinOff: JalIcon.SPINOFF,
            CorporateAction.Split: JalIcon.SPLIT,
            CorporateAction.SymbolChange:  JalIcon.SYMBOL_CHANGE,
            CorporateAction.Delisting: JalIcon.DELISTING
        }
        self.names = {
            CorporateAction.NA: self.tr("UNDEFINED"),
            CorporateAction.SymbolChange: self.tr("Symbol change"),
            CorporateAction.Split: self.tr("Split"),
            CorporateAction.SpinOff: self.tr("Spin-off"),
            CorporateAction.Merger: self.tr("Merger"),
            CorporateAction.Delisting: self.tr("Delisting")
        }
        super().__init__(oid)
        self._otype = LedgerTransaction.CorporateAction
        self._data = self._read("SELECT a.type, a.timestamp, a.number, a.account_id, a.qty, a.symbol_id, a.note "
                                "FROM asset_actions AS a WHERE a.oid=:oid",
                                [(":oid", self._oid)], named=True)
        if self._data is None:
            raise IndexError(LedgerTransaction.NoOpException)
        results_query = self._exec("SELECT s.asset_id, r.symbol_id, r.qty, r.value_share FROM asset_action_results AS r "
                                   "LEFT JOIN asset_symbol AS s ON r.symbol_id=s.id WHERE action_id=:oid",
                                   [(":oid", self._oid)])
        self._results = []
        while results_query.next():
            self._results.append(self._read_record(results_query, named=True, cast=[int, int, Decimal, Decimal]))
        self._view_rows = len(self._results) + 1
        self._subtype = self._data['type']
        self._oname = self.names[self._subtype]
        if self._subtype == CorporateAction.SpinOff or self._view_rows < 2:
            self._view_rows = 2
        self._icon = JalIcon[icons[self._subtype]]
        self._timestamp = self._data['timestamp']
        self._account = jal.db.account.JalAccount(self._data['account_id'])
        self._account_name = self._account.name()
        self._account_currency = JalAsset(self._account.currency()).symbol()
        self._reconciled = self._account.reconciled_at() >= self._timestamp
        self._symbol = JalSymbol(self._data['symbol_id'])
        self._asset = self._symbol.asset()
        self._qty = Decimal(self._data['qty'])
        self._number = self._data['number']
        self._note = self._data['note']
        self._broker = self._account.organization()

    # Settlement returns timestamp as corporate action happens immediately in Jal
    def settlement(self) -> int:
        return self._timestamp

    def description(self, part_only=False) -> str:
        description = self.names[self._subtype]
        if self._note:
            description += ": " + self._note
        for result in self._results:
            if self._subtype == CorporateAction.SpinOff and result['asset_id'] == self._asset.id():
                continue   # Don't display initial asset in list
            description += "\n" + JalAsset(result['asset_id']).name()
            if result['value_share'] < Decimal('1.0'):
                description += f" ({result['value_share'] * Decimal('100')} %)"
        return description

    def value_change(self, part_only=False) -> list:
        result = []
        if self._subtype != CorporateAction.SpinOff:
            result.append(Decimal(-self._qty))
        result += [x['qty'] for x in self._results]
        if len(result) == 1:  # Need to feed at least 2 lines
            result.append(None)
        return result

    def value_currency(self) -> str:
        if self._subtype != CorporateAction.SpinOff:
            symbol = f" {self._symbol.symbol()}\n"
        else:
            symbol = ""
        for x in self._results:
            symbol += f" {JalSymbol(x['symbol_id']).symbol()}\n"
        return symbol[:-1]  # Crop ending line break

    def value_total(self) -> list:
        if self._subtype == CorporateAction.SpinOff:
            balance = []
        elif self._subtype == CorporateAction.Split:
            balance = [Decimal('0')]
        else:
            balance = [self._account.get_asset_amount(self._timestamp, self._asset.id())]
        for asset_id in [x['asset_id'] for x in self._results]:
            balance.append(self._account.get_asset_amount(self._timestamp, asset_id))
        return balance  # Crop ending line break

    def qty(self) -> Decimal:
        return self._qty

    # Price is undefined for corporate action but method is required in FIFO processing
    def price(self):
        return None

    # Returns a list of all results of corporate action. Elements are {"asset_id, qty, value_share}
    def get_results(self) -> list:
        return self._results

    # Returns qty and value_share for result of corporate action that corresponds to given asset
    def get_result_for_asset(self, asset) -> tuple:
        out = [x for x in self._results if x['asset_id'] == asset.id()]
        if len(out) == 1:
            return Decimal(out[0]['qty']), Decimal(out[0]['value_share'])
        else:
            return Decimal('0'), Decimal('0')

    # Sets value_share for the result of corporate action that corresponds to given asset
    def set_result_share(self, asset, share: Decimal) -> None:
        out = [x for x in self._results if x['asset_id'] == asset.id()]
        if len(out) == 1:
            self._exec("UPDATE asset_action_results SET value_share=:share WHERE action_id=:action_id AND symbol_id=:symbol_id",
                       [(":share", format_decimal(share)), (":action_id", self._oid), (":symbol_id", out[0]['symbol_id'])])
            out[0]['value_share'] = format_decimal(share)
        else:
            raise LedgerError(self.tr("Asset isn't a part of corporate action results: ") + f"{asset.name()}")

    # Returns a list {"timestamp", "amount", "note"} that represents payments out of corporate actions to given account
    # in given account currency
    @classmethod
    def get_payments(cls, account) -> list:
        payments = []
        query = cls._exec("SELECT a.timestamp, r.qty, a.note FROM asset_actions AS a "
                          "LEFT JOIN asset_action_results AS r ON r.action_id=a.oid "
                          "LEFT JOIN asset_symbol AS s ON r.symbol_id=s.id "
                          "WHERE a.account_id=:account_id AND s.asset_id=:account_currency",
                          [(":account_id", account.id()), (":account_currency", account.currency())])
        while query.next():
            timestamp, amount, note = cls._read_record(query, cast=[int, Decimal, str])
            payments.append({"timestamp": timestamp, "amount": amount, "note": note})
        return payments

    def processLedger(self, ledger):
        if self._subtype == CorporateAction.NA:
            raise LedgerError(self.tr("Corporate action type isn't defined. Date: ") \
                  + f"{ts2dt(self._timestamp)}, " + f"{self._account.name()} - {self._symbol.symbol()}")
        # Get asset amount accumulated before current operation
        asset_amount = ledger.getAmount(BookAccount.Assets, self._account.id(), self._asset.id())
        if asset_amount < self._qty:
            raise LedgerError(self.tr("Asset amount is not enough for corporate action processing. Date: ")
                              + f"{ts2dt(self._timestamp)}, "
                              + f"Asset amount: {asset_amount}, Operation: {self.dump()}")
        if asset_amount > self._qty:
            raise LedgerError(self.tr("Unhandled case: Corporate action covers not full open position. Date: ")
                              + f"{ts2dt(self._timestamp)}, "
                              + f"Asset amount: {asset_amount}, Operation: {self.dump()}")
        # Calculate total asset allocation after corporate action and verify it equals 100%
        allocation = Decimal('0') + sum([x['value_share'] for x in self._results])
        if self._subtype != CorporateAction.Delisting and allocation != Decimal('1.0'):
            raise LedgerError(self.tr("Results value of corporate action doesn't match 100% of initial asset value. ")
                              + f"Date: {ts2dt(self._timestamp)}, Asset amount: {asset_amount}, "
                              + f"Distributed: {100.0 * float(allocation)}%, Operation: {self.dump()}")
        processed_qty, processed_value = self._close_deals_fifo(Decimal('-1.0'), self._qty)
        # Withdraw value with old quantity of old asset
        ledger.appendTransaction(self, BookAccount.Assets, -processed_qty, asset_id=self._asset.id(), value=-processed_value)
        if self._subtype == CorporateAction.Delisting:  # Map value to costs and exit - nothing more for delisting
            ledger.appendTransaction(self, BookAccount.Costs, processed_value, category=PredefinedCategory.Profit, peer=self._broker, tag=self._asset.tag().id())
            return
        # Process assets after corporate action
        closed_trades = self._deals_closed_by_operation()
        for result in self._results:
            asset = JalSymbol(result['symbol_id']).asset()
            qty = Decimal(result['qty'])
            share = Decimal(result['value_share'])
            value = share * processed_value
            if asset.type() == PredefinedAsset.Money:
                ledger.appendTransaction(self, BookAccount.Money, qty)
                ledger.appendTransaction(self, BookAccount.Incomes, -qty, category=PredefinedCategory.Interest, peer=self._broker)
            else:
                for trade in closed_trades:
                    cost_size_adjustment = (share * self._qty / qty, qty / self._qty)
                    self._account.open_trade(trade, asset, modified_by=self, adjustment=cost_size_adjustment)
                ledger.appendTransaction(self, BookAccount.Assets, qty, asset_id=asset.id(), value=value)

# ----------------------------------------------------------------------------------------------------------------------
# A same-account exchange of one asset into another that PRESERVES THE COST BASIS and recognizes no income.
# It covers wrapping (ETH -> WETH), supplying to and withdrawing from a lending protocol (USDG -> aEthUSDG) and
# liquid staking: the wallet keeps the same economic position, only in the shape of a receipt token, so - unlike a
# Swap - nothing is disposed of at market value and no profit or loss is realized.
#
# The quantity is free to change while the basis is not. A rebasing receipt token folds the yield accrued since the
# last interaction into the amount it mints or burns (Aave: supply 30.854731 USDG -> receive 37.110840 aEthUSDG),
# while a share-based one shows no such difference at all and carries the same yield in its redemption rate (Fluid's
# ERC-4626 fTokens). Booking that difference as income would therefore report income for one protocol and nothing for
# the other though they are economically identical, so a conversion recognizes nothing: the yield rides along as an
# unrealized gain in the position and realizes only when the underlying is finally disposed of. Rewards that arrive
# as a separate inflow with no counterpart (Merkl claims, staking payouts) are a different thing and stay
# StakingReward payments. See CRYPTO_PATH decisions #52-#54.
class Conversion(LedgerTransaction):
    _db_table = "conversions"
    _db_fields = {
        "timestamp": {"mandatory": True, "validation": True},
        "account_id": {"mandatory": True, "validation": True},
        "tx_hash": {"mandatory": False, "validation": True, "default": ''},
        "out_symbol_id": {"mandatory": True, "validation": True},
        "out_qty": {"mandatory": True, "validation": True},
        "in_symbol_id": {"mandatory": True, "validation": True},
        "in_qty": {"mandatory": True, "validation": True},
        "fee_symbol_id": {"mandatory": False, "validation": True, "default": None},
        "fee_qty": {"mandatory": False, "validation": True, "default": None},
        "note": {"mandatory": False, "validation": False}
    }
    PART_FEE = 1

    def __init__(self, operation_data=None, opart=0):
        super().__init__(operation_data)
        self._otype = LedgerTransaction.Conversion
        self._data = self._read("SELECT c.timestamp, c.account_id, c.tx_hash, c.out_symbol_id, c.out_qty, "
                                "c.in_symbol_id, c.in_qty, c.fee_symbol_id, c.fee_qty, c.note FROM conversions AS c "
                                "WHERE c.oid=:oid", [(":oid", self._oid)], named=True)
        if self._data is None:
            raise IndexError(LedgerTransaction.NoOpException)
        self._timestamp = int(self._data['timestamp'])
        self._account = jal.db.account.JalAccount(self._data['account_id'])
        self._account_name = self._account.name()
        self._account_currency = JalAsset(self._account.currency()).symbol()
        self._out_symbol = JalSymbol(self._data['out_symbol_id'])
        self._out_asset = self._out_symbol.asset()
        self._out_qty = Decimal(self._data['out_qty'])
        self._in_symbol = JalSymbol(self._data['in_symbol_id'])
        self._in_asset = self._in_symbol.asset()
        self._in_qty = Decimal(self._data['in_qty'])
        self._fee_symbol = JalSymbol(self._data['fee_symbol_id'])
        self._fee_asset = self._fee_symbol.asset()
        self._fee_qty = Decimal(self._data['fee_qty']) if self._data['fee_qty'] else Decimal('0')
        # The converted asset is the operation's own one - it is the position FIFO consumes
        self._symbol = self._out_symbol
        self._asset = self._out_asset
        self._number = self._data['tx_hash']
        self._note = self._data['note']
        self._icon = JalIcon[JalIcon.CONVERSION]
        self._oname = self.tr("Conversion")
        self._peer_id = self._account.organization()
        self._reconciled = self._account.reconciled_at() >= self._timestamp
        self._view_rows = 3 if self._fee_asset.id() else 2

    # A conversion happens immediately
    def settlement(self) -> int:
        return self._timestamp

    def qty(self) -> Decimal:
        return self._out_qty

    # Price is undefined for a conversion as it keeps the cost basis (FIFO then creates zero profit/loss deals)
    def price(self):
        return None

    def note(self) -> str:
        return self._note

    def description(self, part_only=False) -> str:
        text = f"{self._out_qty} {self._out_symbol.symbol()} -> {self._in_qty} {self._in_symbol.symbol()}"
        if self._fee_asset.id():
            text += " " + self.tr("Fee:") + f" {self._fee_qty} {self._fee_symbol.symbol()}"
        if self._note:
            text += "\n" + self._note
        return text

    def value_change(self, part_only=False) -> list:
        result = [-self._out_qty, self._in_qty]
        if self._fee_asset.id():
            result.append(-self._fee_qty)
        return result

    def value_currency(self) -> str:
        text = f" {self._out_symbol.symbol()}\n {self._in_symbol.symbol()}"
        if self._fee_asset.id():
            text += f"\n {self._fee_symbol.symbol()}"
        return text

    def value_total(self) -> list:
        balance = [self._asset_total(self._account.id(), self._out_asset.id()),
                   self._asset_total(self._account.id(), self._in_asset.id())]
        if self._fee_asset.id():
            balance.append(self._asset_total(self._account.id(), self._fee_asset.id()))
        return balance

    def processLedger(self, ledger):
        if self._out_asset.id() == 0 or self._in_asset.id() == 0:
            raise LedgerError(self.tr("Conversion assets aren't set. Operation: ") + self.dump())
        if self._out_asset.id() == self._in_asset.id():
            raise LedgerError(self.tr("Can't process conversion of an asset into itself. Operation: ") + self.dump())
        if self._out_qty <= Decimal('0') or self._in_qty <= Decimal('0'):
            raise LedgerError(self.tr("Conversion quantities must be positive. Operation: ") + self.dump())
        available = ledger.getAmount(BookAccount.Assets, self._account.id(), self._out_asset.id())
        if available < self._out_qty:
            raise LedgerError(self.tr("Asset amount is not enough for conversion processing. Date: ")
                              + f"{ts2dt(self._timestamp)}, Asset amount: {available}, "
                              + f"Required: {self._out_qty}, Operation: {self.dump()}")
        # The lots of the converted asset are closed at their own cost basis (self.price() is None, so the deals
        # carry no profit or loss) and then re-opened on the acquired asset - each one keeping the operation that
        # opened it, and therefore its acquisition date. The whole position is re-scaled by the quantity the
        # conversion produced: per-unit price is multiplied by out_qty/in_qty and quantity by in_qty/out_qty, which
        # leaves every lot's value untouched. This is exactly how a corporate action and a bridge carry a basis over.
        processed_qty, processed_value = self._close_deals_fifo(Decimal('-1.0'), self._out_qty, asset=self._out_asset)
        if processed_qty < self._out_qty:
            raise LedgerError(self.tr("Processed asset amount is less than conversion amount. Date: ")
                              + f"{ts2dt(self._timestamp)}, Processed amount: {processed_qty}, "
                              + f"Required: {self._out_qty}, Operation: {self.dump()}")
        ledger.appendTransaction(self, BookAccount.Assets, -processed_qty,
                                 asset_id=self._out_asset.id(), value=-processed_value)
        adjustment = (self._out_qty / self._in_qty, self._in_qty / self._out_qty)
        for trade in self._deals_closed_by_operation():
            self._account.open_trade(trade, self._in_asset, modified_by=self, adjustment=adjustment)
        ledger.appendTransaction(self, BookAccount.Assets, self._in_qty,
                                 asset_id=self._in_asset.id(), value=processed_value)
        if self._fee_asset.id():
            self._process_conversion_fee(ledger)

    # Gas paid for the conversion is disposed at its cost basis to Costs/Fees - the same treatment Swap and Bridge
    # give it, so no profit or loss is realized on the native coin spent. See Transfer.processAssetFee() for the
    # jurisdiction caveat that applies here word for word.
    def _process_conversion_fee(self, ledger):
        if not self._peer_id:
            raise LedgerError(self.tr("Can't process the conversion fee as organization isn't set for account: ")
                              + self._account_name)
        available = ledger.getAmount(BookAccount.Assets, self._account.id(), self._fee_asset.id())
        if available < self._fee_qty:
            raise LedgerError(self.tr("Asset amount is not enough to pay the conversion fee. Date: ")
                              + f"{ts2dt(self._timestamp)}, Asset amount: {available}, "
                              + f"Required: {self._fee_qty}, Operation: {self.dump()}")
        processed_qty, processed_value = self._close_deals_fifo(Decimal('-1.0'), self._fee_qty, asset=self._fee_asset,
                                                               account=self._account, record_deals=False)
        if processed_qty < self._fee_qty:
            raise LedgerError(self.tr("Processed asset amount is less than the conversion fee. Date: ")
                              + f"{ts2dt(self._timestamp)}, Processed amount: {processed_qty}, "
                              + f"Required: {self._fee_qty}, Operation: {self.dump()}")
        ledger.appendTransaction(self, BookAccount.Assets, -processed_qty,
                                 asset_id=self._fee_asset.id(), value=-processed_value)
        ledger.appendTransaction(self, BookAccount.Costs, processed_value, part=self.PART_FEE,
                                 category=PredefinedCategory.Fees, peer=self._peer_id, tag=self._fee_asset.tag().id())


# ----------------------------------------------------------------------------------------------------------------------
# A cross-chain move of ONE asset between two accounts (its per-chain listing differs, its cost basis is carried).
# A bridge is seen on-chain as two independent transactions - a send on the source chain and a receive on the
# destination chain - which JAL imports in separate runs. Only the send is recognizable as part of a bridge (it is the
# wallet's own transaction into a known bridge/aggregator); the arrival looks like any other receipt and is imported
# as a plain transfer, which the user later adopts into this operation (jal/db/bridge_matcher.py). A Bridge therefore
# always knows its sending leg, and only the receiving one may be missing:
#   * both legs present -> a complete bridge: the send parks the disposed value in the Transfers book, the receive
#     drains it and re-opens the lots on the destination (cost basis carried, FX-adjusted when the accounts differ in
#     currency). An in-kind fee (in_qty < out_qty) is disposed to Costs at basis.
#   * send only (in_* NULL) -> a "pending half-bridge": the value is parked in the Transfers book and stays in transit
#     until the arrival is matched in.
# Gas and in-kind fees are disposed at cost basis (like the Swap gas fee) - realizing market P&L on them (#18) is a
# crypto-tax refinement deferred until crypto tax treatment is designed. Same-account bridges are forbidden.
class Bridge(LedgerTransaction):
    Fee = 0
    Outgoing = -1
    Incoming = 1
    _db_table = "bridges"
    _db_fields = {
        "out_timestamp": {"mandatory": True, "validation": True},
        "out_account_id": {"mandatory": True, "validation": True},
        "out_symbol_id": {"mandatory": True, "validation": True},
        "out_qty": {"mandatory": True, "validation": True},
        "out_tx_hash": {"mandatory": False, "validation": True, "default": ''},
        "in_timestamp": {"mandatory": False, "validation": True, "default": None},
        "in_account_id": {"mandatory": False, "validation": True, "default": None},
        "in_symbol_id": {"mandatory": False, "validation": True, "default": None},
        "in_qty": {"mandatory": False, "validation": True, "default": None},
        "in_tx_hash": {"mandatory": False, "validation": True, "default": ''},
        "fee_symbol_id": {"mandatory": False, "validation": True, "default": None},
        "fee_qty": {"mandatory": False, "validation": True, "default": None},
        "note": {"mandatory": False, "validation": False}
    }
    PART_FEE = 2

    def __init__(self, operation_data=None, opart=Outgoing):
        assert opart in [Bridge.Outgoing, Bridge.Incoming, Bridge.Fee], "Unknown bridge part"
        icons = {Bridge.Outgoing: JalIcon.TRANSFER_ASSET_OUT,
                 Bridge.Incoming: JalIcon.TRANSFER_ASSET_IN,
                 Bridge.Fee: JalIcon.FEE}
        self.names = {Bridge.Outgoing: self.tr("Outgoing bridge"),
                      Bridge.Incoming: self.tr("Incoming bridge"),
                      Bridge.Fee: self.tr("Bridge fee")}
        super().__init__(operation_data)
        self._otype = LedgerTransaction.Bridge
        self._opart = opart
        self._data = self._read("SELECT out_timestamp, out_account_id, out_symbol_id, out_qty, out_tx_hash, "
                                "in_timestamp, in_account_id, in_symbol_id, in_qty, in_tx_hash, "
                                "fee_symbol_id, fee_qty, note FROM bridges WHERE oid=:oid",
                                [(":oid", self._oid)], named=True)
        if self._data is None:
            raise IndexError(LedgerTransaction.NoOpException)
        present = lambda v: v is not None and v != ''   # _read() returns '' (not None) for a SQL NULL - an absent leg
        self._has_in = present(self._data['in_account_id'])   # the sending leg is always there; only the arrival waits
        self._out_timestamp = int(self._data['out_timestamp'])
        self._in_timestamp = int(self._data['in_timestamp']) if present(self._data['in_timestamp']) else None
        self._out_account = jal.db.account.JalAccount(self._data['out_account_id'])
        self._in_account = jal.db.account.JalAccount(self._data['in_account_id']) if self._has_in else None
        self._out_symbol = JalSymbol(self._data['out_symbol_id'])
        self._in_symbol = JalSymbol(self._data['in_symbol_id']) if self._has_in else None
        self._out_qty = Decimal(self._data['out_qty'])
        self._in_qty = Decimal(self._data['in_qty']) if present(self._data['in_qty']) else None
        self._fee_symbol = JalSymbol(self._data['fee_symbol_id']) if present(self._data['fee_symbol_id']) else None
        self._fee_qty = Decimal(self._data['fee_qty']) if present(self._data['fee_qty']) else Decimal('0')
        # The bridged asset - both legs carry the same one, so the sending leg (always present) names it
        self._symbol = self._out_symbol
        self._asset = self._symbol.asset()
        self._account = self._out_account
        self._out_tx_hash = self._data['out_tx_hash']
        self._in_tx_hash = self._data['in_tx_hash']
        # Each leg is a transaction of its own chain, so the part decides which hash and timestamp represents it
        self._number = self._in_tx_hash if opart == Bridge.Incoming else self._out_tx_hash
        self._note = self._data['note']
        self._timestamp = self._in_timestamp if opart == Bridge.Incoming else self._out_timestamp
        self._icon = JalIcon[icons[opart]]
        self._oname = self.names[opart]
        if opart == Bridge.Incoming:
            self._reconciled = self._has_in and self._in_account.reconciled_at() >= self._in_timestamp
        else:
            self._reconciled = self._out_account.reconciled_at() >= self._out_timestamp

    # A bridge is pending while its arriving leg is unknown (the sent value is still in transit)
    def is_pending(self) -> bool:
        return not self._has_in

    # Finish time of the bridge (required for FIFO compatibility); a pending half only knows when it was sent
    def settlement(self) -> int:
        return self._in_timestamp if self._has_in else self._out_timestamp

    def account_name(self):
        out = self._out_account.name()
        inp = self._in_account.name() if self._has_in else self.tr("(pending)")
        if self._opart == Bridge.Incoming:
            return f"{inp} <- {out}"
        else:   # Outgoing part and fee are booked on the source account
            return f"{out} -> {inp}"

    def account_id(self):
        if self._opart == Bridge.Incoming:
            return self._in_account.id()
        else:
            return self._out_account.id()

    def qty(self) -> Decimal:
        return self._out_qty

    # Price is undefined for a bridge as it keeps cost basis (this makes FIFO processing create zero profit/loss deals)
    def price(self):
        return None

    def note(self) -> str:
        return self._note

    def description(self, part_only=False) -> str:
        if self._opart == Bridge.Fee:
            note = f" ({self._note})" if self._note else ''
            return self.tr("Bridge fee") + note
        out_s = self._out_symbol.symbol()
        in_s = self._in_symbol.symbol() if self._has_in else "?"
        if self.is_pending():
            text = self.tr("Bridge (awaiting matching):") + f" {out_s} -> {in_s}"
        else:
            text = f"{out_s} -> {in_s}"
            if self._in_qty != self._out_qty:
                text += " [" + self.tr("In-kind fee:") + f" {self._out_qty - self._in_qty} {in_s}]"
        if self._note:
            text += " " + self._note
        return text

    def value_change(self, part_only=False) -> list:
        if self._opart == Bridge.Outgoing:
            return [-self._out_qty]
        elif self._opart == Bridge.Incoming:
            return [self._in_qty]
        elif self._opart == Bridge.Fee:
            return [-self._fee_qty]
        else:
            assert False, "Unknown bridge part"

    def value_currency(self) -> str:
        if self._opart == Bridge.Incoming:
            return self._in_symbol.symbol()
        elif self._opart == Bridge.Fee:
            return self._fee_symbol.symbol()
        else:
            return self._out_symbol.symbol()

    def value_total(self) -> list:
        if self._opart == Bridge.Outgoing:
            amount = self._asset_total(self._out_account.id(), self._asset.id())
        elif self._opart == Bridge.Incoming:
            amount = self._asset_total(self._in_account.id(), self._asset.id())
        elif self._opart == Bridge.Fee:
            amount = self._asset_total(self._out_account.id(), self._fee_symbol.asset().id())
        else:
            assert False, "Unknown bridge part"
        return [amount]

    def processLedger(self, ledger):
        if self._has_in:   # Coherence checks that only apply to a complete, matched bridge
            if self._asset.id() == 0 or self._asset.id() != self._in_symbol.asset().id():
                raise LedgerError(self.tr("Bridge must move the same asset between accounts. Operation: ") + self.dump())
            if self._out_account.id() == self._in_account.id():
                # Moving lots back into the same account would shadow the remainder of a partially bridged position
                raise LedgerError(self.tr("Bridge between the same account isn't supported. Operation: ") + self.dump())
            if self._in_qty > self._out_qty:
                raise LedgerError(self.tr("Bridge can't receive more asset than was sent. Operation: ") + self.dump())
            if self._out_timestamp > self._in_timestamp:
                raise LedgerError(self.tr("Bridge receive can't precede its send. Operation: ") + self.dump())
        if self._opart == Bridge.Outgoing:
            self.processOutgoing(ledger)
        elif self._opart == Bridge.Fee:
            if self._fee_symbol is None or self._fee_qty <= Decimal('0'):
                raise LedgerError(self.tr("Bridge fee asset isn't set. Operation: ") + self.dump())
            self.processFee(ledger)
        elif self._opart == Bridge.Incoming:
            self.processIncoming(ledger)
        else:
            assert False, "Unknown bridge part"

    # Withdraw the sent asset at its cost basis and park the value in the Transfers book (a pending half stops here -
    # the value simply stays in transit until the arriving leg is matched in and drains it)
    def processOutgoing(self, ledger):
        available = ledger.getAmount(BookAccount.Assets, self._out_account.id(), self._asset.id())
        if available < self._out_qty:
            raise LedgerError(self.tr("Asset amount is not enough for bridge processing. Date: ")
                              + f"{ts2dt(self._out_timestamp)}, Asset amount: {available}, "
                              + f"Required: {self._out_qty}, Operation: {self.dump()}")
        processed_qty, processed_value = self._close_deals_fifo(Decimal('-1.0'), self._out_qty)
        if processed_qty < self._out_qty:
            raise LedgerError(self.tr("Processed asset amount is less than bridge amount. Date: ")
                              + f"{ts2dt(self._out_timestamp)}, Processed amount: {processed_qty}, "
                              + f"Required: {self._out_qty}, Operation: {self.dump()}")
        ledger.appendTransaction(self, BookAccount.Assets, -processed_qty, asset_id=self._asset.id(), value=-processed_value)
        ledger.appendTransaction(self, BookAccount.Transfers, self._out_qty, asset_id=self._asset.id(), value=processed_value)

    # Gas on the source chain, disposed from the source account at cost basis to Costs/Fees (no P&L, like Swap gas)
    def processFee(self, ledger):
        fee_asset = self._fee_symbol.asset()
        available = ledger.getAmount(BookAccount.Assets, self._out_account.id(), fee_asset.id())
        if available < self._fee_qty:
            raise LedgerError(self.tr("Asset amount is not enough to pay the bridge fee. Date: ")
                              + f"{ts2dt(self._out_timestamp)}, Asset amount: {available}, "
                              + f"Required: {self._fee_qty}, Operation: {self.dump()}")
        processed_qty, processed_value = self._close_deals_fifo(Decimal('-1.0'), self._fee_qty,
                                                               asset=fee_asset, account=self._out_account, record_deals=False)
        if processed_qty < self._fee_qty:
            raise LedgerError(self.tr("Processed asset amount is less than the bridge fee. Date: ")
                              + f"{ts2dt(self._out_timestamp)}, Processed amount: {processed_qty}, "
                              + f"Required: {self._fee_qty}, Operation: {self.dump()}")
        ledger.appendTransaction(self, BookAccount.Assets, -processed_qty, asset_id=fee_asset.id(), value=-processed_value)
        ledger.appendTransaction(self, BookAccount.Costs, processed_value, part=self.PART_FEE,
                                 category=PredefinedCategory.Fees, peer=self._out_account.organization())

    # The arriving leg only ever runs for a complete bridge (a pending half has no such part in 'operation_sequence'):
    # take the deals closed by the outgoing leg (created strictly before the fee leg's, and summing to out_qty), then
    # drain the value the outgoing leg parked in the Transfers book.
    def processIncoming(self, ledger):
        transfer_trades = []
        bridged_qty = Decimal('0')
        for trade in self._deals_closed_by_operation():
            if bridged_qty >= self._out_qty:
                break
            transfer_trades.append(trade)
            bridged_qty += trade.qty()
        value = self._read("SELECT value FROM ledger WHERE book_account=:book_transfers AND otype=:otype AND oid=:id",
                           [(":book_transfers", BookAccount.Transfers), (":otype", self._otype), (":id", self._oid)],
                           check_unique=True)
        if not value:
            raise LedgerError(self.tr("Asset withdrawal not found for bridge.") + f" Operation:  {self.dump()}")
        value = Decimal(value)
        if self._out_account.currency() == self._in_account.currency():
            rate = Decimal('1')
        else:   # Cost basis is converted into the destination account currency with the FX rate at the deposit time
            rate = JalAsset(self._out_account.currency()).quote(self._in_timestamp, self._in_account.currency())[1]
            if rate == Decimal('0'):
                raise LedgerError(self.tr("There is no FX rate to convert bridge cost basis. Date: ")
                                  + f"{ts2dt(self._in_timestamp)}, Operation: {self.dump()}")
        transfer_value = rate * value
        for trade in transfer_trades:   # Move open trades from source to destination (adjust cost basis by FX rate)
            self._in_account.open_trade(trade, self._asset, modified_by=self, adjustment=(rate, Decimal('1')))
        ledger.appendTransaction(self, BookAccount.Transfers, -self._out_qty, asset_id=self._asset.id(), value=-transfer_value)
        ledger.appendTransaction(self, BookAccount.Assets, self._out_qty, asset_id=self._asset.id(), value=transfer_value)
        if self._in_qty < self._out_qty:   # In-kind bridge fee: dispose the difference from the destination at basis
            fee_qty = self._out_qty - self._in_qty
            processed_qty, processed_value = self._close_deals_fifo(Decimal('-1.0'), fee_qty,
                                                                   account=self._in_account, record_deals=False)
            ledger.appendTransaction(self, BookAccount.Assets, -processed_qty, asset_id=self._asset.id(), value=-processed_value)
            ledger.appendTransaction(self, BookAccount.Costs, processed_value, part=self.PART_FEE,
                                     category=PredefinedCategory.Fees, peer=self._in_account.organization())
