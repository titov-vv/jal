import decimal
from datetime import datetime

from PySide6.QtCore import Qt, Slot, QAbstractItemModel, QDate, QModelIndex, QLocale
from PySide6.QtGui import QBrush, QFont
from PySide6.QtWidgets import QHeaderView
from jal.constants import Setup, CustomColor, BookAccount, PredefindedAccountType, AssetData
from jal.db.helpers import executeSQL, readSQLrecord
from jal.db.db import JalDB
from jal.db.settings import JalSettings
from jal.widgets.delegates import GridLinesDelegate


class TreeItem:
    def __init__(self, data, parent=None):
        self._parent = parent
        self.data = data.copy()
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
    def __init__(self, parent_view):
        super().__init__(parent_view)
        self._view = parent_view
        self._grid_delegate = None
        self._root = None
        self._currency = 0
        self._currency_name = ''
        self._date = QDate.currentDate().endOfDay(Qt.UTC).toSecsSinceEpoch()
        self.calculated_names = ['share', 'profit', 'profit_rel', 'value', 'value_a']
        self._columns = [self.tr("Currency/Account/Asset"),
                         self.tr("Asset Name"),
                         self.tr("Qty"),
                         self.tr("Open"),
                         self.tr("Last"),
                         self.tr("Share, %"),
                         self.tr("P/L, %"),
                         self.tr("P/L"),
                         self.tr("Value"),
                         self.tr("Value, ")]

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
            return self.data_background(item.data, index.column(), self._view.isEnabled())
        if role == Qt.TextAlignmentRole:
            if index.column() < 2:
                return int(Qt.AlignLeft)
            else:
                return int(Qt.AlignRight)
        return None

    def data_text(self, data, column):
        if column == 0:
            if data['level'] == 0:
                return data['currency']
            elif data['level'] == 1:
                return data['account']
            else:
                return data['asset']
        elif column == 1:
            expiry_text = ""
            if data['expiry']:
                expiry_date = datetime.utcfromtimestamp(data['expiry'])
                expiry_header = self.tr("Exp:")
                expiry_text = f" [{expiry_header} {expiry_date.strftime('%d.%m.%Y')}]"
            return data['asset_name'] + expiry_text
        elif column == 2:
            if data['qty']:
                if data['asset_is_currency']:
                    decimal_places = 2
                else:
                    decimal_places = -decimal.Decimal(str(data['qty']).rstrip('0')).as_tuple().exponent
                    decimal_places = 6 if decimal_places > 6 else decimal_places
                return QLocale().toString(data['qty'], 'f', decimal_places)
            else:
                return ''
        elif column == 3:
            if data['qty'] != 0 and data['value_i'] != 0:
                return f"{(data['value_i'] / data['qty']):,.4f}"
            else:
                return ''
        elif column == 4:
            return f"{data['quote']:,.4f}" if data['quote'] and data['qty'] != 0 else ''
        elif column == 5:
            return f"{data['share']:,.2f}" if data['share'] else '-.--'
        elif column == 6:
            return f"{100.0 * data['profit_rel']:,.2f}" if data['profit_rel'] else ''
        elif column == 7:
            return f"{data['profit']:,.2f}" if data['profit'] else ''
        elif column == 8:
            return f"{data['value']:,.2f}" if data['value'] else ''
        elif column == 9:
            return f"{data['value_a']:,.2f}" if data['value_a'] else '-.--'
        else:
            assert False

    def data_font(self, data, column):
        if data['level'] < 2:
            font = QFont()
            font.setBold(True)
            return font
        else:
            if column == 1 and data['expiry']:
                expiry_date = datetime.utcfromtimestamp(data['expiry'])
                days_remaining = int((expiry_date - datetime.utcnow()).total_seconds() / 86400)
                if days_remaining <= 10:
                    font = QFont()
                    if days_remaining < 0:
                        font.setStrikeOut(True)
                    else:
                        font.setItalic(True)
                    return font

    def data_background(self, data, column, enabled=True):
        factor = 100 if enabled else 125
        if data['level'] == 0:
            return QBrush(CustomColor.LightPurple.lighter(factor))
        if data['level'] == 1:
            return QBrush(CustomColor.LightBlue.lighter(factor))
        if column == 6 and data['profit_rel']:
            if data['profit_rel'] >= 0:
                return QBrush(CustomColor.LightGreen.lighter(factor))
            else:
                return QBrush(CustomColor.LightRed.lighter(factor))
        if column == 7 and data['profit']:
            if data['profit'] >= 0:
                return QBrush(CustomColor.LightGreen.lighter(factor))
            else:
                return QBrush(CustomColor.LightRed.lighter(factor))

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
        return item.data['account_id'], item.data['asset_id'], item.data['qty']

    def update(self):
        self.calculateHoldings()

    # Populate table 'holdings' with data calculated for given parameters of model: _currency, _date,
    def calculateHoldings(self):
        query = executeSQL(
            "WITH "
            "_last_quotes AS (SELECT MAX(timestamp) AS timestamp, asset_id, currency_id, quote "
            "FROM quotes WHERE timestamp <= :holdings_timestamp GROUP BY asset_id, currency_id), "
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
            "LEFT JOIN _last_quotes AS q ON l.asset_id = q.asset_id AND q.currency_id = a.currency_id "
            "WHERE l.book_account=:assets_book AND a.type_id = :investments AND l.timestamp <= :holdings_timestamp "
            "GROUP BY a.id"
            ") "
            "GROUP BY id HAVING ABS(total_value) > :tolerance) "
            "SELECT h.currency_id, c.symbol AS currency, h.account_id, h.account, h.asset_id, "
            "h.currency_id=h.asset_id AS asset_is_currency, coalesce(a.symbol, c.symbol) AS asset, "
            "coalesce(a.full_name, c.full_name) AS asset_name, ad.value AS expiry, h.qty, h.value AS value_i, "
            "h.quote, h.quote_a, h.total "
            "FROM ("
            "SELECT a.currency_id, l.account_id, a.name AS account, l.asset_id, sum(l.amount) AS qty, "
            "sum(l.value) AS value, q.quote, q.quote*r.quote/ra.quote AS quote_a, t.total_value AS total "
            "FROM ledger AS l "
            "LEFT JOIN accounts AS a ON l.account_id = a.id "
            "LEFT JOIN _last_quotes AS q ON l.asset_id = q.asset_id AND q.currency_id = a.currency_id "
            "LEFT JOIN _last_quotes AS r ON a.currency_id = r.asset_id AND r.currency_id = :base_currency "
            "LEFT JOIN _last_quotes AS ra ON ra.asset_id = :currency AND ra.currency_id = :base_currency "
            "LEFT JOIN _last_assets AS t ON l.account_id = t.id "
            "WHERE a.type_id = :investments AND l.book_account = :assets_book AND l.timestamp <= :holdings_timestamp "
            "GROUP BY l.account_id, l.asset_id "
            "HAVING ABS(qty) > :tolerance "
            "UNION ALL "
            "SELECT a.currency_id, l.account_id, a.name AS account, l.asset_id, sum(l.amount) AS qty, "
            "0 AS value, 1, r.quote/ra.quote AS quote_a, t.total_value AS total "
            "FROM ledger AS l "
            "LEFT JOIN accounts AS a ON l.account_id = a.id "
            "LEFT JOIN _last_quotes AS r ON a.currency_id = r.asset_id AND r.currency_id = :base_currency "
            "LEFT JOIN _last_quotes AS ra ON ra.asset_id = :currency AND ra.currency_id = :base_currency "
            "LEFT JOIN _last_assets AS t ON l.account_id = t.id "
            "WHERE (l.book_account=:money_book OR l.book_account=:liabilities_book) "
            "AND a.type_id = :investments AND l.timestamp <= :holdings_timestamp "
            "GROUP BY l.account_id, l.asset_id "
            "HAVING ABS(qty) > :tolerance "
            ") AS h "
            "LEFT JOIN assets_ext AS c ON c.id=h.currency_id AND c.currency_id=:base_currency "
            "LEFT JOIN assets_ext AS a ON a.id=h.asset_id AND a.currency_id=h.currency_id " 
            "LEFT JOIN asset_data AS ad ON ad.asset_id=a.id AND ad.datatype=:expiry "
            "ORDER BY currency, account, asset_is_currency, asset",
            [(":currency", self._currency), (":money_book", BookAccount.Money),
             (":assets_book", BookAccount.Assets), (":liabilities_book", BookAccount.Liabilities),
             (":holdings_timestamp", self._date), (":investments", PredefindedAccountType.Investment),
             (":tolerance", Setup.DISP_TOLERANCE), (":expiry", AssetData.ExpiryDate),
             (":base_currency", JalSettings().getValue('BaseCurrency'))], forward_only=True)
        # Load data from SQL to tree
        self._root = TreeItem({})
        currency = 0
        c_node = None
        account = 0
        a_node = None
        while query.next():
            values = readSQLrecord(query, named=True)
            values['level'] = 2
            if values['currency_id'] != currency:
                currency = values['currency_id']
                c_node = TreeItem(values, self._root)
                c_node.data['level'] = 0
                c_node.data['asset_name'] = ''
                c_node.data['expiry'] = 0
                c_node.data['qty'] = 0
                self._root.appendChild(c_node)
            if values['account_id'] != account:
                account = values['account_id']
                a_node = TreeItem(values, c_node)
                a_node.data['level'] = 1
                a_node.data['asset_name'] = ''
                a_node.data['expiry'] = 0
                a_node.data['qty'] = 0
                c_node.appendChild(a_node)
            if values['quote']:
                if values['asset_is_currency']:
                    profit = 0
                else:
                    profit = values['quote'] * values['qty'] - values['value_i']
                if values['value_i'] != 0:
                    profit_relative = values['quote'] * values['qty'] / values['value_i'] - 1
                else:
                    profit_relative = 0
                value = values['quote'] * values['qty']
                share = 100.0 * value / values['total']
                value_adjusted = values['quote_a'] * values['qty'] if values['quote_a'] else 0
                values.update(dict(zip(self.calculated_names, [share, profit, profit_relative, value, value_adjusted])))
            else:
                values.update(dict(zip(self.calculated_names, [0, 0, 0, 0, 0])))
            node = TreeItem(values, a_node)
            a_node.appendChild(node)

        # Update totals
        for i in range(self._root.count()):          # Iterate through each currency
            currency_child = self._root.getChild(i)
            for j in range(currency_child.count()):  # Iterate through each account for given currency
                self.add_node_totals(currency_child.getChild(j))
            self.add_node_totals(currency_child)
            for j in range(currency_child.count()):  # Calculate share of each account within currency
                if currency_child.data['value']:
                    currency_child.getChild(j).data['share'] = \
                        100.0 * currency_child.getChild(j).data['value'] / currency_child.data['value']
        # Get full total of totals for all currencies adjusted to common currency
        total = sum([self._root.getChild(i).data['value_a'] for i in range(self._root.count())])
        for i in range(self._root.count()):  # Calculate share of each currency (adjusted to common currency)
            if total != 0:
                self._root.getChild(i).data['share'] = 100.0 * self._root.getChild(i).data[
                    'value_a'] / total
            else:
                self._root.getChild(i).data['share'] = None
        self.modelReset.emit()
        self._view.expandAll()

    # Update node totals with sum of profit, value and adjusted profit and value of all children
    def add_node_totals(self, node):
        profit = sum([node.getChild(i).data['profit'] for i in range(node.count())])
        value = sum([node.getChild(i).data['value'] for i in range(node.count())])
        value_adjusted = sum([node.getChild(i).data['value_a'] for i in range(node.count())])
        profit_relative = profit / (value - profit) if value != profit else 0
        node.data.update(dict(zip(self.calculated_names, [0, profit, profit_relative, value, value_adjusted])))
