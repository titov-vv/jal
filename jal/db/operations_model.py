from datetime import datetime
from PySide6.QtCore import Qt, Slot, QAbstractTableModel, QDate
from PySide6.QtGui import QBrush, QFont
from PySide6.QtWidgets import QStyledItemDelegate, QHeaderView
from jal.constants import CustomColor
from jal.db.helpers import executeSQL, readSQLrecord
from jal.db.operations import LedgerTransaction


class OperationsModel(QAbstractTableModel):
    _tables = {
        LedgerTransaction.IncomeSpending: "actions",
        LedgerTransaction.Dividend: "dividends",
        LedgerTransaction.Trade: "trades",
        LedgerTransaction.Transfer: "transfers",
        LedgerTransaction.CorporateAction: "corp_actions"
    }

    def __init__(self, parent_view):
        super().__init__(parent_view)
        self._columns = [" ", self.tr("Timestamp"), self.tr("Account"), self.tr("Notes"),
                         self.tr("Amount"), self.tr("Balance"), self.tr("Currency")]
        self._view = parent_view
        self._amount_delegate = None
        self._data = []
        self._row_count = 0
        self._begin = 0
        self._end = 0
        self._account = 0
        self._text_filter = ''

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
        operation = LedgerTransaction().get_operation(self._data[index.row()]['op_type'],
                                                      self._data[index.row()]['id'],
                                                      self._data[index.row()]['subtype'])
        if role == Qt.DisplayRole:
            return self.data_text(operation, index.column())
        if role == Qt.FontRole and index.column() == 0:
            # below line isn't related with font, it is put here to be called for each row minimal times (ideally 1)
            self._view.setRowHeight(row, self._view.verticalHeader().defaultSectionSize() * operation.view_rows())
            font = QFont()
            font.setBold(True)
            return font
        if role == Qt.ForegroundRole and self._view.isEnabled():
            if index.column() == 0:
                return QBrush(operation.label_color())
            elif index.column() == 5:
                if operation.reconciled():
                    return QBrush(CustomColor.Blue)
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
            date_time = datetime.utcfromtimestamp(operation.timestamp()).strftime('%d/%m/%Y %H:%M:%S')
            if operation.number():
                date_time += f"\n# {operation.number()}"
            return date_time
        elif column == 2:
            if operation.asset():
                return operation.account() + "\n" + operation.asset()
            else:
                return operation.account()
        elif column == 3:
            return operation.description()
        elif column == 4:
            return operation.value_change()
        elif column == 5:
            return operation.value_total()
        elif column == 6:
            return operation.value_currency()
        else:
            return True, "Unexpected column number"

    def configureView(self):
        self._view.setColumnWidth(0, 10)
        self._view.setColumnWidth(1, self._view.fontMetrics().horizontalAdvance("00/00/0000 00:00:00") * 1.1)
        self._view.setColumnWidth(2, 300)
        self._view.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        font = self._view.horizontalHeader().font()
        font.setBold(True)
        self._view.horizontalHeader().setFont(font)

        self._amount_delegate = ColoredAmountsDelegate(self._view)
        self._view.setItemDelegateForColumn(4, self._amount_delegate)

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

    @Slot()
    def filterText(self, filter):
        if filter:    # FIXME Filter is not used with current query
            self._text_filter = '' # f" AND (num_peer LIKE '%{filter}%' COLLATE NOCASE "
        else:
            self._text_filter = ''
        self.prepareData()

    def update(self):
        self.prepareData()

    @Slot()
    def refresh(self):
        idx = self._view.selectionModel().selection().indexes()
        self.prepareData()
        if idx:
            self._view.setCurrentIndex(idx[0])

    def prepareData(self):
        self._data = []
        if self._begin == 0 and self._end == 0:
            self._row_count = 0
        else:
            query_text = f"SELECT * FROM operation_sequence WHERE timestamp>={self._begin} AND timestamp<={self._end}"
            if self._account:
                query_text += f" AND account_id={self._account}"
            query = executeSQL(query_text, forward_only=True)
            while query.next():
                self._data.append(readSQLrecord(query, named=True))
        self.modelReset.emit()

    def deleteRows(self, rows):
        for row in rows:
            if (row >= 0) and (row < len(self._data)):
                table_name = self._tables[self._data[row]['op_type']]
                query = f"DELETE FROM {table_name} WHERE id={self._data[row]['id']}"
                _ = executeSQL(query)
        self.prepareData()


# ----------------------------------------------------------------------------------------------------------------------
class ColoredAmountsDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        self._view = parent
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        painter.save()
        data = index.model().data(index)
        if len(data) == 1:
            self.draw_value(option.rect, painter, data[0])
        elif len(data) == 2:
            rect = option.rect
            H = rect.height()
            Y = rect.top()
            rect.setHeight(H / 2)
            self.draw_value(option.rect, painter, data[0])
            rect.moveTop(Y + H / 2)
            self.draw_value(option.rect, painter, data[1])
        else:
            assert False
        painter.restore()

    def draw_value(self, rect, painter, value):
        if value is None:
            return
        pen = painter.pen()
        try:
            if self._view.isEnabled():
                if value >= 0:
                    pen.setColor(CustomColor.DarkGreen)
                else:
                    pen.setColor(CustomColor.DarkRed)
            painter.setPen(pen)
            painter.drawText(rect, Qt.AlignRight | Qt.AlignVCenter, f"{value:+,.2f}")
        except TypeError:
            pass
