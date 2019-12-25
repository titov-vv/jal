#from PySide2.QtWidgets import QStyledItemDelegate
from PySide2.QtCore import Qt, QPoint
from PySide2.QtSql import QSqlRelationalDelegate
from PySide2.QtGui import QPalette

class OperationsDelegate(QSqlRelationalDelegate):
    def __init__(self, parent=None):
        QSqlRelationalDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        if index.column() != 0:
            opt = option
            # Since we draw the grid ourselves:
            opt.rect.adjust(0, 0, -1, -1)
            QSqlRelationalDelegate.paint(self, painter, opt, index)
        else:
            model = index.model()
            type = model.data(index, Qt.DisplayRole)
            if type == 1:
                painter.drawText(QPoint(option.rect.x(), option.rect.y()), "+1")
            else:
                painter.drawText(QPoint(option.rect.x(), "-1"))
               # Since we draw the grid ourselves:
            self.drawFocus(painter, option, option.rect.adjusted(0, 0, -1, -1))

        pen = painter.pen()
        painter.setPen(option.palette.color(QPalette.Mid))
        painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())
        painter.drawLine(option.rect.topRight(), option.rect.bottomRight())
        painter.setPen(pen)