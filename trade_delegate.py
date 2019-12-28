from datetime import datetime
from PySide2.QtCore import Qt
from PySide2.QtSql import QSqlRelationalDelegate

#TODO Check, probably need to combine with dividend_delegate.py
class TradeSqlDelegate(QSqlRelationalDelegate):
    def __init__(self, parent=None):
        QSqlRelationalDelegate.__init__(self, parent)

    def setEditorData(self, editor, index):
        if (index.column() == 1) or (index.column() == 2):  # timestamp & settlement columns
            editor.setDateTime(datetime.fromtimestamp(index.model().data(index, Qt.EditRole)))
        else:
            QSqlRelationalDelegate.setEditorData(self, editor, index)

    def setModelData(self, editor, model, index):
        if (index.column() == 1) or (index.column() == 2):  # timestamp & settlement columns
            timestamp = editor.dateTime().toSecsSinceEpoch()
            model.setData(index, timestamp)
        else:
            QSqlRelationalDelegate.setModelData(self, editor, model, index)