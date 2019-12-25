from constants import *
from PySide2.QtWidgets import QMainWindow, QFileDialog, QAbstractItemView
from PySide2.QtSql import QSqlDatabase, QSqlQuery, QSqlQueryModel, QSqlTableModel, QSqlRelationalTableModel
from PySide2.QtCore import Qt, Slot
from PySide2 import QtCore
from ui_main_window import Ui_LedgerMainWindow
from ledger_db import Ledger
from import_1c import import_1c
from build_ledger import Ledger_Bookkeeper
from rebuild_window import RebuildDialog
from balance_delegate import BalanceDelegate
from operation_delegate import OperationsDelegate

class MainWindow(QMainWindow, Ui_LedgerMainWindow):
    def __init__(self):
        QMainWindow.__init__(self, None)
        self.setupUi(self)

        self.ledger = Ledger()
        self.db = QSqlDatabase.addDatabase("QSQLITE")
        self.db.setDatabaseName(DB_PATH)
        self.db.open()

        self.balance_currency = CURRENCY_RUBLE
        self.balance_date = QtCore.QDateTime.currentSecsSinceEpoch()
        self.balance_active_only = 1

        self.ConfigureUI()
        self.UpdateBalances()

    def __del__(self):
        self.db.close()

    def ConfigureUI(self):
        self.BalanceDate.setCalendarPopup(True)
        self.BalanceDate.setDisplayFormat("dd/MM/yyyy")
        self.BalanceDate.setDateTime(QtCore.QDateTime.currentDateTime())

        self.CurrencyNameQuery = QSqlQuery(self.db)
        self.CurrencyNameQuery.exec_("SELECT id, name FROM actives WHERE type_id=1")
        self.CurrencyNameModel = QSqlQueryModel()
        self.CurrencyNameModel.setQuery(self.CurrencyNameQuery)
        self.CurrencyCombo.setModel(self.CurrencyNameModel)
        self.CurrencyCombo.setModelColumn(1)
        self.CurrencyCombo.setCurrentIndex(self.CurrencyCombo.findText("RUB"))

        self.BalancesModel = QSqlTableModel(db=self.db)
        self.BalancesModel.setTable("balances")
        self.BalancesModel.setEditStrategy(QSqlTableModel.OnManualSubmit)
        self.BalancesModel.setHeaderData(2, Qt.Horizontal, "Account")
        self.BalancesModel.setHeaderData(3, Qt.Horizontal, "Crcy")
        self.BalancesModel.setHeaderData(4, Qt.Horizontal, "Sum")
        self.BalancesModel.setHeaderData(5, Qt.Horizontal, "Sum, RUB")
        self.BalancesModel.select()
        self.BalancesTableView.setModel(self.BalancesModel)
        self.BalancesTableView.setItemDelegate(BalanceDelegate(self.BalancesTableView))
        self.BalancesTableView.setColumnHidden(0, True)
        self.BalancesTableView.setColumnHidden(1, True)
        self.BalancesTableView.setColumnHidden(6, True)
        self.BalancesTableView.setColumnHidden(7, True)
        self.BalancesTableView.verticalHeader().setVisible(False)
        self.BalancesTableView.show()

        self.OperationsQuery = QSqlQuery(self.db)
        self.OperationsQuery.exec_("SELECT m.type, m.id, m.timestamp, "
                                   "  m.account_id, a.name AS account, m.amount, "
                                   "  m.num_peer, m.active_id, s.name AS active, s.full_name AS active_name, "
                                   "m.qty_trid, m.price, m.fee_tax, "
                                   "  l.sum_amount AS t_amount, m.t_qty, "
                                   "  CASE WHEN m.timestamp<=a.reconciled_on THEN 1 ELSE 0 END AS reconciled "
                                   "FROM "
                                   "(SELECT 1 AS type, o.id, timestamp, p.name AS num_peer, account_id, sum(d.type*d.sum) AS amount, "
                                   "  o.alt_currency_id AS active_id, coalesce(-t1.id, t2.id, 0) AS qty_trid, sum(d.type*d.alt_sum) AS price, NULL AS fee_tax, NULL AS t_qty "
                                   "FROM actions AS o "
                                   "LEFT JOIN agents AS p ON o.peer_id = p.id "
                                   "LEFT JOIN transfers AS t1 ON t1.from_id = o.id "
                                   "LEFT JOIN transfers AS t2 ON t2.to_id = o.id "
                                   "LEFT JOIN action_details AS d ON o.id = d.pid "
                                   "GROUP BY o.id "
                                   "UNION ALL "
                                   "SELECT 2 AS type, d.id, d.timestamp, d.number AS num_peer, d.account_id, d.sum AS amount, "
                                   "   d.active_id, SUM(coalesce(l.amount,0)) AS qty_trid, NULL AS price, d.sum_tax AS fee_tax, NULL AS t_qty "
                                   "FROM dividends AS d "
                                   "LEFT JOIN ledger AS l ON d.active_id = l.active_id AND d.account_id = l.account_id AND l.book_account = 4 AND l.timestamp<=d.timestamp "
                                   "GROUP BY d.id "
                                   "UNION ALL "
                                   "SELECT 3 AS type, t.id, t.timestamp, t.number AS num_peer, t.account_id, t.sum AS amount, "
                                   "  t.active_id, t.qty AS qty_trid, t.price AS price, t.fee_broker+t.fee_exchange AS fee_tax, l.sum_amount AS t_qty "
                                   "FROM trades AS t "
                                   "LEFT JOIN sequence AS q ON q.type = 3 AND t.id = q.operation_id "
                                   "LEFT JOIN ledger_sums AS l ON l.sid = q.id AND l.book_account = 4 "
                                   "ORDER BY timestamp) AS m "
                                   "LEFT JOIN accounts AS a ON m.account_id = a.id "
                                   "LEFT JOIN actives AS s ON m.active_id = s.id "
                                   "LEFT JOIN sequence AS q ON m.type = q.type AND m.id = q.operation_id "
                                   "LEFT JOIN ledger_sums AS l ON l.sid = q.id AND (l.book_account = 3 or l.book_account=5)")
        self.OperationsModel = QSqlQueryModel()
        self.OperationsModel.setQuery(self.OperationsQuery)
        self.OperationsTableView.setModel(self.OperationsModel)
#        self.OperationsTableView.setItemDelegate(OperationsDelegate(self.OperationsTableView))
        self.OperationsTableView.setSelectionBehavior(QAbstractItemView.SelectRows)  # To select only 1 row
        self.OperationsTableView.setSelectionMode(QAbstractItemView.SingleSelection)
        self.OperationsTableView.verticalHeader().setDefaultSectionSize(21)
        self.OperationsTableView.verticalHeader().setVisible(False)
        self.OperationsTableView.show()

        # MENU ACTIONS
        self.actionExit.triggered.connect(qApp.quit)
        self.action_Import.triggered.connect(self.ImportFrom1C)
        self.action_Re_build_Ledger.triggered.connect(self.ShowRebuildDialog)
        #INTERFACE ACTIONS
        self.MainTabs.currentChanged.connect(self.OnMainTabChange)
        self.BalanceDate.dateChanged.connect(self.onBalanceDateChange)
        self.CurrencyCombo.currentIndexChanged.connect(self.OnBalanceCurrencyChange)
        self.ShowInactiveCheckBox.stateChanged.connect(self.OnBalanceInactiveChange)
        # TABLE ACTIONS
        self.OperationsTableView.selectionModel().selectionChanged.connect(self.OnOperationChange)

    def ImportFrom1C(self):
        import_directory = QFileDialog.getExistingDirectory(self, "Select directory with data to import")
        if import_directory:
            import_directory = import_directory + "/"
            print("Import 1C data from: ", import_directory)
            print("Import 1C data to:   ", DB_PATH)
            import_1c(DB_PATH, import_directory)

    def ShowRebuildDialog(self):
        query = QSqlQuery(self.db)
        query.exec_("SELECT ledger_frontier FROM frontier")
        query.next()
        current_frontier = query.value(0)

        rebuild_dialog = RebuildDialog(current_frontier)
        rebuild_dialog.setGeometry(self.x()+64, self.y()+64, rebuild_dialog.width(), rebuild_dialog.height())
        res = rebuild_dialog.exec_()
        if res:
            self.db.close()
            rebuild_date = rebuild_dialog.getTimestamp()
            Ledger = Ledger_Bookkeeper(DB_PATH)
            Ledger.RebuildLedger(rebuild_date)
            self.db.open()

    @Slot()
    def OnMainTabChange(self, tab_index):
        if tab_index == 0:
            pass
        elif tab_index == 1:
            self.UpdateTransactionsTab()

    @Slot()
    def onBalanceDateChange(self, new_date):
        self.balance_date = self.BalanceDate.dateTime().toSecsSinceEpoch()
        self.UpdateBalances()

    @Slot()
    def OnBalanceCurrencyChange(self, currency_index):
        self.balance_currency = self.CurrencyNameModel.record(currency_index).value("id")
        self.BalancesModel.setHeaderData(5, Qt.Horizontal, "Sum, " + self.CurrencyNameModel.record(currency_index).value("name"))
        self.UpdateBalances()

    @Slot()
    def OnBalanceInactiveChange(self, state):
        if (state == 0):
            self.balance_active_only = 1
        else:
            self.balance_active_only = 0
        self.UpdateBalances()

    def UpdateBalances(self):
        self.ledger.BuildBalancesTable(self.balance_date, self.balance_currency, self.balance_active_only)
        self.BalancesModel.select()

    def UpdateTransactionsTab(self):
        self.StatusBar.showMessage("Transactions to be here")

    @Slot()
    def OnOperationChange(self, selected, deselected):
        idx = selected.indexes()
        selected_row = idx[0].row()
        self.OperationsTabs.setCurrentIndex(self.OperationsModel.record(selected_row).value(0) - 1)