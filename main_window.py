import logging
import os

from PySide2 import QtCore, QtWidgets
from PySide2.QtCore import Slot
from PySide2.QtGui import QDoubleValidator
from PySide2.QtSql import QSqlQuery
from PySide2.QtWidgets import QMainWindow, QFileDialog, QHeaderView, QMenu, QMessageBox, QAction, QLabel

from CustomUI.helpers import VLine
from CustomUI.reference_data import ReferenceDataDialog, ReferenceTreeDelegate, ReferenceBoolDelegate, \
    ReferenceIntDelegate, ReferenceLookupDelegate, ReferenceTimestampDelegate
from UI.ui_main_window import Ui_LedgerMainWindow
from view_delegate import *
from DB.bulk_db import MakeBackup, RestoreBackup
from DB.helpers import init_and_check_db, get_base_currency
from downloader import QuoteDownloader, QuotesUpdateDialog
from ledger import Ledger
from rebuild_window import RebuildDialog
from reports import Reports, ReportParamsDialog
from statements import StatementLoader
from taxes import TaxesRus, TaxExportDialog
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

        self.balance_currency = get_base_currency(self.db)
        self.holdings_currency = self.balance_currency

        self.ledger = Ledger(self.db)
        self.downloader = QuoteDownloader(self.db)

        self.balance_date = QtCore.QDateTime.currentSecsSinceEpoch()
        self.balance_active_only = 1

        self.holdings_date = QtCore.QDateTime.currentSecsSinceEpoch()

        self.operations_since_timestamp = 0
        self.current_index = None

        # Customize Status bar and logs
        self.NewLogEventLbl = QLabel()
        self.StatusBar.addPermanentWidget(VLine())
        self.StatusBar.addPermanentWidget(self.NewLogEventLbl)
        self.Logs.setNotificationLabel(self.NewLogEventLbl)

        self.doubleValidate2 = QDoubleValidator(decimals=2)
        self.doubleValidate6 = QDoubleValidator(decimals=6)
        self.widthForAmountEdit = self.fontMetrics().width("888888888.88") * 1.5
        self.widthForTimestampEdit = self.fontMetrics().width("00/00/0000 00:00:00") * 1.5
        self.ui_config = TableViewConfig(self)

        self.BalanceDate.setDateTime(QtCore.QDateTime.currentDateTime())
        self.HoldingsDate.setDateTime(QtCore.QDateTime.currentDateTime())

        self.ui_config.configure_all()
        self.ActionsDataMapper = self.ui_config.mappers[self.ui_config.ACTIONS]
        self.TradesDataMapper = self.ui_config.mappers[self.ui_config.TRADES]
        self.DividendsDataMapper = self.ui_config.mappers[self.ui_config.DIVIDENDS]
        self.TransfersDataMapper = self.ui_config.mappers[self.ui_config.TRANSFERS]

        self.BalancesCurrencyCombo.init_db(self.db)
        self.HoldingsCurrencyCombo.init_db(self.db)
        self.ChooseAccountBtn.init_db(self.db)

        self.OperationsTableView.setContextMenuPolicy(Qt.CustomContextMenu)
        self.NewOperationMenu = QMenu()
        self.NewOperationMenu.addAction('Income / Spending', self.CreateNewAction)
        self.NewOperationMenu.addAction('Transfer', self.CreateNewTransfer)
        self.NewOperationMenu.addAction('Buy / Sell', self.CreateNewTrade)
        self.NewOperationMenu.addAction('Dividend', self.CreateNewDividend)
        self.NewOperationBtn.setMenu(self.NewOperationMenu)
        # next line forces usage of sizeHint() from delegate
        self.OperationsTableView.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

        self.ActionDetailsTableView.horizontalHeader().moveSection(self.ActionDetailsTableView.model().fieldIndex("note"),
                                                                   self.ActionDetailsTableView.model().fieldIndex("name"))
        self.OperationsTableView.selectionModel().selectionChanged.connect(self.OnOperationChange)
        self.OperationsTableView.selectRow(0)
        self.OnOperationsRangeChange(0)

        self.Logs.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logging.getLogger().addHandler(self.Logs)
        logging.getLogger().setLevel(logging.INFO)

        self.UpdateBalances()

    def __del__(self):
        if self.db:
            self.db.close()

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

    def ShowRebuildDialog(self):
        query = QSqlQuery(self.db)
        query.exec_("SELECT ledger_frontier FROM frontier")
        query.next()
        current_frontier = query.value(0)
        if current_frontier == '':
            current_frontier = 0

        rebuild_dialog = RebuildDialog(current_frontier)
        rebuild_dialog.setGeometry(self.x() + 64, self.y() + 64, rebuild_dialog.width(), rebuild_dialog.height())
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
        elif tab_index == 2:
            self.Logs.cleanNotification()

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

    def SetOperationsFilter(self):
        operations_filter = ""
        if self.operations_since_timestamp > 0:
            operations_filter = "all_operations.timestamp >= {}".format(self.operations_since_timestamp)

        if self.ChooseAccountBtn.account_id != 0:
            if operations_filter == "":
                operations_filter = "all_operations.account_id = {}".format(self.ChooseAccountBtn.account_id)
            else:
                operations_filter = operations_filter + " AND all_operations.account_id = {}".format(
                    self.ChooseAccountBtn.account_id)

        if self.SearchString.text():
            operations_filter = operations_filter + " AND (num_peer LIKE '%{}%' OR asset LIKE '%{}%')".format(
                self.SearchString.text(), self.SearchString.text())

        self.OperationsTableView.model().setFilter(operations_filter)

    @Slot()
    def OnOperationsRangeChange(self, range_index):
        if range_index == 0:  # last week
            self.operations_since_timestamp = QtCore.QDateTime.currentDateTime().toSecsSinceEpoch() - 604800
        elif range_index == 1:  # last month
            self.operations_since_timestamp = QtCore.QDateTime.currentDateTime().toSecsSinceEpoch() - 2678400
        elif range_index == 2:  # last half-year
            self.operations_since_timestamp = QtCore.QDateTime.currentDateTime().toSecsSinceEpoch() - 15811200
        elif range_index == 3:  # last year
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
        self.ActionsDataMapper.model().setFilter("actions.id = 0")
        new_record = self.ActionsDataMapper.model().record()
        new_record.setValue("timestamp", QtCore.QDateTime.currentSecsSinceEpoch())
        if self.ChooseAccountBtn.account_id != 0:
            new_record.setValue("account_id", self.ChooseAccountBtn.account_id)
        assert self.ActionsDataMapper.model().insertRows(0, 1)
        self.ActionsDataMapper.model().setRecord(0, new_record)
        self.ActionDetailsTableView.model().setFilter("action_details.pid = 0")
        self.ActionsDataMapper.toLast()

    def CreateNewTransfer(self):
        self.CheckForNotSavedData()
        self.OperationsTabs.setCurrentIndex(TAB_TRANSFER)
        self.TransfersDataMapper.submit()
        self.TransfersDataMapper.model().setFilter(f"transfers_combined.id = 0")
        new_record = self.TransfersDataMapper.model().record()
        new_record.setValue("from_timestamp", QtCore.QDateTime.currentSecsSinceEpoch())
        if self.ChooseAccountBtn.account_id != 0:
            new_record.setValue("from_acc_id", self.ChooseAccountBtn.account_id)
        new_record.setValue("to_timestamp", QtCore.QDateTime.currentSecsSinceEpoch())
        new_record.setValue("fee_timestamp", 0)
        assert self.TransfersDataMapper.model().insertRows(0, 1)
        self.TransfersDataMapper.model().setRecord(0, new_record)
        self.TransfersDataMapper.toLast()

    def CreateNewTrade(self):
        self.CheckForNotSavedData()
        self.OperationsTabs.setCurrentIndex(TAB_TRADE)
        self.TradesDataMapper.submit()
        self.TradesDataMapper.model().setFilter("trades.id = 0")
        new_record = self.TradesDataMapper.model().record()
        new_record.setValue("timestamp", QtCore.QDateTime.currentSecsSinceEpoch())
        if self.ChooseAccountBtn.account_id != 0:
            new_record.setValue("account_id", self.ChooseAccountBtn.account_id)
        assert self.TradesDataMapper.model().insertRows(0, 1)
        self.TradesDataMapper.model().setRecord(0, new_record)
        self.TradesDataMapper.toLast()

    def CreateNewDividend(self):
        self.CheckForNotSavedData()
        self.OperationsTabs.setCurrentIndex(TAB_DIVIDEND)
        self.DividendsDataMapper.submit()
        self.DividendsDataMapper.model().setFilter("dividends.id = 0")
        new_record = self.DividendsDataMapper.model().record()
        new_record.setValue("timestamp", QtCore.QDateTime.currentSecsSinceEpoch())
        if self.ChooseAccountBtn.account_id != 0:
            new_record.setValue("account_id", self.ChooseAccountBtn.account_id)
        assert self.DividendsDataMapper.model().insertRows(0, 1)
        self.DividendsDataMapper.model().setRecord(0, new_record)
        self.DividendsDataMapper.toLast()

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
        self.UpdateLedger()
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
            pid = self.ActionsDataMapper.model().data(self.ActionsDataMapper.model().index(0, self.ActionsDataMapper.model().fieldIndex("id")))
            if not self.ActionsDataMapper.model().submitAll():
                logging.fatal(self.tr("Action submit failed: ") + self.ActionDetailsTableView.model().lastError().text())
                return
            if pid == 0:  # we have saved new action record
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
        self.UpdateLedger()
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

    def UpdateLedger(self):
        query = QSqlQuery(self.db)
        query.exec_("SELECT ledger_frontier FROM frontier")
        query.next()
        current_frontier = query.value(0)
        if current_frontier == '':
            current_frontier = 0
        # ask for confirmation if we have less then 15 days unreconciled
        if (QtCore.QDateTime.currentDateTime().toSecsSinceEpoch() - current_frontier) > 1296000:
            if QMessageBox().warning(self, self.tr("Confirmation"),
                                     self.tr("More than 2 weeks require rebuild. Do you want to do it right now?"),
                                     QMessageBox.Yes, QMessageBox.No) == QMessageBox.No:
                return
        self.ledger.MakeUpToDate()

    @Slot()
    def EditAccountTypes(self):
        ReferenceDataDialog(self.db, "account_types",
                            [("id", None, 0, None, None),
                             ("name", "Account Type", -1, Qt.AscendingOrder, None)],
                            title="Account Types"
                            ).exec_()

    @Slot()
    def EditAccounts(self):
        ReferenceDataDialog(self.db, "accounts",
                            [("id", None, 0, None, None),
                             ("name", "Name", -1, Qt.AscendingOrder, None),
                             ("type_id", None, 0, None, None),
                             ("currency_id", "Currency", None, None, ReferenceLookupDelegate),
                             ("active", "Act", 32, None, ReferenceBoolDelegate),
                             ("number", "Account #", None, None, None),
                             ("reconciled_on", "Reconciled @", self.fontMetrics().width("00/00/0000 00:00:00") * 1.1,
                              None, ReferenceTimestampDelegate),
                             ("organization_id", "Bank", None, None, ReferenceLookupDelegate)],
                            title="Assets", search_field="full_name", toggle=("active", "Show inactive"),
                            relations=[("type_id", "account_types", "id", "name", "Account type:"),
                                       ("currency_id", "currencies", "id", "name", None),
                                       ("organization_id", "agents", "id", "name", None)]
                            ).exec_()

    @Slot()
    def EditAssets(self):
        ReferenceDataDialog(self.db, "assets",
                            [("id", None, 0, None, None),
                             ("name", "Symbol", None, Qt.AscendingOrder, None),
                             ("type_id", None, 0, None, None),
                             ("full_name", "Name", -1, None, None),
                             ("isin", "ISIN", None, None, None),
                             ("web_id", "WebID", None, None, None),
                             ("src_id", "Data source", None, None, ReferenceLookupDelegate)],
                            title="Assets", search_field="full_name",
                            relations=[("type_id", "asset_types", "id", "name", "Asset type:"),
                                       ("src_id", "data_sources", "id", "name", None)]
                            ).exec_()

    @Slot()
    def EditPeers(self):
        ReferenceDataDialog(self.db, "agents_ext",
                            [("id", " ", 16, None, ReferenceTreeDelegate),
                             ("pid", None, 0, None, None),
                             ("name", "Name", -1, Qt.AscendingOrder, None),
                             ("location", "Location", None, None, None),
                             ("actions_count", "Docs count", None, None, ReferenceIntDelegate),
                             ("children_count", None, None, None, None)],
                            title="Peers", search_field="name", tree_view=True
                            ).exec_()

    @Slot()
    def EditCategories(self):
        ReferenceDataDialog(self.db, "categories_ext",
                            [("id", " ", 16, None, ReferenceTreeDelegate),
                             ("pid", None, 0, None, None),
                             ("name", "Name", -1, Qt.AscendingOrder, None),
                             ("often", "Often", None, None, ReferenceBoolDelegate),
                             ("special", None, 0, None, None),
                             ("children_count", None, None, None, None)],
                            title="Categories", search_field="name", tree_view=True
                            ).exec_()

    @Slot()
    def EditTags(self):
        ReferenceDataDialog(self.db, "tags",
                            [("id", None, 0, None, None),
                             ("tag", "Tag", -1, Qt.AscendingOrder, None)],
                            title="Tags", search_field="tag"
                            ).exec_()

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
    def UpdateQuotes(self):
        update_dialog = QuotesUpdateDialog()
        update_dialog.setGeometry(self.x() + 64, self.y() + 64, update_dialog.width(), update_dialog.height())
        if update_dialog.exec_():
            self.downloader.UpdateQuotes(update_dialog.getStartDate(), update_dialog.getEndDate(),
                                         update_dialog.getUseProxy())
            self.StatusBar.showMessage("Quotes download completed", timeout=60)

    @Slot()
    def loadReportIBKR(self):
        report_file, active_filter = \
            QFileDialog.getOpenFileName(self, self.tr("Select Interactive Brokers Flex-query to import"), ".",
                                        self.tr("IBKR flex-query (*.xml);;Quik HTML-report (*.htm)"))
        if report_file:
            report_loader = StatementLoader(self.db)
            if active_filter == self.tr("IBKR flex-query (*.xml)"):
                report_loader.loadIBFlex(report_file)
            if active_filter == self.tr("Quik HTML-report (*.htm)"):
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
        tax_export_dialog.setGeometry(self.x() + 64, self.y() + 64, tax_export_dialog.width(),
                                      tax_export_dialog.height())
        if tax_export_dialog.exec_():
            taxes = TaxesRus(self.db)
            taxes.save2file(tax_export_dialog.filename, tax_export_dialog.year, tax_export_dialog.account)
