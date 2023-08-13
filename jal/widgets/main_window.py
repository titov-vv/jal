import json
import os
import base64
import logging
from math import log10
from decimal import Decimal
from functools import partial

from PySide6.QtCore import Qt, Slot, QDir, QLocale, QMetaObject
from PySide6.QtGui import QActionGroup, QAction
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QProgressBar, QMenu

from jal import __version__
from jal.ui.ui_main_window import Ui_JAL_MainWindow
from jal.widgets.operations_widget import OperationsWidget
from jal.widgets.tax_widget import TaxWidget, MoneyFlowWidget
from jal.widgets.helpers import dependency_present
from jal.widgets.reference_dialogs import AccountListDialog, AssetListDialog, TagsListDialog,\
    CategoryListDialog, QuotesListDialog, PeerListDialog, BaseCurrencyDialog
from jal.constants import Setup
from jal.db.backup_restore import JalBackup
from jal.db.helpers import get_app_path, get_dbfilename, load_icon
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.settings import JalSettings
from jal.net.downloader import QuoteDownloader
from jal.db.ledger import Ledger
from jal.data_import.statements import Statements
from jal.reports.reports import Reports
from jal.data_import.shop_receipt import ImportReceiptDialog


#-----------------------------------------------------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self, language):
        super().__init__()
        self.running = False
        self.ui = Ui_JAL_MainWindow()
        self.ui.setupUi(self)
        self.restoreGeometry(base64.decodebytes(JalSettings().getValue('WindowGeometry', '').encode('utf-8')))
        self.restoreState(base64.decodebytes(JalSettings().getValue('WindowState', '').encode('utf-8')))

        self.ledger = Ledger()

        # Customize Status bar and logs
        self.ProgressBar = QProgressBar(self)
        self.ui.StatusBar.addPermanentWidget(self.ProgressBar)
        self.ProgressBar.setVisible(False)
        self.ledger.setProgressBar(self, self.ProgressBar)
        self.ui.Logs.setStatusBar(self.ui.StatusBar)
        self.ui.Logs.startLogging()

        self.currentLanguage = language

        self.downloader = QuoteDownloader()
        self.statements = Statements(self)
        self.reports = Reports(self, self.ui.mdiArea)
        self.backup = JalBackup(self, get_dbfilename(get_app_path()))
        self.estimator = None
        self.price_chart = None

        self.ui.actionImportShopReceipt.setEnabled(dependency_present(['PySide6.QtMultimedia']))

        self.actionAbout = QAction(text=self.tr("About"), parent=self)
        self.ui.MainMenu.addAction(self.actionAbout)

        self.langGroup = QActionGroup(self.ui.menuLanguage)
        self.createLanguageMenu()

        self.statementGroup = QActionGroup(self.ui.menuStatement)
        self.createStatementsImportMenu()

        self.reportsGroup = QActionGroup(self.ui.menuReports)
        self.createReportsMenu()

        self.setWindowIcon(load_icon("jal.png"))

        self.connect_signals_and_slots()

        self.ui.actionOperations.trigger()

    def connect_signals_and_slots(self):
        self.ui.actionExit.triggered.connect(QApplication.instance().quit)
        self.ui.actionOperations.triggered.connect(self.createOperationsWindow)
        self.actionAbout.triggered.connect(self.showAboutWindow)
        self.langGroup.triggered.connect(self.onLanguageChanged)
        self.statementGroup.triggered.connect(self.statements.load)
        self.reportsGroup.triggered.connect(self.reports.show)
        self.ui.action_LoadQuotes.triggered.connect(partial(self.downloader.showQuoteDownloadDialog, self))
        self.ui.actionImportShopReceipt.triggered.connect(self.importShopReceipt)
        self.ui.actionBackup.triggered.connect(self.backup.create)
        self.ui.actionRestore.triggered.connect(self.backup.restore)
        self.ui.action_Re_build_Ledger.triggered.connect(partial(self.ledger.showRebuildDialog, self))
        self.ui.actionCleanAll.triggered.connect(self.onCleanDB)
        self.ui.actionAccounts.triggered.connect(partial(self.onDataDialog, "accounts"))
        self.ui.actionAssets.triggered.connect(partial(self.onDataDialog, "assets"))
        self.ui.actionPeers.triggered.connect(partial(self.onDataDialog, "agents"))
        self.ui.actionCategories.triggered.connect(partial(self.onDataDialog, "categories"))
        self.ui.actionTags.triggered.connect(partial(self.onDataDialog, "tags"))
        self.ui.actionQuotes.triggered.connect(partial(self.onDataDialog, "quotes"))
        self.ui.actionBaseCurrency.triggered.connect(partial(self.onDataDialog, "base_currency"))
        self.ui.PrepareTaxForms.triggered.connect(partial(TaxWidget.showInMDI, self.ui.mdiArea))
        self.ui.PrepareFlowReport.triggered.connect(partial(MoneyFlowWidget.showInMDI, self.ui.mdiArea))
        self.downloader.download_completed.connect(self.updateWidgets)
        self.ledger.updated.connect(self.updateWidgets)
        self.statements.load_completed.connect(self.onStatementImport)

    @Slot()
    def showEvent(self, event):
        super().showEvent(event)
        if self.running:
            return
        self.running = True
        # Call slot via queued connection, so it's called from the UI thread after the window has been shown
        QMetaObject().invokeMethod(self, "afterShowEvent", Qt.ConnectionType.QueuedConnection)

    @Slot()
    def afterShowEvent(self):
        # Display information message once if database contains any
        if JalSettings().getValue('MessageOnce'):
            messages = json.loads(JalSettings().getValue('MessageOnce'))
            try:
                message = messages[JalSettings().getLanguage()]   # Try to load language-specific message
            except KeyError:
                message = messages['en']                          # Fallback to English message if failure
            QMessageBox().information(self, self.tr("Info"), message, QMessageBox.Ok)
            JalSettings().setValue('MessageOnce', '')   # Delete message if it was shown
        # Ask for database rebuild if flag is set
        if JalSettings().getValue('RebuildDB', 0) == 1:
            if QMessageBox().warning(self, self.tr("Confirmation"), self.tr("Database data may be inconsistent after recent update. Rebuild it now?"),
                                     QMessageBox.Yes, QMessageBox.No) == QMessageBox.Yes:
                self.ledger.rebuild(from_timestamp=0)

    @Slot()
    def closeEvent(self, event):
        JalSettings().setValue('WindowGeometry', base64.encodebytes(self.saveGeometry().data()).decode('utf-8'))
        JalSettings().setValue('WindowState', base64.encodebytes(self.saveState().data()).decode('utf-8'))
        self.ui.Logs.stopLogging()
        super().closeEvent(event)

    def createLanguageMenu(self):
        langPath = get_app_path() + Setup.LANG_PATH + os.sep

        langDirectory = QDir(langPath)
        for language_file in langDirectory.entryList(['*.qm']):
            language_code = language_file.split('.')[0]
            language = QLocale.languageToString(QLocale(language_code).language())
            action = QAction(icon=load_icon(language_code + '.png'), text=language, parent=self)
            action.setCheckable(True)
            action.setData(language_code)
            self.ui.menuLanguage.addAction(action)
            self.langGroup.addAction(action)

    @Slot()
    def onLanguageChanged(self, action):
        language_code = action.data()
        if language_code != self.currentLanguage:
            JalSettings().setLanguage(language_code)
            QMessageBox().information(self, self.tr("Restart required"),
                                      self.tr("Language was changed to ") +
                                      QLocale.languageToString(QLocale(language_code).language()) + "\n" +
                                      self.tr("You should restart application to apply changes.\n"
                                           "Application will be terminated now."),
                                      QMessageBox.Ok)
            self.close()

    @Slot()
    def onCleanDB(self, action):
        if QMessageBox().warning(None, self.tr("Full clean-up"),
                                 self.tr("All data will be deleted. The actions can't be undone.\nAre you sure?"),
                                 QMessageBox.Yes, QMessageBox.No) == QMessageBox.No:
            return
        JalSettings().setValue("CleanDB", 1)
        QMessageBox().information(self, self.tr("Restart required"),
                                  self.tr("Database will be removed at next JAL start.\n"
                                          "Application will be terminated now."),
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
            self.ui.menuStatement.addAction(action)
            self.statementGroup.addAction(action)

    # Create menu entry for all known reports based on self.reports.sources values
    def createReportsMenu(self):
        groups = {}
        for i, report in enumerate(self.reports.items):
            action = QAction(report['name'].replace('&', '&&'), self)  # & -> && to prevent shortcut creation
            action.setData(i)
            if report['group']:
                if report['group'] not in groups:
                    groups[report['group']] = QMenu(report['group'], self.ui.menuReports)
                    self.ui.menuReports.addAction(groups[report['group']].menuAction())
                submenu = groups[report['group']]
                submenu.addAction(action)
            else:
                self.ui.menuReports.addAction(action)
            self.reportsGroup.addAction(action)

    @Slot()
    def createOperationsWindow(self):
        operations_window = self.ui.mdiArea.addSubWindow(OperationsWidget(self), maximized=True)
        operations_window.widget().dbUpdated.connect(self.ledger.rebuild)

    @Slot()
    def showAboutWindow(self):
        about_box = QMessageBox(self)
        about_box.setAttribute(Qt.WA_DeleteOnClose)
        about_box.setWindowTitle(self.tr("About"))
        version = f"{__version__} (db{Setup.DB_REQUIRED_VERSION})"
        title = "<h3>JAL</h3><p>Just Another Ledger, " + self.tr("version") + " " + version +"</p>" + \
            "<p>DB file: " + JalSettings().DbPath() + "</p>"
        about_box.setText(title)
        about_text = "<p>" + self.tr("More information, manuals and problem reports are at ") + \
                     "<a href=https://github.com/titov-vv/jal>" + self.tr("github home page") + "</a></p><p>" + \
                     self.tr("Questions, comments, help or donations:") + \
                     "</p><p><a href=mailto:jal@gmx.ru>jal@gmx.ru</a></p>" + \
                     "<p><a href=https://t.me/jal_support>Telegram</a></p>"
        about_box.setInformativeText(about_text)
        about_box.show()

    def showProgressBar(self, visible=False):
        self.ProgressBar.setVisible(visible)
        self.ui.centralwidget.setEnabled(not visible)
        self.ui.MainMenu.setEnabled(not visible)

    @Slot()
    def importShopReceipt(self):
        dialog = ImportReceiptDialog(self)
        dialog.finished.connect(self.onSlipImportFinished)
        dialog.open()

    @Slot()
    def onSlipImportFinished(self):
        self.ledger.rebuild()

    @Slot()
    def onDataDialog(self, dlg_type):
        if dlg_type == "accounts":
            AccountListDialog().exec()
        elif dlg_type == "assets":
            AssetListDialog().exec()
        elif dlg_type == "agents":
            PeerListDialog(self).exec()
        elif dlg_type == "categories":
            CategoryListDialog(self).exec()
        elif dlg_type == "tags":
            TagsListDialog(self).exec()
        elif dlg_type == "quotes":
            QuotesListDialog().exec()
        elif dlg_type == "base_currency":
            BaseCurrencyDialog().exec()
        else:
            assert False, f"Unexpected dialog call: '{dlg_type}'"
        self.ledger.rebuild()

    @Slot()
    def updateWidgets(self):
        for window in self.ui.mdiArea.subWindowList():
            window.widget().refresh()

    @Slot()
    def onStatementImport(self, timestamp, totals):
        self.ledger.rebuild()
        for account_id in totals:
            account = JalAccount(account_id)
            for asset_id in totals[account_id]:
                amount = account.get_asset_amount(timestamp, asset_id)
                if amount is not None:
                    delta = Decimal(str(totals[account_id][asset_id])) - amount
                    if delta == Decimal('0'):
                        account.reconcile(timestamp)
                        self.updateWidgets()
                    elif -log10(abs(delta)) >= account.precision():  # Can't combine condition due to log(0)
                        account.reconcile(timestamp)
                        self.updateWidgets()
                    else:
                        asset = JalAsset(asset_id).symbol(account.currency())
                        logging.warning(self.tr("Statement ending balance doesn't match: ") +
                                        f"{account.name()} / {asset} / {amount} (act) <> {totals[account_id][asset_id]} (exp)")
