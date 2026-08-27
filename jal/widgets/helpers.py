import base64
import logging
from datetime import time, datetime, timedelta, timezone
from functools import cmp_to_key, partial
from PySide6.QtCore import Qt, QCollator, QItemSelectionModel, QTimer
from PySide6.QtGui import QImage, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QAbstractItemView, QDialog, QTableView, QDateTimeEdit, QStyle,
                               QSplitter)
from jal.constants import Setup
from jal.db.clock import local_moment, local_reading, local_time, window_bound
from jal.db.settings import JalSettings
try:
    from pyzbar import pyzbar
except ImportError:
    pass  # Helpers that use this imports shouldn't be called if imports are absent

# -----------------------------------------------------------------------------------------------------------------------
# Returns True if all modules from module_list are present in the system
def dependency_present(module_list: list) -> bool:
    result = True
    for module in module_list:
        try:
            __import__(module)
        except ImportError:
            result = False
    return result

# -----------------------------------------------------------------------------------------------------------------------
# Menu labels carry Qt mnemonic markup: a single '&' marks the letter after it as an access key, and '&&' stands for
# a literal ampersand (as in 'Income && Spending'). Modules that are loaded dynamically - reports, broker statements,
# blockchain fetchers - supply their own menu label, so the two helpers below are needed to read such a label back.
#
# Returns the label as the user sees it, with all mnemonic markup removed
def menu_label(text: str) -> str:
    return text.replace('&&', '\x00').replace('&', '').replace('\x00', '&')

# Returns the upper-cased access key declared in the label, or an empty string if the label declares none
def menu_mnemonic(text: str) -> str:
    position = 0
    while position < len(text) - 1:
        if text[position] != '&':
            position += 1
        elif text[position + 1] == '&':
            position += 2      # a literal ampersand, not a marker
        else:
            return text[position + 1].upper()
    return ''

# Orders menu items the way the current language orders them, ignoring the mnemonic markup in it so that marking
# an access key can't move an item.
# Where a menu has sections, 'group_of' names the section of an item and ungrouped items come first,
# as their submenus are appended after all plain entries.
def sort_menu_items(items: list, label_of, group_of=None) -> list:
    collator = QCollator()
    collator.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    order = cmp_to_key(collator.compare)
    if group_of is None:
        return sorted(items, key=lambda item: order(menu_label(label_of(item))))
    return sorted(items, key=lambda item: (bool(group_of(item)),
                                           order(menu_label(group_of(item))),
                                           order(menu_label(label_of(item)))))

# -----------------------------------------------------------------------------------------------------------------------
# Check if given signal of an object is connected or not
def is_signal_connected(object, signal_name) -> bool:
    meta_object = object.metaObject()
    method_index = meta_object.indexOfSignal(signal_name)
    return object.isSignalConnected(meta_object.method(method_index))

# -----------------------------------------------------------------------------------------------------------------------
# center given window with respect to main application window
def center_window(window):
    main_window = None
    for widget in QApplication.topLevelWidgets():
        if widget.objectName() == Setup.MAIN_WND_NAME:
            main_window = widget
    if main_window:
        x = main_window.x() + main_window.width() / 2 - window.width() / 2
        y = main_window.y() + main_window.height() / 2 - window.height() / 2
        window.setGeometry(x, y, window.width(), window.height())

# -----------------------------------------------------------------------------------------------------------------------
# Sets the row height of every table inside the given widget (a form as a rule) from the font that the table
# actually uses.
def set_tables_row_height(widget):
    for table in widget.findChildren(QTableView):
        padding = 2 * table.style().pixelMetric(QStyle.PM_FocusFrameVMargin, None, table)
        table.verticalHeader().setDefaultSectionSize(table.fontMetrics().height() + padding)

# -----------------------------------------------------------------------------------------------------------------------
# QMainWindow.saveState() covers toolbars and dock widgets, but not a QSplitter inside the central widget, so here are
# two helpers that do the job of saving/restoring splitter state.
def restore_splitters(widget, prefix: str):
    for splitter in widget.findChildren(QSplitter):
        if not splitter.objectName():
            continue
        state = JalSettings().getValue(prefix + splitter.objectName(), '')
        if state:
            splitter.restoreState(base64.decodebytes(state.encode('utf-8')))


def save_splitters(widget, prefix: str):
    for splitter in widget.findChildren(QSplitter):
        if not splitter.objectName():
            continue
        JalSettings().setValue(prefix + splitter.objectName(),
                               base64.encodebytes(splitter.saveState().data()).decode('utf-8'))

# -----------------------------------------------------------------------------------------------------------------------
# Column widths of a table are set in code (see configureView() of the models) to values that suit the data it shows,
# and the user is free to drag them elsewhere. These helpers keep such a choice between sessions, the way
# save/restore_splitters() above keeps a splitter position: the layout of a header - widths, order, hidden sections
# and the sort indicator - is stored in the database configuration when the window closes and is put back when the
# table is configured again.
#
# The key of a table is built from its own objectName and from the class of the form it belongs to, because the
# name alone is not unique.
def _columns_owner(view):
    owner = view.parentWidget()
    while owner is not None:
        if not type(owner).__module__.startswith('PySide6') or owner.isWindow():
            return owner
        owner = owner.parentWidget()
    return view    # a table with no form around it is keyed by its own class


def columns_state_key(view, prefix: str) -> str:
    return prefix + type(_columns_owner(view)).__name__ + '_' + view.objectName()


# The layout of every table that is open, as the user has it right now. Several reports re-configure their view on
# every change of the report parameters, which re-applies the default widths, so the layout in use has to be held
# somewhere the next configureView() can find it - the database holds the layout of the previous session only.
_live_columns = {}
_pending_capture = set()
_COLUMNS_TRACKED = "jal_columns_key"    # dynamic property that marks a header whose resizes are already followed


# Restores the column layout of a single view: the one in use if the table is already open, the one stored by the
# previous session otherwise. Called at the end of configureView(), so that a width the user has set survives a
# re-configuration of the report as well as it survives a restart.
def restore_columns(view, prefix: str):
    if not view.objectName():
        return
    header = _view_header(view)
    if header is None:
        return
    key = columns_state_key(view, prefix)
    state = _live_columns.get(key)
    if state is None:
        stored = JalSettings().getStr(key)
        state = base64.decodebytes(stored.encode('utf-8')) if stored else None
    if state is not None:
        header.restoreState(state)
        if hasattr(view, 'footer'):
            view.footer().sync_sections()           # restoreState() is silent, so the footer has to be told about it
    if header.property(_COLUMNS_TRACKED) is None:   # from now on the table reports what the user does to it
        header.setProperty(_COLUMNS_TRACKED, key)
        header.sectionResized.connect(partial(_columns_resized, header, key))


# Stores the column layout of every named table/tree inside the given widget (a window as a rule)
def save_columns(widget, prefix: str):
    for view in widget.findChildren(QAbstractItemView):
        if not view.objectName():
            continue
        if isinstance(view.window(), QDialog) and view.window() is not widget.window():
            continue    # a dialog this window merely owns stores its own columns, under its own key
        header = _view_header(view)
        if header is None:
            continue
        key = columns_state_key(view, prefix)
        state = header.saveState()
        _live_columns[key] = state
        JalSettings().setValue(key, base64.encodebytes(state.data()).decode('utf-8'))


# Drops the layouts of the tables that were open. Only a change of the database needs this - the layout of one
# ledger has no meaning in another.
def forget_columns():
    _live_columns.clear()
    _pending_capture.clear()


# A resize is reported per pixel of a drag, and configureView() emits a burst of them while it applies the default
# widths - so the layout is not read here but in the next turn of the event loop, once the table has settled.
# That deferral is what makes the capture correct during a re-configuration: by the time it runs, restore_columns()
# has already put the layout in use back, and it is that layout which is captured rather than the defaults.
def _columns_resized(header, key, *_args):
    if key in _pending_capture:
        return
    _pending_capture.add(key)
    QTimer.singleShot(0, partial(_capture_columns, header, key))


def _capture_columns(header, key):
    _pending_capture.discard(key)
    try:
        _live_columns[key] = header.saveState()
    except RuntimeError:
        pass      # the table was closed before the capture ran, and its layout was stored by that close


# A tree carries its columns in header(), a table in horizontalHeader(); any other view has no columns to store
def _view_header(view):
    for accessor in ('header', 'horizontalHeader'):
        if hasattr(view, accessor):
            return getattr(view, accessor)()
    return None

# -----------------------------------------------------------------------------------------------------------------------
# The single spacing step JAL's layouts are built from - the style's own idea of "related controls" spacing.
# Layouts loaded from .ui files get it from Qt itself, as they simply don't set a spacing of their own; this
# helper is for the few widgets that build their layout in code and need the same value there.
def layout_step(widget) -> int:
    style = widget.style()
    step = style.pixelMetric(QStyle.PM_LayoutHorizontalSpacing, None, widget)
    if step <= 0:
        step = style.pixelMetric(QStyle.PM_DefaultLayoutSpacing, None, widget)
    return step if step > 0 else 6

# -----------------------------------------------------------------------------------------------------------------------
# Gives an icon-only button a keyboard shortcut and names that shortcut in its tooltip.
def assign_shortcut(button, key, scope, context=Qt.WidgetWithChildrenShortcut):
    sequence = QKeySequence(key)
    if sequence.isEmpty():
        return None
    shortcut = QShortcut(sequence, scope)
    shortcut.setContext(context)
    shortcut.activated.connect(button.click)
    if button.toolTip():
        button.setToolTip(f"{button.toolTip()} ({sequence.toString(QKeySequence.NativeText)})")
    return shortcut

# -----------------------------------------------------------------------------------------------------------------------
# A form that shows/hides a few fields based on a checkbox (fee_check, cross_chain_check, etc...) normally does so with
# a plain widget.setVisible() - but a hidden widget's row still resizes to whatever's left visible in it, so the row
# (and everything below it) shifts by a few pixels up/down each time the checkbox is toggled.
# Setting retainSizeWhenHidden keeps the widget's normal size reserved even while hidden, so the row height - and the
# layout below it - stays put.
def set_visible_retaining_size(widget, visible):
    policy = widget.sizePolicy()
    if not policy.retainSizeWhenHidden():
        policy.setRetainSizeWhenHidden(True)
        widget.setSizePolicy(policy)
    widget.setVisible(visible)
# -----------------------------------------------------------------------------------------------------------------------
# Puts a table's selection back where it was.
#
# Needed where picking a row opens the row in an editor and the editor may refuse to let go - an operation with
# unsaved changes asks the user first, and the user may answer "stay here". By then the table has already moved its
# highlight to the row that was clicked, so without this the highlighted row and the form below it would be two
# different operations. The busy flag is what keeps the restore from being read as yet another selection and asking
# the same question again.
class TableSelectionRestorer:
    def __init__(self, view: QTableView):
        self._view = view
        self._busy = False

    def busy(self) -> bool:
        return self._busy

    def restore(self, selection):
        self._busy = True
        try:
            selection_model = self._view.selectionModel()
            selection_model.select(selection, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
            indexes = selection.indexes()
            if indexes:
                selection_model.setCurrentIndex(indexes[0], QItemSelectionModel.NoUpdate)
        finally:
            self._busy = False
# -----------------------------------------------------------------------------------------------------------------------
# Returns true if text does contain only English alphabet
def is_english(text):
    try:
        text.encode(encoding='utf-8').decode(encoding='ascii')
    except UnicodeDecodeError:
        return False
    else:
        return True

# -----------------------------------------------------------------------------------------------------------------------
# converts string with leading zeros to integer (like '03'->3, '00'->0, ''->0)
def str2int(value: str) -> int:
    value = value.lstrip('0')
    if value:
        return int(value)
    else:
        return 0

# -----------------------------------------------------------------------------------------------------------------------
# The date layout is an explicit preference (Preferences -> Interface) and every date the application shows
# is built from the layout chosen here.
class DateFormat:
    EU = 0            # 31/12/2026
    EU_SHORT = 1      # 31/12/26
    US = 2            # 12/31/2026
    US_SHORT = 3      # 12/31/26
    ISO = 4           # 2026-12-31
    DEFAULT = EU
    SETTINGS_KEY = "DateFormat"
    # Format is a tuple of 2 formats (<for Qt display, e.g. QDateEdit>, <for python text rendering>)
    TIME = ("hh:mm:ss", "%H:%M:%S")    # the time part is the same in every layout
    LAYOUTS = {
        EU:       ("dd/MM/yyyy", "%d/%m/%Y"),
        EU_SHORT: ("dd/MM/yy",   "%d/%m/%y"),
        US:       ("MM/dd/yyyy", "%m/%d/%Y"),
        US_SHORT: ("MM/dd/yyyy", "%m/%d"),
        ISO:      ("yyyy-MM-dd", "%Y-%m-%d")
    }
    _current = None   # A date is formatted per table cell, so the setting is read once and cached here

    # Identifier of the layout the user has chosen, or of the default one when nothing valid is stored
    @classmethod
    def current(cls) -> int:
        if cls._current is None:
            try:
                stored = JalSettings().getInt(cls.SETTINGS_KEY, cls.DEFAULT)
            except RuntimeError:
                return cls.DEFAULT   # No database open yet - a date may be rendered before it is (an early log record)
            cls._current = stored if stored in cls.LAYOUTS else cls.DEFAULT
        return cls._current

    # Drops the cached value, so that the next date rendered picks the layout up from the database again
    @classmethod
    def invalidate(cls) -> None:
        cls._current = None

    # Date part of the current layout: 'qt' picks between a QDateEdit display format and a strftime() one
    @classmethod
    def date(cls, qt: bool = False) -> str:
        layout = cls.current()
        return cls.LAYOUTS[layout][0 if qt else 1]

    # Date and time of the current layout, with the arguments of date() above
    @classmethod
    def datetime(cls, qt: bool = False) -> str:
        return cls.date(qt=qt) + ' ' + cls.TIME[0 if qt else 1]

    # Takes a Qt display format that carries any of the known date layouts - the day-first one that the .ui files
    # declare at design time, or one this method has written before - and returns it with the date part replaced
    # by the layout in use now. The time part, and anything else in the format, is left untouched.
    @classmethod
    def localized(cls, display_format: str) -> str:
        for qt_format, _ in sorted(cls.LAYOUTS.values(), key=lambda layout: -len(layout[0])):
            if qt_format in display_format:
                return display_format.replace(qt_format, cls.date(qt=True))
        return display_format


# -----------------------------------------------------------------------------------------------------------------------
# Applies the date layout the user has chosen to every date/time editor inside the given widget (a form as a rule).
# The .ui files keep declaring the day-first layout as their design-time value - a designer has to show something -
# and this call rewrites it into the layout in use, right after setupUi().
def set_date_formats(widget):
    for editor in widget.findChildren(QDateTimeEdit):
        editor.setDisplayFormat(DateFormat.localized(editor.displayFormat()))

# -----------------------------------------------------------------------------------------------------------------------
# Puts the date layout that was just chosen in the preferences dialog into use without a restart: every editor that
# is open takes the new format and every view that is open repaints the dates it renders through a delegate.
def refresh_date_formats():
    DateFormat.invalidate()
    for widget in QApplication.allWidgets():
        if isinstance(widget, QDateTimeEdit):
            widget.setDisplayFormat(DateFormat.localized(widget.displayFormat()))
        elif isinstance(widget, QAbstractItemView):
            widget.viewport().update()

# -----------------------------------------------------------------------------------------------------------------------
# converts given unix-timestamp into string that represents date and time, on the user's own clock (see jal/db/clock.py)
# 'day_only' is an operation saying its timestamp states a day: there is then no time of day to show, and printing the
# digits it happens to be stored with would show an hour that never happened.
def ts2dt(timestamp: int, day_only: bool = False) -> str:
    if day_only:
        return ts2d(timestamp, day_only=True)
    return local_time(timestamp).strftime(DateFormat.datetime())

# -----------------------------------------------------------------------------------------------------------------------
# converts given unix-timestamp into string that represents date
def ts2d(timestamp: int, day_only: bool = False) -> str:
    return local_time(timestamp, day_only).strftime(DateFormat.date())

# -----------------------------------------------------------------------------------------------------------------------
# QDateTimeAxis renders every value it is given through the machine's local time and has no timezone of its own, while
# every date the application shows elsewhere is rendered by ts2dt() on the user's own clock. An axis label would
# therefore sit an offset away from the very cell it labels. These two convert between the two clocks: ts2axis()
# prepares a timestamp for a chart (series point or axis range) and axis2ts() reads back what a chart reports (the
# coordinate of a hovered point). The offset in force at that instant is used, so DST is handled.
def ts2axis(timestamp: int) -> int:
    return int(datetime.fromtimestamp(local_reading(timestamp), tz=timezone.utc).replace(tzinfo=None).timestamp())

def axis2ts(value: int) -> int:
    return local_moment(int(datetime.fromtimestamp(value).replace(tzinfo=timezone.utc).timestamp()))

# -----------------------------------------------------------------------------------------------------------------------
# The same as ts2d() for a value that is already a READING of some other clock - the year bounds a tax report counts
# in, say - and must not be read a second time on the user's.
def reading2d(reading: int) -> str:
    return datetime.fromtimestamp(reading, tz=timezone.utc).strftime(DateFormat.date())

# -----------------------------------------------------------------------------------------------------------------------
# converts a datetime the user named - a month boundary, a day picked in a date field - into the instant at which
# their own clock reached it
def dt2ts(value: datetime) -> int:
    return window_bound(int(value.replace(tzinfo=timezone.utc).timestamp()))

# -----------------------------------------------------------------------------------------------------------------------
# returns unix timestamp for the first second of the month/year
def month_start_ts(year: int, month: int) -> int:
    start = datetime(year=year, month=month, day=1, hour=0, minute=0, second=0)
    return dt2ts(start)

# returns unix timestamp for the first second of the given week of the month
def week_start_ts(year: int, week: int) -> int:
    start = datetime.strptime(f"{year}-W{week}-1", "%Y-W%W-%w")
    return dt2ts(start)

# -----------------------------------------------------------------------------------------------------------------------
# returns unix timestamp for the last second of the month/year
def month_end_ts(year: int, month: int) -> int:
    start = datetime(year=year, month=month, day=1, hour=0, minute=0, second=0)
    if month == 12:
        end = start.replace(year=year + 1, month=1)
    else:
        end = start.replace(month=month + 1)
    end = end - timedelta(seconds=1)
    return dt2ts(end)

# returns unix timestamp for the last second of the given week of the month
def week_end_ts(year: int, week: int) -> int:
    end = datetime.strptime(f"{year}-W{week}-1", "%Y-W%W-%w") + timedelta(days=7)
    return dt2ts(end)

# -----------------------------------------------------------------------------------------------------------------------
# returns an iterator that represents beginning of each day between start_ts unix-timestamp and end_ts unix-timestamp
def timestamp_range(start_ts, end_ts):
    start_date = datetime.fromtimestamp(start_ts, tz=timezone.utc)
    start_date = datetime.combine(start_date, time.min).replace(tzinfo=timezone.utc)
    end_date = datetime.fromtimestamp(end_ts, tz=timezone.utc)
    end_date = datetime.combine(end_date, time.max).replace(tzinfo=timezone.utc)
    for n in range(int((end_date - start_date).days)+1):
        day_n = start_date + timedelta(n)
        yield int(day_n.timestamp())

# -----------------------------------------------------------------------------------------------------------------------
# returns a list of dictionaries for each month between 'begin' and 'end' timestamps (including):
# { year, number, begin_ts, end_ts }
# where number is a month number from 1 to 12
def month_list(begin: int, end: int) -> list:
    result = []
    year_begin = int(local_time(begin).strftime('%Y'))
    month_begin = str2int(local_time(begin).strftime('%m'))
    year_end = int(local_time(end).strftime('%Y'))
    month_end = str2int(local_time(end).strftime('%m'))
    for year in range(year_begin, year_end+1):
        month1 = month_begin if year == year_begin else 1
        month2 = month_end + 1 if year == year_end else 13
        for month in range(month1, month2):
            result.append({'year': year, 'number': month,
                           'begin_ts': month_start_ts(year, month), 'end_ts': month_end_ts(year, month)})
    return result

# returns a list of dictionaries for each week between 'begin' and 'end' timestamps (including):
# { year, number, begin_ts, end_ts }
# where number is a week number in year from 1 to 53
def week_list(begin: int, end: int) -> list:
    result = []
    year_begin = int(local_time(begin).strftime('%Y'))
    week_begin = str2int(local_time(begin).strftime('%W'))
    if week_begin == 0:
        year_begin -= 1
        week_begin = 53
    year_end = int(local_time(end).strftime('%Y'))
    week_end = int(local_time(end).strftime('%W'))
    if week_end == 0:
        year_end -= 1
        week_end = 53
    for year in range(year_begin, year_end + 1):
        wk1 = week_begin if year == year_begin else 1
        wk2 = week_end + 1 if year == year_end else 54
        for week in range(wk1, wk2):
            result.append({'year': year, 'number': week,
                           'begin_ts': week_start_ts(year, week), 'end_ts': week_end_ts(year, week)})
    return result

# ----------------------------------------------------------------------------------------------------------------------
# Function takes an image and searches for QR in it. Content of first found QR is returned. Otherwise - empty string.
def decodeQR(qr_image: QImage, code_type=None) -> str:
    if qr_image.isNull():
        return ''
    if not dependency_present(['pyzbar']):
        logging.warning("Package pyzbar not found for QR recognition.")
        return ''
    if code_type is None:
        code_type = pyzbar.ZBarSymbol.QRCODE
    qr_image.convertTo(QImage.Format_Grayscale8)
    # bytesPerXXX is more accurate than width and height
    data = (qr_image.bits().tobytes(), qr_image.bytesPerLine(), int(qr_image.sizeInBytes()/qr_image.bytesPerLine()))
    barcodes = pyzbar.decode(data, symbols=[code_type])
    if barcodes:
        return barcodes[0].data.decode('utf-8')
    return ''


# -----------------------------------------------------------------------------------------------------------------------
# Helpers to work with datetime
class ManipulateDate:
    # The instant a day of the user's own clock began at - these are the bounds of a date range, so they are read
    # the way the user stated them and not the way a stored row is.
    @staticmethod
    def toTimestamp(date_value):
        time_value = time(0, 0, 0)
        dt_value = datetime.combine(date_value, time_value)
        return window_bound(int(dt_value.replace(tzinfo=timezone.utc).timestamp()))

    @staticmethod
    def PreviousWeek(day=datetime.today()):
        end = day + timedelta(days=1)
        prev_week = day - timedelta(days=7)
        start_of_week = prev_week - timedelta(days=prev_week.weekday())
        return ManipulateDate.toTimestamp(start_of_week), ManipulateDate.toTimestamp(end)

    @staticmethod
    def PreviousMonth(day=datetime.today()):
        end = day + timedelta(days=1)
        first_day_of_month = day.replace(day=1)
        last_day_of_prev_month = first_day_of_month - timedelta(days=1)
        first_day_of_prev_month = last_day_of_prev_month.replace(day=1)
        return ManipulateDate.toTimestamp(first_day_of_prev_month), ManipulateDate.toTimestamp(end)

    @staticmethod
    def PreviousQuarter(day=datetime.today()):
        end = day + timedelta(days=1)
        prev_quarter_month = day.month - day.month % 3 - 3
        if prev_quarter_month > 0:
            quarter_back = day.replace(day=1, month=prev_quarter_month)
        else:
            quarter_back = day.replace(day=1, month=(prev_quarter_month + 12), year=(day.year - 1))
        return ManipulateDate.toTimestamp(quarter_back), ManipulateDate.toTimestamp(end)

    @staticmethod
    def PreviousYear(day=datetime.today()):
        end = day + timedelta(days=1)
        first_day_of_year = day.replace(day=1, month=1)
        last_day_of_prev_year = first_day_of_year - timedelta(days=1)
        first_day_of_prev_year = last_day_of_prev_year.replace(day=1, month=1)
        return ManipulateDate.toTimestamp(first_day_of_prev_year), ManipulateDate.toTimestamp(end)

    @staticmethod
    def QuarterToDate(day=datetime.today()):
        end = day + timedelta(days=1)
        begin_month = day.month - 3
        if begin_month > 0:
            begin = day.replace(day=1, month=begin_month)
        else:
            begin = day.replace(day=1, month=(begin_month + 12), year=(day.year - 1))
        return ManipulateDate.toTimestamp(begin), ManipulateDate.toTimestamp(end)

    @staticmethod
    def YearToDate(day=datetime.today()):
        end = day + timedelta(days=1)
        begin = day.replace(day=1, year=(day.year - 1))
        return ManipulateDate.toTimestamp(begin), ManipulateDate.toTimestamp(end)

    @staticmethod
    def ThisYear(day=datetime.today()):
        end = day + timedelta(days=1)
        begin = day.replace(day=1, month=1)
        return ManipulateDate.toTimestamp(begin), ManipulateDate.toTimestamp(end)

    @staticmethod
    def LastYear(day=datetime.today()):
        end = day.replace(day=1, month=1)
        begin = end.replace(year=(day.year - 1))
        return ManipulateDate.toTimestamp(begin), ManipulateDate.toTimestamp(end)

    @staticmethod
    def AllDates(day=datetime.today()):
        end = day + timedelta(days=1)
        return 0, ManipulateDate.toTimestamp(end)
