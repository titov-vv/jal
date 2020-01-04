from constants import *
from PySide2.QtWidgets import QMainWindow, QFileDialog, QAbstractItemView, QDataWidgetMapper, QHeaderView
from PySide2.QtSql import QSqlDatabase, QSqlQuery, QSqlQueryModel, QSqlTableModel, QSqlRelationalTableModel, QSqlRelation
from PySide2.QtCore import Qt, Slot, QByteArray
from PySide2 import QtCore
from ui_main_window import Ui_LedgerMainWindow
from ledger_db import Ledger
from import_1c import import_1c
from build_ledger import Ledger_Bookkeeper
from rebuild_window import RebuildDialog
from balance_delegate import BalanceDelegate
from operation_delegate import *
from dividend_delegate import DividendSqlDelegate
from trade_delegate import TradeSqlDelegate
from action_delegate import ActionSqlDelegate

class MainWindow(QMainWindow, Ui_LedgerMainWindow):
    def __init__(self):
        QMainWindow.__init__(self, None)
        self.setupUi(self)

        self.db = QSqlDatabase.addDatabase("QSQLITE")
        self.db.setDatabaseName(DB_PATH)
        self.db.open()
        self.ledger = Ledger(self.db)

        self.balance_currency = CURRENCY_RUBLE
        self.balance_date = QtCore.QDateTime.currentSecsSinceEpoch()
        self.balance_active_only = 1

        self.operations_since_timestamp = 0

        self.ConfigureUI()
        self.UpdateBalances()

    def __del__(self):
        self.db.close()

    def ConfigureUI(self):
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
        self.BalancesModel.setHeaderData(3, Qt.Horizontal, "Balance")
        self.BalancesModel.setHeaderData(4, Qt.Horizontal, "")
        self.BalancesModel.setHeaderData(5, Qt.Horizontal, "Balance, RUB")
        self.BalancesModel.select()
        self.BalancesTableView.setModel(self.BalancesModel)
        self.BalancesTableView.setItemDelegate(BalanceDelegate(self.BalancesTableView))
        self.BalancesTableView.setColumnHidden(0, True)
        self.BalancesTableView.setColumnHidden(1, True)
        self.BalancesTableView.setColumnHidden(6, True)
        self.BalancesTableView.setColumnHidden(7, True)
        self.BalancesTableView.setColumnWidth(2, 150)
        self.BalancesTableView.setColumnWidth(3, 100)
        self.BalancesTableView.setColumnWidth(4, 40)
        self.BalancesTableView.setColumnWidth(5, 110)
        font = self.BalancesTableView.horizontalHeader().font()
        font.setBold(True)
        self.BalancesTableView.horizontalHeader().setFont(font)
        self.BalancesTableView.show()

        self.ChooseAccountBtn.init_DB(self.db)

        self.OperationsModel = QSqlTableModel(db=self.db)
        self.OperationsModel.setTable("all_operations")
        self.OperationsModel.setHeaderData(0, Qt.Horizontal, " ")
        self.OperationsModel.setHeaderData(2, Qt.Horizontal, "Timestamp")
        self.OperationsModel.setHeaderData(4, Qt.Horizontal, "Account")
        self.OperationsModel.setHeaderData(9, Qt.Horizontal, "Notes")
        self.OperationsModel.setHeaderData(11, Qt.Horizontal, "Amount")
        self.OperationsModel.setHeaderData(15, Qt.Horizontal, "Balance")
        self.OperationsModel.setHeaderData(17, Qt.Horizontal, "Currency")
        self.OperationsModel.select()
        self.OperationsTableView.setModel(self.OperationsModel)
        self.OperationsTableView.setItemDelegateForColumn(0, OperationsTypeDelegate(self.OperationsTableView))
        self.OperationsTableView.setItemDelegateForColumn(2, OperationsTimestampDelegate(self.OperationsTableView))
        self.OperationsTableView.setItemDelegateForColumn(4, OperationsAccountDelegate(self.OperationsTableView))
        self.OperationsTableView.setItemDelegateForColumn(9, OperationsNotesDelegate(self.OperationsTableView))
        self.OperationsTableView.setItemDelegateForColumn(11, OperationsAmountDelegate(self.OperationsTableView))
        self.OperationsTableView.setItemDelegateForColumn(15, OperationsTotalsDelegate(self.OperationsTableView))
        self.OperationsTableView.setItemDelegateForColumn(17, OperationsCurrencyDelegate(self.OperationsTableView))
        self.OperationsTableView.setSelectionBehavior(QAbstractItemView.SelectRows)  # To select only 1 row
        self.OperationsTableView.setSelectionMode(QAbstractItemView.SingleSelection)
        self.OperationsTableView.setColumnHidden(1, True)
        self.OperationsTableView.setColumnHidden(3, True) # account id
        self.OperationsTableView.setColumnHidden(5, True) # peer number
        self.OperationsTableView.setColumnHidden(6, True) # active id
        self.OperationsTableView.setColumnHidden(7, True) # active name
        self.OperationsTableView.setColumnHidden(8, True) # active full name
        self.OperationsTableView.setColumnHidden(10, True) # note 2
        self.OperationsTableView.setColumnHidden(12, True) # qty
        self.OperationsTableView.setColumnHidden(13, True) # price
        self.OperationsTableView.setColumnHidden(14, True) # fee
        self.OperationsTableView.setColumnHidden(16, True) # total_qty
        self.OperationsTableView.setColumnHidden(18, True)  # reconciled
        self.OperationsTableView.setColumnWidth(0, 10)
        self.OperationsTableView.setColumnWidth(2, 150)
        self.OperationsTableView.setColumnWidth(4, 400)
        self.OperationsTableView.setColumnWidth(9, 300)
        self.OperationsTableView.setWordWrap(False)
        #self.OperationsTableView.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.OperationsTableView.horizontalHeader().setFont(font)
        self.OperationsTableView.show()

        ###############################################################################################
        # CONFIGURE ACTIONS TAB                                                                       #
        ###############################################################################################
        self.ActionAccountWidget.init_DB(self.db)

        self.ActionsModel = QSqlRelationalTableModel(db=self.db)
        self.ActionsModel.setTable("actions")
        self.ActionsModel.setEditStrategy(QSqlTableModel.OnManualSubmit)
        account_idx = self.ActionsModel.fieldIndex("account_id")
        #peer_id = self.ActionsModel.fieldIndex("peer_id")
        #self.ActionsModel.setRelation(peer_id, QSqlRelation("agents", "id", "name"))
        # Add Peer Selector
        self.ActionsModel.select()
        self.ActionsDataMapper = QDataWidgetMapper(self)
        self.ActionsDataMapper.setModel(self.ActionsModel)
        self.ActionsDataMapper.setSubmitPolicy(QDataWidgetMapper.ManualSubmit)
        self.ActionsDataMapper.setItemDelegate(ActionSqlDelegate(self.ActionsDataMapper))
        self.ActionsDataMapper.addMapping(self.ActionAccountWidget, account_idx) #, QByteArray().setRawData("account_id", 10))
        self.ActionsDataMapper.addMapping(self.ActionTimestampEdit, self.ActionsModel.fieldIndex("timestamp"))
        self.ActionsDataMapper.addMapping(self.ActionPeerEdit, self.ActionsModel.fieldIndex("peer_id"))

        self.ActionDetailsModel = QSqlRelationalTableModel(db=self.db)
        self.ActionDetailsModel.setTable("action_details")
        self.ActionDetailsModel.setEditStrategy(QSqlTableModel.OnManualSubmit)
        self.ActionDetailsModel.setHeaderData(2, Qt.Horizontal, "Category")
        self.ActionDetailsModel.setHeaderData(3, Qt.Horizontal, "Tags")
        self.ActionDetailsModel.setHeaderData(4, Qt.Horizontal, "Amount")
        self.ActionDetailsModel.setHeaderData(5, Qt.Horizontal, "Amount *")
        self.ActionDetailsModel.setHeaderData(6, Qt.Horizontal, "Note")
        self.ActionDetailsModel.select()
        self.ActionDetailsTableView.setModel(self.ActionDetailsModel)
        self.ActionDetailsTableView.setSelectionBehavior(QAbstractItemView.SelectRows)  # To select only 1 row
        self.ActionDetailsTableView.setSelectionMode(QAbstractItemView.SingleSelection)
        self.ActionDetailsTableView.setColumnHidden(0, True)  # pid
        self.ActionDetailsTableView.setColumnHidden(1, True)  # type
        self.ActionDetailsTableView.setColumnWidth(2, 200)  # category
        self.ActionDetailsTableView.setColumnWidth(3, 200)  # tags
        self.ActionDetailsTableView.setColumnWidth(4, 100)  # amount
        self.ActionDetailsTableView.setColumnWidth(5, 100)  # amount *
        self.ActionDetailsTableView.setColumnWidth(6, 400)  # note
        self.ActionDetailsTableView.horizontalHeader().moveSection(6, 2)
        self.ActionDetailsTableView.setColumnWidth(6, 400)
        self.ActionDetailsTableView.show()

        ###############################################################################################
        # CONFIGURE TRADES TAB                                                                        #
        ###############################################################################################
        self.TradeAccountWidget.init_DB(self.db)
        self.TradeActiveWidget.init_DB(self.db)

        self.TradesModel = QSqlRelationalTableModel(db=self.db)
        self.TradesModel.setTable("trades")
        self.TradesModel.setEditStrategy(QSqlTableModel.OnManualSubmit)
        account_idx = self.TradesModel.fieldIndex("account_id")
        active_idx = self.TradesModel.fieldIndex("active_id")
        self.TradesModel.select()
        self.TradesDataMapper = QDataWidgetMapper(self)
        self.TradesDataMapper.setModel(self.TradesModel)
        self.TradesDataMapper.setSubmitPolicy(QDataWidgetMapper.ManualSubmit)
        self.TradesDataMapper.setItemDelegate(TradeSqlDelegate(self.TradesDataMapper))
        self.TradesDataMapper.addMapping(self.TradeAccountWidget, account_idx)
        self.TradesDataMapper.addMapping(self.TradeActiveWidget, active_idx)
        self.TradesDataMapper.addMapping(self.TradeTimestampEdit, self.TradesModel.fieldIndex("timestamp"))
        self.TradesDataMapper.addMapping(self.TradeSettlementEdit, self.TradesModel.fieldIndex("settlement"))
        self.TradesDataMapper.addMapping(self.TradeNumberEdit, self.TradesModel.fieldIndex("number"))
        self.TradesDataMapper.addMapping(self.TradePriceEdit, self.TradesModel.fieldIndex("price"))
        self.TradesDataMapper.addMapping(self.TradeQtyEdit, self.TradesModel.fieldIndex("qty"))
        self.TradesDataMapper.addMapping(self.TradeCouponEdit, self.TradesModel.fieldIndex("coupon"))
        self.TradesDataMapper.addMapping(self.TradeBrokerFeeEdit, self.TradesModel.fieldIndex("fee_broker"))
        self.TradesDataMapper.addMapping(self.TradeExchangeFeeEdit, self.TradesModel.fieldIndex("fee_exchange"))

        ###############################################################################################
        # CONFIGURE DIVIDENDS TAB                                                                     #
        ###############################################################################################
        self.DividendAccountWidget.init_DB(self.db)
        self.DividendActiveWidget.init_DB(self.db)

        self.DividendsModel = QSqlRelationalTableModel(db=self.db)
        self.DividendsModel.setTable("dividends")
        self.DividendsModel.setEditStrategy(QSqlTableModel.OnManualSubmit)
        account_idx = self.DividendsModel.fieldIndex("account_id")
        active_idx = self.DividendsModel.fieldIndex("active_id")
        self.DividendsModel.select()
        self.DividendsDataMapper = QDataWidgetMapper(self)
        self.DividendsDataMapper.setModel(self.DividendsModel)
        self.DividendsDataMapper.setSubmitPolicy(QDataWidgetMapper.ManualSubmit)
        self.DividendsDataMapper.setItemDelegate(DividendSqlDelegate(self.DividendsDataMapper))
        self.DividendsDataMapper.addMapping(self.DividendAccountWidget, account_idx)
        self.DividendsDataMapper.addMapping(self.DividendActiveWidget, active_idx)
        self.DividendsDataMapper.addMapping(self.DividendTimestampEdit, self.DividendsModel.fieldIndex("timestamp"))
        self.DividendsDataMapper.addMapping(self.DividendNumberEdit, self.DividendsModel.fieldIndex("number"))
        self.DividendsDataMapper.addMapping(self.DividendSumEdit, self.DividendsModel.fieldIndex("sum"))
        self.DividendsDataMapper.addMapping(self.DividendSumDescription, self.DividendsModel.fieldIndex("note"))
        self.DividendsDataMapper.addMapping(self.DividendTaxEdit, self.DividendsModel.fieldIndex("sum_tax"))
        self.DividendsDataMapper.addMapping(self.DividendTaxDescription, self.DividendsModel.fieldIndex("note_tax"))

        ###############################################################################################
        # CONFIGURE ACTIONS                                                                           #
        ###############################################################################################
        # MENU ACTIONS
        self.actionExit.triggered.connect(qApp.quit)
        self.action_Import.triggered.connect(self.ImportFrom1C)
        self.action_Re_build_Ledger.triggered.connect(self.ShowRebuildDialog)
        #INTERFACE ACTIONS
        self.MainTabs.currentChanged.connect(self.OnMainTabChange)
        self.BalanceDate.dateChanged.connect(self.onBalanceDateChange)
        self.CurrencyCombo.currentIndexChanged.connect(self.OnBalanceCurrencyChange)
        self.ShowInactiveCheckBox.stateChanged.connect(self.OnBalanceInactiveChange)
        self.DateRangeCombo.currentIndexChanged.connect(self.OnOperationsRangeChange)
        # OPERATIONS TABLE ACTIONS
        self.OperationsTableView.selectionModel().selectionChanged.connect(self.OnOperationChange)
        self.ChooseAccountBtn.clicked.connect(self.OnAccountChange)
        # DIVIDEND TAB ACTIONS
        self.DividendCommitBtn.clicked.connect(self.OnDividendCommit)
        self.DividendAppendBtn.clicked.connect(self.OnDividendAppend)
        self.DividendRemoveBtn.clicked.connect(self.OnDividendRemove)

        self.OperationsTableView.selectRow(0)

    def ImportFrom1C(self):
        import_directory = QFileDialog.getExistingDirectory(self, "Select directory with data to import")
        if import_directory:
            import_directory = import_directory + "/"
            print("Import 1C data from: ", import_directory)
            print("Import 1C data to:   ", DB_PATH)
            self.db.close()
            import_1c(DB_PATH, import_directory)
            self.db.open()

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
            self.StatusBar.showMessage("Balances and Transactions")
        elif tab_index == 1:
            self.StatusBar.showMessage("Other staff will be here")

    @Slot()
    def onBalanceDateChange(self, new_date):
        self.balance_date = self.BalanceDate.dateTime().toSecsSinceEpoch()
        self.UpdateBalances()

    @Slot()
    def OnBalanceCurrencyChange(self, currency_index):
        self.balance_currency = self.CurrencyNameModel.record(currency_index).value("id")
        self.BalancesModel.setHeaderData(5, Qt.Horizontal, "Balance, " + self.CurrencyNameModel.record(currency_index).value("name"))
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

    @Slot()
    def OnOperationChange(self, selected, deselected):
        idx = selected.indexes()
        selected_row = idx[0].row()
        operation_type = self.OperationsModel.record(selected_row).value(self.OperationsModel.fieldIndex("type"))
        operation_id = self.OperationsModel.record(selected_row).value(self.OperationsModel.fieldIndex("id"))
        transfer_id = self.OperationsModel.record(selected_row).value(self.OperationsModel.fieldIndex("qty_trid"))
        if (operation_type == 1):
            self.ActionsModel.setFilter(f"actions.id = {operation_id}")
            self.ActionsDataMapper.setCurrentModelIndex(self.ActionsDataMapper.model().index(0, 0))
            if (transfer_id == 0):    # Income / Spending
                self.OperationsTabs.setCurrentIndex(0)
                self.ActionDetailsModel.setFilter(f"action_details.pid = {operation_id}")
            else:                     # Transfer
                self.OperationsTabs.setCurrentIndex(3)

        elif (operation_type == 2):   # Dividend
            self.OperationsTabs.setCurrentIndex(2)
            self.DividendsModel.setFilter("dividends.id = {}".format(operation_id))
            self.DividendsDataMapper.setCurrentModelIndex(self.DividendsDataMapper.model().index(0, 0))
        elif (operation_type == 3):   # Trade
            self.OperationsTabs.setCurrentIndex(1)
            self.TradesModel.setFilter("trades.id = {}".format(operation_id))
            self.TradesDataMapper.setCurrentModelIndex(self.TradesDataMapper.model().index(0,0))
        else:
            print("Unknown operation type", operation_type)

    def SetOperationsFilter(self):
        operations_filter = ""
        if (self.operations_since_timestamp > 0):
            operations_filter = "all_operations.timestamp >= {}".format(self.operations_since_timestamp)

        if self.ChooseAccountBtn.account_id != 0:
            if operations_filter == "":
                operations_filter = "all_operations.account_id = {}".format(self.ChooseAccountBtn.account_id)
            else:
                operations_filter = operations_filter + " AND all_operations.account_id = {}".format(self.ChooseAccountBtn.account_id)
        self.OperationsModel.setFilter(operations_filter)

    @Slot()
    def OnOperationsRangeChange(self, range_index):
        if (range_index == 0): # last week
            self.operations_since_timestamp = QtCore.QDateTime.currentDateTime().toSecsSinceEpoch() - 604800
        elif (range_index == 1): # last month
            self.operations_since_timestamp = QtCore.QDateTime.currentDateTime().toSecsSinceEpoch() - 2678400
        elif (range_index == 2): # last half-year
            self.operations_since_timestamp = QtCore.QDateTime.currentDateTime().toSecsSinceEpoch() - 15811200
        elif (range_index == 3): # last year
            self.operations_since_timestamp = QtCore.QDateTime.currentDateTime().toSecsSinceEpoch() - 31536000
        else:
            self.operations_since_timestamp = 0
        self.SetOperationsFilter()

    @Slot()
    def OnAccountChange(self):
        self.SetOperationsFilter()

    @Slot()
    def OnDividendCommit(self):
        self.DividendsDataMapper.submit()
        self.DividendsModel.submitAll()
        self.OperationsModel.select()

    @Slot()
    def OnDividendAppend(self):
        row = self.DividendsDataMapper.currentIndex()
        self.DividendsDataMapper.submit()
        self.DividendsModel.insertRow(row)
        self.DividendsDataMapper.setCurrentIndex(row)

    @Slot()
    def OnDividendRemove(self):
        row = self.DividendsDataMapper.currentIndex()
        self.DividendsDataMapper.submit()
        self.DividendsModel.removeRow(row)
        self.DividendsDataMapper.submit()
        self.DividendsModel.submitAll()
        self.OperationsModel.select()
