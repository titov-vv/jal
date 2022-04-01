from math import log10, floor, ceil

from PySide6.QtCore import Qt, QMargins, QDateTime
from PySide6.QtWidgets import QWidget, QHBoxLayout
from PySide6.QtCharts import QChartView, QLineSeries, QScatterSeries, QDateTimeAxis, QValueAxis
from jal.db.db import JalDB
from jal.constants import BookAccount, CustomColor
from jal.db.helpers import executeSQL, readSQL, readSQLrecord
from jal.widgets.mdi import MdiWidget


class ChartWidget(QWidget):
    def __init__(self, parent, quotes, trades, data_range, currency_name):
        QWidget.__init__(self, parent)
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)

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


class ChartWindow(MdiWidget):
    def __init__(self, account_id, asset_id, currency_id, _asset_qty, parent=None):
        super().__init__(parent)

        self.account_id = account_id
        self.asset_id = asset_id
        self.currency_id = currency_id if asset_id != currency_id else 1  # Check whether we have currency or asset
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

        self.ready = True

    def prepare_chart_data(self):
        self.currency_name = JalDB().get_asset_name(JalDB().get_account_currency(self.account_id))
        start_time = readSQL("SELECT MAX(ts) FROM "  # Take either last "empty" timestamp
                             "(SELECT coalesce(MAX(timestamp), 0) AS ts "
                             "FROM ledger WHERE account_id=:account_id AND asset_id=:asset_id "
                             "AND book_account=:assets_book AND amount_acc==0 "
                             "UNION "  # or first timestamp where position started to appear
                             "SELECT coalesce(MIN(timestamp), 0) AS ts "
                             "FROM ledger WHERE account_id=:account_id AND asset_id=:asset_id "
                             "AND book_account=:assets_book AND amount_acc!=0)",
                             [(":account_id", self.account_id), (":asset_id", self.asset_id),
                              (":assets_book", BookAccount.Assets)])
        # Get asset quotes
        query = executeSQL("SELECT timestamp, quote FROM quotes "
                           "WHERE asset_id=:asset_id AND currency_id=:currency_id AND timestamp>:last",
                           [(":asset_id", self.asset_id), (":currency_id", self.currency_id), (":last", start_time)])
        while query.next():
            quote = readSQLrecord(query, named=True)
            self.quotes.append({'timestamp': quote['timestamp'] * 1000, 'quote': quote['quote']})  # timestamp to ms
        # Get deals prices
        query = executeSQL("SELECT timestamp, price, qty FROM trades "
                           "WHERE account_id=:account_id AND asset_id=:asset_id AND timestamp>=:last",
                           [(":account_id", self.account_id), (":asset_id", self.asset_id), (":last", start_time)])
        while query.next():
            trade = readSQLrecord(query, named=True)
            self.trades.append({'timestamp': trade['timestamp'] * 1000, 'price': trade['price'], 'qty': trade['qty']})
        if self.quotes or self.trades:
            min_price = min([x['quote'] for x in self.quotes] + [x['price'] for x in self.trades])
            max_price = max([x['quote'] for x in self.quotes] + [x['price'] for x in self.trades])
            min_ts = min([x['timestamp'] for x in self.quotes] + [x['timestamp'] for x in self.trades]) / 1000
            max_ts = max([x['timestamp'] for x in self.quotes] + [x['timestamp'] for x in self.trades]) / 1000
        else:
            self.range = [0, 0, 0, 0]
            return
        # push range apart if we have too close points
        if min_price == max_price:
            min_price = 0.95 * min_price
            max_price = 1.05 * max_price
        if min_ts == max_ts:
            min_ts = 0.95 * min_ts
            max_ts = 1.05 * max_ts
        # Round min/max values to near "round" values in order to have 10 nice intervals
        step = 10 ** floor(log10(max_price - min_price))
        min_price = floor(min_price / step) * step
        max_price = ceil(max_price / step) * step
        # Add a gap at the beginning and end
        min_ts = int(min_ts - 86400 * 3)
        max_ts = int(max_ts + 86400 * 3)
        self.range = [min_ts, max_ts, min_price, max_price]
