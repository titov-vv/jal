from decimal import Decimal
from functools import partial
from PySide6.QtCore import Qt, Slot, QObject, QDateTime, QAbstractTableModel
from PySide6.QtGui import QFont
from jal.reports.reports import Reports
from jal.db.deposit import JalDeposit
from jal.db.helpers import localize_decimal
from jal.ui.reports.ui_term_deposits_report import Ui_TermDepositsReportWidget
from jal.widgets.delegates import FloatDelegate, TimestampDelegate
from jal.widgets.mdi import MdiWidget

JAL_REPORT_CLASS = "TermDepositsReport"


# ----------------------------------------------------------------------------------------------------------------------
class DepositsListModel(QAbstractTableModel):
    def __init__(self, parent_view):
        super().__init__(parent_view)
        self._columns = [self.tr("Name"), self.tr("Start Date"), self.tr("End Date"), self.tr("Currency"),
                         self.tr("Initial amount"), self.tr("Accrued Interest"), self.tr("Planned End Value")]
        self._timestamp = 0
        self._view = parent_view
        self._data = []
        self._float_delegate = None
        self._timestamp_delegate = None
        self._initial_total = Decimal('0')
        self._accrued_total = Decimal('0')
        self._planned_total = Decimal('0')

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
            deposit = self._data[index.row()]
            return self.data_text(deposit, index.column())

    def data_text(self, deposit: JalDeposit, column: int):
        if column == 0:
            return deposit.name()
        if column == 1:
            return deposit.start_date()
        if column == 2:
            return deposit.end_date()
        if column == 3:
            return deposit.currency().symbol()
        if column == 4:
            return deposit.open_amount()
        if column == 5:
            return deposit.accrued_interest(self._timestamp)
        if column == 6:
            return deposit.close_amount()
        return ''

    def footerData(self, section: int, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if section ==0:
                return self.tr("Total")
            if section == 4:
                return localize_decimal(self._initial_total, precision=2)
            if section == 5:
                return localize_decimal(self._accrued_total, precision=2)
            if section == 6:
                return localize_decimal(self._planned_total, precision=2)
        elif role == Qt.FontRole:
            font = QFont()
            font.setBold(True)
            return font
        elif role == Qt.TextAlignmentRole:
            if section > 3:
                return Qt.AlignRight | Qt.AlignVCenter
            else:
                return Qt.AlignLeft | Qt.AlignVCenter
        return None

    def updateView(self, timestamp):
        if self._timestamp != timestamp:
            self._timestamp = timestamp
            self.prepareData()
            self.configureView()

    def prepareData(self):
        self.beginResetModel()
        self._data = JalDeposit.get_term_deposits(self._timestamp)
        self._initial_total = sum([x.open_amount() for x in self._data])
        self._accrued_total = sum([x.accrued_interest(self._timestamp) for x in self._data])
        self._planned_total = sum([x.close_amount() for x in self._data])
        self.endResetModel()

    def configureView(self):
        font = self._view.horizontalHeader().font()
        font.setBold(True)
        self._view.horizontalHeader().setFont(font)
        self._float_delegate = FloatDelegate(2, allow_tail=False)
        self._timestamp_delegate = TimestampDelegate(display_format='%d/%m/%Y')
        self._view.setItemDelegateForColumn(1, self._timestamp_delegate)
        self._view.setItemDelegateForColumn(2, self._timestamp_delegate)
        self._view.setItemDelegateForColumn(4, self._float_delegate)
        self._view.setItemDelegateForColumn(5, self._float_delegate)
        self._view.setItemDelegateForColumn(6, self._float_delegate)
        self._view.setColumnWidth(0, 200)
        self._view.setColumnWidth(1, self._view.fontMetrics().horizontalAdvance("00/00/0000") * 1.1)
        self._view.setColumnWidth(2, self._view.fontMetrics().horizontalAdvance("00/00/0000") * 1.1)
        self._view.setColumnWidth(3, 100)
        self._view.setColumnWidth(4, 150)
        self._view.setColumnWidth(5, 150)
        self._view.setColumnWidth(6, 150)

# ----------------------------------------------------------------------------------------------------------------------
class TermDepositsReport(QObject):
    def __init__(self):
        super().__init__()
        self.name = self.tr("Term deposits")
        self.window_class = "TermDepositsReportWindow"

# ----------------------------------------------------------------------------------------------------------------------
class TermDepositsReportWindow(MdiWidget):
    def __init__(self, parent: Reports, settings: dict = None):
        super().__init__(parent.mdi_area())
        self.ui = Ui_TermDepositsReportWidget()
        self.ui.setupUi(self)
        self._parent = parent
        self.name = self.tr("Term deposits")

        self.payments_model = DepositsListModel(self.ui.ReportTableView)
        self.ui.ReportTableView.setModel(self.payments_model)

        self.connect_signals_and_slots()

        current_time = QDateTime.currentDateTime()
        current_time.setTimeSpec(Qt.UTC)  # We use UTC everywhere so need to force TZ info
        self.ui.DepositsDate.setDateTime(current_time)

    def connect_signals_and_slots(self):
        self.ui.DepositsDate.dateChanged.connect(self.updateReport)
        self.ui.SaveButton.pressed.connect(partial(self._parent.save_report, self.name, self.ui.ReportTableView.model()))

    @Slot()
    def updateReport(self):
        self.ui.ReportTableView.model().updateView(timestamp=self.ui.DepositsDate.date().endOfDay(Qt.UTC).toSecsSinceEpoch())
