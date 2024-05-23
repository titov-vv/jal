import logging
from decimal import Decimal

import pandas as pd
from PySide6.QtCore import Qt, QAbstractTableModel, QDate
from PySide6.QtGui import QFont
from jal.constants import PredefinedAsset
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.country import JalCountry
from jal.ui.reports.ui_tax_estimation import Ui_TaxEstimationDialog
from jal.widgets.mdi import MdiWidget
from jal.widgets.helpers import ts2d
from jal.widgets.delegates import FloatDelegate


class TaxEstimatorModel(QAbstractTableModel):
    def __init__(self, parent_view, data, currency, tax_currency):
        super().__init__(parent_view)
        self._view = parent_view
        self._data = data
        self._currency = currency
        self._tax_currency = tax_currency
        self._columns = [self.tr("Date"),
                         self.tr("Qty"),
                         self.tr("Open"),
                         self.tr("Rate, ") + self._currency + "/" + self._tax_currency,
                         self.tr("Profit, ") + self._currency,
                         self.tr("Profit, ") + self._tax_currency,
                         self.tr("Tax, ") + self._tax_currency]
        self._float_delegate2 = None
        self._float_delegate4 = None

    def rowCount(self, parent=None):
        return self._data.shape[0]

    def columnCount(self, parent=None):
        return self._data.shape[1]

    def data(self, index, role=Qt.DisplayRole):
        if index.isValid():
            if role == Qt.DisplayRole:
                return self._data.iloc[index.row(), index.column()]
            elif role == Qt.TextAlignmentRole:
                if index.column() == 0:
                    return int(Qt.AlignLeft)
                else:
                    return int(Qt.AlignRight)
            elif role == Qt.FontRole:
                if index.row() == (self._data.shape[0] - 1):
                    bold = QFont()
                    bold.setBold(True)
                    return bold
        return None

    def headerData(self, col, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._columns[col]
        return None

    def configureView(self):
        self._float_delegate2 = FloatDelegate(2, allow_tail=False, parent=self._view)
        self._float_delegate4 = FloatDelegate(4, allow_tail=False, parent=self._view)
        self._view.setColumnWidth(0, 120)
        for i in range(1, len(self._columns)):
            self._view.setColumnWidth(i, 120)
            if i > 3:
                self._view.setItemDelegateForColumn(i, self._float_delegate2)
            else:
                self._view.setItemDelegateForColumn(i, self._float_delegate4)
        font = self._view.horizontalHeader().font()
        font.setBold(True)
        self._view.horizontalHeader().setFont(font)


class TaxEstimator(MdiWidget):
    TAX_RATE = {
        'pt': Decimal('0.28'),
        'ru': Decimal('0.13')
    }
    TAX_CURRENCY = {
        'pt': 'EUR',
        'ru': 'RUB'
    }

    def __init__(self, country_code, account_id, asset_id, asset_qty, parent=None):
        super().__init__(parent)
        self.ui = Ui_TaxEstimationDialog()
        self.ui.setupUi(self)

        self.country = JalCountry(data={'code': country_code}, search=True)
        self.account_id = account_id
        self.asset_id = asset_id
        self.asset_name = JalAsset(self.asset_id).symbol(JalAccount(account_id).currency())
        self.asset_qty = asset_qty
        self.dataframe = None
        self.ready = False
        try:
            self.tax_currency_symbol = self.TAX_CURRENCY[self.country.code()]
        except KeyError:
            self.tax_currency_symbol = ''

        self.setWindowTitle(self.tr("Tax estimation for ") + self.asset_name + " / " + self.country.name())

        self.quote = 0
        self.rate = 1
        self.currency_name = ''
        self.prepare_tax()
        if self.dataframe is None:
            return

        self.ui.QuoteLbl.setText(f"{self.quote:.4f}")
        self.ui.RateLbl.setText(f"{self.rate:.4f} {self.currency_name}/{self.tax_currency_symbol}")

        self.model = TaxEstimatorModel(self.ui.DealsView, self.dataframe, self.currency_name, self.tax_currency_symbol)
        self.ui.DealsView.setModel(self.model)
        self.model.configureView()
        self.ready = True

    def prepare_tax(self):
        try:
            tax_rate = self.TAX_RATE[self.country.code()]
        except KeyError:
            tax_rate = Decimal('0')
            logging.warning(self.tr("Tax rate not found for: ") + self.country.code())
        tax_currency = JalAsset(data={'symbol': self.tax_currency_symbol, 'type_id': PredefinedAsset.Money},
                                search=True, create=False).id()
        account = JalAccount(self.account_id)
        asset = JalAsset(self.asset_id)
        account_currency = JalAsset(account.currency())
        self.currency_name = account_currency.symbol()
        self.quote = asset.quote(QDate.currentDate().endOfDay(Qt.UTC).toSecsSinceEpoch(), account.currency())[1]
        self.rate = account_currency.quote(QDate.currentDate().endOfDay(Qt.UTC).toSecsSinceEpoch(), tax_currency)[1]
        positions = account.open_trades_list(asset)
        table = []
        profit = Decimal('0')
        value = Decimal('0')
        profit_rub = Decimal('0')
        value_rub = Decimal('0')
        for position in positions:
            qty = position.open_qty()
            price = position.open_price()
            o_rate = account_currency.quote(position.open_operation().settlement(), tax_currency)[1]
            position_profit = qty * (self.quote - price)
            position_profit_rub = qty * (self.quote * self.rate - price * o_rate)
            tax = tax_rate * position_profit_rub if position_profit_rub > Decimal('0') else Decimal('0')
            table.append({
                'timestamp': ts2d(position.open_operation().timestamp()),
                'qty': qty,
                'o_price': price,
                'o_rate': o_rate,
                'profit': position_profit,
                'profit_rub': position_profit_rub,
                'tax': tax
            })
            profit += position_profit
            value += qty * price
            profit_rub += position_profit_rub
            value_rub += qty * price * o_rate
        tax = tax_rate * profit_rub if profit_rub > Decimal('0') else Decimal('0')
        table.append(
            {'timestamp': self.tr("TOTAL"), 'qty': self.asset_qty, 'o_price': value / self.asset_qty,
             'o_rate': value_rub / value, 'profit': profit, 'profit_rub': profit_rub, 'tax': tax})
        data = pd.DataFrame(table)
        self.dataframe = data
