from functools import partial

from PySide6.QtCore import Slot, QObject
from jal.ui.reports.ui_deals_report import Ui_DealsReportWidget
from jal.reports.reports import Reports
from jal.widgets.mdi import MdiWidget
from jal.db.trades_model import ClosedTradesModel

JAL_REPORT_CLASS = "DealsReport"


# ----------------------------------------------------------------------------------------------------------------------
class DealsReport(QObject):
    def __init__(self):
        super().__init__()
        self.name = self.name = self.tr("Deals by Account")
        self.window_class = "DealsReportWindow"


# ----------------------------------------------------------------------------------------------------------------------
class DealsReportWindow(MdiWidget):
    def __init__(self, parent: Reports, settings: dict = None):
        super().__init__(parent.mdi_area())
        self.ui = Ui_DealsReportWidget()
        self.ui.setupUi(self)
        self._parent = parent
        self.name = self.tr("Deals")

        # Add available groupings
        self.ui.GroupCombo.addItem(self.tr("<None>"), "")
        self.ui.GroupCombo.addItem(self.tr("Asset"), "symbol")
        self.ui.GroupCombo.addItem(self.tr("Close"), "close_date")
        self.ui.GroupCombo.addItem(self.tr("Asset - Open - Close"), "symbol;open_date;close_date")
        self.ui.GroupCombo.addItem(self.tr("Open - Close"), "open_date;close_date")
        self.ui.GroupCombo.addItem(self.tr("Close - Open"), "close_date;open_date")

        self.trades_model = ClosedTradesModel(self.ui.ReportTreeView)
        self.ui.ReportTreeView.setModel(self.trades_model)

        self.connect_signals_and_slots()

    def connect_signals_and_slots(self):
        self.ui.ReportAccountButton.changed.connect(self.updateReport)
        self.ui.ReportRange.changed.connect(self.updateReport)
        self.ui.GroupCombo.currentIndexChanged.connect(self.updateReport)
        self.ui.SaveButton.pressed.connect(partial(self._parent.save_report, self.name, self.ui.ReportTreeView.model()))

    @Slot()
    def updateReport(self):
        self.ui.ReportTreeView.model().updateView(account_id=self.ui.ReportAccountButton.account_id,
                                                  dates=self.ui.ReportRange.getRange(),
                                                  grouping=self.ui.GroupCombo.currentData())
