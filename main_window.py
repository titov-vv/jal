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
from operation_delegate import OperationsTimestampDelegate
from dividend_delegate import DividendSqlDelegate

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

        self.OperationsModel = QSqlTableModel(db=self.db)
        self.OperationsModel.setTable("all_operations")
        self.OperationsModel.select()
        self.OperationsTableView.setModel(self.OperationsModel)
        self.OperationsTableView.setItemDelegateForColumn(2, OperationsTimestampDelegate(self.OperationsTableView))
        self.OperationsTableView.setSelectionBehavior(QAbstractItemView.SelectRows)  # To select only 1 row
        self.OperationsTableView.setSelectionMode(QAbstractItemView.SingleSelection)
        self.OperationsTableView.setColumnHidden(1, True)
        self.OperationsTableView.setColumnHidden(3, True)
        self.OperationsTableView.setColumnHidden(7, True)
        self.OperationsTableView.verticalHeader().setDefaultSectionSize(21)
        self.OperationsTableView.verticalHeader().setVisible(False)
        #self.OperationsTableView.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.OperationsTableView.show()

        # self.TradesModel = QSqlRelationalTableModel(db=self.db)
        # self.TradesModel.setTable("trades")
        # self.TradesModel.setEditStrategy(QSqlTableModel.OnManualSubmit)
        # account_idx = self.TradesModel.fieldIndex("account_id")
        # self.TradesModel.setRelation(account_idx, QSqlRelation("accounts", "id", "name"))
        # self.TradesModel.select()
        # self.TradeAccountCombo.setModel(self.TradesModel.relationModel(account_idx))
        # self.TradeAccountCombo.setModelColumn(self.TradesModel.relationModel(account_idx).fieldIndex("name"))
        #
        # self.trades_mapper = QDataWidgetMapper(self)
        # self.trades_mapper.setModel(self.TradesModel)
        # self.trades_mapper.addMapping(self.TradeAccountCombo, account_idx)
        # self.trades_mapper.addMapping(self.TradeNumberEdit, self.TradesModel.fieldIndex("number"))

        # self.ActivesModel = QSqlTableModel(db=self.db)
        # self.ActivesModel.setTable("actives")
        # self.ActivesModel.setEditStrategy(QSqlTableModel.OnManualSubmit)
        # self.ActivesModel.select()
        # self.ActivesModel.fetchMore()
        # self.ActivesMapper = QDataWidgetMapper(self)
        # self.ActivesMapper.setModel(self.ActivesModel)
        # self.ActivesMapper.setSubmitPolicy(QDataWidgetMapper.ManualSubmit)
        # #label_property_name = QByteArray()
        # #label_property_name.resize(4)
        # #label_property_name.setRawData("text", 4)
        # self.ActivesMapper.addMapping(self.DividendActiveLbl, self.ActivesModel.fieldIndex("full_name"))#, label_property_name)

        ###############################################################################################
        # CONFIGURE DIVIDENDS TAB                                                                     #
        ###############################################################################################
        self.DividendAccountWidget.init_DB(self.db)

        self.DividendsModel = QSqlRelationalTableModel(db=self.db)
        self.DividendsModel.setTable("dividends")
        self.DividendsModel.setEditStrategy(QSqlTableModel.OnManualSubmit)
        account_idx = self.DividendsModel.fieldIndex("account_id")
        active_idx = self.DividendsModel.fieldIndex("active_id")
        #self.DividendsModel.setRelation(account_idx, QSqlRelation("accounts", "id", "name"))
        self.DividendsModel.setRelation(active_idx, QSqlRelation("actives", "id", "name"))
        self.DividendsModel.select()
        #self.DividendAccountCombo.setModel(self.DividendsModel.relationModel(account_idx))
        #self.DividendAccountCombo.setModelColumn(self.DividendsModel.relationModel(account_idx).fieldIndex("name"))
        self.DividendActiveCombo.setModel(self.DividendsModel.relationModel(active_idx))
        self.DividendActiveCombo.setModelColumn(self.DividendsModel.relationModel(active_idx).fieldIndex("name"))

        self.DividendsModel.relationModel(active_idx).fetchMore()

        self.dividend_mapper = QDataWidgetMapper(self)
        self.dividend_mapper.setModel(self.DividendsModel)
        self.dividend_mapper.setSubmitPolicy(QDataWidgetMapper.ManualSubmit)
        self.dividend_mapper.setItemDelegate(DividendSqlDelegate(self.dividend_mapper))
        self.dividend_mapper.addMapping(self.DividendAccountCombo, account_idx)
        id_property_name = QByteArray()
        id_property_name.resize(10)
        id_property_name.setRawData("account_id", 10)
        self.dividend_mapper.addMapping(self.DividendAccountWidget, account_idx, id_property_name) #"account_id")
        #self.dividend_mapper.addMapping(self.DividendActiveCombo, active_idx)
        self.dividend_mapper.addMapping(self.DividendTimestampEdit, self.DividendsModel.fieldIndex("timestamp"))
        self.dividend_mapper.addMapping(self.DividendNumberEdit, self.DividendsModel.fieldIndex("number"))
        self.dividend_mapper.addMapping(self.DividendSumEdit, self.DividendsModel.fieldIndex("sum"))
        self.dividend_mapper.addMapping(self.DividendSumDescription, self.DividendsModel.fieldIndex("note"))
        self.dividend_mapper.addMapping(self.DividendTaxEdit, self.DividendsModel.fieldIndex("sum_tax"))
        self.dividend_mapper.addMapping(self.DividendTaxDescription, self.DividendsModel.fieldIndex("note_tax"))

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
        # DIVIDEND TAB ACTIONS
        self.DividendCommitBtn.clicked.connect(self.OnDividendCommit)
        self.DividendAppendBtn.clicked.connect(self.OnDividendAppend)
        self.DividendRemoveBtn.clicked.connect(self.OnDividendRemove)

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

    @Slot()
    def OnOperationChange(self, selected, deselected):
        idx = selected.indexes()
        selected_row = idx[0].row()
        operation_type = self.OperationsModel.record(selected_row).value(0)
        operation_id = self.OperationsModel.record(selected_row).value(1)
        if (operation_type == 1):     # Income / Spending
            self.OperationsTabs.setCurrentIndex(0)
        elif (operation_type == 2):   # Dividend
            self.OperationsTabs.setCurrentIndex(2)
            self.DividendsModel.setFilter("dividends.id = {}".format(operation_id))
            self.dividend_mapper.setCurrentModelIndex(self.dividend_mapper.model().index(0, 0))
        elif (operation_type == 3):   # Trade
            self.OperationsTabs.setCurrentIndex(1)
            self.TradesModel.setFilter("trades.id = {}".format(operation_id))
            self.trades_mapper.setCurrentModelIndex(self.trades_mapper.model().index(0,0))
        else:
            print("Unknown operation type", operation_type)

    @Slot()
    def OnOperationsRangeChange(self, range_index):
        if (range_index == 0): # last week
            since_timestamp = QtCore.QDateTime.currentDateTime().toSecsSinceEpoch() - 604800
        elif (range_index == 1): # last month
            since_timestamp = QtCore.QDateTime.currentDateTime().toSecsSinceEpoch() - 2678400
        elif (range_index == 2): # last half-year
            since_timestamp = QtCore.QDateTime.currentDateTime().toSecsSinceEpoch() - 15811200
        elif (range_index == 3): # last year
            since_timestamp = QtCore.QDateTime.currentDateTime().toSecsSinceEpoch() - 31536000
        else:
            since_timestamp = 0
        if (since_timestamp > 0):
            self.OperationsModel.setFilter("all_operations.timestamp >= {}".format(since_timestamp))
        else:
            self.OperationsModel.setFilter("")

    @Slot()
    def OnDividendCommit(self):
        self.dividend_mapper.submit()
        self.DividendsModel.submitAll()
        self.OperationsModel.select()

    @Slot()
    def OnDividendAppend(self):
        row = self.dividend_mapper.currentIndex()
        self.dividend_mapper.submit()
        self.DividendsModel.insertRow(row)
        self.dividend_mapper.setCurrentIndex(row)

    @Slot()
    def OnDividendRemove(self):
        row = self.dividend_mapper.currentIndex()
        self.dividend_mapper.submit()
        self.DividendsModel.removeRow(row)
        self.dividend_mapper.submit()
        self.DividendsModel.submitAll()
        self.OperationsModel.select()
