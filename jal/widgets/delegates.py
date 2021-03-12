from datetime import datetime

from PySide2.QtWidgets import QStyledItemDelegate, QTreeView, QLineEdit
from PySide2.QtCore import Qt
from PySide2.QtGui import QDoubleValidator

from jal.constants import Setup, CustomColor, CorporateAction
from widgets.helpers import g_tr, formatFloatLong


# ----------------------------------------------------------------------------------------------------------------------
# Base class to provide different delegates for WidgetDataMappers in operations widgets
# Separate delegate class is subclassed for every operation widget with own definition of self.delegates for columns
class WidgetMapperDelegateBase(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

        self.timestamp_delegate = TimestampDelegate()
        self.float_delegate = FloatDelegate()
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
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

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
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def formatFloatLong(self, value):
        if abs(value - round(value, 2)) >= Setup.CALC_TOLERANCE:
            text = str(value)
        else:
            text = f"{value:.2f}"
        return text

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
        editor.setText(self.formatFloatLong(float(amount)))

    def paint(self, painter, option, index):
        painter.save()
        try:
            amount = float(index.model().data(index, Qt.DisplayRole))
        except ValueError:
            amount = 0.0
        text = self.formatFloatLong(amount)
        painter.drawText(option.rect, Qt.AlignRight, text)
        painter.restore()

class ReportsFloatDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        painter.save()
        model = index.model()
        record = model.record(index.row())
        amount = record.value(index.column())
        text = formatFloatLong(float(amount)) if amount != '' else ''
        painter.drawText(option.rect, Qt.AlignRight, text)
        painter.restore()
# -----------------------------------------------------------------------------------------------------------------------

class ReportsFloatNDelegate(QStyledItemDelegate):
    def __init__(self, tolerance, parent=None):
        QStyledItemDelegate.__init__(self, parent)
        self._tolerance = tolerance

    def paint(self, painter, option, index):
        painter.save()
        model = index.model()
        record = model.record(index.row())
        amount = record.value(index.column())
        text = f"{amount:.{self._tolerance}f}" if amount != '' else ''
        painter.drawText(option.rect, Qt.AlignRight, text)
        painter.restore()


class ReportsProfitDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        painter.save()
        model = index.model()
        record = model.record(index.row())
        amount = record.value(index.column())
        text = "N/A"
        if amount:
            if amount >= 0:
                painter.fillRect(option.rect, CustomColor.LightGreen)
            else:
                painter.fillRect(option.rect, CustomColor.LightRed)
            text = f"{amount:,.2f}"
        painter.drawText(option.rect, Qt.AlignRight, text)
        painter.restore()


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


class ReportsTimestampDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def displayText(self, value, locale):
        if isinstance(value, str):  # already SQL-preprocessed date
            text = datetime.utcfromtimestamp(int(value)).strftime('%d/%m/%Y')
        else:
            text = datetime.utcfromtimestamp(value).strftime('%d/%m/%Y %H:%M:%S')
        return text


class ReportsYearMonthDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def displayText(self, value, locale):
        text = datetime.utcfromtimestamp(value).strftime('%Y %B')
        return text

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
