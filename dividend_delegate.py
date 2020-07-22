from datetime import datetime
from PySide2.QtCore import Qt
from PySide2.QtSql import QSqlRelationalDelegate


class DividendSqlDelegate(QSqlRelationalDelegate):
    def __init__(self, parent=None):
        QSqlRelationalDelegate.__init__(self, parent)

    def setEditorData(self, editor, index):
        if index.column() == 1:  # timestamp column
            editor.setDateTime(datetime.fromtimestamp(index.model().data(index, Qt.EditRole)))
        else:
            QSqlRelationalDelegate.setEditorData(self, editor, index)
        if (index.column() == 5) or (index.column() == 6):  # sum and tax amounts
            amount = index.model().data(index, Qt.EditRole)
            if amount:
                amount = float(amount)
                editor.setText(f"{amount:.2f}")
            else:
                QSqlRelationalDelegate.setEditorData(self, editor, index)

    def setModelData(self, editor, model, index):
        if index.column() == 1:  # timestamp column
            timestamp = editor.dateTime().toSecsSinceEpoch()
            model.setData(index, timestamp)
        else:
            QSqlRelationalDelegate.setModelData(self, editor, model, index)
