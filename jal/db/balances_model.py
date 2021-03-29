from PySide2.QtCore import Qt, Slot, QAbstractTableModel, QDate
from PySide2.QtGui import QBrush, QFont
from PySide2.QtWidgets import QHeaderView
from jal.constants import Setup, CustomColor, BookAccount
from jal.widgets.helpers import g_tr
from jal.db.helpers import executeSQL
from jal.db.update import JalDB


class BalancesModel(QAbstractTableModel):
    COL_LEVEL = 0
    COL_TYPE = 1
    COL_TYPE_NAME = 2
    COL_ACCOUNT = 3
    COL_ACCOUNT_NAME = 4
    COL_CURRENCY = 5
    COL_CURRENCY_NAME = 6
    COL_AMOUNT = 7
    COL_AMOUNT_A = 8
    COL_UNRECONCILED = 9
    COL_ACTIVE = 10

    def __init__(self, parent_view):
        super().__init__(parent_view)
        self._view = parent_view
        self._data = []
        self._currency = 0
        self._currency_name = ''
        self._active_only = True
        self._date = QDate.currentDate().endOfDay(Qt.UTC).toSecsSinceEpoch()
        self._columns = [g_tr('BalancesModel', "Account"),
                         g_tr('BalancesModel', "Balance"),
                         " ",
                         g_tr('BalancesModel', "Balance, ")]

    def rowCount(self, parent=None):
        return len(self._data)

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
        if role == Qt.DisplayRole:
            return self.data_text(index.row(), index.column())
        if role == Qt.FontRole:
            return self.data_font(index.row(), index.column())
        if role == Qt.BackgroundRole:
            return self.data_background(index.row(), index.column())
        if role == Qt.TextAlignmentRole:
            if index.column() == 0 or index.column() == 2:
                return Qt.AlignLeft
            else:
                return Qt.AlignRight
        return None

    def data_text(self, row, column):
        if column == 0:
            if self._data[row][self.COL_LEVEL] == 0:
                return self._data[row][self.COL_ACCOUNT_NAME]
            else:
                return self._data[row][self.COL_TYPE_NAME]
        elif column == 1:
            return f"{self._data[row][self.COL_AMOUNT]:,.2f}" if self._data[row][self.COL_AMOUNT] != 0 else ''
        elif column == 2:
            return self._data[row][self.COL_CURRENCY_NAME] if self._data[row][self.COL_AMOUNT] != 0 else ''
        elif column == 3:
            return f"{self._data[row][self.COL_AMOUNT_A]:,.2f}" if self._data[row][self.COL_AMOUNT_A] != 0 else ''
        else:
            assert False

    def data_font(self, row, column):
        if self._data[row][self.COL_LEVEL] > 0:
            font = QFont()
            font.setBold(True)
            return font
        if column == 0 and not self._data[row][self.COL_ACTIVE]:
            font = QFont()
            font.setItalic(True)
            return font

    def data_background(self, row, column):
        if column == 3:
            if self._data[row][self.COL_UNRECONCILED] > 15:
                return QBrush(CustomColor.LightRed)
            if self._data[row][self.COL_UNRECONCILED] > 7:
                return QBrush(CustomColor.LightYellow)

    def configureView(self):
        self._view.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for i in range(len(self._columns))[1:]:
            self._view.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        font = self._view.horizontalHeader().font()
        font.setBold(True)
        self._view.horizontalHeader().setFont(font)

    @Slot()
    def setCurrency(self, currency_id):
        if self._currency != currency_id:
            self._currency = currency_id
            self._currency_name = JalDB().get_asset_name(currency_id)
            self.calculateBalances()

    @Slot()
    def setDate(self, new_date):
        if self._date != new_date.endOfDay(Qt.UTC).toSecsSinceEpoch():
            self._date = new_date.endOfDay(Qt.UTC).toSecsSinceEpoch()
            self.calculateBalances()

    @Slot()
    def toggleActive(self, state):
        if state == 0:
            self._active_only = True
        else:
            self._active_only = False
        self.calculateBalances()

    def getAccountId(self, row):
        return self._data[row][self.COL_ACCOUNT]

    def update(self):
        self.calculateBalances()

    # Populate table balances with data calculated for given parameters of model: _currency, _date, _active_only
    def calculateBalances(self):
        query = executeSQL(
            "WITH "
            "_last_quotes AS (SELECT MAX(timestamp) AS timestamp, asset_id, quote "
            "FROM quotes WHERE timestamp <= :balances_timestamp GROUP BY asset_id), "
            "_last_dates AS (SELECT account_id AS ref_id, MAX(timestamp) AS timestamp "
            "FROM ledger WHERE timestamp <= :balances_timestamp GROUP BY ref_id) "
            "SELECT a.type_id AS account_type, t.name AS type_name, l.account_id AS account, "
            "a.name AS account_name, a.currency_id AS currency, c.name AS currency_name, "
            "SUM(CASE WHEN l.book_account=:assets_book THEN l.amount*act_q.quote ELSE l.amount END) AS balance, "
            "SUM(CASE WHEN l.book_account=:assets_book THEN l.amount*coalesce(act_q.quote*cur_q.quote/cur_adj_q.quote, 0) "
            "ELSE l.amount*coalesce(cur_q.quote/cur_adj_q.quote, 0) END) AS balance_adj, "
            "(d.timestamp - coalesce(a.reconciled_on, 0))/86400 AS unreconciled_days, "
            "a.active AS active "
            "FROM ledger AS l "
            "LEFT JOIN accounts AS a ON l.account_id = a.id "
            "LEFT JOIN assets AS c ON c.id = a.currency_id "
            "LEFT JOIN account_types AS t ON a.type_id = t.id "
            "LEFT JOIN _last_quotes AS act_q ON l.asset_id = act_q.asset_id "
            "LEFT JOIN _last_quotes AS cur_q ON a.currency_id = cur_q.asset_id "
            "LEFT JOIN _last_quotes AS cur_adj_q ON cur_adj_q.asset_id = :base_currency "
            "LEFT JOIN _last_dates AS d ON l.account_id = d.ref_id "
            "WHERE (book_account=:money_book OR book_account=:assets_book OR book_account=:liabilities_book) "
            "AND l.timestamp <= :balances_timestamp "
            "GROUP BY l.account_id "
            "HAVING ABS(balance)>:tolerance "
            "ORDER BY account_type",
            [(":base_currency", self._currency), (":money_book", BookAccount.Money),
             (":assets_book", BookAccount.Assets), (":liabilities_book", BookAccount.Liabilities),
             (":balances_timestamp", self._date), (":tolerance", Setup.DISP_TOLERANCE)],
            forward_only=True)
        self._data = []
        current_type = 0
        current_type_name = ''
        indexes = range(query.record().count())
        while query.next():
            values = [0] + list(map(query.value, indexes))
            if self._active_only and (values[self.COL_ACTIVE] == 0):
                continue
            if values[self.COL_TYPE] != current_type:
                if current_type != 0:
                    sub_total = sum([row[self.COL_AMOUNT_A] for row in self._data if row[self.COL_TYPE] == current_type])
                    self._data.append([1, current_type, current_type_name, 0, '', 0, '', 0, sub_total, 0, 1])
                current_type = values[self.COL_TYPE]
                current_type_name = values[self.COL_TYPE_NAME]
            self._data.append(values)
        if current_type != 0:
            sub_total = sum([row[self.COL_AMOUNT_A] for row in self._data if row[self.COL_TYPE] == current_type])
            self._data.append([1, current_type, current_type_name, 0, '', 0, '', 0, sub_total, 0, 1])
        total_sum = sum([row[self.COL_AMOUNT_A] for row in self._data if row[self.COL_LEVEL] == 0])
        self._data.append([2, 0, g_tr("BalancesModel", "Total"), 0, '', 0, '', 0, total_sum, 0, 1])
        self.modelReset.emit()

