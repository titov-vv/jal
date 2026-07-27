from functools import partial

from PySide6.QtCore import Qt, Slot, QObject, QDateTime, QModelIndex
from jal.ui.reports.ui_unsettled_transfers_report import Ui_UnsettledTransfersWidget
from jal.reports.reports import Reports
from jal.db.asset import JalAsset
from jal.db.pending_transfers_model import PendingTransfersModel
from jal.widgets.mdi import MdiWidget
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

        current_time = QDateTime.currentDateTime()
        current_time.setTimeSpec(Qt.UTC)   # We use UTC everywhere so need to force TZ info
        self.ui.ReportDate.setDateTime(current_time)
        self.ui.ReportCurrencyCombo.setIndex(JalAsset.get_base_currency())

        self.connect_signals_and_slots()
        self.updateReport()

    def connect_signals_and_slots(self):
        self.ui.ReportDate.dateChanged.connect(self.updateReport)
        self.ui.ReportCurrencyCombo.changed.connect(self.updateReport)
        self.ui.MatchButton.pressed.connect(self.matchLegs)
        self.ui.ReportTreeView.doubleClicked.connect(self.matchLegAt)
        self.ui.SaveButton.pressed.connect(partial(self._parent.save_report, self.name, self.ui.ReportTreeView.model()))

    @Slot()
    def updateReport(self):
        self.ui.ReportTreeView.model().updateView(currency_id=self.ui.ReportCurrencyCombo.selected_id,
                                                  date=self.ui.ReportDate.date())

    # Opens the two-panel matcher. This report is the worklist the matcher works through, which is why it is opened
    # from here - settling is a batch job rather than something done to one operation at a time.
    @Slot()
    def matchLegs(self):
        self._match(0)

    # ... and a double-click opens it with the leg that was clicked already chosen in its panel
    @Slot(QModelIndex)
    def matchLegAt(self, index):
        self._match(self.ui.ReportTreeView.model().transfer_oid(index))

    def _match(self, oid: int):
        dialog = TransferMatchDialog(oid, parent=self)
        dialog.exec()
        if dialog.changed:
            # Settling writes real operations, so the ledger has to catch up before the figures shown are true again.
            # Reports is constructed by the main window, which owns the Ledger - the same one every editor uses.
            self._parent.parent.ledger.rebuild()
            self.updateReport()
