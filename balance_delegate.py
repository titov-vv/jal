from PySide2.QtWidgets import QStyledItemDelegate
from PySide2.QtCore import Qt
from PySide2.QtGui import QPen,QColor

class BalanceDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        model = index.model()
        record = model.record(index.row())
        value = record.value(4)
        if value < 0:
            painter.font().setBold(True)
            QStyledItemDelegate.paint(self, painter, option, index)
        else:
            QStyledItemDelegate.paint(self, painter, option, index)

    def displayText(self, value, locale):
        if type(value) == float:
            if value == 0:
                res = ""
            else:
                res = '{:.2f}'.format(value, True)
        else:
            res = QStyledItemDelegate.displayText(self, value, locale)
        return res