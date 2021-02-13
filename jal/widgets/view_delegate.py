from datetime import datetime

from PySide2.QtWidgets import QStyledItemDelegate
from PySide2.QtCore import Qt

from jal.constants import CustomColor, CorporateAction
from jal.ui_custom.helpers import g_tr, formatFloatLong


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
            text = datetime.utcfromtimestamp(int(value)).strftime('%d/%m/%Y')
        else:
            text = datetime.utcfromtimestamp(value).strftime('%d/%m/%Y %H:%M:%S')
        return text


class ReportsYearMonthDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def displayText(self, value, locale):
        text = datetime.utcfromtimestamp(value).strftime('%Y %B')
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
