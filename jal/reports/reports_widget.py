from PySide6.QtCore import Qt, Slot, Signal, QDateTime
from jal.ui.ui_reports_widget import Ui_ReportsWidget
from jal.widgets.helpers import ManipulateDate
from jal.widgets.mdi_widget import MdiWidget
from jal.reports.reports import Reports, ReportType


# ----------------------------------------------------------------------------------------------------------------------
class ReportsWidget(MdiWidget, Ui_ReportsWidget):
    onClose = Signal()

    def __init__(self, parent=None):
        MdiWidget.__init__(self, parent)
        self.setupUi(self)

        # Setup reports tab
        self.reports = Reports(self.ReportTableView, self.ReportTreeView)

        self.connect_signals_and_slots()

    def connect_signals_and_slots(self):
        self.ReportRangeCombo.currentIndexChanged.connect(self.onReportRangeChange)
        self.RunReportBtn.clicked.connect(self.onRunReport)
        self.SaveReportBtn.clicked.connect(self.reports.saveReport)

    @Slot()
    def onReportRangeChange(self, range_index):
        report_ranges = {
            0: lambda: (0, 0),
            1: ManipulateDate.Last3Months,
            2: ManipulateDate.RangeYTD,
            3: ManipulateDate.RangeThisYear,
            4: ManipulateDate.RangePreviousYear
        }
        begin, end = report_ranges[range_index]()
        self.ReportFromDate.setDateTime(QDateTime.fromSecsSinceEpoch(begin, spec=Qt.UTC))
        self.ReportToDate.setDateTime(QDateTime.fromSecsSinceEpoch(end, spec=Qt.UTC))

    @Slot()
    def onRunReport(self):
        types = {
            0: ReportType.IncomeSpending,
            1: ReportType.ProfitLoss,
            2: ReportType.Deals,
            3: ReportType.ByCategory
        }
        report_type = types[self.ReportTypeCombo.currentIndex()]
        begin = self.ReportFromDate.dateTime().toSecsSinceEpoch()
        end = self.ReportToDate.dateTime().toSecsSinceEpoch()
        group_dates = 1 if self.ReportGroupCheck.isChecked() else 0
        if report_type == ReportType.ByCategory:
            self.reports.runReport(report_type, begin, end, self.ReportCategoryEdit.selected_id, group_dates)
        else:
            self.reports.runReport(report_type, begin, end, self.ReportAccountBtn.account_id, group_dates)
