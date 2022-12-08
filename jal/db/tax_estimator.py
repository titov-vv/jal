from decimal import Decimal

import pandas as pd
from PySide6.QtCore import Qt, QAbstractTableModel, QDate
from PySide6.QtGui import QFont
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.settings import JalSettings
from jal.ui.reports.ui_tax_estimation import Ui_TaxEstimationDialog
from jal.widgets.mdi import MdiWidget
from jal.widgets.helpers import ts2d


class TaxEstimatorModel(QAbstractTableModel):
    def __init__(self, data, currency):
        QAbstractTableModel.__init__(self)
        self._data = data
        self._currency = currency

    def rowCount(self, parent=None):
        return self._data.shape[0]

    def columnCount(self, parent=None):
        return self._data.shape[1]

    def data(self, index, role=Qt.DisplayRole):
        if index.isValid():
            if role == Qt.DisplayRole:
                if index.column() == 0:
                    return self._data.iloc[index.row(), index.column()]
                elif index.column() == 2 or index.column() == 3:
                    return f"{self._data.iloc[index.row(), index.column()]:.4f}"
                elif index.column() >= 4 or index.column() <= 6:
                    return f"{self._data.iloc[index.row(), index.column()]:,.2f}"
                else:
                    return str(self._data.iloc[index.row(), index.column()])
            elif role == Qt.TextAlignmentRole:
                return int(Qt.AlignRight)
            elif role == Qt.FontRole:
                if index.row() == (self._data.shape[0] - 1):
                    bold = QFont()
                    bold.setBold(True)
                    return bold
        return None

    def headerData(self, col, orientation, role=Qt.DisplayRole):
        headers = [self.tr("Date"),
                   self.tr("Qty"),
                   self.tr("Open"),
                   self.tr("Rate, ") + self._currency + "/RUB",
                   self.tr("Profit, ") + self._currency,
                   self.tr("Profit, RUB"),
                   self.tr("Tax, RUB")]
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return headers[col]
        return None


class TaxEstimator(MdiWidget, Ui_TaxEstimationDialog):
    def __init__(self, account_id, asset_id, asset_qty, parent=None):
        super(TaxEstimator, self).__init__(parent)
        self.setupUi(self)

        self.account_id = account_id
        self.asset_id = asset_id
        self.asset_name = JalAsset(self.asset_id).symbol(JalAccount(account_id).currency())
        self.asset_qty = asset_qty
        self.dataframe = None
        self.ready = False

        self.setWindowTitle(self.tr("Tax estimation for ") + self.asset_name)

        font = self.DealsView.horizontalHeader().font()
        font.setBold(True)
        self.DealsView.horizontalHeader().setFont(font)

        self.quote = 0
        self.rate = 1
        self.currency_name = ''
        self.prepare_tax()
        if self.dataframe is None:
            return

        self.QuoteLbl.setText(f"{self.quote:.4f}")
        self.RateLbl.setText(f"{self.rate:.4f} {self.currency_name}/RUB")

        self.model = TaxEstimatorModel(self.dataframe, self.currency_name)
        self.DealsView.setModel(self.model)
        self.ready = True

    def prepare_tax(self):
        account = JalAccount(self.account_id)
        asset = JalAsset(self.asset_id)
        account_currency = JalAsset(account.currency())
        self.currency_name = account_currency.symbol()
        self.quote = asset.quote(QDate.currentDate().endOfDay(Qt.UTC).toSecsSinceEpoch(), account.currency())[1]
        self.rate = account_currency.quote(QDate.currentDate().endOfDay(Qt.UTC).toSecsSinceEpoch(),
                                           JalSettings().getValue('BaseCurrency'))[1]
        positions = account.open_trades_list(asset)
        table = []
        profit = Decimal('0')
        value = Decimal('0')
        profit_rub = Decimal('0')
        value_rub = Decimal('0')
        for position in positions:
            qty = position['remaining_qty']
            price = position['price']
            o_rate = account_currency.quote(position['operation'].settlement(),
                                            JalSettings().getValue('BaseCurrency'))[1]
            position_profit = qty * (self.quote - price)
            position_profit_rub = qty * (self.quote * self.rate - price * o_rate)
            tax = Decimal('0.13') * position_profit_rub if position_profit_rub > Decimal('0') else Decimal('0')
            table.append({
                'timestamp': ts2d(position['operation'].timestamp()),
                'qty': qty,
                'o_rate': o_rate,
                'o_price': price,
                'profit': position_profit,
                'profit_rub': position_profit_rub,
                'tax': tax
            })
            profit += position_profit
            value += qty * price
            profit_rub += position_profit_rub
            value_rub += qty * price * o_rate
        tax = Decimal('0.13') * profit_rub if profit_rub > Decimal('0') else Decimal('0')
        table.append(
            {'timestamp': self.tr("TOTAL"), 'qty': self.asset_qty, 'o_price': value / self.asset_qty,
             'o_rate': value_rub / value, 'profit': profit, 'profit_rub': profit_rub, 'tax': tax})
        data = pd.DataFrame(table)
        self.dataframe = data
