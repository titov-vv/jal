from PySide2.QtWidgets import QStyledItemDelegate
from datetime import datetime
from PySide2.QtCore import QSize, Qt, QPoint
from PySide2.QtSql import QSqlRelationalDelegate
from PySide2.QtGui import QTextDocument

class OperationsTimestampDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def displayText(self, value, locale):
        return datetime.fromtimestamp(value).strftime('%d/%m/%Y %H:%M:%S')

    def sizeHint(self, option, index):
        fontMetrics = option.fontMetrics
        value = index.model().data(index)
        text = datetime.fromtimestamp(value).strftime('%d/%m/%Y %H:%M:%S')
        document = QTextDocument(text)
        #option.font.setWeight(QtGui.QFont.Bold)  # new line
        document.setDefaultFont(option.font)
        return QSize(document.idealWidth(), fontMetrics.height())

        # def paint(self, painter, option, index):
    #     if index.column() != 0:
    #         opt = option
    #         # Since we draw the grid ourselves:
    #         opt.rect.adjust(0, 0, -1, -1)
    #         QSqlRelationalDelegate.paint(self, painter, opt, index)
    #     else:
    #         model = index.model()
    #         type = model.data(index, Qt.DisplayRole)
    #         if type == 1:
    #             painter.drawText(QPoint(option.rect.x(), option.rect.y()), "+1")
    #         else:
    #             painter.drawText(QPoint(option.rect.x(), option.rect.y()), "-1")
    #            # Since we draw the grid ourselves:
    #         self.drawFocus(painter, option, option.rect.adjusted(0, 0, -1, -1))
    #
    #     pen = painter.pen()
    #     painter.setPen(option.palette.color(QPalette.Mid))
    #     painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())
    #     painter.drawLine(option.rect.topRight(), option.rect.bottomRight())
    #     painter.setPen(pen)