from PySide2.QtCore import Qt
from PySide2.QtSql import QSqlTableModel
from jal.db.helpers import db_connection, executeSQL
from widgets.helpers import g_tr
from jal.widgets.delegates import ReportsTimestampDelegate, ReportsProfitDelegate, \
    ReportsCorpActionDelegate, ReportsFloatDelegate


# -----------------------------------------------------------------------------------------------------------------------
class DealsReportModel(QSqlTableModel):
    def __init__(self, parent_view):
        self._columns = [("asset", g_tr("Reports", "Asset")),
                         ("open_timestamp", g_tr("Reports", "Open Date")),
                         ("close_timestamp", g_tr("Reports", "Close Date")),
                         ("open_price", g_tr("Reports", "Open Price")),
                         ("close_price", g_tr("Reports", "Close Price")),
                         ("qty", g_tr("Reports", "Qty")),
                         ("corp_action", g_tr("Reports", "Note"))]
        self._view = parent_view
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

    def configureView(self):
        self._view.setModel(self)
        self.setColumnNames()
        self.resetDelegates()
        font = self._view.horizontalHeader().font()
        font.setBold(True)
        self._view.horizontalHeader().setFont(font)
        self._view.setColumnWidth(self.fieldIndex("asset"), 300)
        self._view.setColumnWidth(self.fieldIndex("corp_action"), 200)
        self._view.setColumnWidth(self.fieldIndex("open_timestamp"),
                                  self._view.fontMetrics().width("00/00/0000 00:00:00") * 1.1)
        self._view.setColumnWidth(self.fieldIndex("close_timestamp"),
                                  self._view.fontMetrics().width("00/00/0000 00:00:00") * 1.1)
        self._timestamp_delegate = ReportsTimestampDelegate()
        self._view.setItemDelegateForColumn(self.fieldIndex("open_timestamp"), self._timestamp_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex("close_timestamp"), self._timestamp_delegate)
        self._float_delegate = ReportsFloatDelegate()
        self._view.setItemDelegateForColumn(self.fieldIndex("qty"), self._float_delegate)
        self._float2_delegate = ReportsFloatDelegate(2)
        self._view.setItemDelegateForColumn(self.fieldIndex("fee"), self._float2_delegate)
        self._float4_delegate = ReportsFloatDelegate(4)
        self._view.setItemDelegateForColumn(self.fieldIndex("open_price"), self._float4_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex("close_price"), self._float4_delegate)
        self._profit_delegate = ReportsProfitDelegate()
        self._view.setItemDelegateForColumn(self.fieldIndex("profit"), self._profit_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex("rel_profit"), self._profit_delegate)
        self._ca_delegate = ReportsCorpActionDelegate()
        self._view.setItemDelegateForColumn(self.fieldIndex("corp_action"), self._ca_delegate)

    def prepare(self, begin, end, account_id, group_dates):
        if account_id == 0:
            self.report_failure.emit(g_tr('Reports', "You should select account to create Deals report"))
            return False
        if group_dates == 1:
            self._query = executeSQL(
                               "SELECT asset, "
                               "strftime('%s', datetime(open_timestamp, 'unixepoch', 'start of day')) as open_timestamp, "
                               "strftime('%s', datetime(close_timestamp, 'unixepoch', 'start of day')) as close_timestamp, "
                               "SUM(open_price*qty)/SUM(qty) as open_price, SUM(close_price*qty)/SUM(qty) AS close_price, "
                               "SUM(qty) as qty, SUM(fee) as fee, SUM(profit) as profit, "
                               "coalesce(100*SUM(qty*(close_price-open_price)-fee)/SUM(qty*open_price), 0) AS rel_profit "
                               "FROM deals_ext "
                               "WHERE account_id=:account_id AND close_timestamp>=:begin AND close_timestamp<=:end "
                               "GROUP BY asset, open_timestamp, close_timestamp "
                               "ORDER BY close_timestamp, open_timestamp",
                               [(":account_id", account_id), (":begin", begin), (":end", end)], forward_only=False)
        else:
            self._query = executeSQL("SELECT asset, open_timestamp, close_timestamp, open_price, close_price, "
                                    "qty, fee, profit, rel_profit, corp_action FROM deals_ext "
                                    "WHERE account_id=:account_id AND close_timestamp>=:begin AND close_timestamp<=:end "
                                    "ORDER BY close_timestamp, open_timestamp",
                                    [(":account_id", account_id), (":begin", begin), (":end", end)], forward_only=False)
        self.setQuery(self._query)
        self.modelReset.emit()
