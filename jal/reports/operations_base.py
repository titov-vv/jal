# Base classes for Category, Tag and Peer reports
from decimal import Decimal
from PySide6.QtCore import Qt, QAbstractTableModel
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QHeaderView
from jal.db.asset import JalAsset
from jal.db.peer import JalPeer
from jal.db.helpers import localize_decimal
from jal.db.operations import LedgerTransaction
from jal.widgets.helpers import ts2dt
from jal.widgets.delegates import ColoredAmountsDelegate


# FIXME - check if it can have a common base class with OperationsModel
class ReportOperationsModel(QAbstractTableModel):
    def __init__(self, parent_view):
        super().__init__(parent_view)
        self._columns = [self.tr("Timestamp"), self.tr("Account"), self.tr("Peer"),
                         self.tr("Notes"), self.tr("Amount"), self.tr("Currency")]
        self._view = parent_view
        self._amount_delegate = None
        self._data = []
        self._begin = 0
        self._end = 0
        self._total = Decimal('0')
        self._total_currency = 0
        self._total_currency_name = ''
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
            return self._data[row]['otype'], self._data[row]['oid']
        else:
            return [0, 0]

    def data(self, index, role=Qt.DisplayRole, field=''):
        row = index.row()
        odata = self._data[row]
        if not index.isValid():
            return None
        try:
            operation = LedgerTransaction().get_operation(odata['otype'], odata['oid'], odata['opart'])
        except IndexError as e:
            if str(e) == LedgerTransaction.NoOpException:
                return None
            raise e
        if role == Qt.DisplayRole:
            return self.data_text(operation, index.column())
        if role == Qt.DecorationRole and index.column() == 0:
            return operation.icon()
        # if role == Qt.FontRole and index.column() == 0:
        #     # below line isn't related with font, it is put here to be called for each row minimal times (ideally 1)
        #     self._view.setRowHeight(row, self._view.verticalHeader().fontMetrics().height() * operation.view_rows())
        #     return self._view.font()
        if role == Qt.TextAlignmentRole:
            if index.column() == 4:
                return int(Qt.AlignRight)
            return int(Qt.AlignLeft)

    def data_text(self, operation, column):
        if column == 0:
            return ts2dt(operation.timestamp())
        elif column == 1:
            return operation.account_name()
        elif column == 2:
            return JalPeer(operation.peer()).name()
        elif column == 3:
            return operation.description()
        elif column == 4:
            return operation.value_change(part_only=True)
        elif column == 5:
            return operation.value_currency()
        else:
            assert False, "Unexpected column number"

    # Is used by view to display footer Title, Total amount and Total currency with right font and alignment in columns 3-5
    def footerData(self, section: int, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if section == 4:
                return localize_decimal(self._total, precision=2)
            elif section == 5:
                return self._total_currency_name
        elif role == Qt.FontRole:
            return self._bold_font
        elif role == Qt.TextAlignmentRole:
            if section == 4:
                return Qt.AlignRight | Qt.AlignVCenter
            return Qt.AlignLeft | Qt.AlignVCenter
        return None

    def configureView(self):
        self._view.setColumnWidth(0, self._view.fontMetrics().horizontalAdvance("00/00/0000 00:00:00") * 1.2)
        self._view.setColumnWidth(1, 200)
        self._view.setColumnWidth(1, 200)
        self._view.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self._view.horizontalHeader().setFont(self._bold_font)
        self._amount_delegate = ColoredAmountsDelegate(self._view)
        self._view.setItemDelegateForColumn(4, self._amount_delegate)
        self._view.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)  # row size is adjusted in data() method

    # Triggers view update if display parameters were changed
    def updateView(self, update: bool, dates_range: tuple, total_currency_id: int):
        if self._begin != dates_range[0]:
            self._begin = dates_range[0]
            update = True
        if self._end != dates_range[1]:
            self._end = dates_range[1]
            update = True
        if self._total_currency != total_currency_id:
            self._total_currency = total_currency_id
            self._total_currency_name = JalAsset(total_currency_id).symbol()
            update = True
        if update:
            self.prepareData()
            self.configureView()

    def prepareData(self):
        raise NotImplementedError(f"Method prepareData is not defined in {type(self).__name__} class")
