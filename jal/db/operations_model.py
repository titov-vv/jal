from PySide6.QtCore import Qt, Slot, QDate, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QHeaderView
from jal.constants import CustomColor
from jal.db.ledger import Ledger
from jal.db.helpers import localize_decimal
from jal.db.operations import LedgerTransaction
from jal.widgets.helpers import ts2dt
from jal.widgets.delegates import ColoredAmountsDelegate, long_fraction
from jal.universal_cache import UniversalCache

#-----------------------------------------------------------------------------------------------------------------------

class OperationsModel(QAbstractTableModel):
    def __init__(self, parent_view):
        super().__init__(parent_view)
        self._columns = [self.tr("Timestamp"), self.tr("Account"), self.tr("Notes"),
                         self.tr("Amount"), self.tr("Balance"), self.tr("Currency")]
        self._view = parent_view
        self._amount_delegate = None
        self._total_delegate = None
        self._data = []
        self._cache = UniversalCache()
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
            return self._data[row]['otype'], self._data[row]['oid']
        else:
            return [0, 0]

    def data(self, index, role=Qt.DisplayRole, field=''):
        row = index.row()
        odata = self._data[row]
        if not index.isValid():
            return None
        operation = self._cache.get_data(self._fetch_single_row_safe_for_deleted, (row,)) # Tuple is required for key
        if role == Qt.DisplayRole:
            return self._cache.get_data(self._fetch_column_text, (row, index.column())) # operation is too heavy to be an argument for caching -> use row id
        if role == Qt.DecorationRole and index.column() == 0:
            return operation.icon()
        if role == Qt.FontRole:
            # below line isn't related with font, it is put here to be called for each row minimal times (ideally 1)
            if index.column() == 0:
                self._view.setRowHeight(row, self._view.fontMetrics().height() * operation.view_rows())
            return self._view.font()
        if role == Qt.ForegroundRole and self._view.isEnabled():
            if index.column() == 4 and operation.reconciled():
                return CustomColor.Blue
        if role == Qt.ToolTipRole:
            if index.column() == 0:
                return operation.name()
            elif index.column() == 3 or index.column() == 4:
                data = self.data_text(operation, index.column())
                if any([long_fraction(x) for x in data]):
                    return '\n'.join([localize_decimal(x) for x in data])
        if role == Qt.TextAlignmentRole:
            if index.column() == 3 or index.column() == 4:
                return int(Qt.AlignRight)
            return int(Qt.AlignLeft)
        if role == Qt.UserRole:  # return underlying data for given field extra parameter
            return odata[field]

    def _fetch_column_text(self, row_id: int, column_id: int):
        operation = self._cache.get_data(self._fetch_single_row_safe_for_deleted, (row_id,)) # Tuple is required
        return self.data_text(operation, column_id)

    def data_text(self, operation: LedgerTransaction, column):
        if column == 0:
            date_time = ts2dt(operation.timestamp())
            if operation.number() and operation.type() != LedgerTransaction.Transfer:  # Transfer is 1-liner
                date_time += f"\n# {operation.number()}"
            return date_time
        elif column == 1:
            if operation.asset_name() and operation.type() != LedgerTransaction.Transfer:
                return operation.account_name() + "\n" + operation.asset_name()
            else:
                return operation.account_name()
        elif column == 2:
            return operation.description()
        elif column == 3:
            return operation.value_change()
        elif column == 4:
            return operation.value_total()
        elif column == 5:
            return operation.value_currency()
        else:
            assert False, "Unexpected column number"

    def configureView(self):
        self._view.setColumnWidth(0, self._view.fontMetrics().horizontalAdvance("00/00/0000 00:00:00") * 1.2)
        self._view.setColumnWidth(1, 300)
        self._view.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._view.horizontalHeader().setFont(self._bold_font)
        self._amount_delegate = ColoredAmountsDelegate(self._view)
        self._total_delegate = ColoredAmountsDelegate(self._view, colors=False, signs=False)
        self._view.setItemDelegateForColumn(3, self._amount_delegate)     # Amount
        self._view.setItemDelegateForColumn(4, self._total_delegate)      # Balance
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
        self.beginResetModel()
        self._data = []
        self._data = Ledger.get_operations_sequence(self._begin, self._end, self._account)
        self._cache.clear_cache()
        self.endResetModel()

    def delete_rows(self, rows):
        for row in rows:
            if (row >= 0) and (row < len(self._data)):
                try:
                    LedgerTransaction.get_operation(self._data[row]['otype'], self._data[row]['oid'], self._data[row]['opart']).delete()
                except IndexError as e:   # If row is already deleted (for example by another reference from 'opart')
                    if str(e) == LedgerTransaction.NoOpException:
                        pass
        self.prepareData()

    def assign_tag_to_rows(self, rows, tag_id):
        for row in rows:
            if (row >= 0) and (row < len(self._data)):
                LedgerTransaction.get_operation(self._data[row]['otype'], self._data[row]['oid'],self._data[row]['opart']).assign_tag(tag_id)
        self.prepareData()

    def _fetch_single_row_safe_for_deleted(self, row):
        odata = self._data[row]
        try:
            return LedgerTransaction.get_operation(odata['otype'], odata['oid'], odata['opart'])
        except IndexError as e:   # If row is already deleted (for example by another reference to the same 'oid' from different 'opart')
            if str(e) == LedgerTransaction.NoOpException:
                return None
            raise e
