from functools import partial

from PySide6.QtCore import Qt, Slot, QObject, QDateTime, QModelIndex, QPoint
from PySide6.QtWidgets import QMenu, QMessageBox
from jal.ui.reports.ui_unsettled_transfers_report import Ui_UnsettledTransfersWidget
from jal.reports.reports import Reports
from jal.db.asset import JalAsset
from jal.db.pending_transfers_model import PendingTransfersModel
from jal.db.transfer_settlement import TransferSettlement
from jal.widgets.mdi import MdiWidget
from jal.widgets.swap_convert_dialog import SwapConvertDialog
from jal.widgets.transfer_assign_dialog import TransferAssignDialog
from jal.widgets.transfer_match_dialog import TransferMatchDialog

JAL_REPORT_CLASS = "UnsettledTransfersReport"


# ----------------------------------------------------------------------------------------------------------------------
# Lists the transfer legs that are still waiting for their counterpart. A transfer may be recorded knowing only one
# of its two ends ("money on the way"), which replaced guessing the other end at import time; this report is what
# keeps those legs from accumulating unnoticed, and it values the money that is in flight and therefore belongs to
# no account at all.
class UnsettledTransfersReport(QObject):
    def __init__(self):
        super().__init__()
        self.name = self.tr("Unsettled transfers")
        self.window_class = "UnsettledTransfersReportWindow"


# ----------------------------------------------------------------------------------------------------------------------
class UnsettledTransfersReportWindow(MdiWidget):
    def __init__(self, parent: Reports, settings: dict = None):
        super().__init__(parent.mdi_area())
        self.ui = Ui_UnsettledTransfersWidget()
        self.ui.setupUi(self)
        self._parent = parent
        self.name = self.tr("Unsettled transfers")

        self.transfers_model = PendingTransfersModel(self.ui.ReportTreeView)
        self.ui.ReportTreeView.setModel(self.transfers_model)
        self.ui.ReportTreeView.setContextMenuPolicy(Qt.CustomContextMenu)

        current_time = QDateTime.currentDateTime()
        current_time.setTimeSpec(Qt.UTC)   # We use UTC everywhere so need to force TZ info
        self.ui.ReportDate.setDateTime(current_time)
        self.ui.ReportCurrencyCombo.setIndex(JalAsset.get_base_currency())

        self.connect_signals_and_slots()
        self.updateReport()

    def connect_signals_and_slots(self):
        self.ui.ReportDate.dateChanged.connect(self.updateReport)
        self.ui.ReportCurrencyCombo.changed.connect(self.updateReport)
        self.ui.BasisGapsCheck.stateChanged.connect(self.updateReport)
        self.ui.SettleButton.pressed.connect(self.settleAll)
        self.ui.MatchButton.pressed.connect(self.matchLegs)
        self.ui.AssignButton.pressed.connect(self.assignAccount)
        self.ui.SwapButton.pressed.connect(self.convertToSwap)
        self.ui.ReportTreeView.doubleClicked.connect(self.matchLegAt)
        self.ui.ReportTreeView.customContextMenuRequested.connect(self.onContextMenu)
        # Assigning and converting into a swap act on the row that is selected, so without one there is nothing for
        # either button to do. Matching is different - it opens on the whole list and needs no row at all.
        self.ui.ReportTreeView.selectionModel().selectionChanged.connect(self.onSelectionChanged)
        self.ui.AssignButton.setEnabled(False)
        self.ui.SwapButton.setEnabled(False)
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
        self.ui.ReportTreeView.model().updateView(currency_id=self.ui.ReportCurrencyCombo.selected_id,
                                                  date=self.ui.ReportDate.date(),
                                                  with_basis_gaps=self.ui.BasisGapsCheck.isChecked(), update=reload)

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

    @Slot()
    def onSelectionChanged(self, _selected, _deselected):
        self.updateRowButtons()

    # Whether there is a row for the buttons to act on. Called on a reload as well as on a selection: resetting a
    # model drops the selection WITHOUT emitting selectionChanged, so after a reload a button would otherwise stay
    # enabled over the row that was just settled and is no longer there.
    def updateRowButtons(self):
        pending = bool(self._pending_oid(self.ui.ReportTreeView.currentIndex()))
        self.ui.AssignButton.setEnabled(pending)
        self.ui.SwapButton.setEnabled(pending)

    @Slot(QPoint)
    def onContextMenu(self, position):
        index = self.ui.ReportTreeView.indexAt(position)
        if not self._pending_oid(index):
            return   # a transfer that only lacks a cost basis is settled already - neither action applies to it
        self.ui.ReportTreeView.setCurrentIndex(index)
        menu = QMenu(self.ui.ReportTreeView)
        menu.addAction(self.tr("Assign an account..."), self.assignAccount)
        menu.addAction(self.tr("Match with another leg..."), partial(self.matchLegAt, index))
        menu.addAction(self.tr("Convert into a swap..."), self.convertToSwap)
        menu.popup(self.ui.ReportTreeView.viewport().mapToGlobal(position))

    # oid of the row, but only while it is a leg waiting for an account. The rows listed for a missing cost basis are
    # settled transfers, and every settlement action would refuse them - the report shows them to be looked at.
    def _pending_oid(self, index) -> int:
        model = self.ui.ReportTreeView.model()
        if model.transfer_kind(index) == PendingTransfersModel.BASIS:
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
