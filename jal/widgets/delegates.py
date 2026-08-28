from zoneinfo import available_timezones
from decimal import Decimal, InvalidOperation
from PySide6.QtWidgets import (QApplication, QWidget, QStyle, QStyledItemDelegate, QLineEdit, QDateTimeEdit,
                               QTreeView, QComboBox)
from PySide6.QtCore import Qt, QModelIndex, QEvent, QLocale, QDateTime, QDate, QRect, QTime, QTimeZone
from PySide6.QtGui import QDoubleValidator, QBrush, QKeyEvent
from PySide6.QtSql import QSqlQueryModel
from jal.constants import IconOwner, Setup
from jal.widgets.reference_selector import ReferenceSelectorWidget
from jal.db.clock import local_datetime, local_time, local_zone, window_bound
from jal.db.helpers import is_day_marker, localize_decimal, delocalize_decimal
from jal.db.account import JalAccount
from jal.db.icon import JalIcons
from jal.db.asset import JalAsset
from jal.db.symbol import JalSymbol
from jal.widgets.icons import JalIcon
from jal.widgets.helpers import DateFormat, grid_row_height
from jal.widgets.theme import Theme, Meaning


# ----------------------------------------------------------------------------------------------------------------------
# How many LINES the row an index belongs to is laid out for, as the model answers it. A cell may hold fewer values
# than that - a payment with no tax has one amount in a two-line row - and those values belong to the first lines of
# the row, beside the text that made it tall, not to the middle of the empty space. A model that lays its rows out
# in lines answers this role; anything else leaves the cell to be split by what it holds.
ROW_LINES_ROLE = Qt.UserRole + 100


# ----------------------------------------------------------------------------------------------------------------------
# The number of bands a cell of several values is split into: the lines the row was made tall for, and never fewer
# than the values there are to draw.
def cell_bands(index, values: int) -> int:
    lines = index.model().data(index, ROW_LINES_ROLE)
    try:
        return max(int(lines), values)
    except (TypeError, ValueError):
        return values


# ----------------------------------------------------------------------------------------------------------------------
# Draws the background a view item stands on - the selection highlight, the alternating row colour, the hover state -
# through the style that owns them. A delegate that overrides paint() completely has to do this itself: nothing else
# will, and a cell that skips it simply doesn't look selected while the rest of its row does.
def draw_item_panel(painter, option):
    widget = option.widget
    style = widget.style() if widget is not None else QApplication.style()
    style.drawPrimitive(QStyle.PE_PanelItemViewItem, option, painter, widget)


# ----------------------------------------------------------------------------------------------------------------------
# Base class to provide different delegates for WidgetDataMappers in operations widgets
# Separate delegate class is subclassed for every operation widget with own definition of self.delegates for columns
class WidgetMapperDelegateBase(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.timestamp_delegate = TimestampDelegate()
        self.decimal_long_delegate = FloatDelegate(2, allow_tail=True)
        self.decimal_delegate = FloatDelegate(2)
        self.symbol_delegate = SymbolDelegate()
        self.default = QStyledItemDelegate()

        self.delegates = {}

    def get_delegate(self, index):
        column_name = index.model().record().fieldName(index.column())
        try:
            delegate = self.delegates[column_name]
        except KeyError:
            delegate = self.default
        return delegate

    def paint(self, painter, option, index):
        delegate = self.get_delegate(index)
        delegate.paint(painter, option, index)

    def createEditor(self, aParent, option, index):
        delegate = self.get_delegate(index)
        delegate.createEditor(aParent, option, index)

    def setEditorData(self, editor, index):
        delegate = self.get_delegate(index)
        delegate.setEditorData(editor, index)

    def setModelData(self, editor, model, index):
        delegate = self.get_delegate(index)
        delegate.setModelData(editor, model, index)


# ----------------------------------------------------------------------------------------------------------------------
# Custom DateTimeEdit that is able to reset value to None
# i.e. it handles keypress '-', sets timestamp to 0 that effectively cleans the field
class DateTimeEditWithReset(QDateTimeEdit):
    def __init__(self, parent):
        super().__init__(parent)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Minus:
            self.setDateTime(QDateTime(QDate(1970, 1, 1), QTime(0, 0, 0), Qt.UTC))  # = 0 timestamp
        super().keyPressEvent(event)



# ----------------------------------------------------------------------------------------------------------------------
# QTreeView doesn't draw grid lines and have no normal method to implement it
# So the purpose of this delegate is solely to draw dotted box around report cell
class GridLinesDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        self._parent = parent
        super().__init__(parent=parent)

    def paint_grid(self, painter, option, index):
        if issubclass(type(self._parent), QTreeView):  # Extra code for tree views - to draw grid lines
            painter.save()
            pen = painter.pen()
            pen.setWidth(1)
            pen.setStyle(Qt.DotLine)
            pen.setColor(Theme.separator())
            painter.setPen(pen)
            painter.drawRect(option.rect)
            painter.restore()

    def paint(self, painter, option, index):
        self.paint_grid(painter, option, index)
        super().paint(painter, option, index)

    # A tree has no vertical header and thus no default section size: its row is as tall as the tallest sizeHint()
    # among the columns of that row. Reporting the height a table gives its rows keeps a tree and a table in the
    # same window at one row height, and keeps both following the font. I.e. allows to have consistent UI look.
    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        if option.widget is not None:
            size.setHeight(max(size.height(), grid_row_height(option.widget)))
        return size


# ----------------------------------------------------------------------------------------------------------------------
# Delegate to convert timestamp from unix-time to QDateTime and display it in the date layout the user has chosen.
# 'date_only' drops the time part - a settlement date, a quote date and the like carry no meaningful time of day.
# The layout is read for every cell rather than kept here, so that a change of the preference shows at once.
class TimestampDelegate(GridLinesDelegate):
    def __init__(self, date_only: bool = False, parent=None):
        super().__init__(parent=parent)
        self._parent = parent
        self._date_only = date_only

    def displayText(self, value, locale, day_only: bool = False):
        if isinstance(value, str):  # int value comes here in form of string in case of SQL aggregate function results
            try:
                value = int(value)
            except ValueError:
                return self.tr("<invalid>")
        text_format = DateFormat.date() if self._date_only or day_only else DateFormat.datetime()
        text = local_time(value, day_only).strftime(text_format) if value else ''
        return text

    # displayText() is handed the value alone, so a row that says its timestamp states a day is answered here, where
    # the row is still in reach.
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        if self._states_day(index):
            option.text = self.displayText(index.data(Qt.EditRole), option.locale, day_only=True)

    # Whether the row itself says its timestamp states a DAY rather than a moment. An operation that can hold the
    # answer keeps it beside the timestamp, in a column named after it (see jal_init.sql); a row with no such column
    # says nothing and the value is left to answer for itself (see is_day_marker).
    # Only an SQL model is asked: the question is about a table column, and a model that isn't backed by one has no
    # such column to name. Asked of any model that happens to have a record() of its own - a report model keeps one
    # that returns its own row - the call lands on a method that means something entirely different.
    @staticmethod
    def _states_day(index) -> bool:
        model = index.model()
        if not isinstance(model, QSqlQueryModel):
            return False
        flag = model.record().fieldName(index.column()) + '_day_only'
        record = model.record(index.row())
        return bool(record.value(flag)) if record.indexOf(flag) >= 0 else False

    def createEditor(self, aParent, option, index):
        editor = DateTimeEditWithReset(aParent)
        editor.setDisplayFormat(DateFormat.date(qt=True) if self._date_only
                                else DateFormat.datetime(qt=True))
        return editor

    # The editor is put on the clock the value it is given is read on, and Qt converts in both directions from
    # there: it renders the user's own reading and hands back the instant the digits left in it stand for.
    def setEditorData(self, editor, index):
        timestamp = index.model().data(index, Qt.EditRole)
        if timestamp is None or timestamp == '':   # None is an SQL NULL - an optional date that isn't known yet
            QStyledItemDelegate.setEditorData(self, editor, index)
        else:
            day_only = self._states_day(index)
            editor.setTimeZone(local_zone(timestamp, day_only))
            editor.setDateTime(local_datetime(timestamp, day_only))

    def setModelData(self, editor, model, index):
        timestamp = editor.dateTime().toSecsSinceEpoch()
        # A value that states a day is edited on no clock at all (see local_zone), so a time of day typed into one
        # would be stored as if it were Greenwich. A value that says so for itself keeps saying it - what is edited
        # there is which day it is - while one that only spelled it in the value stops being a day the moment it is
        # given a time, and what is left in the editor is then the user's own reading of a moment.
        if editor.timeZone() == QTimeZone(QTimeZone.UTC) and not self._states_day(index) and not is_day_marker(timestamp):
            timestamp = window_bound(timestamp)
        model.setData(index, timestamp)


# -----------------------------------------------------------------------------------------------------------------------
# Delegate for float numbers formatting
# By default has 6 decimal places that may be controlled with 'tolerance' parameter
# 'allow_tail' - display more digits for numbers that have more digits than 'tolerance'
#                and only 'tolerance' digits otherwise
# 'colors' - make Green/Red background for positive/negative values
# 'percent' - multiply values by 100 in order to display percents
# 'empty_zero' - display nothing instead of number 0
class FloatDelegate(GridLinesDelegate):
    DEFAULT_TOLERANCE = 6

    def __init__(self, tolerance=None, allow_tail=True, colors=False, percent=False, empty_zero=False, parent=None):
        self._parent = parent
        super().__init__(parent=parent)
        try:
            self._tolerance = int(tolerance)
        except (ValueError, TypeError):
            self._tolerance = self.DEFAULT_TOLERANCE
        self._allow_tail = allow_tail
        self._colors = colors
        self._color = None
        self._percent = percent
        self._empty_zero = empty_zero
        self._validator = QDoubleValidator()
        self._validator.setLocale(QLocale().system())

    def displayText(self, value, locale):
        try:
            amount = Decimal(value)
        except (TypeError, ValueError, InvalidOperation):
            amount = None
        if amount is None or amount.is_nan():
            return localize_decimal(amount)
        if self._percent:
            amount *= Decimal('100')
        if amount > Decimal('0'):
            self._color = Theme.fill(Meaning.POSITIVE)
        elif amount < Decimal('0'):
            self._color = Theme.fill(Meaning.NEGATIVE)
        else:
            self._color = None
            if self._empty_zero:
                return ''
        decimal_places = -amount.normalize().as_tuple().exponent
        decimal_places = decimal_places if self._allow_tail and (decimal_places > self._tolerance) else self._tolerance
        return localize_decimal(amount, decimal_places)

    # this is required when edit operation is called from QTableView
    def createEditor(self, aParent, option, index):
        float_editor = QLineEdit(aParent)
        float_editor.setValidator(self._validator)
        return float_editor

    def setEditorData(self, editor, index):
        try:
            amount = Decimal(index.model().data(index, Qt.EditRole))
        except (InvalidOperation, TypeError):   # Set to zero if we have None in database
            amount = Decimal('0')
        formatted_text = localize_decimal(amount, precision=self._tolerance, percent=self._percent)
        if self._allow_tail:
            full_text = localize_decimal(amount, percent=self._percent)
            if len(full_text) > len(formatted_text):
                formatted_text = full_text
        editor.setText(formatted_text)

    def setModelData(self, editor, model, index):
        model.setData(index, str(delocalize_decimal(editor.text(), percent=self._percent)))

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        option.displayAlignment = Qt.AlignRight | Qt.AlignVCenter
        if self._colors and self._color is not None:
            option.backgroundBrush = QBrush(self._color)


# ----------------------------------------------------------------------------------------------------------------------
# This is special delegate that have only one purpose - to apply filters for Symbol widgets in operations.
# Currently only currency_id is sent for Asset dialog initialization.
class SymbolDelegate(QStyledItemDelegate):
    def setEditorData(self, editor, index):
        account_id_idx = index.sibling(index.row(), index.model().fieldIndex('account_id'))
        account_currency = JalAccount(index.model().data(account_id_idx, Qt.EditRole)).currency()
        editor.set_dialog_params({"currency_id": account_currency})
        QStyledItemDelegate.setEditorData(self, editor, index)


# ----------------------------------------------------------------------------------------------------------------------
# Toggle True/False by mouse click and display status by relevant icon
class BoolDelegate(GridLinesDelegate):
    def __init__(self, parent=None):
        self._parent = parent
        super().__init__(parent=parent)

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        option.displayAlignment = Qt.AlignCenter

    def paint(self, painter, option, index):
        value = index.model().data(index, Qt.DisplayRole)
        draw_item_panel(painter, option)   # otherwise a selected row loses its highlight in this column
        painter.save()
        if value:
            icon = JalIcon[JalIcon.OK]
        else:
            icon = JalIcon[JalIcon.CANCEL]
        icon.paint(painter, option.rect, Qt.AlignVCenter | Qt.AlignCenter)
        painter.restore()
        self.paint_grid(painter, option, index)

    def editorEvent(self, event, model, option, index):
        if not (index.flags() & Qt.ItemIsEditable):  # honor the model: don't toggle a read-only cell on click
            return super().editorEvent(event, model, option, index)
        if event.type() == QEvent.MouseButtonPress:
            if model.data(index, Qt.DisplayRole):  # Toggle value - from 1 to 0 and from 0 to 1
                model.setData(index, 0)
            else:
                model.setData(index, 1)
        return True


# -----------------------------------------------------------------------------------------------------------------------
# Picks an IANA time zone name (e.g. 'Europe/Berlin'). The names offered are the ones the zone database installed on
# this machine knows, i.e. exactly those that ZoneInfo() will accept afterwards - a name typed by hand couldn't promise
# that. The empty name comes first and means "not stated" (see the 'residence' table).
class TimezoneDelegate(GridLinesDelegate):
    def createEditor(self, aParent, option, index):
        combobox = QComboBox(aParent)
        combobox.addItems([''] + sorted(available_timezones()))
        return combobox

    def setEditorData(self, editor, index):
        editor.setCurrentIndex(editor.findText(index.model().data(index, Qt.EditRole) or ''))

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText())


# -----------------------------------------------------------------------------------------------------------------------
# This delegate is used to present user with a lookup combobox for selection from predefined constant values
# Constructor parameter 'constant_class' indicates which constant set to be used
# (it should be a descendant of PredefinedList class)
class ConstantLookupDelegate(QStyledItemDelegate):
    def __init__(self, constant_class, parent=None):
        self._parent = parent
        super().__init__(parent=parent)
        self.constants = constant_class()

    def displayText(self, value, locale):
        return self.constants.get_name(value)

    def createEditor(self, aParent, option, index):
        combobox = QComboBox(aParent)
        self.constants.load2combo(combobox)
        return combobox

    def setEditorData(self, editor, index):
        idx = editor.findData(index.model().data(index, Qt.EditRole))
        if idx != -1:
            editor.setCurrentIndex(idx)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentData())


# -----------------------------------------------------------------------------------------------------------------------
# Class to allow lookup values selection from reference models
# Parameters:
#   model_class - class of the data model to get values from (from common_models.py). The delegate keeps an instance
#                 of it to display the values of the column.
#   dialog_class - class of the selection dialog to be used for selection (from reference_dialogs.py). It is passed
#                  on to the selector widget, which builds it when the user first asks for it.
#   selector_parent, model_args, dialog_args - passed on to ReferenceSelectorWidget.setup_selector()
class LookupSelectorDelegate(QStyledItemDelegate):
    def __init__(self, parent, model_class, dialog_class, selector_parent=None, model_args=None, dialog_args=None):
        super().__init__(parent=parent)
        self._selector = None
        assert model_class is not None
        assert dialog_class is not None
        self._selector_model_class = model_class
        self._selector_dialog_class = dialog_class
        self._selector_parent = selector_parent
        self._selector_model_args = model_args
        self._selector_dialog_args = dialog_args
        self._selector_model = model_class(parent, **(model_args or {}))

    def displayText(self, value, locale):
        item_name = self._selector_model.getValue(value)
        if item_name is None:
            return ''
        else:
            return item_name

    def createSelector(self, parent) -> None:
        self._selector = ReferenceSelectorWidget(parent, validate=False)
        self._selector.setup_selector(self._selector_model_class, self._selector_dialog_class,
                                      self._selector_parent, self._selector_model_args, self._selector_dialog_args)

    def createEditor(self, aParent, option, index):
        self.createSelector(aParent)
        assert self._selector is not None, "Selector isn't created in LookupSelectorDelegate descendant"
        return self._selector

    def setEditorData(self, editor: QWidget, index: QModelIndex) -> None:
        editor.selected_id = index.data()

    # Value that gets written into the model for a valid selection - subclasses may translate it
    def _stored_value(self, editor):
        return editor.selected_id

    def setModelData(self, editor, model, index):
        if editor.selected_id:  # Check if lookup index is valid or 0
            model.setData(index, self._stored_value(editor))
        else:
            model.setData(index, None)  # replace invalid index with NULL value


# -----------------------------------------------------------------------------------------------------------------------
# Variant of LookupSelectorDelegate for columns that store an asset id while the user thinks in symbols:
# selector model/dialog operate on symbols and symbol<->asset conversion happens at the delegate boundary.
class AssetSelectorDelegate(LookupSelectorDelegate):
    def displayText(self, value, locale):
        return JalAsset(value).symbol()   # active symbols of the asset, comma-separated

    def setEditorData(self, editor: QWidget, index: QModelIndex) -> None:
        symbol_ids = JalAsset(index.data()).active_symbol_ids()
        editor.selected_id = symbol_ids[0] if symbol_ids else 0

    def _stored_value(self, editor):
        return JalSymbol(editor.selected_id).asset().id()


# ----------------------------------------------------------------------------------------------------------------------
# This is a helper function for ColoredAmountsDelegate.
# It returns True if given number has move decimal places than Setup.DEFAULT_ACCOUNT_PRECISION
def long_fraction(x: Decimal) -> bool:
    if x is None:
        return False
    try:
        if x.is_nan():
            return False
    except AttributeError:
        return False
    return abs(x - round(x, Setup.DEFAULT_ACCOUNT_PRECISION)) > Decimal('0')

# ----------------------------------------------------------------------------------------------------------------------
# Draws the last column of the operations list: one ticker per line, each with the logo of the listing it names
# before it. A cell here may hold two or three lines (a trade names the account currency and the asset, a swap names
# what went out, what came in and the fee), so a single decoration centred against the whole cell would belong to
# none of them - the cell is split into a band per line instead, the way ColoredAmountsDelegate splits the amounts
# these tickers stand beside.
class TickerIconsDelegate(GridLinesDelegate):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._parent = parent

    def paint(self, painter, option, index):
        self.paint_grid(painter, option, index)
        draw_item_panel(painter, option)   # otherwise a selected row loses its highlight in this column
        text = index.model().data(index, Qt.DisplayRole)
        if not text:
            return
        lines = text.split("\n")
        listings = index.model().data(index, Qt.DecorationRole)
        if not isinstance(listings, list) or len(listings) != len(lines):
            listings = [0] * len(lines)    # a column that says nothing about its listings gets no icons, not wrong ones
        size = JalIcons.grid_size()
        painter.save()
        if option.state & QStyle.State_Selected:
            pen = painter.pen()
            pen.setColor(option.palette.highlightedText().color())
            painter.setPen(pen)
        height = option.rect.height() / cell_bands(index, len(lines))
        for i, line in enumerate(lines):
            top = int(option.rect.top() + i * height)
            icon = JalIcons.decoration(IconOwner.Symbol, listings[i], size)
            indent = 0
            if icon is not None:   # None where a line has no icon and rows are not indented for the missing ones
                icon.paint(painter, QRect(option.rect.left(), int(top + (height - size) / 2), size, size), Qt.AlignCenter)
                indent = size
            text_rect = QRect(option.rect.left() + indent, top, option.rect.width() - indent, int(height))
            painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter,
                             painter.fontMetrics().elidedText(line, Qt.ElideRight, text_rect.width()))
        painter.restore()


# Display several numbers that provided by the model in form of a list
# Each number is displayed on its own line
# colors - display positive/negative values with green/red color
# signs - display +/- sign before the number if True or only "-" if False
class ColoredAmountsDelegate(QStyledItemDelegate):
    def __init__(self, parent=None, colors=True, signs=True):
        self._view = parent
        self._colors = colors
        self._signs = signs
        super().__init__(parent=parent)

    def paint(self, painter, option, index):
        draw_item_panel(painter, option)  # otherwise a selected row loses its highlight in this column
        data = index.model().data(index)
        if not data:
            return
        painter.save()
        # While a row is selected the style's own pairing wins: the semantic green and red are derived to be
        # readable on the table's ground, not on the highlight color, so they would be the wrong ink for it.
        selected = bool(option.state & QStyle.State_Selected)
        color = option.palette.highlightedText().color() if selected else index.model().data(index, role=Qt.ForegroundRole)
        bands = cell_bands(index, len(data))
        height = option.rect.height() / bands
        for i, item in enumerate(data):
            band = QRect(option.rect.left(), int(option.rect.top() + i * height), option.rect.width(), int(height))
            self.draw_value(band, painter, item, color, colored=self._colors and not selected)
        painter.restore()

    # Displays given value as formatted number with required color (or Green/Red if colored is True)
    # If value is None - do nothing, If value is Decimal.NaN - displays Setup.NULL_VALUE
    def draw_value(self, rect, painter, value, color=None, colored=True):
        text = localize_decimal(value, precision=2, sign=self._signs)
        pen = painter.pen()
        try:
            if self._view.isEnabled():
                if colored:
                    if value is not None and not value.is_nan():
                        if value >= 0:
                            pen.setColor(Theme.text(Meaning.POSITIVE))
                        else:
                            pen.setColor(Theme.text(Meaning.NEGATIVE))
                else:
                    if color is not None:
                        pen.setColor(color)
            painter.setPen(pen)
            painter.drawText(rect, Qt.AlignRight | Qt.AlignVCenter, text)
            if long_fraction(value):  # Underline decimal part
                shift = painter.fontMetrics().horizontalAdvance(text[-Setup.DEFAULT_ACCOUNT_PRECISION:])
                painter.drawLine(rect.right() - shift, rect.bottom(), rect.right(), rect.bottom())
        except (TypeError, AttributeError):
            pass
