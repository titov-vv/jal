import os
import logging
from functools import partial

from PySide6.QtCore import Qt, Slot, QDateTime, QDir, QLocale, QMetaObject
from PySide6.QtGui import QIcon, QActionGroup, QAction
from PySide6.QtWidgets import QApplication, QMainWindow, QMenu, QMessageBox, QLabel, QProgressBar

from jal import __version__
from jal.ui.ui_main_window import Ui_JAL_MainWindow
from jal.widgets.operations_widget import OperationsWidget
from jal.widgets.holdings_widget import HoldingsWidget
from jal.widgets.helpers import ManipulateDate, dependency_present
from jal.widgets.reference_dialogs import AccountTypeListDialog, AccountListDialog, AssetListDialog, TagsListDialog,\
    CategoryListDialog, CountryListDialog, QuotesListDialog, PeerListDialog
from jal.constants import Setup
from jal.db.backup_restore import JalBackup
from jal.db.helpers import get_app_path, get_dbfilename, load_icon
from jal.db.db import JalDB
from jal.db.settings import JalSettings
from jal.net.downloader import QuoteDownloader
from jal.db.ledger import Ledger
from jal.reports.reports import Reports, ReportType
from jal.data_import.statements import StatementLoader
from data_export.taxes import TaxesRus
from jal.data_import.slips import ImportSlipDialog
from jal.widgets.log_viewer import LogViewer


#-----------------------------------------------------------------------------------------------------------------------
class MainWindow(QMainWindow, Ui_JAL_MainWindow):
    def __init__(self, language):
        QMainWindow.__init__(self, None)
        self.running = False
        self.setupUi(self)

        self.ledger = Ledger()   # FIXME - check that ledger should live in main window (not in operations)

        self.ops = self.mdiArea.addSubWindow(self.MainTabs)
        self.ops.setWindowTitle("Balance & Operations OLD")

        self.operations_balance_window = OperationsWidget(self.ledger, self)
        self.mdiArea.addSubWindow(self.operations_balance_window)
        self.holdings_window = HoldingsWidget(self.ledger, self)
        self.mdiArea.addSubWindow(self.holdings_window)
        self.Logs = LogViewer(self)
        self.mdiArea.addSubWindow(self.Logs)

        self.currentLanguage = language

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

        self.setWindowIcon(load_icon("jal.png"))

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

        self.connect_signals_and_slots()

    def connect_signals_and_slots(self):
        self.actionExit.triggered.connect(QApplication.instance().quit)
        self.actionAbout.triggered.connect(self.showAboutWindow)
        self.langGroup.triggered.connect(self.onLanguageChanged)
        self.statementGroup.triggered.connect(self.statements.load)
        self.action_LoadQuotes.triggered.connect(partial(self.downloader.showQuoteDownloadDialog, self))
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
        self.ReportRangeCombo.currentIndexChanged.connect(self.onReportRangeChange)
        self.RunReportBtn.clicked.connect(self.onRunReport)
        self.SaveReportBtn.clicked.connect(self.reports.saveReport)
        # self.downloader.download_completed.connect(self.balances_model.update)  # FIXME
        # self.downloader.download_completed.connect(self.holdings_model.update)
        self.statements.load_completed.connect(self.onStatementImport)
        # self.ledger.updated.connect(self.balances_model.update)   # FIXME
        # self.ledger.updated.connect(self.holdings_model.update)

    @Slot()
    def showEvent(self, event):
        super().showEvent(event)
        if self.running:
            return
        self.running = True
        # Call slot via queued connection so it's called from the UI thread after the window has been shown
        QMetaObject().invokeMethod(self, "afterShowEvent", Qt.ConnectionType.QueuedConnection)

    @Slot()
    def afterShowEvent(self):
        if JalSettings().getValue('RebuildDB', 0) == 1:
            if QMessageBox().warning(self, self.tr("Confirmation"), self.tr("Ledger isn't complete. Rebuild it now?"),
                                     QMessageBox.Yes, QMessageBox.No) == QMessageBox.Yes:
                self.ledger.rebuild()

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
    def importSlip(self):
        dialog = ImportSlipDialog(self)
        dialog.finished.connect(self.onSlipImportFinished)
        dialog.open()

    @Slot()
    def onSlipImportFinished(self):
        self.ledger.rebuild()

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
