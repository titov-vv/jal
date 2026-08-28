from functools import partial

from PySide6.QtCore import Qt, Slot, QObject, QModelIndex, QPoint
from PySide6.QtWidgets import QDialog, QMenu, QMessageBox
from jal.ui.reports.ui_unsettled_transfers_report import Ui_UnsettledTransfersWidget
from jal.reports.reports import Reports
from jal.db.clock import now_dt
from jal.db.asset import JalAsset
from jal.db.pending_transfers_model import PendingTransfersModel
from jal.db.transfer_settlement import TransferSettlement
from jal.widgets.bridge_convert_dialog import BridgeConvertDialog
from jal.widgets.bridge_match_dialog import BridgeMatchDialog
from jal.widgets.mdi import MdiWidget
from jal.widgets.swap_convert_dialog import SwapConvertDialog
from jal.widgets.transfer_assign_dialog import TransferAssignDialog
from jal.widgets.transfer_match_dialog import TransferMatchDialog
from jal.widgets.helpers import set_grids_row_height

JAL_REPORT_CLASS = "UnsettledTransfersReport"


# ----------------------------------------------------------------------------------------------------------------------
# Lists the transfer legs that are still waiting for their counterpart. A transfer may be recorded knowing only one
# of its two ends ("money on the way"), which replaced guessing the other end at import time; this report is what
# keeps those legs from accumulating unnoticed, and it values the money that is in flight and therefore belongs to
# no account at all.
class UnsettledTransfersReport(QObject):
    def __init__(self):
        super().__init__()
        self.name = self.tr("&Unsettled transfers")
        self.window_class = "UnsettledTransfersReportWindow"


# ----------------------------------------------------------------------------------------------------------------------
class UnsettledTransfersReportWindow(MdiWidget):
    def __init__(self, parent: Reports, settings: dict = None):
        super().__init__(parent.mdi_area())
        self.ui = Ui_UnsettledTransfersWidget()
        self.ui.setupUi(self)
        set_grids_row_height(self)
        self._parent = parent
        self.name = self.tr("Unsettled transfers")

        self.transfers_model = PendingTransfersModel(self.ui.ReportTreeView)
        self.ui.ReportTreeView.setModel(self.transfers_model)
        self.ui.ReportTreeView.setContextMenuPolicy(Qt.CustomContextMenu)
        # The list is a worklist rather than a statement, so its order is a question the user asks of it ("the
        # oldest leg", "the largest amount still in flight") rather than a property of the data. The indicator is
        # set to the order the model builds by default, so the header doesn't claim a different one.
        self.ui.ReportTreeView.setSortingEnabled(True)
        self.ui.ReportTreeView.sortByColumn(self.transfers_model.fieldIndex('timestamp'), Qt.AscendingOrder)
        # The chooser is filled from the model, so what it offers and the headings that come out of it are one list
        self.ui.GroupCombo.addItem(self.tr("Nothing"), '')
        for field, name in self.transfers_model.groupings():
            self.ui.GroupCombo.addItem(name, field)

        self.ui.ReportDate.setDate(now_dt().date())
        self.ui.ReportCurrencyCombo.setIndex(JalAsset.get_base_currency())

        self.connect_signals_and_slots()
        self.updateReport()

    def connect_signals_and_slots(self):
        self.ui.ReportDate.dateChanged.connect(self.updateReport)
        self.ui.ReportCurrencyCombo.changed.connect(self.updateReport)
        self.ui.BasisGapsCheck.stateChanged.connect(self.updateReport)
        self.ui.FilterEdit.textChanged.connect(self.updateReport)
        self.ui.GroupCombo.currentIndexChanged.connect(self.updateReport)
        self.ui.UnsolicitedCheck.stateChanged.connect(self.updateReport)
        self.ui.SettleButton.pressed.connect(self.settleAll)
        self.ui.MatchButton.pressed.connect(self.matchLegs)
        self.ui.AssignButton.pressed.connect(self.assignAccount)
        self.ui.SwapButton.pressed.connect(self.convertToSwap)
        self.ui.BridgeButton.pressed.connect(self.convertToBridge)
        self.ui.DustButton.pressed.connect(self.writeOffAsDust)
        self.ui.LegendButton.pressed.connect(self.showLegend)
        self.ui.ReportTreeView.doubleClicked.connect(self.matchLegAt)
        self.ui.ReportTreeView.customContextMenuRequested.connect(self.onContextMenu)
        # Assigning and converting into a swap act on the row that is selected, so without one there is nothing for
        # either button to do. Matching is different - it opens on the whole list and needs no row at all.
        self.ui.ReportTreeView.selectionModel().selectionChanged.connect(self.onSelectionChanged)
        self.ui.AssignButton.setEnabled(False)
        self.ui.SwapButton.setEnabled(False)
        self.ui.BridgeButton.setEnabled(False)
        self.ui.DustButton.setEnabled(False)
        self.ui.SaveButton.pressed.connect(partial(self._parent.save_report, self.name, self.ui.ReportTreeView.model()))

    # The list is a read of the 'transfers' table, so everything that writes one leaves it stale - not only the
    # settlements started from here, but an import that brings in the missing counterpart, an operation edited in the
    # main window, a transfer deleted. What all of those have in common is the ledger rebuild that follows them, and
    # this is what the main window calls on every open report when it happens (MdiWidget.refresh).
    def refresh(self):
        self.updateReport(reload=True)
        self.updateRowButtons()

    # 'reload' is for the case the parameters below can't express: the list is the same list, shown for the same date
    # in the same currency, and what changed is the data under it (see _settled)
    @Slot()
    def updateReport(self, reload: bool = False):
        grouping = self.ui.GroupCombo.currentData() or ''   # None while the chooser is still being filled
        # A flat list needs no expanders, and showing them would indent every row for nothing
        self.ui.ReportTreeView.setRootIsDecorated(bool(grouping))
        self.ui.ReportTreeView.model().updateView(currency_id=self.ui.ReportCurrencyCombo.selected_id,
                                                  date=self.ui.ReportDate.date(),
                                                  with_basis_gaps=self.ui.BasisGapsCheck.isChecked(),
                                                  filter_text=self.ui.FilterEdit.text(), grouping=grouping,
                                                  hide_unsolicited=self.ui.UnsolicitedCheck.isChecked(),
                                                  update=reload)

    # Runs the settlements that need nobody's judgement: the legs that one and the same transaction hash pairs, and
    # the legs that name an address an account of the user's holds. Both act on PROOF rather than on a resemblance,
    # which is why they commit without asking - the same passes an import runs, and for the same reason.
    #
    # They are reachable from here because an import is not the only thing that makes them able to settle something.
    # What they need may have appeared since: an address settles the moment an account holding it is created, and a
    # rule they follow may itself have been corrected. Without this the only way to re-run them over legs already
    # stored is to import something, which is not an answer to "why is this leg still here".
    @Slot()
    def settleAll(self):
        settled = TransferSettlement().settle_all()
        self._settled(settled > 0)
        if settled:
            message = self.tr("Transfers settled: ") + f"{settled}"
        else:
            message = self.tr("Nothing could be settled on its own - what is left needs Match or Assign.")
        QMessageBox().information(self, self.name, message)

    # Opens the two-panel matcher. This report is the worklist the matcher works through, which is why it is opened
    # from here - settling is a batch job rather than something done to one operation at a time.
    @Slot()
    def matchLegs(self):
        self._match(0)

    # ... and a double-click opens it with the leg that was clicked already chosen in its panel
    @Slot(QModelIndex)
    def matchLegAt(self, index):
        if self._pending_oid(index):
            self._match(self._pending_oid(index))

    # Names the account at the missing end of the selected leg - the settlement for a counterpart that will never be
    # imported, and so has nothing to be matched against
    @Slot()
    def assignAccount(self):
        oid = self._pending_oid(self.ui.ReportTreeView.currentIndex())
        if not oid:
            return
        dialog = TransferAssignDialog(oid, parent=self)
        dialog.exec()
        self._settled(dialog.changed)

    # Names the staked position at the missing end of the selected leg. It is the same assignment as above - a box is
    # an account and what moved into it is a transfer - offered as an action of its own because the box is hidden
    # from the ordinary chooser and because this is where a position is usually met for the first time.
    @Slot()
    def assignStakingBox(self):
        oid = self._pending_oid(self.ui.ReportTreeView.currentIndex())
        if not oid:
            return
        dialog = TransferAssignDialog(oid, parent=self, staking=True)
        dialog.exec()
        self._settled(dialog.changed)

    # Replaces the selected leg and the one it was exchanged with by the single Swap operation the two always were -
    # for the pairs that are not a transfer at all, and that no settlement can therefore ever pair (see
    # SwapConvertDialog).
    @Slot()
    def convertToSwap(self):
        oid = self._pending_oid(self.ui.ReportTreeView.currentIndex())
        if not oid:
            return
        dialog = SwapConvertDialog(oid, parent=self)
        dialog.exec()
        self._settled(dialog.changed)

    # Replaces the selected leg and the arrival it crossed chains as by the single Bridge operation the two are. The
    # move whose send the fetcher DID recognize never gets here - it is a pending half-bridge already, and the bridge
    # matcher completes it (see matchBridge) - so this is for the one that was imported as two plain transfers.
    @Slot()
    def convertToBridge(self):
        oid = self._pending_oid(self.ui.ReportTreeView.currentIndex())
        if not oid:
            return
        dialog = BridgeConvertDialog(oid, parent=self)
        dialog.exec()
        self._settled(dialog.changed)

    # Completes a pending half-bridge listed here, with the same dialog the Operations list opens on it
    @Slot()
    def matchBridge(self):
        oid = self._pending_bridge_oid(self.ui.ReportTreeView.currentIndex())
        if not oid:
            return
        self._settled(BridgeMatchDialog(oid, self).exec() == QDialog.Accepted)

    # Writes off a leg that arrived from nowhere. It asks first, and names what is about to happen, because this is
    # the one action here that decides an arrival was never a transfer at all - the coins stay in the account, but
    # nothing will look for the other end of them again.
    @Slot()
    def writeOffAsDust(self):
        oid = self._pending_oid(self.ui.ReportTreeView.currentIndex())
        if not oid:
            return
        refusal = TransferSettlement().refusal_to_mark_dust(oid)
        if refusal:
            QMessageBox().warning(self, self.name, self.tr("This leg can't be written off: ") + refusal)
            return
        question = self.tr("Record this as a dust attack?\n\nThe asset stays in the account it arrived on, at a cost "
                           "basis of zero, and the leg stops waiting for a sender it never had.")
        if QMessageBox().question(self, self.name, question) != QMessageBox.Yes:
            return
        refusal = TransferSettlement().mark_as_dust(oid)
        if refusal:
            QMessageBox().warning(self, self.name, self.tr("This leg can't be written off: ") + refusal)
            return
        self._settled(True)

    # Writes off every poisoning arrival at once. This is the one bulk settlement that needs nobody's judgement, and
    # for the same reason the passes behind Settle don't: a poisoning leg is identified by an address MINTED to
    # imitate one of the user's own accounts, which is a fact about the address rather than a resemblance between
    # two amounts. It is also the one that arrives in bulk - the attack is cheap to repeat, so a wallet collects
    # them by the dozen, and writing them off one dialog at a time is what leaves them sitting in the worklist.
    #
    # A suspected airdrop is never included: that IS a resemblance ("nothing else in this wallet has dealt in this
    # asset"), and a first genuine acquisition looks exactly like one until the second one happens.
    @Slot()
    def writeOffPoisoning(self):
        oids = self.ui.ReportTreeView.model().poisoning_oids()
        if not oids:
            return
        question = self.tr("Write off every arrival from a poisoned address?") + f"\n\n{len(oids)} " \
                   + self.tr("legs are recorded as dust attacks. Each asset stays in the account it arrived on, at "
                             "a cost basis of zero, and none of them waits for a sender again.")
        if QMessageBox().question(self, self.name, question) != QMessageBox.Yes:
            return
        settlement = TransferSettlement()
        refusals = [refusal for refusal in (settlement.mark_as_dust(oid) for oid in oids) if refusal]
        self._settled(len(refusals) < len(oids))
        if refusals:
            QMessageBox().warning(self, self.name, self.tr("Some legs could not be written off: ")
                                  + f"{len(refusals)}/{len(oids)}")

    @Slot()
    def onSelectionChanged(self, _selected, _deselected):
        self.updateRowButtons()

    # Whether there is a row for the buttons to act on. Called on a reload as well as on a selection: resetting a
    # model drops the selection WITHOUT emitting selectionChanged, so after a reload a button would otherwise stay
    # enabled over the row that was just settled and is no longer there.
    def updateRowButtons(self):
        index = self.ui.ReportTreeView.currentIndex()
        pending = bool(self._pending_oid(index))
        self.ui.AssignButton.setEnabled(pending)
        self.ui.SwapButton.setEnabled(pending)
        # The Bridge button converts two transfer legs, so a half-bridge row is not what it acts on - that row is
        # completed from its context menu instead
        self.ui.BridgeButton.setEnabled(pending)
        # Only an ARRIVAL can be unsolicited: what the user sent, the user sent
        self.ui.DustButton.setEnabled(bool(pending and not TransferSettlement().refusal_to_mark_dust(
            self._pending_oid(index))))

    @Slot(QPoint)
    def onContextMenu(self, position):
        index = self.ui.ReportTreeView.indexAt(position)
        self.ui.ReportTreeView.setCurrentIndex(index)
        menu = QMenu(self.ui.ReportTreeView)
        if self._pending_bridge_oid(index):
            # A half-bridge is completed by the bridge matcher, which needs no second leg from this list - the action
            # is named exactly as in the Operations list, because it is the same one
            menu.addAction(self.tr("Match cross-chain legs..."), self.matchBridge)
        elif self._pending_oid(index):
            menu.addAction(self.tr("Assign an account..."), self.assignAccount)
            menu.addAction(self.tr("Assign a staked position..."), self.assignStakingBox)
            menu.addAction(self.tr("Match with another leg..."), partial(self.matchLegAt, index))
            menu.addAction(self.tr("Convert into a swap..."), self.convertToSwap)
            menu.addAction(self.tr("Convert into a bridge..."), self.convertToBridge)
            if not TransferSettlement().refusal_to_mark_dust(self._pending_oid(index)):
                menu.addSeparator()
                menu.addAction(self.tr("Write off as dust..."), self.writeOffAsDust)
        elif self.transfers_model.transfer_kind(index) == PendingTransfersModel.BASIS:
            # No settlement applies to a settled transfer, but a right-click that opens nothing at all reads as a
            # broken menu rather than as an answer - so the row says what it is waiting for and where that is done
            menu.addAction(self.tr("Why is this listed?"), self.explainBasisGap)
        else:
            return   # a group heading, or a row nothing can be done to from here
        # Offered wherever the click landed: it acts on the whole list rather than on the row under the cursor, and
        # a wallet that collects these has them scattered through it
        poisoned = self.transfers_model.poisoning_oids()
        if poisoned:
            menu.addSeparator()
            menu.addAction(self.tr("Write off all poisoning arrivals") + f" ({len(poisoned)})...",
                           self.writeOffPoisoning)
        menu.popup(self.ui.ReportTreeView.viewport().mapToGlobal(position))

    # What a row listed for a missing cost basis is waiting for. It is not a settlement - the transfer is complete -
    # so it is not one of this report's actions, and the answer is where the number itself has to be stated.
    @Slot()
    def explainBasisGap(self):
        QMessageBox().information(self, self.name,
                                  self.tr("This transfer is settled - both of its ends are known - so nothing here "
                                          "can pair it. What is missing is what the asset COST: the two accounts "
                                          "are kept in different currencies, and nothing stated the value the asset "
                                          "arrived at, so its lots opened at zero and the whole of a later sale "
                                          "would be taxed as gain.\n\nA zero may well be right. If it isn't, open "
                                          "this transfer in the operations list and state the amount it arrived "
                                          "for, in the currency of the receiving account."))

    @Slot()
    def showLegend(self):
        rows = "".join(f"<tr><td style='background-color:{color.name()};width:24px;'>&nbsp;</td>"
                       f"<td>&nbsp;{caption}</td></tr>" for color, caption in self.transfers_model.legend())
        QMessageBox().information(self, self.name, f"<table cellspacing='4'>{rows}</table>")

    # oid of the row, but only while it is a TRANSFER leg waiting for its counterpart - which is what every action on
    # this page acts on. Two kinds of row are not that and must never reach one:
    #   * a row listed for a missing cost basis is a settled transfer, and every settlement would refuse it - it is
    #     shown to be looked at;
    #   * a pending half-bridge names an oid in 'bridges', not in 'transfers'. Passing it on would be worse than
    #     refusing it, because the number is perfectly valid in the wrong table and would settle another operation
    #     entirely, so the kind is checked here rather than trusted to a refusal further down.
    def _pending_oid(self, index) -> int:
        model = self.ui.ReportTreeView.model()
        if model.transfer_kind(index) in (PendingTransfersModel.BASIS, PendingTransfersModel.BRIDGE):
            return 0
        return model.transfer_oid(index)

    # ... and the other side of that: the oid of a pending half-bridge row, which only the bridge matcher acts on
    def _pending_bridge_oid(self, index) -> int:
        model = self.ui.ReportTreeView.model()
        if model.transfer_kind(index) != PendingTransfersModel.BRIDGE:
            return 0
        return model.transfer_oid(index)

    def _match(self, oid: int):
        dialog = TransferMatchDialog(oid, parent=self)
        dialog.exec()
        self._settled(dialog.changed)

    # What a settlement leaves behind. The leg it settled is not pending any more, so the row that offered it has to
    # go: left standing it is a worklist entry for work already done, and every action on it would be refused (which
    # is a message about the report being stale, not about the transfer).
    def _settled(self, changed: bool):
        if changed:
            # Settling writes real operations, so the ledger has to catch up before the figures shown are true again.
            # Reports is constructed by the main window, which owns the Ledger - the same one every editor uses.
            self._parent.parent.ledger.rebuild()
            # Refreshed here rather than left to the rebuild's own signal: that route runs through the main window,
            # and this report is opened in tests and reachable in ways that don't involve one.
            self.refresh()
