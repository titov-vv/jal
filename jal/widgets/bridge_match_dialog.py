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
# Lets the user complete a pending half-bridge by hand - which is the only way it can be completed, as the arriving leg
# of a cross-chain move is indistinguishable from any other receipt and is therefore imported as a plain transfer.
# The dialog lists the transfers that could be that arrival and says what accepting each one will create: a Bridge when
# it carries the same asset, or a cross-chain Swap when the asset changed on the way (BridgeMatcher decides).
# The caller emits its dbUpdated to rebuild the ledger.
class BridgeMatchDialog(QDialog):
    def __init__(self, half_oid, parent=None):
        super().__init__(parent)
        self._half_oid = half_oid
        self._matcher = BridgeMatcher()
        self.setWindowTitle(self.tr("Match cross-chain legs"))
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(self.tr("Choose the transfer that this operation arrived as:")))
        self._list = QListWidget(self)
        layout.addWidget(self._list)
        self._options = self._collect_options()
        for _, label in self._options:
            self._list.addItem(QListWidgetItem(label))
        if self._options:
            self._list.setCurrentRow(0)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # (oid, label) for every transfer offered as the arriving leg
    def _collect_options(self) -> list:
        return [(oid, self._transfer_label(oid) + self._result_of(oid))
                for oid in self._matcher.transfer_candidates(self._half_oid)]

    # Names the operation the pair would become, as the same picker offers both (a swap is a disposal, a bridge is not)
    def _result_of(self, oid) -> str:
        if self._matcher.pair_kind(self._half_oid, oid) == BridgeMatcher.SWAP:
            return " → " + self.tr("cross-chain swap")
        return " → " + self.tr("bridge")

    def _transfer_label(self, oid) -> str:
        row = JalDB._read("SELECT withdrawal, deposit_timestamp, deposit_account, symbol_id "
                          "FROM transfers WHERE oid=:oid", [(":oid", oid)], named=True)
        asset_id = JalSymbol(row['symbol_id']).asset().id()
        return self._describe(row['deposit_account'], asset_id, Decimal(row['withdrawal']), row['deposit_timestamp'])

    @staticmethod
    def _describe(account_id, asset_id, qty, timestamp) -> str:
        return f"{qty} {JalAsset(asset_id).symbol()} — {JalAccount(account_id).name()}, {ts2dt(timestamp)}"

    def accept(self):
        row = self._list.currentRow()
        if row < 0 or row >= len(self._options):
            return
        oid, _ = self._options[row]
        try:
            self._matcher.match_with_transfer(self._half_oid, oid)
        except BridgeMatchError as e:
            QMessageBox().warning(self, self.tr("Cannot match operation"), str(e))
            return
        super().accept()
