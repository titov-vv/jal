from datetime import datetime

from PySide2.QtWidgets import QStyledItemDelegate, QTreeView, QLineEdit
from PySide2.QtCore import Qt
from PySide2.QtGui import QDoubleValidator, QBrush

from jal.constants import Setup, CustomColor, CorporateAction
from widgets.helpers import g_tr


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
# Delegate to convert timestamp from unix-time to QDateTime
class TimestampDelegate(QStyledItemDelegate):
    def __init__(self, display_format='%d/%m/%Y %H:%M:%S', parent=None):
        QStyledItemDelegate.__init__(self, parent)
        self._format = display_format

    def displayText(self, value, locale):
        if isinstance(value, str):  # in case of SQL agregates int value comes here in form of string
            value = int(value)
        text = datetime.utcfromtimestamp(value).strftime(self._format)
        return text

    def setEditorData(self, editor, index):
        timestamp = index.model().data(index, Qt.EditRole)
        if timestamp == '':
            QStyledItemDelegate.setEditorData(self, editor, index)
        else:
            editor.setDateTime(datetime.utcfromtimestamp(timestamp))

    def setModelData(self, editor, model, index):
        timestamp = editor.dateTime().toSecsSinceEpoch()
        model.setData(index, timestamp)


# -----------------------------------------------------------------------------------------------------------------------
# Delegate for nice float numbers formatting
class FloatDelegate(QStyledItemDelegate):
    DEFAULT_TOLERANCE = 6

    def __init__(self, tolerance=None, allow_tail=True, colors=False, parent=None):
        QStyledItemDelegate.__init__(self, parent)
        try:
            self._tolerance = int(tolerance)
        except (ValueError, TypeError):
            self._tolerance = self.DEFAULT_TOLERANCE
        self._allow_tail = allow_tail
        self._colors = colors
        self._color = None

    def formatFloatLong(self, value):
        if self._allow_tail and (abs(value - round(value, self._tolerance)) >= Setup.CALC_TOLERANCE):
            text = str(value)
        else:
            text = f"{value:,.{self._tolerance}f}"
        return text

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
        float_editor.setValidator(QDoubleValidator(decimals=2))
        return float_editor

    def setEditorData(self, editor, index):
        try:
            amount = float(index.model().data(index, Qt.EditRole))
        except ValueError:
            amount = 0.0
        editor.setText(f"{amount}")

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        option.displayAlignment = Qt.AlignRight
        if self._colors:
            option.backgroundBrush = QBrush(self._color)


class ReportsCorpActionDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        CorpActionNames = {
            CorporateAction.SymbolChange: g_tr('OperationsDelegate', "Symbol change"),
            CorporateAction.Split: g_tr('OperationsDelegate', "Split"),
            CorporateAction.SpinOff: g_tr('OperationsDelegate', "Spin-off"),
            CorporateAction.Merger: g_tr('OperationsDelegate', "Merger"),
            CorporateAction.StockDividend: g_tr('OperationsDelegate', "Stock dividend")
        }

        painter.save()
        model = index.model()
        record = model.record(index.row())
        type = record.value(index.column())
        if type == '':
            type = 0
        if type > 0:
            text = g_tr('OperationsDelegate', " Opened with ") + CorpActionNames[type]
        elif type < 0:
            text = g_tr('OperationsDelegate', " Closed with ") + CorpActionNames[-type]
        else:
            qty = record.value("qty")
            if qty > 0:
                text = g_tr('OperationsDelegate', " Long")
            else:
                text = g_tr('OperationsDelegate', " Short")
        painter.drawText(option.rect, Qt.AlignLeft, text)
        painter.restore()


class ReportsFloat2ZeroDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        self._parent = parent
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        painter.save()
        pen = painter.pen()
        model = index.model()
        amount = model.data(index, Qt.DisplayRole)
        if amount == 0:
            pen.setColor(CustomColor.Grey)
            painter.setPen(pen)
        text = f"{amount:,.2f}"
        painter.drawText(option.rect, Qt.AlignRight, text)
        # Extra code for tree views - to draw grid lines
        if type(self._parent) == QTreeView:
            pen = painter.pen()
            pen.setWidth(1)
            pen.setStyle(Qt.DotLine)
            pen.setColor(Qt.GlobalColor.lightGray)
            painter.setPen(pen)
            painter.drawRect(option.rect)
        painter.restore()

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
