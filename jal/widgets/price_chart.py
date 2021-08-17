from PySide2.QtCore import Qt, QMargins
from PySide2.QtWidgets import QDialog, QWidget, QHBoxLayout
from PySide2.QtCharts import QtCharts
from jal.db.update import JalDB
from jal.db.helpers import executeSQL, readSQLrecord
from jal.widgets.helpers import g_tr


class chartWidget(QWidget):
    def __init__(self, parent, data):
        QWidget.__init__(self, parent)

        self.series = QtCharts.QLineSeries()
        for point in data:
            self.series.append(point['timestamp'], point['quote'])

        self.chartView = QtCharts.QChartView()
        self.chartView.chart().addSeries(self.series)

        axisX = QtCharts.QDateTimeAxis()
        axisX.setTickCount(12)
        axisX.setFormat("yyyy/MM/dd")
        axisX.setTitleText("Date")
        axisX.setLabelsAngle(-90)
        self.chartView.chart().addAxis(axisX, Qt.AlignBottom)
        self.series.attachAxis(axisX)

        axisY = QtCharts.QValueAxis()
        axisY.setTickCount(10)
        axisY.setTitleText("Price, RUB")    # TODO put correct currency name
        self.chartView.chart().addAxis(axisY, Qt.AlignLeft)
        self.series.attachAxis(axisY)

        self.chartView.chart().legend().hide()
        self.chartView.setViewportMargins(0, 0, 0, 0)
        self.chartView.chart().layout().setContentsMargins(0, 0, 0, 0)   # To remove extra spacing around chart
        self.chartView.chart().setBackgroundRoundness(0)                 # To remove corner rounding
        self.chartView.chart().setMargins(QMargins(0, 0, 0, 0))          # Allow chart to fill all space

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
        self.get_quotes()

        self.chart = chartWidget(self, self.quotes)

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)  # Remove extra space around layout
        self.layout.addWidget(self.chart)
        self.setLayout(self.layout)

        self.setWindowTitle(g_tr('ChartWindow', "Price chart for ") + self.asset_name)
        self.setWindowFlag(Qt.Tool)
        self.setGeometry(position.x(), position.y(), self.width(), self.height())

        self.ready = True

    def get_quotes(self):
        query = executeSQL("SELECT timestamp, quote FROM quotes WHERE asset_id=:asset_id",
                           [(":asset_id", self.asset_id)])
        while query.next():
            quote = readSQLrecord(query, named=True)
            self.quotes.append({'timestamp': quote['timestamp']*1000, 'quote': quote['quote']})  # timestamp to ms
