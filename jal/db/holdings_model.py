from PySide2.QtCore import Qt, Slot, QAbstractTableModel, QDateTime
from PySide2.QtGui import QBrush, QFont
from PySide2.QtWidgets import QHeaderView
from jal.constants import Setup, CustomColor
from jal.db.helpers import executeSQL, readSQL, get_asset_name
from jal.ui_custom.helpers import g_tr


class HoldingsModel(QAbstractTableModel):
    _columns = [g_tr('HoldingsModel', "C/A"),
                g_tr('HoldingsModel', " "),
                g_tr('HoldingsModel', "Asset"),
                g_tr('HoldingsModel', "Qty"),
                g_tr('HoldingsModel', "Open"),
                g_tr('HoldingsModel', "Last"),
                g_tr('HoldingsModel', "Share, %"),
                g_tr('HoldingsModel', "P/L, %"),
                g_tr('HoldingsModel', "P/L"),
                g_tr('HoldingsModel', "Value"),
                g_tr('HoldingsModel', "Value, ")]

    def __init__(self, parent_view, db):
        super().__init__(parent_view)
        self._view = parent_view
        self._db = db
        self._table_name = 'holdings'
        self._currency = 0
        self._currency_name = ''
        self._date = QDateTime.currentSecsSinceEpoch()

    def rowCount(self, parent=None):
        return readSQL(self._db, f"SELECT COUNT(*) FROM {self._table_name}")

    def columnCount(self, parent=None):
        return len(self._columns)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                col_name = self._columns[section] + self._currency_name if section == 10 else self._columns[section]
                return col_name
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = readSQL(self._db, f"SELECT * FROM {self._table_name} WHERE ROWID=:row",
                      [(":row", index.row() + 1)], named=True)
        if role == Qt.DisplayRole:
            return self.data_text(index.column(), row)
        if role == Qt.FontRole:
            return self.data_font(index.column(), row)
        if role == Qt.BackgroundRole:
            return self.data_background(index.column(), row)
        if role == Qt.TextAlignmentRole:
            if index.column() <= 2:
                return Qt.AlignLeft
            else:
                return Qt.AlignRight

    def data_text(self, column, data):
        if column == 0:
            if data['level1']:
                return data['currency'] + " / "  + data['asset_name']
            elif data['level2']:
                return data['account']
            else:
                return ''
        elif column == 1:
            return data['asset']
        elif column == 2:
            return data['asset_name']
        elif column == 3:
            return str(data['qty'])
        elif column == 4:
            return f"{data['open']:,.4f}" if data['open'] else ''
        elif column == 5:
            return f"{data['quote']:,.4f}" if data['quote'] else ''
        elif column == 6:
            return f"{data['share']:,.2f}" if data['share'] else ''
        elif column == 7:
            return f"{data['profit_rel']:,.2f}" if data['profit_rel'] else ''
        elif column == 8:
            return f"{data['profit']:,.2f}" if data['profit'] else ''
        elif column == 9:
            return f"{data['value']:,.2f}" if data['value'] else ''
        elif column == 10:
            return f"{data['value_adj']:,.2f}" if data['value_adj'] else ''
        else:
            assert False

    def data_font(self, _column, data):
        if data['level1'] or data['level2']:
            font = QFont()
            font.setBold(True)
            return font

    def data_background(self, column, data):
        if data['level1']:
            return QBrush(CustomColor.LightPurple)
        if data['level2']:
            return QBrush(CustomColor.LightBlue)
        if column == 7 and data['profit_rel']:
            if data['profit_rel'] >= 0:
                return QBrush(CustomColor.LightGreen)
            else:
                return QBrush(CustomColor.LightRed)
        if column == 8 and data['profit']:
            if data['profit'] >= 0:
                return QBrush(CustomColor.LightGreen)
            else:
                return QBrush(CustomColor.LightRed)

    def configureView(self):
        self._view.setColumnWidth(0, 32)
        self._view.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._view.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        for i in range(len(self._columns))[3:]:
            self._view.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        font = self._view.horizontalHeader().font()
        font.setBold(True)
        self._view.horizontalHeader().setFont(font)

    @Slot()
    def setCurrency(self, currency_id):
        if self._currency != currency_id:
            self._currency = currency_id
            self._currency_name = get_asset_name(self._db, currency_id)
            self.calculateHoldings()

    @Slot()
    def setDate(self, new_date):
        if self._date != new_date.endOfDay(Qt.UTC).toSecsSinceEpoch():
            self._date = new_date.endOfDay(Qt.UTC).toSecsSinceEpoch()
            self.calculateHoldings()

    # Populate table 'holdings' with data calculated for given parameters of model: _currency, _date,
    def calculateHoldings(self):
        _ = executeSQL(self._db, "DELETE FROM t_last_quotes")
        _ = executeSQL(self._db, "DELETE FROM t_last_assets")
        _ = executeSQL(self._db, "DELETE FROM holdings_aux")
        _ = executeSQL(self._db, "DELETE FROM holdings")
        _ = executeSQL(self._db, "INSERT INTO t_last_quotes(timestamp, asset_id, quote) "
                           "SELECT MAX(timestamp) AS timestamp, asset_id, quote "
                           "FROM quotes "
                           "WHERE timestamp <= :balances_timestamp "
                           "GROUP BY asset_id", [(":balances_timestamp", self._date)])
        _ = executeSQL(self._db, "INSERT INTO t_last_assets (id, total_value) "
                           "SELECT a.id, "
                           "SUM(CASE WHEN a.currency_id = l.asset_id THEN l.amount "
                           "ELSE (l.amount*q.quote) END) AS total_value "
                           "FROM ledger AS l "
                           "LEFT JOIN accounts AS a ON l.account_id = a.id "
                           "LEFT JOIN t_last_quotes AS q ON l.asset_id = q.asset_id "
                           "WHERE (l.book_account = 3 OR l.book_account = 4 OR l.book_account = 5) "
                           "AND a.type_id = 4 AND l.timestamp <= :holdings_timestamp "
                           "GROUP BY a.id "
                           "HAVING ABS(total_value) > :tolerance",
                       [(":holdings_timestamp", self._date), (":tolerance", Setup.DISP_TOLERANCE)])
        _ = executeSQL(self._db,
                       "INSERT INTO holdings_aux (currency, account, asset, qty, value, quote, quote_adj, total, total_adj) "
                       "SELECT a.currency_id, l.account_id, l.asset_id, sum(l.amount) AS qty, sum(l.value), "
                       "q.quote, q.quote*cur_q.quote/cur_adj_q.quote, t.total_value, t.total_value*cur_q.quote/cur_adj_q.quote "
                       "FROM ledger AS l "
                       "LEFT JOIN accounts AS a ON l.account_id = a.id "
                       "LEFT JOIN t_last_quotes AS q ON l.asset_id = q.asset_id "
                       "LEFT JOIN t_last_quotes AS cur_q ON a.currency_id = cur_q.asset_id "
                       "LEFT JOIN t_last_quotes AS cur_adj_q ON cur_adj_q.asset_id = :recalc_currency "
                       "LEFT JOIN t_last_assets AS t ON l.account_id = t.id "
                       "WHERE l.book_account = 4 AND l.timestamp <= :holdings_timestamp "
                       "GROUP BY l.account_id, l.asset_id "
                       "HAVING ABS(qty) > :tolerance",
                       [(":recalc_currency", self._currency), (":holdings_timestamp", self._date),
                        (":tolerance", Setup.DISP_TOLERANCE)])
        _ = executeSQL(self._db,
                       "INSERT INTO holdings_aux (currency, account, asset, qty, value, quote, quote_adj, total, total_adj) "
                       "SELECT a.currency_id, l.account_id, l.asset_id, sum(l.amount) AS qty, sum(l.value), 1, "
                       "cur_q.quote/cur_adj_q.quote, t.total_value, t.total_value*cur_q.quote/cur_adj_q.quote "
                       "FROM ledger AS l "
                       "LEFT JOIN accounts AS a ON l.account_id = a.id "
                       "LEFT JOIN t_last_quotes AS cur_q ON a.currency_id = cur_q.asset_id "
                       "LEFT JOIN t_last_quotes AS cur_adj_q ON cur_adj_q.asset_id = :recalc_currency "
                       "LEFT JOIN t_last_assets AS t ON l.account_id = t.id "
                       "WHERE (l.book_account = 3 OR l.book_account = 5) AND a.type_id = 4 AND l.timestamp <= :holdings_timestamp "
                       "GROUP BY l.account_id, l.asset_id "
                       "HAVING ABS(qty) > :tolerance",
                       [(":recalc_currency", self._currency), (":holdings_timestamp", self._date),
                        (":tolerance", Setup.DISP_TOLERANCE)])
        _ = executeSQL(self._db,
                       "INSERT INTO holdings (level1, level2, currency, account, asset, asset_name, "
                       "qty, open, quote, share, profit_rel, profit, value, value_adj) "
                       "SELECT * FROM ( "
                       "SELECT 0 AS level1, 0 AS level2, c.name AS currency, a.name AS account, "
                       "s.name AS asset, s.full_name AS asset_name, "
                       "h.qty, h.value/h.qty AS open, h.quote, 100*h.quote*h.qty/h.total AS share, "
                       "100*(h.quote*h.qty/h.value-1) AS profit_rel, h.quote*h.qty-h.value AS profit, "
                       "h.qty*h.quote AS value, h.qty*h.quote_adj AS value_adj "
                       "FROM holdings_aux AS h "
                       "LEFT JOIN assets AS c ON h.currency = c.id "
                       "LEFT JOIN accounts AS a ON h.account = a.id "
                       "LEFT JOIN assets AS s ON h.asset = s.id "
                       "UNION "
                       "SELECT 0 AS level1, 1 AS level2, c.name AS currency, "
                       "a.name AS account, '' AS asset, '' AS asset_name, "
                       "NULL AS qty, NULL AS open, NULL as quote, NULL AS share, "
                       "100*SUM(h.quote*h.qty-h.value)/(SUM(h.qty*h.quote)-SUM(h.quote*h.qty-h.value)) AS profit_rel, "
                       "SUM(h.quote*h.qty-h.value) AS profit, SUM(h.qty*h.quote) AS value, "
                       "SUM(h.qty*h.quote_adj) AS value_adj "
                       "FROM holdings_aux AS h "
                       "LEFT JOIN assets AS c ON h.currency = c.id "
                       "LEFT JOIN accounts AS a ON h.account = a.id "
                       "GROUP BY currency, account "
                       "UNION "
                       "SELECT 1 AS level1, 1 AS level2, c.name AS currency, '' AS account, '' AS asset, "
                       "c.full_name AS asset_name, NULL AS qty, NULL AS open, NULL as quote, NULL AS share, "
                       "100*SUM(h.quote*h.qty-h.value)/(SUM(h.qty*h.quote)-SUM(h.quote*h.qty-h.value)) AS profit_rel, "
                       "SUM(h.quote*h.qty-h.value) AS profit, SUM(h.qty*h.quote) AS value, "
                       "SUM(h.qty*h.quote_adj) AS value_adj "
                       "FROM holdings_aux AS h "
                       "LEFT JOIN assets AS c ON h.currency = c.id "
                       "GROUP BY currency "
                       ") ORDER BY currency, level1 DESC, account, level2 DESC")