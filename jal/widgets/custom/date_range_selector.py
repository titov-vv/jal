from PySide6.QtCore import Qt, Signal, Slot, Property
from PySide6.QtWidgets import QWidget, QComboBox, QHBoxLayout, QLabel, QDateEdit
from jal.db.clock import day_start, day_finish, local_datetime, now_dt
from jal.widgets.helpers import ManipulateDate, DateFormat


ITEM_NAME = 0
ITEM_METHOD = 1
CUSTOM = 'custom'


# Timestamps that cover the days from 'first' to 'last' entirely; no first day means "since the beginning"
def day_bounds(first, last) -> tuple:
    return (day_start(first) if first is not None else 0), day_finish(last)


# ----------------------------------------------------------------------------------------------------------------------
class DateRangeSelector(QWidget):
    changed = Signal(int, int)   # emits signal when one or both dates were changed, "from" and "to" timestamps are sent

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.report_ranges = {
            'week': (self.tr("Since last week"), ManipulateDate.PreviousWeek),
            'month': (self.tr("Since last month"), ManipulateDate.PreviousMonth),
            'quarter': (self.tr("Since last quarter"), ManipulateDate.PreviousQuarter),
            'year': (self.tr("Since last year"), ManipulateDate.PreviousYear),
            'QTD': (self.tr("3 months"), ManipulateDate.QuarterToDate),
            'YTD': (self.tr("12 months"), ManipulateDate.YearToDate),
            'this_year': (self.tr("This year"), ManipulateDate.ThisYear),
            'last_year': (self.tr("Previous year"), ManipulateDate.LastYear),
            'all': (self.tr("All dates"), ManipulateDate.AllDates),
        }

        self._begin = 0
        self._end = 0
        self._items = []

        self.layout = QHBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.range_combo = QComboBox(self)
        self.range_combo.addItem(self.tr("Custom"), CUSTOM)
        self.layout.addWidget(self.range_combo)

        self.from_label = QLabel(self.tr("From:"), parent=self)
        self.layout.addWidget(self.from_label)

        self.from_date = QDateEdit()
        self.from_date.setDisplayFormat(DateFormat.date(qt=True))
        self.from_date.setCalendarPopup(True)
        self.from_date.setKeyboardTracking(False)
        self.layout.addWidget(self.from_date)

        self.to_label = QLabel(self.tr("To:"), parent=self)
        self.layout.addWidget(self.to_label)

        self.to_date = QDateEdit()
        self.to_date.setDisplayFormat(DateFormat.date(qt=True))
        self.to_date.setCalendarPopup(True)
        self.to_date.setKeyboardTracking(False)
        self.layout.addWidget(self.to_date)

        self.setLayout(self.layout)
        self.setFocusProxy(self.range_combo)

        self.connect_signals_and_slots()

    def getConfig(self):
        return ';'.join(self._items)

    # Presets go before the "Custom" item, which stays last
    def setConfig(self, items_list):
        try:
            self._items = items_list.split(';')
        except AttributeError:
            self._items = []
        for item in self._items:
            try:
                item_name = self.report_ranges[item][ITEM_NAME]
                self.range_combo.insertItem(self.range_combo.count() - 1, item_name, item)
            except KeyError:
                continue
        self.setCurrentIndex(0)

    ItemsList = Property(str, getConfig, setConfig)

    def connect_signals_and_slots(self):
        self.range_combo.activated.connect(self.onRangeChange)
        self.from_date.dateChanged.connect(self.onFromChange)
        self.to_date.dateChanged.connect(self.onToChange)

    # Shows the days and emits the timestamps that cover them
    def _show_days(self, first, last):
        for editor, day in ((self.from_date, first), (self.to_date, last)):
            editor.blockSignals(True)
            editor.setDate(day if day is not None else local_datetime(0).date())
            editor.blockSignals(False)
        self._begin, self._end = day_bounds(first, last)
        self.changed.emit(self._begin, self._end)

    def _select_custom(self):
        self.range_combo.setCurrentIndex(self.range_combo.findData(CUSTOM))

    # Shows the days that 'begin_ts' and 'end_ts' fall on; a zero 'begin_ts' keeps the range open at the start
    def setRange(self, begin_ts, end_ts):
        self._select_custom()
        first = local_datetime(begin_ts).date() if begin_ts else None
        self._show_days(first, local_datetime(end_ts).date())

    def getRange(self):
        return self._begin, self._end

    @Slot()
    def onRangeChange(self, index):
        item = self.range_combo.itemData(index)
        if item == CUSTOM:
            return
        self._show_days(*self.report_ranges[item][ITEM_METHOD](now_dt().date()))

    @Slot()
    def onFromChange(self):
        if self.from_date.date() > self.to_date.date():
            self.to_date.blockSignals(True)
            self.to_date.setDate(self.from_date.date())
            self.to_date.blockSignals(False)
        self._edited()

    @Slot()
    def onToChange(self):
        if self.to_date.date() < self.from_date.date():
            self.from_date.blockSignals(True)
            self.from_date.setDate(self.to_date.date())
            self.from_date.blockSignals(False)
        self._edited()

    def _edited(self):
        self._select_custom()
        self._begin, self._end = day_bounds(self.from_date.date(), self.to_date.date())
        self.changed.emit(self._begin, self._end)

    def setCurrentIndex(self, index):
        self.range_combo.setCurrentIndex(index)
        self.onRangeChange(index)
