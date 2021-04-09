from datetime import datetime
from PySide2.QtCore import Qt, Slot, QAbstractTableModel, QDate
from PySide2.QtSql import QSqlQuery
from PySide2.QtGui import QBrush, QFont
from PySide2.QtWidgets import QStyledItemDelegate, QHeaderView
from jal.constants import CustomColor, TransactionType, TransferSubtype, DividendSubtype, CorporateAction
from jal.widgets.helpers import g_tr
from jal.db.helpers import db_connection, readSQL, executeSQL


class OperationsModel(QAbstractTableModel):
    PAGE_SIZE = 100
    COL_TYPE = 0
    COL_SUBTYPE = 1
    COL_ID = 2
    COL_TIMESTAMP = 3
    COL_ACCOUNT_ID = 4
    COL_ACCOUNT = 5
    COL_NUMBER_PEER = 6
    COL_ASSET_ID = 7
    COL_ASSET = 8
    COL_ASSET_NAME = 9
    COL_NOTE = 10
    COL_NOTE2 = 11
    COL_AMOUNT = 12
    COL_QTY = 13
    COL_PRICE = 14
    COL_FEE_TAX = 15
    COL_TOTAL_AMOUNT = 16
    COL_TOTAL_QTY = 17
    COL_CURRENCY = 18
    COL_RECONCILED = 19

    _columns = [" ",
                g_tr('OperationsModel', "Timestamp"),
                g_tr('OperationsModel', "Account"),
                g_tr('OperationsModel', "Notes"),
                g_tr('OperationsModel', "Amount"),
                g_tr('OperationsModel', "Balance"),
                g_tr('OperationsModel', "Currency")]
    _tables = {
        TransactionType.Action: "actions",
        TransactionType.Dividend: "dividends",
        TransactionType.Trade: "trades",
        TransactionType.Transfer: "transfers",
        TransactionType.CorporateAction: "corp_actions"
    }

    OperationSign = {
        (TransactionType.Action, -1): ('—', CustomColor.DarkRed),
        (TransactionType.Action, +1): ('+', CustomColor.DarkGreen),
        (TransactionType.Dividend, DividendSubtype.Dividend): ('Δ', CustomColor.DarkGreen),
        (TransactionType.Dividend, DividendSubtype.BondInterest): ('%', CustomColor.DarkGreen),
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
    CorpActionNames = {
        CorporateAction.SymbolChange: g_tr('OperationsModel', "Symbol change {old} -> {new}"),
        CorporateAction.Split: g_tr('OperationsModel', "Split {old} {before} into {after}"),
        CorporateAction.SpinOff: g_tr('OperationsModel', "Spin-off {after} {new} from {before} {old}"),
        CorporateAction.Merger: g_tr('OperationsModel', "Merger {before} {old} into {after} {new}"),
        CorporateAction.StockDividend: g_tr('OperationsModel', "Stock dividend: {after} {new}")
    }

    def __init__(self, parent_view):
        super().__init__(parent_view)
        self._view = parent_view
        self._amount_delegate = None
        self._data = []
        self._row_count = 0
        self._query = QSqlQuery(db_connection())
        self._begin = 0
        self._end = 0
        self._account = 0
        self._text_filter = ''

        self.prepareData()

    def rowCount(self, parent=None):
        return len(self._data)

    def columnCount(self, parent=None):
        return len(self._columns)

    def canFetchMore(self, index):
        return len(self._data) < self._row_count

    def fetchMore(self, index):
        new_size = len(self._data) + self.PAGE_SIZE
        new_size = new_size if new_size < self._row_count else self._row_count
        self.beginInsertRows(index, len(self._data), new_size - 1)
        i = 0
        indexes = range(self._query.record().count())
        while (i < self.PAGE_SIZE) and self._query.next():
            values = list(map(self._query.value, indexes))
            self._data.append(values)
            i += 1
        self.endInsertRows()

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._columns[section]
        return None

    def get_operation(self, row):
        if (row >= 0) and (row < len(self._data)):
            return self._data[row][self.COL_TYPE], self._data[row][self.COL_ID]
        else:
            return [0, 0]

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            return self.data_text(index.row(), index.column())
        if role == Qt.FontRole and index.column() == 0:
            font = QFont()
            font.setBold(True)
            return font
        if role == Qt.ForegroundRole:
            return self.data_foreground(index.row(), index.column())
        if role == Qt.TextAlignmentRole:
            if index.column() == 0:
                return Qt.AlignCenter
            if index.column() == 4 or index.column() == 5:
                return Qt.AlignRight
            return Qt.AlignLeft

    def data_text(self, row, column):
        if column == 0:
            try:
                return self.OperationSign[self._data[row][self.COL_TYPE], self._data[row][self.COL_SUBTYPE]][0]
            except KeyError:
                return '?'
        elif column == 1:
            if (self._data[row][self.COL_TYPE] == TransactionType.Trade) or (self._data[row][self.COL_TYPE] == TransactionType.Dividend) \
                    or (self._data[row][self.COL_TYPE] == TransactionType.CorporateAction):
                return f"{datetime.utcfromtimestamp(self._data[row][self.COL_TIMESTAMP]).strftime('%d/%m/%Y %H:%M:%S')}\n# {self._data[row][self.COL_NUMBER_PEER]}"
            else:
                return datetime.utcfromtimestamp(self._data[row][self.COL_TIMESTAMP]).strftime('%d/%m/%Y %H:%M:%S')
        elif column == 2:
            if self._data[row][self.COL_TYPE] == TransactionType.Action:
                return self._data[row][self.COL_ACCOUNT]
            elif (self._data[row][self.COL_TYPE] == TransactionType.Trade) \
                    or (self._data[row][self.COL_TYPE] == TransactionType.Dividend) \
                    or (self._data[row][self.COL_TYPE] == TransactionType.CorporateAction):
                return self._data[row][self.COL_ACCOUNT] + "\n" + self._data[row][self.COL_ASSET_NAME]
            elif self._data[row][self.COL_TYPE] == TransactionType.Transfer:
                if self._data[row][self.COL_SUBTYPE] == TransferSubtype.Fee:
                    return self._data[row][self.COL_ACCOUNT]
                elif self._data[row][self.COL_SUBTYPE] == TransferSubtype.Outgoing:
                    return self._data[row][self.COL_ACCOUNT] + " -> " + self._data[row][self.COL_NOTE2]
                elif self._data[row][self.COL_SUBTYPE] == TransferSubtype.Incoming:
                    return self._data[row][self.COL_ACCOUNT] + " <- " + self._data[row][self.COL_NOTE2]
        elif column == 3:
            if self._data[row][self.COL_TYPE] == TransactionType.Action:
                note = self._data[row][self.COL_NUMBER_PEER]
                if self._data[row][self.COL_ASSET] != '' and self._data[row][self.COL_FEE_TAX] != 0:
                    note += "\n" + g_tr('OperationsModel', "Rate: ")
                    if self._data[row][self.COL_FEE_TAX] >= 1:
                        note += f"{self._data[row][self.COL_FEE_TAX]:.4f} " \
                                f"{self._data[row][self.COL_ASSET]}/{self._data[row][self.COL_CURRENCY]}"
                    else:
                        note += f"{1/self._data[row][self.COL_FEE_TAX]:.4f} " \
                                f"{self._data[row][self.COL_CURRENCY]}/{self._data[row][self.COL_ASSET]}"
                return note
            elif self._data[row][self.COL_TYPE] == TransactionType.Transfer:
                rate = 0 if self._data[row][self.COL_PRICE] == '' else self._data[row][self.COL_PRICE]
                if self._data[row][self.COL_CURRENCY] != self._data[row][self.COL_NUMBER_PEER]:
                    if rate != 0:
                        if rate > 1:
                            return self._data[row][self.COL_NOTE] + f" [1 {self._data[row][self.COL_CURRENCY]} = {rate:.4f} {self._data[row][self.COL_NUMBER_PEER]}]"
                        elif rate < 1:
                            rate = 1 / rate
                            return self._data[row][self.COL_NOTE] +  f" [{rate:.4f} {self._data[row][self.COL_CURRENCY]} = 1 {self._data[row][self.COL_NUMBER_PEER]}]"
                        else:
                            return self._data[row][self.COL_NOTE]
                    else:
                        return g_tr('OperationsModel', "Error. Zero rate")
                else:
                    return self._data[row][self.COL_NOTE]
            elif self._data[row][self.COL_TYPE] == TransactionType.Dividend:
                return self._data[row][self.COL_NOTE] + "\n" + g_tr('OperationsModel', "Tax: ") + self._data[row][self.COL_NOTE2]
            elif self._data[row][self.COL_TYPE] == TransactionType.Trade:
                if self._data[row][self.COL_FEE_TAX] != 0:
                    text = f"{self._data[row][self.COL_QTY]:+.2f} @ {self._data[row][self.COL_PRICE]:.4f}\n({self._data[row][self.COL_FEE_TAX]:.2f}) "
                else:
                    text = f"{self._data[row][self.COL_QTY]:+.2f} @ {self._data[row][self.COL_PRICE]:.4f}\n"
                text = text + self._data[row][self.COL_NOTE] if self._data[row][self.COL_NOTE] else text
                return text
            elif self._data[row][self.COL_TYPE] == TransactionType.CorporateAction:
                basis = 100.0 * self._data[row][self.COL_PRICE]
                if self._data[row][self.COL_SUBTYPE] == CorporateAction.StockDividend:
                    qty_after = self._data[row][self.COL_QTY] - self._data[row][self.COL_AMOUNT]
                else:
                    qty_after = self._data[row][self.COL_QTY]
                text = self.CorpActionNames[self._data[row][self.COL_SUBTYPE]].format(old=self._data[row][self.COL_ASSET], new=self._data[row][self.COL_NOTE],
                                                                    before=self._data[row][self.COL_AMOUNT], after=qty_after)
                if self._data[row][self.COL_SUBTYPE] == CorporateAction.SpinOff:
                    text += f"; {basis:.2f}% " + g_tr('OperationsModel', " cost basis") + "\n" + self._data[row][self.COL_NOTE2]
                return text
            else:
                assert False
        elif column == 4:
            if self._data[row][self.COL_TYPE] == TransactionType.Trade:
                return [self._data[row][self.COL_AMOUNT], self._data[row][self.COL_QTY]]
            elif self._data[row][self.COL_TYPE] == TransactionType.Dividend:
                return [self._data[row][self.COL_AMOUNT], -self._data[row][self.COL_FEE_TAX]]
            elif self._data[row][self.COL_TYPE] == TransactionType.Action:
                if self._data[row][self.COL_ASSET] != '':
                    return [self._data[row][self.COL_AMOUNT], self._data[row][self.COL_PRICE]]
                else:
                    return [self._data[row][self.COL_AMOUNT]]
            elif self._data[row][self.COL_TYPE] == TransactionType.Transfer:
                return [self._data[row][self.COL_AMOUNT]]
            elif self._data[row][self.COL_TYPE] == TransactionType.CorporateAction:
                if self._data[row][self.COL_SUBTYPE] == CorporateAction.SpinOff or self._data[row][self.COL_SUBTYPE] == CorporateAction.StockDividend:
                    return [None, self._data[row][self.COL_QTY] - self._data[row][self.COL_AMOUNT]]
                else:
                    return [-self._data[row][self.COL_AMOUNT], self._data[row][self.COL_QTY]]
            else:
                assert False
        elif column == 5:
            upper_part = f"{self._data[row][self.COL_TOTAL_AMOUNT]:,.2f}" if self._data[row][self.COL_TOTAL_AMOUNT] != '' else "-.--"
            lower_part = f"{self._data[row][self.COL_TOTAL_QTY]:,.2f}" if self._data[row][self.COL_TOTAL_QTY] != '' else ''
            if self._data[row][self.COL_TYPE] == TransactionType.CorporateAction:
                qty_before = self._data[row][self.COL_AMOUNT] if self._data[row][self.COL_SUBTYPE] == CorporateAction.SpinOff else 0
                qty_after = self._data[row][self.COL_TOTAL_QTY] if self._data[row][self.COL_SUBTYPE] == CorporateAction.StockDividend else self._data[row][self.COL_QTY]
                if self._data[row][self.COL_SUBTYPE] == CorporateAction.StockDividend:
                    text = f"\n{qty_after:,.2f}" if qty_after != '' else "\n-.--"
                else:
                    text = f"{qty_before:,.2f}\n{qty_after:,.2f}"
                return text
            elif self._data[row][self.COL_TYPE] == TransactionType.Action or self._data[row][self.COL_TYPE] == TransactionType.Transfer:
                return upper_part
            else:
                return upper_part + "\n" + lower_part
        elif column == 6:
            if self._data[row][self.COL_TYPE] == TransactionType.CorporateAction:
                asset_before = self._data[row][self.COL_ASSET] if self._data[row][self.COL_SUBTYPE] != CorporateAction.StockDividend else ""
                return f" {asset_before}\n {self._data[row][self.COL_NOTE]}"
            else:
                if self._data[row][self.COL_ASSET] != '':
                    return f" {self._data[row][self.COL_CURRENCY]}\n {self._data[row][self.COL_ASSET]}"
                else:
                    return f" {self._data[row][self.COL_CURRENCY]}"
        else:
            assert False

    def data_foreground(self, row, column):
        if column == 0:
            try:
                return QBrush(self.OperationSign[self._data[row][self.COL_TYPE], self._data[row][self.COL_SUBTYPE]][1])
            except KeyError:
                return QBrush(CustomColor.LightRed)
        if column == 5:
            if self._data[row][self.COL_RECONCILED] == 1:
                return QBrush(CustomColor.Blue)

    def configureView(self):
        self._view.setColumnWidth(0, 10)
        self._view.setColumnWidth(1, self._view.fontMetrics().width("00/00/0000 00:00:00") * 1.1)
        self._view.setColumnWidth(2, 300)
        self._view.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        font = self._view.horizontalHeader().font()
        font.setBold(True)
        self._view.horizontalHeader().setFont(font)

        self._amount_delegate = ColoredAmountsDelegate(self._view)
        self._view.setItemDelegateForColumn(4, self._amount_delegate)

        self._view.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

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
        if filter:
            self._text_filter = f" AND (num_peer LIKE '%{filter}%' COLLATE NOCASE "\
                                f"OR note LIKE '%{filter}%' COLLATE NOCASE "\
                                f"OR note2 LIKE '%{filter}%' COLLATE NOCASE "\
                                f"OR asset LIKE '%{filter}%' COLLATE NOCASE "\
                                f"OR asset_name LIKE '%{filter}%' COLLATE NOCASE)"
        else:
            self._text_filter = ''
        self.prepareData()

    def update(self):
        self.prepareData()

    def get_operation_type(self, row):
        if (row >= 0) and (row < len(self._data)):
            return self._data[row][self.COL_TYPE]
        else:
            return 0

    def reconcile_operation(self, row):
        if (row >= 0) and (row < len(self._data)):
            timestamp = self._data[row][self.COL_TIMESTAMP]
            account_id = self._data[row][self.COL_ACCOUNT_ID]
            _ = executeSQL("UPDATE accounts SET reconciled_on=:timestamp WHERE id = :account_id",
                           [(":timestamp", timestamp), (":account_id", account_id)])
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
            count_pfx = "SELECT COUNT(*) "
            query_pfx = "SELECT * "
            query_suffix = f"FROM all_operations AS o WHERE o.timestamp>={self._begin} AND o.timestamp<={self._end}" + \
                           self._text_filter
            if self._account:
                query_suffix = query_suffix + f" AND o.account_id = {self._account}"
            self._row_count = readSQL(count_pfx + query_suffix)
            self._query.prepare(query_pfx + query_suffix)
            self._query.setForwardOnly(True)
            self._query.exec_()
        self.fetchMore(self.createIndex(0, 0))
        self.modelReset.emit()

    def deleteRows(self, rows):
        for row in rows:
            if (row >= 0) and (row < len(self._data)):
                table_name = self._tables[self._data[row][self.COL_TYPE]]
                query = f"DELETE FROM {table_name} WHERE id={self._data[row][self.COL_ID]}"
                _ = executeSQL(query)
        self.prepareData()


class ColoredAmountsDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
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
        if value >= 0:
            pen.setColor(CustomColor.DarkGreen)
        else:
            pen.setColor(CustomColor.DarkRed)
        painter.setPen(pen)
        painter.drawText(rect, Qt.AlignRight | Qt.AlignVCenter, f"{value:+,.2f}")