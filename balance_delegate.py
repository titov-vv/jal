from constants import *
from PySide2.QtWidgets import QStyledItemDelegate
from PySide2.QtGui import QPalette, QBrush
from PySide2.QtCore import Qt

########################################
# FIELD NUMBERS
FIELD_L1        = 0
FIELD_L2        = 1
FIELD_ACCOUNT   = 3
FIELD_ASSET_NAME= 5
FIELD_QTY       = 6
FIELD_OPEN      = 7
FIELD_QUOTE     = 8
FIELD_SHARE     = 9
FIELD_PROFIT_REL = 10
FIELD_PROFIT    = 11

def formatFloatLong(value):
    if (abs(value - round(value)) <= 10e-2):
        text = f"{value:.0f}"
    elif (abs(value - round(value, 2)) <= 10e-4):
        text = f"{value:.2f}"
    elif (abs(value - round(value, 4)) <= 10e-6):
        text = f"{value:.4f}"
    elif (abs(value - round(value, 6)) <= 10e-8):
        text = f"{value:.6f}"
    else:
        text = f"{value:.8f}"
    return text

class BalanceDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        painter.save()
        model = index.model()
        column = index.column()
        record = model.record(index.row())
        value = record.value(column)
        balance = record.value(3)

        if (column == 3) or (column == 5):
            if value == "":
                value = 0
            text = f"{value:,.2f}"
            alignment = Qt.AlignRight
        else:
            text = value
            alignment = Qt.AlignLeft

        if balance == 0:
            font = painter.font()
            font.setBold(True)
            painter.setFont(font)
            if (column == 3) or (column == 4):
                text = ""

        painter.drawText(option.rect, alignment, text)
        painter.restore()

class HoldingsDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        painter.save()
        model = index.model()
        row = index.row()
        column = index.column()

        text = str(model.data(index, Qt.DisplayRole))

        level1 = model.data(model.index(row, FIELD_L1), Qt.DisplayRole)
        level2 = model.data(model.index(row, FIELD_L2), Qt.DisplayRole)

        # Color of header lines background
        if level1:
            painter.fillRect(option.rect, LIGHT_PURPLE_COLOR)
            if column == FIELD_ACCOUNT:
                text = text + " / " + model.data(model.index(row, FIELD_ASSET_NAME), Qt.DisplayRole)
        elif level2:
            painter.fillRect(option.rect, LIGHT_BLUE_COLOR)
        # Set bold font for headers
        if level2:
            font = painter.font()
            font.setBold(True)
            painter.setFont(font)
        else:
            if column == FIELD_ACCOUNT:
                text = ""
            if (column == FIELD_PROFIT) or (column == FIELD_PROFIT_REL):
                amount = model.data(index, Qt.DisplayRole)
                if amount:
                    if amount >= 0:
                        painter.fillRect(option.rect, LIGHT_GREEN_COLOR)
                    else:
                        painter.fillRect(option.rect, LIGHT_RED_COLOR)

        if column <= FIELD_ASSET_NAME:
            alignment = Qt.AlignLeft
        else:
            # if data:
            #     text = formatFloatLong(float(data))
            alignment = Qt.AlignRight

        if (column == FIELD_QTY):
            amount = model.data(index, Qt.DisplayRole)
            if amount == '':
                text = ""
            else:
                text = formatFloatLong(float(amount))

        if (column == FIELD_OPEN):
            amount = model.data(index, Qt.DisplayRole)
            if amount == '':
                text = ""
            else:
                text = f"{amount:.4f}"

        if (column == FIELD_QUOTE):
            amount = model.data(index, Qt.DisplayRole)
            if amount == '':
                text = ""
            else:
                text = f"{amount:.4f}"

        if (column == FIELD_SHARE) or (column == FIELD_PROFIT_REL):
            amount = model.data(index, Qt.DisplayRole)
            if amount == '':
                text = ""
            else:
                text = f"{amount:.2f}"

        if (column >= FIELD_PROFIT):
            amount = model.data(index, Qt.DisplayRole)
            if amount == '':
                text = ""
            else:
                text = f"{amount:,.2f}"

        painter.drawText(option.rect, alignment, text)
        painter.restore()