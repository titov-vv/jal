from PySide2.QtWidgets import QMainWindow, QFileDialog, QAbstractItemView, QDataWidgetMapper, QHeaderView, QMenu, QMessageBox, QAction
from PySide2.QtSql import QSql, QSqlDatabase, QSqlQuery, QSqlQueryModel, QSqlTableModel, QSqlRelationalTableModel, QSqlRelation
from PySide2.QtCore import Slot, QMetaObject
from PySide2.QtGui import QDoubleValidator
from PySide2 import QtCore
from UI.ui_main_window import Ui_LedgerMainWindow
from ledger import Ledger
from bulk_db import importFrom1C, loadDbFromSQL
from rebuild_window import RebuildDialog
from balance_delegate import BalanceDelegate
from operation_delegate import *
from dividend_delegate import DividendSqlDelegate
from trade_delegate import TradeSqlDelegate, OptionGroup
from transfer_delegate import TransferSqlDelegate
from action_delegate import ActionDelegate, ActionDetailDelegate
from CustomUI.account_select import AcountTypeEditDlg, AccountChoiceDlg
from CustomUI.active_select import ActiveChoiceDlg
from CustomUI.peer_select import PeerChoiceDlg
from CustomUI.category_select import CategoryChoiceDlg

class MainWindow(QMainWindow, Ui_LedgerMainWindow):
    def __init__(self):
        QMainWindow.__init__(self, None)
        self.setupUi(self)

        self.db = QSqlDatabase.addDatabase("QSQLITE")
        self.db.setDatabaseName(DB_PATH)
        self.db.open()
        tables = self.db.tables(QSql.Tables)
        if tables == []:
            if QMessageBox().warning(self, self.tr("Database is empty"),
                                     self.tr("Would you like to build it from SQL-script?"),
                                     QMessageBox.Yes, QMessageBox.No) == QMessageBox.Yes:
                self.InitDB()
            self.db.close()
            QMetaObject.invokeMethod(self, "close", Qt.QueuedConnection)
            return
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
        self.doubleValidate2 = QDoubleValidator(decimals=2)
        self.doubleValidate6 = QDoubleValidator(decimals=6)
        widthForAmountEdit = self.fontMetrics().width("888888888.88") * 1.5
        widthForTimestampEdit = self.fontMetrics().width("00/00/0000 00:00:00") * 1.5

        self.ActionTimestampEdit.setFixedWidth(widthForTimestampEdit)
        self.AddActionDetail.setFixedWidth(widthForTimestampEdit * 0.25)
        self.CopyActionDetail.setFixedWidth(widthForTimestampEdit * 0.25)
        self.RemoveActionDetail.setFixedWidth(widthForTimestampEdit * 0.25)

        self.DividendTimestampEdit.setFixedWidth(widthForTimestampEdit)
        self.DividendNumberEdit.setFixedWidth(widthForTimestampEdit)
        self.DividendSumEdit.setFixedWidth(widthForAmountEdit)
        self.DividendTaxEdit.setFixedWidth(widthForAmountEdit)

        self.TradeTimestampEdit.setFixedWidth(widthForTimestampEdit)
        self.TradeNumberEdit.setFixedWidth(widthForTimestampEdit)
        self.TradePriceEdit.setFixedWidth(widthForAmountEdit)
        self.TradeQtyEdit.setFixedWidth(widthForAmountEdit)
        self.TradeCouponEdit.setFixedWidth(widthForAmountEdit)
        self.TradeBrokerFeeEdit.setFixedWidth(widthForAmountEdit)
        self.TradeExchangeFeeEdit.setFixedWidth(widthForAmountEdit)

        self.TransferFromAmount.setFixedWidth(widthForAmountEdit)
        self.TransferToAmount.setFixedWidth(widthForAmountEdit)
        self.TransferFeeAmount.setFixedWidth(widthForAmountEdit)
        self.TransferFromTimestamp.setFixedWidth(widthForTimestampEdit)
        self.TransferToTimestamp.setFixedWidth(widthForTimestampEdit)
        self.TransferFeeTimestamp.setFixedWidth(widthForTimestampEdit)

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
        self.BalancesModel.setHeaderData(self.BalancesModel.fieldIndex("account_name"), Qt.Horizontal, "Account")
        self.BalancesModel.setHeaderData(self.BalancesModel.fieldIndex("balance"), Qt.Horizontal, "Balance")
        self.BalancesModel.setHeaderData(self.BalancesModel.fieldIndex("currency_name"), Qt.Horizontal, "")
        self.BalancesModel.setHeaderData(self.BalancesModel.fieldIndex("balance_adj"), Qt.Horizontal, "Balance, RUB")
        self.BalancesModel.select()
        self.BalancesTableView.setModel(self.BalancesModel)
        self.BalancesTableView.setItemDelegate(BalanceDelegate(self.BalancesTableView))
        self.BalancesTableView.setColumnHidden(self.BalancesModel.fieldIndex("level1"), True)
        self.BalancesTableView.setColumnHidden(self.BalancesModel.fieldIndex("level2"), True)
        self.BalancesTableView.setColumnHidden(self.BalancesModel.fieldIndex("days_unreconciled"), True)
        self.BalancesTableView.setColumnHidden(self.BalancesModel.fieldIndex("active"), True)
        self.BalancesTableView.setColumnWidth(self.BalancesModel.fieldIndex("account_name"), 100)
        self.BalancesTableView.setColumnWidth(self.BalancesModel.fieldIndex("balance"), 100)
        self.BalancesTableView.setColumnWidth(self.BalancesModel.fieldIndex("currency_name"), 40)
        self.BalancesTableView.setColumnWidth(self.BalancesModel.fieldIndex("balance_adj"), 100)
        self.BalancesTableView.horizontalHeader().setSectionResizeMode(self.BalancesModel.fieldIndex("account_name"), QHeaderView.Stretch)
        font = self.BalancesTableView.horizontalHeader().font()
        font.setBold(True)
        self.BalancesTableView.horizontalHeader().setFont(font)
        self.BalancesTableView.show()

        self.HoldingsModel = QSqlTableModel(db=self.db)
        self.HoldingsModel.setTable("holdings")
        self.HoldingsModel.select()
        self.HoldingsTableView.setModel(self.HoldingsModel)
        font = self.HoldingsTableView.horizontalHeader().font()
        font.setBold(True)
        self.HoldingsTableView.horizontalHeader().setFont(font)
        self.HoldingsTableView.show()

        self.ChooseAccountBtn.init_DB(self.db)

        self.OperationsModel = QSqlTableModel(db=self.db)
        self.OperationsModel.setTable("all_operations")
        self.OperationsModel.setHeaderData(self.OperationsModel.fieldIndex("type"), Qt.Horizontal, " ")
        self.OperationsModel.setHeaderData(self.OperationsModel.fieldIndex("timestamp"), Qt.Horizontal, "Timestamp")
        self.OperationsModel.setHeaderData(self.OperationsModel.fieldIndex("account"), Qt.Horizontal, "Account")
        self.OperationsModel.setHeaderData(self.OperationsModel.fieldIndex("note"), Qt.Horizontal, "Notes")
        self.OperationsModel.setHeaderData(self.OperationsModel.fieldIndex("amount"), Qt.Horizontal, "Amount")
        self.OperationsModel.setHeaderData(self.OperationsModel.fieldIndex("t_amount"), Qt.Horizontal, "Balance")
        self.OperationsModel.setHeaderData(self.OperationsModel.fieldIndex("currency"), Qt.Horizontal, "Currency")
        self.OperationsModel.select()
        self.OperationsTableView.setModel(self.OperationsModel)
        self.OperationsTableView.setItemDelegateForColumn(self.OperationsModel.fieldIndex("type"), OperationsTypeDelegate(self.OperationsTableView))
        self.OperationsTableView.setItemDelegateForColumn(self.OperationsModel.fieldIndex("timestamp"), OperationsTimestampDelegate(self.OperationsTableView))
        self.OperationsTableView.setItemDelegateForColumn(self.OperationsModel.fieldIndex("account"), OperationsAccountDelegate(self.OperationsTableView))
        self.OperationsTableView.setItemDelegateForColumn(self.OperationsModel.fieldIndex("note"), OperationsNotesDelegate(self.OperationsTableView))
        self.OperationsTableView.setItemDelegateForColumn(self.OperationsModel.fieldIndex("amount"), OperationsAmountDelegate(self.OperationsTableView))
        self.OperationsTableView.setItemDelegateForColumn(self.OperationsModel.fieldIndex("t_amount"), OperationsTotalsDelegate(self.OperationsTableView))
        self.OperationsTableView.setItemDelegateForColumn(self.OperationsModel.fieldIndex("currency"), OperationsCurrencyDelegate(self.OperationsTableView))
        self.OperationsTableView.setSelectionBehavior(QAbstractItemView.SelectRows)  # To select only 1 row
        self.OperationsTableView.setSelectionMode(QAbstractItemView.SingleSelection)
        self.OperationsTableView.setColumnHidden(self.OperationsModel.fieldIndex("id"), True)
        self.OperationsTableView.setColumnHidden(self.OperationsModel.fieldIndex("account_id"), True)
        self.OperationsTableView.setColumnHidden(self.OperationsModel.fieldIndex("num_peer"), True)
        self.OperationsTableView.setColumnHidden(self.OperationsModel.fieldIndex("active_id"), True)
        self.OperationsTableView.setColumnHidden(self.OperationsModel.fieldIndex("active"), True)
        self.OperationsTableView.setColumnHidden(self.OperationsModel.fieldIndex("active_name"), True)
        self.OperationsTableView.setColumnHidden(self.OperationsModel.fieldIndex("note2"), True)
        self.OperationsTableView.setColumnHidden(self.OperationsModel.fieldIndex("qty_trid"), True)
        self.OperationsTableView.setColumnHidden(self.OperationsModel.fieldIndex("price"), True)
        self.OperationsTableView.setColumnHidden(self.OperationsModel.fieldIndex("fee_tax"), True)
        self.OperationsTableView.setColumnHidden(self.OperationsModel.fieldIndex("t_qty"), True)
        self.OperationsTableView.setColumnHidden(self.OperationsModel.fieldIndex("reconciled"), True)
        self.OperationsTableView.setColumnWidth(self.OperationsModel.fieldIndex("type"), 10)
        self.OperationsTableView.setColumnWidth(self.OperationsModel.fieldIndex("timestamp"), widthForTimestampEdit * 0.7)
        self.OperationsTableView.setColumnWidth(self.OperationsModel.fieldIndex("account"), 300)
        self.OperationsTableView.setColumnWidth(self.OperationsModel.fieldIndex("note"), 300)
        self.OperationsTableView.horizontalHeader().setSectionResizeMode(self.OperationsModel.fieldIndex("note"), QHeaderView.Stretch)
        self.OperationsTableView.setContextMenuPolicy(Qt.CustomContextMenu)
        self.OperationsTableView.setWordWrap(False)
        # next line forces usage of sizeHint() from delegate
        self.OperationsTableView.verticalHeader().setMinimumSectionSize(8)
        self.OperationsTableView.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.OperationsTableView.horizontalHeader().setFont(font)
        self.OperationsTableView.show()

        ###############################################################################################
        # CONFIGURE ACTIONS TAB                                                                       #
        ###############################################################################################
        self.ActionAccountWidget.init_DB(self.db)
        self.ActionPeerWidget.init_DB(self.db)

        self.ActionsModel = QSqlRelationalTableModel(db=self.db)
        self.ActionsModel.setTable("actions")
        self.ActionsModel.setEditStrategy(QSqlTableModel.OnManualSubmit)
        account_idx = self.ActionsModel.fieldIndex("account_id")
        peer_idx = self.ActionsModel.fieldIndex("peer_id")
        self.ActionsModel.dataChanged.connect(self.OnOperationDataChanged)
        self.ActionsModel.select()
        self.ActionsDataMapper = QDataWidgetMapper(self)
        self.ActionsDataMapper.setModel(self.ActionsModel)
        self.ActionsDataMapper.setSubmitPolicy(QDataWidgetMapper.AutoSubmit)
        self.ActionsDataMapper.setItemDelegate(ActionDelegate(self.ActionsDataMapper))
        self.ActionsDataMapper.addMapping(self.ActionAccountWidget, account_idx) # if no USER property QByteArray().setRawData("account_id", 10))
        self.ActionAccountWidget.changed.connect(self.ActionsDataMapper.submit)
        self.ActionsDataMapper.addMapping(self.ActionTimestampEdit, self.ActionsModel.fieldIndex("timestamp"))
        self.ActionsDataMapper.addMapping(self.ActionPeerWidget, peer_idx)
        self.ActionPeerWidget.changed.connect(self.ActionsDataMapper.submit)

        self.ActionDetailsModel = QSqlRelationalTableModel(db=self.db)
        self.ActionDetailsModel.setTable("action_details")
        self.ActionDetailsModel.setJoinMode(QSqlRelationalTableModel.LeftJoin)  # in order not to fail on NULL tags
        self.ActionDetailsModel.setEditStrategy(QSqlTableModel.OnManualSubmit)
        category_idx = self.ActionDetailsModel.fieldIndex("category_id")
        self.ActionDetailsModel.setRelation(category_idx, QSqlRelation("categories", "id", "name"))
        tag_idx = self.ActionDetailsModel.fieldIndex("tag_id")
        self.ActionDetailsModel.setRelation(tag_idx, QSqlRelation("tags", "id", "tag"))
        self.ActionDetailsModel.setHeaderData(category_idx, Qt.Horizontal, "Category")
        self.ActionDetailsModel.setHeaderData(tag_idx, Qt.Horizontal, "Tags")
        self.ActionDetailsModel.setHeaderData(self.ActionDetailsModel.fieldIndex("sum"), Qt.Horizontal, "Amount")
        self.ActionDetailsModel.setHeaderData(self.ActionDetailsModel.fieldIndex("alt_sum"), Qt.Horizontal, "Amount *")
        self.ActionDetailsModel.setHeaderData(self.ActionDetailsModel.fieldIndex("note"), Qt.Horizontal, "Note")
        self.ActionDetailsModel.dataChanged.connect(self.OnOperationDataChanged)
        self.ActionDetailsModel.select()
        self.ActionDetailsTableView.setModel(self.ActionDetailsModel)
        self.ActionDetailsTableView.setItemDelegate(ActionDetailDelegate(self.ActionDetailsTableView))
        self.ActionDetailsTableView.setSelectionBehavior(QAbstractItemView.SelectRows)  # To select only 1 row
        self.ActionDetailsTableView.setSelectionMode(QAbstractItemView.SingleSelection)
        self.ActionDetailsTableView.setColumnHidden(0, True)  # id
        self.ActionDetailsTableView.setColumnHidden(1, True)  # pid
        self.ActionDetailsTableView.setColumnWidth(2, 200)  # category
        self.ActionDetailsTableView.setColumnWidth(3, 200)  # tags
        self.ActionDetailsTableView.setColumnWidth(4, 100)  # amount
        self.ActionDetailsTableView.setColumnWidth(5, 100)  # amount *
        self.ActionDetailsTableView.setColumnWidth(6, 400)  # note
        self.ActionDetailsTableView.horizontalHeader().setSectionResizeMode(6, QHeaderView.Stretch)  # make notes to fill all remaining space
        self.ActionDetailsTableView.horizontalHeader().moveSection(6, 2)  # swap note and category columns
        self.ActionDetailsTableView.setColumnWidth(6, 400)
        self.ActionDetailsTableView.show()

        ###############################################################################################
        # CONFIGURE TRADES TAB                                                                        #
        ###############################################################################################
        self.TradeAccountWidget.init_DB(self.db)
        self.TradeActiveWidget.init_DB(self.db)
        self.BS_group = OptionGroup()
        self.BS_group.addButton(self.BuyRadioBtn, 1)
        self.BS_group.addButton(self.SellRadioBtn, -1)

        self.TradesModel = QSqlTableModel(db=self.db)
        self.TradesModel.setTable("trades")
        self.TradesModel.beforeInsert.connect(self.BeforeTradeInsert)
        self.TradesModel.setEditStrategy(QSqlTableModel.OnManualSubmit)
        account_idx = self.TradesModel.fieldIndex("account_id")
        active_idx = self.TradesModel.fieldIndex("active_id")
        self.TradesModel.dataChanged.connect(self.OnOperationDataChanged)
        self.TradesModel.select()
        self.TradesDataMapper = QDataWidgetMapper(self)
        self.TradesDataMapper.setModel(self.TradesModel)
        self.TradesDataMapper.setSubmitPolicy(QDataWidgetMapper.AutoSubmit)
        self.TradesDataMapper.setItemDelegate(TradeSqlDelegate(self.TradesDataMapper))
        self.TradesDataMapper.addMapping(self.TradeAccountWidget, account_idx)
        self.TradeAccountWidget.changed.connect(self.TradesDataMapper.submit)
        self.TradesDataMapper.addMapping(self.TradeActiveWidget, active_idx)
        self.TradeActiveWidget.changed.connect(self.TradesDataMapper.submit)
        self.TradesDataMapper.addMapping(self.TradeTimestampEdit, self.TradesModel.fieldIndex("timestamp"))
        self.TradesDataMapper.addMapping(self.BS_group, self.TradesModel.fieldIndex("type"))
        self.TradesDataMapper.addMapping(self.TradeSettlementEdit, self.TradesModel.fieldIndex("settlement"))
        self.TradesDataMapper.addMapping(self.TradeNumberEdit, self.TradesModel.fieldIndex("number"))
        self.TradesDataMapper.addMapping(self.TradePriceEdit, self.TradesModel.fieldIndex("price"))
        self.TradesDataMapper.addMapping(self.TradeQtyEdit, self.TradesModel.fieldIndex("qty"))
        self.TradesDataMapper.addMapping(self.TradeCouponEdit, self.TradesModel.fieldIndex("coupon"))
        self.TradesDataMapper.addMapping(self.TradeBrokerFeeEdit, self.TradesModel.fieldIndex("fee_broker"))
        self.TradesDataMapper.addMapping(self.TradeExchangeFeeEdit, self.TradesModel.fieldIndex("fee_exchange"))
        self.TradePriceEdit.setValidator(self.doubleValidate6)
        self.TradeQtyEdit.setValidator(self.doubleValidate6)
        self.TradeCouponEdit.setValidator(self.doubleValidate6)
        self.TradeBrokerFeeEdit.setValidator(self.doubleValidate6)
        self.TradeExchangeFeeEdit.setValidator(self.doubleValidate6)

        ###############################################################################################
        # CONFIGURE DIVIDENDS TAB                                                                     #
        ###############################################################################################
        self.DividendAccountWidget.init_DB(self.db)
        self.DividendActiveWidget.init_DB(self.db)

        self.DividendsModel = QSqlTableModel(db=self.db)
        self.DividendsModel.setTable("dividends")
        self.DividendsModel.setEditStrategy(QSqlTableModel.OnManualSubmit)
        account_idx = self.DividendsModel.fieldIndex("account_id")
        active_idx = self.DividendsModel.fieldIndex("active_id")
        self.DividendsModel.dataChanged.connect(self.OnOperationDataChanged)
        self.DividendsModel.select()
        self.DividendsDataMapper = QDataWidgetMapper(self)
        self.DividendsDataMapper.setModel(self.DividendsModel)
        self.DividendsDataMapper.setSubmitPolicy(QDataWidgetMapper.AutoSubmit)
        self.DividendsDataMapper.setItemDelegate(DividendSqlDelegate(self.DividendsDataMapper))
        self.DividendsDataMapper.addMapping(self.DividendAccountWidget, account_idx)
        self.DividendAccountWidget.changed.connect(self.DividendsDataMapper.submit)
        self.DividendsDataMapper.addMapping(self.DividendActiveWidget, active_idx)
        self.DividendActiveWidget.changed.connect(self.DividendsDataMapper.submit)
        self.DividendsDataMapper.addMapping(self.DividendTimestampEdit, self.DividendsModel.fieldIndex("timestamp"))
        self.DividendsDataMapper.addMapping(self.DividendNumberEdit, self.DividendsModel.fieldIndex("number"))
        self.DividendsDataMapper.addMapping(self.DividendSumEdit, self.DividendsModel.fieldIndex("sum"))
        self.DividendsDataMapper.addMapping(self.DividendSumDescription, self.DividendsModel.fieldIndex("note"))
        self.DividendsDataMapper.addMapping(self.DividendTaxEdit, self.DividendsModel.fieldIndex("sum_tax"))
        self.DividendsDataMapper.addMapping(self.DividendTaxDescription, self.DividendsModel.fieldIndex("note_tax"))
        self.DividendSumEdit.setValidator(self.doubleValidate2)
        self.DividendTaxEdit.setValidator(self.doubleValidate2)

        ###############################################################################################
        # CONFIGURE TRANSFERS TAB                                                                     #
        ###############################################################################################
        self.TransferFromAccountWidget.init_DB(self.db)
        self.TransferToAccountWidget.init_DB(self.db)
        self.TransferFeeAccountWidget.init_DB(self.db)

        self.TransfersModel = QSqlTableModel(db=self.db)
        self.TransfersModel.setTable("transfers_combined")
        self.TransfersModel.setEditStrategy(QSqlTableModel.OnManualSubmit)
        from_idx = self.TransfersModel.fieldIndex("from_acc_id")
        to_idx = self.TransfersModel.fieldIndex("to_acc_id")
        fee_idx = self.TransfersModel.fieldIndex("fee_acc_id")
        self.TransfersModel.dataChanged.connect(self.OnOperationDataChanged)
        self.TransfersModel.select()
        self.TransfersDataMapper = QDataWidgetMapper(self)
        self.TransfersDataMapper.setModel(self.TransfersModel)
        self.TransfersDataMapper.setSubmitPolicy(QDataWidgetMapper.AutoSubmit)
        self.TransfersDataMapper.setItemDelegate(TransferSqlDelegate(self.TransfersDataMapper))
        self.TransfersDataMapper.addMapping(self.TransferFromAccountWidget, from_idx)
        self.TransferFromAccountWidget.changed.connect(self.TransfersDataMapper.submit)
        self.TransfersDataMapper.addMapping(self.TransferToAccountWidget, to_idx)
        self.TransferToAccountWidget.changed.connect(self.TransfersDataMapper.submit)
        self.TransfersDataMapper.addMapping(self.TransferFeeAccountWidget, fee_idx)
        self.TransferFeeAccountWidget.changed.connect(self.TransfersDataMapper.submit)
        self.TransfersDataMapper.addMapping(self.TransferFromTimestamp, self.TransfersModel.fieldIndex("from_timestamp"))
        self.TransfersDataMapper.addMapping(self.TransferToTimestamp, self.TransfersModel.fieldIndex("to_timestamp"))
        self.TransfersDataMapper.addMapping(self.TransferFeeTimestamp, self.TransfersModel.fieldIndex("fee_timestamp"))
        self.TransfersDataMapper.addMapping(self.TransferFromAmount, self.TransfersModel.fieldIndex("from_amount"))
        self.TransfersDataMapper.addMapping(self.TransferToAmount, self.TransfersModel.fieldIndex("to_amount"))
        self.TransfersDataMapper.addMapping(self.TransferFeeAmount, self.TransfersModel.fieldIndex("fee_amount"))
        self.TransfersDataMapper.addMapping(self.TransferNote, self.TransfersModel.fieldIndex("note"))
        self.TransferFromAmount.setValidator(self.doubleValidate2)
        self.TransferToAmount.setValidator(self.doubleValidate2)
        self.TransferFeeAmount.setValidator(self.doubleValidate2)

        ###############################################################################################
        # CONFIGURE ACTIONS                                                                           #
        ###############################################################################################
        # MENU ACTIONS
        self.actionExit.triggered.connect(qApp.quit)
        self.action_Import.triggered.connect(self.ImportFrom1C)
        self.action_Re_build_Ledger.triggered.connect(self.ShowRebuildDialog)
        self.actionInitDB.triggered.connect(self.InitDB)
        self.actionAccountTypes.triggered.connect(self.EditAccountTypes)
        self.actionAccounts.triggered.connect(self.EditAccounts)
        self.actionActives.triggered.connect(self.EditActives)
        self.actionPeers.triggered.connect(self.EditPeers)
        self.actionCategories.triggered.connect(self.EditCategories)
        # INTERFACE ACTIONS
        self.MainTabs.currentChanged.connect(self.OnMainTabChange)
        self.BalanceDate.dateChanged.connect(self.onBalanceDateChange)
        self.CurrencyCombo.currentIndexChanged.connect(self.OnBalanceCurrencyChange)
        self.ShowInactiveCheckBox.stateChanged.connect(self.OnBalanceInactiveChange)
        self.DateRangeCombo.currentIndexChanged.connect(self.OnOperationsRangeChange)
        # OPERATIONS TABLE ACTIONS
        self.OperationsTableView.selectionModel().selectionChanged.connect(self.OnOperationChange)
        self.OperationsTableView.customContextMenuRequested.connect(self.OnOperationsContextMenu)
        self.ChooseAccountBtn.clicked.connect(self.OnAccountChange)
        # OPERATIONS ACTIONS
        self.AddActionDetail.clicked.connect(self.AddDetail)
        self.RemoveActionDetail.clicked.connect(self.RemoveDetail)
        self.NewOperationMenu = QMenu()
        self.NewOperationMenu.addAction('Income / Spending', self.CreateNewAction)
        self.NewOperationMenu.addAction('Transfer', self.CreateNewTransfer)
        self.NewOperationMenu.addAction('Buy / Sell', self.CreateNewTrade)
        self.NewOperationMenu.addAction('Dividend', self.CreateNewDividend)
        self.NewOperationBtn.setMenu(self.NewOperationMenu)
        self.DeleteOperationBtn.clicked.connect(self.DeleteOperation)
        self.CopyOperationBtn.clicked.connect(self.CopyOperation)
        self.SaveOperationBtn.clicked.connect(self.SaveOperation)
        self.RevertOperationBtn.clicked.connect(self.RevertOperation)
        # ACTIVES ACTIONS
        self.ActivesRefreshBtn.clicked.connect(self.UpdateActives)

        self.OperationsTableView.selectRow(0)
        self.OnOperationsRangeChange(0)

    def ImportFrom1C(self):
        import_directory = QFileDialog.getExistingDirectory(self, "Select directory with data to import")
        if import_directory:
            import_directory = import_directory + "/"
            self.db.close()
            importFrom1C(DB_PATH, import_directory)
            self.db.open()

    def InitDB(self):
        init_script, _filter = QFileDialog.getOpenFileName(self, self.tr("Select init-script"), ".",  self.tr("SQL scripts (*.sql)"))
        if init_script:
            self.db.close()
            loadDbFromSQL(DB_PATH, init_script)
            QMessageBox().information(self, self.tr("Database initialized"),
                                  self.tr("Database have been initialized.\n"
                                          "You need to restart the application.\n"
                                          "Application terminates now."),
                                  QMessageBox.Ok)

    def ShowRebuildDialog(self):
        query = QSqlQuery(self.db)
        query.exec_("SELECT ledger_frontier FROM frontier")
        query.next()
        current_frontier = query.value(0)
        if (current_frontier == ''):
            current_frontier = 0

        rebuild_dialog = RebuildDialog(current_frontier)
        rebuild_dialog.setGeometry(self.x()+64, self.y()+64, rebuild_dialog.width(), rebuild_dialog.height())
        if rebuild_dialog.exec_():
            rebuild_date = rebuild_dialog.getTimestamp()
            self.ledger.MakeFromTimestamp(rebuild_date)

    @Slot()
    def OnMainTabChange(self, tab_index):
        if tab_index == 0:
            self.StatusBar.showMessage("Balances and Transactions")
        elif tab_index == 1:
            self.StatusBar.showMessage("Actives report")
            self.UpdateActives()

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
        self.CheckForNotSavedData()

        ##################################################################
        # UPDATE VIEW FOR NEW SELECTED TRANSACTION                       #
        ##################################################################
        idx = selected.indexes()
        if idx:
            selected_row = idx[0].row()
            operation_type = self.OperationsModel.record(selected_row).value(self.OperationsModel.fieldIndex("type"))
            operation_id = self.OperationsModel.record(selected_row).value(self.OperationsModel.fieldIndex("id"))
            if (operation_type == TRANSACTION_ACTION):
                self.ActionsModel.setFilter(f"actions.id = {operation_id}")
                self.ActionsDataMapper.setCurrentModelIndex(self.ActionsDataMapper.model().index(0, 0))
                self.OperationsTabs.setCurrentIndex(TAB_ACTION)
                self.ActionDetailsModel.setFilter(f"action_details.pid = {operation_id}")
            elif (operation_type == TRANSACTION_DIVIDEND):
                self.OperationsTabs.setCurrentIndex(TAB_DIVIDEND)
                self.DividendsModel.setFilter("dividends.id = {}".format(operation_id))
                self.DividendsDataMapper.setCurrentModelIndex(self.DividendsDataMapper.model().index(0, 0))
            elif (operation_type == TRANSACTION_TRADE):
                self.OperationsTabs.setCurrentIndex(TAB_TRADE)
                self.TradesModel.setFilter("trades.id = {}".format(operation_id))
                self.TradesDataMapper.setCurrentModelIndex(self.TradesDataMapper.model().index(0,0))
            elif (operation_type == TRANSACTION_TRANSFER):
                self.OperationsTabs.setCurrentIndex(TAB_TRANSFER)
                self.TransfersModel.setFilter(f"transfers_combined.id = {operation_id}")
                self.TransfersDataMapper.setCurrentModelIndex(self.TransfersDataMapper.model().index(0, 0))
            else:
                assert False

    @Slot()
    def OnOperationsContextMenu(self, pos):
        self.current_index = self.OperationsTableView.indexAt(pos)
        contextMenu = QMenu(self)
        actionReconcile = QAction(text="Reconcile", parent=self)
        actionReconcile.triggered.connect(self.OnReconcile)
        actionCopy = QAction(text="Copy", parent=self)
        actionCopy.triggered.connect(self.CopyOperation)
        actionDelete = QAction(text="Delete", parent=self)
        actionDelete.triggered.connect(self.DeleteOperation)
        contextMenu.addAction(actionReconcile)
        contextMenu.addSeparator()
        contextMenu.addAction(actionCopy)
        contextMenu.addAction(actionDelete)
        contextMenu.popup(self.OperationsTableView.viewport().mapToGlobal(pos))

    @Slot()
    def OnReconcile(self):
        model = self.current_index.model()
        timestamp = model.data(model.index(self.current_index.row(), 2), Qt.DisplayRole)
        account_id = model.data(model.index(self.current_index.row(), 3), Qt.DisplayRole)
        query = QSqlQuery(self.db)
        query.prepare("UPDATE accounts SET reconciled_on=:timestamp WHERE id = :account_id")
        query.bindValue(":timestamp", timestamp)
        query.bindValue(":account_id", account_id)
        assert query.exec_()
        model.select()

    def CheckForNotSavedData(self):
        if self.ActionsModel.isDirty() or self.ActionDetailsModel.isDirty():
            reply = QMessageBox().warning(self, self.tr("You have unsaved changes"),
                                          self.tr("Transaction has uncommitted changes,\ndo you want to save it?"),
                                          QMessageBox.Yes, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.SubmitChangesForTab(TAB_ACTION)
            else:
                self.RevertChangesForTab(TAB_ACTION)
        if self.DividendsModel.isDirty():
            reply = QMessageBox().warning(self, self.tr("You have unsaved changes"),
                                          self.tr("Dividend has uncommitted changes,\ndo you want to save it?"),
                                          QMessageBox.Yes, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.SubmitChangesForTab(TAB_DIVIDEND)
            else:
                self.RevertChangesForTab(TAB_DIVIDEND)
        if self.TradesModel.isDirty():
            reply = QMessageBox().warning(self, self.tr("You have unsaved changes"),
                                          self.tr("Trade has uncommitted changes,\ndo you want to save it?"),
                                          QMessageBox.Yes, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.SubmitChangesForTab(TAB_TRADE)
            else:
                self.RevertChangesForTab(TAB_TRADE)
        if self.TransfersModel.isDirty():
            reply = QMessageBox().warning(self, self.tr("You have unsaved changes"),
                                          self.tr("Transfer has uncommitted changes,\ndo you want to save it?"),
                                          QMessageBox.Yes, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.SubmitChangesForTab(TAB_TRANSFER)
            else:
                self.RevertChangesForTab(TAB_TRANSFER)

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

    def CreateNewAction(self):
        self.CheckForNotSavedData()
        self.OperationsTabs.setCurrentIndex(TAB_ACTION)
        self.ActionsDataMapper.submit()
        self.ActionsModel.setFilter("actions.id = 0")
        new_record = self.ActionsModel.record()
        new_record.setValue("timestamp", QtCore.QDateTime.currentSecsSinceEpoch())
        if (self.ChooseAccountBtn.account_id != 0):
            new_record.setValue("account_id", self.ChooseAccountBtn.account_id)
        assert self.ActionsModel.insertRows(0, 1)
        self.ActionsModel.setRecord(0, new_record)
        self.ActionDetailsModel.setFilter("action_details.pid = 0")
        self.ActionsDataMapper.toLast()

    def CreateNewTransfer(self):
        self.CheckForNotSavedData()
        self.OperationsTabs.setCurrentIndex(TAB_TRANSFER)
        self.TransfersDataMapper.submit()
        self.TransfersModel.setFilter(f"transfers_combined.id = 0")
        new_record = self.TransfersModel.record()
        new_record.setValue("from_timestamp", QtCore.QDateTime.currentSecsSinceEpoch())
        if (self.ChooseAccountBtn.account_id != 0):
            new_record.setValue("from_acc_id", self.ChooseAccountBtn.account_id)
        new_record.setValue("to_timestamp", QtCore.QDateTime.currentSecsSinceEpoch())
        new_record.setValue("fee_timestamp", 0)
        assert self.TransfersModel.insertRows(0, 1)
        self.TransfersModel.setRecord(0, new_record)
        self.TransfersDataMapper.toLast()

    def CreateNewTrade(self):
        self.CheckForNotSavedData()
        self.OperationsTabs.setCurrentIndex(TAB_TRADE)
        self.TradesDataMapper.submit()
        self.TradesModel.setFilter("trades.id = 0")
        new_record = self.TradesModel.record()
        new_record.setValue("timestamp", QtCore.QDateTime.currentSecsSinceEpoch())
        if (self.ChooseAccountBtn.account_id != 0):
            new_record.setValue("account_id", self.ChooseAccountBtn.account_id)
        assert self.TradesModel.insertRows(0, 1)
        self.TradesModel.setRecord(0, new_record)
        self.TradesDataMapper.toLast()

    def CreateNewDividend(self):
        self.CheckForNotSavedData()
        self.OperationsTabs.setCurrentIndex(TAB_DIVIDEND)
        self.DividendsDataMapper.submit()
        self.DividendsModel.setFilter("dividends.id = 0")
        new_record = self.DividendsModel.record()
        new_record.setValue("timestamp", QtCore.QDateTime.currentSecsSinceEpoch())
        if (self.ChooseAccountBtn.account_id != 0):
            new_record.setValue("account_id", self.ChooseAccountBtn.account_id)
        assert self.DividendsModel.insertRows(0, 1)
        self.DividendsModel.setRecord(0, new_record)
        self.DividendsDataMapper.toLast()

    @Slot()
    def DeleteOperation(self):
        if QMessageBox().warning(self, self.tr("Confirmation"),
                                      self.tr("Are you sure to delete this transaction?"),
                                      QMessageBox.Yes, QMessageBox.No) == QMessageBox.No:
            return
        index = self.OperationsTableView.currentIndex()
        operation_type = self.OperationsModel.data(self.OperationsModel.index(index.row(), 0))
        if (operation_type == TRANSACTION_ACTION):
            self.ActionsModel.removeRow(0)
            self.ActionsModel.submitAll()
        elif (operation_type == TRANSACTION_DIVIDEND):
            self.DividendsModel.removeRow(0)
            self.DividendsModel.submitAll()
        elif (operation_type == TRANSACTION_TRADE):
            self.TradesModel.removeRow(0)
            self.TradesModel.submitAll()
        elif (operation_type == TRANSACTION_TRANSFER):
            self.TransfersModel.removeRow(0)
            self.TransfersModel.submitAll()
        else:
            assert False
        self.UpdateLedger()
        self.OperationsModel.select()

    @Slot()
    def CopyOperation(self):
        self.CheckForNotSavedData()
        active_tab = self.OperationsTabs.currentIndex()
        if (active_tab == TAB_ACTION):
            mapper = self.ActionsDataMapper
        elif (active_tab == TAB_TRANSFER):
            mapper = self.TransfersDataMapper
        elif (active_tab == TAB_DIVIDEND):
            mapper = self.DividendsDataMapper
        elif (active_tab == TAB_TRADE):
            mapper = self.TradesDataMapper
        else:
            assert False
        row = mapper.currentIndex()
        new_record = mapper.model().record(row)
        mapper.submit()
        new_record.setNull("id")
        new_record.setValue("timestamp", QtCore.QDateTime.currentSecsSinceEpoch())
        mapper.model().insertRecord(-1, new_record)
        mapper.toLast()

    @Slot()
    def SaveOperation(self):
        active_tab = self.OperationsTabs.currentIndex()
        self.SubmitChangesForTab(active_tab)

    @Slot()
    def RevertOperation(self):
        active_tab = self.OperationsTabs.currentIndex()
        self.RevertChangesForTab(active_tab)

    def SubmitChangesForTab(self, tab2save):
        if (tab2save == TAB_ACTION):
            pid = self.ActionsModel.data(self.ActionsModel.index(0, 0))
            if not self.ActionsModel.submitAll():
                print(self.tr("Action submit failed: "), self.ActionDetailsModel.lastError().text())
                return
            if pid == 0:        # we have saved new action record
                pid = self.ActionsModel.query().lastInsertId()
            for row in range(self.ActionDetailsModel.rowCount()):
                self.ActionDetailsModel.setData(self.ActionDetailsModel.index(row, 1), pid)
            if not self.ActionDetailsModel.submitAll():
                print(self.tr("Action details submit failed: "), self.ActionDetailsModel.lastError().text())
                return
        elif (tab2save == TAB_TRANSFER):
            if not self.TransfersModel.submitAll():
                print(self.tr("Transfer submit failed: "), self.TransfersModel.lastError().text())
                return
        elif (tab2save == TAB_DIVIDEND):
            if not self.DividendsModel.submitAll():
                print(self.tr("Dividend submit failed: "), self.DividendsModel.lastError().text())
                return
        elif (tab2save == TAB_TRADE):
            if not self.TradesModel.submitAll():
                print(self.tr("Trade submit failed: "), self.TradesModel.lastError().text())
                return
        else:
            assert False
        self.UpdateLedger()
        self.OperationsModel.select()
        self.SaveOperationBtn.setEnabled(False)
        self.RevertOperationBtn.setEnabled(False)

    def RevertChangesForTab(self, tab2revert):
        if (tab2revert == TAB_ACTION):
            self.ActionsModel.revertAll()
            self.ActionDetailsModel.revertAll()
        elif (tab2revert == TAB_TRANSFER):
            self.TransfersModel.revertAll()
        elif (tab2revert == TAB_DIVIDEND):
            self.DividendsModel.revertAll()
        elif (tab2revert == TAB_TRADE):
            self.TradesModel.revertAll()
        else:
            assert False
        self.SaveOperationBtn.setEnabled(False)
        self.RevertOperationBtn.setEnabled(False)

    @Slot()
    def BeforeTradeInsert(self, record):
        type = float(record.value("type"))
        price = float(record.value("price"))
        qty = float(record.value("qty"))
        coupon = float(record.value("coupon"))
        fee_broker = float(record.value("fee_broker"))
        fee_exchange = float(record.value("fee_exchange"))
        sum = round(price*qty, 2) + type*(fee_broker + fee_exchange) + coupon
        record.setValue("sum", sum)

    @Slot()
    def AddDetail(self):
        new_record = self.ActionDetailsModel.record()
        self.ActionDetailsModel.insertRecord(-1, new_record)

    @Slot()
    def RemoveDetail(self):
        idx = self.ActionDetailsTableView.selectionModel().selection().indexes()
        selected_row = idx[0].row()
        self.ActionDetailsModel.removeRow(selected_row)
        self.ActionDetailsTableView.setRowHidden(selected_row, True)
        self.SaveOperationBtn.setEnabled(True)
        self.RevertOperationBtn.setEnabled(True)

    @Slot()
    def OnOperationDataChanged(self):
        self.SaveOperationBtn.setEnabled(True)
        self.RevertOperationBtn.setEnabled(True)

    def UpdateLedger(self):
        query = QSqlQuery(self.db)
        query.exec_("SELECT ledger_frontier FROM frontier")
        query.next()
        current_frontier = query.value(0)
        if current_frontier == '':
            current_frontier = 0
        if (QtCore.QDateTime.currentDateTime().toSecsSinceEpoch() - current_frontier) > 1296000: # if we have less then 15 days unreconciled
            if QMessageBox().warning(self, self.tr("Confirmation"),
                                     self.tr("More than 2 weeks require rebuild. Do you want to do it right now?"),
                                     QMessageBox.Yes, QMessageBox.No) == QMessageBox.No:
                return
        self.ledger.MakeUpToDate()

    @Slot()
    def EditAccountTypes(self):
        dlg = AcountTypeEditDlg()
        dlg.init_DB(self.db)
        dlg.exec_()

    @Slot()
    def EditAccounts(self):
        dlg = AccountChoiceDlg()
        dlg.init_DB(self.db)
        dlg.exec_()

    @Slot()
    def EditActives(self):
        dlg = ActiveChoiceDlg()
        dlg.init_DB(self.db)
        dlg.exec_()

    @Slot()
    def EditPeers(self):
        dlg = PeerChoiceDlg()
        dlg.init_DB(self.db)
        dlg.setFilter()
        dlg.exec_()

    @Slot()
    def EditCategories(self):
        dlg = CategoryChoiceDlg()
        dlg.init_DB(self.db)
        dlg.setFilter()
        dlg.exec_()

    @Slot()
    def UpdateActives(self):
        self.ledger.BuildActivesTable(1580233494, CURRENCY_RUBLE)
        self.HoldingsModel.select()