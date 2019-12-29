from PySide2.QtWidgets import QStyledItemDelegate
from PySide2.QtCore import Qt

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
            text = f"{value:,.2f}"
            alignment = Qt.AlignRight
        else:
            text = value
            alignment = Qt.AlignLeft

        if balance == 0:
            font = painter.font()
            font.setBold(True)
            painter.setFont(font)
            if (column == 3) or (column ==4):
                text = ""

        painter.drawText(option.rect, alignment, text)
        painter.restore()
