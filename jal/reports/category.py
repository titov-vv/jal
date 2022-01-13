from PySide6.QtCore import Qt, Signal, Slot, QObject
from PySide6.QtSql import QSqlTableModel
from PySide6.QtWidgets import QHeaderView
from jal.ui.reports.ui_category_report import Ui_CategoryReportWidget
from jal.db.helpers import db_connection, executeSQL
from jal.widgets.delegates import FloatDelegate, TimestampDelegate
from jal.widgets.mdi import MdiWidget

JAL_REPORT_CLASS = "CategoryReport"


# ----------------------------------------------------------------------------------------------------------------------
# TODO Reimplement report based on 'ledger' DB table in order to include all types of operations
class CategoryReportModel(QSqlTableModel):
    def __init__(self, parent_view):
        self._columns = [("timestamp", self.tr("Timestamp")),
                         ("account", self.tr("Account")),
                         ("name", self.tr("Peer Name")),
                         ("amount", self.tr("Amount")),
                         ("note", self.tr("Note"))]
        self._view = parent_view
        self._query = None
        self._timestamp_delegate = None
        self._float_delegate = None
        self._begin = 0
        self._end = 0
        self._category_id = 0
        QSqlTableModel.__init__(self, parent=parent_view, db=db_connection())

    def setColumnNames(self):
        for column in self._columns:
            self.setHeaderData(self.fieldIndex(column[0]), Qt.Horizontal, column[1])

    def resetDelegates(self):
        for column in self._columns:
            self._view.setItemDelegateForColumn(self.fieldIndex(column[0]), None)

    def configureView(self):
        if self.columnCount() == 0:
            return
        self._view.setModel(self)
        self.setColumnNames()
        self.resetDelegates()
        font = self._view.horizontalHeader().font()
        font.setBold(True)
        self._view.horizontalHeader().setFont(font)
        self._view.horizontalHeader().setSectionResizeMode(self.fieldIndex("note"), QHeaderView.Stretch)
        self._view.setColumnWidth(self.fieldIndex("account"), 200)
        self._view.setColumnWidth(self.fieldIndex("name"), 200)
        self._view.setColumnWidth(self.fieldIndex("amount"), 200)
        self._view.setColumnWidth(self.fieldIndex("timestamp"),
                                  self._view.fontMetrics().horizontalAdvance("00/00/0000 00:00:00") * 1.1)
        self._timestamp_delegate = TimestampDelegate()
        self._view.setItemDelegateForColumn(self.fieldIndex("timestamp"), self._timestamp_delegate)
        self._float_delegate = FloatDelegate(2, allow_tail=False)
        self._view.setItemDelegateForColumn(self.fieldIndex("amount"), self._float_delegate)

    def setDatesRange(self, begin, end):
        self._begin = begin
        self._end = end
        self.calculateCategoryReport()
        self.configureView()

    def setCategory(self, category):
        self._category_id = category
        self.calculateCategoryReport()
        self.configureView()

    def calculateCategoryReport(self):
        if self._category_id == 0:
            return
        self._query = executeSQL("SELECT a.timestamp, ac.name AS account, p.name, d.amount, d.note "
                                "FROM actions AS a "
                                "LEFT JOIN action_details AS d ON d.pid=a.id "
                                "LEFT JOIN agents AS p ON p.id=a.peer_id "
                                "LEFT JOIN accounts AS ac ON ac.id=a.account_id "
                                "WHERE a.timestamp>=:begin AND a.timestamp<=:end "
                                "AND d.category_id=:category_id",
                                [(":category_id", self._category_id), (":begin", self._begin), (":end", self._end)],
                                 forward_only=False)
        self.setQuery(self._query)
        self.modelReset.emit()


# ----------------------------------------------------------------------------------------------------------------------
class CategoryReport(QObject):
    def __init__(self):
        super().__init__()
        self.name = self.tr("Operations by Category")
        self.window_class = "CategoryReportWindow"


# ----------------------------------------------------------------------------------------------------------------------
class CategoryReportWindow(MdiWidget, Ui_CategoryReportWidget):
    def __init__(self, parent=None):
        MdiWidget.__init__(self, parent)
        self.setupUi(self)
        self.parent_mdi = parent

        self.category_model = CategoryReportModel(self.ReportTableView)
        self.ReportTableView.setModel(self.category_model)

        self.connect_signals_and_slots()

    def connect_signals_and_slots(self):
        self.ReportRange.changed.connect(self.ReportTableView.model().setDatesRange)
        self.ReportCategoryEdit.changed.connect(self.onCategoryChange)

    @Slot()
    def onCategoryChange(self):
        self.ReportTableView.model().setCategory(self.ReportCategoryEdit.selected_id)
