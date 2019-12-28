from constants import *
from PySide2.QtWidgets import QStyledItemDelegate
from datetime import datetime
from PySide2.QtCore import QSize, Qt
from PySide2.QtGui import QTextDocument, QFont, QColor

class OperationsTypeDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        painter.save()
        font = painter.font()
        font.setBold(True)
        pen = painter.pen()

        model = index.model()
        type = model.data(index, Qt.DisplayRole)
        amount = model.data(model.index(index.row(), 5), Qt.DisplayRole)
        qty_trid = model.data(model.index(index.row(), 10), Qt.DisplayRole)
        if (type == 1):
            if (qty_trid > 0):
                text = ">"
                pen.setColor(DARK_BLUE_COLOR)
            elif (qty_trid < 0):
                text = "<"
                pen.setColor(DARK_BLUE_COLOR)
            else:
                if (amount >= 0):
                    text = "+"
                    pen.setColor(DARK_GREEN_COLOR)
                else:
                    text = "—"
                    pen.setColor(DARK_RED_COLOR)
        elif (type == 2):
            text = "Δ"
            pen.setColor(DARK_GREEN_COLOR)
        elif (type == 3):
            if (qty_trid >= 0):
                text = "B"
                pen.setColor(DARK_GREEN_COLOR)
            else:
                text = "S"
                pen.setColor(DARK_RED_COLOR)

        painter.setFont(font)
        painter.setPen(pen)
        painter.drawText(option.rect, Qt.AlignCenter, text)
        painter.restore()

    def sizeHint(self, option, index):
        fontMetrics = option.fontMetrics
        document = QTextDocument("W")
        option.font.setWeight(QFont.Bold)
        document.setDefaultFont(option.font)
        return QSize(document.idealWidth(), fontMetrics.height())

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

