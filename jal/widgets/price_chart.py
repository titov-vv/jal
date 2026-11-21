from math import floor, ceil
from decimal import Decimal

from PySide6.QtCore import Qt, QMargins, QDateTime, Signal
from PySide6.QtGui import QPen
from PySide6.QtWidgets import QApplication, QWidget, QHBoxLayout
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QScatterSeries, QDateTimeAxis, QValueAxis, QXYSeries
from jal.db.operations import LedgerTransaction
from jal.widgets.helpers import ts2d, DateFormat, ts2axis, axis2ts
from jal.widgets.theme import Theme, Meaning, is_dark_theme


# A price line with a marker per lot. show_lots() picks the lots drawn, the one highlighted and an average cost line;
# lotClicked reports the lot (its 'lot' index) whose marker was clicked.
class ChartWidget(QWidget):
    lotClicked = Signal(int)
    MARKER_SIZE = 7
    SELECTED_SIZE = 13

    def __init__(self, parent, quotes, trades, data_range, currency_name):
        super().__init__(parent=parent)
        self.setMinimumWidth(300)
        self.setMinimumHeight(250)
        self._trades = trades
        self._range = data_range
        self._visible = []          # the trades drawn now

        self.quotes_series = QLineSeries()
        for point in quotes:            # Conversion to 'float' in order not to get 'int' overflow on some platforms
            self.quotes_series.append(float(ts2axis(point['timestamp']) * 1000), point['quote'])
        self.average_series = QLineSeries()
        self.trade_series = self._marker_series(QScatterSeries.MarkerShape.MarkerShapeCircle, self.MARKER_SIZE)
        self.income_series = self._marker_series(QScatterSeries.MarkerShape.MarkerShapeTriangle, self.MARKER_SIZE)
        self.selected_series = self._marker_series(QScatterSeries.MarkerShape.MarkerShapeCircle, self.SELECTED_SIZE)

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
        self.axisY.setTitleText(self.tr("Price, ") + currency_name)

        self.chartView = QChartView()
        chart = self.chartView.chart()
        chart.addAxis(self.axisX, Qt.AlignBottom)
        chart.addAxis(self.axisY, Qt.AlignLeft)
        for series in (self.quotes_series, self.average_series, self.trade_series, self.income_series,
                       self.selected_series):
            chart.addSeries(series)
            series.attachAxis(self.axisX)
            series.attachAxis(self.axisY)
        chart.legend().hide()
        self.chartView.setViewportMargins(0, 0, 0, 0)
        chart.layout().setContentsMargins(0, 0, 0, 0)  # To remove extra spacing around chart
        chart.setBackgroundRoundness(0)  # To remove corner rounding
        chart.setMargins(QMargins(0, 0, 0, 0))  # Allow chart to fill all space

        # A QChart takes its colors from a chart theme of its own, which knows nothing about QPalette; setTheme()
        # overwrites every series color, so the series are colored after it.
        chart.setTheme(QChart.ChartTheme.ChartThemeDark if is_dark_theme() else QChart.ChartTheme.ChartThemeLight)
        chart.setBackgroundBrush(QApplication.palette().base())
        self.quotes_series.setColor(Theme.text(Meaning.INFO))
        self.average_series.setPen(QPen(Theme.text(Meaning.MUTED), 1, Qt.DashLine))
        for series in (self.trade_series, self.income_series, self.selected_series):
            series.setBorderColor(Theme.text(Meaning.MUTED))
        self.selected_series.setColor(Theme.fill(Meaning.WARNING))

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)  # Remove extra space around layout
        self.layout.addWidget(self.chartView)
        self.setLayout(self.layout)
        self.show_lots({x['lot'] for x in trades}, None, None)

    def _marker_series(self, shape, size) -> QScatterSeries:
        series = QScatterSeries()
        series.setMarkerShape(shape)
        series.setMarkerSize(size)
        series.hovered.connect(self.MouseOverTrade)
        series.clicked.connect(self.onMarkerClicked)
        return series

    @staticmethod
    def _point(trade) -> tuple:     # Conversion to 'float' in order not to get 'int' overflow on some platforms
        return float(ts2axis(trade['timestamp']) * 1000), float(trade['price'])

    # Draws the markers of the lots in 'visible', 'selected' highlighted, and the 'average' cost line (None for none)
    def show_lots(self, visible: set, selected, average) -> None:
        self._visible = [x for x in self._trades if x['lot'] in visible]
        for series, income in ((self.trade_series, False), (self.income_series, True)):
            points = [x for x in self._visible if x['income'] == income]
            series.clear()
            for trade in points:
                series.append(*self._point(trade))
            series.setPointsConfiguration(
                {i: {QXYSeries.PointConfiguration.Color: Theme.text(x['meaning'])} for i, x in enumerate(points)})
        self.selected_series.clear()
        chosen = [x for x in self._visible if x['lot'] == selected]
        if chosen:
            self.selected_series.setMarkerShape(QScatterSeries.MarkerShape.MarkerShapeTriangle if chosen[0]['income']
                                                else QScatterSeries.MarkerShape.MarkerShapeCircle)
            self.selected_series.append(*self._point(chosen[0]))
        self.average_series.clear()
        if average is not None and self._range[2] <= average <= self._range[3]:
            for timestamp in self._range[:2]:
                self.average_series.append(float(ts2axis(timestamp) * 1000), float(average))

    def _trades_at(self, point) -> list:
        return [x for x in self._visible if self._point(x) == (point.x(), point.y())]

    def onMarkerClicked(self, point):
        trades = self._trades_at(point)
        if trades:
            self.lotClicked.emit(trades[0]['lot'])

    def MouseOverTrade(self, point, state):
        trade = self._trades_at(point) if state else []
        if not trade:
            self.setToolTip("")
            return
        hovered = axis2ts(int(point.x() / 1000))
        qty = sum([x['qty'] for x in trade])
        avg_price = sum([x['price']*x['qty'] for x in trade]) / qty
        tip_text = ts2d(hovered) + ": "
        if trade[0]['income']:
            cost_text = self.tr("cost 0, quote")
            tip_text += f"+{qty}, {cost_text} {avg_price}"
        else:
            tip_text += f"+{qty}@{avg_price}" if qty > 0 else f"{qty}@{avg_price}"
        if trade[0]['text']:
            tip_text += "\n" + trade[0]['text']
        self.setToolTip(tip_text)


# The chart markers of 'lots' (as JalAccount.open_trades_list() gives them), each with its index in 'lots' as 'lot';
# a zero-cost income lot sits on the quote of its day and an unquoted one is not drawn
def lot_markers(lots, asset, currency_id) -> list:
    trades = []
    for i, lot in enumerate(lots):
        operation = lot.open_operation()
        if lot.open_qty() >= 0:
            meaning, text = Meaning.POSITIVE, QApplication.translate("ChartWidget", "Buy")
        else:
            meaning, text = Meaning.NEGATIVE, QApplication.translate("ChartWidget", "Sell")
        if operation.type() in (LedgerTransaction.AssetPayment, LedgerTransaction.AssetIncome):
            text = operation.name() + "\n" + operation.description().split('\n')[0]
        price = lot.open_price(adjusted=True)
        income = operation.type() == LedgerTransaction.AssetIncome and price == Decimal('0')
        if income:
            quote_ts, price = asset.quote(operation.timestamp(), currency_id, report_missing=False)
            if not quote_ts:
                continue
        trades.append({
            'lot': i,
            'timestamp': operation.timestamp(),
            'price': price,
            'qty': lot.open_qty(),
            'meaning': meaning,   # what the marker means - its colour depends on the ground and is picked later
            'text': text,
            'income': income
        })
    return trades


# The quotes of 'asset' in 'currency_id' from 30 days before the first marker to 'end_time', and the chart's
# [min_ts, max_ts, min_price, max_price] range rounded to nice values
def price_history(asset, currency_id, trades, end_time) -> (list, list):
    start_time = 0 if not trades else min([x['timestamp'] for x in trades]) - 2592000  # Shift back by 30 days
    quotes = [{'timestamp': x[0], 'quote': x[1]}
              for x in asset.quotes(start_time, end_time, currency_id, adjust_splits=True)]
    if not quotes and not trades:
        return quotes, [0, 0, 0, 0]
    min_price = min([x['quote'] for x in quotes] + [x['price'] for x in trades])
    max_price = max([x['quote'] for x in quotes] + [x['price'] for x in trades])
    min_ts = min([x['timestamp'] for x in quotes] + [x['timestamp'] for x in trades])
    max_ts = max([x['timestamp'] for x in quotes] + [x['timestamp'] for x in trades])
    # push range apart if we have very close points
    if min_price == max_price:
        min_price = Decimal('0.95') * min_price
        max_price = Decimal('1.05') * max_price
    if min_ts == max_ts:
        min_ts = 0.95 * min_ts
        max_ts = 1.05 * max_ts
    # Round min/max values to near "round" values in order to have 10 nice intervals
    step = Decimal(1) if min_price == max_price else Decimal(10) ** Decimal(floor(Decimal.log10(max_price - min_price)))
    min_price = floor(min_price / step) * step
    max_price = ceil(max_price / step) * step
    # Add a gap at the beginning and end
    return quotes, [int(min_ts - 86400 * 3), int(max_ts + 86400 * 3), min_price, max_price]
