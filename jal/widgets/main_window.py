import os
import logging
from functools import partial

from PySide6.QtCore import Qt, Slot, QDateTime, QDir, QLocale
from PySide6.QtGui import QIcon, QActionGroup, QAction
from PySide6.QtWidgets import QApplication, QMainWindow, QMenu, QMessageBox, QLabel, QProgressBar

from jal import __version__
from jal.ui.ui_main_window import Ui_JAL_MainWindow
from jal.widgets.helpers import ManipulateDate, dependency_present
from jal.widgets.reference_dialogs import AccountTypeListDialog, AccountListDialog, AssetListDialog, TagsListDialog,\
    CategoryListDialog, CountryListDialog, QuotesListDialog, PeerListDialog
from jal.constants import Setup, TransactionType
from jal.db.backup_restore import JalBackup
from jal.db.helpers import get_app_path, get_dbfilename, load_icon
from jal.db.db import JalDB
from jal.db.settings import JalSettings
from jal.net.downloader import QuoteDownloader
from jal.db.ledger import Ledger
from jal.db.balances_model import BalancesModel
from jal.db.holdings_model import HoldingsModel
from jal.db.operations_model import OperationsModel
from jal.reports.reports import Reports, ReportType
from jal.data_import.statements import StatementLoader
from jal.reports.taxes import TaxesRus
from jal.data_import.slips import ImportSlipDialog
from jal.db.tax_estimator import TaxEstimator
from jal.widgets.price_chart import ChartWindow


#-----------------------------------------------------------------------------------------------------------------------
class MainWindow(QMainWindow, Ui_JAL_MainWindow):
    def __init__(self, language):
        QMainWindow.__init__(self, None)
        self.setupUi(self)

        self.currentLanguage = language
        self.current_index = None  # this is used in onOperationContextMenu() to track item for menu

        self.ledger = Ledger()
        self.downloader = QuoteDownloader()
        self.taxes = TaxesRus()
        self.statements = StatementLoader()
        self.backup = JalBackup(self, get_dbfilename(get_app_path()))
        self.estimator = None
        self.price_chart = None

        self.actionImportSlipRU.setEnabled(dependency_present(['pyzbar', 'PIL']))

        self.actionAbout = QAction(text=self.tr("About"), parent=self)
        self.MainMenu.addAction(self.actionAbout)

        self.langGroup = QActionGroup(self.menuLanguage)
        self.createLanguageMenu()

        self.statementGroup = QActionGroup(self.menuStatement)
        self.createStatementsImportMenu()

        # Set icons
        self.setWindowIcon(load_icon("jal.png"))
        self.NewOperationBtn.setIcon(load_icon("new.png"))
        self.CopyOperationBtn.setIcon(load_icon("copy.png"))
        self.DeleteOperationBtn.setIcon(load_icon("delete.png"))

        # Operations view context menu
        self.contextMenu = QMenu(self.OperationsTableView)
        self.actionReconcile = QAction(load_icon("reconcile.png"), self.tr("Reconcile"), self)
        self.actionCopy = QAction(load_icon("copy.png"), self.tr("Copy"), self)
        self.actionDelete = QAction(load_icon("delete.png"), self.tr("Delete"), self)
        self.contextMenu.addAction(self.actionReconcile)
        self.contextMenu.addSeparator()
        self.contextMenu.addAction(self.actionCopy)
        self.contextMenu.addAction(self.actionDelete)

        # Customize Status bar and logs
        self.ProgressBar = QProgressBar(self)
        self.StatusBar.addWidget(self.ProgressBar)
        self.ProgressBar.setVisible(False)
        self.ledger.setProgressBar(self, self.ProgressBar)
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
        current_time = QDateTime.currentDateTime()
        current_time.setTimeSpec(Qt.UTC)  # We use UTC everywhere so need to force TZ info
        self.BalanceDate.setDateTime(current_time)
        self.BalancesCurrencyCombo.setIndex(JalSettings().getValue('BaseCurrency'))
        self.HoldingsDate.setDateTime(current_time)
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
        self.statements.load_completed.connect(self.onStatementImport)
        self.ledger.updated.connect(self.balances_model.update)
        self.ledger.updated.connect(self.holdings_model.update)

    @Slot()
    def closeEvent(self, event):
        self.logger.removeHandler(self.Logs)    # Removing handler (but it doesn't prevent exception at exit)
        logging.raiseExceptions = False         # Silencing logging module exceptions

    def createLanguageMenu(self):
        langPath = get_app_path() + Setup.LANG_PATH + os.sep

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
            QMessageBox().information(self, self.tr("Restart required"),
                                      self.tr("Language was changed to ") +
                                      QLocale.languageToString(QLocale(language_code).language()) + "\n" +
                                      self.tr("You should restart application to apply changes\n"
                                           "Application will be terminated now"),
                                      QMessageBox.Ok)
            self.close()

    # Create import menu for all known statements based on self.statements.sources values
    def createStatementsImportMenu(self):
        for i, source in enumerate(self.statements.sources):
            if 'icon' in source:
                source_icon = load_icon(source['icon'])
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
        about_box.setWindowTitle(self.tr("About"))
        title = self.tr("<h3>JAL</h3><p>Just Another Ledger, version {version}</p>".format(version=__version__))
        about_box.setText(title)
        about = self.tr("<p>More information, manuals and problem reports are at "
                        "<a href=https://github.com/titov-vv/jal>github home page</a></p>"
                        "<p>Questions, comments, help or donations:</p>"
                        "<p><a href=mailto:jal@gmx.ru>jal@gmx.ru</a></p>"
                        "<p><a href=https://t.me/jal_support>Telegram</a></p>")
        about_box.setInformativeText(about)
        about_box.show()

    def showProgressBar(self, visible=False):
        self.ProgressBar.setVisible(visible)
        self.centralwidget.setEnabled(not visible)
        self.MainMenu.setEnabled(not visible)

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
        self.ReportFromDate.setDateTime(QDateTime.fromSecsSinceEpoch(begin, spec=Qt.UTC))
        self.ReportToDate.setDateTime(QDateTime.fromSecsSinceEpoch(end, spec=Qt.UTC))

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
        dialog.finished.connect(self.onSlipImportFinished)
        dialog.open()

    @Slot()
    def onSlipImportFinished(self):
        self.ledger.rebuild()

    @Slot()
    def onHoldingsContextMenu(self, pos):
        index = self.HoldingsTableView.indexAt(pos)
        contextMenu = QMenu(self.HoldingsTableView)
        actionShowChart = QAction(text=self.tr("Show Price Chart"), parent=self.HoldingsTableView)
        actionShowChart.triggered.connect(
            partial(self.showPriceChart, self.HoldingsTableView.viewport().mapToGlobal(pos), index))
        contextMenu.addAction(actionShowChart)
        actionEstimateTax = QAction(text=self.tr("Estimate Russian Tax"), parent=self.HoldingsTableView)
        actionEstimateTax.triggered.connect(
            partial(self.estimateRussianTax, self.HoldingsTableView.viewport().mapToGlobal(pos), index))
        contextMenu.addAction(actionEstimateTax)
        contextMenu.popup(self.HoldingsTableView.viewport().mapToGlobal(pos))

    @Slot()
    def showPriceChart(self, position, index):
        model = index.model()
        account, asset, asset_qty = model.get_data_for_tax(index)
        self.price_chart = ChartWindow(account, asset, asset_qty, position)
        if self.price_chart.ready:
            self.price_chart.open()

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
                reply = QMessageBox().warning(None, self.tr("You have unsaved changes"),
                                              self.OperationsTabs.widget(i).name +
                                              self.tr(" has uncommitted changes,\ndo you want to save it?"),
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
        idx = self.operations_model.index(self.current_index.row(), 0)  # we need only row to address fields by name
        timestamp = self.operations_model.data(idx, Qt.UserRole, field="timestamp")
        account_id = self.operations_model.data(idx, Qt.UserRole, field="account_id")
        JalDB().reconcile_account(account_id, timestamp)
        self.operations_model.refresh()

    @Slot()
    def deleteOperation(self):
        if QMessageBox().warning(None, self.tr("Confirmation"),
                                 self.tr("Are you sure to delete selected transacion(s)?"),
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
            AccountTypeListDialog().exec()
        elif dlg_type == "accounts":
            AccountListDialog().exec()
        elif dlg_type == "assets":
            AssetListDialog().exec()
        elif dlg_type == "agents":
            PeerListDialog().exec()
        elif dlg_type == "categories":
            CategoryListDialog().exec()
        elif dlg_type == "tags":
            TagsListDialog().exec()
        elif dlg_type == "countries":
            CountryListDialog().exec()
        elif dlg_type == "quotes":
            QuotesListDialog().exec()
        else:
            assert False

    @Slot()
    def onStatementImport(self, timestamp, totals):
        self.ledger.rebuild()
        for account_id in totals:
            for asset_id in totals[account_id]:
                amount = JalDB().get_asset_amount(timestamp, account_id, asset_id)
                if amount is not None:
                    if abs(totals[account_id][asset_id] - amount) <= Setup.DISP_TOLERANCE:
                        JalDB().reconcile_account(account_id, timestamp)
                        self.balances_model.update()   # Update required to display reconciled
                    else:
                        account = JalDB().get_account_name(account_id)
                        asset = JalDB().get_asset_name(asset_id)
                        logging.warning(self.tr("Statement ending balance doesn't match: ") +
                                        f"{account} / {asset} / {amount} <> {totals[account_id][asset_id]}")
