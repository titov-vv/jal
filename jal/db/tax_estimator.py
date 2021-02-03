import pandas as pd
from PySide2.QtCore import Qt, QAbstractTableModel
from PySide2.QtWidgets import QDialog, QTableView, QVBoxLayout, QFrame
from jal.db.helpers import executeSQL, readSQLrecord, get_asset_name
from jal.ui_custom.helpers import g_tr

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
                return self._data.iloc[index.row(), index.column()]
        return None

    def headerData(self, col, orientation, role=Qt.DisplayRole):
        if (orientation == Qt.Horizontal and role == Qt.DisplayRole):
            return str(self._data.columns[col])
        return None

class TaxEstimator(QDialog):
    def __init__(self, db, account_id, asset_id, asset_qty, parent=None):
        super(TaxEstimator, self).__init__(parent)
        self.db = db
        self.account_id = account_id
        self.asset_id = asset_id
        self.asset_qty = asset_qty
        self.dataframe = None

        self.setWindowTitle(g_tr('TaxEstimator', "Tax estimation for ") + get_asset_name(self.db, self.asset_id))
        self.setWindowFlag(Qt.Tool)

        self.prepareTax()

        # Create widgets
        self.deals_view = QTableView(self)
        self.deals_view.setFrameShape(QFrame.Panel)
        self.model = TaxEstimatorModel(self.dataframe)
        self.deals_view.setModel(self.model)
        # Create layout and add widgets
        self.layout = QVBoxLayout()
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.deals_view)
        # Set dialog layout
        self.setLayout(self.layout)

    def prepareTax(self):
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

        query = executeSQL(self.db,
                           "SELECT strftime('%d/%m/%Y', datetime(t.timestamp, 'unixepoch')) AS timestamp, "
                           "t.qty AS qty, t.price AS o_price, oq.quote AS o_rate, "
                           "lq.quote AS c_price, cq.quote AS c_rate FROM trades AS t "
                           "LEFT JOIN sequence AS s ON s.operation_id = t.id AND s.type = 3 "
                           "LEFT JOIN accounts AS ac ON ac.id = :account_id "
                           "LEFT JOIN t_last_dates AS od ON od.ref_id = t.settlement "
                           "LEFT JOIN quotes AS oq ON ac.currency_id=oq.asset_id AND oq.timestamp=od.timestamp "
                           "LEFT JOIN t_last_quotes AS lq ON lq.asset_id=:asset_id "
                           "LEFT JOIN t_last_quotes AS cq ON cq.asset_id=ac.currency_id "
                           "WHERE t.account_id=:account_id AND t.asset_id=:asset_id AND t.qty*(:total_qty)>0 "
                           "ORDER BY s.id DESC",
                           [(":account_id", self.account_id), (":asset_id", self.asset_id),
                            (":total_qty", self.asset_qty)])

        table = []
        while query.next():
            record = readSQLrecord(query, named=True)
            table.append(record)
        data = pd.DataFrame(table)
        self.dataframe = data
