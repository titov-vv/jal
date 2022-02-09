import os
import base64
import logging
from functools import partial

from PySide6.QtCore import Qt, Slot, QDir, QLocale, QMetaObject
from PySide6.QtGui import QIcon, QActionGroup, QAction
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QProgressBar

from jal import __version__
from jal.ui.ui_main_window import Ui_JAL_MainWindow
from jal.widgets.operations_widget import OperationsWidget
from jal.widgets.tax_widget import TaxWidget
from jal.widgets.helpers import dependency_present
from jal.widgets.reference_dialogs import AccountTypeListDialog, AccountListDialog, AssetListDialog, TagsListDialog,\
    CategoryListDialog, CountryListDialog, QuotesListDialog, PeerListDialog
from jal.constants import Setup
from jal.db.backup_restore import JalBackup
from jal.db.helpers import get_app_path, get_dbfilename, load_icon
from jal.db.db import JalDB
from jal.db.settings import JalSettings
from jal.net.downloader import QuoteDownloader
from jal.db.ledger import Ledger
from jal.data_import.statements import Statements
from jal.reports.reports import Reports
from jal.data_import.slips import ImportSlipDialog


#-----------------------------------------------------------------------------------------------------------------------
class MainWindow(QMainWindow, Ui_JAL_MainWindow):
    def __init__(self, language):
        QMainWindow.__init__(self, None)
        self.running = False
        self.setupUi(self)
        self.restoreGeometry(base64.decodebytes(JalSettings().getValue('WindowGeometry', '').encode('utf-8')))
        self.restoreState(base64.decodebytes(JalSettings().getValue('WindowState', '').encode('utf-8')))

        self.ledger = Ledger()

        # Customize Status bar and logs
        self.ProgressBar = QProgressBar(self)
        self.StatusBar.addPermanentWidget(self.ProgressBar)
        self.ProgressBar.setVisible(False)
        self.ledger.setProgressBar(self, self.ProgressBar)
        self.Logs.setStatusBar(self.StatusBar)
        self.logger = logging.getLogger()
        self.logger.addHandler(self.Logs)
        log_level = os.environ.get('LOGLEVEL', 'INFO').upper()
        self.logger.setLevel(log_level)

        self.currentLanguage = language

        self.downloader = QuoteDownloader()
        self.statements = Statements(self)
        self.reports = Reports(self, self.mdiArea)
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

        self.reportsGroup = QActionGroup(self.menuReports)
        self.createReportsMenu()

        self.setWindowIcon(load_icon("jal.png"))

        self.connect_signals_and_slots()

        self.actionOperations.trigger()

    def connect_signals_and_slots(self):
        self.actionExit.triggered.connect(QApplication.instance().quit)
        self.actionOperations.triggered.connect(self.createOperationsWindow)
        self.actionAbout.triggered.connect(self.showAboutWindow)
        self.langGroup.triggered.connect(self.onLanguageChanged)
        self.statementGroup.triggered.connect(self.statements.load)
        self.reportsGroup.triggered.connect(self.reports.show)
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
        self.PrepareTaxForms.triggered.connect(partial(self.mdiArea.addSubWindow, TaxWidget(self), maximized=True))
        self.downloader.download_completed.connect(self.updateWidgets)
        self.ledger.updated.connect(self.updateWidgets)
        self.statements.load_completed.connect(self.onStatementImport)

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
        JalSettings().setValue('WindowGeometry', base64.encodebytes(self.saveGeometry()).decode('utf-8'))
        JalSettings().setValue('WindowState', base64.encodebytes(self.saveState()).decode('utf-8'))
        self.logger.removeHandler(self.Logs)    # Removing handler (but it doesn't prevent exception at exit)
        logging.raiseExceptions = False         # Silencing logging module exceptions
        super().closeEvent(event)

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

    # Create import menu for all known statements based on self.statements.items values
    def createStatementsImportMenu(self):
        for i, statement in enumerate(self.statements.items):
            statement_name = statement['name'].replace('&', '&&')  # & -> && to prevent shortcut creation
            if statement['icon']:
                statement_icon = load_icon(statement['icon'])
                action = QAction(statement_icon, statement_name, self)
            else:
                action = QAction(statement_name, self)
            action.setData(i)
            self.menuStatement.addAction(action)
            self.statementGroup.addAction(action)

    # Create menu entry for all known reports based on self.reports.sources values
    def createReportsMenu(self):
        for i, report in enumerate(self.reports.items):
            action = QAction(report['name'].replace('&', '&&'), self)  # & -> && to prevent shortcut creation
            action.setData(i)
            self.menuReports.addAction(action)
            self.reportsGroup.addAction(action)

    @Slot()
    def createOperationsWindow(self):
        operations_window = self.mdiArea.addSubWindow(OperationsWidget(self), maximized=True)
        operations_window.widget().dbUpdated.connect(self.ledger.rebuild)

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
    def updateWidgets(self):
        for window in self.mdiArea.subWindowList():
            window.widget().refresh()

    @Slot()
    def onStatementImport(self, timestamp, totals):
        self.ledger.rebuild()
        for account_id in totals:
            for asset_id in totals[account_id]:
                amount = JalDB().get_asset_amount(timestamp, account_id, asset_id)
                if amount is not None:
                    if abs(totals[account_id][asset_id] - amount) <= Setup.DISP_TOLERANCE:
                        JalDB().reconcile_account(account_id, timestamp)
                        self.updateWidgets()
                    else:
                        account = JalDB().get_account_name(account_id)
                        asset = JalDB().get_asset_name(asset_id)
                        logging.warning(self.tr("Statement ending balance doesn't match: ") +
                                        f"{account} / {asset} / {amount} <> {totals[account_id][asset_id]}")
