from datetime import datetime

from PySide2.QtWidgets import QStyledItemDelegate
from PySide2.QtCore import Qt, QSize
from PySide2.QtGui import QTextDocument, QFont

from constants import TransactionType, TransferSubtype, CustomColor
from CustomUI.helpers import formatFloatLong


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
            painter.fillRect(option.rect, CustomColor.LightYellow)
        if unreconciled_days > 15:
            painter.fillRect(option.rect, CustomColor.LightRed)

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
            painter.fillRect(option.rect, CustomColor.LightPurple)
            text = text + " / " + record.value("asset_name")
        elif level2:
            painter.fillRect(option.rect, CustomColor.LightBlue)
        else:
            text = ""
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)

        painter.drawText(option.rect, Qt.AlignLeft, text)
        painter.restore()


# TODO: Check holdings float formatting delegates for possible optimization
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
            painter.fillRect(option.rect, CustomColor.LightPurple)
        elif level2:
            painter.fillRect(option.rect, CustomColor.LightBlue)

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
            painter.fillRect(option.rect, CustomColor.LightPurple)
        elif level2:
            painter.fillRect(option.rect, CustomColor.LightBlue)

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
            painter.fillRect(option.rect, CustomColor.LightPurple)
            font = painter.font()
            font.setBold(True)
            painter.setFont(font)
        elif level2:
            painter.fillRect(option.rect, CustomColor.LightBlue)
            font = painter.font()
            font.setBold(True)
            painter.setFont(font)
        else:
            if amount:
                if amount >= 0:
                    painter.fillRect(option.rect, CustomColor.LightGreen)
                else:
                    painter.fillRect(option.rect, CustomColor.LightRed)

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
            painter.fillRect(option.rect, CustomColor.LightPurple)
            font = painter.font()
            font.setBold(True)
            painter.setFont(font)
        elif level2:
            painter.fillRect(option.rect, CustomColor.LightBlue)
            font = painter.font()
            font.setBold(True)
            painter.setFont(font)

        if amount == '':
            text = ""
        else:
            text = f"{amount:,.2f}"

        painter.drawText(option.rect, Qt.AlignRight, text)
        painter.restore()


class OperationsTypeDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        painter.save()
        font = painter.font()
        font.setBold(True)
        pen = painter.pen()

        model = index.model()
        record = model.record(index.row())
        transaction_type = record.value(index.column())
        amount = record.value("amount")
        if amount == '':
            amount = 0
        if transaction_type == TransactionType.Action:
            if amount >= 0:
                text = "+"
                pen.setColor(CustomColor.DarkGreen)
            else:
                text = "—"
                pen.setColor(CustomColor.DarkRed)
        elif transaction_type == TransactionType.Dividend:
            text = "Δ"
            pen.setColor(CustomColor.DarkGreen)
        elif transaction_type == TransactionType.Trade:
            if amount <= 0:  # TODO Change from amount to qty as amount might be 0 for Corp.Actions
                text = "B"
                pen.setColor(CustomColor.DarkGreen)
            else:
                text = "S"
                pen.setColor(CustomColor.DarkRed)
        elif transaction_type == TransactionType.Transfer:
            transfer_subtype = record.value("qty_trid")
            if transfer_subtype == TransferSubtype.Incoming:
                text = ">"
                pen.setColor(CustomColor.DarkBlue)
            elif transfer_subtype == TransferSubtype.Outgoing:
                text = "<"
                pen.setColor(CustomColor.DarkBlue)
            elif transfer_subtype == TransferSubtype.Fee:
                text = "="
                pen.setColor(CustomColor.DarkRed)
            else:
                assert False
        else:
            assert False

        painter.setFont(font)
        painter.setPen(pen)
        painter.drawText(option.rect, Qt.AlignCenter, text)
        painter.restore()

    def sizeHint(self, option, index):
        transaction_type = index.data(Qt.DisplayRole)
        fontMetrics = option.fontMetrics
        document = QTextDocument("W")
        option.font.setWeight(QFont.Bold)
        document.setDefaultFont(option.font)
        w = document.idealWidth()
        h = fontMetrics.height()
        if (transaction_type == TransactionType.Dividend) or (transaction_type == TransactionType.Trade):
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
        record = model.record(index.row())
        timestamp = record.value(index.column())
        transaction_type = record.value("type")
        number = record.value("num_peer")
        text = datetime.fromtimestamp(timestamp).strftime('%d/%m/%Y %H:%M:%S')
        if (transaction_type == TransactionType.Trade) or (transaction_type == TransactionType.Dividend):
            text = text + f"\n# {number}"
        painter.drawText(option.rect, Qt.AlignLeft, text)
        painter.restore()


class OperationsAccountDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        painter.save()
        model = index.model()
        record = model.record(index.row())
        account = record.value(index.column())
        transaction_type = record.value("type")
        if transaction_type == TransactionType.Action:
            text = account
        elif (transaction_type == TransactionType.Trade) or (transaction_type == TransactionType.Dividend):
            asset_name = record.value("asset_name")
            text = account + "\n" + asset_name
        elif transaction_type == TransactionType.Transfer:
            account2 = record.value("note2")
            transfer_subtype = record.value("qty_trid")
            if transfer_subtype == TransferSubtype.Fee:
                text = account
            elif transfer_subtype == TransferSubtype.Outgoing:
                text = account + " -> " + account2
            elif transfer_subtype == TransferSubtype.Incoming:
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
        record = model.record(index.row())
        transaction_type = record.value("type")
        if transaction_type == TransactionType.Action:
            text = record.value("num_peer")
        elif transaction_type == TransactionType.Transfer:
            text = record.value(index.column())
        elif transaction_type == TransactionType.Dividend:
            text = record.value(index.column()) + "\n" + record.value("note2")
        elif transaction_type == TransactionType.Trade:
            # Take corp.action description if any or construct Qty x Price for Buy/Sell operations
            text = record.value(index.column())
            if not text:
                qty = record.value("qty_trid")
                price = record.value("price")
                fee = record.value("fee_tax")
                if fee != 0:
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
        record = model.record(index.row())
        amount = record.value(index.column())
        if amount == '':
            amount = 0
        transaction_type = record.value("type")
        qty = record.value("qty_trid")
        tax = record.value("fee_tax")
        if transaction_type == TransactionType.Trade:
            text = f"{amount:+,.2f}"
            rect.setHeight(H / 2)
            if amount >= 0:
                pen.setColor(CustomColor.DarkGreen)
            else:
                pen.setColor(CustomColor.DarkRed)
            painter.setPen(pen)
            painter.drawText(option.rect, Qt.AlignRight, text)
            text = f"{qty:+,.2f}"
            rect.moveTop(Y + H / 2)
            if qty >= 0:
                pen.setColor(CustomColor.DarkGreen)
            else:
                pen.setColor(CustomColor.DarkRed)
            painter.setPen(pen)
            painter.drawText(option.rect, Qt.AlignRight, text)
        elif transaction_type == TransactionType.Dividend:
            text = f"{amount:+,.2f}"
            rect.setHeight(H / 2)
            pen.setColor(CustomColor.DarkGreen)
            painter.setPen(pen)
            painter.drawText(rect, Qt.AlignRight, text)
            text = f"{tax:,.2f}"
            rect.moveTop(Y + H / 2)
            pen.setColor(CustomColor.DarkRed)
            painter.setPen(pen)
            painter.drawText(rect, Qt.AlignRight, text)
        else:
            if amount >= 0:
                pen.setColor(CustomColor.DarkGreen)
            else:
                pen.setColor(CustomColor.DarkRed)
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
        record = model.record(index.row())
        total_money = record.value(index.column())
        total_shares = record.value("t_qty")
        reconciled = record.value("reconciled")
        upper_part = "<void>"
        lower_part = ''
        if total_shares != '':
            lower_part = f"{total_shares:,.2f}"
        if total_money != '':
            upper_part = f"{total_money:,.2f}"
        text = upper_part + "\n" + lower_part

        if reconciled == 1:
            pen.setColor(CustomColor.Blue)
            painter.setPen(pen)

        painter.drawText(option.rect, Qt.AlignRight, text)
        painter.restore()


class OperationsCurrencyDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        painter.save()
        model = index.model()
        record = model.record(index.row())
        currency = record.value(index.column())
        asset_name = record.value("asset")
        text = " " + currency
        if asset_name != "":
            text = text + "\n " + asset_name
        painter.drawText(option.rect, Qt.AlignLeft, text)
        painter.restore()
