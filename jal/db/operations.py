from math import copysign
from datetime import datetime
from PySide6.QtWidgets import QApplication
from jal.constants import Setup, BookAccount, CustomColor, PredefinedPeer, PredefinedCategory
from jal.db.helpers import readSQL, executeSQL, readSQLrecord
from jal.db.db import JalDB


# ----------------------------------------------------------------------------------------------------------------------
class LedgerTransaction:
    NA = 0                  # Transaction types - these are aligned with tabs in main window
    IncomeSpending = 1
    Dividend = 2
    Trade = 3
    Transfer = 4
    CorporateAction = 5

    def __init__(self, operation_id=None):
        self._oid = operation_id
        self._otype = 0
        self._data = None
        self._table = ''       # Table where operation is stored in DB
        self._view_rows = 1    # How many rows it will require operation in QTableView
        self._label = '?'
        self._label_color = CustomColor.LightRed
        self._timestamp = 0
        self._account = 0
        self._account_name = ''
        self._account_currency = ''
        self._asset = 0
        self._asset_name = ''
        self._number = ''
        self._reconciled = False

    def tr(self, text):
        return QApplication.translate("IBKR", text)

    def dump(self):
        return f"{self._data}"

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
            raise ValueError(f"An attempt to create unknown operation type: {operation_type}")

    # Returns how many rows is required to display operation in QTableView
    def view_rows(self) -> int:
        return self._view_rows

    def _money_total(self, account_id) -> float:
        money = readSQL("SELECT amount_acc FROM ledger_totals WHERE op_type=:op_type AND operation_id=:oid AND "
                        "account_id = :account_id AND book_account=:book",
                        [(":op_type", self._otype), (":oid", self._oid),
                         (":account_id", account_id), (":book", BookAccount.Money)])
        debt = readSQL("SELECT amount_acc FROM ledger_totals WHERE op_type=:op_type AND operation_id=:oid AND "
                       "account_id = :account_id AND book_account=:book",
                       [(":op_type", self._otype), (":oid", self._oid),
                        (":account_id", account_id), (":book", BookAccount.Liabilities)])
        if money is not None:
            return money
        else:
            return debt

    def _asset_total(self, account_id, asset_id) -> float:
        return readSQL("SELECT amount_acc FROM ledger_totals WHERE op_type=:op_type AND operation_id=:oid AND "
                       "account_id = :account_id AND asset_id AND book_account=:book",
                       [(":op_type", self._otype), (":oid", self._oid), (":account_id", account_id),
                        (":asset_id", asset_id), (":book", BookAccount.Assets)])

    def type(self):
        return self._otype

    def oid(self):
        return self._oid

    def label(self):
        return self._label

    def label_color(self):
        return self._label_color

    def timestamp(self):
        return self._timestamp

    def account(self):
        return self._account_name

    def account_id(self):
        return self._account

    def asset(self):
        return self._asset_name

    def number(self):
        return self._number

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

    def processLedger(self, ledger):
        return
        raise NotImplementedError(f"processLedger() method is not defined in {type(self).__name__} class")


# ----------------------------------------------------------------------------------------------------------------------
class IncomeSpending(LedgerTransaction):
    def __init__(self, operation_id=None):
        super().__init__(operation_id)
        self._otype = LedgerTransaction.IncomeSpending
        self._table = "actions"
        self._data = readSQL("SELECT a.timestamp, a.account_id, a.peer_id, p.name AS peer, "
                             "a.alt_currency_id AS currency FROM actions AS a "
                             "LEFT JOIN agents AS p ON a.peer_id = p.id WHERE a.id=:oid",
                             [(":oid", self._oid)], named=True)
        self._timestamp = self._data['timestamp']
        self._account = self._data['account_id']
        self._account_name = JalDB().get_account_name(self._account)
        self._account_currency = JalDB().get_asset_name(JalDB().get_account_currency(self._account))
        self._reconciled = JalDB().account_reconciliation_timestamp(self._account) >= self._timestamp
        self._peer_id = self._data['peer_id']
        self._peer = self._data['peer']
        self._currency = self._data['currency']
        details_query = executeSQL("SELECT d.category_id, c.name AS category, d.tag_id, t.tag, "
                                   "d.amount, d.amount_alt, d.note FROM action_details AS d "
                                   "LEFT JOIN categories AS c ON c.id=d.category_id "
                                   "LEFT JOIN tags AS t ON t.id=d.tag_id "
                                   "WHERE d.pid= :pid", [(":pid", self._oid)])
        self._details = []
        while details_query.next():
            self._details.append(readSQLrecord(details_query, named=True))
        self._amount = sum(line['amount'] for line in self._details)
        self._label, self._label_color = ('—', CustomColor.DarkRed) if self._amount < 0 else ('+', CustomColor.DarkGreen)
        if self._currency:
            self._view_rows = 2
            self._currency_name = JalDB().get_asset_name(self._currency)
        self._amount_alt = sum(line['amount_alt'] for line in self._details)

    def description(self) -> str:
        description = self._peer
        if self._currency:
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
        amount = self._money_total(self._account)
        if amount is not None:
            return f"{amount:,.2f}"
        else:
            return super().value_total()

    def processLedger(self, ledger):
        if len(self._details) == 0:
            self.dump()
            raise ValueError(self.tr("Can't process operation without details"))
        if self._amount < 0:
            credit_taken = ledger.takeCredit(self, self._account, -self._amount)
            ledger.appendTransaction(self, BookAccount.Money, -(-self._amount - credit_taken))
        else:
            credit_returned = ledger.returnCredit(self, self._account, self._amount)
            if credit_returned < self._amount:
                ledger.appendTransaction(self, BookAccount.Money, self._amount - credit_returned)
        for detail in self._details:
            book = BookAccount.Costs if detail['amount'] < 0 else BookAccount.Incomes
            ledger.appendTransaction(self, book, -detail['amount'],
                                     category=detail['category_id'], peer=self._peer_id, tag=detail['tag_id'])


# ----------------------------------------------------------------------------------------------------------------------
class Dividend(LedgerTransaction):
    Dividend = 1
    BondInterest = 2
    StockDividend = 3

    def __init__(self, operation_id=None):
        labels = {
            Dividend.Dividend: ('Δ', CustomColor.DarkGreen),
            Dividend.BondInterest: ('%', CustomColor.DarkGreen),
            Dividend.StockDividend: ('Δ\n+', CustomColor.DarkGreen),
        }
        super().__init__(operation_id)
        self._table = "dividends"
        self._otype = LedgerTransaction.Dividend
        self._view_rows = 2
        self._data = readSQL("SELECT d.type, d.timestamp, d.number, d.account_id, d.amount, d.asset_id, d.tax, "
                             "l.amount_acc AS t_qty, d.note AS note, c.name AS country "
                             "FROM dividends AS d "
                             "LEFT JOIN assets AS a ON d.asset_id = a.id "
                             "LEFT JOIN countries AS c ON a.country_id = c.id "
                             "LEFT JOIN ledger_totals AS l ON l.op_type=d.op_type AND l.operation_id=d.id "
                             "AND l.book_account = :book_assets WHERE d.id=:oid",
                             [(":book_assets", BookAccount.Assets), (":oid", self._oid)], named=True)
        self._subtype = self._data['type']
        self._label, self._label_color = labels[self._subtype]
        self._timestamp = self._data['timestamp']
        self._account = self._data['account_id']
        self._account_name = JalDB().get_account_name(self._account)
        self._account_currency = JalDB().get_asset_name(JalDB().get_account_currency(self._account))
        self._reconciled = JalDB().account_reconciliation_timestamp(self._account) >= self._timestamp
        self._asset = self._data['asset_id']
        self._asset_symbol = JalDB().get_asset_name(self._asset)
        self._asset_name = JalDB().get_asset_name(self._asset, full=True)
        self._number = self._data['number']
        self._amount = self._data['amount']
        self._tax = self._data['tax']
        self._note = self._data['note']
        self._broker = JalDB().get_account_bank(self._account)

    def description(self) -> str:
        return self._note + "\n" + self.tr("Tax: ") + JalDB().get_asset_country(self._asset)

    def value_change(self) -> list:
        if self._tax:
            return [self._amount, -self._tax]
        else:
            return [self._amount, None]

    def value_currency(self) -> str:
        if self._subtype == Dividend.StockDividend:
            if self._tax:
                return f" {self._asset_symbol}\n {self._account_currency}"
            else:
                return f" {self._asset_symbol}"
        else:
            return f" {self._account_currency}\n {self._asset_symbol}"

    def value_total(self) -> str:
        amount = self._money_total(self._account)
        if self._subtype == Dividend.StockDividend:
            qty = self._asset_total(self._account, self._asset)
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

    def processLedger(self, ledger):
        if self._broker is None:
            raise ValueError(
                self.tr("Can't process trade as bank isn't set for investment account: ") + self._account_name)
        
        if self._subtype == Dividend.StockDividend:
            self.processStockDividend(ledger)
            return

        if self._subtype == Dividend.Dividend:
            income_category = PredefinedCategory.Dividends
        elif self._subtype == Dividend.BondInterest:
            income_category = PredefinedCategory.Interest
        else:
            raise ValueError(self.tr("Unsupported dividend type.") + f" Operation: {self.dump()}")
        if self._amount > 0:
            credit_returned = ledger.returnCredit(self, self._account, self._amount - self._tax)
            if credit_returned < (self._amount - self._tax):
                ledger.appendTransaction(self, BookAccount.Money, self._amount - credit_returned)  # tax will be deducted separately
            ledger.appendTransaction(self, BookAccount.Incomes, -self._amount,
                                     category=income_category, peer=self._broker)
        else:   # This branch is valid for accrued bond interest payments for bond buying trades
            credit_taken = ledger.takeCredit(self, self._account, -self._amount - self._tax)  # tax always positive
            if credit_taken < -self._amount:
                ledger.appendTransaction(self, BookAccount.Money, self._amount + credit_taken)  # tax will be deducted separately
            ledger.appendTransaction(self, BookAccount.Costs, -self._amount,
                                     category=income_category, peer=self._broker)
        if self._tax:
            ledger.appendTransaction(self, BookAccount.Money, -self._tax)
            ledger.appendTransaction(self, BookAccount.Costs, self._tax,
                                     category=PredefinedCategory.Taxes, peer=self._broker)

    def processStockDividend(self, ledger):
        asset_amount = ledger.getAmount(BookAccount.Assets, self._account, self._asset)
        if asset_amount < -Setup.CALC_TOLERANCE:
            raise NotImplemented(self.tr("Not supported action: stock dividend closes short trade.") +
                                 f" Operation: {self.dump()}")
        quote = JalDB().get_quote(self._asset, JalDB().get_account_currency(self._account), self._timestamp)
        if quote is None:
            raise ValueError(self.tr("No stock quote for stock dividend.") + f" Operation: {self.dump()}")
        _ = executeSQL(
            "INSERT INTO open_trades(timestamp, op_type, operation_id, account_id, asset_id, price, remaining_qty) "
            "VALUES(:timestamp, :type, :operation_id, :account_id, :asset_id, :price, :remaining_qty)",
            [(":timestamp", self._timestamp), (":type", self._otype), (":operation_id", self._oid),
             (":account_id", self._account), (":asset_id", self._asset), (":price", quote),
             (":remaining_qty", self._amount)])
        ledger.appendTransaction(self, BookAccount.Assets, self._amount,
                                 asset_id=self._asset, value=self._amount * quote)
        if self._tax:
            ledger.appendTransaction(self, BookAccount.Money, -self._tax)
            ledger.appendTransaction(self, BookAccount.Costs, self._tax,
                                     category=PredefinedCategory.Taxes, peer=self._broker)


# ----------------------------------------------------------------------------------------------------------------------
class Trade(LedgerTransaction):
    def __init__(self, operation_id=None):
        super().__init__(operation_id)
        self._table = "trades"
        self._otype = LedgerTransaction.Trade
        self._view_rows = 2
        self._data = readSQL("SELECT t.timestamp, t.number, t.account_id, t.asset_id, t.qty, t.price AS price, "
                             "t.fee, t.note FROM trades AS t WHERE t.id=:oid", [(":oid", self._oid)], named=True)
        self._label, self._label_color = ('S', CustomColor.DarkRed) if self._data['qty'] < 0 else ('B', CustomColor.DarkGreen)
        self._timestamp = self._data['timestamp']
        self._account = JalDB().get_account_name(self._data['account_id'])
        self._account = self._data['account_id']
        self._account_name = JalDB().get_account_name(self._account)
        self._account_currency = JalDB().get_asset_name(JalDB().get_account_currency(self._account))
        self._reconciled = JalDB().account_reconciliation_timestamp(self._account) >= self._timestamp
        self._asset = self._data['asset_id']
        self._asset_symbol = JalDB().get_asset_name(self._asset)
        self._asset_name = JalDB().get_asset_name(self._asset, full=True)
        self._number = self._data['number']
        self._qty = self._data['qty']
        self._price = self._data['price']
        self._fee = self._data['fee']
        self._note = self._data['note']
        self._broker = JalDB().get_account_bank(self._account)

    def description(self) -> str:
        if self._fee != 0:
            text = f"{self._qty:+.2f} @ {self._price:.4f}\n({self._fee:.2f}) "
        else:
            text = f"{self._qty:+.2f} @ {self._price:.4f}\n"
        text += self._note
        return text

    def value_change(self) -> list:
        return [-(self._price * self._qty), self._qty]

    def value_currency(self) -> str:
        return f" {self._account_currency}\n {self._asset_symbol}"

    def value_total(self) -> str:
        amount = self._money_total(self._account)
        qty = self._asset_total(self._account, self._asset)
        if amount is None:
            return super().value_total()
        else:
            return f"{amount:,.2f}\n{qty:,.2f}"

    def processLedger(self, ledger):
        if self._broker is None:
            raise ValueError(
                self.tr("Can't process trade as bank isn't set for investment account: ") + self._account_name)

        type = copysign(1, self._qty)  # 1 is buy, -1 is sell
        qty = abs(self._qty)
        trade_value = round(self._price * qty, 2) + type * self._fee
        processed_qty = 0
        processed_value = 0
        # Get asset amount accumulated before current operation
        asset_amount = ledger.getAmount(BookAccount.Assets, self._account, self._asset)
        if ((-type) * asset_amount) > 0:  # Process deal match if we have asset that is opposite to operation
            # Get a list of all previous not matched trades or corporate actions
            query = executeSQL(
                "SELECT timestamp, op_type, operation_id, account_id, asset_id, price, remaining_qty "
                "FROM open_trades "
                "WHERE account_id=:account_id AND asset_id=:asset_id AND remaining_qty!=0 "
                "ORDER BY timestamp, op_type DESC",
                [(":account_id", self._account), (":asset_id", self._asset)])
            while query.next():
                opening_trade = readSQLrecord(query, named=True)
                next_deal_qty = opening_trade['remaining_qty']
                if (processed_qty + next_deal_qty) > qty:  # We can't close all trades with current operation
                    next_deal_qty = qty - processed_qty  # If it happens - just process the remainder of the trade
                _ = executeSQL("UPDATE open_trades SET remaining_qty=remaining_qty-:qty "
                               "WHERE op_type=:op_type AND operation_id=:id AND asset_id=:asset_id",
                               [(":qty", next_deal_qty), (":op_type", opening_trade['op_type']),
                                (":id", opening_trade['operation_id']), (":asset_id", self._asset)])
                _ = executeSQL(
                    "INSERT INTO deals(account_id, asset_id, open_op_type, open_op_id, open_timestamp, open_price, "
                    "close_op_type, close_op_id, close_timestamp, close_price, qty) "
                    "VALUES(:account_id, :asset_id, :open_op_type, :open_op_id, :open_timestamp, :open_price, "
                    ":close_op_type, :close_op_id, :close_timestamp, :close_price, :qty)",
                    [(":account_id", self._account), (":asset_id", self._asset),
                     (":open_op_type", opening_trade['op_type']), (":open_op_id", opening_trade['operation_id']),
                     (":open_timestamp", opening_trade['timestamp']), (":open_price", opening_trade['price']),
                     (":close_op_type", self._otype), (":close_op_id", self._oid),
                     (":close_timestamp", self._timestamp), (":close_price", self._price),
                     (":qty", (-type) * next_deal_qty)])
                processed_qty += next_deal_qty
                processed_value += (next_deal_qty * opening_trade['price'])
                if processed_qty == qty:
                    break
        if type > 0:
            credit_value = ledger.takeCredit(self, self._account, trade_value)
        else:
            credit_value = ledger.returnCredit(self, self._account, trade_value)
        if credit_value < trade_value:
            ledger.appendTransaction(self, BookAccount.Money, (-type) * (trade_value - credit_value))
        if processed_qty > 0:  # Add result of closed deals
            # decrease (for sell) or increase (for buy) amount of assets in ledger
            ledger.appendTransaction(self, BookAccount.Assets, type * processed_qty,
                                     asset_id=self._asset, value=type * processed_value)
            ledger.appendTransaction(self, BookAccount.Incomes, type * ((self._price * processed_qty) - processed_value),
                                     category=PredefinedCategory.Profit, peer=self._broker)
        if processed_qty < qty:  # We have reminder that opens a new position
            _ = executeSQL(
                "INSERT INTO open_trades(timestamp, op_type, operation_id, account_id, asset_id, price, remaining_qty) "
                "VALUES(:timestamp, :type, :operation_id, :account_id, :asset_id, :price, :remaining_qty)",
                [(":timestamp", self._timestamp), (":type", self._otype), (":operation_id", self._oid),
                 (":account_id", self._account), (":asset_id", self._asset), (":price", self._price),
                 (":remaining_qty", qty - processed_qty)])
            ledger.appendTransaction(self, BookAccount.Assets, type * (qty - processed_qty), asset_id=self._asset,
                                     value=type * (qty - processed_qty) * self._price)
        if self._fee:
            ledger.appendTransaction(self, BookAccount.Costs, self._fee,
                                     category=PredefinedCategory.Fees, peer=self._broker)


# ----------------------------------------------------------------------------------------------------------------------
class Transfer(LedgerTransaction):
    Fee = 0
    Outgoing = -1
    Incoming = 1

    def __init__(self, operation_id=None, display_type=None):
        labels = {
            Transfer.Outgoing: ('<', CustomColor.DarkBlue),
            Transfer.Incoming: ('>', CustomColor.DarkBlue),
            Transfer.Fee: ('=', CustomColor.DarkRed)
        }
        super().__init__(operation_id)
        self.table = "transfers"
        self._otype = LedgerTransaction.Transfer
        self._display_type = display_type
        self._data = readSQL("SELECT t.withdrawal_timestamp, t.withdrawal_account, t.withdrawal, t.deposit_timestamp, "
                             "t.deposit_account, t.deposit, t.fee_account, t.fee, t.asset, t.note "
                             "FROM transfers AS t WHERE t.id=:oid", [(":oid", self._oid)], named=True)
        self._withdrawal_account = self._data['withdrawal_account']
        self._withdrawal_account_name = JalDB().get_account_name(self._withdrawal_account)
        self._withdrawal_timestamp = self._data['withdrawal_timestamp']
        self._withdrawal = self._data['withdrawal']
        self._withdrawal_currency = JalDB().get_asset_name(JalDB().get_account_currency(self._withdrawal_account))
        self._deposit_account = self._data['deposit_account']
        self._deposit_account_name = JalDB().get_account_name(self._deposit_account)
        self._deposit = self._data['deposit']
        self._deposit_currency = JalDB().get_asset_name(JalDB().get_account_currency(self._deposit_account))
        self._deposit_timestamp = self._data['deposit_timestamp']
        self._fee_account = self._data['fee_account']
        self._fee_currency = JalDB().get_asset_name(JalDB().get_account_currency(self._fee_account))
        self._fee_account_name = JalDB().get_account_name(self._fee_account)
        self._fee = self._data['fee']
        self._label, self._label_color = labels[display_type]
        self._note = self._data['note']
        if self._display_type == Transfer.Outgoing:
            self._reconciled = JalDB().account_reconciliation_timestamp(self._withdrawal_account) >= self._timestamp
        elif self._display_type == Transfer.Incoming:
            self._reconciled = JalDB().account_reconciliation_timestamp(self._deposit_account) >= self._timestamp
        elif self._display_type == Transfer.Fee:
            self._reconciled = JalDB().account_reconciliation_timestamp(self._fee_account) >= self._timestamp
        else:
            assert True, "Unknown transfer type"


    def timestamp(self):
        if self._display_type == Transfer.Incoming:
            return self._deposit_timestamp
        else:
            return self._withdrawal_timestamp

    def account(self):
        if self._display_type == Transfer.Fee:
            return self._fee_account_name
        elif self._display_type == Transfer.Outgoing:
            return self._withdrawal_account_name + " -> " + self._deposit_account_name
        elif self._display_type == Transfer.Incoming:
            return self._deposit_account_name + " <- " + self._withdrawal_account_name
        else:
            assert True, "Unknown transfer type"

    def account_id(self):
        if self._display_type == Transfer.Fee:
            return self._fee_account
        elif self._display_type == Transfer.Outgoing:
            return self._withdrawal_account
        elif self._display_type == Transfer.Incoming:
            return self._deposit_account
        else:
            assert True, "Unknown transfer type"

    def description(self) -> str:
        try:
            rate = self._withdrawal / self._deposit
        except ZeroDivisionError:
            rate = 0
        if self._withdrawal_currency != self._deposit_currency:
            if rate != 0:
                if rate > 1:
                    return self._note + f" [1 {self._deposit_currency} = {rate:.4f} {self._withdrawal_currency}]"
                elif rate < 1:
                    rate = 1 / rate
                    return self._note + f" [{rate:.4f} {self._deposit_currency} = 1 {self._withdrawal_currency}]"
                else:
                    return self._note
            else:
                return self._note + " " + self.tr("Error. Zero rate")
        else:
            return self._note

    def value_change(self) -> list:
        if self._display_type == Transfer.Outgoing:
            return [-self._withdrawal]
        elif self._display_type == Transfer.Incoming:
            return [self._deposit]
        elif self._display_type == Transfer.Fee:
            return [-self._fee]
        else:
            assert True, "Unknown transfer type"

    def value_currency(self) -> str:
        if self._display_type == Transfer.Outgoing:
            return self._withdrawal_currency
        elif self._display_type == Transfer.Incoming:
            return self._deposit_currency
        elif self._display_type == Transfer.Fee:
            return self._fee_currency
        else:
            assert True, "Unknown transfer type"

    def value_total(self) -> str:
        amount = None
        if self._display_type == Transfer.Outgoing:
            amount = self._money_total(self._withdrawal_account)
        elif self._display_type == Transfer.Incoming:
            amount = self._money_total(self._deposit_account)
        elif self._display_type == Transfer.Fee:
            amount = self._money_total(self._fee_account)
        else:
            assert True, "Unknown transfer type"
        if amount is None:
            return super().value_total()
        else:
            return f"{amount:,.2f}"

    def processLedger(self, ledger):
        if self._display_type == Transfer.Outgoing:
            credit_taken = ledger.takeCredit(self, self._withdrawal_account, self._withdrawal)
            ledger.appendTransaction(self, BookAccount.Money, -(self._withdrawal - credit_taken))
            ledger.appendTransaction(self, BookAccount.Transfers, self._withdrawal)
        elif self._display_type == Transfer.Fee:
            credit_taken = ledger.takeCredit(self, self._fee_account, self._fee)
            ledger.appendTransaction(self, BookAccount.Money, -(self._fee - credit_taken))
            ledger.appendTransaction(self, BookAccount.Costs, self._fee,
                                    category=PredefinedCategory.Fees, peer=PredefinedPeer.Financial)
        elif self._display_type == Transfer.Incoming:
            credit_returned = ledger.returnCredit(self, self._deposit_account, self._deposit)
            if credit_returned < self._deposit:
                ledger.appendTransaction(self, BookAccount.Money, self._deposit - credit_returned)
            ledger.appendTransaction(self, BookAccount.Transfers, -self._deposit)
        else:  # TODO implement assets transfer
            assert True, "Unknown transfer type"


# ----------------------------------------------------------------------------------------------------------------------
class CorporateAction(LedgerTransaction):
    Merger = 1
    SpinOff = 2
    SymbolChange = 3
    Split = 4
    Delisting = 5

    def __init__(self, operation_id=None):
        labels = {
            CorporateAction.Merger: ('⭃', CustomColor.Black),
            CorporateAction.SpinOff: ('⎇', CustomColor.DarkGreen),
            CorporateAction.Split: ('ᗕ', CustomColor.Black),
            CorporateAction.SymbolChange:  ('🡘', CustomColor.Black),
            CorporateAction.Delisting: ('✖', CustomColor.DarkRed)
        }
        self.CorpActionNames = {
            CorporateAction.SymbolChange: self.tr("Symbol change {old} -> {new}"),
            CorporateAction.Split: self.tr("Split {old} {before} into {after}"),
            CorporateAction.SpinOff: self.tr("Spin-off {after} {new} from {before} {old}"),
            CorporateAction.Merger: self.tr("Merger {before} {old} into {after} {new}"),
            CorporateAction.Delisting: self.tr("Delisting of {before} {old}")
        }
        super().__init__(operation_id)
        self._table = "corp_actions"
        self._otype = LedgerTransaction.CorporateAction
        self._view_rows = 2
        self._data = readSQL("SELECT a.type, a.timestamp, a.number, a.account_id, "
                             "a.qty, a.asset_id, a.qty_new, a.asset_id_new, a.basis_ratio, a.note "
                             "FROM corp_actions AS a WHERE a.id=:oid", [(":oid", self._oid)], named=True)
        self._subtype = self._data['type']
        self._label, self._label_color = labels[self._subtype]
        self._timestamp = self._data['timestamp']
        self._account = self._data['account_id']
        self._account_name = JalDB().get_account_name(self._account)
        self._account_currency = JalDB().get_asset_name(JalDB().get_account_currency(self._account))
        self._reconciled = JalDB().account_reconciliation_timestamp(self._account) >= self._timestamp
        self._asset = self._data['asset_id']
        self._asset_symbol = JalDB().get_asset_name(self._asset)
        self._asset_name = JalDB().get_asset_name(self._asset, full=True)
        self._qty = self._data['qty']
        self._asset_new = self._data['asset_id_new']
        self._asset_new_symbol = JalDB().get_asset_name(self._asset_new)
        self._asset_name_new = JalDB().get_asset_name(self._asset_new, full=True)
        self._qty_after = self._data['qty_new']
        self._number = self._data['number']
        self._basis = self._data['basis_ratio']
        self._broker = JalDB().get_account_bank(self._account)

    def description(self) -> str:
        basis = 100.0 * self._basis
        text = self.CorpActionNames[self._subtype].format(old=self._asset_name, new=self._asset_name,
                                                          before=self._qty, after=self._qty_after)
        if self._subtype == CorporateAction.SpinOff:
            text += f"; {basis:.2f}% " + self.tr(" cost basis") + "\n" + self._asset_name_new
        return text

    def value_change(self) -> list:
        if self._subtype == CorporateAction.SpinOff:
            return [None, self._qty_after - self._qty]
        elif self._subtype == CorporateAction.Delisting:
            return [-self._qty, None]
        else:
            return [-self._qty, self._qty_after]

    def value_currency(self) -> str:
        if self._subtype == CorporateAction.SpinOff:
            return f" {self._asset_symbol}\n {self._asset_new_symbol}"
        elif self._subtype == CorporateAction.Delisting:
            return f" {self._asset_symbol}\n"
        else:
            return f"\n {self._asset_new_symbol}"

    def value_total(self) -> str:
        if self._subtype == CorporateAction.SpinOff:
            return f"{self._qty:,.2f}\n{self._qty_after:,.2f}"
        elif self._subtype == CorporateAction.Delisting:
            return f"{self._qty_after:,.2f}\n"
        else:
            return f"\n{self._qty_after:,.2f}"

    def processLedger(self, ledger):
        processed_qty = 0
        processed_value = 0
        # Get asset amount accumulated before current operation
        asset_amount = ledger.getAmount(BookAccount.Assets, self._account, self._asset)
        if asset_amount < (self._qty - 2 * Setup.CALC_TOLERANCE):
            raise ValueError(self.tr("Asset amount is not enough for corporate action processing. Date: ")
                             + f"{datetime.utcfromtimestamp(self._timestamp).strftime('%d/%m/%Y %H:%M:%S')}, "
                             + f"Asset amount: {asset_amount}, Operation: {self.dump()}")
        # Get a list of all previous not matched trades or corporate actions
        query = executeSQL("SELECT timestamp, op_type, operation_id, account_id, asset_id, price, remaining_qty "
                           "FROM open_trades "
                           "WHERE account_id=:account_id AND asset_id=:asset_id  AND remaining_qty!=0 "
                           "ORDER BY timestamp, op_type DESC",
                           [(":account_id", self._account), (":asset_id", self._asset)])
        while query.next():
            opening_trade = readSQLrecord(query, named=True)
            next_deal_qty = opening_trade['remaining_qty']
            if (processed_qty + next_deal_qty) > (self._qty + 2 * Setup.CALC_TOLERANCE):  # We can't close all trades with current operation
                raise ValueError(self.tr("Unhandled case: Corporate action covers not full open position. Date: ")
                                 + f"{datetime.utcfromtimestamp(self._timestamp).strftime('%d/%m/%Y %H:%M:%S')}, "
                                 + f"Processed: {processed_qty}, Next: {next_deal_qty}, Operation: {self.dump()}")
            _ = executeSQL("UPDATE open_trades SET remaining_qty=0 "  # FIXME - is it true to have here 0? (i.e. if we have not a full match)
                           "WHERE op_type=:op_type AND operation_id=:id AND asset_id=:asset_id",
                           [(":op_type", opening_trade['op_type']), (":id", opening_trade['operation_id']),
                            (":asset_id", self._asset)])

            # Deal have the same open and close prices as corportate action doesn't create profit, but redistributes value
            _ = executeSQL(
                "INSERT INTO deals(account_id, asset_id, open_op_type, open_op_id, open_timestamp, open_price, "
                " close_op_type, close_op_id, close_timestamp, close_price, qty) "
                "VALUES(:account_id, :asset_id, :open_op_type, :open_op_id, :open_timestamp, :open_price, "
                ":close_op_type, :close_op_id, :close_timestamp, :close_price, :qty)",
                [(":account_id", self._account), (":asset_id", self._asset),
                 (":open_op_type", opening_trade['op_type']), (":open_op_id", opening_trade['operation_id']),
                 (":open_timestamp", opening_trade['timestamp']), (":open_price", opening_trade['price']),
                 (":close_op_type", self._otype), (":close_op_id", self._oid),
                 (":close_timestamp", self._timestamp), (":close_price", opening_trade['price']),
                 (":qty", next_deal_qty)])
            processed_qty += next_deal_qty
            processed_value += (next_deal_qty * opening_trade['price'])
            if processed_qty == self._qty:
                break
        # Asset allocations for different corporate actions:
        # +-----------------+-------+-----+------------+-----------+----------+---------------+
        # |                 | Asset | Qty | cost basis | Asset new | Qty new  | cost basis    |
        # +-----------------+-------+-----+------------+-----------+----------+---------------+
        # | Symbol Change   |   A   |  N  |  100 %     |     B     |    N     |   100%        |
        # | (R-)Split       |   A   |  N  |  100 %     |     A     |    M     |   100%        |
        # | Merger          |   A   |  N  |  100 %     |     B     |    M     |   100%        |
        # | Spin-Off        |   A   |  N  |  100 %     |   A & B   | AxN, BxM | X% & (100-X)% |
        # | Delisting       |   A   |  N  |  100 %     |   None    |   None   |    0 %        |
        # +-----------------+-------+-----+------------+-----------+----------+---------------+
        # Withdraw value with old quantity of old asset as it common for all corporate action
        ledger.appendTransaction(self, BookAccount.Assets, -processed_qty,
                                 asset_id=self._asset, value=-processed_value)
        if self._subtype == CorporateAction.Delisting:  # Map value to costs
            ledger.appendTransaction(self, BookAccount.Costs, processed_value,
                                     category=PredefinedCategory.Profit, peer=self._broker)
            return
        new_value = processed_value
        if self._subtype == CorporateAction.SpinOff:
            new_value = processed_value * (1 - self._basis)
            price = (processed_value - new_value) / self._qty
            # Modify value for old asset
            ledger.appendTransaction(self, BookAccount.Assets, self._qty,
                                     asset_id=self._asset, value=processed_value - new_value)
            _ = executeSQL(
                "INSERT INTO open_trades(timestamp, op_type, operation_id, account_id, asset_id, price, remaining_qty) "
                "VALUES(:timestamp, :type, :operation_id, :account_id, :asset_id, :price, :remaining_qty)",
                [(":timestamp", self._timestamp), (":type", self._otype), (":operation_id", self._oid),
                 (":account_id", self._account), (":asset_id", self._asset), (":price", price),
                 (":remaining_qty", self._qty)])
        # Create value for new asset
        new_price = new_value / self._qty_after
        _ = executeSQL(
            "INSERT INTO open_trades(timestamp, op_type, operation_id, account_id, asset_id, price, remaining_qty) "
            "VALUES(:timestamp, :type, :operation_id, :account_id, :asset_id, :price, :remaining_qty)",
            [(":timestamp", self._timestamp), (":type",self._otype), (":operation_id", self._oid),
             (":account_id", self._account), (":asset_id", self._asset_new), (":price", new_price),
             (":remaining_qty", self._qty_after)])
        ledger.appendTransaction(self, BookAccount.Assets, self._qty_after, asset_id=self._asset_new, value=new_value)
