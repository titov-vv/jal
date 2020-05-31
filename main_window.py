from PySide2.QtWidgets import QMainWindow, QFileDialog, QAbstractItemView, QDataWidgetMapper, QHeaderView, QMenu, QMessageBox, QAction, QInputDialog
from PySide2.QtSql import QSql, QSqlDatabase, QSqlQuery, QSqlQueryModel, QSqlTableModel, QSqlRelationalTableModel, QSqlRelation
from PySide2.QtCore import Slot, QMetaObject
from PySide2.QtGui import QDoubleValidator
from PySide2 import QtCore
import os
from UI.ui_main_window import Ui_LedgerMainWindow
from ledger import Ledger
from taxes import TaxesRus, TaxExportDialog
from reports import Reports, ReportParamsDialog
from bulk_db import loadDbFromSQL, MakeBackup, RestoreBackup
from statements import StatementLoader
from rebuild_window import RebuildDialog
from downloader import QuoteDownloader, QuotesUpdateDialog
from balance_delegate import BalanceDelegate, HoldingsDelegate
from operation_delegate import *
from dividend_delegate import DividendSqlDelegate
from trade_delegate import TradeSqlDelegate
from transfer_delegate import TransferSqlDelegate
from action_delegate import ActionDelegate, ActionDetailDelegate
from CustomUI.account_select import AcountTypeEditDlg, AccountChoiceDlg
from CustomUI.asset_select import AssetChoiceDlg
from CustomUI.peer_select import PeerChoiceDlg
from CustomUI.category_select import CategoryChoiceDlg
from CustomUI.tag_select import TagChoiceDlg
#-----------------------------------------------------------------------------------------------------------------------
# model - QSqlTableModel where titles should be set for given columns
# column_title_list - list of column_name/header_title pairs
def ModelSetColumnHeaders(model, column_title_list):
    for column_title in column_title_list:
        model.setHeaderData(model.fieldIndex(column_title[0]), Qt.Horizontal, column_title[1])

# view - QTableView where columns will be hidden
# columns_list - list of column names
def HideViewColumns(view, columns_list):
    for column in columns_list:
        view.setColumnHidden(view.model().fieldIndex(column), True)

# view - QTableView where column width should be set
# column_width_list - list of column_name/width pairs
def ViewSetColumnWidths(view, column_width_list):
    for column_width in column_width_list:
        view.setColumnWidth(view.model().fieldIndex(column_width[0]), column_width[1])

# This function gets a list of column_name/widget/width/validator pairs and:
# 1) adds mapping between model and widget, 2) sets correct widget width, 3) set validator for widget
# model - QSqlTableModel from where data to be mapped to widgets
# mapper - QDataWidgetMapper to map data
# column_widget_list - list of column_name/widget/width pairs that should be mapped
def AddAndConfigureMappings(model, mapper, column_widget_list):
    for column_widget in column_widget_list:
        mapper.addMapping(column_widget[1], model.fieldIndex(column_widget[0]))  # if no USER property QByteArray().setRawData("account_id", 10))
        if column_widget[2]:
            column_widget[1].setFixedWidth(column_widget[2])
        if column_widget[3]:
            column_widget[1].setValidator(column_widget[3])

#-----------------------------------------------------------------------------------------------------------------------
class MainWindow(QMainWindow, Ui_LedgerMainWindow):
    def __init__(self):
        QMainWindow.__init__(self, None)
        self.setupUi(self)

        self.own_path = os.path.dirname(os.path.realpath(__file__)) + os.sep
        self.db = QSqlDatabase.addDatabase("QSQLITE")
        self.db.setDatabaseName(self.own_path + DB_PATH)
        self.db.open()
        tables = self.db.tables(QSql.Tables)
        if tables == []:
            self.InitDB()
            QMetaObject.invokeMethod(self, "close", Qt.QueuedConnection)
            return

        query = QSqlQuery(self.db)
        query.exec_("SELECT value FROM settings WHERE name='SchemaVersion'")
        query.next()
        if query.value(0) != TARGET_SCHEMA:
            self.db.close()
            QMessageBox().critical(self, self.tr("Database version mismatch"),
                                  self.tr("Database schema version is wrong"),
                                  QMessageBox.Ok)
            QMetaObject.invokeMethod(self, "close", Qt.QueuedConnection)
            return

        query = QSqlQuery(self.db)
        query.exec_("SELECT value FROM settings WHERE name='BaseCurrency'")
        query.next()
        self.balance_currency = query.value(0)
        self.holdings_currency = query.value(0)

        self.ledger = Ledger(self.db)
        self.downloader = QuoteDownloader(self.db)

        self.balance_date = QtCore.QDateTime.currentSecsSinceEpoch()
        self.balance_active_only = 1

        self.holdings_date = QtCore.QDateTime.currentSecsSinceEpoch()

        self.operations_since_timestamp = 0

        self.ConfigureUI()
        self.UpdateBalances()

    def __del__(self):
        self.db.close()

    def UseSqlTable(self, table_name, column_title_list):
        model = QSqlTableModel(db=self.db)
        model.setTable(table_name)
        model.setEditStrategy(QSqlTableModel.OnManualSubmit)
        ModelSetColumnHeaders(model, column_title_list)
        model.select()
        return model

    def ConfigureTableView(self, view, model, hide_columns_list, column_width_list, stretch_column):
        view.setModel(model)
        HideViewColumns(view, hide_columns_list)
        ViewSetColumnWidths(view, column_width_list)
        view.horizontalHeader().setSectionResizeMode(model.fieldIndex(stretch_column), QHeaderView.Stretch)
        view.setSelectionBehavior(QAbstractItemView.SelectRows)
        font = view.horizontalHeader().font()
        font.setBold(True)
        view.horizontalHeader().setFont(font)

    def ConfigureUI(self):
        self.doubleValidate2 = QDoubleValidator(decimals=2)
        self.doubleValidate6 = QDoubleValidator(decimals=6)
        widthForAmountEdit = self.fontMetrics().width("888888888.88") * 1.5
        widthForTimestampEdit = self.fontMetrics().width("00/00/0000 00:00:00") * 1.5

        self.AddActionDetail.setFixedWidth(widthForTimestampEdit * 0.25)
        self.CopyActionDetail.setFixedWidth(widthForTimestampEdit * 0.25)
        self.RemoveActionDetail.setFixedWidth(widthForTimestampEdit * 0.25)

        self.BalanceDate.setDateTime(QtCore.QDateTime.currentDateTime())
        self.HoldingsDate.setDateTime(QtCore.QDateTime.currentDateTime())

        self.CurrencyNameQuery = QSqlQuery(self.db)
        self.CurrencyNameQuery.exec_("SELECT id, name FROM assets WHERE type_id=1")
        self.CurrencyNameModel = QSqlQueryModel()
        self.CurrencyNameModel.setQuery(self.CurrencyNameQuery)
        self.BalancesCurrencyCombo.setModel(self.CurrencyNameModel)
        self.BalancesCurrencyCombo.setModelColumn(1)
        self.BalancesCurrencyCombo.setCurrentIndex(self.BalancesCurrencyCombo.findText("RUB"))
        self.HoldingsCurrencyCombo.setModel(self.CurrencyNameModel)
        self.HoldingsCurrencyCombo.setModelColumn(1)
        self.HoldingsCurrencyCombo.setCurrentIndex(self.HoldingsCurrencyCombo.findText("RUB"))

        self.BalancesModel = self.UseSqlTable("balances", [("account_name", "Account"), ("balance", "Balance"),
                                                   ("currency_name", ""), ("balance_adj", "Balance, RUB")])
        self.ConfigureTableView(self.BalancesTableView, self.BalancesModel,
                                ["level1", "level2", "days_unreconciled", "active"],
                                [("account_name", 75), ("balance", 100), ("currency_name", 35), ("balance_adj", 110)],
                                "account_name")
        self.BalancesTableView.setItemDelegate(BalanceDelegate(self.BalancesTableView))
        self.BalancesTableView.show()

        self.HoldingsModel = self.UseSqlTable("holdings", [("account", "C/A"), ("asset", ""), ("asset_name", "Asset"),
                                                   ("qty", "Qty"), ("open", "Open"), ("quote", "Last"),
                                                   ("share", "Share, %"), ("profit_rel", "P/L, %"), ("profit", "P/L"),
                                                   ("value", "Value"), ("value_adj", "Value, RUB")])
        self.ConfigureTableView(self.HoldingsTableView, self.HoldingsModel,
                                ["level1", "level2", "currency"], [("account", 32)], "asset_name")
        self.HoldingsTableView.setItemDelegate(HoldingsDelegate(self.HoldingsTableView))
        self.HoldingsTableView.show()

        self.ChooseAccountBtn.init_DB(self.db)

        self.OperationsModel = self.UseSqlTable("all_operations", [("type", " "), ("timestamp", "Timestamp"), ("account", "Account"),
                                                     ("note", "Notes"), ("amount", "Amount"), ("t_amount", "Balance"),
                                                     ("currency", "Currency")])
        self.ConfigureTableView(self.OperationsTableView, self.OperationsModel,
                                ["id", "account_id", "num_peer", "asset_id", "asset", "asset_name",
                                 "note2", "qty_trid", "price", "fee_tax", "t_qty", "reconciled"],
                                [("type", 10), ("timestamp", widthForTimestampEdit * 0.7), ("account", 300), ("note", 300)],
                                "note")
        self.OperationsTableView.setItemDelegateForColumn(self.OperationsModel.fieldIndex("type"), OperationsTypeDelegate(self.OperationsTableView))
        self.OperationsTableView.setItemDelegateForColumn(self.OperationsModel.fieldIndex("timestamp"), OperationsTimestampDelegate(self.OperationsTableView))
        self.OperationsTableView.setItemDelegateForColumn(self.OperationsModel.fieldIndex("account"), OperationsAccountDelegate(self.OperationsTableView))
        self.OperationsTableView.setItemDelegateForColumn(self.OperationsModel.fieldIndex("note"), OperationsNotesDelegate(self.OperationsTableView))
        self.OperationsTableView.setItemDelegateForColumn(self.OperationsModel.fieldIndex("amount"), OperationsAmountDelegate(self.OperationsTableView))
        self.OperationsTableView.setItemDelegateForColumn(self.OperationsModel.fieldIndex("t_amount"), OperationsTotalsDelegate(self.OperationsTableView))
        self.OperationsTableView.setItemDelegateForColumn(self.OperationsModel.fieldIndex("currency"), OperationsCurrencyDelegate(self.OperationsTableView))
        self.OperationsTableView.setSelectionMode(QAbstractItemView.SingleSelection)
        self.OperationsTableView.setContextMenuPolicy(Qt.CustomContextMenu)
        self.OperationsTableView.setWordWrap(False)
        # next line forces usage of sizeHint() from delegate
        self.OperationsTableView.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.OperationsTableView.show()

        ###############################################################################################
        # CONFIGURE ACTIONS TAB                                                                       #
        ###############################################################################################
        self.ActionAccountWidget.init_DB(self.db)
        self.ActionPeerWidget.init_DB(self.db)

        self.ActionsModel = QSqlTableModel(db=self.db)
        self.ActionsModel.setTable("actions")
        self.ActionsModel.setEditStrategy(QSqlTableModel.OnManualSubmit)
        self.ActionsModel.dataChanged.connect(self.OnOperationDataChanged)
        self.ActionsModel.select()
        self.ActionsDataMapper = QDataWidgetMapper(self)
        self.ActionsDataMapper.setModel(self.ActionsModel)
        self.ActionsDataMapper.setSubmitPolicy(QDataWidgetMapper.AutoSubmit)
        self.ActionsDataMapper.setItemDelegate(ActionDelegate(self.ActionsDataMapper))
        AddAndConfigureMappings(self.ActionsModel, self.ActionsDataMapper,
                                [("timestamp",  self.ActionTimestampEdit,   widthForTimestampEdit,  None),
                                 ("account_id", self.ActionAccountWidget,   0,                      None),
                                 ("peer_id",    self.ActionPeerWidget,      0,                      None)])
        self.ActionAccountWidget.changed.connect(self.ActionsDataMapper.submit)
        self.ActionPeerWidget.changed.connect(self.ActionsDataMapper.submit)

        self.ActionDetailsModel = QSqlRelationalTableModel(db=self.db)
        self.ActionDetailsModel.setTable("action_details")
        self.ActionDetailsModel.setJoinMode(QSqlRelationalTableModel.LeftJoin)  # in order not to fail on NULL tags
        self.ActionDetailsModel.setEditStrategy(QSqlTableModel.OnManualSubmit)
        category_idx = self.ActionDetailsModel.fieldIndex("category_id")
        self.ActionDetailsModel.setRelation(category_idx, QSqlRelation("categories", "id", "name"))
        tag_idx = self.ActionDetailsModel.fieldIndex("tag_id")
        self.ActionDetailsModel.setRelation(tag_idx, QSqlRelation("tags", "id", "tag"))
        ModelSetColumnHeaders(self.ActionDetailsModel, [("category_id", "Category"), ("tag_id", "Tags"),
                                                        ("sum", "Amount"), ("alt_sum", "Amount *"), ("note", "Note")])
        self.ActionDetailsModel.dataChanged.connect(self.OnOperationDataChanged)
        self.ActionDetailsModel.select()
        self.ActionDetailsTableView.setModel(self.ActionDetailsModel)
        self.ActionDetailsTableView.setItemDelegate(ActionDetailDelegate(self.ActionDetailsTableView))
        self.ActionDetailsTableView.setSelectionBehavior(QAbstractItemView.SelectRows)  # To select only 1 row
        self.ActionDetailsTableView.setSelectionMode(QAbstractItemView.SingleSelection)
        HideViewColumns(self.ActionDetailsTableView, ["id", "pid"])
        # "name" and "tag" are column names from Relations
        ViewSetColumnWidths(self.ActionDetailsTableView, [("name", 200), ("tag", 200), ("sum", 100),
                                                          ("alt_sum", 100), ("note", 400)])
        self.ActionDetailsTableView.horizontalHeader().setSectionResizeMode(
            self.ActionDetailsModel.fieldIndex("note"), QHeaderView.Stretch)  # make notes to fill all remaining space
        self.ActionDetailsTableView.horizontalHeader().moveSection(self.ActionDetailsModel.fieldIndex("note"),
                                                                   self.ActionDetailsModel.fieldIndex("name"))
        self.ActionDetailsTableView.show()

        ###############################################################################################
        # CONFIGURE TRADES TAB                                                                        #
        ###############################################################################################
        self.TradeActionWidget.init_DB(self.db)
        self.TradeAccountWidget.init_DB(self.db)
        self.TradeAssetWidget.init_DB(self.db)

        self.TradesModel = QSqlRelationalTableModel(db=self.db)
        self.TradesModel.setTable("trades")
        self.TradesModel.setJoinMode(QSqlRelationalTableModel.LeftJoin)
        self.TradesModel.setEditStrategy(QSqlTableModel.OnManualSubmit)
        corp_action_idx = self.ActionDetailsModel.fieldIndex("corp_action_id")
        self.ActionDetailsModel.setRelation(corp_action_idx, QSqlRelation("corp_actions", "id", "type"))
        self.TradesModel.dataChanged.connect(self.OnOperationDataChanged)
        self.TradesModel.select()
        self.TradesDataMapper = QDataWidgetMapper(self)
        self.TradesDataMapper.setModel(self.TradesModel)
        self.TradesDataMapper.setSubmitPolicy(QDataWidgetMapper.AutoSubmit)
        self.TradesDataMapper.setItemDelegate(TradeSqlDelegate(self.TradesDataMapper))
        AddAndConfigureMappings(self.TradesModel, self.TradesDataMapper,
                [("timestamp",      self.TradeTimestampEdit,    widthForTimestampEdit,  None),
                 ("corp_action_id", self.TradeActionWidget,     0,                      None),
                 ("account_id",     self.TradeAccountWidget,    0,                      None),
                 ("asset_id",       self.TradeAssetWidget,      0,                      None),
                 ("settlement",     self.TradeSettlementEdit,   0,                      None),
                 ("number",         self.TradeNumberEdit,       widthForTimestampEdit,  None),
                 ("price",          self.TradePriceEdit,        widthForAmountEdit,     self.doubleValidate6),
                 ("qty",            self.TradeQtyEdit,          widthForAmountEdit,     self.doubleValidate6),
                 ("coupon",         self.TradeCouponEdit,       widthForAmountEdit,     self.doubleValidate6),
                 ("fee",            self.TradeFeeEdit,          widthForAmountEdit,     self.doubleValidate6)])
        self.TradeAccountWidget.changed.connect(self.TradesDataMapper.submit)
        self.TradeAssetWidget.changed.connect(self.TradesDataMapper.submit)

        ###############################################################################################
        # CONFIGURE DIVIDENDS TAB                                                                     #
        ###############################################################################################
        self.DividendAccountWidget.init_DB(self.db)
        self.DividendAssetWidget.init_DB(self.db)

        self.DividendsModel = QSqlTableModel(db=self.db)
        self.DividendsModel.setTable("dividends")
        self.DividendsModel.setEditStrategy(QSqlTableModel.OnManualSubmit)
        self.DividendsModel.dataChanged.connect(self.OnOperationDataChanged)
        self.DividendsModel.select()
        self.DividendsDataMapper = QDataWidgetMapper(self)
        self.DividendsDataMapper.setModel(self.DividendsModel)
        self.DividendsDataMapper.setSubmitPolicy(QDataWidgetMapper.AutoSubmit)
        self.DividendsDataMapper.setItemDelegate(DividendSqlDelegate(self.DividendsDataMapper))
        AddAndConfigureMappings(self.DividendsModel, self.DividendsDataMapper,
                        [("timestamp",  self.DividendTimestampEdit,     widthForTimestampEdit,  None),
                         ("account_id", self.DividendAccountWidget,     0,                      None),
                         ("asset_id",   self.DividendAssetWidget,       0,                      None),
                         ("number",     self.DividendNumberEdit,        widthForTimestampEdit,  None),
                         ("sum",        self.DividendSumEdit,           widthForAmountEdit,     self.doubleValidate2),
                         ("note",       self.DividendSumDescription,    0,                      None),
                         ("sum_tax",    self.DividendTaxEdit,           widthForAmountEdit,     self.doubleValidate2),
                         ("note_tax",   self.DividendTaxDescription,    0,                      None)])
        self.DividendAccountWidget.changed.connect(self.DividendsDataMapper.submit)
        self.DividendAssetWidget.changed.connect(self.DividendsDataMapper.submit)

        ###############################################################################################
        # CONFIGURE TRANSFERS TAB                                                                     #
        ###############################################################################################
        self.TransferFromAccountWidget.init_DB(self.db)
        self.TransferToAccountWidget.init_DB(self.db)
        self.TransferFeeAccountWidget.init_DB(self.db)

        self.TransfersModel = QSqlTableModel(db=self.db)
        self.TransfersModel.setTable("transfers_combined")
        self.TransfersModel.setEditStrategy(QSqlTableModel.OnManualSubmit)
        self.TransfersModel.dataChanged.connect(self.OnOperationDataChanged)
        self.TransfersModel.select()
        self.TransfersDataMapper = QDataWidgetMapper(self)
        self.TransfersDataMapper.setModel(self.TransfersModel)
        self.TransfersDataMapper.setSubmitPolicy(QDataWidgetMapper.AutoSubmit)
        self.TransfersDataMapper.setItemDelegate(TransferSqlDelegate(self.TransfersDataMapper))
        AddAndConfigureMappings(self.TransfersModel, self.TransfersDataMapper,
                    [("from_acc_id",    self.TransferFromAccountWidget, 0,                      None),
                     ("to_acc_id",      self.TransferToAccountWidget,   0,                      None),
                     ("fee_acc_id",     self.TransferFeeAccountWidget,  0,                      None),
                     ("from_timestamp", self.TransferFromTimestamp,     widthForTimestampEdit,  None),
                     ("to_timestamp",   self.TransferToTimestamp,       widthForTimestampEdit,  None),
                     ("fee_timestamp",  self.TransferFeeTimestamp,      widthForTimestampEdit,  None),
                     ("from_amount",    self.TransferFromAmount,        widthForAmountEdit,     self.doubleValidate2),
                     ("to_amount",      self.TransferToAmount,          widthForAmountEdit,     self.doubleValidate2),
                     ("fee_amount",     self.TransferFeeAmount,         widthForAmountEdit,     self.doubleValidate2),
                     ("note",           self.TransferNote,              0,                      None)])
        self.TransferFromAccountWidget.changed.connect(self.TransfersDataMapper.submit)
        self.TransferToAccountWidget.changed.connect(self.TransfersDataMapper.submit)
        self.TransferFeeAccountWidget.changed.connect(self.TransfersDataMapper.submit)

        ###############################################################################################
        # CONFIGURE ACTIONS                                                                           #
        ###############################################################################################
        # MENU ACTIONS
        self.actionExit.triggered.connect(qApp.quit)
        self.action_Load_quotes.triggered.connect(self.UpdateQuotes)
        self.actionLoad_Statement.triggered.connect(self.loadReportIBKR)
        self.actionBackup.triggered.connect(self.Backup)
        self.actionRestore.triggered.connect(self.Restore)
        self.action_Re_build_Ledger.triggered.connect(self.ShowRebuildDialog)
        self.actionAccountTypes.triggered.connect(self.EditAccountTypes)
        self.actionAccounts.triggered.connect(self.EditAccounts)
        self.actionAssets.triggered.connect(self.EditAssets)
        self.actionPeers.triggered.connect(self.EditPeers)
        self.actionCategories.triggered.connect(self.EditCategories)
        self.actionTags.triggered.connect(self.EditTags)
        self.MakeIncomeSpendingReport.triggered.connect(self.ReportIncomeSpending)
        self.MakeDealsReport.triggered.connect(self.ReportDeals)
        self.MakePLReport.triggered.connect(self.ReportProfitLoss)
        self.PrepareTaxForms.triggered.connect(self.ExportTaxForms)
        # INTERFACE ACTIONS
        self.MainTabs.currentChanged.connect(self.OnMainTabChange)
        self.BalanceDate.dateChanged.connect(self.onBalanceDateChange)
        self.HoldingsDate.dateChanged.connect(self.onHoldingsDateChange)
        self.BalancesCurrencyCombo.currentIndexChanged.connect(self.OnBalanceCurrencyChange)
        self.HoldingsCurrencyCombo.currentIndexChanged.connect(self.OnHoldingsCurrencyChange)
        self.ShowInactiveCheckBox.stateChanged.connect(self.OnBalanceInactiveChange)
        self.DateRangeCombo.currentIndexChanged.connect(self.OnOperationsRangeChange)
        # OPERATIONS TABLE ACTIONS
        self.OperationsTableView.selectionModel().selectionChanged.connect(self.OnOperationChange)
        self.OperationsTableView.customContextMenuRequested.connect(self.OnOperationsContextMenu)
        self.ChooseAccountBtn.clicked.connect(self.OnAccountChange)
        self.SearchString.textChanged.connect(self.OnSearchChange)
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

        self.OperationsTableView.selectRow(0)
        self.OnOperationsRangeChange(0)

    def Backup(self):
        backup_directory = QFileDialog.getExistingDirectory(self, "Select directory to save backup")
        if backup_directory:
            MakeBackup(self.own_path + DB_PATH, backup_directory)

    def Restore(self):
        restore_directory = QFileDialog.getExistingDirectory(self, "Select directory to restore from")
        if restore_directory:
            self.db.close()
            RestoreBackup(self.own_path + DB_PATH, restore_directory)
            QMessageBox().information(self, self.tr("Data restored"),
                                      self.tr("Database was loaded from the backup.\n"
                                              "You need to restart the application.\n"
                                              "Application terminates now."),
                                      QMessageBox.Ok)
            qApp.quit()

    def InitDB(self):
        self.db.close()
        loadDbFromSQL(self.own_path + DB_PATH, self.own_path + INIT_SCRIPT_PATH)
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
            self.StatusBar.showMessage("Asset holdings report")
            self.UpdateHoldings()

    @Slot()
    def onBalanceDateChange(self, new_date):
        self.balance_date = self.BalanceDate.dateTime().toSecsSinceEpoch()
        self.UpdateBalances()

    @Slot()
    def onHoldingsDateChange(self, new_date):
        self.holdings_date = self.HoldingsDate.dateTime().toSecsSinceEpoch()
        self.UpdateHoldings()

    @Slot()
    def OnBalanceCurrencyChange(self, currency_index):
        self.balance_currency = self.CurrencyNameModel.record(currency_index).value("id")
        self.BalancesModel.setHeaderData(self.BalancesModel.fieldIndex("balance_adj"), Qt.Horizontal,
                                         "Balance, " + self.CurrencyNameModel.record(currency_index).value("name"))
        self.UpdateBalances()

    @Slot()
    def OnHoldingsCurrencyChange(self, currency_index):
        self.holdings_currency = self.CurrencyNameModel.record(currency_index).value("id")
        self.HoldingsModel.setHeaderData(self.HoldingsModel.fieldIndex("value_adj"), Qt.Horizontal,
                                         "Value, " + self.CurrencyNameModel.record(currency_index).value("name"))
        self.UpdateHoldings()

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
                self.DividendsModel.setFilter(f"dividends.id = {operation_id}")
                self.DividendsDataMapper.setCurrentModelIndex(self.DividendsDataMapper.model().index(0, 0))
            elif (operation_type == TRANSACTION_TRADE):
                self.OperationsTabs.setCurrentIndex(TAB_TRADE)
                self.TradesModel.setFilter(f"trades.id = {operation_id}")
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

        if self.SearchString.text():
            operations_filter = operations_filter + " AND (num_peer LIKE '%{}%' OR asset LIKE '%{}%')".format(self.SearchString.text(), self.SearchString.text())

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
    def OnSearchChange(self):
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
            row = self.ActionsDataMapper.currentIndex()
            operation_id = self.ActionsModel.record(row).value(self.ActionsModel.fieldIndex("id"))
            self.ActionsDataMapper.submit()
            new_record = self.ActionsModel.record(row)
            new_record.setNull("id")
            new_record.setValue("timestamp", QtCore.QDateTime.currentSecsSinceEpoch())
            self.ActionsModel.setFilter("actions.id = 0")
            assert self.ActionsModel.insertRows(0, 1)
            self.ActionsModel.setRecord(0, new_record)
            self.ActionsDataMapper.toLast()
            # Get SQL records of details and insert it into details table
            self.ActionDetailsModel.setFilter("action_details.pid = 0")
            query = QSqlQuery(self.db)
            query.prepare("SELECT * FROM action_details WHERE pid = :pid ORDER BY id DESC")
            query.bindValue(":pid", operation_id)
            query.setForwardOnly(True)
            assert query.exec_()
            while query.next():
                new_record = query.record()
                new_record.setNull("id")
                new_record.setNull("pid")
                assert self.ActionDetailsModel.insertRows(0, 1)
                self.ActionDetailsModel.setRecord(0, new_record)
        elif (active_tab == TAB_TRANSFER):
            row = self.TransfersDataMapper.currentIndex()
            self.TransfersDataMapper.submit()
            new_record = self.TransfersModel.record(row)
            new_record.setNull("id")
            new_record.setValue("from_timestamp", QtCore.QDateTime.currentSecsSinceEpoch())
            new_record.setValue("to_timestamp", QtCore.QDateTime.currentSecsSinceEpoch())
            new_record.setValue("fee_timestamp", 0)
            self.TransfersModel.setFilter(f"transfers_combined.id = 0")
            assert self.TransfersModel.insertRows(0, 1)
            self.TransfersModel.setRecord(0, new_record)
            self.TransfersDataMapper.toLast()
        elif (active_tab == TAB_DIVIDEND):
            row = self.DividendsDataMapper.currentIndex()
            self.DividendsDataMapper.submit()
            new_record = self.DividendsModel.record()
            new_record.setNull("id")
            new_record.setValue("timestamp", QtCore.QDateTime.currentSecsSinceEpoch())
            self.DividendsModel.setFilter("dividends.id = 0")
            assert self.DividendsModel.insertRows(0, 1)
            self.DividendsModel.setRecord(0, new_record)
            self.DividendsDataMapper.toLast()
        elif (active_tab == TAB_TRADE):
            row = self.TradesDataMapper.currentIndex()
            self.TradesDataMapper.submit()
            new_record = self.TradesModel.record(row)
            new_record.setNull("id")
            new_record.setValue("timestamp", QtCore.QDateTime.currentSecsSinceEpoch())
            self.TradesModel.setFilter("trades.id = 0")
            assert self.TradesModel.insertRows(0, 1)
            self.TradesModel.setRecord(0, new_record)
            self.TradesDataMapper.toLast()
        else:
            assert False

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
            pid = self.ActionsModel.data(self.ActionsModel.index(0, self.ActionsModel.fieldIndex("id")))
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
            record = self.TransfersModel.record(0)
            note = record.value(self.TransfersModel.fieldIndex("note"))
            if not note:                           # If we don't have note - set it to NULL value to fire DB trigger
                self.TransfersModel.setData(self.TransfersModel.index(0, self.TransfersModel.fieldIndex("note")), None)
            fee_amount = record.value(self.TransfersModel.fieldIndex("fee_amount"))
            if not fee_amount:
                fee_amount = 0
            if abs(float(fee_amount)) < CALC_TOLERANCE:   # If we don't have fee - set Fee Account to NULL to fire DB trigger
                self.TransfersModel.setData(self.TransfersModel.index(0, self.TransfersModel.fieldIndex("fee_acc_id")), None)
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
    def EditAssets(self):
        dlg = AssetChoiceDlg()
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
    def EditTags(self):
        dlg = TagChoiceDlg()
        dlg.init_DB(self.db)
        dlg.setFilter()
        dlg.exec_()

    @Slot()
    def UpdateHoldings(self):
        self.ledger.BuildHoldingsTable(self.holdings_date, self.holdings_currency)
        self.HoldingsModel.select()
        for row in range(self.HoldingsModel.rowCount()):
            if self.HoldingsModel.data(self.HoldingsModel.index(row, 1)):
                self.HoldingsTableView.setSpan(row, 3, 1, 3)
        self.HoldingsTableView.show()

    @Slot()
    def UpdateQuotes(self):
        update_dialog = QuotesUpdateDialog()
        update_dialog.setGeometry(self.x() + 64, self.y() + 64, update_dialog.width(), update_dialog.height())
        if update_dialog.exec_():
            self.downloader.UpdateQuotes(update_dialog.getStartDate(), update_dialog.getEndDate(), update_dialog.getUseProxy())

    @Slot()
    def loadReportIBKR(self):
        report_file, filter = QFileDialog.getOpenFileName(self, self.tr("Select Interactive Brokers Flex-query to import"), ".",
                                                           self.tr("IBRK flex-query (*.xml);;Quik HTML-report (*.htm)"))
        if report_file:
            report_loader = StatementLoader(self.db)
            if filter == self.tr("IBRK flex-query (*.xml)"):
                report_loader.loadIBFlex(report_file)
            if filter == self.tr("Quik HTML-report (*.htm)"):
                report_loader.loadQuikHtml(report_file)
            self.UpdateLedger()

    @Slot()
    def ReportDeals(self):
        deals_export_dialog = ReportParamsDialog(self.db)
        deals_export_dialog.setGeometry(self.x() + 64, self.y() + 64, deals_export_dialog.width(),
                                        deals_export_dialog.height())
        if deals_export_dialog.exec_():
            deals = Reports(self.db, deals_export_dialog.filename)
            deals.save_deals(deals_export_dialog.account,
                             deals_export_dialog.begin, deals_export_dialog.end, deals_export_dialog.group_dates)

    @Slot()
    def ReportProfitLoss(self):
        pl_export_dialog = ReportParamsDialog(self.db)
        pl_export_dialog.setGeometry(self.x() + 64, self.y() + 64, pl_export_dialog.width(),
                                     pl_export_dialog.height())
        if pl_export_dialog.exec_():
            deals = Reports(self.db, pl_export_dialog.filename)
            deals.save_profit_loss(pl_export_dialog.account, pl_export_dialog.begin, pl_export_dialog.end)

    @Slot()
    def ReportIncomeSpending(self):
        income_spending_export_dialog = ReportParamsDialog(self.db)
        income_spending_export_dialog.setGeometry(self.x() + 64, self.y() + 64, income_spending_export_dialog.width(),
                                                  income_spending_export_dialog.height())
        if income_spending_export_dialog.exec_():
            deals = Reports(self.db, income_spending_export_dialog.filename)
            deals.save_income_sending(income_spending_export_dialog.begin, income_spending_export_dialog.end)

    @Slot()
    def ExportTaxForms(self):
        tax_export_dialog = TaxExportDialog(self.db)
        tax_export_dialog.setGeometry(self.x() + 64, self.y() + 64, tax_export_dialog.width(), tax_export_dialog.height())
        if tax_export_dialog.exec_():
            taxes = TaxesRus(self.db)
            taxes.save2file(tax_export_dialog.filename, tax_export_dialog.year, tax_export_dialog.account)
