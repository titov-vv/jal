import logging
import importlib
import os

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMessageBox

from jal.constants import Setup
from jal.db.settings import JalSettings
from jal.data_import.statement import Statement_ImportError
from jal.widgets.account_select import SelectAccountDialog


# ----------------------------------------------------------------------------------------------------------------------
# Registry of blockchain transaction fetchers, deliberately separate from Statements: that one is driven by a file
# dialog and asks for a filename, while a fetcher is driven by a wallet account and goes to the network. Modules are
# discovered the same way statement modules are - by a JAL_FETCHER_CLASS attribute - so a new chain is added by
# dropping a module into this package.
class ChainFetchers(QObject):
    load_completed = Signal(int, dict)
    load_failed = Signal()

    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.items = []
        self.loadFetchersList()

    def loadFetchersList(self):
        folder = os.path.dirname(os.path.realpath(__file__))
        modules = [x[:-3] for x in os.listdir(folder) if x.endswith(".py") and not x.startswith("__")]
        for module_name in modules:
            try:
                module = importlib.import_module(f"jal.net.chain_fetchers.{module_name}")
            except ImportError:
                logging.error(self.tr("Chain fetcher module can't be imported: ") + module_name)
                continue
            try:
                class_name = getattr(module, "JAL_FETCHER_CLASS")
            except AttributeError:
                continue    # Not a fetcher module - the base class and the registry itself land here
            try:
                fetcher_class = getattr(module, class_name)
            except AttributeError:
                logging.error(self.tr("Chain fetcher class can't be loaded: ") + class_name)
                continue
            fetcher = fetcher_class()
            self.items.append({'name': fetcher.name, 'module': module, 'loader_class': class_name,
                               'location_id': fetcher.location_id, 'icon': fetcher.icon_name})
            logging.debug(f"Class '{class_name}' providing '{fetcher.name}' chain fetcher has been loaded")
        self.items = sorted(self.items, key=lambda item: item['name'])

    # Called from the menu, so it receives the QAction that was triggered
    def load(self, action):
        descriptor = self.items[action.data()]
        fetcher_class = getattr(descriptor['module'], descriptor['loader_class'])
        wallets = fetcher_class.wallets()
        if not wallets:
            QMessageBox().warning(None, self.tr("No wallets"),
                                  self.tr("There is no active wallet account for this blockchain. "
                                          "Create one with its Blockchain and Address attributes filled."),
                                  QMessageBox.Ok)
            return
        account = wallets[0] if len(wallets) == 1 else self._select_wallet(wallets)
        if account is None:
            return
        fetcher = fetcher_class()
        try:
            fetcher.fetch(account)
            totals = fetcher.import_fetched()
        except Statement_ImportError as error:
            logging.error(self.tr("Blockchain fetch failed: ") + str(error))
            self.load_failed.emit()
            return
        self._report_skipped(fetcher)
        logging.info(self.tr("Transactions were fetched from blockchain for account: ") + account.name())
        self.load_completed.emit(fetcher.period()[1], totals)

    # Asks which wallet to fetch when several accounts share one chain
    def _select_wallet(self, wallets):
        dialog = SelectAccountDialog(self.tr("Select wallet account to fetch:"), wallets[0].id())
        if dialog.exec() != dialog.Accepted:
            return None
        chosen = [x for x in wallets if x.id() == dialog.account_id]
        return chosen[0] if chosen else None

    # Transactions that were recognized but produced no operation are shown rather than dropped quietly - otherwise
    # an unsupported kind of transaction is indistinguishable from an empty history.
    def _report_skipped(self, fetcher) -> None:
        skipped = fetcher.skipped()
        if not skipped:
            return
        details = "\n".join(f"{count} x {reason}" for reason, count in sorted(skipped.items()))
        logging.info(self.tr("Some transactions were not imported:") + "\n" + details)
        QMessageBox().information(None, self.tr("Not everything was imported"),
                                  self.tr("These transactions were recognized but not imported:") + "\n\n" + details,
                                  QMessageBox.Ok)
