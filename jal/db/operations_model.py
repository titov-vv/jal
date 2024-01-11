from decimal import Decimal
from PySide6.QtCore import Qt, Slot, QDate, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QStyledItemDelegate, QHeaderView
from jal.constants import CustomColor, Setup
from jal.db.ledger import Ledger
from jal.db.helpers import localize_decimal
from jal.db.operations import LedgerTransaction
from jal.widgets.helpers import ts2dt


#-----------------------------------------------------------------------------------------------------------------------
# Function returns True if given number has move decimal places than Setup.DEFAULT_ACCOUNT_PRECISION
def long_fraction(x: Decimal) -> bool:
    if x is None:
        return False
    if x.is_nan():
        return False
    return abs(x - round(x, Setup.DEFAULT_ACCOUNT_PRECISION)) > Decimal('0')
#-----------------------------------------------------------------------------------------------------------------------

class OperationsModel(QAbstractTableModel):
    def __init__(self, parent_view):
        super().__init__(parent_view)
        self._columns = [" ", self.tr("Timestamp"), self.tr("Account"), self.tr("Notes"),
                         self.tr("Amount"), self.tr("Balance"), self.tr("Currency")]
        self._view = parent_view
        self._amount_delegate = None
        self._total_delegate = None
        self._data = []
        self._begin = 0
        self._end = 0
        self._account = 0
        self._bold_font = QFontDatabase.systemFont(QFontDatabase.GeneralFont)
        self._bold_font.setBold(True)

        self.prepareData()

    def rowCount(self, parent=None):
        return len(self._data)

    def columnCount(self, parent=None):
        return len(self._columns)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._columns[section]
        return None

    def get_operation(self, row):
        if (row >= 0) and (row < self.rowCount()):
            return self._data[row]['op_type'], self._data[row]['id']
        else:
            return [0, 0]

    def data(self, index, role=Qt.DisplayRole, field=''):
        row = index.row()
        if not index.isValid():
            return None
        operation = LedgerTransaction().get_operation(self._data[row]['op_type'],
                                                      self._data[row]['id'],
                                                      self._data[row]['subtype'])
        if role == Qt.DisplayRole:
            return self.data_text(operation, index.column())
        if role == Qt.FontRole and index.column() == 0:
            # below line isn't related with font, it is put here to be called for each row minimal times (ideally 1)
            self._view.setRowHeight(row, self._view.verticalHeader().fontMetrics().height() * operation.view_rows())
            return self._bold_font
        if role == Qt.ForegroundRole and self._view.isEnabled():
            if index.column() == 0:
                return operation.label_color()
            if index.column() == 5 and operation.reconciled():
                return CustomColor.Blue
        if role == Qt.ToolTipRole:
            if index.column() == 0:
                return operation.name()
            elif index.column() == 4 or index.column() == 5:
                data = self.data_text(operation, index.column())
                if any([long_fraction(x) for x in data]):
                    return '\n'.join([localize_decimal(x) for x in data])
        if role == Qt.TextAlignmentRole:
            if index.column() == 0:
                return int(Qt.AlignCenter | Qt.AlignVCenter)
            if index.column() == 4 or index.column() == 5:
                return int(Qt.AlignRight)
            return int(Qt.AlignLeft)
        if role == Qt.UserRole:  # return underlying data for given field extra parameter
            return self._data[index.row()][field]

    def data_text(self, operation, column):
        if column == 0:
            return operation.label()
        elif column == 1:
            date_time = ts2dt(operation.timestamp())
            if operation.number()  and operation.type() != LedgerTransaction.Transfer:  # Transfer is 1-liner
                date_time += f"\n# {operation.number()}"
            return date_time
        elif column == 2:
            if operation.asset_name() and operation.type() != LedgerTransaction.Transfer:
                return operation.account_name() + "\n" + operation.asset_name()
            else:
                return operation.account_name()
        elif column == 3:
            return operation.description()
        elif column == 4:
            return operation.value_change()
        elif column == 5:
            return operation.value_total()
        elif column == 6:
            return operation.value_currency()
        else:
            assert False, "Unexpected column number"

    def configureView(self):
        self._view.setColumnWidth(0, 10)
        self._view.setColumnWidth(1, self._view.fontMetrics().horizontalAdvance("00/00/0000 00:00:00") * 1.1)
        self._view.setColumnWidth(2, 300)
        self._view.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self._view.horizontalHeader().setFont(self._bold_font)
        self._amount_delegate = ColoredAmountsDelegate(self._view)
        self._total_delegate = ColoredAmountsDelegate(self._view, colors=False, signs=False)
        self._view.setItemDelegateForColumn(4, self._amount_delegate)
        self._view.setItemDelegateForColumn(5, self._total_delegate)

        self._view.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)  # row size is adjusted in data() method

    @Slot()
    def setAccount(self, account_id):
        if self._account != account_id:
            self._account = account_id
            self.prepareData()

    def getAccount(self):
        return self._account

    @Slot()
    def setDateRange(self, start, end=0):
        self._begin = start
        if end:
            self._end = end
        else:
            self._end = QDate.currentDate().endOfDay(Qt.UTC).toSecsSinceEpoch()
        self.prepareData()

    def update(self):
        self.prepareData()

    @Slot()
    def refresh(self):
        idx = self._view.selectionModel().selection().indexes()
        idx = idx[0] if idx else QModelIndex()  # Take first selected or empty index
        if self._view.model() != self:          # View uses some proxy model
            idx = self._view.model().mapToSource(idx)
        self.prepareData()
        if self._view.model() != self:
            idx = self._view.model().mapFromSource(idx)
        self._view.setCurrentIndex(idx)

    def prepareData(self):
        self._data = []
        self._data = Ledger.get_operations_sequence(self._begin, self._end, self._account)
        self.modelReset.emit()

    def delete_rows(self, rows):
        for row in rows:
            if (row >= 0) and (row < len(self._data)):
                LedgerTransaction.get_operation(self._data[row]['op_type'], self._data[row]['id'],
                                                display_type=self._data[row]['subtype']).delete()
        self.prepareData()

    def assign_tag_to_rows(self, rows, tag_id):
        for row in rows:
            if (row >= 0) and (row < len(self._data)):
                LedgerTransaction.get_operation(self._data[row]['op_type'], self._data[row]['id'],
                                                display_type=self._data[row]['subtype']).assign_tag(tag_id)
        self.prepareData()


# ----------------------------------------------------------------------------------------------------------------------
# Display several numbers that provided by the model in form of a list
# Each number is displayed on its own line
# colors - display positive/negative values with green/red color
# signs - display +/- sign before the number if True or only "-" if False
class ColoredAmountsDelegate(QStyledItemDelegate):
    def __init__(self, parent=None, colors=True, signs=True):
        self._view = parent
        self._colors = colors
        self._signs = signs
        super().__init__(parent=parent)

    def paint(self, painter, option, index):
        painter.save()
        data = index.model().data(index)
        color = index.model().data(index, role = Qt.ForegroundRole)
        rect = option.rect
        H = rect.height()
        Y = rect.top()
        rect.setHeight(H / len(data))
        for i, item in enumerate(data):
            rect.moveTop(Y + i * (H / len(data)))
            self.draw_value(option.rect, painter, item, color)
        painter.restore()


    # Displays given value as formatted number with required color (or Green/Red if self._colors is True)
    # If value is None - displays nothing, If value is NaN - displays Setup.NULL_VALUE
    def draw_value(self, rect, painter, value, color=None):
        text = localize_decimal(value, precision=2, sign=self._signs)
        pen = painter.pen()
        try:
            if self._view.isEnabled():
                if self._colors:
                    if value >= 0:
                        pen.setColor(CustomColor.DarkGreen)
                    else:
                        pen.setColor(CustomColor.DarkRed)
                else:
                    if color is not None:
                        pen.setColor(color)
            painter.setPen(pen)
            painter.drawText(rect, Qt.AlignRight | Qt.AlignVCenter, text)
            if long_fraction(value):  # Underline decimal part
                shift = painter.fontMetrics().horizontalAdvance(text[-Setup.DEFAULT_ACCOUNT_PRECISION:])
                painter.drawLine(rect.right() - shift, rect.bottom(), rect.right(), rect.bottom())
        except TypeError:
            pass
