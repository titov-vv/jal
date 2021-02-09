from PySide2.QtCore import Qt, Slot, QAbstractTableModel, QDateTime
from PySide2.QtGui import QBrush, QFont
from PySide2.QtWidgets import QHeaderView
from jal.constants import CustomColor, BookAccount
from jal.ui_custom.helpers import g_tr
from jal.db.helpers import executeSQL, readSQL, get_asset_name


class BalancesModel(QAbstractTableModel):
    _columns = [g_tr('BalancesModel', "Account"),
                g_tr('BalancesModel', "Balance"),
                " ",
                g_tr('BalancesModel', "Balance, ")]

    def __init__(self, parent, db):
        super().__init__(parent)
        self._parent = parent
        self._db = db
        self._table_name = 'balances'
        self._currency = 0
        self._currency_name = ''
        self._active_only = 1
        self._date = QDateTime.currentSecsSinceEpoch()

    def rowCount(self, parent=None):
        return readSQL(self._db, f"SELECT COUNT(*) FROM {self._table_name}")

    def columnCount(self, parent=None):
        return len(self._columns)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                col_name = self._columns[section] + self._currency_name if section == 3 else self._columns[section]
                return col_name
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        row = readSQL(self._db, "SELECT * FROM balances WHERE ROWID=:row", [(":row", index.row()+1)], named=True)
        if role == Qt.DisplayRole:
            return self.data_text(index.column(), row)
        if role == Qt.FontRole:
            return self.data_font(index.column(), row)
        if role == Qt.BackgroundRole:
            return self.data_background(index.column(), row)
        if role == Qt.TextAlignmentRole:
            if index.column() == 0 or index.column() == 2:
                return Qt.AlignLeft
            else:
                return Qt.AlignRight

    def data_text(self, column, data):
        if column == 0:
            return data['account_name']
        elif column == 1:
            return f"{data['balance']:,.2f}" if data['balance'] != 0 else ''
        elif column == 2:
            return data['currency_name'] if data['balance'] != 0 else ''
        elif column == 3:
            return f"{data['balance_adj']:,.2f}" if data['balance_adj'] != 0 else ''
        else:
            assert False

    def data_font(self, column, data):
        if (column == 0 or column == 3) and data['balance'] == 0:
            font = QFont()
            font.setBold(True)
            return font
        if column == 0 and not data['active']:
            font = QFont()
            font.setItalic(True)
            return font

    def data_background(self, column, data):
        if column == 3:
            if data['days_unreconciled'] > 15:
                return QBrush(CustomColor.LightRed)
            if data['days_unreconciled'] > 7:
                return QBrush(CustomColor.LightYellow)

    def configureHeader(self, view):
        view.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for i in range(len(self._columns))[1:]:
            view.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        font = view.horizontalHeader().font()
        font.setBold(True)
        view.horizontalHeader().setFont(font)

    @Slot()
    def setCurrency(self, currency_id):
        if self._currency != currency_id:
            self._currency = currency_id
            self._currency_name = get_asset_name(self._db, currency_id)
            self.calculateBalances()

    @Slot()
    def setDate(self, new_date):
        if self._date != new_date.endOfDay(Qt.UTC).toSecsSinceEpoch():
            self._date = new_date.endOfDay(Qt.UTC).toSecsSinceEpoch()
            self.calculateBalances()

    @Slot()
    def toggleActive(self, state):
        if state == 0:
            self._active_only = 1
        else:
            self._active_only = 0
        self.calculateBalances()

    # Populate table balances with data calculated for given parameters of model: _currency, _date, _active_only
    def calculateBalances(self):
        _ = executeSQL(self._db, "DELETE FROM t_last_quotes")
        _ = executeSQL(self._db, "DELETE FROM t_last_dates")
        _ = executeSQL(self._db, "DELETE FROM balances_aux")
        _ = executeSQL(self._db, "DELETE FROM balances")
        _ = executeSQL(self._db, "INSERT INTO t_last_quotes(timestamp, asset_id, quote) "
                           "SELECT MAX(timestamp) AS timestamp, asset_id, quote "
                           "FROM quotes "
                           "WHERE timestamp <= :balances_timestamp "
                           "GROUP BY asset_id", [(":balances_timestamp", self._date)])
        _ = executeSQL(self._db, "INSERT INTO t_last_dates(ref_id, timestamp) "
                           "SELECT account_id AS ref_id, MAX(timestamp) AS timestamp "
                           "FROM ledger "
                           "WHERE timestamp <= :balances_timestamp "
                           "GROUP BY ref_id", [(":balances_timestamp", self._date)])
        _ = executeSQL(self._db,
                       "INSERT INTO balances_aux(account_type, account, currency, balance, "
                       "balance_adj, unreconciled_days, active) "
                       "SELECT a.type_id AS account_type, l.account_id AS account, a.currency_id AS currency, "
                       "SUM(CASE WHEN l.book_account=4 THEN l.amount*act_q.quote ELSE l.amount END) AS balance, "
                       "SUM(CASE WHEN l.book_account=4 THEN l.amount*coalesce(act_q.quote*cur_q.quote/cur_adj_q.quote, 0) "
                       "ELSE l.amount*coalesce(cur_q.quote/cur_adj_q.quote, 0) END) AS balance_adj, "
                       "(d.timestamp - coalesce(a.reconciled_on, 0))/86400 AS unreconciled_days, "
                       "a.active AS active "
                       "FROM ledger AS l "
                       "LEFT JOIN accounts AS a ON l.account_id = a.id "
                       "LEFT JOIN t_last_quotes AS act_q ON l.asset_id = act_q.asset_id "
                       "LEFT JOIN t_last_quotes AS cur_q ON a.currency_id = cur_q.asset_id "
                       "LEFT JOIN t_last_quotes AS cur_adj_q ON cur_adj_q.asset_id = :base_currency "
                       "LEFT JOIN t_last_dates AS d ON l.account_id = d.ref_id "
                       "WHERE (book_account = :money_book OR book_account = :assets_book OR book_account = :liabilities_book) "
                       "AND l.timestamp <= :balances_timestamp "
                       "GROUP BY l.account_id "
                       "HAVING ABS(balance)>0.0001",
                       [(":base_currency", self._currency), (":money_book", BookAccount.Money),
                        (":assets_book", BookAccount.Assets), (":liabilities_book", BookAccount.Liabilities),
                        (":balances_timestamp", self._date)])
        _ = executeSQL(self._db,
                       "INSERT INTO balances(level1, level2, account_name, currency_name, "
                       "balance, balance_adj, days_unreconciled, active) "
                       "SELECT  level1, level2, account, currency, balance, balance_adj, unreconciled_days, active "
                       "FROM ( "
                       "SELECT 0 AS level1, 0 AS level2, account_type, a.name AS account, c.name AS currency, "
                       "balance, balance_adj, unreconciled_days, b.active "
                       "FROM balances_aux AS b LEFT JOIN accounts AS a ON b.account = a.id "
                       "LEFT JOIN assets AS c ON b.currency = c.id "
                       "WHERE b.active >= :active_only "
                       "UNION "
                       "SELECT 0 AS level1, 1 AS level2, account_type, t.name AS account, c.name AS currency, "
                       "0 AS balance, SUM(balance_adj) AS balance_adj, 0 AS unreconciled_days, 1 AS active "
                       "FROM balances_aux AS b LEFT JOIN account_types AS t ON b.account_type = t.id "
                       "LEFT JOIN assets AS c ON c.id = :base_currency "
                       "WHERE active >= :active_only "
                       "GROUP BY account_type "
                       "UNION "
                       "SELECT 1 AS level1, 0 AS level2, -1 AS account_type, 'Total' AS account, c.name AS currency, "
                       "0 AS balance, SUM(balance_adj) AS balance_adj, 0 AS unreconciled_days, 1 AS active "
                       "FROM balances_aux LEFT JOIN assets AS c ON c.id = :base_currency "
                       "WHERE active >= :active_only "
                       ") ORDER BY level1, account_type, level2",
                       [(":base_currency", self._currency), (":active_only", self._active_only)])
        self._db.commit()
        self.modelReset.emit()