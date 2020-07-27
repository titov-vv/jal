from constants import *
from CustomUI.helpers import formatFloatLong

from PySide2.QtCore import Qt
from PySide2.QtWidgets import QStyledItemDelegate


class BalanceAccountDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        painter.save()
        model = index.model()
        record = model.record(index.row())
        value = record.value(index.column())
        balance = record.value("balance")
        active_account = record.value("active")

        if not active_account:  # Show inactive accounts in Italic text
            font = painter.font()
            font.setItalic(True)
            painter.setFont(font)

        if balance == 0:
            font = painter.font()
            font.setBold(True)
            painter.setFont(font)

        painter.drawText(option.rect, Qt.AlignLeft, value)
        painter.restore()


class BalanceAmountDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        painter.save()
        model = index.model()
        record = model.record(index.row())
        value = record.value(index.column())
        balance = record.value("balance")

        if balance == 0:
            text = ""
        else:
            if value == "":
                value = 0
            text = f"{value:,.2f}"

        painter.drawText(option.rect, Qt.AlignRight, text)
        painter.restore()


class BalanceCurrencyDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        painter.save()
        model = index.model()
        record = model.record(index.row())
        text = record.value(index.column())
        balance = record.value("balance")

        if balance == 0:
            text = ""

        painter.drawText(option.rect, Qt.AlignLeft, text)
        painter.restore()


class BalanceAmountAdjustedDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        painter.save()
        model = index.model()
        record = model.record(index.row())
        value = record.value(index.column())
        balance = record.value("balance")
        unreconciled_days = record.value("days_unreconciled")

        if unreconciled_days > 7:
            painter.fillRect(option.rect, LIGHT_YELLOW_COLOR)
        if unreconciled_days > 15:
            painter.fillRect(option.rect, LIGHT_RED_COLOR)

        if value == "":
            value = 0
        text = f"{value:,.2f}"

        if balance == 0:
            font = painter.font()
            font.setBold(True)
            painter.setFont(font)

        painter.drawText(option.rect, Qt.AlignRight, text)
        painter.restore()


class HoldingsAccountDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        painter.save()
        model = index.model()
        record = model.record(index.row())
        text = record.value(index.column())
        level1 = record.value("level1")
        level2 = record.value("level2")

        if level1:
            painter.fillRect(option.rect, LIGHT_PURPLE_COLOR)
            text = text + " / " + record.value("asset_name")
        elif level2:
            painter.fillRect(option.rect, LIGHT_BLUE_COLOR)
        else:
            text = ""
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)

        painter.drawText(option.rect, Qt.AlignLeft, text)
        painter.restore()


class HoldingsFloatDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        painter.save()
        model = index.model()
        record = model.record(index.row())
        amount = record.value(index.column())
        level1 = record.value("level1")
        level2 = record.value("level2")

        if level1:
            painter.fillRect(option.rect, LIGHT_PURPLE_COLOR)
        elif level2:
            painter.fillRect(option.rect, LIGHT_BLUE_COLOR)

        if amount == '':
            text = ""
        else:
            text = formatFloatLong(float(amount))

        painter.drawText(option.rect, Qt.AlignRight, text)
        painter.restore()


class HoldingsFloat4Delegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        painter.save()
        model = index.model()
        record = model.record(index.row())
        amount = record.value(index.column())
        level1 = record.value("level1")
        level2 = record.value("level2")

        if level1:
            painter.fillRect(option.rect, LIGHT_PURPLE_COLOR)
        elif level2:
            painter.fillRect(option.rect, LIGHT_BLUE_COLOR)

        if amount == '':
            text = ""
        else:
            text = f"{amount:.4f}"

        painter.drawText(option.rect, Qt.AlignRight, text)
        painter.restore()


class HoldingsProfitDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        painter.save()
        model = index.model()
        record = model.record(index.row())
        amount = record.value(index.column())
        level1 = record.value("level1")
        level2 = record.value("level2")

        if level1:
            painter.fillRect(option.rect, LIGHT_PURPLE_COLOR)
            font = painter.font()
            font.setBold(True)
            painter.setFont(font)
        elif level2:
            painter.fillRect(option.rect, LIGHT_BLUE_COLOR)
            font = painter.font()
            font.setBold(True)
            painter.setFont(font)
        else:
            if amount:
                if amount >= 0:
                    painter.fillRect(option.rect, LIGHT_GREEN_COLOR)
                else:
                    painter.fillRect(option.rect, LIGHT_RED_COLOR)

        if amount == '':
            text = ""
        else:
            text = f"{amount:,.2f}"

        painter.drawText(option.rect, Qt.AlignRight, text)
        painter.restore()


class HoldingsFloat2Delegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        painter.save()
        model = index.model()
        record = model.record(index.row())
        amount = record.value(index.column())
        level1 = record.value("level1")
        level2 = record.value("level2")

        if level1:
            painter.fillRect(option.rect, LIGHT_PURPLE_COLOR)
            font = painter.font()
            font.setBold(True)
            painter.setFont(font)
        elif level2:
            painter.fillRect(option.rect, LIGHT_BLUE_COLOR)
            font = painter.font()
            font.setBold(True)
            painter.setFont(font)

        if amount == '':
            text = ""
        else:
            text = f"{amount:,.2f}"

        painter.drawText(option.rect, Qt.AlignRight, text)
        painter.restore()