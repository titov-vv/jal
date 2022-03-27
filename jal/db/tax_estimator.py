import logging

import pandas as pd
from PySide6.QtCore import Qt, QAbstractTableModel
from PySide6.QtGui import QFont
from jal.db.helpers import executeSQL, readSQL, readSQLrecord
from jal.db.db import JalDB
from jal.db.settings import JalSettings
from jal.ui.reports.ui_tax_estimation import Ui_TaxEstimationDialog
from jal.widgets.mdi import MdiWidget


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
        self.asset_name = JalDB().get_asset_name(self.asset_id)
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
        _ = executeSQL("DELETE FROM t_last_dates")
        _ = executeSQL("DELETE FROM t_last_quotes")

        _ = executeSQL("INSERT INTO t_last_dates(ref_id, timestamp) "
                       "SELECT ref_id, coalesce(MAX(q.timestamp), 0) AS timestamp "
                       "FROM ("
                       "SELECT t.timestamp AS ref_id FROM trades AS t "
                       "WHERE t.account_id=:account_id AND t.asset_id=:asset_id "
                       "UNION "
                       "SELECT t.settlement AS ref_id FROM trades AS t "
                       "WHERE t.account_id=:account_id AND t.asset_id=:asset_id "
                       ") LEFT JOIN accounts AS a ON a.id = :account_id "
                       "LEFT JOIN quotes AS q ON ref_id >= q.timestamp AND a.currency_id=q.asset_id AND q.currency_id=:base_currency "
                       "WHERE ref_id IS NOT NULL "
                       "GROUP BY ref_id ORDER BY ref_id",
                       [(":account_id", self.account_id), (":asset_id", self.asset_id),
                        (":base_currency", JalSettings().getValue('BaseCurrency'))])
        _ = executeSQL("INSERT INTO t_last_quotes(timestamp, asset_id, quote) "
                       "SELECT MAX(timestamp) AS timestamp, asset_id, quote "
                       "FROM quotes AS q LEFT JOIN accounts AS a ON a.id = :account_id "
                       "WHERE q.asset_id = :asset_id OR q.asset_id = a.currency_id  AND q.currency_id=:base_currency "
                       "GROUP BY asset_id",
                       [(":account_id", self.account_id), (":asset_id", self.asset_id),
                        (":base_currency", JalSettings().getValue('BaseCurrency'))])

        self.quote = readSQL("SELECT quote FROM t_last_quotes WHERE asset_id=:asset_id",
                             [(":asset_id", self.asset_id)])
        if self.quote is None:
            logging.error(self.tr("Can't get current quote for ") + self.asset_name)
            return
        self.currency_name = JalDB().get_asset_name(JalDB().get_account_currency(self.account_id))

        self.rate = readSQL("SELECT quote FROM accounts AS a "
                            "LEFT JOIN t_last_quotes AS q ON q.asset_id=a.currency_id WHERE id=:account_id",
                            [(":account_id", self.account_id)])
        if self.rate is None:
            logging.error(self.tr("Can't get current rate for ") + self.currency_name)
            return

        query = executeSQL("SELECT strftime('%d/%m/%Y', datetime(t.timestamp, 'unixepoch')) AS timestamp, "
                           "t.qty AS qty, t.price AS o_price, oq.quote AS o_rate FROM trades AS t "
                           "LEFT JOIN accounts AS ac ON ac.id = :account_id "
                           "LEFT JOIN t_last_dates AS od ON od.ref_id = IIF(t.settlement=0, t.timestamp, t.settlement) "
                           "LEFT JOIN quotes AS oq ON ac.currency_id=oq.asset_id AND oq.currency_id=:base_currency "
                           "AND oq.timestamp=od.timestamp "
                           "WHERE t.account_id=:account_id AND t.asset_id=:asset_id AND t.qty*(:total_qty)>0 "
                           "ORDER BY t.timestamp DESC, t.id DESC",
                           [(":account_id", self.account_id), (":asset_id", self.asset_id),
                            (":total_qty", self.asset_qty), (":base_currency", JalSettings().getValue('BaseCurrency'))])
        table = []
        remainder = self.asset_qty
        profit = 0
        value = 0
        profit_rub = 0
        value_rub = 0
        while query.next():
            record = readSQLrecord(query, named=True)
            record['qty'] = record['qty'] if record['qty'] <= remainder else remainder
            record['profit'] = record['qty'] * (self.quote - record['o_price'])
            record['o_rate'] = 1 if record['o_rate'] == '' else record['o_rate']
            record['profit_rub'] = record['qty'] * (self.quote * self.rate - record['o_price'] * record['o_rate'])
            record['tax'] = 0.13 * record['profit_rub'] if record['profit_rub'] > 0 else 0
            table.append(record)
            remainder -= record['qty']
            profit += record['profit']
            value += record['qty'] * record['o_price']
            profit_rub += record['profit_rub']
            value_rub += record['qty'] * record['o_price'] * record['o_rate']
            if remainder <= 0:
                break
        tax = 0.13 * profit_rub if profit_rub > 0 else 0
        table.append(
            {'timestamp': self.tr("TOTAL"), 'qty': self.asset_qty, 'o_price': value / self.asset_qty,
             'o_rate': value_rub / value,
             'profit': profit, 'profit_rub': profit_rub, 'tax': tax})
        data = pd.DataFrame(table)
        self.dataframe = data
