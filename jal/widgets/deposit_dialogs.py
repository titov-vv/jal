from decimal import Decimal, InvalidOperation

from PySide6.QtCore import Qt, QDateTime
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QDateTimeEdit, QMessageBox)

from jal.constants import PredefinedAgents, PredefinedCategory
from jal.db.db import JalDB
from jal.db.account import JalAccount
from jal.db.common_models import AccountListModel, PeerTreeModel
from jal.db.deposit import JalDepositBox
from jal.db.helpers import now_ts
from jal.db.operations import LedgerTransaction
from jal.widgets.reference_dialogs import AccountListDialog, PeerListDialog
from jal.widgets.reference_selector import ReferenceSelectorWidget


# ----------------------------------------------------------------------------------------------------------------------
# Asks for what a new deposit needs and creates its box together with the transfer that funds it. The box is an
# account of a hidden type, but the word "account" never appears here: the user opens a deposit at a bank, in a
# currency, funded from one of their accounts - the account behind it is an implementation detail.
class NewDepositDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Open a deposit"))
        self.deposit = None
        layout = QFormLayout(self)

        self._name = QLineEdit(self)
        layout.addRow(self.tr("Name"), self._name)
        self._account = ReferenceSelectorWidget(self)
        self._account_model = AccountListModel(self)
        self._account_dialog = AccountListDialog(self)
        self._account.setup_selector(self._account_model, self._account_dialog)
        layout.addRow(self.tr("Funded from"), self._account)
        self._peer = ReferenceSelectorWidget(self)
        self._peer_model = PeerTreeModel(self)
        self._peer_dialog = PeerListDialog(self)
        self._peer.setup_selector(self._peer_model, self._peer_dialog)
        layout.addRow(self.tr("Bank"), self._peer)
        self._amount = QLineEdit(self)
        layout.addRow(self.tr("Amount"), self._amount)
        self._opened = QDateTimeEdit(self)
        self._opened.setTimeSpec(Qt.UTC)
        self._opened.setDisplayFormat("dd/MM/yyyy hh:mm:ss")
        self._opened.setCalendarPopup(True)
        self._opened.setDateTime(QDateTime.currentDateTimeUtc())
        layout.addRow(self.tr("Opened"), self._opened)
        self._ends = QDateTimeEdit(self)
        self._ends.setTimeSpec(Qt.UTC)
        self._ends.setDisplayFormat("dd/MM/yyyy")
        self._ends.setCalendarPopup(True)
        self._ends.setDateTime(QDateTime.currentDateTimeUtc())
        layout.addRow(self.tr("Ends"), self._ends)
        self._rate = QLineEdit(self)
        layout.addRow(self.tr("Interest rate, %"), self._rate)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def accept(self):
        name = self._name.text().strip()
        funding = JalAccount(self._account.selected_id)
        if not name:
            return _warn(self, self.tr("A deposit needs a name"))
        if not funding.id():
            return _warn(self, self.tr("An account isn't chosen to fund the deposit"))
        amount = _decimal(self._amount.text())
        if amount is None or amount <= Decimal('0'):
            return _warn(self, self.tr("The amount put into a deposit should be positive"))
        rate = _decimal(self._rate.text()) or Decimal('0')
        peer = self._peer.selected_id if self._peer.selected_id else funding.organization()
        if JalDB._read("SELECT id FROM accounts WHERE name=:name", [(":name", name)]) is not None:
            return _warn(self, self.tr("An account or a deposit with this name already exists"))
        self.deposit = JalDepositBox.create(name, funding.currency(), peer if peer else PredefinedAgents.Empty,
                                            end_date=self._ends.dateTime().toSecsSinceEpoch(), rate=rate)
        move_money(funding.id(), self.deposit.id(), amount, self._opened.dateTime().toSecsSinceEpoch())
        super().accept()


# ----------------------------------------------------------------------------------------------------------------------
# Moves money in or out of an existing deposit: a Put funds it from an account, a Get (and a Close, which is a Get of
# the whole balance followed by deactivating the box) returns money to one.
class DepositTransferDialog(QDialog):
    PUT, GET, CLOSE = 1, 2, 3
    _TITLES = {PUT: "Put money into the deposit", GET: "Take money out of the deposit", CLOSE: "Close the deposit"}

    def __init__(self, deposit: JalDepositBox, mode: int, parent=None):
        super().__init__(parent)
        self._deposit = deposit
        self._mode = mode
        self.setWindowTitle(self.tr(self._TITLES[mode]))
        layout = QFormLayout(self)

        self._account = ReferenceSelectorWidget(self)
        self._account_model = AccountListModel(self)
        self._account_dialog = AccountListDialog(self)
        self._account.setup_selector(self._account_model, self._account_dialog)
        layout.addRow(self.tr("From account") if mode == self.PUT else self.tr("To account"), self._account)
        self._timestamp = QDateTimeEdit(self)
        self._timestamp.setTimeSpec(Qt.UTC)
        self._timestamp.setDisplayFormat("dd/MM/yyyy hh:mm:ss")
        self._timestamp.setCalendarPopup(True)
        self._timestamp.setDateTime(QDateTime.currentDateTimeUtc())
        layout.addRow(self.tr("Date/Time"), self._timestamp)
        self._amount = QLineEdit(self)
        # Closing returns whatever the deposit holds; the amount is shown but stays editable, because the balance
        # JAL knows may lag behind the bank if an interest payment hasn't been recorded yet.
        if mode == self.CLOSE:
            self._amount.setText(str(deposit.balance(now_ts())))
        layout.addRow(self.tr("Amount"), self._amount)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def accept(self):
        account = JalAccount(self._account.selected_id)
        if not account.id():
            return _warn(self, self.tr("An account isn't chosen"))
        if account.currency() != self._deposit.currency().id():
            return _warn(self, self.tr("The account is kept in another currency than the deposit"))
        amount = _decimal(self._amount.text())
        if amount is None or amount <= Decimal('0'):
            return _warn(self, self.tr("The amount should be positive"))
        timestamp = self._timestamp.dateTime().toSecsSinceEpoch()
        if self._mode == self.PUT:
            move_money(account.id(), self._deposit.id(), amount, timestamp)
        else:
            move_money(self._deposit.id(), account.id(), amount, timestamp)
        if self._mode == self.CLOSE:
            self._deposit.close()
        super().accept()


# ----------------------------------------------------------------------------------------------------------------------
# Records interest credited to a deposit, together with the tax the bank withheld from it. Both are lines of ONE
# income/spending operation on the deposit: the ledger books every line by its own sign, so a positive interest line
# and a negative tax line describe exactly what reached the deposit and what was taken off it.
class DepositInterestDialog(QDialog):
    def __init__(self, deposit: JalDepositBox, parent=None):
        super().__init__(parent)
        self._deposit = deposit
        self.setWindowTitle(self.tr("Interest credited to the deposit"))
        layout = QFormLayout(self)

        self._timestamp = QDateTimeEdit(self)
        self._timestamp.setTimeSpec(Qt.UTC)
        self._timestamp.setDisplayFormat("dd/MM/yyyy hh:mm:ss")
        self._timestamp.setCalendarPopup(True)
        self._timestamp.setDateTime(QDateTime.currentDateTimeUtc())
        layout.addRow(self.tr("Date/Time"), self._timestamp)
        self._interest = QLineEdit(self)
        layout.addRow(self.tr("Interest"), self._interest)
        self._tax = QLineEdit(self)
        layout.addRow(self.tr("Tax withheld"), self._tax)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def accept(self):
        interest = _decimal(self._interest.text())
        if interest is None or interest <= Decimal('0'):
            return _warn(self, self.tr("The interest should be positive"))
        tax = _decimal(self._tax.text()) or Decimal('0')
        if tax < Decimal('0'):
            return _warn(self, self.tr("The tax withheld can't be negative"))
        if not self._deposit.organization():
            return _warn(self, self.tr("The bank isn't set for this deposit"))
        record_interest(self._deposit, self._timestamp.dateTime().toSecsSinceEpoch(), interest, tax)
        super().accept()


# ----------------------------------------------------------------------------------------------------------------------
# Creates the money transfer that a deposit action consists of. Both accounts are kept in the same currency (that is
# checked before the call), so the amount withdrawn equals the amount deposited.
def move_money(from_account_id: int, to_account_id: int, amount: Decimal, timestamp: int) -> None:
    LedgerTransaction.create_new(LedgerTransaction.Transfer,
                                 {"withdrawal_timestamp": timestamp, "withdrawal_account": from_account_id,
                                  "withdrawal": amount, "deposit_timestamp": timestamp,
                                  "deposit_account": to_account_id, "deposit": amount})


# Creates the income/spending operation that credits interest to a deposit (and withholds tax from it, if any)
def record_interest(deposit: JalDepositBox, timestamp: int, interest: Decimal, tax: Decimal) -> None:
    lines = [{"category_id": PredefinedCategory.Interest, "amount": interest}]
    if tax > Decimal('0'):
        lines.append({"category_id": PredefinedCategory.Taxes, "amount": -tax})
    LedgerTransaction.create_new(LedgerTransaction.IncomeSpending,
                                 {"timestamp": timestamp, "account_id": deposit.id(),
                                  "peer_id": deposit.organization(), "lines": lines})


def _decimal(text: str):
    try:
        return Decimal(text.strip().replace(',', '.'))
    except (InvalidOperation, AttributeError):
        return None


def _warn(dialog, text) -> None:
    QMessageBox().warning(dialog, dialog.tr("Incomplete data"), text, QMessageBox.Ok)
