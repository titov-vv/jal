import logging
import importlib
import os
from functools import partial

from PySide6.QtCore import QObject, Signal, Slot, Qt
from PySide6.QtWidgets import QMessageBox, QDialog, QVBoxLayout, QLabel, QListWidget, QListWidgetItem, \
    QCheckBox, QDialogButtonBox

from jal.constants import Setup, AssetLocation
from jal.db.ledger import Ledger
from jal.db.operations import LedgerAssetShortage, LedgerError
from jal.db.rebase_residue import RebaseResidue
from jal.db.settings import JalSettings
from jal.widgets.helpers import sort_menu_items
from jal.data_import.statement import Statement_ImportError
from jal.net.arrival_reconciler import ArrivalReconciler, log_findings

# Highest swap oid that was already checked against the route it came from - see ChainFetchers._audit_swaps(). It is
# a position, not a result, so it is kept in the settings the way a fetcher's sync cursor is kept on its account.
_AUDITED_SWAP_SETTING = "LiFiAuditedSwap"


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
    show_progress = Signal(bool)     # Signal is emitted when the fetch wants to start or stop display of progress
    update_progress = Signal(float)  # Signal is emitted to report the share of wallets fetched so far, in percent
    # Signal is emitted to report the status text shown next to the progress bar - see _on_page_fetched(). A wallet's
    # history has no known total ahead of time, so this is text ("<ticker>: fetching page N...") rather than a
    # second percentage.
    update_progress_text = Signal(str)
    # A rebase residue is booked one per closing of a position, so a wallet may legitimately leave several behind.
    # The bound only keeps a rebuild that stops without progressing from looping - it is not a limit anybody meets.
    _MAX_ABSORBED_RESIDUES = 32

    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.items = []
        self._cancelled = False
        self._fetcher = None    # The fetcher that is running now, so that on_cancel() can reach into it
        self.loadFetchersList()

    # Stops the run between wallets and holds back the checks that follow it
    @Slot()
    def on_cancel(self):
        self._cancelled = True
        if self._fetcher is not None:
            self._fetcher.cancel()

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
        self.items = sort_menu_items(self.items, lambda item: item['name'])

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
        label = fetcher_class.display_symbol or descriptor['name']
        self._cancelled = False
        self.show_progress.emit(True)
        try:
            for i, account in enumerate(accounts):
                if self._cancelled:   # 'Stop' pressed while the previous wallet was being imported
                    logging.warning(self.tr("Interrupted by user"))
                    break
                fetcher = fetcher_class()
                fetcher.page_fetched.connect(partial(self._on_page_fetched, label))
                self._fetcher = fetcher
                try:
                    fetcher.fetch(account)
                    # From here to the end of import_fetched() the run may NOT be interrupted: it writes the
                    # operations and then advances the wallet's sync cursor past them, and a stop in between would
                    # either lose what was fetched or move the cursor over what was never stored.
                    totals = fetcher.import_fetched()
                except Statement_ImportError as error:
                    logging.error(self.tr("Blockchain fetch failed: ") + f"{account.name()}: {error}")
                    failed.append((account.name(), str(error)))
                    continue
                finally:
                    self._fetcher = None
                    self.update_progress.emit(100.0 * (i + 1) / len(accounts))
                imported_any = True
                for reason, count in fetcher.skipped().items():
                    skipped[reason] = skipped.get(reason, 0) + count
                logging.info(self.tr("Transactions were fetched from blockchain for account: ") + account.name())
                self.load_completed.emit(fetcher.period()[1], totals)
        except KeyboardInterrupt:   # the wallet being read was abandoned - see ChainFetcher._wait_for()
            logging.warning(self.tr("Interrupted by user"))
        finally:
            self.show_progress.emit(False)
        self._report_skipped(skipped)
        self._report_failures(failed)
        # The three checks below refine what was just imported and each of them costs network requests of its own, so
        # a run the user stopped does not go on to spend them. Nothing is lost by that: all three are idempotent and
        # pick up whatever they skipped at the next fetch (the swap audit remembers how far it has looked, the other
        # two find their own work in the database each time).
        if imported_any and not self._cancelled:
            self._settle_transfers()
            self._absorb_rebase_residue()
            self._audit_swaps()
        if not imported_any:
            self.load_failed.emit()

    # Settles the transfer legs whose counterpart is on another chain, which is the one pairing no amount of fetching
    # can make: the two ends are two transactions and neither names the other, so the legs wait for whoever routed
    # the move to say they belong together (ArrivalReconciler.settle_pending_transfers).
    #
    # It runs after the whole run rather than per wallet because it is the second leg that completes the pair, and
    # that one commonly arrives with a LATER wallet of the same run. The ledger is rebuilt again for what it settled:
    # each account emitted its load_completed as it was imported, and those rebuilds happened before this.
    def _settle_transfers(self) -> None:
        if self._cancelled:
            return    # An earlier phase was stopped and then this one never starts
        self.show_progress.emit(True)
        try:
            settled, findings = ArrivalReconciler().settle_pending_transfers(progress=self._on_leg_checked,
                                                                             interrupted=lambda: self._cancelled)
        except Exception as error:   # like the audit below: a lookup that fails must not fail the import
            logging.warning(self.tr("Pending transfers could not be settled: ") + f"{error}")
            return
        finally:
            self.show_progress.emit(False)
        if self._cancelled:
            logging.warning(self.tr("Settling of transfers was interrupted by user"))
        log_findings(findings)
        if settled:
            logging.info(self.tr("Transfers settled from the route they were sent by: ") + f"{settled}")
            Ledger().rebuild()

    # Finishes a ledger that stopped one crumb short of a lending withdrawal, which is what a rebasing receipt token
    # leaves behind: its Transfer events under-report the balance the protocol really hands back, so closing the
    # position in full asks for a few units of the last decimal more than the books hold. RebaseResidue books the
    # difference (and refuses anything that isn't plainly one) - see it for what is and isn't absorbed here.
    #
    # It runs after the import, where the shortage comes into being, and drives the rebuild itself because the stop
    # is the only place the numbers exist: the ledger reports where it halted and by how much, the crumb is booked,
    # and the rebuild resumes past it. A position that was opened and closed several times leaves one residue per
    # closing, so this repeats until the ledger completes, refuses, or fails - never more times than there are
    # conversions to stop at.
    def _absorb_rebase_residue(self) -> None:
        if self._cancelled:
            return    # As above: a phase that never starts reports nothing
        ledger = Ledger()
        reconciler = RebaseResidue()
        for _ in range(self._MAX_ABSORBED_RESIDUES):
            try:
                ledger.rebuild()
            except LedgerError:
                pass          # under pytest rebuild() re-raises what it stopped on; 'stopped_by' is set either way
            except Exception as error:   # like the checks around it, a failure here must not fail the import
                logging.warning(self.tr("Rebase residue could not be checked: ") + f"{error}")
                return
            # 'Stop' is taken between the passes, each of which is a full ledger rebuild.
            if self._cancelled:
                logging.warning(self.tr("Absorption of rebase residues was interrupted by user"))
                return
            if not isinstance(ledger.stopped_by, LedgerAssetShortage):
                return        # the ledger is complete, or stopped on something this can't make good
            if not reconciler.absorb(ledger.stopped_by):
                return
        logging.warning(self.tr("Too many rebase residues in a row - the ledger was left incomplete"))

    # Checks the swaps the database holds against the routes they really were.
    #
    # A same-chain swap is what a cross-chain move looks like from the sending chain alone whenever the route also pays
    # the wallet something on that chain: that payout is the only incoming asset the transaction has, so the classifier
    # books the whole sent amount as disposed for it and realizes a loss that never happened. Nothing on-chain
    # distinguishes that from a genuine exchange - only the aggregator that routed it can say - so the check is made
    # here, right after an import, which is when such a swap comes into being.
    #
    # Each swap is looked up once: the highest oid checked is remembered, and later runs start above it. The first run
    # therefore examines the whole history (which is what finds the misbookings already stored) and every run after it
    # only the swaps that were just imported.
    def _audit_swaps(self) -> None:
        if self._cancelled:
            return    # As above: a phase that never starts reports nothing
        settings = JalSettings()
        checked_upto = settings.getInt(_AUDITED_SWAP_SETTING, 0)
        self.show_progress.emit(True)
        try:
            last_oid, findings = ArrivalReconciler().audit_swaps(checked_upto, progress=self._on_swap_checked,
                                                                 interrupted=lambda: self._cancelled)
        except Exception as error:   # a check that fails must never take a successful import down with it
            logging.warning(self.tr("Cross-chain check of swaps could not be completed: ") + f"{error}")
            return
        finally:
            self.show_progress.emit(False)
        if self._cancelled:
            logging.warning(self.tr("Check of swaps was interrupted by user"))
        settings.setValue(_AUDITED_SWAP_SETTING, last_oid)
        if not findings:
            return
        log_findings(findings)
        QMessageBox().warning(None, self.tr("Check these swaps"),
                              self.tr("The aggregator that routed these operations describes them differently than "
                                      "they are booked. Each one has to be corrected by hand - what the ledger says "
                                      "about them is wrong:")
                              + "\n\n" + "\n\n".join(findings), QMessageBox.Ok)

    # Relays one wallet's page_fetched into the status text shown next to the progress bar.
    def _on_page_fetched(self, label: str, page: int) -> None:
        self.update_progress_text.emit(f"{label}: " + self.tr("fetching page") + f" {page}...")

    # ... and the swap audit into the same place. Unlike a fetch this one knows its total up front, so it reports a
    # real share of the work as well.
    def _on_swap_checked(self, checked: int, total: int) -> None:
        self.update_progress_text.emit(self.tr("checking swaps") + f" {checked + 1}/{total}...")
        self.update_progress.emit(100.0 * checked / total if total else 100.0)

    # ... and the same for the pending transfer legs, which are asked about one network request at a time as well
    def _on_leg_checked(self, checked: int, total: int) -> None:
        self.update_progress_text.emit(self.tr("settling transfers") + f" {checked + 1}/{total}...")
        self.update_progress.emit(100.0 * checked / total if total else 100.0)

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
        # Bitcoin has no contracts at all, hence no tokens to tell apart and no list to download: everything a BTC
        # wallet ever holds is BTC itself. The gate would abort every fetch of it over a cache that can never fill.
        if location_id == AssetLocation.BTC_BLOCKCHAIN:
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
