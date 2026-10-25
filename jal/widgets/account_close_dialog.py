from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QDateTimeEdit, QPlainTextEdit

from jal.constants import PredefinedAgents
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.clock import local_zone, now_dt
from jal.db.helpers import localize_amount
from jal.db.ledger import Ledger
from jal.db.operations import LedgerTransaction
from jal.db.peer import JalPeer
from jal.db.symbol import JalSymbol
from jal.widgets.helpers import DateFormat


# ----------------------------------------------------------------------------------------------------------------------
# Closes an account that its provider closed: shows what JalAccount.closure_plan() would write off at the chosen
# moment, or why it can't be done, and on Ok writes it off and rebuilds the ledger.
class AccountCloseDialog(QDialog):
    def __init__(self, account_id: int, parent=None):
        super().__init__(parent)
        self._account = JalAccount(account_id)
        self.setWindowTitle(self.tr("Close account"))
        layout = QFormLayout(self)

        layout.addRow(self.tr("Account"), QLabel(self._account.name(), self))
        self._closed = QDateTimeEdit(self)
        self._closed.setTimeZone(local_zone())
        self._closed.setDisplayFormat(DateFormat.datetime(qt=True))
        self._closed.setCalendarPopup(True)
        self._closed.setDateTime(now_dt())
        layout.addRow(self.tr("Closed on"), self._closed)
        self._note = QLineEdit(self._default_note(), self)
        layout.addRow(self.tr("Note"), self._note)
        self._plan = QPlainTextEdit(self)
        self._plan.setReadOnly(True)
        layout.addRow(self.tr("Write-off"), self._plan)

        self._buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addRow(self._buttons)

        Ledger().rebuild()   # the plan is read from the ledger
        self._closed.dateTimeChanged.connect(self._show_plan)
        self._show_plan()

    def _default_note(self) -> str:
        if self._account.organization() == PredefinedAgents.Empty:
            return self.tr("Account closed")
        return self.tr("Account closed by ") + JalPeer(self._account.organization()).name()

    def _timestamp(self) -> int:
        return self._closed.dateTime().toSecsSinceEpoch()

    def _show_plan(self):
        refusals, records = self._account.closure_plan(self._timestamp())
        if refusals:
            text = self.tr("The account can't be closed:") + "\n" + "\n".join(refusals)
        elif records:
            text = "\n".join(self._describe(otype, data) for otype, data in records)
        else:
            text = self.tr("Nothing is left to write off, the account will only be set Closed")
        self._plan.setPlainText(text)
        self._buttons.button(QDialogButtonBox.Ok).setEnabled(not refusals)

    def _describe(self, otype: int, data: dict) -> str:
        if otype == LedgerTransaction.IncomeSpending:
            amount = -data['lines'][0]['amount']
            return self.tr("Cash to Losses: ") + f"{localize_amount(amount)} {JalAsset(self._account.currency()).symbol()}"
        return self.tr("Asset to Losses: ") + f"{localize_amount(data['qty'])} {JalSymbol(data['symbol_id']).symbol()}"

    def accept(self):
        timestamp = self._timestamp()
        if self._account.close(timestamp, self._note.text().strip()):
            self._show_plan()   # something changed since the plan was shown
            return
        Ledger().rebuild(from_timestamp=timestamp)
        super().accept()
