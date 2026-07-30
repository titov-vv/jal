from functools import partial

from PySide6.QtCore import Qt, Slot, QObject, QDateTime, QModelIndex, QPoint
from PySide6.QtWidgets import QMenu
from jal.ui.reports.ui_unsettled_transfers_report import Ui_UnsettledTransfersWidget
from jal.reports.reports import Reports
from jal.db.asset import JalAsset
from jal.db.pending_transfers_model import PendingTransfersModel
from jal.widgets.mdi import MdiWidget
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
        self.ui.MatchButton.pressed.connect(self.matchLegs)
        self.ui.AssignButton.pressed.connect(self.assignAccount)
        self.ui.ReportTreeView.doubleClicked.connect(self.matchLegAt)
        self.ui.ReportTreeView.customContextMenuRequested.connect(self.onContextMenu)
        # Assigning acts on the row that is selected, so without one there is nothing for the button to do. Matching
        # is different - it opens on the whole list and needs no row at all.
        self.ui.ReportTreeView.selectionModel().selectionChanged.connect(self.onSelectionChanged)
        self.ui.AssignButton.setEnabled(False)
        self.ui.SaveButton.pressed.connect(partial(self._parent.save_report, self.name, self.ui.ReportTreeView.model()))

    @Slot()
    def updateReport(self):
        self.ui.ReportTreeView.model().updateView(currency_id=self.ui.ReportCurrencyCombo.selected_id,
                                                  date=self.ui.ReportDate.date(),
                                                  with_basis_gaps=self.ui.BasisGapsCheck.isChecked())

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

    @Slot()
    def onSelectionChanged(self, _selected, _deselected):
        self.ui.AssignButton.setEnabled(bool(self._pending_oid(self.ui.ReportTreeView.currentIndex())))

    @Slot(QPoint)
    def onContextMenu(self, position):
        index = self.ui.ReportTreeView.indexAt(position)
        if not self._pending_oid(index):
            return   # a transfer that only lacks a cost basis is settled already - neither action applies to it
        self.ui.ReportTreeView.setCurrentIndex(index)
        menu = QMenu(self.ui.ReportTreeView)
        menu.addAction(self.tr("Assign an account..."), self.assignAccount)
        menu.addAction(self.tr("Match with another leg..."), partial(self.matchLegAt, index))
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

    def _settled(self, changed: bool):
        if changed:
            # Settling writes real operations, so the ledger has to catch up before the figures shown are true again.
            # Reports is constructed by the main window, which owns the Ledger - the same one every editor uses.
            self._parent.parent.ledger.rebuild()
            self.updateReport()
