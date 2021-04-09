from PySide2.QtCore import Qt, Signal
from PySide2.QtSql import QSqlTableModel
from PySide2.QtWidgets import QHeaderView
from jal.db.helpers import db_connection, executeSQL
from jal.widgets.helpers import g_tr
from jal.widgets.delegates import FloatDelegate, TimestampDelegate


#-----------------------------------------------------------------------------------------------------------------------
# TODO Reimplement report based on 'ledger' DB table in order to include all types of operations
class CategoryReportModel(QSqlTableModel):
    def __init__(self, parent_view):
        self._columns = [("timestamp", g_tr("Reports", "Timestamp")),
                         ("account", g_tr("Reports", "Account")),
                         ("name", g_tr("Reports", "Peer Name")),
                         ("sum", g_tr("Reports", "Amount")),
                         ("note", g_tr("Reports", "Note"))]
        self._view = parent_view
        self._query = None
        self._timestamp_delegate = None
        self._float_delegate = None
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
        self._view.horizontalHeader().setSectionResizeMode(self.fieldIndex("note"), QHeaderView.Stretch)
        self._view.setColumnWidth(self.fieldIndex("account"), 200)
        self._view.setColumnWidth(self.fieldIndex("name"), 200)
        self._view.setColumnWidth(self.fieldIndex("amount"), 200)
        self._view.setColumnWidth(self.fieldIndex("timestamp"),
                                  self._view.fontMetrics().width("00/00/0000 00:00:00") * 1.1)
        self._timestamp_delegate = TimestampDelegate()
        self._view.setItemDelegateForColumn(self.fieldIndex("timestamp"), self._timestamp_delegate)
        self._float_delegate = FloatDelegate(2, allow_tail=False)
        self._view.setItemDelegateForColumn(self.fieldIndex("amount"), self._float_delegate)

    def prepare(self, begin, end, category_id, group_dates):
        if category_id == 0:
            raise ValueError(g_tr('Reports', "You should select category to create By Category report"))
        self._query = executeSQL("SELECT a.timestamp, ac.name AS account, p.name, d.amount, d.note "
                                "FROM actions AS a "
                                "LEFT JOIN action_details AS d ON d.pid=a.id "
                                "LEFT JOIN agents AS p ON p.id=a.peer_id "
                                "LEFT JOIN accounts AS ac ON ac.id=a.account_id "
                                "WHERE a.timestamp>=:begin AND a.timestamp<=:end "
                                "AND d.category_id=:category_id",
                                [(":category_id", category_id), (":begin", begin), (":end", end)], forward_only=False)
        self.setQuery(self._query)
        self.modelReset.emit()
