from datetime import datetime
from PySide6.QtCore import Qt, Slot, QAbstractTableModel, QDate
from PySide6.QtSql import QSqlQuery
from PySide6.QtGui import QBrush, QFont
from PySide6.QtWidgets import QStyledItemDelegate, QHeaderView
from jal.constants import CustomColor, TransactionType, TransferSubtype, DividendSubtype, CorporateAction
from jal.db.helpers import db_connection, readSQL, executeSQL, readSQLrecord


class OperationsModel(QAbstractTableModel):
    PAGE_SIZE = 100
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

    def __init__(self, parent_view):
        super().__init__(parent_view)
        self._columns = [" ", self.tr("Timestamp"), self.tr("Account"), self.tr("Notes"),
                         self.tr("Amount"), self.tr("Balance"), self.tr("Currency")]
        self.CorpActionNames = {
            CorporateAction.SymbolChange: self.tr("Symbol change {old} -> {new}"),
            CorporateAction.Split: self.tr("Split {old} {before} into {after}"),
            CorporateAction.SpinOff: self.tr("Spin-off {after} {new} from {before} {old}"),
            CorporateAction.Merger: self.tr("Merger {before} {old} into {after} {new}"),
            CorporateAction.StockDividend: self.tr("Stock dividend: {after} {new}")
        }
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
        while (i < self.PAGE_SIZE) and self._query.next():
            values = readSQLrecord(self._query, named=True)
            self._data.append(values)
            i += 1
        self.endInsertRows()

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._columns[section]
        return None

    def get_operation(self, row):
        if (row >= 0) and (row < len(self._data)):
            return self._data[row]['type'], self._data[row]['id']
        else:
            return [0, 0]

    def data(self, index, role=Qt.DisplayRole, field=''):
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            return self.data_text(index.row(), index.column())
        if role == Qt.FontRole and index.column() == 0:
            font = QFont()
            font.setBold(True)
            return font
        if role == Qt.ForegroundRole and self._view.isEnabled():
            return self.data_foreground(index.row(), index.column())
        if role == Qt.TextAlignmentRole:
            if index.column() == 0:
                return Qt.AlignCenter
            if index.column() == 4 or index.column() == 5:
                return Qt.AlignRight
            return Qt.AlignLeft
        if role == Qt.UserRole:  # return underlying data for given field extra parameter
            return self._data[index.row()][field]

    def data_text(self, row, column):
        if column == 0:
            try:
                return self.OperationSign[self._data[row]['type'], self._data[row]['subtype']][0]
            except KeyError:
                return '?'
        elif column == 1:
            if (self._data[row]['type'] == TransactionType.Trade) or (self._data[row]['type'] == TransactionType.Dividend) \
                    or (self._data[row]['type'] == TransactionType.CorporateAction):
                return f"{datetime.utcfromtimestamp(self._data[row]['timestamp']).strftime('%d/%m/%Y %H:%M:%S')}\n# {self._data[row]['num_peer']}"
            else:
                return datetime.utcfromtimestamp(self._data[row]['timestamp']).strftime('%d/%m/%Y %H:%M:%S')
        elif column == 2:
            if self._data[row]['type'] == TransactionType.Action:
                return self._data[row]['account']
            elif (self._data[row]['type'] == TransactionType.Trade) \
                    or (self._data[row]['type'] == TransactionType.Dividend) \
                    or (self._data[row]['type'] == TransactionType.CorporateAction):
                return self._data[row]['account'] + "\n" + self._data[row]['asset_name']
            elif self._data[row]['type'] == TransactionType.Transfer:
                if self._data[row]['subtype'] == TransferSubtype.Fee:
                    return self._data[row]['account']
                elif self._data[row]['subtype'] == TransferSubtype.Outgoing:
                    return self._data[row]['account'] + " -> " + self._data[row]['note2']
                elif self._data[row]['subtype'] == TransferSubtype.Incoming:
                    return self._data[row]['account'] + " <- " + self._data[row]['note2']
        elif column == 3:
            if self._data[row]['type'] == TransactionType.Action:
                note = self._data[row]['num_peer']
                if self._data[row]['asset'] != '' and self._data[row]['fee_tax'] != 0:
                    note += "\n" + self.tr("Rate: ")
                    if self._data[row]['fee_tax'] >= 1:
                        note += f"{self._data[row]['fee_tax']:.4f} " \
                                f"{self._data[row]['asset']}/{self._data[row]['currency']}"
                    else:
                        note += f"{1/self._data[row]['fee_tax']:.4f} " \
                                f"{self._data[row]['currency']}/{self._data[row]['asset']}"
                return note
            elif self._data[row]['type'] == TransactionType.Transfer:
                rate = 0 if self._data[row]['price'] == '' else self._data[row]['price']
                if self._data[row]['currency'] != self._data[row]['num_peer']:
                    if rate != 0:
                        if rate > 1:
                            return self._data[row]['note'] + f" [1 {self._data[row]['currency']} = {rate:.4f} {self._data[row]['num_peer']}]"
                        elif rate < 1:
                            rate = 1 / rate
                            return self._data[row]['note'] +  f" [{rate:.4f} {self._data[row]['currency']} = 1 {self._data[row]['num_peer']}]"
                        else:
                            return self._data[row]['note']
                    else:
                        return self.tr("Error. Zero rate")
                else:
                    return self._data[row]['note']
            elif self._data[row]['type'] == TransactionType.Dividend:
                return self._data[row]['note'] + "\n" + self.tr("Tax: ") + self._data[row]['note2']
            elif self._data[row]['type'] == TransactionType.Trade:
                if self._data[row]['fee_tax'] != 0:
                    text = f"{self._data[row]['qty_trid']:+.2f} @ {self._data[row]['price']:.4f}\n({self._data[row]['fee_tax']:.2f}) "
                else:
                    text = f"{self._data[row]['qty_trid']:+.2f} @ {self._data[row]['price']:.4f}\n"
                text = text + self._data[row]['note'] if self._data[row]['note'] else text
                return text
            elif self._data[row]['type'] == TransactionType.CorporateAction:
                basis = 100.0 * self._data[row]['price']
                if self._data[row]['subtype'] == CorporateAction.StockDividend:
                    qty_after = self._data[row]['qty_trid'] - self._data[row]['amount']
                else:
                    qty_after = self._data[row]['qty_trid']
                text = self.CorpActionNames[self._data[row]['subtype']].format(old=self._data[row]['asset'], new=self._data[row]['note'],
                                                                    before=self._data[row]['amount'], after=qty_after)
                if self._data[row]['subtype'] == CorporateAction.SpinOff:
                    text += f"; {basis:.2f}% " + self.tr(" cost basis") + "\n" + self._data[row]['note2']
                return text
            else:
                assert False
        elif column == 4:
            if self._data[row]['type'] == TransactionType.Trade:
                return [self._data[row]['amount'], self._data[row]['qty_trid']]
            elif self._data[row]['type'] == TransactionType.Dividend:
                return [self._data[row]['amount'], -self._data[row]['fee_tax']]
            elif self._data[row]['type'] == TransactionType.Action:
                if self._data[row]['asset'] != '':
                    return [self._data[row]['amount'], self._data[row]['price']]
                else:
                    return [self._data[row]['amount']]
            elif self._data[row]['type'] == TransactionType.Transfer:
                return [self._data[row]['amount']]
            elif self._data[row]['type'] == TransactionType.CorporateAction:
                if self._data[row]['subtype'] == CorporateAction.SpinOff or self._data[row]['subtype'] == CorporateAction.StockDividend:
                    return [None, self._data[row]['qty_trid'] - self._data[row]['amount']]
                else:
                    return [-self._data[row]['amount'], self._data[row]['qty_trid']]
            else:
                assert False
        elif column == 5:
            upper_part = f"{self._data[row]['t_amount']:,.2f}" if self._data[row]['t_amount'] != '' else "-.--"
            lower_part = f"{self._data[row]['t_qty']:,.2f}" if self._data[row]['t_qty'] != '' else ''
            if self._data[row]['type'] == TransactionType.CorporateAction:
                qty_before = self._data[row]['amount'] if self._data[row]['subtype'] == CorporateAction.SpinOff else 0
                qty_after = self._data[row]['t_qty'] if self._data[row]['subtype'] == CorporateAction.StockDividend else self._data[row]['qty_trid']
                if self._data[row]['subtype'] == CorporateAction.StockDividend:
                    text = f"\n{qty_after:,.2f}" if qty_after != '' else "\n-.--"
                else:
                    text = f"{qty_before:,.2f}\n{qty_after:,.2f}"
                return text
            elif self._data[row]['type'] == TransactionType.Action or self._data[row]['type'] == TransactionType.Transfer:
                return upper_part
            else:
                return upper_part + "\n" + lower_part
        elif column == 6:
            if self._data[row]['type'] == TransactionType.CorporateAction:
                asset_before = self._data[row]['asset'] if self._data[row]['subtype'] != CorporateAction.StockDividend else ""
                return f" {asset_before}\n {self._data[row]['note']}"
            else:
                if self._data[row]['asset'] != '':
                    return f" {self._data[row]['currency']}\n {self._data[row]['asset']}"
                else:
                    return f" {self._data[row]['currency']}"
        else:
            assert False

    def data_foreground(self, row, column):
        if column == 0:
            try:
                return QBrush(self.OperationSign[self._data[row]['type'], self._data[row]['subtype']][1])
            except KeyError:
                return QBrush(CustomColor.LightRed)
        if column == 5:
            if self._data[row]['reconciled'] == 1:
                return QBrush(CustomColor.Blue)

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
            return self._data[row]['type']
        else:
            return 0

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
            self._query.exec()
        self.fetchMore(self.createIndex(0, 0))
        self.modelReset.emit()

    def deleteRows(self, rows):
        for row in rows:
            if (row >= 0) and (row < len(self._data)):
                table_name = self._tables[self._data[row]['type']]
                query = f"DELETE FROM {table_name} WHERE id={self._data[row]['id']}"
                _ = executeSQL(query)
        self.prepareData()


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
