import os
import logging
from functools import partial

from PySide2.QtCore import Qt, Slot, QDateTime, QDir, QLocale
from PySide2.QtGui import QIcon
from PySide2.QtWidgets import QApplication, QMainWindow, QMenu, QMessageBox, QLabel, QActionGroup, QAction

from jal import __version__
from jal.ui.ui_main_window import Ui_LedgerMainWindow
from jal.ui.ui_abort_window import Ui_AbortWindow
from jal.ui_custom.helpers import g_tr, ManipulateDate, dependency_present
from jal.ui_custom.reference_dialogs import ReferenceDialogs
from jal.constants import TransactionType
from jal.db.backup_restore import JalBackup
from jal.db.helpers import get_dbfilename, executeSQL
from jal.db.settings import JalSettings
from jal.data_import.downloader import QuoteDownloader
from jal.db.ledger import Ledger
from jal.db.balances_model import BalancesModel
from jal.db.holdings_model import HoldingsModel
from jal.db.operations_model import OperationsModel
from jal.reports.reports import Reports, ReportType
from jal.data_import.statements import StatementLoader
from jal.reports.taxes import TaxesRus
from jal.data_import.slips import ImportSlipDialog
from jal.db.tax_estimator import TaxEstimator


#-----------------------------------------------------------------------------------------------------------------------
# This simly displays one message and OK button - to facilitate start-up error communication
class AbortWindow(QMainWindow, Ui_AbortWindow):
    def __init__(self, error):
        QMainWindow.__init__(self, None)
        self.setupUi(self)

        message = error.message
        if error.details:
            message = message + "\n" + error.details
        self.MessageLbl.setText(message)

#-----------------------------------------------------------------------------------------------------------------------
class MainWindow(QMainWindow, Ui_LedgerMainWindow):
    def __init__(self, db, own_path, language):
        QMainWindow.__init__(self, None)
        self.setupUi(self)

        self.db = db  # TODO Get rid of any connection storage as we may get it anytime (example is in JalSettings)
        self.own_path = own_path
        self.currentLanguage = language
        self.current_index = None  # this is used in onOperationContextMenu() to track item for menu

        self.ledger = Ledger(self.db)
        self.downloader = QuoteDownloader(self.db)
        self.downloader.download_completed.connect(self.onQuotesDownloadCompletion)
        self.taxes = TaxesRus(self.db)
        self.statements = StatementLoader(self, self.db)
        self.statements.load_completed.connect(self.onStatementLoaded)
        self.statements.load_failed.connect(self.onStatementLoadFailure)
        self.backup = JalBackup(self, get_dbfilename(self.own_path))
        self.estimator = None

        self.actionImportSlipRU.setEnabled(dependency_present(['pyzbar', 'PIL']))

        # Customize Status bar and logs
        self.NewLogEventLbl = QLabel(self)
        self.StatusBar.addWidget(self.NewLogEventLbl)
        self.Logs.setNotificationLabel(self.NewLogEventLbl)
        self.Logs.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self.logger = logging.getLogger()
        self.logger.addHandler(self.Logs)
        log_level = os.environ.get('LOGLEVEL', 'INFO').upper()
        self.logger.setLevel(log_level)

        # Setup reports tab
        self.ReportAccountBtn.init_db(self.db)
        self.ReportCategoryEdit.init_db(self.db)
        self.reports = Reports(self.db, self.ReportTableView)
        self.reports.report_failure.connect(self.onReportFailure)

        # Customize UI configuration
        self.balances_model = BalancesModel(self.BalancesTableView, self.db)
        self.BalancesTableView.setModel(self.balances_model)
        self.balances_model.configureView()

        self.holdings_model = HoldingsModel(self.HoldingsTableView, self.db)
        self.HoldingsTableView.setModel(self.holdings_model)
        self.holdings_model.configureView()
        self.HoldingsTableView.setContextMenuPolicy(Qt.CustomContextMenu)

        self.operations_model = OperationsModel(self.OperationsTableView, self.db)
        self.OperationsTableView.setModel(self.operations_model)
        self.operations_model.configureView()
        self.OperationsTableView.setContextMenuPolicy(Qt.CustomContextMenu)

        self.reference_dialogs = ReferenceDialogs(self)
        self.connect_signals_and_slots()

        self.NewOperationMenu = QMenu()
        for i in range(self.OperationsTabs.count()):
            if hasattr(self.OperationsTabs.widget(i), "isCustom"):
                self.OperationsTabs.widget(i).init_db(self.db)
                self.OperationsTabs.widget(i).dbUpdated.connect(self.showCommitted)
                self.NewOperationMenu.addAction(self.OperationsTabs.widget(i).name,
                                                partial(self.createOperation, i))
        self.NewOperationBtn.setMenu(self.NewOperationMenu)

        # Setup balance and holdings parameters
        self.BalanceDate.setDateTime(QDateTime.currentDateTime())
        self.BalancesCurrencyCombo.init_db(self.db, JalSettings().getValue('BaseCurrency'))
        self.HoldingsDate.setDateTime(QDateTime.currentDateTime())
        self.HoldingsCurrencyCombo.init_db(self.db, JalSettings().getValue('BaseCurrency'))

        # Create menu for different operations
        self.ChooseAccountBtn.init_db(self.db)

        # Operations view context menu
        self.contextMenu = QMenu(self.OperationsTableView)
        self.actionReconcile = QAction(text=g_tr('MainWindow', "Reconcile"), parent=self)
        self.actionReconcile.triggered.connect(self.reconcileAtCurrentOperation)
        self.actionCopy = QAction(text=g_tr('MainWindow', "Copy"), parent=self)
        self.actionCopy.triggered.connect(self.copyOperation)
        self.actionDelete = QAction(text=g_tr('MainWindow', "Delete"), parent=self)
        self.actionDelete.triggered.connect(self.deleteOperation)
        self.contextMenu.addAction(self.actionReconcile)
        self.contextMenu.addSeparator()
        self.contextMenu.addAction(self.actionCopy)
        self.contextMenu.addAction(self.actionDelete)

        self.actionAbout = QAction(text=g_tr('MainWindow', "Abou&t"), parent=self)
        self.MainMenu.addAction(self.actionAbout)
        self.actionAbout.triggered.connect(self.showAboutWindow)

        self.langGroup = QActionGroup(self.menuLanguage)
        self.createLanguageMenu()
        self.langGroup.triggered.connect(self.onLanguageChanged)

        self.OperationsTabs.setCurrentIndex(TransactionType.NA)
        self.OperationsTableView.selectRow(0)
        self.OnOperationsRangeChange(0)

    def connect_signals_and_slots(self):
        self.actionExit.triggered.connect(QApplication.instance().quit)
        self.action_Load_quotes.triggered.connect(partial(self.downloader.showQuoteDownloadDialog, self))
        self.actionImportStatement.triggered.connect(self.statements.loadReport)
        self.actionImportSlipRU.triggered.connect(self.importSlip)
        self.actionBackup.triggered.connect(self.backup.create)
        self.actionRestore.triggered.connect(self.backup.restore)
        self.action_Re_build_Ledger.triggered.connect(partial(self.ledger.showRebuildDialog, self))
        self.actionAccountTypes.triggered.connect(partial(self.reference_dialogs.show, "account_types"))
        self.actionAccounts.triggered.connect(partial(self.reference_dialogs.show, "accounts"))
        self.actionAssets.triggered.connect(partial(self.reference_dialogs.show, "assets"))
        self.actionPeers.triggered.connect(partial(self.reference_dialogs.show, "agents_ext"))
        self.actionCategories.triggered.connect(partial(self.reference_dialogs.show, "categories_ext"))
        self.actionTags.triggered.connect(partial(self.reference_dialogs.show, "tags"))
        self.actionCountries.triggered.connect(partial(self.reference_dialogs.show, "countries"))
        self.actionQuotes.triggered.connect(partial(self.reference_dialogs.show, "quotes"))
        self.PrepareTaxForms.triggered.connect(partial(self.taxes.showTaxesDialog, self))
        self.BalanceDate.dateChanged.connect(self.BalancesTableView.model().setDate)
        self.HoldingsDate.dateChanged.connect(self.HoldingsTableView.model().setDate)
        self.BalancesCurrencyCombo.changed.connect(self.BalancesTableView.model().setCurrency)
        self.BalancesTableView.doubleClicked.connect(self.OnBalanceDoubleClick)
        self.HoldingsCurrencyCombo.changed.connect(self.HoldingsTableView.model().setCurrency)
        self.ReportRangeCombo.currentIndexChanged.connect(self.onReportRangeChange)
        self.RunReportBtn.clicked.connect(self.onRunReport)
        self.SaveReportBtn.clicked.connect(self.reports.saveReport)
        self.ShowInactiveCheckBox.stateChanged.connect(self.BalancesTableView.model().toggleActive)
        self.DateRangeCombo.currentIndexChanged.connect(self.OnOperationsRangeChange)
        self.ChooseAccountBtn.changed.connect(self.OperationsTableView.model().setAccount)
        self.SearchString.textChanged.connect(self.OperationsTableView.model().filterText)
        self.HoldingsTableView.customContextMenuRequested.connect(self.onHoldingsContextMenu)
        self.OperationsTableView.selectionModel().selectionChanged.connect(self.OnOperationChange)
        self.OperationsTableView.customContextMenuRequested.connect(self.onOperationContextMenu)
        self.DeleteOperationBtn.clicked.connect(self.deleteOperation)
        self.CopyOperationBtn.clicked.connect(self.copyOperation)

    def closeDatabase(self):
        self.db.close()

    @Slot()
    def closeEvent(self, event):
        self.logger.removeHandler(self.Logs)    # Removing handler (but it doesn't prevent exception at exit)
        logging.raiseExceptions = False         # Silencing logging module exceptions
        self.db.close()                         # Closing database file

    def createLanguageMenu(self):
        langPath = self.own_path + "languages" + os.sep

        langDirectory = QDir(langPath)
        for language_file in langDirectory.entryList(['*.qm']):
            language_code = language_file.split('.')[0]
            language = QLocale.languageToString(QLocale(language_code).language())
            language_icon = QIcon(langPath + language_code + '.png')
            action = QAction(language_icon, language, self)
            action.setCheckable(True)
            action.setData(language_code)
            self.menuLanguage.addAction(action)
            self.langGroup.addAction(action)

    @Slot()
    def onLanguageChanged(self, action):
        language_code = action.data()
        if language_code != self.currentLanguage:
            executeSQL(self.db,
                       "UPDATE settings "
                       "SET value=(SELECT id FROM languages WHERE language = :new_language) WHERE name ='Language'",
                       [(':new_language', language_code)])
            QMessageBox().information(self, g_tr('MainWindow', "Restart required"),
                                      g_tr('MainWindow', "Language was changed to ") +
                                      QLocale.languageToString(QLocale(language_code).language()) + "\n" +
                                      g_tr('MainWindow', "You should restart application to apply changes\n"
                                           "Application will be terminated now"),
                                      QMessageBox.Ok)
            self.close()

    @Slot()
    def showAboutWindow(self):
        about_box = QMessageBox(self)
        about_box.setAttribute(Qt.WA_DeleteOnClose)
        about_box.setWindowTitle(g_tr('MainWindow', "About"))
        title = g_tr('MainWindow',
                     "<h3>JAL</h3><p>Just Another Ledger, version {version}</p>".format(version=__version__))
        about_box.setText(title)
        about = g_tr('MainWindow', "<p>Please visit <a href=\"https://github.com/titov-vv/jal\">"
                                   "Github home page</a> for more information</p>")
        about_box.setInformativeText(about)
        about_box.show()

    @Slot()
    def OnBalanceDoubleClick(self, index):
        self.ChooseAccountBtn.account_id = index.model().getAccountId(index.row())

    @Slot()
    def onReportRangeChange(self, range_index):
        report_ranges = {
            0: lambda: (0, 0),
            1: ManipulateDate.Last3Months,
            2: ManipulateDate.RangeYTD,
            3: ManipulateDate.RangeThisYear,
            4: ManipulateDate.RangePreviousYear
        }
        begin, end = report_ranges[range_index]()
        self.ReportFromDate.setDateTime(QDateTime.fromSecsSinceEpoch(begin))
        self.ReportToDate.setDateTime(QDateTime.fromSecsSinceEpoch(end))

    @Slot()
    def onRunReport(self):
        types = {
            0: ReportType.IncomeSpending,
            1: ReportType.ProfitLoss,
            2: ReportType.Deals,
            3: ReportType.ByCategory
        }
        report_type = types[self.ReportTypeCombo.currentIndex()]
        begin = self.ReportFromDate.dateTime().toSecsSinceEpoch()
        end = self.ReportToDate.dateTime().toSecsSinceEpoch()
        group_dates = 1 if self.ReportGroupCheck.isChecked() else 0
        if report_type == ReportType.ByCategory:
            self.reports.runReport(report_type, begin, end, self.ReportCategoryEdit.selected_id, group_dates)
        else:
            self.reports.runReport(report_type, begin, end, self.ReportAccountBtn.account_id, group_dates)

    @Slot()
    def onReportFailure(self, error_msg):
        self.StatusBar.showMessage(error_msg, timeout=30000)

    @Slot()
    def OnOperationsRangeChange(self, range_index):
        view_ranges = {
            0: ManipulateDate.startOfPreviousWeek,
            1: ManipulateDate.startOfPreviousMonth,
            2: ManipulateDate.startOfPreviousQuarter,
            3: ManipulateDate.startOfPreviousYear,
            4: lambda: 0
        }
        self.OperationsTableView.model().setDateRange(view_ranges[range_index]())

    @Slot()
    def onQuotesDownloadCompletion(self):
        self.StatusBar.showMessage(g_tr('MainWindow', "Quotes download completed"), timeout=60000)
        self.balances_model.update()

    @Slot()
    def onStatementLoaded(self):
        self.StatusBar.showMessage(g_tr('MainWindow', "Statement load completed"), timeout=60000)
        self.ledger.rebuild()
        self.balances_model.update()  # FIXME this should be better linked to some signal emitted by ledger after rebuild completion

    @Slot()
    def onStatementLoadFailure(self):
        self.StatusBar.showMessage(g_tr('MainWindow', "Statement load failed"), timeout=60000)

    @Slot()
    def showCommitted(self):
        self.ledger.rebuild()
        self.balances_model.update()   # FIXME this should be better linked to some signal emitted by ledger after rebuild completion

    @Slot()
    def importSlip(self):
        dialog = ImportSlipDialog(self, self.db)
        dialog.show()

    @Slot()
    def onHoldingsContextMenu(self, pos):
        index = self.HoldingsTableView.indexAt(pos)
        contextMenu = QMenu(self.HoldingsTableView)
        actionEstimateTax = QAction(text=g_tr('Ledger', "Estimate Russian Tax"), parent=self.HoldingsTableView)
        actionEstimateTax.triggered.connect(
            partial(self.estimateRussianTax, self.HoldingsTableView.viewport().mapToGlobal(pos), index))
        contextMenu.addAction(actionEstimateTax)
        contextMenu.popup(self.HoldingsTableView.viewport().mapToGlobal(pos))

    @Slot()
    def estimateRussianTax(self, position, index):
        model = index.model()
        account, asset, asset_qty = model.get_data_for_tax(index)
        self.estimator = TaxEstimator(self.db, account, asset, asset_qty, position)
        if self.estimator.ready:
            self.estimator.open()

    @Slot()
    def OnOperationChange(self, selected, _deselected):
        self.checkForUncommittedChanges()

        if len(self.OperationsTableView.selectionModel().selectedRows()) != 1:
            self.OperationsTabs.setCurrentIndex(TransactionType.NA)
        else:
            idx = selected.indexes()
            if idx:
                selected_row = idx[0].row()
                operation_type, operation_id = self.OperationsTableView.model().get_operation(selected_row)
                self.OperationsTabs.setCurrentIndex(operation_type)
                self.OperationsTabs.widget(operation_type).setId(operation_id)

    @Slot()
    def checkForUncommittedChanges(self):
        for i in range(self.OperationsTabs.count()):
            if hasattr(self.OperationsTabs.widget(i), "isCustom") and self.OperationsTabs.widget(i).modified:
                reply = QMessageBox().warning(None,
                                              g_tr('MainWindow', "You have unsaved changes"),
                                              self.OperationsTabs.widget(i).name +
                                              g_tr('MainWindow', " has uncommitted changes,\ndo you want to save it?"),
                                              QMessageBox.Yes, QMessageBox.No)
                if reply == QMessageBox.Yes:
                    self.OperationsTabs.widget(i).saveChanges()
                else:
                    self.OperationsTabs.widget(i).revertChanges()

    @Slot()
    def onOperationContextMenu(self, pos):
        self.current_index = self.OperationsTableView.indexAt(pos)
        if len(self.OperationsTableView.selectionModel().selectedRows()) != 1:
            self.actionReconcile.setEnabled(False)
            self.actionCopy.setEnabled(False)
        else:
            self.actionReconcile.setEnabled(True)
            self.actionCopy.setEnabled(True)
        self.contextMenu.popup(self.OperationsTableView.viewport().mapToGlobal(pos))

    @Slot()
    def reconcileAtCurrentOperation(self):
        self.operations_model.reconcile_operation(self.current_index.row())

    @Slot()
    def deleteOperation(self):
        if QMessageBox().warning(None, g_tr('MainWindow', "Confirmation"),
                                 g_tr('MainWindow', "Are you sure to delete selected transacion(s)?"),
                                 QMessageBox.Yes, QMessageBox.No) == QMessageBox.No:
            return
        rows = []
        for index in self.OperationsTableView.selectionModel().selectedRows():
            rows.append(index.row())
        self.operations_model.deleteRows(rows)
        self.ledger.rebuild()
        self.balances_model.update()  # FIXME this should be better linked to some signal emitted by ledger after rebuild completion

    @Slot()
    def createOperation(self, operation_type):
        self.checkForUncommittedChanges()
        self.OperationsTabs.widget(operation_type).createNew(account_id=self.operations_model.getAccount())
        self.OperationsTabs.setCurrentIndex(operation_type)

    @Slot()
    def copyOperation(self):
        operation_type = self.OperationsTabs.currentIndex()
        if operation_type == TransactionType.NA:
            return
        self.checkForUncommittedChanges()
        self.OperationsTabs.widget(operation_type).copyNew()
