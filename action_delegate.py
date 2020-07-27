from datetime import datetime
from PySide2.QtCore import Qt
from PySide2.QtSql import QSqlRelationalDelegate
from CustomUI.reference_selector import CategorySelector
from CustomUI.reference_selector import TagSelector


# TODO: Check below delegates and probably move it to view_delegates.py

class ActionDelegate(QSqlRelationalDelegate):
    def __init__(self, parent=None):
        QSqlRelationalDelegate.__init__(self, parent)

    def setEditorData(self, editor, index):
        if index.column() == 1:  # timestamp column
            editor.setDateTime(datetime.fromtimestamp(index.model().data(index, Qt.EditRole)))
        else:
            QSqlRelationalDelegate.setEditorData(self, editor, index)

    def setModelData(self, editor, model, index):
        if index.column() == 1:  # timestamp column
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
            text = ""
            if amount:
                text = f"{amount:.2f}"
            painter.drawText(option.rect, Qt.AlignRight, text)
            painter.restore()
        else:
            QSqlRelationalDelegate.paint(self, painter, option, index)

    def createEditor(self, aParent, option, index):
        if index.column() == 2:  # show category selector
            category_selector = CategorySelector(aParent)
            category_selector.init_db(index.model().database())
            return category_selector
        if index.column() == 3:  # show tag selector
            tag_selector = TagSelector(aParent)
            tag_selector.init_db(index.model().database())
            return tag_selector
        return QSqlRelationalDelegate.createEditor(self, aParent, option, index)

    def setModelData(self, editor, model, index):
        if index.column() == 2:  # Assign category
            model.setData(index, editor.selected_id)
            return
        if index.column() == 3:  # Assign tag
            model.setData(index, editor.selected_id)
            return
        return QSqlRelationalDelegate.setModelData(self, editor, model, index)
