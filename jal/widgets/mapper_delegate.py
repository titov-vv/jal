from datetime import datetime
from PySide2.QtCore import Qt
from PySide2.QtSql import QSqlRelationalDelegate
from PySide2.QtWidgets import QLineEdit
from PySide2.QtGui import QDoubleValidator
from jal.constants import Setup

#TODO combine delegates into one module
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
