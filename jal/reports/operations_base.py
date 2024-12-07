# Base classes for Category, Tag and Peer reports
from decimal import Decimal
from PySide6.QtCore import Qt, QAbstractTableModel
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QHeaderView
from jal.db.asset import JalAsset
from jal.db.account import JalAccount
from jal.db.category import JalCategory
from jal.db.tag import JalTag
from jal.db.peer import JalPeer
from jal.db.helpers import localize_decimal
from jal.db.operations import LedgerTransaction
from jal.widgets.helpers import ts2dt
from jal.widgets.delegates import ColoredAmountsDelegate


class ReportOperationsModel(QAbstractTableModel):
    # hidden_column indicates which column to hide from display in the view
    def __init__(self, parent_view, hidden_column=None):
        super().__init__(parent_view)
        self._columns = [self.tr("Timestamp"), self.tr("Account"), self.tr("Peer"), self.tr("Category"), self.tr("Tag"),
                         self.tr("Notes"), self.tr("Amount"), self.tr("Currency")]
        self._view = parent_view
        self._hidden = hidden_column
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
            return self.data_text(operation, index.column(), odata)
        if role == Qt.DecorationRole and index.column() == 0:
            return operation.icon()

    def data_text(self, operation, column, odata):
        if column == 0:
            return ts2dt(operation.timestamp())
        elif column == 1:
            return operation.account_name()
        elif column == 2:
            return JalPeer(operation.peer()).name()
        elif column == 3:
            return JalCategory(odata['category_id']).name()
        elif column == 4:
            return JalTag(odata['tag_id']).name()
        elif column == 5:
            return operation.description(part_only=True)
        elif column == 6:
            return operation.value_change(part_only=True)
        elif column == 7:
            return operation.value_currency()
        else:
            assert False, "Unexpected column number"

    # Is used by view to display footer Title, Total amount and Total currency with right font and alignment in columns 3-5
    def footerData(self, section: int, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if section == 6:
                return localize_decimal(self._total, precision=2)
            elif section == 7:
                return self._total_currency_name
        elif role == Qt.FontRole:
            return self._bold_font
        elif role == Qt.TextAlignmentRole:
            if section == 6:
                return Qt.AlignRight | Qt.AlignVCenter
            return Qt.AlignLeft | Qt.AlignVCenter
        return None

    def configureView(self):
        self._view.setColumnWidth(0, self._view.fontMetrics().horizontalAdvance("00/00/0000 00:00:00") * 1.2)
        self._view.setColumnWidth(1, 150)
        self._view.setColumnWidth(2, 150)
        self._view.setColumnWidth(3, 150)
        self._view.setColumnWidth(4, 150)
        self._view.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self._view.horizontalHeader().setFont(self._bold_font)
        self._amount_delegate = ColoredAmountsDelegate(self._view)
        self._view.setItemDelegateForColumn(6, self._amount_delegate)
        self._view.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)  # row size is adjusted in data() method
        if self._hidden is not None:
            self._view.setColumnHidden(self._hidden, True)

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

    # self._data array should be populated by child classes.
    # Then they call this method to calculate total value.
    def prepareData(self):
        self.beginResetModel()
        self._total = Decimal('0')
        for line in self._data:
            account_currency = JalAccount(line['account_id']).currency()
            amount = -Decimal(line['amount'])
            if account_currency == self._total_currency:
                self._total += amount
            else:
                self._total += amount * JalAsset(account_currency).quote(line['timestamp'], self._total_currency)[1]
        self.endResetModel()
