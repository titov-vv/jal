from PySide2.QtCore import Qt, Slot, QAbstractItemModel, QDate, QModelIndex
from PySide2.QtGui import QBrush, QFont
from PySide2.QtWidgets import QHeaderView
from jal.constants import Setup, CustomColor, BookAccount, PredefindedAccountType
from jal.db.helpers import executeSQL
from jal.db.update import JalDB
from jal.widgets.helpers import g_tr
from jal.widgets.delegates import GridLinesDelegate


class TreeItem():
    def __init__(self, data, parent=None):
        self._parent = parent
        self.data = data[:]
        self._children = []

    def appendChild(self, child):
        child.setParent(self)
        self._children.append(child)

    def getChild(self, id):
        if id < 0 or id > len(self._children):
            return None
        return self._children[id]

    def count(self):
        return len(self._children)

    def setParent(self, parent):
        self._parent = parent

    def getParent(self):
        return self._parent


class HoldingsModel(QAbstractItemModel):
    DATA_COL = 13
    COL_LEVEL = 0
    COL_CURRENCY = 1
    COL_CURRENCY_NAME = 2
    COL_ACCOUNT = 3
    COL_ACCOUNT_NAME = 4
    COL_ASSET = 5
    COL_ASSET_IS_CURRENCY = 6
    COL_ASSET_NAME = 7
    COL_ASSET_FULLNAME = 8
    COL_QTY = 9
    COL_VALUE_I = 10
    COL_QUOTE = 11
    COL_QUOTE_A = 12
    COL_TOTAL = 13
    COL_SHARE = 14
    COL_PROFIT = 15
    COL_PROFIT_R = 16
    COL_VALUE = 17
    COL_VALUE_A = 18

    def __init__(self, parent_view):
        super().__init__(parent_view)
        self._view = parent_view
        self._grid_delegate = None
        self._root = None
        self._currency = 0
        self._currency_name = ''
        self._date = QDate.currentDate().endOfDay(Qt.UTC).toSecsSinceEpoch()
        self._columns = [g_tr('HoldingsModel', "Currency/Account/Asset"),
                         g_tr('HoldingsModel', "Asset Name"),
                         g_tr('HoldingsModel', "Qty"),
                         g_tr('HoldingsModel', "Open"),
                         g_tr('HoldingsModel', "Last"),
                         g_tr('HoldingsModel', "Share, %"),
                         g_tr('HoldingsModel', "P/L, %"),
                         g_tr('HoldingsModel', "P/L"),
                         g_tr('HoldingsModel', "Value"),
                         g_tr('HoldingsModel', "Value, ")]

    def rowCount(self, parent=None):
        if not parent.isValid():
            parent_item = self._root
        else:
            parent_item = parent.internalPointer()
        if parent_item is not None:
            return parent_item.count()
        else:
            return 0

    def columnCount(self, parent=None):
        return len(self._columns)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                col_name = self._columns[section] + self._currency_name if section == 9 else self._columns[section]
                return col_name
        return None

    def index(self, row, column, parent=None):
        if not parent.isValid():
            parent = self._root
        else:
            parent = parent.internalPointer()
        child = parent.getChild(row)
        if child:
            return self.createIndex(row, column, child)
        return QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()
        child_item = index.internalPointer()
        parent_item = child_item.getParent()
        if parent_item == self._root:
            return QModelIndex()
        return self.createIndex(0, 0, parent_item)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        item = index.internalPointer()
        if role == Qt.DisplayRole:
            return self.data_text(item.data, index.column())
        if role == Qt.FontRole:
            return self.data_font(item.data, index.column())
        if role == Qt.BackgroundRole:
            return self.data_background(item.data, index.column())
        if role == Qt.TextAlignmentRole:
            if index.column() < 2:
                return Qt.AlignLeft
            else:
                return Qt.AlignRight
        return None

    def data_text(self, data, column):
        if column == 0:
            if data[self.COL_LEVEL] == 0:
                return data[self.COL_CURRENCY_NAME]
            elif data[self.COL_LEVEL] == 1:
                return data[self.COL_ACCOUNT_NAME]
            else:
                return data[self.COL_ASSET_NAME]
        elif column == 1:
            return data[self.COL_ASSET_FULLNAME]
        elif column == 2:
            return str(data[self.COL_QTY]) if data[self.COL_QTY] != 0 else ''
        elif column == 3:
            if data[self.COL_QTY] != 0 and data[self.COL_VALUE_I] != 0:
                return f"{(data[self.COL_VALUE_I] / data[self.COL_QTY]):,.4f}"
            else:
                return ''
        elif column == 4:
            return f"{data[self.COL_QUOTE]:,.4f}" if data[self.COL_QUOTE] and data[self.COL_QTY] != 0 else ''
        elif column == 5:
            return f"{data[self.COL_SHARE]:,.2f}" if data[self.COL_SHARE] else '-.--'
        elif column == 6:
            return f"{100.0 * data[self.COL_PROFIT_R]:,.2f}" if data[self.COL_PROFIT_R] else ''
        elif column == 7:
            return f"{data[self.COL_PROFIT]:,.2f}" if data[self.COL_PROFIT] else ''
        elif column == 8:
            return f"{data[self.COL_VALUE]:,.2f}" if data[self.COL_VALUE] else ''
        elif column == 9:
            return f"{data[self.COL_VALUE_A]:,.2f}" if data[self.COL_VALUE_A] else '-.--'
        else:
            assert False

    def data_font(self, data, _column):
        if data[self.COL_LEVEL] < 2:
            font = QFont()
            font.setBold(True)
            return font

    def data_background(self, data, column):
        if data[self.COL_LEVEL] == 0:
            return QBrush(CustomColor.LightPurple)
        if data[self.COL_LEVEL] == 1:
            return QBrush(CustomColor.LightBlue)
        if column == 6 and data[self.COL_PROFIT_R]:
            if data[self.COL_PROFIT_R] >= 0:
                return QBrush(CustomColor.LightGreen)
            else:
                return QBrush(CustomColor.LightRed)
        if column == 7 and data[self.COL_PROFIT]:
            if data[self.COL_PROFIT] >= 0:
                return QBrush(CustomColor.LightGreen)
            else:
                return QBrush(CustomColor.LightRed)

    def configureView(self):
        self._view.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._view.header().setSectionResizeMode(1, QHeaderView.Stretch)
        for i in range(len(self._columns))[2:]:
            self._view.header().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self._grid_delegate = GridLinesDelegate(self._view)
        for i in range(len(self._columns)):
            self._view.setItemDelegateForColumn(i, self._grid_delegate)
        font = self._view.header().font()
        font.setBold(True)
        self._view.header().setFont(font)

    @Slot()
    def setCurrency(self, currency_id):
        if self._currency != currency_id:
            self._currency = currency_id
            self._currency_name = JalDB().get_asset_name(currency_id)
            self.calculateHoldings()

    @Slot()
    def setDate(self, new_date):
        if self._date != new_date.endOfDay(Qt.UTC).toSecsSinceEpoch():
            self._date = new_date.endOfDay(Qt.UTC).toSecsSinceEpoch()
            self.calculateHoldings()

    def get_data_for_tax(self, index):
        if not index.isValid():
            return None
        item = index.internalPointer()
        return item.data[self.COL_ACCOUNT], item.data[self.COL_ASSET], item.data[self.COL_QTY]

    def update(self):
        self.calculateHoldings()

    # Populate table 'holdings' with data calculated for given parameters of model: _currency, _date,
    def calculateHoldings(self):
        query = executeSQL(
            "WITH "
            "_last_quotes AS (SELECT MAX(timestamp) AS timestamp, asset_id, quote "
            "FROM quotes WHERE timestamp <= :holdings_timestamp GROUP BY asset_id), "
            "_last_assets AS ("
            "SELECT id, SUM(t_value) AS total_value "
            "FROM "
            "("
            "SELECT a.id, SUM(l.amount) AS t_value "
            "FROM ledger AS l "
            "LEFT JOIN accounts AS a ON l.account_id = a.id "
            "WHERE (l.book_account=:money_book OR l.book_account=:liabilities_book) "
            "AND a.type_id = :investments AND l.timestamp <= :holdings_timestamp GROUP BY a.id "
            "UNION ALL "
            "SELECT a.id, SUM(l.amount*q.quote) AS t_value "
            "FROM ledger AS l "
            "LEFT JOIN accounts AS a ON l.account_id = a.id "
            "LEFT JOIN _last_quotes AS q ON l.asset_id = q.asset_id "
            "WHERE l.book_account=:assets_book AND a.type_id = :investments AND l.timestamp <= :holdings_timestamp "
            "GROUP BY a.id"
            ") "
            "GROUP BY id HAVING ABS(total_value) > :tolerance) "
            "SELECT h.currency_id, c.name AS currency, h.account_id, h.account, h.asset_id, "
            "c.name=a.name AS asset_is_currency,  a.name AS asset, a.full_name AS asset_name, "
            "h.qty, h.value, h.quote, h.quote_a, h.total FROM ("
            "SELECT a.currency_id, l.account_id, a.name AS account, l.asset_id, sum(l.amount) AS qty, "
            "sum(l.value) AS value, q.quote, q.quote*cur_q.quote/cur_adj_q.quote AS quote_a, t.total_value AS total "
            "FROM ledger AS l "
            "LEFT JOIN accounts AS a ON l.account_id = a.id "
            "LEFT JOIN _last_quotes AS q ON l.asset_id = q.asset_id "
            "LEFT JOIN _last_quotes AS cur_q ON a.currency_id = cur_q.asset_id "
            "LEFT JOIN _last_quotes AS cur_adj_q ON cur_adj_q.asset_id = :base_currency "
            "LEFT JOIN _last_assets AS t ON l.account_id = t.id "
            "WHERE a.type_id = :investments AND l.book_account = :assets_book AND l.timestamp <= :holdings_timestamp "
            "GROUP BY l.account_id, l.asset_id "
            "HAVING ABS(qty) > :tolerance "
            "UNION ALL "
            "SELECT a.currency_id, l.account_id, a.name AS account, l.asset_id, sum(l.amount) AS qty, "
            "0 AS value, 1, cur_q.quote/cur_adj_q.quote AS quote_a, t.total_value AS total "
            "FROM ledger AS l "
            "LEFT JOIN accounts AS a ON l.account_id = a.id "
            "LEFT JOIN _last_quotes AS cur_q ON a.currency_id = cur_q.asset_id "
            "LEFT JOIN _last_quotes AS cur_adj_q ON cur_adj_q.asset_id = :base_currency "
            "LEFT JOIN _last_assets AS t ON l.account_id = t.id "
            "WHERE (l.book_account=:money_book OR l.book_account=:liabilities_book) "
            "AND a.type_id = :investments AND l.timestamp <= :holdings_timestamp "
            "GROUP BY l.account_id, l.asset_id "
            "HAVING ABS(qty) > :tolerance "
            ") AS h "
            "LEFT JOIN assets AS c ON c.id=h.currency_id "
            "LEFT JOIN assets AS a ON a.id=h.asset_id "
            "ORDER BY currency, account, asset_is_currency, asset",
            [(":base_currency", self._currency), (":money_book", BookAccount.Money),
             (":assets_book", BookAccount.Assets), (":liabilities_book", BookAccount.Liabilities),
             (":holdings_timestamp", self._date), (":investments", PredefindedAccountType.Investment),
             (":tolerance", Setup.DISP_TOLERANCE)], forward_only=True)
        # Load data from SQL to tree
        self._root = TreeItem([])
        currency = 0
        c_node = None
        account = 0
        a_node = None
        indexes = range(query.record().count())
        while query.next():
            values = [2] + list(map(query.value, indexes))
            if values[self.COL_CURRENCY] != currency:
                currency = values[self.COL_CURRENCY]
                c_node = TreeItem(values, self._root)
                c_node.data[self.COL_LEVEL] = 0
                c_node.data[self.COL_ASSET_FULLNAME] = ''
                c_node.data[self.COL_QTY] = 0
                self._root.appendChild(c_node)
            if values[self.COL_ACCOUNT] != account:
                account = values[self.COL_ACCOUNT]
                a_node = TreeItem(values, c_node)
                a_node.data[self.COL_LEVEL] = 1
                a_node.data[self.COL_ASSET_FULLNAME] = ''
                a_node.data[self.COL_QTY] = 0
                c_node.appendChild(a_node)
            if values[self.COL_QUOTE]:
                if values[self.COL_ASSET_IS_CURRENCY]:
                    profit = 0
                else:
                    profit = values[self.COL_QUOTE] * values[self.COL_QTY] - values[self.COL_VALUE_I]
                if values[self.COL_VALUE_I] != 0:
                    profit_relative = values[self.COL_QUOTE] * values[self.COL_QTY] / values[self.COL_VALUE_I] - 1
                else:
                    profit_relative = 0
                value = values[self.COL_QUOTE] * values[self.COL_QTY]
                share = 100.0 * value / values[self.COL_TOTAL]
                value_adjusted = values[self.COL_QUOTE_A] * values[self.COL_QTY] if values[self.COL_QUOTE_A] else 0
                values += [share, profit, profit_relative, value, value_adjusted]
            else:
                values += [0, 0, 0, 0, 0]
            node = TreeItem(values, a_node)
            a_node.appendChild(node)

        # Update totals
        for i in range(self._root.count()):          # Iterate through each currency
            currency_child = self._root.getChild(i)
            for j in range(currency_child.count()):  # Iterate through each account for given currency
                self.add_node_totals(currency_child.getChild(j))
            self.add_node_totals(currency_child)
            for j in range(currency_child.count()):  # Calculate share of each account within currency
                currency_child.getChild(j).data[self.COL_SHARE] = \
                    100.0 * currency_child.getChild(j).data[self.COL_VALUE] / currency_child.data[self.COL_VALUE]
        # Get full total of totals for all currencies adjusted to common currency
        total = sum([self._root.getChild(i).data[self.COL_VALUE_A] for i in range(self._root.count())])
        for i in range(self._root.count()):  # Calculate share of each currency (adjusted to common currency)
            if total != 0:
                self._root.getChild(i).data[self.COL_SHARE] = 100.0 * self._root.getChild(i).data[
                    self.COL_VALUE_A] / total
            else:
                self._root.getChild(i).data[self.COL_SHARE] = None
        self.modelReset.emit()
        self._view.expandAll()

    # Update node totals with sum of profit, value and adjusted profit and value of all children
    def add_node_totals(self, node):
        profit = sum([node.getChild(i).data[self.COL_PROFIT] for i in range(node.count())])
        value = sum([node.getChild(i).data[self.COL_VALUE] for i in range(node.count())])
        value_adjusted = sum([node.getChild(i).data[self.COL_VALUE_A] for i in range(node.count())])
        profit_relative = profit / (value - profit) if value != profit else 0
        node.data += [0, profit, profit_relative, value, value_adjusted]
