from decimal import Decimal
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QListWidget, QListWidgetItem,
                               QDialogButtonBox, QMessageBox)
from jal.db.db import JalDB
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.symbol import JalSymbol
from jal.db.bridge_matcher import BridgeMatcher, BridgeMatchError
from jal.widgets.helpers import ts2dt


# ----------------------------------------------------------------------------------------------------------------------
# Lets the user complete a pending half-bridge by hand: it lists the counterparts that could form a valid bridge with
# it - other pending half-bridges fetched from the other chain, and existing incoming/outgoing asset transfers that
# are really this bridge's other leg (the fetcher couldn't tell, so it imported them as plain transfers). Picking one
# and accepting fuses them into a complete bridge (BridgeMatcher). The caller emits its dbUpdated to rebuild the ledger.
class BridgeMatchDialog(QDialog):
    def __init__(self, half_oid, parent=None):
        super().__init__(parent)
        self._half_oid = half_oid
        self._matcher = BridgeMatcher()
        self._halves_by_oid = {h['oid']: h for h in self._matcher._pending_halves()}
        self.setWindowTitle(self.tr("Match bridge"))
        layout = QVBoxLayout(self)
        target = self._halves_by_oid.get(half_oid)
        need = self.tr("receiving") if (target and target['is_out']) else self.tr("sending")
        layout.addWidget(QLabel(self.tr("Choose the {0} leg that completes this bridge:").format(need)))
        self._list = QListWidget(self)
        layout.addWidget(self._list)
        self._options = self._collect_options()
        for _, _, label in self._options:
            self._list.addItem(QListWidgetItem(label))
        if self._options:
            self._list.setCurrentRow(0)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # (kind, oid, label) for every counterpart offered - pending halves first, then adoptable transfers
    def _collect_options(self) -> list:
        options = []
        for oid in self._matcher.candidates(self._half_oid):
            h = self._halves_by_oid[oid]
            options.append(('half', oid,
                            self._describe(h['account_id'], h['asset_id'], h['qty'], h['timestamp'], self.tr("bridge half"))))
        for oid in self._matcher.transfer_candidates(self._half_oid):
            options.append(('transfer', oid, self._transfer_label(oid)))
        return options

    def _transfer_label(self, oid) -> str:
        row = JalDB._read("SELECT withdrawal_timestamp, withdrawal_account, withdrawal, deposit_timestamp, "
                          "deposit_account, symbol_id FROM transfers WHERE oid=:oid", [(":oid", oid)], named=True)
        target = self._halves_by_oid.get(self._half_oid)
        if target and target['is_out']:   # a pending send-half adopts the transfer's deposit (arrival) side
            account_id, timestamp = row['deposit_account'], row['deposit_timestamp']
        else:                             # a pending receive-half adopts the transfer's withdrawal (departure) side
            account_id, timestamp = row['withdrawal_account'], row['withdrawal_timestamp']
        asset_id = JalSymbol(row['symbol_id']).asset().id()
        return self._describe(account_id, asset_id, Decimal(row['withdrawal']), timestamp, self.tr("transfer"))

    @staticmethod
    def _describe(account_id, asset_id, qty, timestamp, kind) -> str:
        return f"{qty} {JalAsset(asset_id).symbol()} — {JalAccount(account_id).name()}, {ts2dt(timestamp)} ({kind})"

    def accept(self):
        row = self._list.currentRow()
        if row < 0 or row >= len(self._options):
            return
        kind, oid, _ = self._options[row]
        try:
            if kind == 'half':
                self._matcher.match(self._half_oid, oid)
            else:
                self._matcher.match_with_transfer(self._half_oid, oid)
        except BridgeMatchError as e:
            QMessageBox().warning(self, self.tr("Cannot match bridge"), str(e))
            return
        super().accept()
