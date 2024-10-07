import logging
from decimal import Decimal
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from jal.constants import BookAccount, PredefinedCategory, PredefinedAsset, DepositActions
from jal.db.helpers import format_decimal
from jal.db.db import JalDB
import jal.db.account
from jal.db.asset import JalAsset
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
    TermDeposit = 6
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
        elif operation_type == LedgerTransaction.TermDeposit:
            return TermDeposit(oid, opart)
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
        elif operation_type == LedgerTransaction.TermDeposit:
            table = TermDeposit._db_table
            fields = TermDeposit._db_fields
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
    # Returns total qty, value of deals created.
    def _close_deals_fifo(self, deal_sign, qty):
        assert self._asset.id() == self.asset().id()      # The function works with these assumptions as any operation
        assert self._account.id() == self.account().id()  # takes only one incoming asset and account
        processed_qty = Decimal('0')
        processed_value = Decimal('0')
        open_trades = self._account.open_trades_list(self._asset)
        for trade in open_trades:
            remaining_qty = trade.open_qty(adjusted=True)
            next_deal_qty = remaining_qty
            if (processed_qty + next_deal_qty) > qty:  # We can't close full quantity with current operation
                next_deal_qty = qty - processed_qty    # If it happens - just process the remainder of the trade
            trade.set_qty((remaining_qty - next_deal_qty)/trade.q_adjustment())
            self._account.open_trade(trade, self._asset, modified_by=self)
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
    _db_table = "asset_payments"
    _db_fields = {
        "timestamp": {"mandatory": True, "validation": True},
        "ex_date": {"mandatory": False, "validation": False},
        "number": {"mandatory": False, "validation": True, "default": ''},
        "type": {"mandatory": True, "validation": True},
        "account_id": {"mandatory": True, "validation": True},
        "asset_id": {"mandatory": True, "validation": True},
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
            AssetPayment.Fee: JalIcon.FEE
        }
        self.names = {
            AssetPayment.NA: self.tr("UNDEFINED"),
            AssetPayment.Dividend: self.tr("Dividend"),
            AssetPayment.BondInterest: self.tr("Bond Interest"),
            AssetPayment.StockDividend: self.tr("Stock Dividend"),
            AssetPayment.StockVesting: self.tr("Stock Vesting"),
            AssetPayment.BondAmortization: self.tr("Bond Amortization"),
            AssetPayment.Fee: self.tr("Asset fee/tax")
        }
        super().__init__(oid)
        self._otype = LedgerTransaction.AssetPayment
        self._opart = opart
        self._view_rows = 2
        self._data = self._read("SELECT p.type, p.timestamp, p.ex_date, p.number, p.account_id, p.asset_id, "
                                "p.amount, p.tax, l.amount_acc AS t_qty, p.note AS note "
                                "FROM asset_payments AS p "
                                "LEFT JOIN assets AS a ON p.asset_id = a.id "
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
        self._asset = JalAsset(self._data['asset_id'])
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
        if skip_accrued:
            query = "SELECT p.oid FROM asset_payments p LEFT JOIN trades t ON p.account_id=t.account_id "\
                    "AND p.asset_id=t.asset_id AND p.number=t.number AND t.number!='' "\
                    "WHERE p.account_id=:account AND t.oid IS NULL"
        else:
            query = "SELECT p.oid FROM asset_payments p WHERE p.account_id=:account"
        params = [(":account", account_id)]
        if asset_id:
            query += " AND p.asset_id=:asset"
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
        text = self._note if self._note else self.tr("Dividend payment for:") + f" {self._asset.symbol()} ({self._asset.name()})"
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
        if self._tax:
            return [self._amount, -self._tax]
        else:
            return [self._amount, None]

    def value_currency(self) -> str:
        if (self._subtype == AssetPayment.StockDividend or self._subtype == AssetPayment.StockVesting) and not self._opart:
            if self._tax:
                return f" {self._asset.symbol(self._account.currency())}\n {self._account_currency}"
            else:
                return f" {self._asset.symbol(self._account.currency())}"
        else:
            return f" {self._account_currency}"

    def value_total(self) -> list:
        balance = []
        amount = self._money_total(self._account.id())
        if self._subtype == AssetPayment.StockDividend or self._subtype == AssetPayment.StockVesting:
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
        if self._subtype == AssetPayment.StockDividend or self._subtype == AssetPayment.StockVesting:
            self.processStockDividendOrVesting(ledger)
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
        "asset_id": {"mandatory": True, "validation": True},
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
        self._data = self._read("SELECT t.timestamp, t.settlement, t.number, t.account_id, t.asset_id, t.qty, "
                                "t.price, t.fee, t.note FROM trades AS t WHERE t.oid=:oid",
                                [(":oid", self._oid)], named=True)
        self._timestamp = int(self._data['timestamp'])
        self._settlement = int(self._data['settlement'])
        self._account = jal.db.account.JalAccount(self._data['account_id'])
        self._account_name = self._account.name()
        self._account_currency = JalAsset(self._account.currency()).symbol()
        self._reconciled = self._account.reconciled_at() >= self._timestamp
        self._asset = JalAsset(self._data['asset_id'])
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
        deal_text = f"{self._qty:+.2f} {self._asset.symbol(self._account.currency())} @ {self._price:.4f}"
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
            return f" {self._account_currency}\n {self._asset.symbol(self._account.currency())}"

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
        oid = self._read("SELECT oid FROM asset_payments WHERE timestamp=:timestamp AND account_id=:account "
                         "AND asset_id=:asset AND number=:number AND type=:interest",
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
        "number": {"mandatory": False, "validation": True, "default": ''},
        "asset": {"mandatory": False, "validation": True, "default": None},
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
                                "t.deposit_timestamp, t.deposit_account, t.deposit, t.fee_account, t.fee, t.asset, "
                                "t.number, t.note FROM transfers AS t WHERE t.oid=:oid",
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
        self._asset = JalAsset(self._data['asset'])
        self._number = self._data['number']
        self._account = self._withdrawal_account
        self._note = self._data['note']
        self._icon = JalIcon[icons[(opart, self._asset.id() == 0)]]
        self._oname = self.names[(opart, self._asset.id() == 0)]
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
                return self._asset.symbol(self._withdrawal_account.currency())
            else:
                return self._withdrawal_currency
        elif self._opart == Transfer.Incoming:
            if self._asset.id():
                return self._asset.symbol(self._deposit_account.currency())
            else:
                return self._deposit_currency
        elif self._opart == Transfer.Fee:
            return self._fee_currency
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
            if self._withdrawal_account.currency() == self._deposit_account.currency():
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
        "asset_id": {"mandatory": True, "validation": True},
        "qty": {"mandatory": True, "validation": True},
        "note": {"mandatory": False, "validation": False},
        "outcome": {
            "mandatory": True, "validation": False, "children": True,
            "child_table": "action_results", "child_pid": "action_id",
            "child_fields": {
                "action_id": {"mandatory": True, "validation": False},    # TODO Check if mandatory requirement is true here and works as expected
                "asset_id": {"mandatory": True, "validation": False},
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
        self._data = self._read("SELECT a.type, a.timestamp, a.number, a.account_id, a.qty, a.asset_id, a.note "
                                "FROM asset_actions AS a WHERE a.oid=:oid", [(":oid", self._oid)], named=True)
        if self._data is None:
            raise IndexError(LedgerTransaction.NoOpException)
        results_query = self._exec("SELECT asset_id, qty, value_share FROM action_results WHERE action_id=:oid",
                                   [(":oid", self._oid)])
        self._results = []
        while results_query.next():
            self._results.append(self._read_record(results_query, named=True))
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
        self._asset = JalAsset(self._data['asset_id'])
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
        query = self._exec("SELECT asset_id, value_share FROM action_results WHERE action_id=:oid",
                           [(":oid", self._oid)])
        while query.next():
            result = self._read_record(query, named=True, cast=[int, Decimal])
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
        query = self._exec("SELECT qty FROM action_results WHERE action_id=:oid", [(":oid", self._oid)])
        while query.next():
            result.append(self._read_record(query, cast=[Decimal]))
        if len(result) == 1:  # Need to feed at least 2 lines
            result.append(None)
        return result

    def value_currency(self) -> str:
        if self._subtype != CorporateAction.SpinOff:
            symbol = f" {self._asset.symbol(self._account.currency())}\n"
        else:
            symbol = ""
        query = self._exec("SELECT asset_id FROM action_results WHERE action_id=:oid", [(":oid", self._oid)])
        while query.next():
            symbol += f" {JalAsset(self._read_record(query, cast=[int])).symbol()}\n"
        return symbol[:-1]  # Crop ending line break

    def value_total(self) -> list:
        if self._subtype == CorporateAction.SpinOff:
            balance = []
        elif self._subtype == CorporateAction.Split:
            balance = [Decimal('0')]
        else:
            balance = [self._account.get_asset_amount(self._timestamp, self._asset.id())]
        query = self._exec("SELECT asset_id FROM action_results WHERE action_id=:oid", [(":oid", self._oid)])
        while query.next():
            balance.append(self._account.get_asset_amount(self._timestamp, self._read_record(query, cast=[int])))
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
    def get_result_for_asset(self, asset) -> (Decimal, Decimal):
        out = [x for x in self._results if x['asset_id'] == asset.id()]
        if len(out) == 1:
            return Decimal(out[0]['qty']), Decimal(out[0]['value_share'])
        else:
            return Decimal('0'), Decimal('0')

    # Sets value_share for the result of corporate action that corresponds to given asset
    def set_result_share(self, asset, share: Decimal) -> None:
        out = [x for x in self._results if x['asset_id'] == asset.id()]
        if len(out) == 1:
            self._exec("UPDATE action_results SET value_share=:share WHERE action_id=:action_id AND asset_id=:asset_id",
                       [(":share", format_decimal(share)), (":action_id", self._oid), (":asset_id", asset.id())])
            out[0]['value_share'] = format_decimal(share)
        else:
            raise LedgerError(self.tr("Asset isn't a part of corporate action results: ") + f"{asset.name()}")

    # Returns a list {"timestamp", "amount", "note"} that represents payments out of corporate actions to given account
    # in given account currency
    @classmethod
    def get_payments(cls, account) -> list:
        payments = []
        query = cls._exec("SELECT a.timestamp, r.qty, a.note FROM asset_actions AS a "
                          "LEFT JOIN action_results AS r ON r.action_id=a.oid "
                          "WHERE a.account_id=:account_id AND r.asset_id=:account_currency",
                          [(":account_id", account.id()), (":account_currency", account.currency())])
        while query.next():
            timestamp, amount, note = cls._read_record(query, cast=[int, Decimal, str])
            payments.append({"timestamp": timestamp, "amount": amount, "note": note})
        return payments

    def processLedger(self, ledger):
        if self._subtype == CorporateAction.NA:
            raise LedgerError(self.tr("Corporate action type isn't defined. Date: ") \
                  + f"{ts2dt(self._timestamp)}, " + f"{self._account.name()} - {self._asset.symbol()}")
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
        allocation = Decimal('0')
        query = self._exec("SELECT value_share FROM action_results WHERE action_id=:oid", [(":oid", self._oid)])
        while query.next():
            allocation += self._read_record(query, cast=[Decimal])
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
        query = self._exec("SELECT asset_id, qty, value_share FROM action_results WHERE action_id=:oid", [(":oid", self._oid)])  # FIXME - replace with get_results() call
        closed_trades = self._deals_closed_by_operation()
        while query.next():
            asset, qty, share = self._read_record(query, cast=[JalAsset, Decimal, Decimal])
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
class TermDeposit(LedgerTransaction):
    _db_table = "term_deposits"
    _db_fields = {
        "account_id": {"mandatory": True, "validation": False},
        "note": {"mandatory": False, "validation": False},
        "actions": {
            "mandatory": True, "validation": False, "children": True,
            "child_table": "deposit_actions", "child_pid": "deposit_id",
            "child_fields": {
                "deposit_id": {"mandatory": True, "validation": False},
                "timestamp": {"mandatory": True, "validation": False},
                "action_type": {"mandatory": True, "validation": False},
                "amount": {"mandatory": True, "validation": False}
            }
        }
    }

    def __init__(self, oid=None, opart=0):
        icons = {
            DepositActions.Opening: JalIcon.DEPOSIT_OPEN,
            DepositActions.TopUp: JalIcon.DEPOSIT_OPEN,
            DepositActions.Renewal: JalIcon.DEPOSIT_OPEN,
            DepositActions.PartialWithdrawal: JalIcon.DEPOSIT_CLOSE,
            DepositActions.Closing: JalIcon.DEPOSIT_CLOSE,
            DepositActions.InterestAccrued: JalIcon.INTEREST,
            DepositActions.TaxWithheld: JalIcon.TAX
        }
        super().__init__(oid)
        self._otype = LedgerTransaction.TermDeposit
        self._aid = opart   # action id
        self._data = self._read("SELECT da.timestamp, td.account_id, da.action_type, da.amount, td.note "
                                "FROM term_deposits td LEFT JOIN deposit_actions da ON td.oid=da.deposit_id "
                                "WHERE td.oid=:oid AND da.id=:aid",
                                [(":oid", self._oid), (":aid", self._aid)], named=True)
        if self._data is None:
            raise IndexError(LedgerTransaction.NoOpException)
        self._timestamp = self._data['timestamp']
        self._account = jal.db.account.JalAccount(self._data['account_id'])
        self._account_name = self._account.name()
        self._note = self._data['note']
        self._action = self._data['action_type']
        self._account_currency = JalAsset(self._account.currency()).symbol()
        self._amount = Decimal(self._data['amount'])
        self._icon = JalIcon[icons[self._action]]
        self._oname = f'{DepositActions().get_name(self._action)}'
        self._peer_id = self._account.organization()
        self._reconciled = self._account.reconciled_at() >= self._timestamp

    def _get_deposit_amount(self) -> Decimal:
        amount = Decimal('0')
        query = self._exec("SELECT amount FROM ledger WHERE otype=:otype AND oid=:oid AND "
                           "book_account=:book AND account_id=:account_id AND timestamp<=:timestamp",
                           [(":otype", self._otype), (":oid", self._oid), (":timestamp", self._timestamp),
                            (":account_id", self._account.id()), (":book", BookAccount.Savings)])
        while query.next():
            amount += self._read_record(query, cast=[Decimal])
        return amount

    def description(self, part_only=False) -> str:
        return f'{DepositActions().get_name(self._action)}: "{self._note}"'

    def value_change(self, part_only=False) -> list:
        if self._action == DepositActions.Opening or self._action == DepositActions.TaxWithheld:
            return [-self._amount]
        elif self._action == DepositActions.Closing or self._action == DepositActions.InterestAccrued:
            return [self._amount]
        else:
            return []

    def value_currency(self) -> str:
        return f" {self._account_currency}"

    def value_total(self) -> list:
        money = self._read("SELECT amount_acc FROM ledger WHERE otype=:otype AND oid=:oid AND "
                           "account_id = :account_id AND book_account=:book AND timestamp=:timestamp",
                           [(":otype", self._otype), (":oid", self._oid),
                            (":account_id", self._account.id()), (":book", BookAccount.Money), (":timestamp", self._timestamp)])
        debt = self._read("SELECT amount_acc FROM ledger WHERE otype=:otype AND oid=:oid AND "
                          "account_id = :account_id AND book_account=:book AND timestamp=:timestamp",
                          [(":otype", self._otype), (":oid", self._oid),
                           (":account_id", self._account.id()), (":book", BookAccount.Liabilities), (":timestamp", self._timestamp)])
        if money is None and debt is None:
            return []
        money = Decimal('0') if money is None else Decimal(money)
        debt = Decimal('0') if debt is None else Decimal(debt)
        return [money + debt]

    def amount(self) -> Decimal:
        return self._amount

    def processLedger(self, ledger):
        if not self._peer_id:
            raise LedgerError(self.tr("Can't process deposit as bank isn't set for account: ") + self._account_name)
        if self._action in [DepositActions.Opening, DepositActions.TopUp, DepositActions.Closing, DepositActions.PartialWithdrawal]:
            amount = self._get_deposit_amount() if self._action == DepositActions.Closing else self._amount
            if self._action in [DepositActions.Opening, DepositActions.TopUp]:
                amount = -amount
            if amount < Decimal('0'):
                credit_taken = ledger.takeCredit(self, self._account.id(), -amount)
                ledger.appendTransaction(self, BookAccount.Money, -(-amount - credit_taken))
            else:
                credit_returned = ledger.returnCredit(self, self._account.id(), amount)
                if credit_returned < amount:
                    ledger.appendTransaction(self, BookAccount.Money, amount - credit_returned)
            ledger.appendTransaction(self, BookAccount.Savings, -amount)
        elif self._action == DepositActions.TaxWithheld:
            ledger.appendTransaction(self, BookAccount.Savings, -self._amount)
            ledger.appendTransaction(self, BookAccount.Costs, self._amount,
                                     category=PredefinedCategory.Taxes, peer=self._peer_id, part=self._aid)
        elif self._action == DepositActions.InterestAccrued:
            ledger.appendTransaction(self, BookAccount.Savings, self._amount)
            ledger.appendTransaction(self, BookAccount.Incomes, -self._amount,
                                     category=PredefinedCategory.Interest, peer=self._peer_id, part=self._aid)
        else:
            assert False, "Not implemented deposit action"
