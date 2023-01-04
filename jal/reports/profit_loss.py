from decimal import Decimal
from PySide6.QtCore import Qt, Slot, QObject, QAbstractTableModel
from jal.ui.reports.ui_profit_loss_report import Ui_ProfitLossReportWidget
from jal.reports.reports import Reports
from jal.db.account import JalAccount
from jal.constants import BookAccount, PredefinedCategory
from jal.widgets.helpers import month_list
from jal.widgets.delegates import FloatDelegate
from jal.widgets.mdi import MdiWidget

JAL_REPORT_CLASS = "ProfitLossReport"
# TODO This report should be improved with more relevant data columns and tree structure for grouping by years


#-----------------------------------------------------------------------------------------------------------------------
class ProfitLossModel(QAbstractTableModel):
    def __init__(self, parent_view):
        super().__init__(parent_view)
        self._columns = [self.tr("Period"), self.tr("In / Out"), self.tr("Assets (begin)"),self.tr("Total result"),
                         self.tr("Profit / Loss"), self.tr("Returns"), self.tr("Taxes & Fees")]
        self.month_name = [
            self.tr('Jan'), self.tr('Feb'), self.tr('Mar'), self.tr('Apr'), self.tr('May'), self.tr('Jun'),
            self.tr('Jul'), self.tr('Aug'), self.tr('Sep'), self.tr('Oct'), self.tr('Nov'), self.tr('Dec')
        ]
        self._view = parent_view
        self._data = []
        self._month_list = []
        self._begin = 0
        self._end = 0
        self._account_id = 0
        self._float_delegate = None

    def rowCount(self, parent=None):
        return len(self._data)

    def columnCount(self, parent=None):
        return len(self._columns)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._columns[section]
        return None

    def data(self, index, role=Qt.DisplayRole, field=''):
        if role == Qt.DisplayRole:
            return self._data[index.row()][index.column()]

    def setDatesRange(self, begin, end):
        self._begin = begin
        self._end = end
        self._month_list = month_list(begin, end)
        self.prepareData()
        self.configureView()

    def setAccount(self, account_id):
        self._account_id = account_id
        self.prepareData()
        self.configureView()

    def prepareData(self):
        self._data = []
        account = JalAccount(self._account_id)
        for month in self._month_list:
            assets = account.assets_list(month['begin_ts'])
            asset_value = Decimal('0')
            for asset_data in assets:
                asset = asset_data['asset']
                asset_value += asset_data['amount'] * asset.quote(month['begin_ts'], account.currency())[1]
            result = account.get_book_turnover(BookAccount.Costs, month['begin_ts'], month['end_ts']) + \
                     account.get_book_turnover(BookAccount.Incomes, month['begin_ts'], month['end_ts'])
            interest = account.get_category_turnover(PredefinedCategory.Dividends, month['begin_ts'], month['end_ts']) + \
                       account.get_category_turnover(PredefinedCategory.Interest, month['begin_ts'], month['end_ts'])
            fee_tax = account.get_category_turnover(PredefinedCategory.Fees, month['begin_ts'], month['end_ts']) + \
                       account.get_category_turnover(PredefinedCategory.Taxes, month['begin_ts'], month['end_ts'])
            data_row = [
                f"{month['year']} {self.month_name[month['month'] - 1]}",
                -account.get_book_turnover(BookAccount.Transfers, month['begin_ts'], month['end_ts']),
                asset_value,
                -result,
                -account.get_category_turnover(PredefinedCategory.Profit, month['begin_ts'], month['end_ts']),
                -interest,
                -fee_tax]
            self._data.append(data_row)
        self.modelReset.emit()

    def configureView(self):
        self._view.setModel(self)
        font = self._view.horizontalHeader().font()
        font.setBold(True)
        self._view.horizontalHeader().setFont(font)
        self._float_delegate = FloatDelegate(2, allow_tail=False, colors=True)
        self._view.setItemDelegateForColumn(1, self._float_delegate)
        self._view.setItemDelegateForColumn(2, self._float_delegate)
        self._view.setItemDelegateForColumn(3, self._float_delegate)
        self._view.setItemDelegateForColumn(4, self._float_delegate)
        self._view.setItemDelegateForColumn(5, self._float_delegate)
        self._view.setItemDelegateForColumn(6, self._float_delegate)


# ----------------------------------------------------------------------------------------------------------------------
class ProfitLossReport(QObject):
    def __init__(self):
        super().__init__()
        self.name = self.name = self.tr("P&L by Account")
        self.window_class = "ProfitLossReportWindow"


# ----------------------------------------------------------------------------------------------------------------------
class ProfitLossReportWindow(MdiWidget, Ui_ProfitLossReportWidget):
    def __init__(self, parent: Reports, settings: dict = None):
        MdiWidget.__init__(self, parent.mdi_area())
        self.setupUi(self)
        self._parent = parent

        self.pl_model = ProfitLossModel(self.ReportTableView)
        self.ReportTableView.setModel(self.pl_model)

        self.connect_signals_and_slots()

    def connect_signals_and_slots(self):
        self.ReportRange.changed.connect(self.ReportTableView.model().setDatesRange)
        self.ReportAccountBtn.changed.connect(self.onAccountChange)

    @Slot()
    def onAccountChange(self):
        self.ReportTableView.model().setAccount(self.ReportAccountBtn.account_id)
