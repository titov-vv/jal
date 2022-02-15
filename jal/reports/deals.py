from PySide6.QtCore import Qt, Slot, QObject
from PySide6.QtSql import QSqlTableModel
from jal.ui.reports.ui_deals_report import Ui_DealsReportWidget
from jal.db.helpers import db_connection, executeSQL
from jal.db.operations import CorporateAction
from jal.widgets.delegates import TimestampDelegate, FloatDelegate
from jal.widgets.mdi import MdiWidget

JAL_REPORT_CLASS = "DealsReport"


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
        self.ca_names = {
            CorporateAction.SymbolChange: self.tr("Symbol change"),
            CorporateAction.Split: self.tr("Split"),
            CorporateAction.SpinOff: self.tr("Spin-off"),
            CorporateAction.Merger: self.tr("Merger")
        }
        self._view = parent_view
        self._begin = 0
        self._end = 0
        self._account_id = 0
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

    def setDatesRange(self, begin, end):
        self._begin = begin
        self._end = end
        self.calculateDealsReport()
        self.configureView()

    def setAccount(self, account_id):
        self._account_id = account_id
        self.calculateDealsReport()
        self.configureView()

    def setGrouping(self, group_dates):
        self._group_dates = group_dates
        self.calculateDealsReport()
        self.configureView()

    def calculateDealsReport(self):
        if self._account_id == 0:
            return
        if self._group_dates == 1:
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
                [(":account_id", self._account_id), (":begin", self._begin), (":end", self._end)], forward_only=False)
        else:
            self._query = executeSQL(
                "SELECT asset, open_timestamp AS o_datetime, close_timestamp AS c_datetime, "
                "open_price, close_price, qty, fee, profit, rel_profit, corp_action "
                "FROM deals_ext "
                "WHERE account_id=:account_id AND close_timestamp>=:begin AND close_timestamp<=:end "
                "ORDER BY c_datetime, o_datetime",
                [(":account_id", self._account_id), (":begin", self._begin), (":end", self._end)], forward_only=False)
        self.setQuery(self._query)
        self.modelReset.emit()


# ----------------------------------------------------------------------------------------------------------------------
class DealsReport(QObject):
    def __init__(self):
        super().__init__()
        self.name = self.name = self.tr("Deals by Account")
        self.window_class = "DealsReportWindow"


# ----------------------------------------------------------------------------------------------------------------------
class DealsReportWindow(MdiWidget, Ui_DealsReportWidget):
    def __init__(self, parent=None):
        MdiWidget.__init__(self, parent)
        self.setupUi(self)
        self.parent_mdi = parent

        self.category_model = DealsReportModel(self.ReportTableView)
        self.ReportTableView.setModel(self.category_model)

        self.connect_signals_and_slots()

    def connect_signals_and_slots(self):
        self.ReportRange.changed.connect(self.ReportTableView.model().setDatesRange)
        self.ReportAccountBtn.changed.connect(self.onAccountChange)
        self.ReportGroupCheck.clicked.connect(self.onGroupChange)

    @Slot()
    def onAccountChange(self):
        self.ReportTableView.model().setAccount(self.ReportAccountBtn.account_id)

    @Slot()
    def onGroupChange(self):
        group_dates = 1 if self.ReportGroupCheck.isChecked() else 0
        self.ReportTableView.model().setGrouping(group_dates)
