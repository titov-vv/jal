from functools import partial
from datetime import datetime, timezone
from PySide6.QtCore import Qt, Slot, QObject, QAbstractItemModel, QModelIndex
from PySide6.QtGui import QAction, QBrush
from PySide6.QtWidgets import QMenu
from jal.reports.reports import Reports
from jal.db.asset import JalAsset
from jal.ui.reports.ui_income_spending_report import Ui_IncomeSpendingReportWidget
from jal.constants import CustomColor
from jal.db.category import JalCategory
from jal.widgets.helpers import is_signal_connected, month_list, month_start_ts, month_end_ts, \
    week_list, week_start_ts, week_end_ts, str2int
from jal.widgets.icons import JalIcon
from jal.widgets.delegates import GridLinesDelegate, FloatDelegate
from jal.widgets.mdi import MdiWidget

JAL_REPORT_CLASS = "IncomeSpendingReport"

MONTHLY = 12
WEEKLY = 53
CATEGORY_ROLE = Qt.UserRole

# ----------------------------------------------------------------------------------------------------------------------
class ReportTreeItem(QObject):
    def __init__(self, begin, end, item_id, name, periods=MONTHLY, parent=None):
        super().__init__()
        self._parent = parent
        if parent is not None:
            self._periods = parent.periods   # Child should have the same periodicity as parent
        else:
            self._periods = periods
        self._id = item_id
        self.name = name
        self._begin = begin
        self._end = end
        self._y_s = int(datetime.fromtimestamp(begin, tz=timezone.utc).strftime('%Y'))
        self._y_e = int(datetime.fromtimestamp(end, tz=timezone.utc).strftime('%Y'))
        if self._periods == MONTHLY:
            self._p_s = str2int(datetime.fromtimestamp(begin, tz=timezone.utc).strftime('%m'))
            self._p_e = str2int(datetime.fromtimestamp(end, tz=timezone.utc).strftime('%m'))
        elif self._periods == WEEKLY:
            self._p_s = str2int(datetime.fromtimestamp(begin, tz=timezone.utc).strftime('%W'))
            if self._p_s == 0:  # This is a week that starts a year before
                self._y_s -= 1
                self._p_s = 53
            self._p_e = str2int(datetime.fromtimestamp(end, tz=timezone.utc).strftime('%W'))
        else:
            assert False, "Wrong period for Income/Spending report"
        # amounts is 2D-array of per month amounts:
        # amounts[year][period_id] - amount for particular month (period_id from 1 to 12) or week (from 1 to 53)
        # amounts[year][0] - total per year
        self._amounts = [[0] * (self._periods + 1) for _ in range(self._y_e - self._y_s + 1)]
        self._total = 0
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

    def removeEmptyChildren(self):
        for child in self._children:
            child.removeEmptyChildren()
        self._children = [x for x in self._children if x.getAmount(0, 0) != 0]

    def dataCount(self):
        if self._y_s == self._y_e:
            return self._p_e - self._p_s + 3  # + 1 for year, + 1 for totals
        else:
            # (self._periods + 1) * (self._y_e - self._y_s - 1) + (self._p_e + 1) + (self._periods - self._p_s + 2) + 1 simplified to:
            return (self._periods + 1) * (self._y_e - self._y_s - 1) + (self._p_e - self._p_s + self._periods + 4)

    # Converts table column number into (year, period_id) value
    # column 0 - name of row - return (-1, -1)
    # then repetition of [year], [jan], [feb] ... [nov], [dec] - return (year, 0), (year, 1) ... (year, 12)
    # or repetition of [year], [wk1], [wk2] .. [wk53] - return (year, 0), (year, 1) ... (year, 53)
    # last column is total value - return (0, 0)
    def column2calendar(self, column: int) -> (int, int):
        if column == 0:
            return -1, -1
        if column == self.dataCount():
            return 0, 0
        if column == 1:
            return self._y_s, 0
        column = column + self._p_s - 2
        year = self._y_s + int(column / (self._periods + 1))
        period_id = column % (self._periods + 1)
        return year, period_id

    def period_name(self, period_id: int) -> str:
        month_name = [
            self.tr('Jan'), self.tr('Feb'), self.tr('Mar'), self.tr('Apr'), self.tr('May'), self.tr('Jun'),
            self.tr('Jul'), self.tr('Aug'), self.tr('Sep'), self.tr('Oct'), self.tr('Nov'), self.tr('Dec')
        ]
        if self._periods == MONTHLY:
            return month_name[period_id - 1]
        elif self._periods == WEEKLY:
            prefix = self.tr("wk")   # On separate line as it won't be extracted for translation otherwise
            return f"{prefix}{period_id}"
        else:
            assert False, "Wrong period for Income/Spending report"

    def setParent(self, parent):
        self._parent = parent

    def getParent(self):
        return self._parent

    def addAmount(self, year, period_id, amount):
        y_i = year - self._y_s
        self._amounts[y_i][period_id] += amount
        self._amounts[y_i][0] += amount
        self._total += amount
        if self._parent is not None:
            self._parent.addAmount(year, period_id, amount)

    # Return amount for given year and period or total amount if year==0
    def getAmount(self, year, period_id):
        if year == 0:
            return self._total
        y_i = year - self._y_s
        return self._amounts[y_i][period_id]

    def getLeafById(self, id):
        if self._id == id:
            return self
        leaf = None
        for child in self._children:
            leaf = child.getLeafById(id)
        return leaf

    def details(self, year, period_id):
        if period_id == 0:
            p_begin = 1
            p_end = self._periods
        else:
            p_begin = p_end = period_id
        if year == 0:
            begin_ts = self._begin
            end_ts = self._end
        elif self._periods == MONTHLY:
            begin_ts = month_start_ts(year, p_begin) if month_start_ts(year, p_begin) > self._begin else self._begin
            end_ts = month_end_ts(year, p_end) if month_end_ts(year, p_end) < self._end else self._end
        elif self._periods == WEEKLY:
            begin_ts = week_start_ts(year, p_begin) if week_start_ts(year, p_begin) > self._begin else self._begin
            end_ts = week_end_ts(year, p_end) if week_end_ts(year, p_end) < self._end else self._end
        else:
            assert False, "Wrong period for Income/Spending report"
        item_summary = {
            'category_id': self._id,
            'begin_ts': begin_ts,
            'end_ts': end_ts,
            'total': self.getAmount(year, period_id)
        }
        return item_summary

    @property
    def year_begin(self):
        return self._y_s

    @property
    def period_begin(self):
        return self._p_s

    @property
    def year_end(self):
        return self._y_e

    @property
    def period_end(self):
        return self._p_e

    @property
    def periods(self):
        return self._periods


# ----------------------------------------------------------------------------------------------------------------------
class IncomeSpendingReportModel(QAbstractItemModel):
    def __init__(self, parent_view):
        super().__init__(parent_view)
        self._periodicity = MONTHLY
        self._begin = 0
        self._end = 0
        self._currency = 0
        self._period_list = []
        self._view = parent_view
        self._root = None
        self._grid_delegate = None
        self._float_delegate = None

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
            return parent_item.dataCount() + 1  # + 1 for row header
        else:
            return 0

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                year, period = self._root.column2calendar(section)
                if year < 0:
                    col_name = ''
                elif year == 0:
                    col_name = self.tr("TOTAL")
                else:
                    if period == 0:
                        status = '▼' if self._view.isColumnHidden(section + 1) else '▶'
                        col_name = f"{year} " + status
                    else:
                        col_name = self._root.period_name(period)
                return col_name
            if role == Qt.TextAlignmentRole:
                return int(Qt.AlignCenter)
        return None

    def headerWidth(self, section):
        return self._view.header().sectionSize(section)

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
                year, period = self._root.column2calendar(index.column())
                return item.getAmount(year, period)
        if role == Qt.ForegroundRole:
            if index.column() != 0:
                year, period = self._root.column2calendar(index.column())
                if item.getAmount(year, period) > 0:
                    return QBrush(CustomColor.DarkGreen)
                elif item.getAmount(year, period) < 0:
                    return QBrush(CustomColor.DarkRed)
                else:
                    return QBrush(CustomColor.Grey)
        if role == Qt.TextAlignmentRole:
            if index.column() == 0:
                return int(Qt.AlignLeft)
            else:
                return int(Qt.AlignRight)
        if role == CATEGORY_ROLE:  # return category id for given index
            if index.column() != 0:
                year, period = self._root.column2calendar(index.column())
                return item.details(year, period)
        return None

    def configureView(self):
        self._grid_delegate = GridLinesDelegate(self._view)
        self._float_delegate = FloatDelegate(2, allow_tail=False, parent=self._view)
        for column in range(self.columnCount()):
            if column == 0:
                self._view.setItemDelegateForColumn(column, self._grid_delegate)
                self._view.setColumnWidth(column, 300)
            else:
                self._view.setItemDelegateForColumn(column, self._float_delegate)
                self._view.setColumnWidth(column, 100)
        font = self._view.header().font()
        font.setBold(True)
        self._view.header().setFont(font)

        if not is_signal_connected(self._view.header(), "sectionDoubleClicked(int)"):
            self._view.header().sectionDoubleClicked.connect(self.toggeYearColumns)

    def toggeYearColumns(self, section):
        year, period = self._root.column2calendar(section)
        if year >= 0 and period == 0:
            if year == self._root.year_begin:
                year_columns = 12 - self._root.period_begin + 1
            elif year == self._root.year_end:
                year_columns = self._root.period_end
            else:
                year_columns = 12
            for i in range(year_columns):
                new_state = not self._view.isColumnHidden(section + i + 1)
                self._view.setColumnHidden(section + i + 1, new_state)
            self.headerDataChanged.emit(Qt.Horizontal, section, section)

    def setPeriod(self, period_id):
        if period_id == 1:
            self._periodicity = WEEKLY
        else:
            self._periodicity = MONTHLY
        self.prepareData()
        self.configureView()

    def setDatesRange(self, begin, end):
        self._begin = begin
        self._end = end
        self.prepareData()
        self.configureView()

    def setCurrency(self, currency_id):
        if self._currency != currency_id:
            self._currency = currency_id
            self.prepareData()
            self.configureView()

    def prepareData(self):
        if not self._currency:
            return
        self.beginResetModel()
        root_category = JalCategory(0)
        if self._periodicity == MONTHLY:
            self._period_list = month_list(self._begin, self._end)
        elif self._periodicity == WEEKLY:
            self._period_list = week_list(self._begin, self._end)
        else:
            assert False, "Wrong period for Income/Spending report"
        self._root = ReportTreeItem(self._begin, self._end, -1, "ROOT", periods=self._periodicity)  # invisible root
        self._root.appendChild(ReportTreeItem(self._begin, self._end, 0, self.tr("TOTAL"), periods=self._periodicity))  # visible root
        self._load_child_amounts(root_category)
        self._root.removeEmptyChildren()
        self.endResetModel()
        self._view.expandAll()

    def _load_child_amounts(self, parent_category: JalCategory):
        for category in parent_category.get_child_categories():
            leaf = self._root.getLeafById(category.id())
            if leaf is None:
                parent = self._root.getLeafById(category.parent_id())
                leaf = ReportTreeItem(self._begin, self._end, category.id(), category.name(), parent=parent)
                parent.appendChild(leaf)
            for period in self._period_list:
                leaf.addAmount(period['year'], period['number'],
                               category.get_turnover(period['begin_ts'], period['end_ts'], self._currency))
            self._load_child_amounts(category)


# ----------------------------------------------------------------------------------------------------------------------
class IncomeSpendingReport(QObject):
    def __init__(self):
        super().__init__()
        self.name = self.tr("Income & Spending")
        self.window_class = "IncomeSpendingReportWindow"


# ----------------------------------------------------------------------------------------------------------------------
class IncomeSpendingReportWindow(MdiWidget):
    def __init__(self, parent: Reports, settings: dict = None):
        super().__init__(parent.mdi_area())
        self.ui = Ui_IncomeSpendingReportWidget()
        self.ui.setupUi(self)
        self._parent = parent
        self.name = self.tr("Income & Spending")
        self.current_index = None  # this is used in onOperationContextMenu() to track item for menu

        self.income_spending_model = IncomeSpendingReportModel(self.ui.ReportTreeView)
        self.ui.ReportTreeView.setModel(self.income_spending_model)
        self.ui.ReportTreeView.setContextMenuPolicy(Qt.CustomContextMenu)

        # Operations view context menu
        self.contextMenu = QMenu(self.ui.ReportTreeView)
        self.actionDetails = QAction(JalIcon[JalIcon.LIST], self.tr("Show operations"), self)
        self.contextMenu.addAction(self.actionDetails)

        self.connect_signals_and_slots()

        if settings is None:
            begin, end = self.ui.ReportRange.getRange()
            period = self.ui.PeriodComboBox.currentIndex()
            settings = {'period': period, 'begin_ts': begin, 'end_ts': end, 'currency_id': JalAsset.get_base_currency()}
        self.ui.PeriodComboBox.setCurrentIndex(settings['period'])
        self.ui.ReportRange.setRange(settings['begin_ts'], settings['end_ts'])
        self.ui.CurrencyCombo.setIndex(settings['currency_id'])

    def connect_signals_and_slots(self):
        self.ui.PeriodComboBox.currentIndexChanged.connect(self.ui.ReportTreeView.model().setPeriod)
        self.ui.ReportRange.changed.connect(self.ui.ReportTreeView.model().setDatesRange)
        self.ui.CurrencyCombo.changed.connect(self.ui.ReportTreeView.model().setCurrency)
        self.ui.ReportTreeView.customContextMenuRequested.connect(self.onCellContextMenu)
        self.actionDetails.triggered.connect(self.showDetailsReport)
        self.ui.SaveButton.pressed.connect(partial(self._parent.save_report, self.name, self.ui.ReportTreeView.model()))

    @Slot()
    def onCellContextMenu(self, position):
        self.current_index = self.ui.ReportTreeView.indexAt(position)
        if self.current_index.isValid() and self.current_index.column() != 0:
            self.contextMenu.popup(self.ui.ReportTreeView.viewport().mapToGlobal(position))

    @Slot()
    def showDetailsReport(self):
        details = self.income_spending_model.data(self.current_index, CATEGORY_ROLE)
        self._parent.show_report("CategoryReportWindow", details)
