from datetime import datetime
from PySide2.QtCore import Qt, QAbstractItemModel, QModelIndex
from jal.constants import BookAccount, PredefinedAsset
from jal.db.helpers import executeSQL


# ----------------------------------------------------------------------------------------------------------------------
class ReportTreeItem():
    def __init__(self, begin, end, id, name, parent=None):
        self._parent = parent
        self._id = id
        self.name = name
        self._y_s = int(datetime.utcfromtimestamp(begin).strftime('%Y'))
        self._m_s = int(datetime.utcfromtimestamp(begin).strftime('%-m'))
        self._y_e = int(datetime.utcfromtimestamp(end).strftime('%Y'))
        self._m_e = int(datetime.utcfromtimestamp(end).strftime('%-m'))
        # amounts is 2D-array of per month amounts:
        # amounts[year][month] - amount for particular month
        # amounts[year][0] - total per year
        self._amounts = [ [0] * 13 for _ in range(self._y_e - self._y_s + 1)]
        self._children = []

    def appendChild(self, child):
        child.setParent(self)
        self._children.append(child)

    def getChild(self, id):
        if id < 0 or id > len(self._children):
            return None
        return self._children[id]

    def childrenCount(self):
        return len(self._children)

    def dataCount(self):
        return self._y_e - self._y_s + self._m_s + 12 - self._m_e

    def setParent(self, parent):
        self._parent = parent

    def getParent(self):
        return self._parent

    def addAmount(self, year, month, amount):
        y_i = year - self._y_s
        self._amounts[y_i][month] += amount
        self._amounts[y_i][0] += amount

    def getAmount(self, offset):
        y_i = int(offset / 12)
        m_i = offset % 12
        try:
            value = self._amounts[y_i][m_i]
        except:
            value = 0
        return value

    def getLeafById(self, id):
        if self._id == id:
            return self
        leaf = None
        for child in self._children:
            leaf = child.getLeafById(id)
        return leaf


# ----------------------------------------------------------------------------------------------------------------------
class IncomeSpendingReport(QAbstractItemModel):
    COL_LEVEL = 0
    COL_ID = 1
    COL_PID = 2
    COL_NAME = 3
    COL_PATH = 4
    COL_TIMESTAMP = 5
    COL_AMOUNT = 6

    def __init__(self, parent_view):
        super().__init__(parent_view)
        self._view = parent_view
        self._root = None

    def rowCount(self, parent=None):
        if not parent.isValid():
            parent_item = self._root
        else:
            parent_item = parent.internalPointer()
        if parent_item is not None:
            return parent_item.childrenCount()
        else:
            return 0

    def columnCount(self, parent=None):
        if not parent.isValid():
            parent_item = self._root
        else:
            parent_item = parent.internalPointer()
        if parent_item is not None:
            return parent_item.dataCount()
        else:
            return 0

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                col_name = f"COL: {section}"
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

    def parent(self, index=None):
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
            if index.column() == 0:
                return item.name
            else:
                return item.getAmount(index.column() - 1)
        return None

    def prepare(self, begin, end, account_id, group_dates):
        query = executeSQL("WITH "
                           "_months AS (SELECT strftime('%s', datetime(timestamp, 'unixepoch', 'start of month') ) "
                           "AS month, asset_id, MAX(timestamp) AS last_timestamp "
                           "FROM quotes AS q "
                           "LEFT JOIN assets AS a ON q.asset_id=a.id "
                           "WHERE a.type_id=:asset_money "
                           "GROUP BY month, asset_id), "
                           "_category_amounts AS ( "
                           "SELECT strftime('%s', datetime(t.timestamp, 'unixepoch', 'start of month')) AS month_start, "
                           "t.category_id AS id, sum(-t.amount * coalesce(q.quote, 1)) AS amount "
                           "FROM ledger AS t "
                           "LEFT JOIN _months AS d ON month_start = d.month AND t.asset_id = d.asset_id "
                           "LEFT JOIN quotes AS q ON d.last_timestamp = q.timestamp AND t.asset_id = q.asset_id "
                           "WHERE (t.book_account=:book_costs OR t.book_account=:book_incomes) "
                           "AND t.timestamp>=:begin AND t.timestamp<=:end "
                           "GROUP BY month_start, category_id) "
                           "SELECT ct.level, ct.id, c.pid, c.name, ct.path, ca.month_start, "
                           "coalesce(ca.amount, 0) AS amount "
                           "FROM categories_tree AS ct "
                           "LEFT JOIN _category_amounts AS ca ON ct.id=ca.id "
                           "LEFT JOIN categories AS c ON ct.id=c.id "
                           "ORDER BY path, month_start",
                           [(":asset_money", PredefinedAsset.Money), (":book_costs", BookAccount.Costs),
                            (":book_incomes", BookAccount.Incomes), (":begin", begin), (":end", end)])
        query.setForwardOnly(True)
        self._root = ReportTreeItem(begin, end, 0, "ROOT")
        indexes = range(query.record().count())
        while query.next():
            values = list(map(query.value, indexes))
            leaf = self._root.getLeafById(values[self.COL_ID])
            if leaf is None:
                parent = self._root.getLeafById(values[self.COL_PID])
                leaf = ReportTreeItem(begin, end, values[self.COL_ID], values[self.COL_NAME], parent)
                parent.appendChild(leaf)
            if values[self.COL_TIMESTAMP]:
                year = int(datetime.utcfromtimestamp(int(values[self.COL_TIMESTAMP])).strftime('%Y'))
                month = int(datetime.utcfromtimestamp(int(values[self.COL_TIMESTAMP])).strftime('%-m'))
                leaf.addAmount(year, month, values[self.COL_AMOUNT])
        self.modelReset.emit()
        self._view.expandAll()
