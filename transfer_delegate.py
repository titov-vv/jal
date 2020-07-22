from datetime import datetime
from PySide2.QtCore import Qt
from PySide2.QtSql import QSqlRelationalDelegate


class TransferSqlDelegate(QSqlRelationalDelegate):
    def __init__(self, parent=None):
        QSqlRelationalDelegate.__init__(self, parent)

    def setEditorData(self, editor, index):
        if (index.column() == 2) or (index.column() == 5) or (
                index.column() == 8):  # timestamps of from,to and fee docs
            timestamp = index.model().data(index, Qt.EditRole)
            if timestamp == '':
                QSqlRelationalDelegate.setEditorData(self, editor, index)
            else:
                editor.setDateTime(datetime.fromtimestamp(timestamp))
        else:
            QSqlRelationalDelegate.setEditorData(self, editor, index)

        if (index.column() == 10) or (index.column() == 11) or (index.column() == 12):
            amount = index.model().data(index, Qt.EditRole)
            if amount:
                amount = float(amount)
                editor.setText(f"{amount:.2f}")
            else:
                QSqlRelationalDelegate.setEditorData(self, editor, index)

    def setModelData(self, editor, model, index):
        if (index.column() == 2) or (index.column() == 5) or (
                index.column() == 8):  # timestamps of from,to and fee docs
            timestamp = editor.dateTime().toSecsSinceEpoch()
            model.setData(index, timestamp)
        else:
            QSqlRelationalDelegate.setModelData(self, editor, model, index)
