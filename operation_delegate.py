from constants import *
from PySide2.QtWidgets import QStyledItemDelegate
from datetime import datetime
from PySide2.QtCore import QSize, Qt
from PySide2.QtGui import QTextDocument, QFont, QColor

########################################
# FIELD NUMBERS
FIELD_TYPE          = 0
FIELD_ID            = 1
FIELD_TIMESTAMP     = 2
FIELD_ACCOUNT_ID    = 3
FIELD_ACCOUNT       = 4
FIELD_PEER_NUMBER   = 5
FIELD_ASSET_ID     = 6
FIELD_ASSET        = 7
FIELD_ASSET_NAME   = 8
FIELD_NOTE          = 9
FIELD_NOTE2         = 10
FIELD_AMOUNT        = 11
FIELD_QTY_TRID      = 12
FIELD_PRICE         = 13
FIELD_FEE_TAX       = 14
FIELD_TOTAL_AMOUNT  = 15
FIELD_TOTAL_QTY     = 16
FIELD_CURRENCY      = 17
FIELD_RECONCILED    = 18

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
        amount = model.data(model.index(index.row(), FIELD_AMOUNT), Qt.DisplayRole)
        if amount == '':
            amount = 0
        if (type == TRANSACTION_ACTION):
            if (amount >= 0):
                text = "+"
                pen.setColor(DARK_GREEN_COLOR)
            else:
                text = "—"
                pen.setColor(DARK_RED_COLOR)
        elif (type == TRANSACTION_DIVIDEND):
            text = "Δ"
            pen.setColor(DARK_GREEN_COLOR)
        elif (type == TRANSACTION_TRADE):
            if (amount <= 0):  # For Buy we spend money while for Sell we get money
                text = "B"
                pen.setColor(DARK_GREEN_COLOR)
            else:
                text = "S"
                pen.setColor(DARK_RED_COLOR)
        elif (type == TRANSACTION_TRANSFER):
            transfer_subtype = model.data(model.index(index.row(), FIELD_QTY_TRID), Qt.DisplayRole)
            if (transfer_subtype == TRANSFER_IN):
                text = ">"
                pen.setColor(DARK_BLUE_COLOR)
            elif (transfer_subtype == TRANSFER_OUT):
                text = "<"
                pen.setColor(DARK_BLUE_COLOR)
            elif (transfer_subtype == TRANSFER_FEE):
                text = "="
                pen.setColor(DARK_RED_COLOR)
            else:
                assert Falses
        else:
            assert False

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
        if (type == TRANSACTION_DIVIDEND) or (type == TRANSACTION_TRADE):
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
        type = model.data(model.index(index.row(), FIELD_TYPE), Qt.DisplayRole)
        number = model.data(model.index(index.row(), FIELD_PEER_NUMBER), Qt.DisplayRole)
        if (type == TRANSACTION_TRADE) or (type == TRANSACTION_DIVIDEND):
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
        type = model.data(model.index(index.row(), FIELD_TYPE), Qt.DisplayRole)
        if (type == TRANSACTION_ACTION):
            text = account
        elif (type == TRANSACTION_TRADE) or (type == TRANSACTION_DIVIDEND):
            asset_name = model.data(model.index(index.row(), FIELD_ASSET_NAME), Qt.DisplayRole)
            text = account + "\n" + asset_name
        elif (type == TRANSACTION_TRANSFER):
            account2 = model.data(model.index(index.row(), FIELD_NOTE2), Qt.DisplayRole)
            transfer_subtype = model.data(model.index(index.row(), FIELD_QTY_TRID), Qt.DisplayRole)
            if (transfer_subtype == TRANSFER_FEE):
                text = account
            elif (transfer_subtype == TRANSFER_OUT):
                text = account + " -> " + account2
            elif (transfer_subtype == TRANSFER_IN):
                text = account + " <- " + account2
            else:
                assert False
        else:
            assert False
        painter.drawText(option.rect, Qt.AlignLeft, text)
        painter.restore()

class OperationsNotesDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        painter.save()
        model = index.model()
        type = model.data(model.index(index.row(), FIELD_TYPE), Qt.DisplayRole)
        if (type == TRANSACTION_ACTION):
            text = model.data(model.index(index.row(), FIELD_PEER_NUMBER), Qt.DisplayRole)
        elif (type == TRANSACTION_TRANSFER):
            text = model.data(index, Qt.DisplayRole)
        elif (type == TRANSACTION_DIVIDEND):
            note = model.data(index, Qt.DisplayRole)
            note2 = model.data(model.index(index.row(), FIELD_NOTE2), Qt.DisplayRole)
            text = note + "\n" + note2
        elif (type == TRANSACTION_TRADE):
            qty = model.data(model.index(index.row(), FIELD_QTY_TRID), Qt.DisplayRole)
            price = model.data(model.index(index.row(), FIELD_PRICE), Qt.DisplayRole)
            fee = model.data(model.index(index.row(), FIELD_FEE_TAX), Qt.DisplayRole)
            if (fee != 0):
                text = f"{qty:+.2f} @ {price:.2f}\n({fee:.2f})"
            else:
                text = f"{qty:+.2f} @ {price:.2f}"
        else:
            assert False
        painter.drawText(option.rect, Qt.AlignLeft, text)
        painter.restore()

class OperationsAmountDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        painter.save()
        pen = painter.pen()
        rect = option.rect
        H = rect.height()
        Y = rect.top()

        model = index.model()
        amount = model.data(index, Qt.DisplayRole)
        if amount == '':
            amount = 0
        type = model.data(model.index(index.row(), FIELD_TYPE), Qt.DisplayRole)
        qty = model.data(model.index(index.row(), FIELD_QTY_TRID), Qt.DisplayRole)
        tax = model.data(model.index(index.row(), FIELD_FEE_TAX), Qt.DisplayRole)
        if (type == TRANSACTION_TRADE):
            text = f"{amount:+,.2f}"
            rect.setHeight(H / 2)
            if (amount >= 0):
                pen.setColor(DARK_GREEN_COLOR)
            else:
                pen.setColor(DARK_RED_COLOR)
            painter.setPen(pen)
            painter.drawText(option.rect, Qt.AlignRight, text)
            text = f"{qty:+,.2f}"
            rect.moveTop(Y + H / 2)
            if (qty >= 0):
                pen.setColor(DARK_GREEN_COLOR)
            else:
                pen.setColor(DARK_RED_COLOR)
            painter.setPen(pen)
            painter.drawText(option.rect, Qt.AlignRight, text)
        elif (type == TRANSACTION_DIVIDEND):
            text = f"{amount:+,.2f}"
            rect.setHeight(H/2)
            pen.setColor(DARK_GREEN_COLOR)
            painter.setPen(pen)
            painter.drawText(rect, Qt.AlignRight, text)
            text = f"-{tax:,.2f}"
            rect.moveTop(Y+H/2)
            pen.setColor(DARK_RED_COLOR)
            painter.setPen(pen)
            painter.drawText(rect, Qt.AlignRight, text)
        else:
            if (amount >= 0):
                pen.setColor(DARK_GREEN_COLOR)
            else:
                pen.setColor(DARK_RED_COLOR)
            text = f"{amount:+,.2f}\n"
            painter.setPen(pen)
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
        total_shares = model.data(model.index(index.row(), FIELD_TOTAL_QTY), Qt.DisplayRole)
        reconciled = model.data(model.index(index.row(), FIELD_RECONCILED), Qt.DisplayRole)
        if (total_shares != ''):
            text = f"{total_money:,.2f}\n{total_shares:,.2f}"
        elif (total_money != ''):
            text = f"{total_money:,.2f}\n"
        else:
            text = "<void>"

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
        asset_name = model.data(model.index(index.row(), FIELD_ASSET), Qt.DisplayRole)
        text = " " + currency
        if (asset_name != ""):
            text = text + "\n " + asset_name
        painter.drawText(option.rect, Qt.AlignLeft, text)
        painter.restore()