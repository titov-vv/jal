from decimal import Decimal
from functools import partial
from PySide6.QtCore import Qt, Slot, QObject, QAbstractTableModel
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHeaderView
from jal.reports.reports import Reports
from jal.db.operations import AssetPayment
from jal.db.helpers import localize_decimal
from jal.ui.reports.ui_assets_payments_report import Ui_AssetsPaymentsReportWidget
from jal.widgets.delegates import FloatDelegate
from jal.widgets.mdi import MdiWidget
from jal.widgets.helpers import ts2dt

JAL_REPORT_CLASS = "AssetsPaymentsReport"

# ----------------------------------------------------------------------------------------------------------------------
class AssetsPaymentsModel(QAbstractTableModel):
    def __init__(self, parent_view):
        super().__init__(parent_view)
        self._columns = [self.tr("Date"), self.tr("Symbol"), self.tr("Asset"), self.tr("Type"),
                         self.tr("Amount"), self.tr("Tax"), self.tr("Note")]
        self._types = [self.tr("N/A"), self.tr("Dividend"), self.tr("Bond Interest"), self.tr("Stock Dividend"),
                       self.tr("Stock Vesting"), self.tr("Bond Amortization")]
        self._view = parent_view
        self._data = []
        self._account_id = 0
        self._begin = self._end = 0
        self._float_delegate = None
        self._total = Decimal('0')
        self._total_tax = Decimal('0')

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
            dividend = self._data[index.row()]
            return self.data_text(dividend, index.column())

    def data_text(self, dividend, column):
        if column == 0:
            return ts2dt(dividend.timestamp())
        if column == 1:
            return dividend.asset().symbol()
        if column == 2:
            return dividend.asset().name()
        if column == 3:
            return self._types[dividend.subtype()]
        if column == 4:
            return dividend.amount()
        if column == 5:
            return dividend.tax()
        if column == 6:
            return dividend.note()
        return ''

    def footerData(self, section: int, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if section == 4:
                return localize_decimal(self._total, precision=2)
            if section == 5:
                return localize_decimal(self._total_tax, precision=2)
        elif role == Qt.FontRole:
            font = QFont()
            font.setBold(True)
            return font
        elif role == Qt.TextAlignmentRole:
            if section == 4 or section == 5:
                return Qt.AlignRight | Qt.AlignVCenter
            else:
                return Qt.AlignLeft | Qt.AlignVCenter
        return None

    def updateView(self, account_id, dates):
        update = False
        if self._account_id != account_id:
            self._account_id = account_id
            update = True
        if self._begin != dates[0]:
            self._begin = dates[0]
            update = True
        if self._end != dates[1]:
            self._end = dates[1]
            update = True
        if update:
            self.prepareData()
            self.configureView()

    def prepareData(self):
        self.beginResetModel()
        dividends = AssetPayment.get_list(self._account_id)
        self._data = [x for x in dividends if self._begin <= x.timestamp() <= self._end]
        self._total = sum([x.amount() for x in self._data])
        self._total_tax = sum([x.tax() for x in self._data])
        self.endResetModel()

    def configureView(self):
        font = self._view.horizontalHeader().font()
        font.setBold(True)
        self._view.horizontalHeader().setFont(font)
        self._float_delegate = FloatDelegate(2, allow_tail=False)
        self._view.setItemDelegateForColumn(4, self._float_delegate)
        self._view.setItemDelegateForColumn(5, self._float_delegate)
        self._view.setColumnWidth(0, self._view.fontMetrics().horizontalAdvance("00/00/0000 00:00:00") * 1.1)
        self._view.setColumnWidth(2, 200)
        if self._view.horizontalHeader().count():  # Next line crashes if there are no columns (count==0)
            self._view.horizontalHeader().setSectionResizeMode(6, QHeaderView.Stretch)

# ----------------------------------------------------------------------------------------------------------------------
class AssetsPaymentsReport(QObject):
    def __init__(self):
        super().__init__()
        self.name = self.tr("Assets' Payments")
        self.window_class = "AssetsPaymentsReportWindow"

# ----------------------------------------------------------------------------------------------------------------------
class AssetsPaymentsReportWindow(MdiWidget):
    def __init__(self, parent: Reports, settings: dict = None):
        super().__init__(parent.mdi_area())
        self.ui = Ui_AssetsPaymentsReportWidget()
        self.ui.setupUi(self)
        self._parent = parent
        self.name = self.tr("Assets' Payments")

        self.payments_model = AssetsPaymentsModel(self.ui.ReportTableView)
        self.ui.ReportTableView.setModel(self.payments_model)

        self.connect_signals_and_slots()

    def connect_signals_and_slots(self):
        self.ui.ReportAccountButton.changed.connect(self.updateReport)
        self.ui.ReportRange.changed.connect(self.updateReport)
        self.ui.SaveButton.pressed.connect(partial(self._parent.save_report, self.name, self.ui.ReportTableView.model()))

    @Slot()
    def updateReport(self):
        self.ui.ReportTableView.model().updateView(account_id=self.ui.ReportAccountButton.account_id,
                                                   dates=self.ui.ReportRange.getRange())
