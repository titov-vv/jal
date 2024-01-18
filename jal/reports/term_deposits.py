from PySide6.QtCore import Qt, Slot, QObject
from jal.reports.reports import Reports
from jal.ui.reports.ui_term_deposits_report import Ui_TermDepositsReportWidget
from jal.widgets.mdi import MdiWidget

JAL_REPORT_CLASS = "TermDepositsReport"


# ----------------------------------------------------------------------------------------------------------------------
class TermDepositsReport(QObject):
    def __init__(self):
        super().__init__()
        self.name = self.tr("Term deposits")
        self.window_class = "TermDepositsReportWindow"

# ----------------------------------------------------------------------------------------------------------------------
class TermDepositsReportWindow(MdiWidget):
    def __init__(self, parent: Reports, settings: dict = None):
        super().__init__(parent.mdi_area())
        self.ui = Ui_TermDepositsReportWidget()
        self.ui.setupUi(self)
        self._parent = parent
        self.name = self.tr("Term deposits")
