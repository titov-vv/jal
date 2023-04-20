from PySide6.QtCore import Qt, Signal, Slot, Property, QDateTime, QTimeZone
from PySide6.QtWidgets import QWidget, QComboBox, QHBoxLayout, QLabel, QDateEdit
from jal.widgets.helpers import ManipulateDate


ITEM_NAME = 0
ITEM_METHOD = 1
# ----------------------------------------------------------------------------------------------------------------------
class DateRangeSelector(QWidget):
    changed = Signal(int, int)   # emits signal when one or both dates were changed, "from" and "to" timestamps are sent

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.report_ranges = {
            'week': (self.tr("Week"), ManipulateDate.PreviousWeek),
            'month': (self.tr("Month"), ManipulateDate.PreviousMonth),
            'quarter': (self.tr("Quarter"), ManipulateDate.PreviousQuarter),
            'year': (self.tr("Year"), ManipulateDate.PreviousYear),
            'QTD': (self.tr("Quarter to date"), ManipulateDate.QuarterToDate),
            'YTD': (self.tr("Year to date"), ManipulateDate.YearToDate),
            'this_year': (self.tr("This year"), ManipulateDate.ThisYear),
            'last_year': (self.tr("Previous year"), ManipulateDate.LastYear),
            'all': (self.tr("All dates"), ManipulateDate.AllDates),
        }

        self._begin = 0
        self._end = 0
        self._items = []
        self.changing_range = False

        self.layout = QHBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.range_combo = QComboBox(self)
        self.layout.addWidget(self.range_combo)

        self.from_label = QLabel(self.tr("From:"), parent=self)
        self.layout.addWidget(self.from_label)

        button_space = self.height()
        self.from_date = QDateEdit()
        self.from_date.setDisplayFormat("dd/MM/yyyy")
        self.from_date.setFixedWidth(self.from_date.fontMetrics().horizontalAdvance("00/00/0000") + button_space)
        self.from_date.setCalendarPopup(True)
        self.from_date.setTimeSpec(Qt.UTC)
        self.layout.addWidget(self.from_date)

        self.from_label = QLabel(self.tr("To:"), parent=self)
        self.layout.addWidget(self.from_label)

        self.to_date = QDateEdit()
        self.to_date.setDisplayFormat("dd/MM/yyyy")
        self.to_date.setFixedWidth(self.from_date.fontMetrics().horizontalAdvance("00/00/0000") + button_space)
        self.to_date.setCalendarPopup(True)
        self.to_date.setTimeSpec(Qt.UTC)
        self.layout.addWidget(self.to_date)

        self.setLayout(self.layout)
        self.setFocusProxy(self.range_combo)

        self.connect_signals_and_slots()

    def getConfig(self):
        return ';'.join(self._items)

    def setConfig(self, items_list):
        try:
            self._items = items_list.split(';')
        except AttributeError:
            self._items = []
        for item in self._items:
            try:
                item_name = self.report_ranges[item][ITEM_NAME]
                self.range_combo.addItem(item_name, item)
            except KeyError:
                continue

    ItemsList = Property(str, getConfig, setConfig)

    def connect_signals_and_slots(self):
        self.range_combo.currentIndexChanged.connect(self.onRangeChange)
        self.from_date.dateChanged.connect(self.onFromChange)
        self.to_date.dateChanged.connect(self.onToChange)

    def _update_range(self):
        self.changing_range = True
        self.from_date.setDateTime(QDateTime.fromSecsSinceEpoch(self._begin, QTimeZone(0)))
        self.to_date.setDateTime(QDateTime.fromSecsSinceEpoch(self._end, QTimeZone(0)))
        self.changing_range = False
        self.changed.emit(self._begin, self._end)

    def setRange(self, begin_ts, end_ts):
        self._begin = begin_ts
        self._end = end_ts
        self._update_range()

    def getRange(self):
        return self._begin, self._end

    @Slot()
    def onRangeChange(self, index):
        item = self.range_combo.itemData(index)
        self._begin, self._end = self.report_ranges[item][ITEM_METHOD]()
        self._update_range()

    @Slot()
    def onFromChange(self):
        self._begin = self.from_date.date().startOfDay(Qt.UTC).toSecsSinceEpoch()
        if not self.changing_range:
            self.changed.emit(self._begin, self._end)

    @Slot()
    def onToChange(self):
        self._end = self.to_date.date().startOfDay(Qt.UTC).toSecsSinceEpoch()
        if not self.changing_range:
            self.changed.emit(self._begin, self._end)

    def setCurrentIndex(self, index):
        if index == self.range_combo.currentIndex():
            self.onRangeChange(index)
        else:
            self.range_combo.setCurrentIndex(index)
