from __future__ import annotations

from decimal import Decimal
from PySide6.QtCore import Qt, Slot, QObject, QAbstractItemModel, QModelIndex
from jal.ui.reports.ui_deals_report import Ui_DealsReportWidget
from jal.reports.reports import Reports
from jal.db.account import JalAccount
from jal.db.operations import LedgerTransaction
from jal.widgets.helpers import ts2d
from jal.widgets.delegates import TimestampDelegate, FloatDelegate
from jal.widgets.mdi import MdiWidget
from jal.widgets.delegates import GridLinesDelegate

JAL_REPORT_CLASS = "DealsReport"


# ----------------------------------------------------------------------------------------------------------------------
# Class to group trades and display them in TreeView
class TradeTreeItem:
    def __init__(self, trade, parent=None, group=''):
        self._parent = parent
        self._trade = trade
        self._children = []
        self._group = group
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

    def setParent(self, parent):
        self._parent = parent

    def getParent(self):
        return self._parent

    def appendChild(self, child):
        child.setParent(self)
        self._children.append(child)
        if self._group:
            self.updateGroupDetails(child.details())

    def updateGroupDetails(self, child_data):
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
        if self._parent is not None:
            self._parent.updateGroupDetails(child_data)

    def getChild(self, id):
        if id < 0 or id > len(self._children):
            return None
        return self._children[id]

    def childrenCount(self):
        return len(self._children)

    def details(self):
        return self._data

    def isGroup(self):
        return self._group != ''

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
class ClosedTradesModel(QAbstractItemModel):
    def __init__(self, parent_view):
        super().__init__(parent_view)
        self._view = parent_view
        self._root = None
        self._trades = []
        self._account_id = 0
        self._begin = self._end = 0
        self._groups = []
        self._grid_delegate = None
        self._float_delegate = None
        self._float2_delegate = None
        self._float4_delegate = None
        self._timestamp_delegate = None
        self._profit_delegate = None
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

    def fieldIndex(self, field_name: str) -> int:
        for i, column in enumerate(self._columns):
            if column['field'] == field_name:
                return i
        return -1

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
        if parent is None:
            parent_item = self._root
        elif not parent.isValid():
            parent_item = self._root
        else:
            parent_item = parent.internalPointer()
        if parent_item is not None:
            return len(self._columns)
        else:
            return 0

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

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                return self._columns[section]['name']
            if role == Qt.TextAlignmentRole:
                return int(Qt.AlignCenter)
        return None

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

    def setAccount(self, account_id):
        self._account_id = account_id
        self.prepareData()
        self.configureView()

    def prepareData(self):
        self._trades = JalAccount(self._account_id).closed_trades_list()
        self._trades = [x for x in self._trades if self._begin <= x.close_operation().timestamp() <= self._end]
        self._root = TradeTreeItem(None)
        for trade in self._trades:
            new_item = TradeTreeItem(trade)
            leaf = self._root.getGroupLeaf(self._groups, new_item)
            leaf.appendChild(new_item)
        self.modelReset.emit()
        self._view.expandAll()

    def configureView(self):
        self._view.setSortingEnabled(True)
        for column in range(self.columnCount()):
            if column == 0:
                self._view.setColumnWidth(column, 300)
            else:
                self._view.setColumnWidth(column, 100)
        font = self._view.header().font()
        font.setBold(True)
        self._view.header().setFont(font)
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

    def setDatesRange(self, begin, end):
        self._begin = begin
        self._end = end
        self.prepareData()
        self.configureView()

    # defines report grouping by provided field list - 'group_field1;group_field2;...'
    def setGrouping(self, group_list):
        if group_list:
            self._groups = group_list.split(';')
        else:
            self._groups = []
        self.prepareData()
        self.configureView()


# ----------------------------------------------------------------------------------------------------------------------
class DealsReport(QObject):
    def __init__(self):
        super().__init__()
        self.name = self.name = self.tr("Deals by Account")
        self.window_class = "DealsReportWindow"


# ----------------------------------------------------------------------------------------------------------------------
class DealsReportWindow(MdiWidget):
    def __init__(self, parent: Reports, settings: dict = None):
        super().__init__(parent.mdi_area())
        self.ui = Ui_DealsReportWidget()
        self.ui.setupUi(self)
        self._parent = parent

        # Add available groupings
        self.ui.GroupCombo.addItem(self.tr("<None>"), "")
        self.ui.GroupCombo.addItem(self.tr("Asset"), "symbol")
        self.ui.GroupCombo.addItem(self.tr("Close"), "close_date")
        self.ui.GroupCombo.addItem(self.tr("Asset - Open - Close"), "symbol;open_date;close_date")
        self.ui.GroupCombo.addItem(self.tr("Open - Close"), "open_date;close_date")
        self.ui.GroupCombo.addItem(self.tr("Close - Open"), "close_date;open_date")

        self.trades_model = ClosedTradesModel(self.ui.ReportTreeView)
        self.ui.ReportTreeView.setModel(self.trades_model)

        self.connect_signals_and_slots()

    def connect_signals_and_slots(self):
        self.ui.ReportAccountBtn.changed.connect(self.onAccountChange)
        self.ui.ReportRange.changed.connect(self.ui.ReportTreeView.model().setDatesRange)
        self.ui.GroupCombo.currentIndexChanged.connect(self.onGroupingChange)

    @Slot()
    def onAccountChange(self):
        self.ui.ReportTreeView.model().setAccount(self.ui.ReportAccountBtn.account_id)

    @Slot()
    def onGroupingChange(self, idx):
        self.ui.ReportTreeView.model().setGrouping(self.ui.GroupCombo.itemData(idx))
