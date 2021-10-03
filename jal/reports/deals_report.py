from PySide6.QtCore import Qt
from PySide6.QtSql import QSqlTableModel
from jal.db.helpers import db_connection, executeSQL
from jal.constants import CorporateAction
from jal.widgets.delegates import TimestampDelegate, FloatDelegate


# -----------------------------------------------------------------------------------------------------------------------
class DealsReportModel(QSqlTableModel):
    def __init__(self, parent_view):
        self._columns = [("asset", self.tr("Asset")),
                         ("o_datetime", self.tr("Open Date")),
                         ("c_datetime", self.tr("Close Date")),
                         ("open_price", self.tr("Open Price")),
                         ("close_price", self.tr("Close Price")),
                         ("qty", self.tr("Qty")),
                         ("fee", self.tr("Fee")),
                         ("profit", self.tr("P/L")),
                         ("rel_profit", self.tr("P/L, %")),
                         ("corp_action", self.tr("Note"))]
        self.ca_names = {CorporateAction.SymbolChange: self.tr("Symbol change"),
                         CorporateAction.Split: self.tr("Split"),
                         CorporateAction.SpinOff: self.tr("Spin-off"),
                         CorporateAction.Merger: self.tr("Merger"),
                         CorporateAction.StockDividend: self.tr("Stock dividend")}
        self._view = parent_view
        self._group_dates = 0
        self._query = None
        self._timestamp_delegate = None
        self._float_delegate = None
        self._float2_delegate = None
        self._float4_delegate = None
        self._profit_delegate = None
        self._ca_delegate = None
        QSqlTableModel.__init__(self, parent=parent_view, db=db_connection())

    def setColumnNames(self):
        for column in self._columns:
            self.setHeaderData(self.fieldIndex(column[0]), Qt.Horizontal, column[1])

    def resetDelegates(self):
        for column in self._columns:
            self._view.setItemDelegateForColumn(self.fieldIndex(column[0]), None)

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if index.column() == self.fieldIndex("corp_action"):
                try:
                    ca_type = int(super().data(index, role))
                except ValueError:
                    ca_type = 0
                if ca_type > 0:
                    text = self.tr(" Opened with ") + self.ca_names[ca_type]
                elif ca_type < 0:
                    text = self.tr(" Closed with ") + self.ca_names[-ca_type]
                else:
                    text = ''
                return text
        return super().data(index, role)

    def configureView(self):
        self._view.setModel(self)
        self.setColumnNames()
        self.resetDelegates()
        font = self._view.horizontalHeader().font()
        font.setBold(True)
        self._view.horizontalHeader().setFont(font)
        self._view.setColumnWidth(self.fieldIndex("asset"), 300)
        self._view.setColumnWidth(self.fieldIndex("corp_action"), 200)
        self._view.setColumnWidth(self.fieldIndex("o_datetime"),
                                  self._view.fontMetrics().horizontalAdvance("00/00/0000 00:00:00") * 1.1)
        self._view.setColumnWidth(self.fieldIndex("c_datetime"),
                                  self._view.fontMetrics().horizontalAdvance("00/00/0000 00:00:00") * 1.1)
        if self._group_dates == 1:
            self._timestamp_delegate = TimestampDelegate(display_format='%d/%m/%Y')
        else:
            self._timestamp_delegate = TimestampDelegate()
        self._view.setItemDelegateForColumn(self.fieldIndex("o_datetime"), self._timestamp_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex("c_datetime"), self._timestamp_delegate)
        self._float_delegate = FloatDelegate(0, allow_tail=True)
        self._view.setItemDelegateForColumn(self.fieldIndex("qty"), self._float_delegate)
        self._float2_delegate = FloatDelegate(2, allow_tail=False)
        self._view.setItemDelegateForColumn(self.fieldIndex("fee"), self._float2_delegate)
        self._float4_delegate = FloatDelegate(4, allow_tail=False)
        self._view.setItemDelegateForColumn(self.fieldIndex("open_price"), self._float4_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex("close_price"), self._float4_delegate)
        self._profit_delegate = FloatDelegate(2, allow_tail=False, colors=True)
        self._view.setItemDelegateForColumn(self.fieldIndex("profit"), self._profit_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex("rel_profit"), self._profit_delegate)

    def prepare(self, begin, end, account_id, group_dates):
        if account_id == 0:
            raise ValueError(self.tr("You should select account to create Deals report"))
        self._group_dates = group_dates
        if group_dates == 1:
            self._query = executeSQL(
                "SELECT asset, "
                "strftime('%s', datetime(open_timestamp, 'unixepoch', 'start of day')) as o_datetime, "
                "strftime('%s', datetime(close_timestamp, 'unixepoch', 'start of day')) as c_datetime, "
                "SUM(open_price*qty)/SUM(qty) as open_price, SUM(close_price*qty)/SUM(qty) AS close_price, "
                "SUM(qty) as qty, SUM(fee) as fee, SUM(profit) as profit, "
                "coalesce(100*SUM(qty*(close_price-open_price)-fee)/SUM(qty*open_price), 0) AS rel_profit "
                "FROM deals_ext "
                "WHERE account_id=:account_id AND close_timestamp>=:begin AND close_timestamp<=:end "
                "GROUP BY asset, o_datetime, c_datetime "
                "ORDER BY c_datetime, o_datetime",
                [(":account_id", account_id), (":begin", begin), (":end", end)], forward_only=False)
        else:
            self._query = executeSQL(
                "SELECT asset, open_timestamp AS o_datetime, close_timestamp AS c_datetime, "
                "open_price, close_price, qty, fee, profit, rel_profit, corp_action "
                "FROM deals_ext "
                "WHERE account_id=:account_id AND close_timestamp>=:begin AND close_timestamp<=:end "
                "ORDER BY c_datetime, o_datetime",
                [(":account_id", account_id), (":begin", begin), (":end", end)], forward_only=False)
        self.setQuery(self._query)
        self.modelReset.emit()
