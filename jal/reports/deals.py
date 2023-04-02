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
class DealsReportWindow(MdiWidget, Ui_DealsReportWidget):
    def __init__(self, parent: Reports, settings: dict = None):
        MdiWidget.__init__(self, parent.mdi_area())
        self.setupUi(self)
        self._parent = parent

        # Add available groupings
        self.GroupCombo.addItem(self.tr("<None>"), "")
        self.GroupCombo.addItem(self.tr("Asset"), "symbol")
        self.GroupCombo.addItem(self.tr("Close"), "close_date")
        self.GroupCombo.addItem(self.tr("Asset - Open - Close"), "symbol;open_date;close_date")
        self.GroupCombo.addItem(self.tr("Open - Close"), "open_date;close_date")
        self.GroupCombo.addItem(self.tr("Close - Open"), "close_date;open_date")

        self.trades_model = ClosedTradesModel(self.ReportTreeView)
        self.ReportTreeView.setModel(self.trades_model)

        self.connect_signals_and_slots()

    def connect_signals_and_slots(self):
        self.ReportAccountBtn.changed.connect(self.onAccountChange)
        self.ReportRange.changed.connect(self.ReportTreeView.model().setDatesRange)
        self.GroupCombo.currentIndexChanged.connect(self.onGroupingChange)

    @Slot()
    def onAccountChange(self):
        self.ReportTreeView.model().setAccount(self.ReportAccountBtn.account_id)

    @Slot()
    def onGroupingChange(self, idx):
        self.ReportTreeView.model().setGrouping(self.GroupCombo.itemData(idx))
