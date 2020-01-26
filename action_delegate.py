from datetime import datetime
from PySide2.QtCore import Qt
from PySide2.QtSql import QSqlRelationalDelegate
from CustomUI.category_select import CategorySelector

class ActionDelegate(QSqlRelationalDelegate):
    def __init__(self, parent=None):
        QSqlRelationalDelegate.__init__(self, parent)

    def setEditorData(self, editor, index):
        if (index.column() == 1):  # timestamp column
            editor.setDateTime(datetime.fromtimestamp(index.model().data(index, Qt.EditRole)))
        else:
            QSqlRelationalDelegate.setEditorData(self, editor, index)

    def setModelData(self, editor, model, index):
        if (index.column() == 1):  # timestamp column
            timestamp = editor.dateTime().toSecsSinceEpoch()
            model.setData(index, timestamp)
        else:
            QSqlRelationalDelegate.setModelData(self, editor, model, index)

# This also helps to display Drop-down list for lookup fields
class ActionDetailDelegate(QSqlRelationalDelegate):
    def __init__(self, parent=None):
        QSqlRelationalDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        if (index.column() == 4) or (index.column() == 5):  # format float precision for sum and alternative sum
            painter.save()
            amount = index.model().data(index, Qt.DisplayRole)
            if amount == 0:
                text = ""
            else:
                text = f"{amount:.2f}"
            painter.drawText(option.rect, Qt.AlignRight, text)
            painter.restore()
        else:
            QSqlRelationalDelegate.paint(self, painter, option, index)

    def createEditor(self, aParent, option, index):
        if index.column() != 2:
            return QSqlRelationalDelegate.createEditor(self, aParent, option, index)
        # show category selector
        category_selector = CategorySelector(aParent)
        category_selector.init_DB(index.model().database())
        return category_selector

    def setModelData(self, editor, model, index):
        if index.column() != 2:
            return QSqlRelationalDelegate.setModelData(self, editor, model, index)
        # Assign category
        model.setData(index, editor.category_id)