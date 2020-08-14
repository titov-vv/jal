import logging
import os
from functools import partial

from PySide2 import QtCore, QtWidgets
from PySide2.QtCore import Slot
from PySide2.QtGui import QDoubleValidator
from PySide2.QtWidgets import QMainWindow, QFileDialog, QHeaderView, QMenu, QMessageBox, QLabel

from CustomUI.helpers import VLine
from UI.ui_main_window import Ui_LedgerMainWindow
from view_delegate import *
from DB.bulk_db import MakeBackup, RestoreBackup
from DB.helpers import init_and_check_db, get_base_currency
from downloader import QuoteDownloader
from ledger import Ledger
from operations import LedgerOperationsView, LedgerInitValues
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
        self.operations = LedgerOperationsView(self.OperationsTableView)
        self.ui_config = TableViewConfig(self)

        self.ui_config.configure_all()
        self.operation_details = {
            TRANSACTION_ACTION: ('Transaction', self.ui_config.mappers[self.ui_config.ACTIONS], 'actions', self.ActionDetailsTableView, 'action_details', LedgerInitValues[TRANSACTION_ACTION]),
            TRANSACTION_TRADE: ('Trade', self.ui_config.mappers[self.ui_config.TRADES], 'trades', None, None, LedgerInitValues[TRANSACTION_TRADE]),
            TRANSACTION_DIVIDEND: ('Dividend', self.ui_config.mappers[self.ui_config.DIVIDENDS], 'dividends', None, None, LedgerInitValues[TRANSACTION_DIVIDEND]),
            TRANSACTION_TRANSFER: ('Transfer', self.ui_config.mappers[self.ui_config.TRANSFERS], 'transfers_combined', None, None, LedgerInitValues[TRANSACTION_TRANSFER])
        }
        self.operations.setOperationsDetails(self.operation_details)
        self.operations.activateOperationView.connect(self.ShowOperationTab)
        self.operations.stateIsCommitted.connect(self.showCommitted)
        self.operations.stateIsModified.connect(self.showModified)

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
    def OnAccountChange(self):
        self.operations.setAccountId(self.ChooseAccountBtn.account_id)

    def OnSearchTextChange(self):
        self.operations.setSearchText(self.SearchString.text())

    @Slot()
    def OnOperationsRangeChange(self, range_index):
        self.operations.setOperationsRange(self.operations.view_ranges[range_index]())

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
