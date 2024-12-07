from __future__ import annotations
from decimal import Decimal
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from jal.db.tree_model import AbstractTreeItem, ReportTreeModel
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.helpers import localize_decimal
from jal.db.operations import LedgerTransaction
from jal.widgets.helpers import ts2d
from jal.widgets.delegates import TimestampDelegate, FloatDelegate, GridLinesDelegate

# ----------------------------------------------------------------------------------------------------------------------
# Class to group trades and display them in TreeView
class TradeTreeItem(AbstractTreeItem):
    def __init__(self, trade=None, parent=None, group=''):
        super().__init__(parent, group)
        self._trade = trade
        if trade is None:
            self._data = {
                'symbol': '',
                'open_ts': 0, 'open_date': '', 'close_ts': 0, 'close_date': '',
                'open_price': Decimal('0'), 'close_price': Decimal('0'),
                'qty': Decimal('0'), 'fee': Decimal('0'), 'p/l': Decimal('0'), 'p/l%': Decimal('0'),
                'note': ''
            }
        else:
            self._data = {
                'symbol': self._trade.symbol(),
                'open_ts': self._trade.open_operation().timestamp(),
                'open_date': ts2d(self._trade.open_operation().timestamp()),
                'close_ts': self._trade.close_operation().timestamp(),
                'close_date': ts2d(self._trade.close_operation().timestamp()),
                'open_price': self._trade.open_price(),
                'close_price': self._trade.close_price(),
                'qty': self._trade.qty(),
                'fee': self._trade.fee(),
                'p/l': self._trade.profit(),
                'p/l%': self._trade.profit(percent=True),
                'note': ''
            }
            if self._trade.open_operation().type() == LedgerTransaction.CorporateAction:
                self._data['note'] += self._trade.open_operation().name() + " ▶"
            if self._trade.close_operation().type() == LedgerTransaction.CorporateAction:
                self._data['note'] += "▶ " + self._trade.close_operation().name()

    def _calculateGroupTotals(self, child_data):
        self._data['symbol'] = child_data['symbol']
        if self._data['open_ts'] == 0 or self._data['open_ts'] > child_data['open_ts']:
            self._data['open_ts'] = child_data['open_ts']
        if self._data['close_ts'] < child_data['close_ts']:
            self._data['close_ts'] = child_data['close_ts']
        self._data['open_price'] = (self._data['open_price'] * self._data['qty'] + child_data['open_price'] *
                                    child_data['qty']) / (self._data['qty'] + child_data['qty'])
        self._data['close_price'] = (self._data['close_price'] * self._data['qty'] + child_data['close_price'] *
                                     child_data['qty']) / (self._data['qty'] + child_data['qty'])
        self._data['qty'] += child_data['qty']
        self._data['fee'] += child_data['fee']
        self._data['p/l'] += child_data['p/l']
        self._data['p/l%'] = Decimal('100') * self._data['p/l'] / (self._data['open_price'] * self._data['qty'])

    def _afterParentGroupUpdate(self, group_data):
        pass

    def details(self):
        return self._data

    # assigns group value if this tree item is a group item
    def setGroupValue(self, value):
        if self._group:
            self._data[self._group] = value

    # returns (group_field_name, group_value) if item is a group item, otherwise returns None
    def getGroup(self):
        if self._group:
            return self._group, self._data[self._group]
        else:
            return None

    # returns an element of tree that will provide right group parent for 'item' with given 'group_fields'
    def getGroupLeaf(self, group_fields: list, item: TradeTreeItem) -> TradeTreeItem:
        if group_fields:
            group_item = None
            group_name = group_fields[0]
            for child in self._children:
                if child.details()[group_name] == item.details()[group_name]:
                    group_item = child
            if group_item is None:
                group_item = TradeTreeItem(None, parent=self, group=group_name)
                group_item.setGroupValue(item.details()[group_name])
                self._children.append(group_item)
            return group_item.getGroupLeaf(group_fields[1:], item)
        else:
            return self


# ----------------------------------------------------------------------------------------------------------------------
class ClosedTradesModel(ReportTreeModel):
    def __init__(self, parent_view):
        super().__init__(parent_view)
        self._trades = []
        self._account_id = 0
        self._begin = self._end = 0
        self._grid_delegate = None
        self._float_delegate = None
        self._float2_delegate = None
        self._float4_delegate = None
        self._timestamp_delegate = None
        self._profit_delegate = None
        self._total_currency_name = ''
        self._columns = [
            {'name': self.tr("Asset"), 'field': 'symbol'},
            {'name': self.tr("Open Date/Time"), 'field': 'open_ts'},
            {'name': self.tr("Open Date"), 'field': 'open_date'},
            {'name': self.tr("Close Date/Time"), 'field': 'close_ts'},
            {'name': self.tr("Close Date"), 'field': 'close_date'},
            {'name': self.tr("Open Price"), 'field': 'open_price'},
            {'name': self.tr("Close Price"), 'field': 'close_price'},
            {'name': self.tr("Qty"), 'field': 'qty'},
            {'name': self.tr("Fee"), 'field': 'fee'},
            {'name': self.tr("P/L"), 'field': 'p/l'},
            {'name': self.tr("P/L, %"), 'field': 'p/l%'},
            {'name': self.tr("Note"), 'field': 'note'}
        ]
        self._configured = False

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        item = index.internalPointer()
        if role == Qt.DisplayRole:
            if item.isGroup():
                field = self._columns[index.column()]['field']
                if field == 'symbol':
                    group, value = item.getGroup()
                    display_name = [x['name'] for x in self._columns if x['field']==group][0]
                    return f"{display_name}: {value}"
                if field == 'open_ts' or field == 'close_ts':
                    return 0
            return item.details()[self._columns[index.column()]['field']]
        return None

    def footerData(self, section: int, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            total_data = self._root.details()
            if section == self.fieldIndex('symbol'):
                return self.tr("Total:")
            elif section == self.fieldIndex('p/l'):
                return localize_decimal(total_data[self._columns[section]['field']], precision=2)
            elif section == self.fieldIndex('p/l%'):
                return self._total_currency_name
        elif role == Qt.FontRole:
            font = QFont()
            font.setBold(True)
            return font
        elif role == Qt.TextAlignmentRole:
            if section == self.fieldIndex('p/l'):
                return Qt.AlignRight | Qt.AlignVCenter
            else:
                return Qt.AlignLeft | Qt.AlignVCenter
        return None

    def updateView(self, account_id, dates, grouping):
        update = False
        if self._account_id != account_id:
            self._account_id = account_id
            self._total_currency_name = JalAsset(JalAccount(account_id).currency()).symbol()
            update = True
        if self._begin != dates[0]:
            self._begin = dates[0]
            update = True
        if self._end != dates[1]:
            self._end = dates[1]
            update = True
        if self.setGrouping(grouping) or update:
            self.prepareData()

    def prepareData(self):
        self.beginResetModel()
        self._trades = JalAccount(self._account_id).closed_trades_list()
        self._trades = [x for x in self._trades if self._begin <= x.close_operation().timestamp() <= self._end]
        self._root = TradeTreeItem()
        for trade in self._trades:
            new_item = TradeTreeItem(trade)
            leaf = self._root.getGroupLeaf(self._groups, new_item)
            leaf.appendChild(new_item)
        self.endResetModel()
        super().prepareData()

    def configureView(self):
        self._view.setSortingEnabled(True)
        for column in range(self.columnCount()):
            if column == self.fieldIndex('symbol'):
                self._view.setColumnWidth(column, 300)
            else:
                self._view.setColumnWidth(column, 100)
        self._view.setColumnHidden(self.fieldIndex('open_date'), True)
        self._view.setColumnHidden(self.fieldIndex('close_date'), True)
        self._view.setColumnWidth(self.fieldIndex('open_ts'), self._view.fontMetrics().horizontalAdvance("00/00/0000 00:00:00") * 1.1)
        self._view.setColumnWidth(self.fieldIndex('close_ts'), self._view.fontMetrics().horizontalAdvance("00/00/0000 00:00:00") * 1.1)
        self._grid_delegate = GridLinesDelegate(self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex('symbol'), self._grid_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex('note'), self._grid_delegate)
        self._timestamp_delegate = TimestampDelegate(parent=self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex('open_ts'), self._timestamp_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex('close_ts'), self._timestamp_delegate)
        self._float_delegate = FloatDelegate(0, allow_tail=True, parent=self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("qty"), self._float_delegate)
        self._float2_delegate = FloatDelegate(2, allow_tail=False, parent=self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("fee"), self._float2_delegate)
        self._float4_delegate = FloatDelegate(4, allow_tail=False, parent=self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex('open_price'), self._float4_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex('close_price'), self._float4_delegate)
        self._profit_delegate = FloatDelegate(2, allow_tail=False, colors=True, parent=self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("p/l"), self._profit_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex("p/l%"), self._profit_delegate)
        super().configureView()
