from math import floor, ceil
from decimal import Decimal

from PySide6.QtCore import Qt, QMargins, QDateTime
from PySide6.QtWidgets import QWidget, QHBoxLayout
from PySide6.QtCharts import QChartView, QLineSeries, QScatterSeries, QDateTimeAxis, QValueAxis, QXYSeries
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.operations import LedgerTransaction
from jal.constants import CustomColor
from jal.widgets.mdi import MdiWidget
from jal.widgets.helpers import ts2d


class ChartWidget(QWidget):
    def __init__(self, parent, quotes, trades, data_range, currency_name):
        super().__init__(parent=parent)
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)

        self.quotes_series = QLineSeries()
        for point in quotes:            # Conversion to 'float' in order not to get 'int' overflow on some platforms
            self.quotes_series.append(float(point['timestamp']), point['quote'])
        self.quotes_series.setColor(CustomColor.DarkBlue)

        self._trades = trades
        self.trade_series = QScatterSeries()
        points_config = {}
        for i, point in enumerate(trades):            # Conversion to 'float' in order not to get 'int' overflow on some platforms
            self.trade_series.append(float(point['timestamp']), point['price'])
            points_config[i] = {QXYSeries.PointConfiguration.Color: point['color']}
        self.trade_series.setMarkerSize(7)
        self.trade_series.setBorderColor(CustomColor.Grey)
        self.trade_series.setPointsConfiguration(points_config)
        self.trade_series.hovered.connect(self.MouseOverTrade)

        self.axisX = QDateTimeAxis()
        self.axisX.setTickCount(11)
        self.axisX.setRange(QDateTime().fromSecsSinceEpoch(data_range[0]), QDateTime().fromSecsSinceEpoch(data_range[1]))
        self.axisX.setFormat("yyyy/MM/dd")
        self.axisX.setLabelsAngle(-90)
        self.axisX.setTitleText("Date")

        self.axisY = QValueAxis()
        self.axisY.setTickCount(11)
        self.axisY.setRange(data_range[2], data_range[3])
        self.axisY.setTitleText("Price, " + currency_name)

        self.chartView = QChartView()
        self.chartView.chart().addSeries(self.quotes_series)
        self.chartView.chart().addSeries(self.trade_series)
        self.chartView.chart().addAxis(self.axisX, Qt.AlignBottom)
        self.quotes_series.attachAxis(self.axisX)
        self.trade_series.attachAxis(self.axisX)
        self.chartView.chart().addAxis(self.axisY, Qt.AlignLeft)
        self.quotes_series.attachAxis(self.axisY)
        self.trade_series.attachAxis(self.axisY)
        self.chartView.chart().legend().hide()
        self.chartView.setViewportMargins(0, 0, 0, 0)
        self.chartView.chart().layout().setContentsMargins(0, 0, 0, 0)  # To remove extra spacing around chart
        self.chartView.chart().setBackgroundRoundness(0)  # To remove corner rounding
        self.chartView.chart().setMargins(QMargins(0, 0, 0, 0))  # Allow chart to fill all space

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)  # Remove extra space around layout
        self.layout.addWidget(self.chartView)
        self.setLayout(self.layout)

    def MouseOverTrade(self, point, state):
        if state:
            trade = [x for x in self._trades if float(x['timestamp']) == point.x() and float(x['price']) == point.y()]
            qty = sum([x['qty'] for x in trade])
            avg_price = sum([x['price']*x['qty'] for x in trade]) / qty
            tip_text = ts2d(int(point.x()/1000)) + ": "
            tip_text += f"+{qty}@{avg_price}" if qty > 0 else f"{qty}@{avg_price}"
            if len(trade) and trade[0]['text']:
                tip_text += "\n" + trade[0]['text']
            self.setToolTip(tip_text)
        else:
            self.setToolTip("")

class ChartWindow(MdiWidget):
    def __init__(self, account_id, asset_id, currency_id, timestamp, parent=None):
        super().__init__(parent)

        self.account_id = account_id
        self.asset_id = asset_id
        self.currency_id = currency_id if asset_id != currency_id else 1  # Check whether we have currency or asset
        self.asset_name = JalAsset(self.asset_id).symbol(JalAccount(self.account_id).currency())
        self.quotes = []
        self.trades = []
        self.currency_name = ''
        self.range = [0, 0, 0, 0]

        self.prepare_chart_data(timestamp)

        self.chart = ChartWidget(self, self.quotes, self.trades, self.range, self.currency_name)

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)  # Remove extra space around layout
        self.layout.addWidget(self.chart)
        self.setLayout(self.layout)

        self.setWindowTitle(self.tr("Price chart for ") + self.asset_name)

        self.ready = True

    def load_open_trades(self, account, asset, end_time):
        trades = []
        positions = account.open_trades_list(asset, end_time)
        for trade in positions:
            operation = trade.open_operation()
            if trade.open_qty() >= 0:
                marker_color = CustomColor.LightGreen
                text = self.tr("Buy")
            else:
                marker_color = CustomColor.LightRed
                text = self.tr("Sell")
            if operation.type() == LedgerTransaction.AssetPayment:
                text = operation.name() + "\n" + operation.description().split('\n')[0]
            trades.append({
                'timestamp': operation.timestamp() * 1000,  # timestamp to ms
                'price': trade.open_price(adjusted=True),
                'qty': trade.open_qty(),
                'color': marker_color,
                'text': text
            })
        return trades

    def prepare_chart_data(self, end_time):
        account = JalAccount(self.account_id)
        asset = JalAsset(self.asset_id)
        self.currency_name = JalAsset(account.currency()).symbol()
        self.trades = self.load_open_trades(account, asset, end_time)
        start_time = 0 if not self.trades else min([x['timestamp'] for x in self.trades])/1000 - 2592000  # Shift back by 30 days
        quotes = asset.quotes(start_time, end_time, self.currency_id, adjust_splits=True)
        for quote in quotes:
            self.quotes.append({'timestamp': quote[0] * 1000, 'quote': quote[1]})  # timestamp to ms
        if self.quotes or self.trades:
            min_price = min([x['quote'] for x in self.quotes] + [x['price'] for x in self.trades])
            max_price = max([x['quote'] for x in self.quotes] + [x['price'] for x in self.trades])
            min_ts = min([x['timestamp'] for x in self.quotes] + [x['timestamp'] for x in self.trades]) / 1000
            max_ts = max([x['timestamp'] for x in self.quotes] + [x['timestamp'] for x in self.trades]) / 1000
        else:
            self.range = [0, 0, 0, 0]
            return
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
        min_ts = int(min_ts - 86400 * 3)
        max_ts = int(max_ts + 86400 * 3)
        self.range = [min_ts, max_ts, min_price, max_price]
