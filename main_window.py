import logging
import os
from functools import partial

from PySide2 import QtCore, QtWidgets
from PySide2.QtCore import Slot
from PySide2.QtGui import QDoubleValidator
from PySide2.QtWidgets import QMainWindow, QFileDialog, QMenu, QMessageBox, QLabel

from UI.ui_main_window import Ui_LedgerMainWindow
from CustomUI.helpers import VLine, ManipulateDate
from CustomUI.table_view_config import TableViewConfig
from constants import *
from DB.bulk_db import MakeBackup, RestoreBackup
from DB.helpers import init_and_check_db, get_dbfilename
from downloader import QuoteDownloader
from ledger import Ledger
from operations import LedgerOperationsView, LedgerInitValues
from reports import Reports
from statements import StatementLoader
from taxes import TaxesRus


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
        self.operations = LedgerOperationsView(self.OperationsTableView)
        self.ui_config = TableViewConfig(self)

        self.ui_config.configure_all()
        self.operation_details = {
            TRANSACTION_ACTION: (
                'Income / Spending', self.ui_config.mappers[self.ui_config.ACTIONS], 'actions',
                self.ActionDetailsTableView, 'action_details', LedgerInitValues[TRANSACTION_ACTION]),
            TRANSACTION_TRADE: (
                'Trade', self.ui_config.mappers[self.ui_config.TRADES], 'trades', None, None,
                LedgerInitValues[TRANSACTION_TRADE]),
            TRANSACTION_DIVIDEND: (
                'Dividend', self.ui_config.mappers[self.ui_config.DIVIDENDS], 'dividends', None, None,
                LedgerInitValues[TRANSACTION_DIVIDEND]),
            TRANSACTION_TRANSFER: (
                'Transfer', self.ui_config.mappers[self.ui_config.TRANSFERS], 'transfers_combined', None, None,
                LedgerInitValues[TRANSACTION_TRANSFER])
        }
        self.operations.setOperationsDetails(self.operation_details)
        self.operations.activateOperationView.connect(self.ShowOperationTab)
        self.operations.stateIsCommitted.connect(self.showCommitted)
        self.operations.stateIsModified.connect(self.showModified)

        # Setup balance and holdings tables
        self.ledger.setViews(self.BalancesTableView, self.HoldingsTableView)
        self.BalanceDate.setDateTime(QtCore.QDateTime.currentDateTime())
        self.BalancesCurrencyCombo.init_db(self.db)   # this line will trigger onBalanceDateChange -> view updated
        self.HoldingsDate.setDateTime(QtCore.QDateTime.currentDateTime())
        self.HoldingsCurrencyCombo.init_db(self.db)   # and this will trigger onHoldingsDateChange -> view updated

        # Create menu for different operations
        self.ChooseAccountBtn.init_db(self.db)
        self.NewOperationMenu = QMenu()
        for operation in self.operation_details:
            self.NewOperationMenu.addAction(self.operation_details[operation][LedgerOperationsView.OP_NAME],
                                            partial(self.operations.addNewOperation, operation))
        self.NewOperationBtn.setMenu(self.NewOperationMenu)

        self.ActionDetailsTableView.horizontalHeader().moveSection(self.ActionDetailsTableView.model().fieldIndex("note"),
                                                                   self.ActionDetailsTableView.model().fieldIndex("name"))
        self.OperationsTableView.selectRow(0)  # TODO find a way to select last row from self.operations
        self.OnOperationsRangeChange(0)

    @Slot()
    def closeEvent(self, event):
        self.logger.removeHandler(self.Logs)    # Removing handler (but it doesn't prevent exception at exit)
        logging.raiseExceptions = False         # Silencing logging module exceptions
        self.db.close()                         # Closing database file

    def Backup(self):
        backup_directory = QFileDialog.getExistingDirectory(self, "Select directory to save backup")
        if backup_directory:
            MakeBackup(get_dbfilename(self.own_path), backup_directory)

    def Restore(self):
        restore_directory = QFileDialog.getExistingDirectory(self, "Select directory to restore from")
        if restore_directory:
            self.db.close()
            RestoreBackup(get_dbfilename(self.own_path), restore_directory)
            QMessageBox().information(self, self.tr("Data restored"),
                                      self.tr("Database was loaded from the backup.\n"
                                              "Application will be restarted now."),
                                      QMessageBox.Ok)
            QtWidgets.QApplication.instance().quit()

    @Slot()
    def onBalanceDateChange(self, _new_date):
        self.ledger.setBalancesDate(self.BalanceDate.dateTime().toSecsSinceEpoch())

    @Slot()
    def onHoldingsDateChange(self, _new_date):
        self.ledger.setHoldingsDate(self.HoldingsDate.dateTime().toSecsSinceEpoch())

    @Slot()
    def OnBalanceCurrencyChange(self, _currency_index):
        self.ledger.setBalancesCurrency(self.BalancesCurrencyCombo.selected_currency(),
                                        self.BalancesCurrencyCombo.selected_currency_name())

    @Slot()
    def OnHoldingsCurrencyChange(self, _currency_index):
        self.ledger.setHoldingsCurrency(self.HoldingsCurrencyCombo.selected_currency(),
                                        self.HoldingsCurrencyCombo.selected_currency_name())

    @Slot()
    def OnBalanceInactiveChange(self, state):
        if state == 0:
            self.ledger.setActiveBalancesOnly(1)
        else:
            self.ledger.setActiveBalancesOnly(0)

    @Slot()
    def OnAccountChange(self):
        self.operations.setAccountId(self.ChooseAccountBtn.account_id)

    @Slot()
    def OnSearchTextChange(self):
        self.operations.setSearchText(self.SearchString.text())

    @Slot()
    def OnOperationsRangeChange(self, range_index):
        view_ranges = {
            0: ManipulateDate.startOfPreviousWeek,
            1: ManipulateDate.startOfPreviousMonth,
            2: ManipulateDate.startOfPreviousQuarter,
            3: ManipulateDate.startOfPreviousYear,
            4: lambda: 0
        }
        self.operations.setOperationsRange(view_ranges[range_index]())

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
        self.ledger.MakeUpToDate()
        self.SaveOperationBtn.setEnabled(False)
        self.RevertOperationBtn.setEnabled(False)

    @Slot()
    def showModified(self):
        self.SaveOperationBtn.setEnabled(True)
        self.RevertOperationBtn.setEnabled(True)
