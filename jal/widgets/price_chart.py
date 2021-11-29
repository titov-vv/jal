from math import log10, floor, ceil

from PySide6.QtCore import Qt, QMargins, QDateTime
from PySide6.QtWidgets import QDialog, QWidget, QHBoxLayout
from PySide6.QtCharts import QChartView, QLineSeries, QScatterSeries, QDateTimeAxis, QValueAxis
from jal.db.db import JalDB
from jal.constants import BookAccount, CustomColor
from jal.db.helpers import executeSQL, readSQL, readSQLrecord


class ChartWidget(QWidget):
    def __init__(self, parent, quotes, trades, data_range, currency_name):
        QWidget.__init__(self, parent)

        self.quotes_series = QLineSeries()
        for point in quotes:            # Conversion to 'float' in order not to get 'int' overflow on some platforms
            self.quotes_series.append(float(point['timestamp']), point['quote'])

        self.trade_series = QScatterSeries()
        for point in trades:            # Conversion to 'float' in order not to get 'int' overflow on some platforms
            self.trade_series.append(float(point['timestamp']), point['price'])
        self.trade_series.setMarkerSize(5)
        self.trade_series.setBorderColor(CustomColor.LightRed)
        self.trade_series.setBrush(CustomColor.DarkRed)

        axisX = QDateTimeAxis()
        axisX.setTickCount(11)
        axisX.setRange(QDateTime().fromSecsSinceEpoch(data_range[0]), QDateTime().fromSecsSinceEpoch(data_range[1]))
        axisX.setFormat("yyyy/MM/dd")
        axisX.setLabelsAngle(-90)
        axisX.setTitleText("Date")

        axisY = QValueAxis()
        axisY.setTickCount(11)
        axisY.setRange(data_range[2], data_range[3])
        axisY.setTitleText("Price, " + currency_name)

        self.chartView = QChartView()
        self.chartView.chart().addSeries(self.quotes_series)
        self.chartView.chart().addSeries(self.trade_series)
        self.chartView.chart().addAxis(axisX, Qt.AlignBottom)
        self.chartView.chart().setAxisX(axisX, self.quotes_series)
        self.chartView.chart().setAxisX(axisX, self.trade_series)
        self.chartView.chart().addAxis(axisY, Qt.AlignLeft)
        self.chartView.chart().setAxisY(axisY, self.quotes_series)
        self.chartView.chart().setAxisY(axisY, self.trade_series)
        self.chartView.chart().legend().hide()
        self.chartView.setViewportMargins(0, 0, 0, 0)
        self.chartView.chart().layout().setContentsMargins(0, 0, 0, 0)  # To remove extra spacing around chart
        self.chartView.chart().setBackgroundRoundness(0)  # To remove corner rounding
        self.chartView.chart().setMargins(QMargins(0, 0, 0, 0))  # Allow chart to fill all space

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)  # Remove extra space around layout
        self.layout.addWidget(self.chartView)
        self.setLayout(self.layout)


class ChartWindow(QDialog):
    def __init__(self, account_id, asset_id, _asset_qty, position, parent=None):
        super().__init__(parent)

        self.account_id = account_id
        self.asset_id = asset_id
        self.asset_name = JalDB().get_asset_name(self.asset_id)
        self.quotes = []
        self.trades = []
        self.currency_name = ''
        self.range = [0, 0, 0, 0]

        self.prepare_chart_data()

        self.chart = ChartWidget(self, self.quotes, self.trades, self.range, self.currency_name)

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)  # Remove extra space around layout
        self.layout.addWidget(self.chart)
        self.setLayout(self.layout)

        self.setWindowTitle(self.tr("Price chart for ") + self.asset_name)
        self.setWindowFlag(Qt.Tool)
        self.setGeometry(position.x(), position.y(), self.width(), self.height())

        self.ready = True

    def prepare_chart_data(self):
        min_price = max_price = 0
        min_ts = max_ts = 0

        self.currency_name = JalDB().get_asset_name(JalDB().get_account_currency(self.account_id))
        start_time = readSQL("SELECT MAX(ts) FROM "  # Take either last "empty" timestamp
                             "(SELECT coalesce(MAX(timestamp), 0) AS ts "
                             "FROM ledger_sums WHERE account_id=:account_id AND asset_id=:asset_id "
                             "AND book_account=:assets_book AND sum_amount==0 "
                             "UNION "  # or first timestamp where position started to appear
                             "SELECT coalesce(MIN(timestamp), 0) AS ts "
                             "FROM ledger_sums WHERE account_id=:account_id AND asset_id=:asset_id "
                             "AND book_account=:assets_book AND sum_amount!=0)",
                             [(":account_id", self.account_id), (":asset_id", self.asset_id),
                              (":assets_book", BookAccount.Assets)])
        # Get quotes quotes
        query = executeSQL("SELECT timestamp, quote FROM quotes WHERE asset_id=:asset_id AND timestamp>:last",
                           [(":asset_id", self.asset_id), (":last", start_time)])
        while query.next():
            quote = readSQLrecord(query, named=True)
            self.quotes.append({'timestamp': quote['timestamp'] * 1000, 'quote': quote['quote']})  # timestamp to ms
            min_price = quote['quote'] if min_price == 0 or quote['quote'] < min_price else min_price
            max_price = quote['quote'] if quote['quote'] > max_price else max_price
            min_ts = quote['timestamp'] if min_ts == 0 or quote['timestamp'] < min_ts else min_ts
            max_ts = quote['timestamp'] if quote['timestamp'] > max_ts else max_ts

        # Get deals quotes
        query = executeSQL("SELECT timestamp, price, qty FROM trades "
                           "WHERE account_id=:account_id AND asset_id=:asset_id AND timestamp>=:last",
                           [(":account_id", self.account_id), (":asset_id", self.asset_id), (":last", start_time)])
        while query.next():
            trade = readSQLrecord(query, named=True)
            self.trades.append({'timestamp': trade['timestamp'] * 1000, 'price': trade['price'], 'qty': trade['qty']})
            min_price = trade['price'] if min_price == 0 or trade['price'] < min_price else min_price
            max_price = trade['price'] if trade['price'] > max_price else max_price
            min_ts = trade['timestamp'] if min_ts == 0 or trade['timestamp'] < min_ts else min_ts
            max_ts = trade['timestamp'] if trade['timestamp'] > max_ts else max_ts

        # Round min/max values to near "round" values in order to have 10 nice intervals
        step = 10 ** floor(log10(max_price - min_price))
        min_price = floor(min_price / step) * step
        max_price = ceil(max_price / step) * step

        # Add a gap at the beginning and end
        min_ts -= 86400 * 3
        max_ts += 86400 * 3

        self.range = [min_ts, max_ts, min_price, max_price]
