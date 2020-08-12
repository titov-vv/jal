import logging
import os
from functools import partial

from PySide2 import QtCore, QtWidgets
from PySide2.QtCore import Slot
from PySide2.QtGui import QDoubleValidator
from PySide2.QtSql import QSqlQuery
from PySide2.QtWidgets import QMainWindow, QFileDialog, QHeaderView, QMenu, QMessageBox, QAction, QLabel

from CustomUI.helpers import VLine
from UI.ui_main_window import Ui_LedgerMainWindow
from view_delegate import *
from DB.bulk_db import MakeBackup, RestoreBackup
from DB.helpers import init_and_check_db, get_base_currency
from downloader import QuoteDownloader
from ledger import Ledger
from operations import LedgerOperationsView
from reports import Reports
from statements import StatementLoader
from taxes import TaxesRus
from CustomUI.table_view_config import TableViewConfig


# -----------------------------------------------------------------------------------------------------------------------
class MainWindow(QMainWindow, Ui_LedgerMainWindow):
    def __init__(self):
        QMainWindow.__init__(self, None)
        self.setupUi(self)

        self.own_path = os.path.dirname(os.path.realpath(__file__)) + os.sep
        self.db = init_and_check_db(self, self.own_path)
        if not self.db:
            return

        self.ledger = Ledger(self.db)
        self.downloader = QuoteDownloader(self.db)
        self.downloader.download_completed.connect(self.onQuotesDownloadCompletion)
        self.reports = Reports(self.db)
        self.taxes = TaxesRus(self.db)
        self.statements = StatementLoader(self.db)
        self.statements.load_completed.connect(self.onStatementLoaded)

        # Customize Status bar and logs
        self.NewLogEventLbl = QLabel(self)
        self.StatusBar.addPermanentWidget(VLine())
        self.StatusBar.addPermanentWidget(self.NewLogEventLbl)
        self.Logs.setNotificationLabel(self.NewLogEventLbl)
        self.Logs.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self.logger = logging.getLogger()
        self.logger.addHandler(self.Logs)
        self.logger.setLevel(logging.INFO)

        # Customize UI configutation
        self.doubleValidate2 = QDoubleValidator(decimals=2)
        self.doubleValidate6 = QDoubleValidator(decimals=6)
        self.widthForAmountEdit = self.fontMetrics().width("888888888.88") * 1.5
        self.widthForTimestampEdit = self.fontMetrics().width("00/00/0000 00:00:00") * 1.25
        self.ui_config = TableViewConfig(self)
        self.ui_config.configure_all()

        self.operation_details = {
            TRANSACTION_ACTION: ('Transaction', self.ui_config.mappers[self.ui_config.ACTIONS], 'actions', self.ActionDetailsTableView, 'action_details'),
            TRANSACTION_TRADE: ('Trade', self.ui_config.mappers[self.ui_config.TRADES], 'trades', None, None),
            TRANSACTION_DIVIDEND: ('Dividend', self.ui_config.mappers[self.ui_config.DIVIDENDS], 'dividends', None, None),
            TRANSACTION_TRANSFER: ('Transfer', self.ui_config.mappers[self.ui_config.TRANSFERS], 'transfers_combined', None, None)
        }
        self.operations = LedgerOperationsView(self.OperationsTableView, self.operation_details)
        self.operations.activateOperationView.connect(self.ShowOperationTab)
        self.operations.stateIsCommitted.connect(self.showCommitted)

        self.ActionsDataMapper = self.ui_config.mappers[self.ui_config.ACTIONS]
        self.TradesDataMapper = self.ui_config.mappers[self.ui_config.TRADES]
        self.DividendsDataMapper = self.ui_config.mappers[self.ui_config.DIVIDENDS]
        self.TransfersDataMapper = self.ui_config.mappers[self.ui_config.TRANSFERS]

        # Setup balance table
        self.balance_currency = get_base_currency(self.db)
        self.balance_date = QtCore.QDateTime.currentSecsSinceEpoch()
        self.balance_active_only = 1
        self.BalanceDate.setDateTime(QtCore.QDateTime.currentDateTime())
        self.BalancesCurrencyCombo.init_db(self.db)   # this line will trigger onBalanceDateChange -> view updated

        # Setup holdings table
        self.holdings_currency = self.balance_currency
        self.holdings_date = QtCore.QDateTime.currentSecsSinceEpoch()
        self.HoldingsDate.setDateTime(QtCore.QDateTime.currentDateTime())
        self.HoldingsCurrencyCombo.init_db(self.db)   # and this will trigger onHoldingsDateChange -> view updated

        self.ChooseAccountBtn.init_db(self.db)
        # Setup operations table
        # self.operations_since_timestamp = 0
        self.current_index = None
        self.OperationsTableView.setContextMenuPolicy(Qt.CustomContextMenu)
        self.NewOperationMenu = QMenu()
        self.NewOperationMenu.addAction('Income / Spending', partial(self.operations.addNewOperation, TRANSACTION_ACTION))
        self.NewOperationMenu.addAction('Transfer', partial(self.operations.addNewOperation, TRANSACTION_TRANSFER))
        self.NewOperationMenu.addAction('Buy / Sell', partial(self.operations.addNewOperation, TRANSACTION_TRADE))
        self.NewOperationMenu.addAction('Dividend', partial(self.operations.addNewOperation, TRANSACTION_DIVIDEND))
        self.NewOperationBtn.setMenu(self.NewOperationMenu)
        # next line forces usage of sizeHint() from delegate
        self.OperationsTableView.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

        self.ActionDetailsTableView.horizontalHeader().moveSection(self.ActionDetailsTableView.model().fieldIndex("note"),
                                                                   self.ActionDetailsTableView.model().fieldIndex("name"))
        self.OperationsTableView.selectionModel().selectionChanged.connect(self.OnOperationChange)
        self.OperationsTableView.selectRow(0)
        self.OnOperationsRangeChange(0)

    def closeEvent(self, event):
        self.logger.removeHandler(self.Logs)    # Removing handler (but it doesn't prevent exception at exit)
        logging.raiseExceptions = False         # Silencing logging module exceptions
        self.db.close()                         # Closing database file

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
            QtWidgets.QApplication.instance().quit()

    @Slot()
    def onBalanceDateChange(self, _new_date):
        self.balance_date = self.BalanceDate.dateTime().toSecsSinceEpoch()
        self.UpdateBalances()

    @Slot()
    def onHoldingsDateChange(self, _new_date):
        self.holdings_date = self.HoldingsDate.dateTime().toSecsSinceEpoch()
        self.UpdateHoldings()

    @Slot()
    def OnBalanceCurrencyChange(self, currency_index):
        self.balance_currency = self.BalancesCurrencyCombo.selected_currency()
        balances_model = self.BalancesTableView.model()
        balances_model.setHeaderData(balances_model.fieldIndex("balance_adj"), Qt.Horizontal,
                                     "Balance, " + self.BalancesCurrencyCombo.selected_currency_name())
        self.UpdateBalances()

    @Slot()
    def OnHoldingsCurrencyChange(self, currency_index):
        self.holdings_currency = self.HoldingsCurrencyCombo.selected_currency()
        holidings_model = self.HoldingsTableView.model()
        holidings_model.setHeaderData(holidings_model.fieldIndex("value_adj"), Qt.Horizontal,
                                      "Value, " + self.HoldingsCurrencyCombo.selected_currency_name())
        self.UpdateHoldings()

    @Slot()
    def OnBalanceInactiveChange(self, state):
        if state == 0:
            self.balance_active_only = 1
        else:
            self.balance_active_only = 0
        self.UpdateBalances()

    def UpdateBalances(self):
        self.ledger.BuildBalancesTable(self.balance_date, self.balance_currency, self.balance_active_only)
        self.BalancesTableView.model().select()

    @Slot()
    def UpdateHoldings(self):
        self.ledger.BuildHoldingsTable(self.holdings_date, self.holdings_currency)
        holidings_model = self.HoldingsTableView.model()
        holidings_model.select()
        for row in range(holidings_model.rowCount()):
            if holidings_model.data(holidings_model.index(row, 1)):
                self.HoldingsTableView.setSpan(row, 3, 1, 3)
        self.HoldingsTableView.show()


    @Slot()
    def OnOperationChange(self, selected, _deselected):
        self.CheckForNotSavedData()

        ##################################################################
        # UPDATE VIEW FOR NEW SELECTED TRANSACTION                       #
        ##################################################################
        idx = selected.indexes()
        if idx:
            selected_row = idx[0].row()
            operations_table = self.OperationsTableView.model()
            operation_type = operations_table.record(selected_row).value(operations_table.fieldIndex("type"))
            operation_id = operations_table.record(selected_row).value(operations_table.fieldIndex("id"))
            if operation_type == TRANSACTION_ACTION:
                self.ActionsDataMapper.model().setFilter(f"actions.id = {operation_id}")
                self.ActionsDataMapper.setCurrentModelIndex(self.ActionsDataMapper.model().index(0, 0))
                self.OperationsTabs.setCurrentIndex(TAB_ACTION)
                self.ActionDetailsTableView.model().setFilter(f"action_details.pid = {operation_id}")
            elif operation_type == TRANSACTION_DIVIDEND:
                self.OperationsTabs.setCurrentIndex(TAB_DIVIDEND)
                self.DividendsDataMapper.model().setFilter(f"dividends.id = {operation_id}")
                self.DividendsDataMapper.setCurrentModelIndex(self.DividendsDataMapper.model().index(0, 0))
            elif operation_type == TRANSACTION_TRADE:
                self.OperationsTabs.setCurrentIndex(TAB_TRADE)
                self.TradesDataMapper.model().setFilter(f"trades.id = {operation_id}")
                self.TradesDataMapper.setCurrentModelIndex(self.TradesDataMapper.model().index(0, 0))
            elif operation_type == TRANSACTION_TRANSFER:
                self.OperationsTabs.setCurrentIndex(TAB_TRANSFER)
                self.TransfersDataMapper.model().setFilter(f"transfers_combined.id = {operation_id}")
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
        if self.ActionsDataMapper.model().isDirty() or self.ActionDetailsTableView.model().isDirty():
            reply = QMessageBox().warning(self, self.tr("You have unsaved changes"),
                                          self.tr("Transaction has uncommitted changes,\ndo you want to save it?"),
                                          QMessageBox.Yes, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.SubmitChangesForTab(TAB_ACTION)
            else:
                self.RevertChangesForTab(TAB_ACTION)
        if self.DividendsDataMapper.model().isDirty():
            reply = QMessageBox().warning(self, self.tr("You have unsaved changes"),
                                          self.tr("Dividend has uncommitted changes,\ndo you want to save it?"),
                                          QMessageBox.Yes, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.SubmitChangesForTab(TAB_DIVIDEND)
            else:
                self.RevertChangesForTab(TAB_DIVIDEND)
        if self.TradesDataMapper.model().isDirty():
            reply = QMessageBox().warning(self, self.tr("You have unsaved changes"),
                                          self.tr("Trade has uncommitted changes,\ndo you want to save it?"),
                                          QMessageBox.Yes, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.SubmitChangesForTab(TAB_TRADE)
            else:
                self.RevertChangesForTab(TAB_TRADE)
        if self.TransfersDataMapper.model().isDirty():
            reply = QMessageBox().warning(self, self.tr("You have unsaved changes"),
                                          self.tr("Transfer has uncommitted changes,\ndo you want to save it?"),
                                          QMessageBox.Yes, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.SubmitChangesForTab(TAB_TRANSFER)
            else:
                self.RevertChangesForTab(TAB_TRANSFER)

    # def SetOperationsFilter(self):
        # operations_filter = ""
        # if self.operations_since_timestamp > 0:
        #     operations_filter = "all_operations.timestamp >= {}".format(self.operations_since_timestamp)
        #
        # if self.ChooseAccountBtn.account_id != 0:
        #     if operations_filter == "":
        #         operations_filter = "all_operations.account_id = {}".format(self.ChooseAccountBtn.account_id)
        #     else:
        #         operations_filter = operations_filter + " AND all_operations.account_id = {}".format(
        #             self.ChooseAccountBtn.account_id)
        #
        # if self.SearchString.text():
        #     operations_filter = operations_filter + " AND (num_peer LIKE '%{}%' OR asset LIKE '%{}%')".format(
        #         self.SearchString.text(), self.SearchString.text())
        #
        # self.OperationsTableView.model().setFilter(operations_filter)

    @Slot()
    def OnAccountChange(self):
        self.operations.setAccount(self.ChooseAccountBtn.account_id)

    def OnSearchTextChange(self):
        self.operations.setSearchText(self.SearchString.text())

    @Slot()
    def OnOperationsRangeChange(self, range_index):
        operations_since_timestamp = 0
        if range_index == 0:  # last week
            operations_since_timestamp = QtCore.QDateTime.currentDateTime().toSecsSinceEpoch() - 604800
        elif range_index == 1:  # last month
            operations_since_timestamp = QtCore.QDateTime.currentDateTime().toSecsSinceEpoch() - 2678400
        elif range_index == 2:  # last half-year
            operations_since_timestamp = QtCore.QDateTime.currentDateTime().toSecsSinceEpoch() - 7905600
        elif range_index == 3:  # last year
            operations_since_timestamp = QtCore.QDateTime.currentDateTime().toSecsSinceEpoch() - 31536000
        # self.SetOperationsFilter()
        self.operations.setOperationsRange(operations_since_timestamp)

    # def emit_before_mapper_commit(self, operation_type):
    #     if operation_type == TRANSACTION_TRANSFER:
    #         transfer_mapper = self.op_details[operation_type][self.OP_MAPPER]
    #         record = transfer_mapper.model().record(0)
    #         note = record.value(transfer_mapper.model().fieldIndex("note"))
    #         if not note:  # If we don't have note - set it to NULL value to fire DB trigger
    #             transfer_mapper.model().setData(transfer_mapper.model().index(0, transfer_mapper.model().fieldIndex("note")), None)
    #         fee_amount = record.value(transfer_mapper.model().fieldIndex("fee_amount"))
    #         if not fee_amount:
    #             fee_amount = 0
    #         if abs(float(fee_amount)) < CALC_TOLERANCE:  # If we don't have fee - set Fee Account to NULL to fire DB trigger
    #             transfer_mapper.model().setData(transfer_mapper.model().index(0, transfer_mapper.model().fieldIndex("fee_acc_id")), None)
    #
    # def emit_before_view_commit(self, operation_type):
    #     if operation_type == TRANSACTION_ACTION:
    #         actions_mapper = self.op_details[operation_type][self.OP_MAPPER]
    #         pid = actions_mapper.model().data(actions_mapper.model().index(0, actions_mapper.model().fieldIndex("id")))
    #         if pid is None:  # we just have saved new action record (mapper submitAll() is called before this signal)
    #             pid = actions_mapper.model().query().lastInsertId()
    #         action_details_view = self.op_details[operation_type][self.OP_CHILD_VIEW]
    #         for row in range(action_details_view.model().rowCount()):
    #             action_details_view.model().setData(action_details_view.model().index(row, 1), pid)

    # def commit_operation(self, operation_type):
    #     self.emit_before_mapper_commit(operation_type)
    #     if self.op_details[operation_type][self.OP_MAPPER]:  # if mapper defined for operation type
    #         if not self.op_details[operation_type][self.OP_MAPPER].model().submitAll():
    #             logging.fatal(
    #                 self.tr("Action submit failed: ") + self.op_details[operation_type][self.OP_MAPPER].model().lastError().text())
    #             return
    #
    #     self.emit_before_view_commit(operation_type)
    #     if self.op_details[operation_type][self.OP_CHILD_VIEW]:  # if mapper defined for operation type
    #         if not self.op_details[operation_type][self.OP_CHILD_VIEW].model().submitAll():
    #             logging.fatal(
    #                 self.tr("Action details submit failed: ") + self.op_details[operation_type][self.OP_CHILD_VIEW].model().lastError().text())
    #             return
    #     self.emit_clean()
    #     self.ledger.MakeUpToDate()
    #     self.OperationsTableView.model().select()



    # def revert_operation(self, operation_type):
    #     if self.op_details[operation_type][self.OP_MAPPER]:  # if mapper defined for operation type
    #         self.op_details[operation_type][self.OP_MAPPER].model().revertAll()
    #     if self.op_details[operation_type][self.OP_CHILD_VIEW]:  # if mapper defined for operation type
    #         self.op_details[operation_type][self.OP_CHILD_VIEW].model().revertAll()
    #     self.emit_clean()

    # def ask_to_commit_changes(self, operation_type):
    #     reply = QMessageBox().warning(None, "You have unsaved changes",
    #                                   self.op_details[operation_type][self.OP_NAME] +
    #                                   " has uncommitted changes,\ndo you want to save it?",
    #                                   QMessageBox.Yes, QMessageBox.No)
    #     if reply == QMessageBox.Yes:
    #         self.commit_operation(operation_type)
    #     else:
    #         self.revert_operation(operation_type)

    # def check_and_commit_changes(self):
    #     for operation_type in self.op_details:
    #         if self.op_details[operation_type][self.OP_MAPPER]:   # if mapper defined for operation type
    #             if self.op_details[operation_type][self.OP_MAPPER].model().isDirty():
    #                 self.ask_to_commit_changes(operation_type)
    #         if self.op_details[operation_type][self.OP_CHILD_VIEW]:     # if view defined for operatation type
    #             if self.op_details[operation_type][self.OP_CHILD_VIEW].model().isDirty():
    #                 self.ask_to_commit_changes(operation_type)

    # def create_new_details(self, operation_type):
    #     view = self.op_details[operation_type][self.OP_CHILD_VIEW]
    #     if view:
    #         view.model().setFilter(f"{self.op_details[operation_type][self.OP_CHILD_TABLE]}.pid = 0")

    # def emit_prepare_new_record(self, operation_type, new_record):
    #     if operation_type == TRANSACTION_ACTION or operation_type == TRANSACTION_TRADE or operation_type == TRANSACTION_DIVIDEND:
    #         new_record.setValue("timestamp", QtCore.QDateTime.currentSecsSinceEpoch())
    #         if self.ChooseAccountBtn.account_id != 0:
    #             new_record.setValue("account_id", self.ChooseAccountBtn.account_id)
    #     if operation_type == TRANSACTION_TRANSFER:
    #         new_record.setValue("from_timestamp", QtCore.QDateTime.currentSecsSinceEpoch())
    #         if self.ChooseAccountBtn.account_id != 0:
    #             new_record.setValue("from_acc_id", self.ChooseAccountBtn.account_id)
    #         new_record.setValue("to_timestamp", QtCore.QDateTime.currentSecsSinceEpoch())
    #         new_record.setValue("fee_timestamp", 0)

    # def CreateNewOperation(self, operation_type):
    #     self.check_and_commit_changes()
    #     self.OperationsTabs.setCurrentIndex(self.op_details[operation_type][self.OP_TAB])
    #     mapper = self.op_details[operation_type][self.OP_MAPPER]
    #     mapper.submit()
    #     mapper.model().setFilter(f"{self.op_details[operation_type][self.OP_MAPPER_TABLE]}.id = 0")
    #     new_record = mapper.model().record()
    #     self.emit_prepare_new_record(operation_type, new_record)
    #     assert mapper.model().insertRows(0, 1)
    #     mapper.model().setRecord(0, new_record)
    #     mapper.toLast()
    #     self.create_new_details(operation_type)

    # def CreateNewAction(self, action_type):
    #     self.CheckForNotSavedData()
    #     self.OperationsTabs.setCurrentIndex(TAB_ACTION)
    #     self.ActionsDataMapper.submit()
    #     self.ActionsDataMapper.model().setFilter("actions.id = 0")
    #     new_record = self.ActionsDataMapper.model().record()
    #
    #     new_record.setValue("timestamp", QtCore.QDateTime.currentSecsSinceEpoch())
    #     if self.ChooseAccountBtn.account_id != 0:
    #         new_record.setValue("account_id", self.ChooseAccountBtn.account_id)
    #
    #     assert self.ActionsDataMapper.model().insertRows(0, 1)
    #     self.ActionsDataMapper.model().setRecord(0, new_record)
    #     self.ActionsDataMapper.toLast()
    #     self.ActionDetailsTableView.model().setFilter("action_details.pid = 0")
    #
    # def CreateNewTransfer(self, action_type):
    #     self.CheckForNotSavedData()
    #     self.OperationsTabs.setCurrentIndex(TAB_TRANSFER)
    #     self.TransfersDataMapper.submit()
    #     self.TransfersDataMapper.model().setFilter(f"transfers_combined.id = 0")
    #     new_record = self.TransfersDataMapper.model().record()
    #
    #     new_record.setValue("from_timestamp", QtCore.QDateTime.currentSecsSinceEpoch())
    #     if self.ChooseAccountBtn.account_id != 0:
    #         new_record.setValue("from_acc_id", self.ChooseAccountBtn.account_id)
    #     new_record.setValue("to_timestamp", QtCore.QDateTime.currentSecsSinceEpoch())
    #     new_record.setValue("fee_timestamp", 0)
    #
    #     assert self.TransfersDataMapper.model().insertRows(0, 1)
    #     self.TransfersDataMapper.model().setRecord(0, new_record)
    #     self.TransfersDataMapper.toLast()
    #
    # def CreateNewTrade(self, action_type):
    #     self.CheckForNotSavedData()
    #     self.OperationsTabs.setCurrentIndex(TAB_TRADE)
    #     self.TradesDataMapper.submit()
    #     self.TradesDataMapper.model().setFilter("trades.id = 0")
    #     new_record = self.TradesDataMapper.model().record()
    #
    #     new_record.setValue("timestamp", QtCore.QDateTime.currentSecsSinceEpoch())
    #     if self.ChooseAccountBtn.account_id != 0:
    #         new_record.setValue("account_id", self.ChooseAccountBtn.account_id)
    #
    #     assert self.TradesDataMapper.model().insertRows(0, 1)
    #     self.TradesDataMapper.model().setRecord(0, new_record)
    #     self.TradesDataMapper.toLast()
    #
    # def CreateNewDividend(self, action_type):
    #     self.CheckForNotSavedData()
    #     self.OperationsTabs.setCurrentIndex(TAB_DIVIDEND)
    #     self.DividendsDataMapper.submit()
    #     self.DividendsDataMapper.model().setFilter("dividends.id = 0")
    #     new_record = self.DividendsDataMapper.model().record()
    #
    #     new_record.setValue("timestamp", QtCore.QDateTime.currentSecsSinceEpoch())
    #     if self.ChooseAccountBtn.account_id != 0:
    #         new_record.setValue("account_id", self.ChooseAccountBtn.account_id)
    #
    #     assert self.DividendsDataMapper.model().insertRows(0, 1)
    #     self.DividendsDataMapper.model().setRecord(0, new_record)
    #     self.DividendsDataMapper.toLast()

    @Slot()
    def DeleteOperation(self):
        if QMessageBox().warning(self, self.tr("Confirmation"),
                                 self.tr("Are you sure to delete this transaction?"),
                                 QMessageBox.Yes, QMessageBox.No) == QMessageBox.No:
            return
        index = self.OperationsTableView.currentIndex()
        operations_model = self.OperationsTableView.model()
        operation_type = operations_model.data(operations_model.index(index.row(), 0))
        if operation_type == TRANSACTION_ACTION:
            self.ActionsDataMapper.model().removeRow(0)
            self.ActionsDataMapper.model().submitAll()
        elif operation_type == TRANSACTION_DIVIDEND:
            self.DividendsDataMapper.model().removeRow(0)
            self.DividendsDataMapper.model().submitAll()
        elif operation_type == TRANSACTION_TRADE:
            self.TradesDataMapper.model().removeRow(0)
            self.TradesDataMapper.model().submitAll()
        elif operation_type == TRANSACTION_TRANSFER:
            self.TransfersDataMapper.model().removeRow(0)
            self.TransfersDataMapper.model().submitAll()
        else:
            assert False
        self.ledger.MakeUpToDate()
        operations_model.select()

    @Slot()
    def CopyOperation(self):
        self.CheckForNotSavedData()
        active_tab = self.OperationsTabs.currentIndex()
        if active_tab == TAB_ACTION:
            row = self.ActionsDataMapper.currentIndex()
            operation_id = self.ActionsDataMapper.model().record(row).value(self.ActionsDataMapper.model().fieldIndex("id"))
            self.ActionsDataMapper.submit()
            new_record = self.ActionsDataMapper.model().record(row)
            new_record.setNull("id")
            new_record.setValue("timestamp", QtCore.QDateTime.currentSecsSinceEpoch())
            self.ActionsDataMapper.model().setFilter("actions.id = 0")
            assert self.ActionsDataMapper.model().insertRows(0, 1)
            self.ActionsDataMapper.model().setRecord(0, new_record)
            self.ActionsDataMapper.toLast()
            # Get SQL records of details and insert it into details table
            self.ActionDetailsTableView.model().setFilter("action_details.pid = 0")
            query = QSqlQuery(self.db)
            query.prepare("SELECT * FROM action_details WHERE pid = :pid ORDER BY id DESC")
            query.bindValue(":pid", operation_id)
            query.setForwardOnly(True)
            assert query.exec_()
            while query.next():
                new_record = query.record()
                new_record.setNull("id")
                new_record.setNull("pid")
                assert self.ActionDetailsTableView.model().insertRows(0, 1)
                self.ActionDetailsTableView.model().setRecord(0, new_record)
        elif active_tab == TAB_TRANSFER:
            row = self.TransfersDataMapper.currentIndex()
            self.TransfersDataMapper.submit()
            new_record = self.TransfersDataMapper.model().record(row)
            new_record.setNull("id")
            new_record.setValue("from_timestamp", QtCore.QDateTime.currentSecsSinceEpoch())
            new_record.setValue("to_timestamp", QtCore.QDateTime.currentSecsSinceEpoch())
            new_record.setValue("fee_timestamp", 0)
            self.TransfersDataMapper.model().setFilter(f"transfers_combined.id = 0")
            assert self.TransfersDataMapper.model().insertRows(0, 1)
            self.TransfersDataMapper.model().setRecord(0, new_record)
            self.TransfersDataMapper.toLast()
        elif active_tab == TAB_DIVIDEND:
            row = self.DividendsDataMapper.currentIndex()
            self.DividendsDataMapper.submit()
            new_record = self.DividendsDataMapper.model().record(row)
            new_record.setNull("id")
            new_record.setValue("timestamp", QtCore.QDateTime.currentSecsSinceEpoch())
            self.DividendsDataMapper.model().setFilter("dividends.id = 0")
            assert self.DividendsDataMapper.model().insertRows(0, 1)
            self.DividendsDataMapper.model().setRecord(0, new_record)
            self.DividendsDataMapper.toLast()
        elif active_tab == TAB_TRADE:
            row = self.TradesDataMapper.currentIndex()
            self.TradesDataMapper.submit()
            new_record = self.TradesDataMapper.model().record(row)
            new_record.setNull("id")
            new_record.setValue("timestamp", QtCore.QDateTime.currentSecsSinceEpoch())
            self.TradesDataMapper.model().setFilter("trades.id = 0")
            assert self.TradesDataMapper.model().insertRows(0, 1)
            self.TradesDataMapper.model().setRecord(0, new_record)
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
        if tab2save == TAB_ACTION:
            if not self.ActionsDataMapper.model().submitAll():
                logging.fatal(self.tr("Action submit failed: ") + self.ActionDetailsTableView.model().lastError().text())
                return

            pid = self.ActionsDataMapper.model().data(
                self.ActionsDataMapper.model().index(0, self.ActionsDataMapper.model().fieldIndex("id")))
            if pid is None:  # we have saved new action record
                pid = self.ActionsDataMapper.model().query().lastInsertId()
            for row in range(self.ActionDetailsTableView.model().rowCount()):
                self.ActionDetailsTableView.model().setData(self.ActionDetailsTableView.model().index(row, 1), pid)

            if not self.ActionDetailsTableView.model().submitAll():
                logging.fatal(self.tr("Action details submit failed: ") + self.ActionDetailsTableView.model().lastError().text())
                return
        elif tab2save == TAB_TRANSFER:
            record = self.TransfersDataMapper.model().record(0)
            note = record.value(self.TransfersDataMapper.model().fieldIndex("note"))
            if not note:  # If we don't have note - set it to NULL value to fire DB trigger
                self.TransfersDataMapper.model().setData(self.TransfersDataMapper.model().index(0, self.TransfersDataMapper.model().fieldIndex("note")), None)
            fee_amount = record.value(self.TransfersDataMapper.model().fieldIndex("fee_amount"))
            if not fee_amount:
                fee_amount = 0
            if abs(float(
                    fee_amount)) < CALC_TOLERANCE:  # If we don't have fee - set Fee Account to NULL to fire DB trigger
                self.TransfersDataMapper.model().setData(self.TransfersDataMapper.model().index(0, self.TransfersDataMapper.model().fieldIndex("fee_acc_id")),
                                            None)

            if not self.TransfersDataMapper.model().submitAll():
                logging.fatal(self.tr("Transfer submit failed: ") + self.TransfersDataMapper.model().lastError().text())
                return
        elif tab2save == TAB_DIVIDEND:
            if not self.DividendsDataMapper.model().submitAll():
                logging.fatal(self.tr("Dividend submit failed: ") + self.DividendsDataMapper.model().lastError().text())
                return
        elif tab2save == TAB_TRADE:
            if not self.TradesDataMapper.model().submitAll():
                logging.fatal(self.tr("Trade submit failed: ") + self.TradesDataMapper.model().lastError().text())
                return
        else:
            assert False
        self.ledger.MakeUpToDate()
        self.OperationsTableView.model().select()
        self.SaveOperationBtn.setEnabled(False)
        self.RevertOperationBtn.setEnabled(False)

    def RevertChangesForTab(self, tab2revert):
        if tab2revert == TAB_ACTION:
            self.ActionsDataMapper.model().revertAll()
            self.ActionDetailsTableView.model().revertAll()
        elif tab2revert == TAB_TRANSFER:
            self.TransfersDataMapper.model().revertAll()
        elif tab2revert == TAB_DIVIDEND:
            self.DividendsDataMapper.model().revertAll()
        elif tab2revert == TAB_TRADE:
            self.TradesDataMapper.model().revertAll()
        else:
            assert False
        self.SaveOperationBtn.setEnabled(False)
        self.RevertOperationBtn.setEnabled(False)

    @Slot()
    def AddDetail(self):
        new_record = self.ActionDetailsTableView.model().record()
        self.ActionDetailsTableView.model().insertRecord(-1, new_record)

    @Slot()
    def RemoveDetail(self):
        idx = self.ActionDetailsTableView.selectionModel().selection().indexes()
        selected_row = idx[0].row()
        self.ActionDetailsTableView.model().removeRow(selected_row)
        self.ActionDetailsTableView.setRowHidden(selected_row, True)
        self.SaveOperationBtn.setEnabled(True)
        self.RevertOperationBtn.setEnabled(True)

    @Slot()
    def on_data_changed(self):
        self.SaveOperationBtn.setEnabled(True)
        self.RevertOperationBtn.setEnabled(True)

    @Slot()
    def onQuotesDownloadCompletion(self):
        self.StatusBar.showMessage("Quotes download completed", timeout=60000)

    @Slot()
    def onStatementLoaded(self):
        self.StatusBar.showMessage("Statement load completed", timeout=60000)
        self.ledger.MakeUpToDate()

    @Slot()
    def ShowOperationTab(self, operation_type):
        tab_list = {
            TRANSACTION_ACTION: TAB_ACTION,
            TRANSACTION_TRANSFER: TAB_TRANSFER,
            TRANSACTION_TRADE: TAB_TRADE,
            TRANSACTION_DIVIDEND: TAB_DIVIDEND
        }
        self.OperationsTabs.setCurrentIndex(tab_list[operation_type])

    @Slot()
    def showCommitted(self):
        self.SaveOperationBtn.setEnabled(False)
        self.RevertOperationBtn.setEnabled(False)