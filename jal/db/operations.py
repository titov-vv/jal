from PySide6.QtWidgets import QApplication
from jal.constants import BookAccount, CustomColor
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

    def label(self):
        return self._label

    def label_color(self):
        return self._label_color

    def timestamp(self):
        return self._timestamp

    def account(self):
        return self._account_name

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


# ----------------------------------------------------------------------------------------------------------------------
class IncomeSpending(LedgerTransaction):
    def __init__(self, operation_id=None):
        super().__init__(operation_id)
        self._otype = LedgerTransaction.IncomeSpending
        self._table = "actions"
        data = readSQL("SELECT a.timestamp, a.account_id, a.peer_id, p.name AS peer, a.alt_currency_id AS currency "
                       "FROM actions AS a LEFT JOIN agents AS p ON a.peer_id = p.id WHERE a.id=:oid",
                       [(":oid", self._oid)], named=True)
        self._timestamp = data['timestamp']
        self._account = data['account_id']
        self._account_name = JalDB().get_account_name(self._account)
        self._account_currency = JalDB().get_asset_name(JalDB().get_account_currency(self._account))
        self._reconciled = JalDB().account_reconciliation_timestamp(self._account) >= self._timestamp
        self._peer = data['peer']
        self._currency = data['currency']
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
        data = readSQL("SELECT d.type, d.timestamp, d.number, d.account_id, d.amount, d.asset_id, d.tax, "
                       "l.amount_acc AS t_qty, d.note AS note, c.name AS country "
                       "FROM dividends AS d "
                       "LEFT JOIN assets AS a ON d.asset_id = a.id "
                       "LEFT JOIN countries AS c ON a.country_id = c.id "
                       "LEFT JOIN ledger_totals AS l ON l.op_type=d.op_type AND l.operation_id=d.id "
                       "AND l.book_account = :book_assets WHERE d.id=:oid",
                       [(":book_assets", BookAccount.Assets), (":oid", self._oid)], named=True)
        self._view_rows = 2
        self._subtype = data['type']
        self._label, self._label_color = labels[self._subtype]
        self._timestamp = data['timestamp']
        self._account = data['account_id']
        self._account_name = JalDB().get_account_name(self._account)
        self._account_currency = JalDB().get_asset_name(JalDB().get_account_currency(self._account))
        self._reconciled = JalDB().account_reconciliation_timestamp(self._account) >= self._timestamp
        self._asset = data['asset_id']
        self._asset_symbol = JalDB().get_asset_name(self._asset)
        self._asset_name = JalDB().get_asset_name(self._asset, full=True)
        self._number = data['number']
        self._amount = data['amount']
        self._tax = data ['tax']
        self._note = data['note']

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


# ----------------------------------------------------------------------------------------------------------------------
class Trade(LedgerTransaction):
    def __init__(self, operation_id=None):
        super().__init__(operation_id)
        self._table = "trades"
        self._otype = LedgerTransaction.Trade
        data = readSQL("SELECT t.timestamp, t.number, t.account_id, t.asset_id, t.qty, t.price AS price, t.fee, t.note "
                       "FROM trades AS t WHERE t.id=:oid", [(":oid", self._oid)], named=True)
        self._view_rows = 2
        self._label, self._label_color = ('S', CustomColor.DarkRed) if data['qty'] < 0 else ('B', CustomColor.DarkGreen)
        self._timestamp = data['timestamp']
        self._account = JalDB().get_account_name(data['account_id'])
        self._account = data['account_id']
        self._account_name = JalDB().get_account_name(self._account)
        self._account_currency = JalDB().get_asset_name(JalDB().get_account_currency(self._account))
        self._reconciled = JalDB().account_reconciliation_timestamp(self._account) >= self._timestamp
        self._asset = data['asset_id']
        self._asset_symbol = JalDB().get_asset_name(self._asset)
        self._asset_name = JalDB().get_asset_name(self._asset, full=True)
        self._number = data['number']
        self._qty = data['qty']
        self._price = data['price']
        self._fee = data['fee']
        self._note = data['note']

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


# ----------------------------------------------------------------------------------------------------------------------
class Transfer(LedgerTransaction):
    Fee = 0
    Outgoing = -1
    Incoming = 1

    def __init__(self, operation_id=None, display_type=None):
        labels = {
            Transfer.Outgoing: ('<', CustomColor.DarkBlue),
            Transfer.Incoming: ('>', CustomColor.DarkBlue),
            Transfer.Fee: ('=', CustomColor.DarkRed),
        }
        super().__init__(operation_id)
        self.table = "transfers"
        self._otype = LedgerTransaction.Transfer
        data = readSQL("SELECT t.withdrawal_timestamp, t.withdrawal_account, t.withdrawal, "
                       "t.deposit_timestamp, t.deposit_account, t.deposit, t.fee_account, t.fee, t.asset, t.note "
                       "FROM transfers AS t WHERE t.id=:oid", [(":oid", self._oid)], named=True)
        self._display_type = display_type
        self._withdrawal_account = data['withdrawal_account']
        self._withdrawal_account_name = JalDB().get_account_name(self._withdrawal_account)
        self._withdrawal_timestamp = data['withdrawal_timestamp']
        self._withdrawal = data['withdrawal']
        self._withdrawal_currency = JalDB().get_asset_name(JalDB().get_account_currency(self._withdrawal_account))
        self._deposit_account = data['deposit_account']
        self._deposit_account_name = JalDB().get_account_name(self._deposit_account)
        self._deposit = data['deposit']
        self._deposit_currency = JalDB().get_asset_name(JalDB().get_account_currency(self._deposit_account))
        self._deposit_timestamp = data['deposit_timestamp']
        self._fee_account = data['fee_account']
        self._fee_currency = JalDB().get_asset_name(JalDB().get_account_currency(self._fee_account))
        self._fee_account_name = JalDB().get_account_name(self._fee_account)
        self._fee = data['fee']
        self._label, self._label_color = labels[display_type]
        self._note = data['note']
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


# ----------------------------------------------------------------------------------------------------------------------
class CorporateAction(LedgerTransaction):
    Merger = 1
    SpinOff = 2
    SymbolChange = 3
    Split = 4

    def __init__(self, operation_id=None):
        labels = {
            CorporateAction.Merger: ('⭃', CustomColor.Black),
            CorporateAction.SpinOff: ('⎇', CustomColor.DarkGreen),
            CorporateAction.Split: ('ᗕ', CustomColor.Black),
            CorporateAction.SymbolChange:  ('🡘', CustomColor.Black)
        }
        self.CorpActionNames = {
            CorporateAction.SymbolChange: self.tr("Symbol change {old} -> {new}"),
            CorporateAction.Split: self.tr("Split {old} {before} into {after}"),
            CorporateAction.SpinOff: self.tr("Spin-off {after} {new} from {before} {old}"),
            CorporateAction.Merger: self.tr("Merger {before} {old} into {after} {new}")
        }
        super().__init__(operation_id)
        self._table = "corp_actions"
        self._otype = LedgerTransaction.CorporateAction
        data = readSQL("SELECT a.type, a.timestamp, a.number, a.account_id, "
                       "a.qty, a.asset_id, a.qty_new, a.asset_id_new, a.basis_ratio, a.note "
                       "FROM corp_actions AS a WHERE a.id=:oid", [(":oid", self._oid)], named=True)
        self._view_rows = 2
        self._subtype = data['type']
        self._label, self._label_color = labels[self._subtype]
        self._timestamp = data['timestamp']
        self._account = data['account_id']
        self._account_name = JalDB().get_account_name(self._account)
        self._account_currency = JalDB().get_asset_name(JalDB().get_account_currency(self._account))
        self._reconciled = JalDB().account_reconciliation_timestamp(self._account) >= self._timestamp
        self._asset = data['asset_id']
        self._asset_symbol = JalDB().get_asset_name(self._asset)
        self._asset_name = JalDB().get_asset_name(self._asset, full=True)
        self._qty = data['qty']
        self._asset_new = data['asset_id_new']
        self._asset_new_symbol = JalDB().get_asset_name(self._asset_new)
        self._asset_name_new = JalDB().get_asset_name(self._asset_new, full=True)
        self._qty_after = data['qty_new']
        self._number = data['number']
        self._basis = data['basis_ratio']

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
        else:
            return [-self._qty, self._qty_after]

    def value_currency(self) -> str:
        if self._subtype == CorporateAction.SpinOff:
            return f" {self._asset_symbol}\n {self._asset_new_symbol}"
        else:
            return f"\n {self._asset_new_symbol}"

    def value_total(self) -> str:
        if self._subtype == CorporateAction.SpinOff:
            return f"{self._qty:,.2f}\n{self._qty_after:,.2f}"
        else:
            return f"\n{self._qty_after:,.2f}"
