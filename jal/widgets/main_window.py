import os
import logging
from functools import partial

from PySide2.QtCore import Qt, Slot, QDateTime, QDir, QLocale
from PySide2.QtGui import QIcon
from PySide2.QtWidgets import QApplication, QMainWindow, QMenu, QMessageBox, QLabel, QActionGroup, QAction

from jal import __version__
from jal.ui.ui_main_window import Ui_JAL_MainWindow
from jal.widgets.helpers import g_tr, ManipulateDate, dependency_present
from jal.widgets.reference_dialogs import AccountTypeListDialog, AccountListDialog, AssetListDialog, TagsListDialog,\
    CategoryListDialog, CountryListDialog, QuotesListDialog, PeerListDialog
from jal.constants import TransactionType
from jal.db.backup_restore import JalBackup
from jal.db.helpers import get_dbfilename
from jal.db.update import JalDB
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
class MainWindow(QMainWindow, Ui_JAL_MainWindow):
    def __init__(self, own_path, language):
        QMainWindow.__init__(self, None)
        self.setupUi(self)

        self.own_path = own_path
        self.currentLanguage = language
        self.current_index = None  # this is used in onOperationContextMenu() to track item for menu

        self.ledger = Ledger()
        self.downloader = QuoteDownloader()
        self.taxes = TaxesRus()
        self.statements = StatementLoader()
        self.backup = JalBackup(self, get_dbfilename(self.own_path))
        self.estimator = None

        self.actionImportSlipRU.setEnabled(dependency_present(['pyzbar', 'PIL']))

        self.actionAbout = QAction(text=g_tr('MainWindow', "About"), parent=self)
        self.MainMenu.addAction(self.actionAbout)

        self.langGroup = QActionGroup(self.menuLanguage)
        self.createLanguageMenu()

        self.statementGroup = QActionGroup(self.menuStatement)
        self.createStatementsImportMenu()

        # Operations view context menu
        self.contextMenu = QMenu(self.OperationsTableView)
        self.actionReconcile = QAction(text=g_tr('MainWindow', "Reconcile"), parent=self)
        self.actionCopy = QAction(text=g_tr('MainWindow', "Copy"), parent=self)
        self.actionDelete = QAction(text=g_tr('MainWindow', "Delete"), parent=self)
        self.contextMenu.addAction(self.actionReconcile)
        self.contextMenu.addSeparator()
        self.contextMenu.addAction(self.actionCopy)
        self.contextMenu.addAction(self.actionDelete)

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
        self.reports = Reports(self.ReportTableView, self.ReportTreeView)

        # Customize UI configuration
        self.balances_model = BalancesModel(self.BalancesTableView)
        self.BalancesTableView.setModel(self.balances_model)
        self.balances_model.configureView()

        self.holdings_model = HoldingsModel(self.HoldingsTableView)
        self.HoldingsTableView.setModel(self.holdings_model)
        self.holdings_model.configureView()
        self.HoldingsTableView.setContextMenuPolicy(Qt.CustomContextMenu)

        self.operations_model = OperationsModel(self.OperationsTableView)
        self.OperationsTableView.setModel(self.operations_model)
        self.operations_model.configureView()
        self.OperationsTableView.setContextMenuPolicy(Qt.CustomContextMenu)

        self.connect_signals_and_slots()

        self.NewOperationMenu = QMenu()
        for i in range(self.OperationsTabs.count()):
            if hasattr(self.OperationsTabs.widget(i), "isCustom"):
                self.OperationsTabs.widget(i).dbUpdated.connect(self.ledger.rebuild)
                self.OperationsTabs.widget(i).dbUpdated.connect(self.operations_model.refresh)
                self.NewOperationMenu.addAction(self.OperationsTabs.widget(i).name,
                                                partial(self.createOperation, i))
        self.NewOperationBtn.setMenu(self.NewOperationMenu)

        # Setup balance and holdings parameters
        self.BalanceDate.setDateTime(QDateTime.currentDateTime())
        self.BalancesCurrencyCombo.setIndex(JalSettings().getValue('BaseCurrency'))
        self.HoldingsDate.setDateTime(QDateTime.currentDateTime())
        self.HoldingsCurrencyCombo.setIndex(JalSettings().getValue('BaseCurrency'))

        self.OperationsTabs.setCurrentIndex(TransactionType.NA)
        self.OperationsTableView.selectRow(0)
        self.OnOperationsRangeChange(0)

    def connect_signals_and_slots(self):
        self.actionExit.triggered.connect(QApplication.instance().quit)
        self.actionAbout.triggered.connect(self.showAboutWindow)
        self.langGroup.triggered.connect(self.onLanguageChanged)
        self.statementGroup.triggered.connect(self.statements.load)
        self.actionReconcile.triggered.connect(self.reconcileAtCurrentOperation)
        self.action_Load_quotes.triggered.connect(partial(self.downloader.showQuoteDownloadDialog, self))
        self.actionImportSlipRU.triggered.connect(self.importSlip)
        self.actionBackup.triggered.connect(self.backup.create)
        self.actionRestore.triggered.connect(self.backup.restore)
        self.action_Re_build_Ledger.triggered.connect(partial(self.ledger.showRebuildDialog, self))
        self.actionAccountTypes.triggered.connect(partial(self.onDataDialog, "account_types"))
        self.actionAccounts.triggered.connect(partial(self.onDataDialog, "accounts"))
        self.actionAssets.triggered.connect(partial(self.onDataDialog, "assets"))
        self.actionPeers.triggered.connect(partial(self.onDataDialog, "agents"))
        self.actionCategories.triggered.connect(partial(self.onDataDialog, "categories"))
        self.actionTags.triggered.connect(partial(self.onDataDialog, "tags"))
        self.actionCountries.triggered.connect(partial(self.onDataDialog, "countries"))
        self.actionQuotes.triggered.connect(partial(self.onDataDialog, "quotes"))
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
        self.SearchString.editingFinished.connect(self.updateOperationsFilter)
        self.HoldingsTableView.customContextMenuRequested.connect(self.onHoldingsContextMenu)
        self.OperationsTableView.selectionModel().selectionChanged.connect(self.OnOperationChange)
        self.OperationsTableView.customContextMenuRequested.connect(self.onOperationContextMenu)
        self.DeleteOperationBtn.clicked.connect(self.deleteOperation)
        self.actionDelete.triggered.connect(self.deleteOperation)
        self.CopyOperationBtn.clicked.connect(self.copyOperation)
        self.actionCopy.triggered.connect(self.copyOperation)
        self.downloader.download_completed.connect(self.balances_model.update)
        self.downloader.download_completed.connect(self.holdings_model.update)
        self.statements.load_completed.connect(self.ledger.rebuild)
        self.ledger.updated.connect(self.balances_model.update)
        self.ledger.updated.connect(self.holdings_model.update)

    @Slot()
    def closeEvent(self, event):
        self.logger.removeHandler(self.Logs)    # Removing handler (but it doesn't prevent exception at exit)
        logging.raiseExceptions = False         # Silencing logging module exceptions

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
            JalSettings().setValue('Language', JalDB().get_language_id(language_code))
            QMessageBox().information(self, g_tr('MainWindow', "Restart required"),
                                      g_tr('MainWindow', "Language was changed to ") +
                                      QLocale.languageToString(QLocale(language_code).language()) + "\n" +
                                      g_tr('MainWindow', "You should restart application to apply changes\n"
                                           "Application will be terminated now"),
                                      QMessageBox.Ok)
            self.close()

    # Create import menu for all known statements based on self.statements.sources values
    def createStatementsImportMenu(self):
        for i, source in enumerate(self.statements.sources):
            if 'icon' in source:
                source_icon = QIcon(self.own_path + "img" + os.sep + source['icon'])
                action = QAction(source_icon, source['name'], self)
            else:
                action = QAction(source['name'], self)
            action.setData(i)
            self.menuStatement.addAction(action)
            self.statementGroup.addAction(action)

    @Slot()
    def showAboutWindow(self):
        about_box = QMessageBox(self)
        about_box.setAttribute(Qt.WA_DeleteOnClose)
        about_box.setWindowTitle(g_tr('MainWindow', "About"))
        title = g_tr('MainWindow',
                     "<h3>JAL</h3><p>Just Another Ledger, version {version}</p>".format(version=__version__))
        about_box.setText(title)
        about = g_tr('MainWindow', "<p>More information, manuals and problem reports are at "
                                   "<a href=https://github.com/titov-vv/jal>github home page</a></p>"
                                   "<p>Questions, comments, donations: <a href=mailto:jal@gmx.ru>jal@gmx.ru</a></p>")
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
    def importSlip(self):
        dialog = ImportSlipDialog(self)
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
        self.estimator = TaxEstimator(account, asset, asset_qty, position)
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

    @Slot()
    def updateOperationsFilter(self):
        self.OperationsTableView.model().filterText(self.SearchString.text())

    @Slot()
    def onDataDialog(self, dlg_type):
        if dlg_type == "account_types":
            AccountTypeListDialog().exec_()
        elif dlg_type == "accounts":
            AccountListDialog().exec_()
        elif dlg_type == "assets":
            AssetListDialog().exec_()
        elif dlg_type == "agents":
            PeerListDialog().exec_()
        elif dlg_type == "categories":
            CategoryListDialog().exec_()
        elif dlg_type == "tags":
            TagsListDialog().exec_()
        elif dlg_type == "countries":
            CountryListDialog().exec_()
        elif dlg_type == "quotes":
            QuotesListDialog().exec_()
        else:
            assert False