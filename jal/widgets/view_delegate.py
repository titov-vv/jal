from datetime import datetime
from math import copysign

from PySide2.QtWidgets import QStyledItemDelegate
from PySide2.QtCore import Qt, QSize
from PySide2.QtGui import QTextDocument, QFont

from jal.constants import TransactionType, TransferSubtype, CustomColor, CorporateAction
from jal.ui_custom.helpers import g_tr, formatFloatLong
from jal.ui_custom.reference_selector import CategorySelector, TagSelector
from jal.db.helpers import get_category_name


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
        OperationSign = {
            (TransactionType.Action, -1): ('—', CustomColor.DarkRed),
            (TransactionType.Action, +1): ('+', CustomColor.DarkGreen),
            (TransactionType.Dividend, 0): ('Δ', CustomColor.DarkGreen),
            (TransactionType.Trade, -1): ('S', CustomColor.DarkRed),
            (TransactionType.Trade, +1): ('B', CustomColor.DarkGreen),
            (TransactionType.Transfer, TransferSubtype.Outgoing): ('<', CustomColor.DarkBlue),
            (TransactionType.Transfer, TransferSubtype.Incoming): ('>', CustomColor.DarkBlue),
            (TransactionType.Transfer, TransferSubtype.Fee): ('=', CustomColor.DarkRed),
            (TransactionType.CorporateAction, CorporateAction.Merger): ('⭃', CustomColor.Black),
            (TransactionType.CorporateAction, CorporateAction.SpinOff): ('⎇', CustomColor.DarkGreen),
            (TransactionType.CorporateAction, CorporateAction.Split): ('ᗕ', CustomColor.Black),
            (TransactionType.CorporateAction, CorporateAction.SymbolChange): ('🡘', CustomColor.Black),
            (TransactionType.CorporateAction, CorporateAction.StockDividend): ('Δ\ns', CustomColor.DarkGreen)
        }

        painter.save()
        font = painter.font()
        font.setBold(True)
        pen = painter.pen()

        model = index.model()
        record = model.record(index.row())
        transaction_type = record.value(index.column())
        if transaction_type == TransactionType.Action:
            sub_type = copysign(1, record.value("amount"))
        elif transaction_type == TransactionType.Trade:
            sub_type = copysign(1, record.value("qty_trid"))
        elif transaction_type == TransactionType.Transfer:
            sub_type = record.value("qty_trid")
        elif transaction_type == TransactionType.CorporateAction:
            sub_type = record.value("fee_tax")
        else:
            sub_type = 0

        try:
            text = OperationSign[transaction_type, sub_type][0]
            pen.setColor(OperationSign[transaction_type, sub_type][1])
        except:
            text = '?'
            pen.setColor(CustomColor.LightRed)

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
        if (transaction_type == TransactionType.Dividend) \
                or (transaction_type == TransactionType.Trade) \
                or (transaction_type == TransactionType.CorporateAction):
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
        if (transaction_type == TransactionType.Trade) \
                or (transaction_type == TransactionType.Dividend) \
                or (transaction_type == TransactionType.CorporateAction):
            text = text + f"\n# {number}"
        painter.drawText(option.rect, Qt.AlignLeft | Qt.AlignVCenter, text)
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
        elif (transaction_type == TransactionType.Trade) \
                or (transaction_type == TransactionType.Dividend) \
                or (transaction_type == TransactionType.CorporateAction):
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
        painter.drawText(option.rect, Qt.AlignLeft | Qt.AlignVCenter, text)
        painter.restore()


class OperationsNotesDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        CorpActionNames = {
            CorporateAction.SymbolChange: g_tr('OperationsDelegate', "Symbol change {old} -> {new}"),
            CorporateAction.Split: g_tr('OperationsDelegate', "Split {old} {before} into {after}"),
            CorporateAction.SpinOff: g_tr('OperationsDelegate', "Spin-off {after} {new} from {before} {old}"),
            CorporateAction.Merger: g_tr('OperationsDelegate', "Merger {before} {old} into {after} {new}"),
            CorporateAction.StockDividend: g_tr('OperationsDelegate', "Stock dividend: {after} {new}")
        }

        painter.save()
        model = index.model()
        record = model.record(index.row())
        transaction_type = record.value("type")
        if transaction_type == TransactionType.Action:
            text = record.value("num_peer")
        elif transaction_type == TransactionType.Transfer:
            exchange_text = ''
            currency1 = record.value("currency")
            currency2 = record.value("num_peer")
            rate_text = record.value("price")
            if rate_text == '':
                rate = 0
            else:
                rate = -rate_text           # TODO Fix negative rate values in database
            if currency1 != currency2:
                if rate != 0:
                    if rate > 1:
                        exchange_text = f" [1 {currency1} = {rate:.4f} {currency2}]"
                    else:
                        rate = 1 / rate
                        exchange_text = f" [{rate:.4f} {currency1} = 1 {currency2}]"
                else:
                    exchange_text = g_tr('OperationsDelegate', "Error. Zero rate")
            text = record.value(index.column()) + exchange_text
        elif transaction_type == TransactionType.Dividend:
            text = record.value(index.column()) + "\n" + g_tr('OperationsDelegate', "Tax: ") + record.value("note2")
        elif transaction_type == TransactionType.Trade:
            qty = record.value("qty_trid")
            price = record.value("price")
            fee = record.value("fee_tax")
            if fee != 0:
                text = f"{qty:+.2f} @ {price:.2f}\n({fee:.2f})"
            else:
                text = f"{qty:+.2f} @ {price:.2f}"
        elif transaction_type == TransactionType.CorporateAction:
            sub_type = record.value("fee_tax")
            symbol_before = record.value("asset")
            symbol_after = record.value("note")
            qty_before = record.value("amount")
            qty_after = record.value("qty_trid")
            text = CorpActionNames[sub_type].format(old=symbol_before, new=symbol_after,
                                                         before=qty_before, after=qty_after) \
                   + "\n" + record.value("note2")
        else:
            assert False
        painter.drawText(option.rect, Qt.AlignLeft | Qt.AlignVCenter, text)
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
            painter.drawText(option.rect, Qt.AlignRight  | Qt.AlignVCenter, text)
            text = f"{qty:+,.2f}"
            rect.moveTop(Y + H / 2)
            if qty >= 0:
                pen.setColor(CustomColor.DarkGreen)
            else:
                pen.setColor(CustomColor.DarkRed)
            painter.setPen(pen)
            painter.drawText(option.rect, Qt.AlignRight | Qt.AlignVCenter, text)
        elif transaction_type == TransactionType.Dividend:
            text = f"{amount:+,.2f}"
            rect.setHeight(H / 2)
            pen.setColor(CustomColor.DarkGreen)
            painter.setPen(pen)
            painter.drawText(rect, Qt.AlignRight, text)
            text = f"-{tax:,.2f}"    # Tax is always negative so sign is fixed here
            rect.moveTop(Y + H / 2)
            pen.setColor(CustomColor.DarkRed)
            painter.setPen(pen)
            painter.drawText(option.rect, Qt.AlignRight | Qt.AlignVCenter, text)
        elif transaction_type == TransactionType.Action or transaction_type == TransactionType.Transfer:
            if amount >= 0:
                pen.setColor(CustomColor.DarkGreen)
            else:
                pen.setColor(CustomColor.DarkRed)
            text = f"{amount:+,.2f}"
            painter.setPen(pen)
            painter.drawText(option.rect, Qt.AlignRight | Qt.AlignVCenter, text)
        elif transaction_type == TransactionType.CorporateAction:
            sub_type = record.value("fee_tax")
            qty_before = -record.value("amount")
            qty_after = record.value("qty_trid")
            if sub_type == CorporateAction.SpinOff or sub_type == CorporateAction.StockDividend:
                text = ""
            else:
                text = f"{qty_before:+,.2f}"
            rect.setHeight(H / 2)
            pen.setColor(CustomColor.DarkRed)
            painter.setPen(pen)
            painter.drawText(option.rect, Qt.AlignRight | Qt.AlignVCenter, text)
            text = f"{qty_after:+,.2f}"
            rect.moveTop(Y + H / 2)
            pen.setColor(CustomColor.DarkGreen)
            painter.setPen(pen)
            painter.drawText(option.rect, Qt.AlignRight | Qt.AlignVCenter, text)
        else:
            assert False
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
        transaction_type = record.value("type")
        total_shares = record.value("t_qty")
        reconciled = record.value("reconciled")
        upper_part = "<void>"
        lower_part = ''
        if total_shares != '':
            lower_part = f"{total_shares:,.2f}"
        if total_money != '':
            upper_part = f"{total_money:,.2f}"
        if transaction_type == TransactionType.CorporateAction:
            sub_type = record.value("fee_tax")
            qty_before = record.value("amount") if sub_type ==CorporateAction.SpinOff else 0
            qty_after = record.value("t_qty") if sub_type == CorporateAction.StockDividend else record.value("qty_trid")
            if sub_type == CorporateAction.StockDividend:
                text = f"\n{qty_after:,.2f}" if qty_after != '' else '\n<void>'
            else:
                text = f"{qty_before:,.2f}\n{qty_after:,.2f}"
        elif transaction_type == TransactionType.Action or transaction_type == TransactionType.Transfer:
            text = upper_part
        else:
            text = upper_part + "\n" + lower_part

        if reconciled == 1:
            pen.setColor(CustomColor.Blue)
            painter.setPen(pen)

        painter.drawText(option.rect, Qt.AlignRight | Qt.AlignVCenter, text)
        painter.restore()


class OperationsCurrencyDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        painter.save()
        model = index.model()
        record = model.record(index.row())
        transaction_type = record.value("type")
        if transaction_type == TransactionType.CorporateAction:
            sub_type = record.value("fee_tax")
            asset_before = record.value("asset") if sub_type != CorporateAction.StockDividend else ""
            asset_after = record.value("note")
            text = f" {asset_before}\n {asset_after}"
        else:
            currency = record.value(index.column())
            asset_name = record.value("asset")
            text = " " + currency
            if asset_name != "":
                text = text + "\n " + asset_name
        painter.drawText(option.rect, Qt.AlignLeft | Qt.AlignVCenter, text)
        painter.restore()


class ReportsFloatDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        painter.save()
        model = index.model()
        record = model.record(index.row())
        amount = record.value(index.column())
        text = formatFloatLong(float(amount)) if amount != '' else ''
        painter.drawText(option.rect, Qt.AlignRight, text)
        painter.restore()


class ReportsFloat2Delegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        painter.save()
        model = index.model()
        record = model.record(index.row())
        amount = record.value(index.column())
        text = f"{amount:.2f}" if amount != '' else ''
        painter.drawText(option.rect, Qt.AlignRight, text)
        painter.restore()


class ReportsFloat4Delegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        painter.save()
        model = index.model()
        record = model.record(index.row())
        amount = record.value(index.column())
        text = f"{amount:.4f}" if amount != '' else ''
        painter.drawText(option.rect, Qt.AlignRight, text)
        painter.restore()


class ReportsProfitDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        painter.save()
        model = index.model()
        record = model.record(index.row())
        amount = record.value(index.column())
        text = "N/A"
        if amount:
            if amount >= 0:
                painter.fillRect(option.rect, CustomColor.LightGreen)
            else:
                painter.fillRect(option.rect, CustomColor.LightRed)
            text = f"{amount:,.2f}"
        painter.drawText(option.rect, Qt.AlignRight, text)
        painter.restore()


class ReportsCorpActionDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        CorpActionNames = {
            CorporateAction.SymbolChange: g_tr('OperationsDelegate', "Symbol change"),
            CorporateAction.Split: g_tr('OperationsDelegate', "Split"),
            CorporateAction.SpinOff: g_tr('OperationsDelegate', "Spin-off"),
            CorporateAction.Merger: g_tr('OperationsDelegate', "Merger"),
            CorporateAction.StockDividend: g_tr('OperationsDelegate', "Stock dividend")
        }

        painter.save()
        model = index.model()
        record = model.record(index.row())
        type = record.value(index.column())
        if type == '':
            type = 0
        if type > 0:
            text = g_tr('OperationsDelegate', " Opened with ") + CorpActionNames[type]
        elif type < 0:
            text = g_tr('OperationsDelegate', " Closed with ") + CorpActionNames[-type]
        else:
            qty = record.value("qty")
            if qty > 0:
                text = g_tr('OperationsDelegate', " Long")
            else:
                text = g_tr('OperationsDelegate', " Short")
        painter.drawText(option.rect, Qt.AlignLeft, text)
        painter.restore()


class ReportsTimestampDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def displayText(self, value, locale):
        if isinstance(value, str):  # already SQL-preprocessed date
            text = datetime.fromtimestamp(int(value)).strftime('%d/%m/%Y')
        else:
            text = datetime.fromtimestamp(value).strftime('%d/%m/%Y %H:%M:%S')
        return text


class ReportsYearMonthDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def displayText(self, value, locale):
        text = datetime.fromtimestamp(value).strftime('%Y %B')
        return text

class ReportsPandasDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        painter.save()
        pen = painter.pen()
        model = index.model()
        if index.column() == 0:
            text = model.data(index, Qt.DisplayRole)
            painter.drawText(option.rect, Qt.AlignLeft, text)
        else:
            amount = model.data(index, Qt.DisplayRole)
            if amount == 0:
                pen.setColor(CustomColor.Grey)
                painter.setPen(pen)
            text = f"{amount:,.2f}"
            painter.drawText(option.rect, Qt.AlignRight, text)
        painter.setPen(pen)
        painter.restore()

class SlipLinesPandasDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        painter.save()
        pen = painter.pen()
        model = index.model()
        if index.column() == 0:
            text = model.data(index, Qt.DisplayRole)
            painter.drawText(option.rect, Qt.AlignLeft | Qt.AlignVCenter, text)
        if index.column() == 1:
            text = get_category_name(index.model().database(), int(model.data(index, Qt.DisplayRole)))
            confidence = model.data(index.siblingAtColumn(2), Qt.DisplayRole)
            if confidence > 0.75:
                painter.fillRect(option.rect, CustomColor.LightGreen)
            elif confidence > 0.5:
                painter.fillRect(option.rect, CustomColor.LightYellow)
            else:
                painter.fillRect(option.rect, CustomColor.LightRed)
            painter.drawText(option.rect, Qt.AlignLeft | Qt.AlignVCenter, text)
        elif index.column() == 4:
            amount = model.data(index, Qt.DisplayRole)
            if amount == 2:
                pen.setColor(CustomColor.Grey)
                painter.setPen(pen)
            text = f"{amount:,.2f}"
            painter.drawText(option.rect, Qt.AlignRight | Qt.AlignVCenter, text)
        painter.setPen(pen)
        painter.restore()

    def createEditor(self, aParent, option, index):
        if index.column() == 1:
            category_selector = CategorySelector(aParent)
            category_selector.init_db(index.model().database())
            return category_selector
        if index.column() == 3:
            tag_selector = TagSelector(aParent)
            tag_selector.init_db(index.model().database())
            return tag_selector

    def setModelData(self, editor, model, index):
        if index.column() == 1:
            model.setData(index, editor.selected_id)
            model.setData(index.siblingAtColumn(2), 1) # set confidence level to 1
        if index.column() ==3:
            model.setData(index, editor.selected_id)