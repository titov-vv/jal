from PySide6.QtCore import Qt, Signal, Slot, QDateTime
from PySide6.QtWidgets import QWidget, QComboBox, QHBoxLayout, QLabel, QDateEdit
from jal.widgets.helpers import ManipulateDate


# ----------------------------------------------------------------------------------------------------------------------
class DateRangeSelector(QWidget):
    changed = Signal(int, int)   # emits signal when one or both dates were changed, "from" and "to" timestamps are sent

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self._begin = 0
        self._end = 0
        self.changing_range = False

        self.layout = QHBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.range_combo = QComboBox(self)
        self.range_combo.addItem(self.tr("Quarter to date"))
        self.range_combo.addItem(self.tr("Year to date"))
        self.range_combo.addItem(self.tr("This year"))
        self.range_combo.addItem(self.tr("Previous year"))
        self.layout.addWidget(self.range_combo)

        self.from_label = QLabel(self.tr("From:"), parent=self)
        self.layout.addWidget(self.from_label)

        self.from_date = QDateEdit()
        self.from_date.setDisplayFormat("dd/MM/yyyy")
        self.from_date.setCalendarPopup(True)
        self.from_date.setTimeSpec(Qt.UTC)
        self.layout.addWidget(self.from_date)

        self.from_label = QLabel(self.tr("To:"), parent=self)
        self.layout.addWidget(self.from_label)

        self.to_date = QDateEdit()
        self.to_date.setDisplayFormat("dd/MM/yyyy")
        self.to_date.setCalendarPopup(True)
        self.to_date.setTimeSpec(Qt.UTC)
        self.layout.addWidget(self.to_date)

        self.setLayout(self.layout)

        self.setFocusProxy(self.range_combo)

        self.connect_signals_and_slots()

    def connect_signals_and_slots(self):
        self.range_combo.currentIndexChanged.connect(self.onRangeChange)
        self.from_date.dateChanged.connect(self.onFromChange)
        self.to_date.dateChanged.connect(self.onToChange)

    @Slot()
    def onRangeChange(self, index):
        report_ranges = {
            0: ManipulateDate.Last3Months,
            1: ManipulateDate.RangeYTD,
            2: ManipulateDate.RangeThisYear,
            3: ManipulateDate.RangePreviousYear
        }
        self._begin, self._end = report_ranges[index]()
        self.changing_range = True
        self.from_date.setDateTime(QDateTime.fromSecsSinceEpoch(self._begin, spec=Qt.UTC))
        self.to_date.setDateTime(QDateTime.fromSecsSinceEpoch(self._end, spec=Qt.UTC))
        self.changing_range = False
        self.changed.emit(self._begin, self._end)

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
