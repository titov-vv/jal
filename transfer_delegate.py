from datetime import datetime
from PySide2.QtCore import Qt
from PySide2.QtSql import QSqlRelationalDelegate

#TODO Check, probably need to combine with dividend_delegate.py
class TransferSqlDelegate(QSqlRelationalDelegate):
    def __init__(self, parent=None):
        QSqlRelationalDelegate.__init__(self, parent)

    def setEditorData(self, editor, index):
        if (index.column() == 2) or (index.column() == 5) or (index.column() == 8):  # timestamps of from,to and fee docs
            timestamp = index.model().data(index, Qt.EditRole)
            if (timestamp == ''):
                QSqlRelationalDelegate.setEditorData(self, editor, index)
            else:
                editor.setDateTime(datetime.fromtimestamp(timestamp))
        else:
            QSqlRelationalDelegate.setEditorData(self, editor, index)

    def setModelData(self, editor, model, index):
        if (index.column() == 2) or (index.column() == 5) or (index.column() == 8):  # timestamps of from,to and fee docs
            timestamp = editor.dateTime().toSecsSinceEpoch()
            model.setData(index, timestamp)
        else:
            QSqlRelationalDelegate.setModelData(self, editor, model, index)