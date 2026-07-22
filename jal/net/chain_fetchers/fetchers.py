import logging
import importlib
import os

from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtWidgets import QMessageBox, QDialog, QVBoxLayout, QLabel, QListWidget, QListWidgetItem, \
    QCheckBox, QDialogButtonBox

from jal.constants import Setup, AssetLocation
from jal.db.settings import JalSettings
from jal.data_import.statement import Statement_ImportError


# ----------------------------------------------------------------------------------------------------------------------
# Lets the user pick which wallets of one blockchain to fetch, with a checkbox per account and an "all" checkbox that
# selects or clears the whole list at once - the same interaction the quotes-download dialog uses. Shown only when a
# chain has more than one wallet; a single wallet is fetched without asking.
class WalletSelectDialog(QDialog):
    _ACCOUNT_ROLE = Qt.UserRole

    def __init__(self, chain_name: str, wallets: list, parent=None):
        super().__init__(parent=parent)
        self.setWindowTitle(self.tr("Fetch blockchain transactions"))
        self._syncing = False   # guards the two-way sync between the "all" checkbox and the item checkboxes
        self._all_state_before_click = Qt.Unchecked
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(self.tr("Select wallets to fetch:") + f" {chain_name}"))
        self._all = QCheckBox(self.tr("All wallets"))
        self._all.setTristate(True)
        layout.addWidget(self._all)
        self._list = QListWidget(self)
        for wallet in wallets:
            item = QListWidgetItem(f"{wallet.name()}  ({wallet.address()})", self._list)
            item.setData(self._ACCOUNT_ROLE, wallet.id())
            item.setCheckState(Qt.Checked)
        layout.addWidget(self._list)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._list.itemChanged.connect(self._on_item_changed)
        self._all.pressed.connect(self._on_all_pressed)
        self._all.clicked.connect(self._on_all_clicked)
        self._sync_all_checkbox()

    # Ids of the wallets the user left checked
    def selected_ids(self) -> list:
        return [self._list.item(i).data(self._ACCOUNT_ROLE) for i in range(self._list.count())
                if self._list.item(i).checkState() == Qt.Checked]

    def _on_item_changed(self, _item):
        if not self._syncing:
            self._sync_all_checkbox()

    # The state is captured before the click because Qt has already cycled the tristate box by the time 'clicked'
    # fires - a partially-checked box would otherwise step to 'checked' on its own and confuse the decision below.
    def _on_all_pressed(self):
        self._all_state_before_click = self._all.checkState()

    def _on_all_clicked(self, _checked):
        # A click clears the list only when it was fully checked; from empty or partial it checks everything.
        target = Qt.Unchecked if self._all_state_before_click == Qt.Checked else Qt.Checked
        self._syncing = True
        try:
            for i in range(self._list.count()):
                self._list.item(i).setCheckState(target)
        finally:
            self._syncing = False
        self._sync_all_checkbox()

    # Reflects the item states onto the "all" checkbox: checked / unchecked / partially checked
    def _sync_all_checkbox(self):
        checked = sum(1 for i in range(self._list.count())
                      if self._list.item(i).checkState() == Qt.Checked)
        self._syncing = True
        try:
            if checked == 0:
                self._all.setCheckState(Qt.Unchecked)
            elif checked == self._list.count():
                self._all.setCheckState(Qt.Checked)
            else:
                self._all.setCheckState(Qt.PartiallyChecked)
        finally:
            self._syncing = False


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
        accounts = self._select_wallets(descriptor['name'], wallets)
        if not accounts:   # nothing checked, or the dialog was cancelled
            return
        if not self._ensure_token_lists(fetcher_class.location_id):
            return
        # Each wallet is fetched and imported on its own: it has its own address, its own sync cursor and its own
        # ending balance, so its result is emitted with its own timestamp (the balance reconciliation in the main
        # window is per-account and per-instant). One wallet failing must not abandon the others, so failures are
        # collected and reported together at the end instead of aborting the whole run.
        skipped = {}
        failed = []
        imported_any = False
        for account in accounts:
            fetcher = fetcher_class()
            try:
                fetcher.fetch(account)
                totals = fetcher.import_fetched()
            except Statement_ImportError as error:
                logging.error(self.tr("Blockchain fetch failed: ") + f"{account.name()}: {error}")
                failed.append((account.name(), str(error)))
                continue
            imported_any = True
            for reason, count in fetcher.skipped().items():
                skipped[reason] = skipped.get(reason, 0) + count
            logging.info(self.tr("Transactions were fetched from blockchain for account: ") + account.name())
            self.load_completed.emit(fetcher.period()[1], totals)
        self._report_skipped(skipped)
        self._report_failures(failed)
        if not imported_any:
            self.load_failed.emit()

    # Token allow-/block-lists back the spam filter that decides which fetched tokens are real. Against an empty
    # cache the filter has nothing to judge by: a token seen for the first time is unpriceable and looks exactly
    # like a dust airdrop, so a legitimate coin (a wallet's first USDT) is quarantined AND auto-blacklisted -
    # and the auto-blacklist then blocks it on every later fetch even once the lists are loaded. Rather than let
    # that happen silently on the first fetch, the user is told and the lists for this chain are downloaded first.
    # Returns False - aborting the fetch - if the cache is still empty afterwards, since fetching then would walk
    # straight into that trap.
    def _ensure_token_lists(self, location_id: int) -> bool:
        # A venue that publishes the value of every transfer needs no downloaded list to tell a real token from
        # spam - the fetcher judges by that value and resolves a token's identity from the venue's own registry
        # (Hyperliquid: 'spotMeta'). There is no curated allow-list to download for such a chain, so the gate that
        # protects the first fetch of a list-backed chain would only ever abort it. See CRYPTO_PATH decision #67.
        if location_id == AssetLocation.HL_BLOCKCHAIN:
            return True
        lists = self.parent.token_lists
        if not lists.is_empty(location_id):
            return True
        QMessageBox().information(None, self.tr("Token lists"),
                                  self.tr("Token allow/block lists are not loaded yet. They are needed to tell real "
                                          "tokens from unsolicited spam airdrops during import, and will be "
                                          "downloaded now."), QMessageBox.Ok)
        lists.refresh(location_id=location_id, force=True)
        if lists.is_empty(location_id):   # cancelled by the user, or every download failed
            QMessageBox().warning(None, self.tr("Token lists"),
                                  self.tr("Token lists could not be loaded (see log for details). Fetching now could "
                                          "hide real tokens as spam, so the import was stopped. Try again later, or "
                                          "load the lists manually from the Import menu."), QMessageBox.Ok)
            return False
        return True

    # Which wallets of the chain to fetch. A single wallet is fetched without asking; several are offered in a
    # checkbox dialog so the user may fetch any subset in one go. Returns the chosen JalAccounts, or [] on cancel.
    def _select_wallets(self, chain_name: str, wallets: list) -> list:
        if len(wallets) == 1:
            return wallets
        dialog = WalletSelectDialog(chain_name, wallets)
        if dialog.exec() != QDialog.Accepted:
            return []
        chosen = set(dialog.selected_ids())
        return [x for x in wallets if x.id() in chosen]

    # Transactions that were recognized but produced no operation are shown rather than dropped quietly - otherwise
    # an unsupported kind of transaction is indistinguishable from an empty history. Counts are summed across all the
    # wallets fetched in one run and shown once.
    def _report_skipped(self, skipped: dict) -> None:
        if not skipped:
            return
        details = "\n".join(f"{count} x {reason}" for reason, count in sorted(skipped.items()))
        logging.info(self.tr("Some transactions were not imported:") + "\n" + details)
        QMessageBox().information(None, self.tr("Not everything was imported"),
                                  self.tr("These transactions were recognized but not imported:") + "\n\n" + details,
                                  QMessageBox.Ok)

    # Wallets whose fetch failed are reported together, so one broken account (a bad address, a network error) is
    # visible without hiding the wallets that were imported successfully in the same run.
    def _report_failures(self, failed: list) -> None:
        if not failed:
            return
        details = "\n".join(f"{name}: {error}" for name, error in failed)
        QMessageBox().warning(None, self.tr("Some wallets could not be fetched"),
                              self.tr("Fetching failed for these wallets:") + "\n\n" + details, QMessageBox.Ok)
