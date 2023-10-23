import logging
from decimal import Decimal
from PySide6.QtWidgets import QApplication
from jal.constants import BookAccount, CustomColor, PredefinedCategory, PredefinedAsset
from jal.db.helpers import format_decimal
from jal.db.db import JalDB
import jal.db.account
from jal.db.asset import JalAsset
from jal.widgets.helpers import ts2dt


# ----------------------------------------------------------------------------------------------------------------------
# Class to define and handle custom ledger errors
class LedgerError(Exception):
    pass


# ----------------------------------------------------------------------------------------------------------------------
class LedgerTransaction(JalDB):
    NA = 0                  # Transaction types - these are aligned with tabs in main window
    IncomeSpending = 1
    Dividend = 2
    Trade = 3
    Transfer = 4
    CorporateAction = 5
    _db_table = ''   # Table where operation is stored in DB
    _db_fields = {}

    def __init__(self, operation_data=None):
        super().__init__()
        if type(operation_data) == dict:
            operation_id = self.create_operation(self._db_table, self._db_fields, operation_data)
        else:
            operation_id = operation_data
        self._oid = operation_id
        self._otype = 0
        self._oname = ''
        self._subtype = 0
        self._data = None
        self._view_rows = 1    # How many rows it will require operation in QTableView
        self._label = '?'
        self._label_color = CustomColor.LightRed
        self._timestamp = 0
        self._account = None
        self._account_name = ''
        self._account_currency = ''
        self._asset = None
        self._number = ''
        self._reconciled = False

    def tr(self, text):
        return QApplication.translate("LedgerTransaction", text)

    def dump(self):
        return str(self._data)

    @staticmethod
    def get_operation(operation_type, operation_id, display_type=None):
        if operation_type == LedgerTransaction.IncomeSpending:
            return IncomeSpending(operation_id)
        elif operation_type == LedgerTransaction.Dividend:
            return Dividend(operation_id)
        elif operation_type == LedgerTransaction.Trade:
            return Trade(operation_id)
        elif operation_type == LedgerTransaction.Transfer:
            return Transfer(operation_id, display_type)
        elif operation_type == LedgerTransaction.CorporateAction:
            return CorporateAction(operation_id)
        else:
            raise ValueError(f"An attempt to select unknown operation type: {operation_type}")

    @staticmethod
    def create_new(operation_type, operation_data):
        if operation_type == LedgerTransaction.IncomeSpending:
            return IncomeSpending(operation_data)
        elif operation_type == LedgerTransaction.Dividend:
            return Dividend(operation_data)
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
        _ = self._exec(f"DELETE FROM {self._db_table} WHERE id={self._oid}")
        self._oid = 0
        self._otype = 0
        self._data = None

    # Returns operation id if operation found by operation data, else 0
    def find_operation(self, operation_type: int, operation_data: dict) -> int:
        if operation_type == LedgerTransaction.IncomeSpending:
            table = IncomeSpending._db_table
            fields = IncomeSpending._db_fields
        elif operation_type == LedgerTransaction.Dividend:
            table = Dividend._db_table
            fields = Dividend._db_fields
        elif operation_type == LedgerTransaction.Trade:
            table = Trade._db_table
            fields = Trade._db_fields
        elif operation_type == LedgerTransaction.Transfer:
            table = Transfer._db_table
            fields = Transfer._db_fields
        elif operation_type == LedgerTransaction.CorporateAction:
            table = CorporateAction._db_table
            fields = CorporateAction._db_fields
        else:
            raise ValueError(f"An attempt to create unknown operation type: {operation_type}")
        self.validate_operation_data(table, fields, operation_data)
        return self.locate_operation(table, fields, operation_data)

    # Returns how many rows is required to display operation in QTableView
    def view_rows(self) -> int:
        return self._view_rows

    def _money_total(self, account_id) -> Decimal:
        money = self._read("SELECT amount_acc FROM ledger_totals WHERE op_type=:op_type AND operation_id=:oid AND "
                           "account_id = :account_id AND book_account=:book",
                           [(":op_type", self._otype), (":oid", self._oid),
                            (":account_id", account_id), (":book", BookAccount.Money)])
        money = Decimal('0') if money is None else Decimal(money)
        debt = self._read("SELECT amount_acc FROM ledger_totals WHERE op_type=:op_type AND operation_id=:oid AND "
                          "account_id = :account_id AND book_account=:book",
                          [(":op_type", self._otype), (":oid", self._oid),
                           (":account_id", account_id), (":book", BookAccount.Liabilities)])
        debt = Decimal('0') if debt is None else Decimal(debt)
        return money + debt

    def _asset_total(self, account_id, asset_id) -> Decimal:
        amount = self._read("SELECT amount_acc FROM ledger_totals WHERE op_type=:op_type AND operation_id=:oid AND "
                            "account_id=:account_id AND asset_id=:asset_id AND book_account=:book",
                            [(":op_type", self._otype), (":oid", self._oid), (":account_id", account_id),
                             (":asset_id", asset_id), (":book", BookAccount.Assets)])
        amount = Decimal('0') if amount is None else Decimal(amount)
        return amount

    # Performs FIFO deals match in ledger: takes current open positions from 'open_trades' table and converts
    # them into deals in 'deals' table while supplied qty is enough.
    # deal_sign = +1 if closing deal is Buy operation and -1 if it is Sell operation.
    # qty - quantity of asset that closes previous open positions
    # price is None if we process corporate action or transfer where we keep initial value and don't have profit or loss
    # Returns total qty, value of deals created.
    def _close_deals_fifo(self, deal_sign, qty, price):
        processed_qty = Decimal('0')
        processed_value = Decimal('0')
        # Get a list of all previous not matched trades or corporate actions
        query = self._exec("SELECT timestamp, op_type, operation_id, account_id, asset_id, price, remaining_qty "
                           "FROM trades_opened "
                           "WHERE account_id=:account_id AND asset_id=:asset_id AND remaining_qty!=:zero "
                           "ORDER BY timestamp, op_type DESC",
                           [(":account_id", self._account.id()), (":asset_id", self._asset.id()),
                            (":zero", format_decimal(Decimal('0')))])
        while query.next():
            opening_trade = self._read_record(query, named=True, cast=[int, int, int, int, int, Decimal, Decimal])
            next_deal_qty = opening_trade['remaining_qty']
            if (processed_qty + next_deal_qty) > qty:  # We can't close all trades with current operation
                next_deal_qty = qty - processed_qty    # If it happens - just process the remainder of the trade
            remaining_qty = opening_trade['remaining_qty'] - next_deal_qty
            _ = self._exec("UPDATE trades_opened SET remaining_qty=:new_remaining_qty "
                           "WHERE op_type=:op_type AND operation_id=:id AND asset_id=:asset_id",
                           [(":new_remaining_qty", format_decimal(remaining_qty)), (":asset_id", self._asset.id()),
                            (":op_type", opening_trade['op_type']), (":id", opening_trade['operation_id'])])
            open_price = opening_trade['price']
            close_price = opening_trade['price'] if price is None else price
            _ = self._exec(
                "INSERT INTO trades_closed(account_id, asset_id, open_op_type, open_op_id, open_timestamp, open_price, "
                "close_op_type, close_op_id, close_timestamp, close_price, qty) "
                "VALUES(:account_id, :asset_id, :open_op_type, :open_op_id, :open_timestamp, :open_price, "
                ":close_op_type, :close_op_id, :close_timestamp, :close_price, :qty)",
                [(":account_id", self._account.id()), (":asset_id", self._asset.id()),
                 (":open_op_type", opening_trade['op_type']), (":open_op_id", opening_trade['operation_id']),
                 (":open_timestamp", opening_trade['timestamp']), (":open_price", format_decimal(open_price)),
                 (":close_op_type", self._otype), (":close_op_id", self._oid),
                 (":close_timestamp", self.timestamp()), (":close_price", format_decimal(close_price)),
                 (":qty", format_decimal((-deal_sign) * next_deal_qty))])
            processed_qty += next_deal_qty
            processed_value += (next_deal_qty * open_price)
            if processed_qty == qty:
                break
        return processed_qty, processed_value

    def id(self):
        return self._oid

    def type(self):
        return self._otype

    def subtype(self):
        return self._subtype

    def oid(self):
        return self._oid

    def label(self):
        return self._label

    def name(self):
        return self._oname

    def label_color(self):
        return self._label_color

    def timestamp(self):
        return self._timestamp

    def account(self):
        return self._account

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

    def description(self) -> str:
        return ''

    def value_change(self) -> list:
        return [0]

    def value_total(self) -> str:
        return "-.--"

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

    def __init__(self, operation_id=None):
        super().__init__(operation_id)
        self._otype = LedgerTransaction.IncomeSpending
        self._data = self._read("SELECT a.timestamp, a.account_id, a.peer_id, p.name AS peer, "
                                "a.alt_currency_id AS currency FROM actions AS a "
                                "LEFT JOIN agents AS p ON a.peer_id = p.id WHERE a.id=:oid",
                                [(":oid", self._oid)], named=True)
        self._timestamp = self._data['timestamp']
        self._account = jal.db.account.JalAccount(self._data['account_id'])
        self._account_name = self._account.name()
        self._account_currency = JalAsset(self._account.currency()).symbol()
        self._reconciled = self._account.reconciled_at() >= self._timestamp
        self._peer_id = self._data['peer_id']
        self._peer = self._data['peer']
        self._currency = self._data['currency']
        details_query = self._exec("SELECT d.category_id, c.name AS category, d.tag_id, t.tag, "
                                   "d.amount, d.amount_alt, d.note FROM action_details AS d "
                                   "LEFT JOIN categories AS c ON c.id=d.category_id "
                                   "LEFT JOIN tags AS t ON t.id=d.tag_id "
                                   "WHERE d.pid= :pid", [(":pid", self._oid)])
        self._details = []
        while details_query.next():
            self._details.append(self._read_record(details_query, named=True))
        self._amount = sum(Decimal(line['amount']) for line in self._details)
        self._label, self._label_color = ('—', CustomColor.DarkRed) if self._amount < 0 else ('+', CustomColor.DarkGreen)
        if self._currency:
            self._view_rows = 2
            self._currency_name = JalAsset(self._currency).symbol()
        self._amount_alt = sum(Decimal(line['amount_alt']) for line in self._details)

    def description(self) -> str:
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

    def value_change(self) -> list:
        if self._currency:
            return [self._amount, self._amount_alt]
        else:
            return [self._amount]

    def value_currency(self) -> str:
        if self._currency:
            return f" {self._account_currency}\n {self._currency_name}"
        else:
            return f" {self._account_currency}"

    def value_total(self) -> str:
        amount = self._money_total(self._account.id())
        if amount is not None:
            return f"{amount:,.2f}"
        else:
            return super().value_total()

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
            raise LedgerError(self.tr("Can't process operation without details") + f"  Operation: {self.dump()}")
        if self._amount < Decimal('0'):
            credit_taken = ledger.takeCredit(self, self._account.id(), -self._amount)
            ledger.appendTransaction(self, BookAccount.Money, -(-self._amount - credit_taken))
        else:
            credit_returned = ledger.returnCredit(self, self._account.id(), self._amount)
            if credit_returned < self._amount:
                ledger.appendTransaction(self, BookAccount.Money, self._amount - credit_returned)
        for detail in self._details:
            book = BookAccount.Costs if Decimal(detail['amount']) < Decimal('0') else BookAccount.Incomes
            ledger.appendTransaction(self, book, -Decimal(detail['amount']),
                                     category=detail['category_id'], peer=self._peer_id, tag=detail['tag_id'])


# ----------------------------------------------------------------------------------------------------------------------
class Dividend(LedgerTransaction):
    Dividend = 1
    BondInterest = 2
    StockDividend = 3
    StockVesting = 4
    _db_table = "dividends"
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

    def __init__(self, operation_id=None):
        labels = {
            Dividend.Dividend: ('Δ', CustomColor.DarkGreen),
            Dividend.BondInterest: ('%', CustomColor.DarkGreen),
            Dividend.StockDividend: ('Δ\n+', CustomColor.DarkGreen),
            Dividend.StockVesting: ('Δ\n+', CustomColor.DarkBlue)
        }
        super().__init__(operation_id)
        self._otype = LedgerTransaction.Dividend
        self._view_rows = 2
        self._data = self._read("SELECT d.type, d.timestamp, d.ex_date, d.number, d.account_id, d.asset_id, "
                                "d.amount, d.tax, l.amount_acc AS t_qty, d.note AS note "
                                "FROM dividends AS d "
                                "LEFT JOIN assets AS a ON d.asset_id = a.id "
                                "LEFT JOIN ledger_totals AS l ON l.op_type=d.op_type AND l.operation_id=d.id "
                                "AND l.book_account = :book_assets WHERE d.id=:oid",
                                [(":book_assets", BookAccount.Assets), (":oid", self._oid)], named=True)
        self._subtype = self._data['type']
        try:
            self._label, self._label_color = labels[self._subtype]
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
        self._broker = self._account.organization()

    # Returns a list of Dividend objects for given asset, account and subtype
    # if asset_id is 0 - return for all assets, if subtype is 0 - return all types
    # skip_accrued=True - don't include accrued interest in resulting list
    @classmethod
    def get_list(cls, account_id: int, asset_id: int = 0, subtype: int = 0, skip_accrued: bool = False) -> list:
        dividends = []
        if skip_accrued:
            query = "SELECT d.id FROM dividends d LEFT JOIN trades t ON d.account_id=t.account_id "\
                    "AND d.asset_id=t.asset_id AND d.number=t.number AND t.number!='' "\
                    "WHERE d.account_id=:account AND t.id IS NULL"
        else:
            query = "SELECT d.id FROM dividends d WHERE d.account_id=:account"
        params = [(":account", account_id)]
        if asset_id:
            query += " AND d.asset_id=:asset"
            params += [(":asset", asset_id)]
        if subtype:
            query += " AND d.type=:type"
            params += [(":type", subtype)]
        query = cls._exec(query, params)
        while query.next():
            dividends.append(Dividend(cls._read_record(query, cast=[int])))
        return dividends

    # Settlement returns timestamp - it is required for stock dividend/vesting
    def settlement(self) -> int:
        return self._timestamp

    # Returns ex-dividend date if it is present for this dividend
    def ex_date(self) -> int:
        return self._ex_date

    # Return price of asset for stock dividend and vesting
    def price(self) -> Decimal:
        if self._subtype != Dividend.StockDividend and self._subtype != Dividend.StockVesting:
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
        if self._subtype == Dividend.StockDividend or self._subtype == Dividend.StockVesting:
            price = self._asset.quote(self._timestamp, self._account.currency())[1]
            if not price:
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

    def description(self) -> str:
        return self._note + "\n" + self.tr("Tax: ") + self._asset.country_name()

    def value_change(self) -> list:
        if self._tax:
            return [self._amount, -self._tax]
        else:
            return [self._amount, None]

    def value_currency(self) -> str:
        if self._subtype == Dividend.StockDividend or self._subtype == Dividend.StockVesting:
            if self._tax:
                return f" {self._asset.symbol(self._account.currency())}\n {self._account_currency}"
            else:
                return f" {self._asset.symbol(self._account.currency())}"
        else:
            return f" {self._account_currency}\n {self._asset.symbol(self._account.currency())}"

    def value_total(self) -> str:
        amount = self._money_total(self._account.id())
        if self._subtype == Dividend.StockDividend or self._subtype == Dividend.StockVesting:
            qty = self._asset_total(self._account.id(), self._asset.id())
            if qty is None:
                return super().value_total()
            if amount is None:
                return f"{qty:.2f}"
            else:
                return f"{qty:.2f}\n{amount:.2f}"
        if amount is not None:
            return f"{amount:,.2f}"
        else:
            return super().value_total()

    def update_amount(self, amount: Decimal) -> None:
        self._exec("UPDATE dividends SET amount=:amount WHERE id=:id",
                   [(":id", self._oid), (":amount", format_decimal(amount))])

    def update_tax(self, new_tax) -> None:   # FIXME method should take Decimal value, not float
        _ = self._exec("UPDATE dividends SET tax=:tax WHERE id=:dividend_id",
                       [(":dividend_id", self._oid), (":tax", new_tax)], commit=True)

    def processLedger(self, ledger):
        if self._broker is None:
            raise LedgerError(
                self.tr("Can't process dividend as bank isn't set for investment account: ") + self._account_name)
        if self._subtype == Dividend.StockDividend or self._subtype == Dividend.StockVesting:
            self.processStockDividendOrVesting(ledger)
            return
        if self._subtype == Dividend.Dividend:
            category = PredefinedCategory.Dividends
        elif self._subtype == Dividend.BondInterest:
            category = PredefinedCategory.Interest
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
            ledger.appendTransaction(self, BookAccount.Incomes, -self._amount, category=category, peer=self._broker)
        else:   # This branch is valid for accrued bond interest payments for bond buying trades
            ledger.appendTransaction(self, BookAccount.Costs, -self._amount, category=category, peer=self._broker)
        if self._tax:
            ledger.appendTransaction(self, BookAccount.Costs, self._tax,
                                     category=PredefinedCategory.Taxes, peer=self._broker)

    def processStockDividendOrVesting(self, ledger):
        asset_amount = ledger.getAmount(BookAccount.Assets, self._account.id(), self._asset.id())
        if asset_amount < Decimal('0'):
            raise NotImplemented(self.tr("Not supported action: stock dividend or vesting closes short trade.") +
                                 f" Operation: {self.dump()}")
        _ = self._exec(
            "INSERT INTO trades_opened(timestamp, op_type, operation_id, account_id, asset_id, price, remaining_qty) "
            "VALUES(:timestamp, :type, :operation_id, :account_id, :asset_id, :price, :remaining_qty)",
            [(":timestamp", self._timestamp), (":type", self._otype), (":operation_id", self._oid),
             (":account_id", self._account.id()), (":asset_id", self._asset.id()),
             (":price", format_decimal(self.price())),(":remaining_qty", format_decimal(self._amount))])
        ledger.appendTransaction(self, BookAccount.Assets, self._amount,
                                 asset_id=self._asset.id(), value=self._amount * self.price())
        if self._tax:
            ledger.appendTransaction(self, BookAccount.Money, -self._tax)
            ledger.appendTransaction(self, BookAccount.Costs, self._tax,
                                     category=PredefinedCategory.Taxes, peer=self._broker)


# ----------------------------------------------------------------------------------------------------------------------
class Trade(LedgerTransaction):
    _db_table = "trades"
    _db_fields = {
        "timestamp": {"mandatory": True, "validation": True},
        "settlement": {"mandatory": False, "validation": False},
        "number": {"mandatory": False, "validation": True},
        "account_id": {"mandatory": True, "validation": True},
        "asset_id": {"mandatory": True, "validation": True},
        "qty": {"mandatory": True, "validation": True},
        "price": {"mandatory": True, "validation": True},
        "fee": {"mandatory": True, "validation": False},
        "note": {"mandatory": False, "validation": False}
    }

    # operation_data is either an integer to select operation from database or a dict with operation data that is used
    # to create a new operation in database and then select it
    def __init__(self, operation_data=None):
        super().__init__(operation_data)
        self._otype = LedgerTransaction.Trade
        self._view_rows = 2
        self._data = self._read("SELECT t.timestamp, t.settlement, t.number, t.account_id, t.asset_id, t.qty, "
                                "t.price, t.fee, t.note FROM trades AS t WHERE t.id=:oid",
                                [(":oid", self._oid)], named=True)
        self._timestamp = self._data['timestamp']
        self._settlement = self._data['settlement']
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
        self._broker = self._account.organization()
        if self._qty < Decimal('0'):
            self._label, self._label_color = ('S', CustomColor.DarkRed)
        else:
            self._label, self._label_color = ('B', CustomColor.DarkGreen)

    def settlement(self) -> int:
        return self._settlement

    def price(self) -> Decimal:
        return self._price

    def update_price(self, price: Decimal) -> None:
        self._exec("UPDATE trades SET price=:price WHERE id=:id", [(":id", self._oid),
                                                                   (":price", format_decimal(price))])

    def qty(self) -> Decimal:
        return self._qty

    def update_qty(self, qty: Decimal) -> None:
        self._exec("UPDATE trades SET qty=:qty WHERE id=:id", [(":id", self._oid), (":qty", format_decimal(qty))])

    def fee(self) -> Decimal:
        return self._fee

    def amount(self) -> Decimal:
        return self._price * self._qty

    def description(self) -> str:
        if self._fee != Decimal('0'):
            text = f"{self._qty:+.2f} @ {self._price:.4f}\n({self._fee:.2f}) "
        else:
            text = f"{self._qty:+.2f} @ {self._price:.4f}\n"
        text += self._note
        return text

    def value_change(self) -> list:
        return [-(self._price * self._qty), self._qty]

    def value_currency(self) -> str:
        return f" {self._account_currency}\n {self._asset.symbol(self._account.currency())}"

    def value_total(self) -> str:
        amount = self._money_total(self._account.id())
        qty = self._asset_total(self._account.id(), self._asset.id())
        if amount is None or qty is None:
            return super().value_total()
        else:
            return f"{amount:,.2f}\n{qty:,.2f}"

    # Searches for dividend with type BondInterest that matches trade by timestamp, account, asset and number
    # This dividend represents accrued interest for this operation.
    # Returns value of accrued interest or 0 if such isn't found
    def accrued_interest(self,currency_id: int = 0) -> Decimal:
        id = self._read("SELECT id FROM dividends WHERE timestamp=:timestamp AND account_id=:account "
                        "AND asset_id=:asset AND number=:number AND type=:interest",
                        [(":timestamp", self._timestamp), (":account", self._account.id()), (":number", self._number),
                         (":asset", self._asset.id()), (":interest", Dividend.BondInterest)])
        value = Dividend(id).amount() if id else Decimal('0')
        if currency_id and currency_id != self._account.currency():
            return value * JalAsset(self._account.currency()).quote(self.timestamp(), currency_id)[1]
        else:
            return value

    def processLedger(self, ledger):
        if self._broker is None:
            raise LedgerError(
                self.tr("Can't process trade as bank isn't set for investment account: ") + self._account_name)
        deal_sign = Decimal('1.0').copy_sign(self._qty)  # 1 is buy and -1 is sell operation
        qty = abs(self._qty)
        trade_value = self._price * qty + deal_sign * self._fee
        processed_qty = Decimal('0')
        processed_value = Decimal('0')
        # Get asset amount accumulated before current operation
        asset_amount = ledger.getAmount(BookAccount.Assets, self._account.id(), self._asset.id())
        if ((-deal_sign) * asset_amount) > Decimal('0'):  # Match trade if we have asset that is opposite to operation
            processed_qty, processed_value = self._close_deals_fifo(deal_sign, qty, self._price)
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
                                     category=PredefinedCategory.Profit, peer=self._broker)
        if processed_qty < qty:  # We have a reminder that opens a new position
            _ = self._exec(
                "INSERT INTO trades_opened(timestamp, op_type, operation_id, account_id, asset_id, price, remaining_qty) "
                "VALUES(:timestamp, :type, :operation_id, :account_id, :asset_id, :price, :remaining_qty)",
                [(":timestamp", self._timestamp), (":type", self._otype), (":operation_id", self._oid),
                 (":account_id", self._account.id()), (":asset_id", self._asset.id()),
                 (":price", format_decimal(self._price)), (":remaining_qty", format_decimal(qty - processed_qty))])
            ledger.appendTransaction(self, BookAccount.Assets, deal_sign * (qty - processed_qty),
                                     asset_id=self._asset.id(), value=deal_sign * (qty - processed_qty) * self._price)
        if self._fee:
            ledger.appendTransaction(self, BookAccount.Costs, self._fee,
                                     category=PredefinedCategory.Fees, peer=self._broker)


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

    def __init__(self, operation_id=None, display_type=None):
        labels = {
            Transfer.Outgoing: ('<', CustomColor.DarkBlue),
            Transfer.Incoming: ('>', CustomColor.DarkBlue),
            Transfer.Fee: ('=', CustomColor.DarkRed)
        }
        super().__init__(operation_id)
        self._otype = LedgerTransaction.Transfer
        self._display_type = display_type
        self._data = self._read("SELECT t.withdrawal_timestamp, t.withdrawal_account, t.withdrawal, "
                                "t.deposit_timestamp, t.deposit_account, t.deposit, t.fee_account, t.fee, t.asset, "
                                "t.number, t.note FROM transfers AS t WHERE t.id=:oid",
                                [(":oid", self._oid)], named=True)
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
        try:
            self._label, self._label_color = labels[display_type]
        except KeyError:
            assert False, "Unknown transfer type"
        self._asset = JalAsset(self._data['asset'])
        self._number = self._data['number']
        self._account = self._withdrawal_account
        self._note = self._data['note']
        if self._display_type == Transfer.Outgoing:
            self._reconciled = self._withdrawal_account.reconciled_at() >= self._withdrawal_timestamp
        elif self._display_type == Transfer.Incoming:
            self._reconciled = self._deposit_account.reconciled_at() >= self._deposit_timestamp
        elif self._display_type == Transfer.Fee:
            self._reconciled = self._fee_account.reconciled_at() >= self._withdrawal_timestamp
        else:
            assert False, "Unknown transfer type"

    def timestamp(self):
        if self._display_type == Transfer.Incoming:
            return self._deposit_timestamp
        else:
            return self._withdrawal_timestamp

    # This is required for compatibility with other asset actions, but it will also allow to get finish time of transfer
    def settlement(self):
        return self._deposit_timestamp

    def account_name(self):
        if self._display_type == Transfer.Fee:
            return self._fee_account_name
        elif self._display_type == Transfer.Outgoing:
            return self._withdrawal_account_name + " -> " + self._deposit_account_name
        elif self._display_type == Transfer.Incoming:
            return self._deposit_account_name + " <- " + self._withdrawal_account_name
        else:
            assert False, "Unknown transfer type"

    def account_id(self):
        if self._display_type == Transfer.Fee:
            return self._fee_account.id()
        elif self._display_type == Transfer.Outgoing:
            return self._withdrawal_account.id()
        elif self._display_type == Transfer.Incoming:
            return self._deposit_account.id()
        else:
            assert False, "Unknown transfer type"

    def description(self) -> str:
        if self._asset.id():
            if self._display_type == Transfer.Incoming and self._withdrawal_currency != self._deposit_currency:
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

    def value_change(self) -> list:
        if self._display_type == Transfer.Outgoing:
            return [-self._withdrawal]
        elif self._display_type == Transfer.Incoming:
            if self._asset.id():
                return [self._withdrawal]  # amount of asset doesn't change and self._deposit contains a cost basis
            else:
                return [self._deposit]
        elif self._display_type == Transfer.Fee:
            return [-self._fee]
        else:
            assert False, "Unknown transfer type"

    def value_currency(self) -> str:
        if self._display_type == Transfer.Outgoing:
            if self._asset.id():
                return self._asset.symbol(self._withdrawal_account.currency())
            else:
                return self._withdrawal_currency
        elif self._display_type == Transfer.Incoming:
            if self._asset.id():
                return self._asset.symbol(self._deposit_account.currency())
            else:
                return self._deposit_currency
        elif self._display_type == Transfer.Fee:
            return self._fee_currency
        else:
            assert False, "Unknown transfer type"

    def value_total(self) -> str:
        if self._display_type == Transfer.Outgoing:
            if self._asset.id():
                amount = self._asset_total(self._withdrawal_account.id(), self._asset.id())
            else:
                amount = self._money_total(self._withdrawal_account.id())
        elif self._display_type == Transfer.Incoming:
            if self._asset.id():
                amount = self._asset_total(self._deposit_account.id(), self._asset.id())
            else:
                amount = self._money_total(self._deposit_account.id())
        elif self._display_type == Transfer.Fee:
            amount = self._money_total(self._fee_account.id())
        else:
            assert False, "Unknown transfer type"
        if amount is None:
            return super().value_total()
        else:
            return f"{amount:,.2f}"

    def processLedger(self, ledger):
        if self._display_type == Transfer.Outgoing:
            if self._asset.id():
                self.processAssetTransfer(ledger)
            else:
                credit_taken = ledger.takeCredit(self, self._withdrawal_account.id(), self._withdrawal)
                ledger.appendTransaction(self, BookAccount.Money, -(self._withdrawal - credit_taken))
                ledger.appendTransaction(self, BookAccount.Transfers, self._withdrawal)
        elif self._display_type == Transfer.Fee:
            if not self._fee_account.organization():
                raise LedgerError(self.tr("Can't collect fee from the account '{}' ({}) as organization isn't set for it. Date: {}").format(
                    self._fee_account.name(), self._fee_account.number(), ts2dt(self._withdrawal_timestamp)))
            credit_taken = ledger.takeCredit(self, self._fee_account.id(), self._fee)
            ledger.appendTransaction(self, BookAccount.Money, -(self._fee - credit_taken))
            ledger.appendTransaction(self, BookAccount.Costs, self._fee,
                                     category=PredefinedCategory.Fees, peer=self._fee_account.organization())
        elif self._display_type == Transfer.Incoming:
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
        if self._display_type == Transfer.Outgoing:   # Withdraw asset from source account
            asset_amount = ledger.getAmount(BookAccount.Assets, self._withdrawal_account.id(), self._asset.id())
            if asset_amount < transfer_amount:
                raise LedgerError(self.tr("Asset amount is not enough for asset transfer processing. Date: ")
                                  + f"{ts2dt(self._withdrawal_timestamp)}, Asset amount: {asset_amount}, "
                                  + f"Required: {transfer_amount}, Operation: {self.dump()}")
            processed_qty, processed_value = self._close_deals_fifo(Decimal('-1.0'), transfer_amount, None)
            if processed_qty < transfer_amount:
                raise LedgerError(self.tr("Processed asset amount is less than transfer amount. Date: ")
                                  + f"{ts2dt(self._withdrawal_timestamp)}, Processed amount: {processed_qty}, "
                                  + f"Required: {transfer_amount}, Operation: {self.dump()}")
            ledger.appendTransaction(self, BookAccount.Assets, -processed_qty,
                                     asset_id=self._asset.id(), value=-processed_value)
            ledger.appendTransaction(self, BookAccount.Transfers, transfer_amount,
                                     asset_id=self._asset.id(), value=processed_value)
        elif self._display_type == Transfer.Incoming:
            # get initial value of withdrawn asset
            value = self._read("SELECT value FROM ledger "
                               "WHERE book_account=:book_transfers AND op_type=:op_type AND operation_id=:id",
                               [(":book_transfers", BookAccount.Transfers), (":op_type", self._otype),
                                (":id", self._oid)], check_unique=True)
            if not value:
                raise LedgerError(self.tr("Asset withdrawal not found for transfer.") + f" Operation:  {self.dump()}")
            if self._withdrawal_account.currency() == self._deposit_account.currency():
                transferred_value = Decimal(value)
            else:
                transferred_value = self._deposit
            price = transferred_value / transfer_amount
            _ = self._exec(
                "INSERT INTO trades_opened(timestamp, op_type, operation_id, account_id, asset_id, price, remaining_qty) "
                "VALUES(:timestamp, :type, :operation_id, :account_id, :asset_id, :price, :remaining_qty)",
                [(":timestamp", self._deposit_timestamp), (":type", self._otype), (":operation_id", self._oid),
                 (":account_id", self._deposit_account.id()), (":asset_id", self._asset.id()),
                 (":price", format_decimal(price)), (":remaining_qty", format_decimal(transfer_amount))])
            ledger.appendTransaction(self, BookAccount.Transfers, -transfer_amount,
                                     asset_id=self._asset.id(), value=-transferred_value)
            ledger.appendTransaction(self, BookAccount.Assets, transfer_amount,
                                     asset_id=self._asset.id(), value=transferred_value)
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

    def __init__(self, operation_id=None):
        labels = {
            CorporateAction.NA: ("?", CustomColor.LightRed),
            CorporateAction.Merger: ('⭃', CustomColor.Black),
            CorporateAction.SpinOff: ('⎇', CustomColor.DarkGreen),
            CorporateAction.Split: ('ᗕ', CustomColor.Black),
            CorporateAction.SymbolChange:  ('🡘', CustomColor.Black),
            CorporateAction.Delisting: ('✖', CustomColor.DarkRed)
        }
        self.names = {
            CorporateAction.NA: self.tr("UNDEFINED"),
            CorporateAction.SymbolChange: self.tr("Symbol change"),
            CorporateAction.Split: self.tr("Split"),
            CorporateAction.SpinOff: self.tr("Spin-off"),
            CorporateAction.Merger: self.tr("Merger"),
            CorporateAction.Delisting: self.tr("Delisting")
        }
        super().__init__(operation_id)
        self._otype = LedgerTransaction.CorporateAction
        self._data = self._read("SELECT a.type, a.timestamp, a.number, a.account_id, a.qty, a.asset_id, a.note "
                                "FROM asset_actions AS a WHERE a.id=:oid", [(":oid", self._oid)], named=True)
        results_query = self._exec("SELECT asset_id, qty, value_share FROM action_results WHERE action_id=:oid",
                                   [(":oid", self._oid)])
        self._results = []
        while results_query.next():
            self._results.append(self._read_record(results_query, named=True))
        self._view_rows = len(self._results)
        self._subtype = self._data['type']
        self._oname = self.names[self._subtype]
        if self._subtype == CorporateAction.SpinOff or self._view_rows < 2:
            self._view_rows = 2
        self._label, self._label_color = labels[self._subtype]
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

    def description(self) -> str:
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

    def value_change(self) -> list:
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

    def value_total(self) -> str:
        if self._subtype == CorporateAction.SpinOff:
            balance = ""
        elif self._subtype == CorporateAction.Split:
            balance = f"{0.00:,.2f}\n"
        else:
            balance = f"{self._account.get_asset_amount(self._timestamp, self._asset.id()):,.2f}\n"
        query = self._exec("SELECT asset_id FROM action_results WHERE action_id=:oid", [(":oid", self._oid)])
        while query.next():
            qty = self._account.get_asset_amount(self._timestamp, self._read_record(query, cast=[int]))
            balance += f"{qty:,.2f}\n"
        return balance[:-1]  # Crop ending line break

    def qty(self) -> Decimal:
        return self._qty

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
            raise  LedgerError(self.tr("Asset isn't a part of corporate action results: ") + f"{asset.name()}")

    # Returns a list {"timestamp", "amount", "note"} that represents payments out of corporate actions to given account
    # in given account currency
    @classmethod
    def get_payments(cls, account) -> list:
        payments = []
        query = cls._exec("SELECT a.timestamp, r.qty, a.note FROM asset_actions AS a "
                          "LEFT JOIN action_results AS r ON r.action_id=a.id "
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
                                        f"Distributed: {100.0 * float(allocation)}%, Operation: {self.dump()}")
        processed_qty, processed_value = self._close_deals_fifo(Decimal('-1.0'), self._qty, None)
        # Withdraw value with old quantity of old asset
        ledger.appendTransaction(self, BookAccount.Assets, -processed_qty,
                                 asset_id=self._asset.id(), value=-processed_value)
        if self._subtype == CorporateAction.Delisting:  # Map value to costs and exit - nothing more for delisting
            ledger.appendTransaction(self, BookAccount.Costs, processed_value,
                                     category=PredefinedCategory.Profit, peer=self._broker)
            return
        # Process assets after corporate action
        query = self._exec("SELECT asset_id, qty, value_share FROM action_results WHERE action_id=:oid",
                           [(":oid", self._oid)])
        while query.next():
            asset, qty, share = self._read_record(query, cast=[JalAsset, Decimal, Decimal])
            if asset.type() == PredefinedAsset.Money:
                ledger.appendTransaction(self, BookAccount.Money, qty)
                ledger.appendTransaction(self, BookAccount.Incomes, -qty,
                                         category=PredefinedCategory.Interest, peer=self._broker)
            else:
                value = share * processed_value
                price = value / qty
                _ = self._exec(
                    "INSERT INTO trades_opened(timestamp, op_type, operation_id, "
                    "account_id, asset_id, price, remaining_qty) "
                    "VALUES(:timestamp, :type, :operation_id, :account_id, :asset_id, :price, :remaining_qty)",
                    [(":timestamp", self._timestamp), (":type", self._otype), (":operation_id", self._oid),
                     (":account_id", self._account.id()), (":asset_id", asset.id()), (":price", format_decimal(price)),
                     (":remaining_qty", format_decimal(qty))])
                ledger.appendTransaction(self, BookAccount.Assets, qty, asset_id=asset.id(), value=value)
