from functools import partial
from PySide6.QtCore import Qt, Slot, QObject, QDateTime, QMargins
from PySide6.QtWidgets import QWidget, QHBoxLayout
from PySide6.QtCharts import QChartView, QLineSeries, QDateTimeAxis, QValueAxis
from jal.reports.reports import Reports
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.ui.reports.ui_account_balance_report import Ui_AccountBalanceHistoryReportWidget
from jal.widgets.mdi import MdiWidget
from jal.widgets.helpers import timestamp_range

JAL_REPORT_CLASS = "AccountBalanceHistoryReport"

# ----------------------------------------------------------------------------------------------------------------------
class BalanceChartWidget(QWidget):
    def __init__(self, parent): #, quotes, trades, data_range, currency_name):
        super().__init__(parent=parent)
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)
        self.chartView = QChartView()
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)  # Remove extra space around layout
        self.layout.addWidget(self.chartView)
        self.setLayout(self.layout)
        self.axisX = None
        self.axisY = None

    def updateView(self, balances, currency_name):
        self.balances_series = QLineSeries()
        for point in balances:            # Conversion to 'float' in order not to get 'int' overflow on some platforms
            self.balances_series.append(float(point['timestamp']), point['balance'])

        # Cleanup if anything already drawn in the chart
        self.chartView.chart().removeAllSeries()
        axes = self.chartView.chart().axes()
        for axis in axes:
            self.chartView.chart().removeAxis(axis)

        # Create new X-axis
        self.axisX = QDateTimeAxis()
        self.axisX.setFormat("yyyy/MM/dd")
        self.axisX.setLabelsAngle(-90)
        self.axisX.setTitleText("Date")
        min_ts = int(min([x['timestamp'] for x in balances]) / 1000)
        max_ts = int(max([x['timestamp'] for x in balances]) / 1000)
        self.axisX.setRange(QDateTime().fromSecsSinceEpoch(min_ts), QDateTime().fromSecsSinceEpoch(max_ts))

        # Create new Y-axis
        self.axisY = QValueAxis()
        self.axisY.setTitleText("Balance, " + currency_name)

        # Arrange chart
        self.chartView.chart().addSeries(self.balances_series)
        self.chartView.chart().addAxis(self.axisX, Qt.AlignBottom)
        self.balances_series.attachAxis(self.axisX)
        self.chartView.chart().addAxis(self.axisY, Qt.AlignLeft)
        self.balances_series.attachAxis(self.axisY)
        self.chartView.chart().legend().hide()
        self.chartView.setViewportMargins(0, 0, 0, 0)
        self.chartView.chart().layout().setContentsMargins(0, 0, 0, 0)  # To remove extra spacing around chart
        self.chartView.chart().setBackgroundRoundness(0)  # To remove corner rounding
        self.chartView.chart().setMargins(QMargins(0, 0, 0, 0))  # Allow chart to fill all space

# ----------------------------------------------------------------------------------------------------------------------
class AccountBalanceHistoryReport(QObject):
    def __init__(self):
        super().__init__()
        self.name = self.tr("Account balance history")
        self.window_class = "AccountBalanceHistoryReportWindow"

# ----------------------------------------------------------------------------------------------------------------------
class AccountBalanceHistoryReportWindow(MdiWidget):
    def __init__(self, parent: Reports, settings: dict = None):
        super().__init__(parent.mdi_area())
        self.ui = Ui_AccountBalanceHistoryReportWidget()
        self.ui.setupUi(self)
        self._parent = parent
        self.name = self.tr("Account balance")

        self.chart = BalanceChartWidget(self)
        self.ui.reportLayout.addWidget(self.chart)

        if settings is not None:
            self.ui.ReportRange.setRange(settings['begin_ts'], settings['end_ts'])
            self.ui.ReportAccountButton.account_id = settings['account_id']
        self.connect_signals_and_slots()
        self.updateReport()

    def connect_signals_and_slots(self):
        self.ui.ReportRange.changed.connect(self.updateReport)
        self.ui.ReportAccountButton.changed.connect(self.updateReport)
        self.ui.SaveButton.pressed.connect(partial(self._parent.save_chart, self.chart.chartView))

    @Slot()
    def updateReport(self):
        if self.ui.ReportAccountButton.account_id == 0:
            return
        account = JalAccount(self.ui.ReportAccountButton.account_id)
        balances = []
        date_range = self.ui.ReportRange.getRange()
        for ts in timestamp_range(date_range[0], date_range[1]):
            balances.append({'timestamp': ts*1000, 'balance': account.balance(ts)})
        self.chart.updateView(balances, JalAsset(account.currency()).symbol())
