from decimal import Decimal
from functools import partial

from PySide6.QtCore import Qt, Slot, QObject, QDateTime, QAbstractTableModel
from PySide6.QtGui import QFont

from jal.db.deposit import JalDepositBox
from jal.db.helpers import localize_decimal
from jal.db.operations import LedgerTransaction
from jal.db.peer import JalPeer
from jal.reports.reports import Reports
from jal.ui.reports.ui_deposits_report import Ui_DepositsReportWidget
from jal.widgets.delegates import FloatDelegate, TimestampDelegate
from jal.widgets.deposit_dialogs import NewDepositDialog, DepositTransferDialog, DepositInterestDialog
from jal.widgets.icons import JalIcon
from jal.widgets.mdi import MdiWidget

JAL_REPORT_CLASS = "DepositsReport"


# ----------------------------------------------------------------------------------------------------------------------
# The deposits that were open at the report date, one row each.
class DepositsListModel(QAbstractTableModel):
    def __init__(self, parent_view):
        super().__init__(parent_view)
        self._columns = [self.tr("Name"), self.tr("Bank"), self.tr("Currency"), self.tr("Opened"), self.tr("Ends"),
                         self.tr("Rate, %"), self.tr("Balance"), self.tr("Interest")]
        self._timestamp = 0
        self._view = parent_view
        self._data = []
        self._float_delegate = None
        self._rate_delegate = None
        self._timestamp_delegate = None
        self._balance_total = Decimal('0')
        self._interest_total = Decimal('0')

    def rowCount(self, parent=None):
        return len(self._data)

    def columnCount(self, parent=None):
        return len(self._columns)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._columns[section]
        return None

    def headerWidth(self, section):
        return self._view.horizontalHeader().sectionSize(section)

    def data(self, index, role=Qt.DisplayRole, field=''):
        if role == Qt.DisplayRole:
            return self.data_text(self._data[index.row()], index.column())

    def data_text(self, deposit: JalDepositBox, column: int):
        if column == 0:
            return deposit.name()
        if column == 1:
            return JalPeer(deposit.organization()).name()
        if column == 2:
            return deposit.currency().symbol()
        if column == 3:
            return deposit.opened_at()
        if column == 4:
            return deposit.end_date()
        if column == 5:
            return deposit.rate()
        if column == 6:
            return deposit.balance(self._timestamp)
        if column == 7:
            return deposit.accrued_interest(self._timestamp)
        return ''

    def footerData(self, section: int, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if section == 0:
                return self.tr("Total")
            if section == 6:
                return localize_decimal(self._balance_total, precision=2)
            if section == 7:
                return localize_decimal(self._interest_total, precision=2)
        elif role == Qt.FontRole:
            font = QFont()
            font.setBold(True)
            return font
        elif role == Qt.TextAlignmentRole:
            return Qt.AlignRight | Qt.AlignVCenter if section > 4 else Qt.AlignLeft | Qt.AlignVCenter
        return None

    # The deposit shown in a given row, or None if the row doesn't point at one. Totals mix currencies, exactly as
    # the term deposits report always did - they are a rough sum, not a converted one.
    def deposit(self, index) -> JalDepositBox:
        if not index.isValid() or index.row() >= len(self._data):
            return None
        return self._data[index.row()]

    def updateView(self, timestamp=None):
        if timestamp is not None:
            self._timestamp = timestamp
        self.prepareData()
        self.configureView()

    def prepareData(self):
        self.beginResetModel()
        self._data = JalDepositBox.get_deposits(self._timestamp)
        self._balance_total = sum([x.balance(self._timestamp) for x in self._data], Decimal('0'))
        self._interest_total = sum([x.accrued_interest(self._timestamp) for x in self._data], Decimal('0'))
        self.endResetModel()

    def configureView(self):
        font = self._view.horizontalHeader().font()
        font.setBold(True)
        self._view.horizontalHeader().setFont(font)
        self._float_delegate = FloatDelegate(2, allow_tail=False)
        self._rate_delegate = FloatDelegate(2, allow_tail=False, empty_zero=True)
        self._timestamp_delegate = TimestampDelegate(display_format='%d/%m/%Y')
        self._view.setItemDelegateForColumn(3, self._timestamp_delegate)
        self._view.setItemDelegateForColumn(4, self._timestamp_delegate)
        self._view.setItemDelegateForColumn(5, self._rate_delegate)
        self._view.setItemDelegateForColumn(6, self._float_delegate)
        self._view.setItemDelegateForColumn(7, self._float_delegate)
        self._view.setColumnWidth(0, 200)
        self._view.setColumnWidth(1, 150)
        self._view.setColumnWidth(2, 80)
        for column in (3, 4):
            self._view.setColumnWidth(column, self._view.fontMetrics().horizontalAdvance("00/00/0000") * 1.1)
        for column in (5, 6, 7):
            self._view.setColumnWidth(column, 120)


# ----------------------------------------------------------------------------------------------------------------------
# Everything that happened to one deposit, with the balance it left behind after each step.
class DepositDetailsModel(QAbstractTableModel):
    def __init__(self, parent_view):
        super().__init__(parent_view)
        self._columns = [self.tr("Date/Time"), self.tr("Operation"), self.tr("Amount"), self.tr("Balance")]
        self._view = parent_view
        self._data = []
        self._timestamp = 0
        self._float_delegate = None
        self._timestamp_delegate = None

    def rowCount(self, parent=None):
        return len(self._data)

    def columnCount(self, parent=None):
        return len(self._columns)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._columns[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        record = self._data[index.row()]
        if index.column() == 0:
            return record['timestamp']
        if index.column() == 1:
            return record['operation']
        if index.column() == 2:
            return record['amount']
        if index.column() == 3:
            return record['balance']
        return ''

    def setDeposit(self, deposit: JalDepositBox, timestamp: int):
        self.beginResetModel()
        self._timestamp = timestamp
        self._data = []
        if deposit is not None:
            for record in deposit.details(timestamp):
                record['operation'] = self._operation_name(record['otype'], record['oid'])
                self._data.append(record)
        self.endResetModel()
        self.configureView()

    # Name of the operation a ledger row came from. An operation that was deleted since the ledger was built has
    # nothing to name it, and a details table must not raise over that.
    @staticmethod
    def _operation_name(otype: int, oid: int) -> str:
        try:
            return LedgerTransaction().get_operation(otype, oid).name()
        except (IndexError, ValueError):
            return ''

    def configureView(self):
        font = self._view.horizontalHeader().font()
        font.setBold(True)
        self._view.horizontalHeader().setFont(font)
        self._float_delegate = FloatDelegate(2, allow_tail=False)
        self._timestamp_delegate = TimestampDelegate()
        self._view.setItemDelegateForColumn(0, self._timestamp_delegate)
        self._view.setItemDelegateForColumn(2, self._float_delegate)
        self._view.setItemDelegateForColumn(3, self._float_delegate)
        self._view.setColumnWidth(0, self._view.fontMetrics().horizontalAdvance("00/00/0000 00:00:00") * 1.25)
        self._view.setColumnWidth(1, 200)
        self._view.setColumnWidth(2, 120)
        self._view.setColumnWidth(3, 120)


# ----------------------------------------------------------------------------------------------------------------------
class DepositsReport(QObject):
    def __init__(self):
        super().__init__()
        self.name = self.tr("Deposits")
        self.window_class = "DepositsReportWindow"


# ----------------------------------------------------------------------------------------------------------------------
# Manages term deposits: what is open, what each of them did, and the actions that record a new one, a top-up, a
# withdrawal, credited interest or a closure. Every action writes ordinary operations behind the scenes (transfers
# between the funding account and the deposit, an income/spending for the interest) - see jal.widgets.deposit_dialogs.
class DepositsReportWindow(MdiWidget):
    def __init__(self, parent: Reports, settings: dict = None):
        super().__init__(parent.mdi_area())
        self.ui = Ui_DepositsReportWidget()
        self.ui.setupUi(self)
        self._parent = parent
        self.name = self.tr("Deposits")

        self.deposits_model = DepositsListModel(self.ui.ReportTableView)
        self.ui.ReportTableView.setModel(self.deposits_model)
        self.details_model = DepositDetailsModel(self.ui.DetailsTableView)
        self.ui.DetailsTableView.setModel(self.details_model)

        self.ui.NewButton.setIcon(JalIcon[JalIcon.DEPOSIT_ACCOUNT])
        self.ui.PutButton.setIcon(JalIcon[JalIcon.DEPOSIT_OPEN])
        self.ui.GetButton.setIcon(JalIcon[JalIcon.DEPOSIT_CLOSE])
        self.ui.InterestButton.setIcon(JalIcon[JalIcon.INTEREST])
        self.ui.CloseButton.setIcon(JalIcon[JalIcon.OK])

        self.connect_signals_and_slots()

        current_time = QDateTime.currentDateTime()
        current_time.setTimeSpec(Qt.UTC)  # We use UTC everywhere so need to force TZ info
        self.ui.DepositsDate.setDateTime(current_time)
        self.updateReport()

    def connect_signals_and_slots(self):
        self.ui.DepositsDate.dateChanged.connect(self.updateReport)
        self.ui.ReportTableView.selectionModel().selectionChanged.connect(self.onDepositSelected)
        self.ui.NewButton.pressed.connect(self.onNewDeposit)
        self.ui.PutButton.pressed.connect(partial(self.onTransfer, DepositTransferDialog.PUT))
        self.ui.GetButton.pressed.connect(partial(self.onTransfer, DepositTransferDialog.GET))
        self.ui.CloseButton.pressed.connect(partial(self.onTransfer, DepositTransferDialog.CLOSE))
        self.ui.InterestButton.pressed.connect(self.onInterest)
        self.ui.SaveButton.pressed.connect(
            partial(self._parent.save_report, self.name, self.ui.ReportTableView.model()))

    def _timestamp(self) -> int:
        return self.ui.DepositsDate.date().endOfDay(Qt.UTC).toSecsSinceEpoch()

    # The deposit the actions apply to, or None when nothing is selected
    def _selected(self) -> JalDepositBox:
        indexes = self.ui.ReportTableView.selectionModel().selectedRows()
        return self.deposits_model.deposit(indexes[0]) if indexes else None

    @Slot()
    def updateReport(self):
        self.deposits_model.updateView(timestamp=self._timestamp())
        self.details_model.setDeposit(self._selected(), self._timestamp())

    @Slot()
    def onDepositSelected(self, _selected=None, _deselected=None):
        self.details_model.setDeposit(self._selected(), self._timestamp())

    # An action writes real operations, so the ledger has to catch up before the figures shown here are true again.
    # Reports is constructed by the main window, which owns the Ledger - the same one every operation editor uses.
    def _after_change(self):
        self._parent.parent.ledger.rebuild()
        self.updateReport()

    @Slot()
    def onNewDeposit(self):
        if NewDepositDialog(parent=self).exec():
            self._after_change()

    @Slot()
    def onTransfer(self, mode):
        deposit = self._selected()
        if deposit is None:
            return
        if DepositTransferDialog(deposit, mode, parent=self).exec():
            self._after_change()

    @Slot()
    def onInterest(self):
        deposit = self._selected()
        if deposit is None:
            return
        if DepositInterestDialog(deposit, parent=self).exec():
            self._after_change()
