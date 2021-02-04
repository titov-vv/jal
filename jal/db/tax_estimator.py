import pandas as pd
from PySide2.QtCore import Qt, QAbstractTableModel
from PySide2.QtWidgets import QDialog
from jal.db.helpers import executeSQL, readSQL, readSQLrecord, get_asset_name
from jal.ui_custom.helpers import g_tr
from jal.ui.ui_tax_estimation import Ui_TaxEstimationDialog

class TaxEstimatorModel(QAbstractTableModel):
    def __init__(self, data):
        QAbstractTableModel.__init__(self)
        self._data = data

    def rowCount(self, parent=None):
        return self._data.shape[0]

    def columnCount(self, parent=None):
        return self._data.shape[1]

    def data(self, index, role=Qt.DisplayRole):
        if index.isValid():
            if role == Qt.DisplayRole:
                return str(self._data.iloc[index.row(), index.column()])
        return None

    def headerData(self, col, orientation, role=Qt.DisplayRole):
        if (orientation == Qt.Horizontal and role == Qt.DisplayRole):
            return str(self._data.columns[col])
        return None

class TaxEstimator(QDialog, Ui_TaxEstimationDialog):
    def __init__(self, db, account_id, asset_id, asset_qty, parent=None):
        super(TaxEstimator, self).__init__(parent)
        self.setupUi(self)

        self.db = db
        self.account_id = account_id
        self.asset_id = asset_id
        self.asset_qty = asset_qty
        self.dataframe = None

        self.setWindowTitle(g_tr('TaxEstimator', "Tax estimation for ") + get_asset_name(self.db, self.asset_id))
        self.setWindowFlag(Qt.Tool)

        self.quote = 0
        self.rate = 1
        self.prepare_tax()
        self.QuoteLbl.setText(f"{self.quote:.4f}")
        self.RateLbl.setText(f"{self.rate:.4f}")

        self.model = TaxEstimatorModel(self.dataframe)
        self.DealsView.setModel(self.model)

    def prepare_tax(self):
        _ = executeSQL(self.db, "DELETE FROM t_last_dates")
        _ = executeSQL(self.db, "DELETE FROM t_last_quotes")

        _ = executeSQL(self.db,
                       "INSERT INTO t_last_dates(ref_id, timestamp) "
                       "SELECT ref_id, coalesce(MAX(q.timestamp), 0) AS timestamp "
                       "FROM ("
                       "SELECT t.settlement AS ref_id FROM trades AS t "
                       "WHERE t.account_id=:account_id AND t.asset_id=:asset_id"
                       ") LEFT JOIN accounts AS a ON a.id = :account_id "
                       "LEFT JOIN quotes AS q ON ref_id >= q.timestamp AND a.currency_id=q.asset_id "
                       "WHERE ref_id IS NOT NULL "
                       "GROUP BY ref_id",
                       [(":account_id", self.account_id), (":asset_id", self.asset_id)])
        _ = executeSQL(self.db,
                       "INSERT INTO t_last_quotes(timestamp, asset_id, quote) "
                       "SELECT MAX(timestamp) AS timestamp, asset_id, quote "
                       "FROM quotes AS q LEFT JOIN accounts AS a ON a.id = :account_id "
                       "WHERE q.asset_id = :asset_id OR q.asset_id = a.currency_id "
                       "GROUP BY asset_id",
                       [(":account_id", self.account_id), (":asset_id", self.asset_id)])

        self.quote = readSQL(self.db, "SELECT quote FROM t_last_quotes WHERE asset_id=:asset_id",
                             [(":asset_id", self.asset_id)])
        self.rate = readSQL(self.db, "SELECT quote FROM accounts AS a "
                                     "LEFT JOIN t_last_quotes AS q ON q.asset_id=a.currency_id WHERE id=:account_id",
                            [(":account_id", self.account_id)])

        query = executeSQL(self.db,
                           "SELECT strftime('%d/%m/%Y', datetime(t.timestamp, 'unixepoch')) AS timestamp, "
                           "t.qty AS qty, t.price AS o_price, oq.quote AS o_rate FROM trades AS t "
                           "LEFT JOIN sequence AS s ON s.operation_id = t.id AND s.type = 3 "
                           "LEFT JOIN accounts AS ac ON ac.id = :account_id "
                           "LEFT JOIN t_last_dates AS od ON od.ref_id = t.settlement "
                           "LEFT JOIN quotes AS oq ON ac.currency_id=oq.asset_id AND oq.timestamp=od.timestamp "
                           "WHERE t.account_id=:account_id AND t.asset_id=:asset_id AND t.qty*(:total_qty)>0 "
                           "ORDER BY s.id DESC",
                           [(":account_id", self.account_id), (":asset_id", self.asset_id),
                            (":total_qty", self.asset_qty)])
        table = []
        remainder = self.asset_qty
        profit = 0
        value = 0
        profit_rub = 0
        value_rub = 0
        tax = 0
        while query.next():
            record = readSQLrecord(query, named=True)
            record['qty'] = record['qty'] if record['qty'] >= remainder else remainder
            record['profit'] = record['qty'] * (self.quote - record['o_price'])
            record['profit_rub'] = record['qty'] * (self.quote * self.rate - record['o_price'] * record['o_rate'])
            record['tax'] = 0.13 * record['profit_rub']
            table.append(record)
            remainder -= record['qty']
            profit += record['profit']
            value += record['qty'] * record['o_price']
            profit_rub += record['profit_rub']
            value_rub += record['qty'] * record['o_price'] * record['o_rate']
            tax += record['tax']
            if remainder <= 0:
                break
        table.append(
            {'timestamp': g_tr("TaxEstimator", "TOTAL"), 'qty': self.asset_qty, 'o_price': value / self.asset_qty,
             'o_rate': value_rub / value,
             'profit': profit, 'profit_rub': profit_rub, 'tax': tax})
        data = pd.DataFrame(table)
        self.dataframe = data
