from datetime import datetime
import decimal
from PySide6.QtWidgets import QWidget, QStyledItemDelegate, QLineEdit, QDateTimeEdit, QTreeView
from PySide6.QtCore import Qt, QModelIndex, QEvent, QLocale, QDateTime, QDate, QTime
from PySide6.QtGui import QDoubleValidator, QBrush, QKeyEvent
from jal.constants import CustomColor
from jal.widgets.reference_selector import PeerSelector, CategorySelector, TagSelector
from jal.db.helpers import readSQL


# ----------------------------------------------------------------------------------------------------------------------
# Base class to provide different delegates for WidgetDataMappers in operations widgets
# Separate delegate class is subclassed for every operation widget with own definition of self.delegates for columns
class WidgetMapperDelegateBase(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

        self.timestamp_delegate = TimestampDelegate()
        self.float_delegate = FloatDelegate(2)
        self.default = QStyledItemDelegate()

        self.delegates = {}

    def get_delegate(self, index):
        column = index.column()
        try:
            delegate = self.delegates[column]
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
# Delegate to convert timestamp from unix-time to QDateTime and display it according to the given format
class TimestampDelegate(QStyledItemDelegate):
    def __init__(self, display_format='%d/%m/%Y %H:%M:%S', parent=None):
        QStyledItemDelegate.__init__(self, parent)
        self._format = display_format

    def displayText(self, value, locale):
        if isinstance(value, str):  # in case of SQL aggregates int value comes here in form of string
            value = int(value)
        text = datetime.utcfromtimestamp(value).strftime(self._format) if value else ''
        return text

    def createEditor(self, aParent, option, index):
        editor = DateTimeEditWithReset(aParent)
        editor.setTimeSpec(Qt.UTC)
        if 'H' in self._format:  # we have hours and need DataTime editor to edit it
            editor.setDisplayFormat("dd/MM/yyyy hh:mm:ss")  # TODO should we use QLocale for formats?
        else:
            editor.setDisplayFormat("dd/MM/yyyy")
        return editor

    def setEditorData(self, editor, index):
        timestamp = index.model().data(index, Qt.EditRole)
        if timestamp == '':
            QStyledItemDelegate.setEditorData(self, editor, index)
        else:
            editor.setDateTime(QDateTime.fromSecsSinceEpoch(timestamp, spec=Qt.UTC))

    def setModelData(self, editor, model, index):
        timestamp = editor.dateTime().toSecsSinceEpoch()
        model.setData(index, timestamp)


# -----------------------------------------------------------------------------------------------------------------------
# Delegate for float numbers formatting
# By default has 6 decimal places that may be controlled with 'tolerance' parameter
# 'allow_tail' - display more digits for numbers that have more digits than 'tolerance'
#                and only 'tolerance' digits otherwise
# 'colors' - make Green/Red background for positive/negative values
class FloatDelegate(QStyledItemDelegate):
    DEFAULT_TOLERANCE = 6

    def __init__(self, tolerance=None, allow_tail=True, colors=False, parent=None):
        self._parent = parent
        QStyledItemDelegate.__init__(self, parent)
        try:
            self._tolerance = int(tolerance)
        except (ValueError, TypeError):
            self._tolerance = self.DEFAULT_TOLERANCE
        self._allow_tail = allow_tail
        self._colors = colors
        self._color = None
        self._validator = QDoubleValidator()
        self._validator.setLocale(QLocale().system())

    def formatFloatLong(self, value):
        precision = self._tolerance
        decimal_places = -decimal.Decimal(str(value).rstrip('0')).as_tuple().exponent
        if self._allow_tail and (decimal_places > self._tolerance):
            precision = decimal_places
        return QLocale().toString(value, 'f', precision)

    def displayText(self, value, locale):
        try:
            amount = float(value)
        except ValueError:
            amount = 0.0
        if amount > 0:
            self._color = CustomColor.LightGreen
        elif amount < 0:
            self._color = CustomColor.LightRed
        return self.formatFloatLong(amount)

    # this is required when edit operation is called from QTableView
    def createEditor(self, aParent, option, index):
        float_editor = QLineEdit(aParent)
        float_editor.setValidator(self._validator)
        return float_editor

    def setEditorData(self, editor, index):
        try:
            amount = float(index.model().data(index, Qt.EditRole))
        except (ValueError, TypeError):
            amount = 0.0
        # QLocale().toString works in a bit weird way with float formatting - garbage appears after 5-6 decimal digits
        # if too long precision is specified for short number. So we need to be more precise setting precision.
        decimal_places = -decimal.Decimal(str(amount).rstrip('0')).as_tuple().exponent
        editor.setText(QLocale().toString(amount, 'f', decimal_places))

    def setModelData(self, editor, model, index):
        value = QLocale().toDouble(editor.text())[0]
        model.setData(index, value)

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        option.displayAlignment = Qt.AlignRight
        if self._colors:
            option.backgroundBrush = QBrush(self._color)

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        if type(self._parent) == QTreeView:  # Extra code for tree views - to draw grid lines
            painter.save()
            pen = painter.pen()
            pen.setWidth(1)
            pen.setStyle(Qt.DotLine)
            pen.setColor(Qt.GlobalColor.lightGray)
            painter.setPen(pen)
            painter.drawRect(option.rect)
            painter.restore()


# ----------------------------------------------------------------------------------------------------------------------
# Display '*' if true and empty cell if false
# Toggle True/False by mouse click
class BoolDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        self._parent = parent
        QStyledItemDelegate.__init__(self, parent)

    def displayText(self, value, locale):
        if value:
            return ' ☒ '
        else:
            return ' ☐ '

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        option.displayAlignment = Qt.AlignCenter

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        if type(self._parent) == QTreeView:  # Extra code for tree views - to draw grid lines
            painter.save()
            pen = painter.pen()
            pen.setWidth(1)
            pen.setStyle(Qt.DotLine)
            pen.setColor(Qt.GlobalColor.lightGray)
            painter.setPen(pen)
            painter.drawRect(option.rect)
            painter.restore()

    def editorEvent(self, event, model, option, index):
        if event.type() == QEvent.MouseButtonPress:
            if model.data(index, Qt.DisplayRole):  # Toggle value - from 1 to 0 and from 0 to 1
                model.setData(index, 0)
            else:
                model.setData(index, 1)
        return True


# ----------------------------------------------------------------------------------------------------------------------
# QTreeView doesn't draw grid lines and have no normal method to implement it
# So the purpose of this delegate is solely to draw dotted box around report cell
class GridLinesDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        painter.save()
        pen = painter.pen()
        pen.setWidth(1)
        pen.setStyle(Qt.DotLine)
        pen.setColor(Qt.GlobalColor.lightGray)
        painter.setPen(pen)
        painter.drawRect(option.rect)
        painter.restore()
        super().paint(painter, option, index)


# -----------------------------------------------------------------------------------------------------------------------
# Base class for lookup delegate that allows Peer, Category and Tag selection
class LookupSelectorDelegate(QStyledItemDelegate):
    Category = 1
    Tag = 2
    Peer = 3

    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def displayText(self, value, locale):
        item_name = readSQL(f"SELECT {self._field} FROM {self._table} WHERE id=:id", [(":id", value)])
        return item_name

    def createEditor(self, aParent, option, index):
        if self._type == self.Category:
            selector = CategorySelector(aParent)
        elif self._type == self.Tag:
            selector = TagSelector(aParent)
        elif self._type == self.Peer:
            selector = PeerSelector(aParent)
        else:
            raise ValueError
        return selector

    def setEditorData(self, editor: QWidget, index: QModelIndex) -> None:
        editor.selected_id = index.data()

    def setModelData(self, editor, model, index):
        model.setData(index, editor.selected_id)


class CategorySelectorDelegate(LookupSelectorDelegate):
    def __init__(self, parent=None):
        LookupSelectorDelegate.__init__(self, parent)
        self._type = LookupSelectorDelegate.Category
        self._table = "categories"
        self._field = "name"


class TagSelectorDelegate(LookupSelectorDelegate):
    def __init__(self, parent=None):
        LookupSelectorDelegate.__init__(self, parent)
        self._type = LookupSelectorDelegate.Tag
        self._table = "tags"
        self._field = "tag"


class PeerSelectorDelegate(LookupSelectorDelegate):
    def __init__(self, parent=None):
        LookupSelectorDelegate.__init__(self, parent)
        self._type = LookupSelectorDelegate.Peer
        self._table = "agents"
        self._field = "name"
# -----------------------------------------------------------------------------------------------------------------------
