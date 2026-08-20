from math import floor, ceil
from decimal import Decimal

from PySide6.QtCore import Qt, QMargins, QDateTime
from PySide6.QtWidgets import QApplication, QWidget, QHBoxLayout, QLabel
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QScatterSeries, QDateTimeAxis, QValueAxis
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.chain_balance import JalChainBalance
from jal.widgets.helpers import ts2d, DateFormat, ts2axis, axis2ts
from jal.widgets.mdi import MdiWidget
from jal.widgets.theme import Theme, Meaning, is_dark_theme


# ----------------------------------------------------------------------------------------------------------------------
# How much a position has earned without anything being booked for it - the quantity the chain reports minus the
# quantity the books hold, plotted at every moment the chain was read.
#
# It is a different picture from the price chart next door, and deliberately so: that one draws what a unit is WORTH
# over time, this one draws how many units appeared out of nowhere. For a rebasing token or a staking container those
# are the two independent halves of what the position did, and only the second one is invisible everywhere else.
#
# The line is a step rather than a curve, and the steps are uneven. A point exists where a refresh happened, so the
# shape says as much about how often quotes were updated as about the yield itself - and for Hyperliquid it is a
# daily staircase besides, since rewards are distributed once a day and nothing moves in between. That is why the
# points are drawn as markers on the line instead of being smoothed away: every one of them is a measurement, and the
# space between two of them is not information.
class AccrualChartWidget(QWidget):
    def __init__(self, parent, series, data_range, unit_name):
        super().__init__(parent=parent)
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)

        self._series = series
        self.accrued_series = QLineSeries()
        self.points_series = QScatterSeries()
        for point in series:      # Conversion to 'float' in order not to get 'int' overflow on some platforms
            self.accrued_series.append(float(ts2axis(point['timestamp']) * 1000), float(point['accrued']))
            self.points_series.append(float(ts2axis(point['timestamp']) * 1000), float(point['accrued']))
        self.points_series.setMarkerSize(7)
        self.points_series.hovered.connect(self.MouseOverPoint)

        self.axisX = QDateTimeAxis()
        self.axisX.setTickCount(11)
        self.axisX.setRange(QDateTime().fromSecsSinceEpoch(ts2axis(data_range[0])),
                            QDateTime().fromSecsSinceEpoch(ts2axis(data_range[1])))
        self.axisX.setFormat(DateFormat.date(qt=True))
        self.axisX.setLabelsAngle(-90)
        self.axisX.setTitleText(self.tr("Date"))

        self.axisY = QValueAxis()
        self.axisY.setTickCount(11)
        self.axisY.setRange(data_range[2], data_range[3])
        self.axisY.setTitleText(self.tr("Accrued, ") + unit_name)

        self.chartView = QChartView()
        self.chartView.chart().addSeries(self.accrued_series)
        self.chartView.chart().addSeries(self.points_series)
        self.chartView.chart().addAxis(self.axisX, Qt.AlignBottom)
        self.accrued_series.attachAxis(self.axisX)
        self.points_series.attachAxis(self.axisX)
        self.chartView.chart().addAxis(self.axisY, Qt.AlignLeft)
        self.accrued_series.attachAxis(self.axisY)
        self.points_series.attachAxis(self.axisY)
        self.chartView.chart().legend().hide()
        self.chartView.setViewportMargins(0, 0, 0, 0)
        self.chartView.chart().layout().setContentsMargins(0, 0, 0, 0)   # To remove extra spacing around chart
        self.chartView.chart().setBackgroundRoundness(0)                 # To remove corner rounding
        self.chartView.chart().setMargins(QMargins(0, 0, 0, 0))          # Allow chart to fill all space

        # A QChart paints its own background and takes its axis and label colours from a chart theme of its own,
        # which knows nothing about QPalette. So it is pointed at the chart theme that matches the application's
        # ground and then given that ground itself - after which the series can be derived like anything else.
        # This has to come after the theme is set: setTheme() overwrites every colour a series already had.
        chart = self.chartView.chart()
        chart.setTheme(QChart.ChartTheme.ChartThemeDark if is_dark_theme() else QChart.ChartTheme.ChartThemeLight)
        chart.setBackgroundBrush(QApplication.palette().base())
        self.accrued_series.setColor(Theme.text(Meaning.POSITIVE))
        self.points_series.setColor(Theme.text(Meaning.POSITIVE))
        self.points_series.setBorderColor(Theme.text(Meaning.MUTED))

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.chartView)
        self.setLayout(self.layout)

    # Both quantities behind a point, because the accrual alone doesn't say what it accrued ON - the same 0.07 means
    # something different against 6 staked coins than against 12.
    def MouseOverPoint(self, point, state):
        if not state:
            self.setToolTip("")
            return
        hovered = axis2ts(int(point.x() / 1000))
        measured = [x for x in self._series if x['timestamp'] == hovered]
        if not measured:
            self.setToolTip("")
            return
        measurement = measured[0]
        self.setToolTip(ts2d(measurement['timestamp']) + "\n"
                        + self.tr("On chain: ") + f"{measurement['chain']}\n"
                        + self.tr("In books: ") + f"{measurement['ledger']}\n"
                        + self.tr("Accrued: ") + f"{measurement['accrued']}")


class AccrualChartWindow(MdiWidget):
    def __init__(self, account_id, asset_id, parent=None):
        super().__init__(parent)
        account = JalAccount(account_id)
        asset = JalAsset(asset_id)
        series = JalChainBalance().accrual_history(account_id, asset_id)
        name = asset.symbol(currency=account.currency(), location=account.chain())

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        # A position that was never read, or read once, has no history to draw yet - and it is worth saying so
        # plainly. The series can only ever be accumulated going forward: no source anywhere reports what a balance
        # was on a past date, so an empty chart here means "not measured yet" and never "nothing was earned".
        if len(series) < 2:
            self.layout.addWidget(QLabel(
                self.tr("Not enough on-chain measurements yet - the balance history is collected as quotes are "
                        "updated, and cannot be filled in for the past."), parent=self))
        else:
            self.layout.addWidget(AccrualChartWidget(self, series, self._range(series), name))
        self.setLayout(self.layout)
        self.setWindowTitle(self.tr("Accrued quantity: ") + f"{name} @ {account.name()}")
        self.ready = True

    # Axis bounds. The vertical one always starts at zero: an accrual is measured FROM nothing, and letting the axis
    # start at the first reading would turn a position that grew by a hundredth of a percent into a dramatic climb.
    @staticmethod
    def _range(series) -> list:
        min_ts = min(x['timestamp'] for x in series) - 86400
        max_ts = max(x['timestamp'] for x in series) + 86400
        top = max(x['accrued'] for x in series)
        if top <= Decimal('0'):
            return [min_ts, max_ts, 0, 1]
        step = Decimal(10) ** Decimal(floor(Decimal.log10(top)))
        return [min_ts, max_ts, 0, ceil(top / step) * step]
