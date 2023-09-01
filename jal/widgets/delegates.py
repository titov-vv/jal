from datetime import datetime
from decimal import Decimal, InvalidOperation
from PySide6.QtWidgets import QWidget, QStyledItemDelegate, QLineEdit, QDateTimeEdit, QTreeView, QComboBox
from PySide6.QtCore import Qt, QModelIndex, QEvent, QLocale, QDateTime, QDate, QTime, QTimeZone
from PySide6.QtGui import QDoubleValidator, QBrush, QKeyEvent
from jal.constants import CustomColor
from jal.widgets.reference_selector import AssetSelector, PeerSelector, CategorySelector, TagSelector
from jal.db.db import JalModel
from jal.db.helpers import localize_decimal, delocalize_decimal
from jal.db.account import JalAccount


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
# Delegate to convert timestamp from unix-time to QDateTime and display it according to the given format
class TimestampDelegate(QStyledItemDelegate):
    def __init__(self, display_format='%d/%m/%Y %H:%M:%S', parent=None):
        super().__init__(parent=parent)
        self._parent = parent
        self._format = display_format

    def displayText(self, value, locale):
        if isinstance(value, str):  # int value comes here in form of string in case of SQL aggregate function results
            value = int(value)
        text = datetime.utcfromtimestamp(value).strftime(self._format) if value else ''
        return text

    def createEditor(self, aParent, option, index):
        editor = DateTimeEditWithReset(aParent)
        editor.setTimeSpec(Qt.UTC)
        if 'H' in self._format:  # we have hours and need DataTime editor to edit it
            editor.setDisplayFormat("dd/MM/yyyy hh:mm:ss")
        else:
            editor.setDisplayFormat("dd/MM/yyyy")
        return editor

    def setEditorData(self, editor, index):
        timestamp = index.model().data(index, Qt.EditRole)
        if timestamp == '':
            QStyledItemDelegate.setEditorData(self, editor, index)
        else:
            editor.setDateTime(QDateTime.fromSecsSinceEpoch(timestamp, QTimeZone(0)))

    def setModelData(self, editor, model, index):
        timestamp = editor.dateTime().toSecsSinceEpoch()
        model.setData(index, timestamp)

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        if type(self._parent) == QTreeView:    # Extra code for tree views - to draw grid lines
            painter.save()
            pen = painter.pen()
            pen.setWidth(1)
            pen.setStyle(Qt.DotLine)
            pen.setColor(Qt.GlobalColor.lightGray)
            painter.setPen(pen)
            painter.drawRect(option.rect)
            painter.restore()


# -----------------------------------------------------------------------------------------------------------------------
# Delegate for float numbers formatting
# By default has 6 decimal places that may be controlled with 'tolerance' parameter
# 'allow_tail' - display more digits for numbers that have more digits than 'tolerance'
#                and only 'tolerance' digits otherwise
# 'colors' - make Green/Red background for positive/negative values
# 'percent' - multiply values by 100 in order to display percents
# 'empty_zero' - display nothing instead of number 0
class FloatDelegate(QStyledItemDelegate):
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
        except ValueError:
            amount = Decimal('0')
        amount = Decimal('0') if amount.is_nan() else amount  # Protection against occasional NaNs in database
        if self._percent:
            amount *= Decimal('100')
        if amount > Decimal('0'):
            self._color = CustomColor.LightGreen
        elif amount < Decimal('0'):
            self._color = CustomColor.LightRed
        else:
            self._color = None
            if self._empty_zero:
                return ''
        decimal_places = -amount.normalize().as_tuple().exponent
        decimal_places = decimal_places if self._allow_tail and (decimal_places > self._tolerance) else self._tolerance
        return QLocale().toString(float(amount), 'f', decimal_places)

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
        option.displayAlignment = Qt.AlignRight
        if self._colors and self._color is not None:
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
# Delegate to apply currency filter for AssetSelector widgets based on current account
class SymbolDelegate(QStyledItemDelegate):
    def setEditorData(self, editor, index):
        account_currency = JalAccount(index.model().data(index.sibling(index.row(),
                                                                       index.model().fieldIndex('account_id')),
                                                         Qt.EditRole)).currency()
        editor.setFilterValue(account_currency)
        QStyledItemDelegate.setEditorData(self, editor, index)


# ----------------------------------------------------------------------------------------------------------------------
# Display '*' if true and empty cell if false
# Toggle True/False by mouse click
class BoolDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        self._parent = parent
        super().__init__(parent=parent)

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


# ----------------------------------------------------------------------------------------------------------------------
# QTreeView doesn't draw grid lines and have no normal method to implement it
# So the purpose of this delegate is solely to draw dotted box around report cell
class GridLinesDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent=parent)

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
# Base class for lookup delegate that allows Asset, Peer, Category and Tag selection
class LookupSelectorDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._table = ''
        self._field = ''
        self._selector = None

    def displayText(self, value, locale):
        item_name = JalModel(self, self._table).get_value(self._field, "id", value)
        if item_name is None:
            return ''
        else:
            return item_name

    def createSelector(self, parent) -> None:
        raise NotImplementedError("Method createSelector() isn't defined")

    def createEditor(self, aParent, option, index):
        self.createSelector(aParent)
        assert self._selector is not None, "Selector isn't created in LookupSelectorDelegate descendant"
        return self._selector

    def setEditorData(self, editor: QWidget, index: QModelIndex) -> None:
        editor.selected_id = index.data()

    def setModelData(self, editor, model, index):
        if editor.selected_id:  # Check if lookup index is valid or 0
            model.setData(index, editor.selected_id)
        else:
            model.setData(index, None)  # replace invalid index with NULL value


class CategorySelectorDelegate(LookupSelectorDelegate):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._table = "categories"
        self._field = "name"

    def createSelector(self, parent) -> None:
        self._selector = CategorySelector(parent, validate=False)


class TagSelectorDelegate(LookupSelectorDelegate):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._table = "tags"
        self._field = "tag"

    def createSelector(self, parent) -> None:
        self._selector = TagSelector(parent, validate=False)


class PeerSelectorDelegate(LookupSelectorDelegate):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._table = "agents"
        self._field = "name"

    def createSelector(self, parent) -> None:
        self._selector = PeerSelector(parent, validate=False)


class AssetSelectorDelegate(LookupSelectorDelegate):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._table = "assets_ext"
        self._field = "symbol"

    def createSelector(self, parent) -> None:
        self._selector = AssetSelector(parent, validate=False)
