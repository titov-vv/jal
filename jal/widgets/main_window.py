import json
import base64
import logging
from math import log10
from decimal import Decimal
from functools import partial

from PySide6.QtCore import Qt, Slot, QDir, QLocale, QMetaObject, QUrl
from PySide6.QtGui import QActionGroup, QAction, QDesktopServices
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QProgressBar, QMenu, QPushButton

from jal import __version__
from jal.ui.ui_main_window import Ui_JAL_MainWindow
from jal.widgets.operations_widget import OperationsWidget
from jal.widgets.tax_widget import TaxWidget, MoneyFlowWidget, TaxMergeDialog
from jal.widgets.helpers import dependency_present, menu_label, menu_mnemonic
from jal.widgets.icons import JalIcon, AUX_PREFIX, CHAIN_PREFIX
from jal.widgets.reference_dialogs import AccountListDialog, TagsListDialog, CategoryListDialog, QuotesListDialog, PeerListDialog, BaseCurrencyDialog, TokenBlacklistDialog
from jal.widgets.assets_dialogs import SymbolListDialog
from jal.widgets.preferences_dialog import PreferencesDialog
from jal.constants import Setup, JalGlobals
from jal.db.db import JalDB
from jal.db.backup_restore import JalBackup
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.settings import JalSettings
from jal.net.downloader import QuoteDownloader
from jal.net.token_lists import TokenListProvider
from jal.db.ledger import Ledger
from jal.data_import.statements import Statements
from jal.net.chain_fetchers.fetchers import ChainFetchers
from jal.reports.reports import Reports
from jal.data_import.shop_receipt import ImportReceiptDialog


#-----------------------------------------------------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self, translator):
        super().__init__()
        self._translator = translator
        self.globals = JalGlobals()  # Initialize and keep global values
        self.icons = JalIcon()  # This variable is used to initialize JalIcons class and keep its cache in memory.
                                # It is not used directly but icons are accessed via @classmethod of JalIcons class
                                # Should be called before ui-initialization
        self.running = False
        self.ui = Ui_JAL_MainWindow()
        self.ui.setupUi(self)
        self.restoreGeometry(base64.decodebytes(JalSettings().getValue('WindowGeometry', '').encode('utf-8')))
        self.restoreState(base64.decodebytes(JalSettings().getValue('WindowState', '').encode('utf-8')))

        self.ledger = Ledger()

        # Customize Status bar and logs
        self.ProgressBar = QProgressBar(self)  # Use default range 0 - 100
        self.ui.StatusBar.addPermanentWidget(self.ProgressBar, stretch=1)
        self.CancelButton = QPushButton(self.tr("Stop"), parent=self)
        self.CancelButton.setFixedWidth(int(self.CancelButton.fontMetrics().horizontalAdvance(self.CancelButton.text()) * 1.5))
        self.ui.StatusBar.addPermanentWidget(self.CancelButton)
        self.ProgressBar.setVisible(False)
        self.CancelButton.setVisible(False)
        self.ui.Logs.setStatusBar(self.ui.StatusBar)
        self.ui.Logs.startLogging()

        self.downloader = QuoteDownloader()
        self.token_lists = TokenListProvider()
        self.statements = Statements(self)
        self.chain_fetchers = ChainFetchers(self)
        self.reports = Reports(self, self.ui.mdiArea)
        self.backup = JalBackup(self)
        self.estimator = None
        self.price_chart = None

        self.ui.actionImportShopReceipt.setEnabled(dependency_present(['PySide6.QtMultimedia']))

        self.langGroup = QActionGroup(self.ui.menuLanguage)
        self.createLanguageMenu()

        self.statementGroup = QActionGroup(self.ui.menuStatement)
        self.createStatementsImportMenu()

        self.blockchainGroup = QActionGroup(self.ui.menuBlockchain)
        self.createBlockchainImportMenu()

        self.reportsGroup = QActionGroup(self.ui.menuReports)
        self.createReportsMenu()

        self.setWindowIcon(JalIcon[JalIcon.APP_MAIN])

        self.connect_signals_and_slots()

        self.ui.actionOperations.trigger()

    def connect_signals_and_slots(self):
        self.ui.actionExit.triggered.connect(QApplication.instance().quit)
        self.ui.actionOperations.triggered.connect(self.showOperationsWindow)
        self.ui.actionAbout.triggered.connect(self.showAboutWindow)
        self.ui.actionDocumentation.triggered.connect(partial(self.openHelpDocument, Setup.REPO_README))
        self.ui.actionFAQ.triggered.connect(partial(self.openHelpDocument, Setup.REPO_FAQ))
        self.ui.actionErrorMessages.triggered.connect(partial(self.openHelpDocument, Setup.REPO_ERRORS))
        self.ui.actionReportProblem.triggered.connect(partial(QDesktopServices.openUrl, QUrl(Setup.REPO_URL + "/issues")))
        self.langGroup.triggered.connect(self.onLanguageChanged)
        self.statementGroup.triggered.connect(self.statements.load)
        self.blockchainGroup.triggered.connect(self.chain_fetchers.load)
        self.reportsGroup.triggered.connect(self.reports.show)
        self.ui.action_LoadQuotes.triggered.connect(partial(self.downloader.showQuoteDownloadDialog, self))
        self.ui.actionLoadTokenLists.triggered.connect(self.loadTokenLists)
        self.ui.actionImportShopReceipt.triggered.connect(self.importShopReceipt)
        self.ui.actionMergeRuTaxFiles.triggered.connect(self.mergeRuTaxFiles)
        self.ui.actionBackup.triggered.connect(self.backup.create)
        self.ui.actionRestore.triggered.connect(self.backup.restore)
        self.ui.action_Re_build_Ledger.triggered.connect(partial(self.ledger.showRebuildDialog, self))
        self.ui.actionDeleteAllData.triggered.connect(self.onCleanDB)
        self.ui.actionAccounts.triggered.connect(partial(self.onDataDialog, AccountListDialog))
        self.ui.actionAssets.triggered.connect(partial(self.onDataDialog, SymbolListDialog))
        self.ui.actionPeers.triggered.connect(partial(self.onDataDialog, PeerListDialog))
        self.ui.actionCategories.triggered.connect(partial(self.onDataDialog, CategoryListDialog))
        self.ui.actionTags.triggered.connect(partial(self.onDataDialog, TagsListDialog))
        self.ui.actionQuoteHistory.triggered.connect(partial(self.onDataDialog, QuotesListDialog))
        self.ui.actionTokenBlacklist.triggered.connect(partial(self.onDataDialog, TokenBlacklistDialog))
        self.ui.actionBaseCurrency.triggered.connect(partial(self.onDataDialog, BaseCurrencyDialog))
        self.ui.actionPreferences.triggered.connect(self.showPreferences)
        self.ui.PrepareTaxForms.triggered.connect(partial(TaxWidget.showInMDI, self.ui.mdiArea))
        self.ui.PrepareFlowReport.triggered.connect(partial(MoneyFlowWidget.showInMDI, self.ui.mdiArea))
        self.CancelButton.clicked.connect(self.downloader.on_cancel)
        self.CancelButton.clicked.connect(self.ledger.on_cancel)
        self.CancelButton.clicked.connect(self.token_lists.on_cancel)
        self.token_lists.show_progress.connect(self.onToggleProgressDisplay)
        self.token_lists.update_progress.connect(self.onUpdatePorgressDisplay)
        self.downloader.download_completed.connect(self.updateWidgets)
        self.downloader.show_progress.connect(self.onToggleProgressDisplay)
        self.downloader.update_progress.connect(self.onUpdatePorgressDisplay)
        self.ledger.updated.connect(self.updateWidgets)
        self.ledger.show_progress.connect(self.onToggleProgressDisplay)
        self.ledger.update_progress.connect(self.onUpdatePorgressDisplay)
        self.statements.load_completed.connect(self.onStatementImport)
        self.chain_fetchers.load_completed.connect(self.onStatementImport)
        self.chain_fetchers.show_progress.connect(self.onToggleProgressDisplay)
        self.chain_fetchers.update_progress.connect(self.onUpdatePorgressDisplay)
        self.chain_fetchers.update_progress_text.connect(self.onUpdateProgressText)

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
        self.downloader.wait_for_pending()
        self.token_lists.wait_for_pending()
        super().closeEvent(event)

    def createLanguageMenu(self):
        langDirectory = QDir(JalSettings.path(JalSettings.PATH_LANG))
        current_language = JalSettings().getLanguage()
        for language_file in langDirectory.entryList(['*.qm']):
            language_code = language_file.split('.')[0]
            language = QLocale.languageToString(QLocale(language_code).language())
            action = QAction(icon=JalIcon.country_flag(language_code), text=language, parent=self)
            action.setCheckable(True)
            action.setChecked(language_code == current_language)   # the group shows which language is in use now
            action.setData(language_code)
            self.ui.menuLanguage.addAction(action)
            self.langGroup.addAction(action)

    @Slot()
    def onLanguageChanged(self, action):
        language_code = action.data()
        if language_code != JalSettings().getLanguage():
            JalSettings().setLanguage(language_code)
            self._translator.load(JalSettings.path(JalDB.PATH_LANG_FILE))
            if QMessageBox().question(self, self.tr("Translation"),
                                      self.tr("Translate predefined names in the database?\n(Default answer is 'yes', if haven't renamed manually before)"),
                                      QMessageBox.Yes, QMessageBox.No) == QMessageBox.Yes:
                JalDB().retranslate()
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
        JalSettings().setValue("CleanDB", "yes")
        QMessageBox().information(self, self.tr("Restart required"),
                                  self.tr("Database will be removed at next JAL start.\n"
                                          "Application will be terminated now."),
                                  QMessageBox.Ok)
        self.close()

    # Adds one menu item for a dynamically loaded module (a report, a broker statement or a blockchain fetcher).
    # The label comes from the module itself and carries its own Qt mnemonic markup, so every module - and every
    # translation of it - picks its own access key. 'asks_input' marks an action that requires something from the
    # user (a file to read, a wallet to fetch) before it can do any work, which is what the ellipsis announces.
    # 'icon_prefix' tells which set of module logos 'icon_name' is looked up in - see JalIcon.module_icon().
    def addModuleAction(self, menu, group, label, index, icon_name='', icon_prefix=AUX_PREFIX, asks_input=False):
        if asks_input:
            label += "..."
        action = QAction(JalIcon.module_icon(icon_prefix, icon_name), label, self) if icon_name else QAction(label, self)
        action.setData(index)
        menu.addAction(action)
        group.addAction(action)

    # Reports two items of one menu that compete for the same access key. Qt keeps such a menu usable - the key
    # cycles between the matching items instead of activating one - but it makes the menu harder to operate.
    # Labels of dynamically built menus come from separately translated modules, so nothing else can catch this.
    # The message is intentionally not translated: it is addressed to whoever maintains those translations.
    @staticmethod
    def checkMenuMnemonics(menu_name: str, labels: list):
        used = {}
        for label in labels:
            key = menu_mnemonic(label)
            if not key:
                continue
            if key in used:
                logging.warning(f"Menu '{menu_name}': '{menu_label(label)}' and '{used[key]}' "
                                f"both use access key '{key}'")
            else:
                used[key] = menu_label(label)

    # Create import menu for all known statements based on self.statements.items values
    def createStatementsImportMenu(self):
        for i, statement in enumerate(self.statements.items):
            self.addModuleAction(self.ui.menuStatement, self.statementGroup, statement['name'], i, icon_name=statement['icon'], asks_input=True)
        self.checkMenuMnemonics("Import->Statement", [x['name'] for x in self.statements.items])

    # Create import menu for all known blockchain fetchers based on self.chain_fetchers.items values
    def createBlockchainImportMenu(self):
        for i, fetcher in enumerate(self.chain_fetchers.items):
            self.addModuleAction(self.ui.menuBlockchain, self.blockchainGroup, fetcher['name'], i, icon_name=fetcher['icon'], icon_prefix=CHAIN_PREFIX, asks_input=True)
        self.checkMenuMnemonics("Import->Blockchain", [x['name'] for x in self.chain_fetchers.items])

    # Create menu entry for all known reports based on self.reports.items values.
    # Reports that declare a group get a submenu of their own.
    def createReportsMenu(self):
        groups = {}
        for i, report in enumerate(self.reports.items):
            if report['group']:
                if report['group'] not in groups:
                    groups[report['group']] = QMenu(report['group'], self.ui.menuReports)
                self.addModuleAction(groups[report['group']], self.reportsGroup, report['name'], i)
            else:
                self.addModuleAction(self.ui.menuReports, self.reportsGroup, report['name'], i)
        if groups:
            self.ui.menuReports.addSeparator()
        for group_name, submenu in groups.items():
            self.ui.menuReports.addAction(submenu.menuAction())
            self.checkMenuMnemonics(f"Reports->{menu_label(group_name)}",
                                    [x['name'] for x in self.reports.items if x['group'] == group_name])
        self.checkMenuMnemonics("Reports", [x['name'] for x in self.reports.items if not x['group']] + list(groups))

    # The operations window is the main view of the application - there is no use for a second copy of it,
    # so an already open one is brought to the front instead of being added again.
    @Slot()
    def showOperationsWindow(self):
        for window in self.ui.mdiArea.subWindowList():
            if isinstance(window.widget(), OperationsWidget):
                self.ui.mdiArea.setActiveSubWindow(window)
                return
        operations_window = self.ui.mdiArea.addSubWindow(OperationsWidget(self), maximized=True)
        operations_window.widget().dbUpdated.connect(self.ledger.rebuild)

    # Opens a document from the project repository in a browser, in the language the application is set to
    @Slot()
    def openHelpDocument(self, document: str):
        language = JalSettings().getLanguage()
        suffix = '' if language == 'en' else f".{language}"
        url = f"{Setup.REPO_URL}/blob/master/{Setup.HELP_DOCUMENTS[document]}{suffix}.md"
        QDesktopServices.openUrl(QUrl(url))

    @Slot()
    def showAboutWindow(self):
        about_box = QMessageBox(self)
        about_box.setAttribute(Qt.WA_DeleteOnClose)
        about_box.setWindowTitle(self.tr("About"))
        version = f"{__version__} (db{Setup.DB_REQUIRED_VERSION})"
        title = "<h3>JAL</h3><p>Just Another Ledger, " + self.tr("version") + " " + version +"</p>" + \
            "<p>DB file: " + JalSettings.path(JalSettings.PATH_DB_FILE) + "</p>"
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
        self.CancelButton.setVisible(visible)
        self.ui.centralwidget.setEnabled(not visible)
        self.ui.MainMenu.setEnabled(not visible)

    # Downloads the token allow-/block- lists that back the unknown/spam token policy.
    # Normally lists are refreshed lazily, this menu entry re-downloads all of them on demand.
    @Slot()
    def loadTokenLists(self):
        entries = self.token_lists.refresh(force=True)
        if self.token_lists.was_cancelled():
            return   # Interruption is reported into the log by the provider itself
        if entries:
            QMessageBox().information(self, self.tr("Token lists"),
                                      self.tr("Token lists were updated, entries loaded: ") + f"{entries}",
                                      QMessageBox.Ok)
        else:   # Every download failed - details of each failure are in the log
            QMessageBox().warning(self, self.tr("Token lists"),
                                  self.tr("Failed to download token lists, see log for details"), QMessageBox.Ok)

    @Slot()
    def importShopReceipt(self):
        dialog = ImportReceiptDialog(self)
        dialog.finished.connect(self.onSlipImportFinished)
        dialog.open()

    @Slot()
    def onSlipImportFinished(self):
        self.ledger.rebuild()

    @Slot()
    def mergeRuTaxFiles(self):
        TaxMergeDialog().exec()

    @Slot()
    def onDataDialog(self, dialog_class):
        dialog_class().exec()
        self.ledger.rebuild()

    # Preferences change application settings only and never any operation, so no ledger rebuild is needed here
    @Slot()
    def showPreferences(self):
        PreferencesDialog(parent=self).exec()

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

    @Slot(bool)
    def onToggleProgressDisplay(self, visible):
        self.ProgressBar.setValue(0)
        self.ProgressBar.setFormat('%p%')   # clears any per-page label left by a blockchain fetch
        self.showProgressBar(visible)

    def onUpdatePorgressDisplay(self, progress_percent: float):
        self.ProgressBar.setValue(int(progress_percent))

    def onUpdateProgressText(self, text: str):
        self.ProgressBar.setFormat(text)
