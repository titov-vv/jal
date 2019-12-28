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
        model = index.model()
        type = model.data(index, Qt.DisplayRole)
        fontMetrics = option.fontMetrics
        document = QTextDocument("W")
        option.font.setWeight(QFont.Bold)
        document.setDefaultFont(option.font)
        w = document.idealWidth()
        h = fontMetrics.height()*2
        if (type == 3):
            h = h * 2
        return QSize(w, h)

class OperationsTimestampDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def displayText(self, value, locale):
        return datetime.fromtimestamp(value).strftime('%d/%m/%Y %H:%M:%S')

    def paint(self, painter, option, index):
        painter.save()
        model = index.model()
        timestamp = model.data(index, Qt.DisplayRole)
        text = datetime.fromtimestamp(timestamp).strftime('%d/%m/%Y %H:%M:%S')
        type = model.data(model.index(index.row(), 0), Qt.DisplayRole)
        number = model.data(model.index(index.row(), 6), Qt.DisplayRole)
        if (type == 3):
            text = text + f"\n # {number}"
        painter.drawText(option.rect, Qt.AlignLeft, text)
        painter.restore()

