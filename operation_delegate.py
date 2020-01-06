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
        amount = model.data(model.index(index.row(), 11), Qt.DisplayRole)
        qty_trid = model.data(model.index(index.row(), 12), Qt.DisplayRole)
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
        type = index.data(Qt.DisplayRole)
        fontMetrics = option.fontMetrics
        document = QTextDocument("W")
        option.font.setWeight(QFont.Bold)
        document.setDefaultFont(option.font)
        w = document.idealWidth()
        h = fontMetrics.height()
        if (type == 2) or (type == 3):
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
        number = model.data(model.index(index.row(), 5), Qt.DisplayRole)
        if (type != 1):
            text = text + f"\n# {number}"
        painter.drawText(option.rect, Qt.AlignLeft, text)
        painter.restore()

class OperationsAccountDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        painter.save()
        model = index.model()
        account = model.data(index, Qt.DisplayRole)
        type = model.data(model.index(index.row(), 0), Qt.DisplayRole)
        if (type == 1):
            #peer = model.data(model.index(index.row(), 5), Qt.DisplayRole)
            text = account #+ "\n" + peer
        elif (type == 2):
            active_name = model.data(model.index(index.row(), 8), Qt.DisplayRole)
            text = account + "\n" + active_name
        elif (type == 3):
            active_name = model.data(model.index(index.row(), 8), Qt.DisplayRole)
            qty = model.data(model.index(index.row(), 12), Qt.DisplayRole)
            price = model.data(model.index(index.row(), 13), Qt.DisplayRole)
            fee = model.data(model.index(index.row(), 14), Qt.DisplayRole)
            if (qty < 0):
                text = account + f"\n{qty:.2f} @ {price:.2f} [f: {fee:.2f}] " + active_name
            else:
                text = account + f"\n+{qty:.2f} @ {price:.2f} [f: {fee:.2f}] " + active_name
        else:
            text = "OperationsAccountDelegate: unknown operation"
        painter.drawText(option.rect, Qt.AlignLeft, text)
        painter.restore()

class OperationsNotesDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        painter.save()
        model = index.model()
        type = model.data(model.index(index.row(), 0), Qt.DisplayRole)
        if (type == 1):
            peer = model.data(model.index(index.row(), 5), Qt.DisplayRole)
            text = peer
        else:
            note = model.data(index, Qt.DisplayRole)
            note2 = model.data(model.index(index.row(), 10), Qt.DisplayRole)
            text = note + "\n" + note2
        painter.drawText(option.rect, Qt.AlignLeft, text)
        painter.restore()

class OperationsAmountDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        painter.save()
        model = index.model()
        amount = model.data(index, Qt.DisplayRole)
        type = model.data(model.index(index.row(), 0), Qt.DisplayRole)
        qty = model.data(model.index(index.row(), 12), Qt.DisplayRole)
        if (type != 1) and (qty != 0):
            text = f"{amount:.2f}\n{qty:.2f}"
        else:
            text = f"{amount:.2f}\n"
        painter.drawText(option.rect, Qt.AlignRight, text)
        painter.restore()

class OperationsTotalsDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        painter.save()
        pen = painter.pen()

        model = index.model()
        total_money = model.data(index, Qt.DisplayRole)
        total_shares = model.data(model.index(index.row(), 16), Qt.DisplayRole)
        reconciled = model.data(model.index(index.row(), 18), Qt.DisplayRole)
        if (total_shares != ''):
            text = f"{total_money:.2f}\n{total_shares:.2f}"
        else:
            text = f"{total_money:.2f}\n"

        if (reconciled == 1):
            pen.setColor(BLUE_COLOR)
            painter.setPen(pen)
        painter.drawText(option.rect, Qt.AlignRight, text)
        painter.restore()

class OperationsCurrencyDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        painter.save()
        model = index.model()
        currency = model.data(index, Qt.DisplayRole)
        active_name = model.data(model.index(index.row(), 7), Qt.DisplayRole)
        text = " " + currency + "\n " + active_name
        painter.drawText(option.rect, Qt.AlignLeft, text)
        painter.restore()