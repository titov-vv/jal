from datetime import datetime
from PySide2.QtCore import Qt
from PySide2.QtSql import QSqlRelationalDelegate
from PySide2.QtWidgets import QLineEdit
from PySide2.QtGui import QDoubleValidator
from jal.constants import Setup


# -----------------------------------------------------------------------------------------------------------------------
# Delegate to convert timestamp from unix-time to QDateTime
class TimestampDelegate(QSqlRelationalDelegate):
    def __init__(self, parent=None):
        QSqlRelationalDelegate.__init__(self, parent)

    def setEditorData(self, editor, index):
        timestamp = index.model().data(index, Qt.EditRole)
        if timestamp == '':
            QSqlRelationalDelegate.setEditorData(self, editor, index)
        else:
            editor.setDateTime(datetime.utcfromtimestamp(timestamp))

    def setModelData(self, editor, model, index):
        timestamp = editor.dateTime().toSecsSinceEpoch()
        model.setData(index, timestamp)

# -----------------------------------------------------------------------------------------------------------------------
# Delegate for nice float numbers formatting
class FloatDelegate(QSqlRelationalDelegate):
    def __init__(self, parent=None):
        QSqlRelationalDelegate.__init__(self, parent)

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
        amount = index.model().data(index, Qt.EditRole)
        if amount:
            editor.setText(self.formatFloatLong(float(amount)))
        else:
            QSqlRelationalDelegate.setEditorData(self, editor, index)

    def paint(self, painter, option, index):
        painter.save()
        amount = index.model().data(index, Qt.DisplayRole)
        text = ""
        if amount:
            text = self.formatFloatLong(float(amount))
        painter.drawText(option.rect, Qt.AlignRight, text)
        painter.restore()

# -----------------------------------------------------------------------------------------------------------------------
# Delegate wrapper class which allows proper delegate selection by table/field basis
class MapperDelegate(QSqlRelationalDelegate):
    def __init__(self, parent=None):
        QSqlRelationalDelegate.__init__(self, parent)

        self.timestamp_delegate = TimestampDelegate()
        self.float_delegate = FloatDelegate()

        self.delegates = {
            'actions': {1: self.timestamp_delegate},
            'dividends': {1: self.timestamp_delegate,
                          2: self.timestamp_delegate,
                          7: self.float_delegate,
                          8: self.float_delegate},
            'trades': {1: self.timestamp_delegate,
                       2: self.timestamp_delegate,
                       6: self.float_delegate,
                       7: self.float_delegate,
                       8: self.float_delegate},
            'transfers': {1: self.timestamp_delegate,
                          3: self.float_delegate,
                          4: self.timestamp_delegate,
                          6: self.float_delegate,
                          8: self.float_delegate},
            'corp_actions': {1: self.timestamp_delegate,
                             6: self.float_delegate,
                             8: self.float_delegate,
                             9: self.float_delegate}
        }

    def getDelegate(self, index):
        table = index.model().tableName()
        column = index.column()
        try:
            delegate = self.delegates[table][column]
        except KeyError:
            delegate = None
        return delegate

    def paint(self, painter, option, index):
        delegate = self.getDelegate(index)
        if delegate:
            delegate.paint(painter, option, index)
        else:
            QSqlRelationalDelegate.paint(self, painter, option, index)

    def createEditor(self, aParent, option, index):
        delegate = self.getDelegate(index)
        if delegate:
            return delegate.createEditor(aParent, option, index)
        else:
            return QSqlRelationalDelegate.createEditor(self, aParent, option, index)

    def setEditorData(self, editor, index):
        delegate = self.getDelegate(index)
        if delegate:
            delegate.setEditorData(editor, index)
        else:
            QSqlRelationalDelegate.setEditorData(self, editor, index)

    def setModelData(self, editor, model, index):
        delegate = self.getDelegate(index)
        if delegate:
            delegate.setModelData(editor, model, index)
        else:
            QSqlRelationalDelegate.setModelData(self, editor, model, index)