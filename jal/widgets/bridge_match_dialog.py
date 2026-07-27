from decimal import Decimal
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QListWidget, QListWidgetItem,
                               QDialogButtonBox, QMessageBox)
from jal.db.db import JalDB
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.symbol import JalSymbol
from jal.db.bridge_matcher import BridgeMatcher, BridgeMatchError
from jal.net.arrival_reconciler import ArrivalReconciler
from jal.widgets.helpers import ts2dt


# ----------------------------------------------------------------------------------------------------------------------
# Lets the user complete a pending half-bridge, whose arriving leg is otherwise unrecognizable: it looks like any other
# receipt and is imported as a plain transfer. The dialog lists the transfers that could be that arrival and says what
# accepting each one will create: a Bridge when it carries the same asset, or a cross-chain Swap when the asset changed
# on the way (BridgeMatcher decides).
#
# Whoever routed the move is asked as well (jal/net/arrival_reconciler.py), because they recorded both ends and JAL
# saw only one. What they answer is used in whichever of three ways fits:
#   * it names one of the listed transfers as the arrival -> that transfer is marked and offered first, and it is what
#     the user should accept: adopting the real transfer consumes it, while booking a leg beside it would leave the
#     same movement in the ledger twice;
#   * no transfer matches, but the arrival can be placed -> it is offered as a leg of its own, which is the only way to
#     complete a move whose destination chain JAL has not fetched (or has no fetcher for at all);
#   * the arrival is known but cannot be placed -> what stands in the way is shown, since it names exactly what the
#     user has to create.
# Nothing is ever accepted automatically: a wrong counter-leg mis-books money as badly as a missing one, so the choice
# stays the user's. The caller emits its dbUpdated to rebuild the ledger.
#
# The reconciler is passed in rather than built here. Which sources exist, in what order they are asked and how far
# each may be believed is not the dialog's business (jal/net/route_resolvers.py decides it, for the pending transfer
# legs just as much as for this), and a caller that has already asked hands over what it holds rather than paying
# for the same lookup twice - a reconciler caches its answers for as long as it lives.
class BridgeMatchDialog(QDialog):
    TRANSFER = 'transfer'   # the option adopts an existing transfer, which is consumed by the match
    LEG = 'leg'             # ... or books the arriving leg from what the aggregator reported

    def __init__(self, half_oid, parent=None, reconciler=None):
        super().__init__(parent)
        self._half_oid = half_oid
        self._matcher = BridgeMatcher()
        self._reconciler = reconciler if reconciler is not None else ArrivalReconciler()
        self.setWindowTitle(self.tr("Match cross-chain legs"))
        layout = QVBoxLayout(self)
        self._proposal = self._ask_resolvers()
        if self._proposal is not None:
            layout.addWidget(QLabel(self._proposal.route.source + self.tr(" reports this move as: ")
                                    + self._proposal.text))
            if self._proposal.problem:
                layout.addWidget(QLabel(self._proposal.problem))
        layout.addWidget(QLabel(self.tr("Choose the transfer that this operation arrived as:")))
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

    # What the sources recorded about the sending transaction, or None when none of them knows anything about it -
    # which is the ordinary answer for a move routed by somebody they don't cover. The lookup goes to the network, so
    # the wait is shown.
    def _ask_resolvers(self):
        QGuiApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            return self._reconciler.arrival_of_half(self._half_oid)
        finally:
            QGuiApplication.restoreOverrideCursor()

    # (kind, payload, label) for every option offered, best first
    def _collect_options(self) -> list:
        arrival_hash = self._reported_arrival_hash()
        options = []
        confirmed = []
        for oid in self._matcher.transfer_candidates(self._half_oid):
            label = self._transfer_label(oid) + self._result_of(oid)
            if arrival_hash and self._transfer_hash(oid).lower() == arrival_hash.lower():
                confirmed.append((self.TRANSFER, oid,
                                  label + self.tr(" — confirmed by ") + self._proposal.route.source))
            else:
                options.append((self.TRANSFER, oid, label))
        if confirmed:
            # The reported arrival is already in the ledger as this transfer; offering to book it a second time as a
            # leg of its own would duplicate the movement, so only the transfer is offered.
            return confirmed + options
        leg = self._proposal.leg if self._proposal is not None and self._proposal.is_placeable() else None
        # A leg that would not form a valid operation is not offered at all - the same refusal a mismatching transfer
        # gets, and for the same reasons (an arrival that precedes its departure, a bridge delivering more than it was
        # sent). What was reported is still shown above the list, so the disagreement stays visible.
        if leg is not None and self._matcher.leg_kind(self._half_oid, leg) is not None:
            options.insert(0, (self.LEG, leg, self._leg_label(leg)))
        return options

    # The destination transaction hash that was reported, or '' when nothing usable was. It is the one thing every
    # source states exactly, whatever its confidence tier: a source that may not say how much arrived can still say
    # which of the listed transfers IS the arrival, and that is the answer worth the most here anyway.
    def _reported_arrival_hash(self) -> str:
        if self._proposal is None or self._proposal.route is None:
            return ''
        return self._proposal.route.receiving.tx_hash

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
    def _transfer_hash(oid) -> str:
        return JalDB._read("SELECT number FROM transfers WHERE oid=:oid", [(":oid", oid)]) or ''

    # An arrival that has no transfer of its own is described from the leg that would be booked for it, so that it
    # reads exactly like the transfer options it stands among.
    def _leg_label(self, leg: dict) -> str:
        described = self._describe(leg['account_id'], leg['asset_id'], leg['qty'], leg['timestamp'])
        kind = self.tr("cross-chain swap") if self._matcher.leg_kind(self._half_oid, leg) == BridgeMatcher.SWAP \
            else self.tr("bridge")
        return described + " → " + kind + self.tr(" — booked from ") + self._proposal.route.source \
            + self.tr(", not yet fetched from the chain")

    @staticmethod
    def _describe(account_id, asset_id, qty, timestamp) -> str:
        return f"{qty} {JalAsset(asset_id).symbol()} — {JalAccount(account_id).name()}, {ts2dt(timestamp)}"

    def accept(self):
        row = self._list.currentRow()
        if row < 0 or row >= len(self._options):
            return
        kind, payload, _ = self._options[row]
        try:
            if kind == self.LEG:
                self._matcher.match_with_leg(self._half_oid, payload)
            else:
                self._matcher.match_with_transfer(self._half_oid, payload)
        except BridgeMatchError as e:
            QMessageBox().warning(self, self.tr("Cannot match operation"), str(e))
            return
        super().accept()
