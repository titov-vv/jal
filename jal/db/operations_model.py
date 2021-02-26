import logging
from datetime import datetime
from PySide2.QtCore import Qt, Slot, QAbstractTableModel, QDate
from PySide2.QtSql import QSqlQuery
from PySide2.QtGui import QBrush, QFont
from PySide2.QtWidgets import QStyledItemDelegate, QHeaderView
from jal.constants import CustomColor, TransactionType, TransferSubtype, DividendSubtype, CorporateAction
from jal.ui_custom.helpers import g_tr
from jal.db.helpers import readSQL, readSQLrecord, executeSQL


class OperationsModel(QAbstractTableModel):
    PAGE_SIZE = 100
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

    def __init__(self, parent_view, db):
        super().__init__(parent_view)
        self._view = parent_view
        self._amount_delegate = None
        self._db = db
        self._row_count = 0
        self._current_size = 0
        self._table_name = 'all_operations'
        self._query = QSqlQuery(self._db)
        self._begin = 0
        self._end = 0
        self._account = 0

        self.prepareData()

    def rowCount(self, parent=None):
        return self._current_size

    def columnCount(self, parent=None):
        return len(self._columns)

    def canFetchMore(self, index):
        return self._current_size < self._row_count

    def fetchMore(self, index):
        new_size = self._current_size + self.PAGE_SIZE
        new_size = new_size if new_size < self._row_count else self._row_count
        self.beginInsertRows(index, self._current_size, new_size - 1)
        self._current_size = new_size
        self.endInsertRows()

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._columns[section]
        return None

    def get_operation(self, row):
        if self._query.seek(row):
            data = readSQLrecord(self._query, named=True)
            return data['type'], data['id']
        else:
            return [0, 0]

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if self._query.seek(index.row()):
            row = readSQLrecord(self._query, named=True)
        else:
            logging.error(g_tr('OperationsModel', "Can't fetch operation data for row ") + f"{index.row()}")
            return

        if role == Qt.DisplayRole:
            return self.data_text(index.column(), row)
        if role == Qt.FontRole and index.column() == 0:
            font = QFont()
            font.setBold(True)
            return font
        if role == Qt.ForegroundRole:
            return self.data_foreground(index.column(), row)
        if role == Qt.TextAlignmentRole:
            if index.column() == 0:
                return Qt.AlignCenter
            if index.column() == 4 or index.column() == 5:
                return Qt.AlignRight
            return Qt.AlignLeft

    def data_text(self, column, data):
        if column == 0:
            try:
                return self.OperationSign[data['type'], data['subtype']][0]
            except:
                return '?'
        elif column == 1:
            if (data['type'] == TransactionType.Trade) or (data['type'] == TransactionType.Dividend) \
                    or (data['type'] == TransactionType.CorporateAction):
                return f"{datetime.utcfromtimestamp(data['timestamp']).strftime('%d/%m/%Y %H:%M:%S')}\n# {data['num_peer']}"
            else:
                return datetime.utcfromtimestamp(data['timestamp']).strftime('%d/%m/%Y %H:%M:%S')
        elif column == 2:
            if data['type'] == TransactionType.Action:
                return data['account']
            elif (data['type'] == TransactionType.Trade) \
                    or (data['type'] == TransactionType.Dividend) \
                    or (data['type'] == TransactionType.CorporateAction):
                return data['account'] + "\n" + data['asset_name']
            elif data['type'] == TransactionType.Transfer:
                if data['subtype'] == TransferSubtype.Fee:
                    return data['account']
                elif data['subtype'] == TransferSubtype.Outgoing:
                    return data['account'] + " -> " + data['note2']
                elif data['subtype'] == TransferSubtype.Incoming:
                    return data['account'] + " <- " + data['note2']
        elif column == 3:
            if data['type'] == TransactionType.Action:
                return data['num_peer']
            elif data['type'] == TransactionType.Transfer:
                rate = 0 if data['price'] == '' else data['price']
                if data['currency'] != data['num_peer']:
                    if rate != 0:
                        if rate > 1:
                            return data['note'] + f" [1 {data['currency']} = {rate:.4f} {data['num_peer']}]"
                        elif rate < 1:
                            rate = 1 / rate
                            return data['note'] +  f" [{rate:.4f} {data['currency']} = 1 {data['num_peer']}]"
                        else:
                            return data['note']
                    else:
                        return g_tr('OperationsModel', "Error. Zero rate")
                else:
                    return data['note']
            elif data['type'] == TransactionType.Dividend:
                return data['note'] + "\n" + g_tr('OperationsModel', "Tax: ") + data['note2']
            elif data['type'] == TransactionType.Trade:
                if data['fee_tax'] != 0:
                    text = f"{data['qty_trid']:+.2f} @ {data['price']:.4f}\n({data['fee_tax']:.2f}) "
                else:
                    text = f"{data['qty_trid']:+.2f} @ {data['price']:.4f}\n"
                text = text + data['note'] if data['note'] else text
                return text
            elif data['type'] == TransactionType.CorporateAction:
                basis = 100.0 * data['price']
                if data['subtype'] == CorporateAction.StockDividend:
                    qty_after = data['qty_trid'] - data['amount']
                else:
                    qty_after = data['qty_trid']
                text = self.CorpActionNames[data['subtype']].format(old=data['asset'], new=data['note'],
                                                                    before=data['amount'], after=qty_after)
                if data['subtype'] == CorporateAction.SpinOff:
                    text += f"; {basis:.2f}% " + g_tr('OperationsModel', " cost basis") + "\n" + data['note2']
                return text
            else:
                assert False
        elif column == 4:
            if data['type'] == TransactionType.Trade:
                return [data['amount'], data['qty_trid']]
            elif data['type'] == TransactionType.Dividend:
                return [data['amount'], -data['fee_tax']]
            elif data['type'] == TransactionType.Action or data['type'] == TransactionType.Transfer:
                return [data['amount']]
            elif data['type'] == TransactionType.CorporateAction:
                if data['subtype'] == CorporateAction.SpinOff or data['subtype'] == CorporateAction.StockDividend:
                    return [None, data['qty_trid'] - data['amount']]
                else:
                    return [-data['amount'], data['qty_trid']]
            else:
                assert False
        elif column == 5:
            upper_part = f"{data['t_amount']:,.2f}" if data['t_amount'] != '' else "-.--"
            lower_part = f"{data['t_qty']:,.2f}" if data['t_qty'] != '' else ''
            if data['type'] == TransactionType.CorporateAction:
                qty_before = data['amount'] if data['subtype'] == CorporateAction.SpinOff else 0
                qty_after = data['t_qty'] if data['subtype'] == CorporateAction.StockDividend else data['qty_trid']
                if data['subtype'] == CorporateAction.StockDividend:
                    text = f"\n{qty_after:,.2f}" if qty_after != '' else "\n-.--"
                else:
                    text = f"{qty_before:,.2f}\n{qty_after:,.2f}"
                return text
            elif data['type'] == TransactionType.Action or data['type'] == TransactionType.Transfer:
                return upper_part
            else:
                return upper_part + "\n" + lower_part
        elif column == 6:
            if data['type'] == TransactionType.CorporateAction:
                asset_before = data['asset'] if data['subtype'] != CorporateAction.StockDividend else ""
                return f" {asset_before}\n {data['note']}"
            else:
                if data['asset'] != '':
                    return f" {data['currency']}\n {data['asset']}"
                else:
                    return f" {data['currency']}"
        else:
            assert False

    def data_foreground(self, column, data):
        if column == 0:
            try:
                return QBrush(self.OperationSign[data['type'], data['subtype']][1])
            except:
                return QBrush(CustomColor.LightRed)
        if column == 5:
            if data['reconciled'] == 1:
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
        pass  # TODO add free text search

    def update(self):
        self.prepareData()

    def get_operation_type(self, row):
        if self._query.seek(row):
            data = readSQLrecord(self._query, named=True)
            return data['type']
        return 0

    def reconcile_operation(self, row):
        if self._query.seek(row):
            data = readSQLrecord(self._query, named=True)
            timestamp = data['timestamp']
            account_id = data['account_id']
            _ = executeSQL(self._db, "UPDATE accounts SET reconciled_on=:timestamp WHERE id = :account_id",
                           [(":timestamp", timestamp), (":account_id", account_id)])
            self.prepareData()

    def prepareData(self):
        if self._begin == 0 and self._end == 0:
            self._row_count = self._current_size = 0
        else:
            count_pfx = "SELECT COUNT(*) "
            query_pfx = "SELECT * "
            query_suffix = f"FROM {self._table_name} AS o WHERE o.timestamp>={self._begin} AND o.timestamp<={self._end}"
            if self._account:
                query_suffix = query_suffix + f" AND o.account_id = {self._account}"
            self._row_count = readSQL(self._db, count_pfx + query_suffix)
            self._current_size = self.PAGE_SIZE if self.PAGE_SIZE < self._row_count else self._row_count
            self._query.prepare(query_pfx + query_suffix)
            self._query.exec_()
        self.modelReset.emit()

    def deleteRows(self, rows):
        for row in rows:
            if self._query.seek(row):
                data = readSQLrecord(self._query, named=True)
                table_name = self._tables[data['type']]
                query = f"DELETE FROM {table_name} WHERE id={data['id']}"
                _ = executeSQL(self._db, query)
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