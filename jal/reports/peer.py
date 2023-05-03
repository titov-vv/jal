from PySide6.QtCore import Slot, QObject
from jal.db.ledger import Ledger
from jal.reports.reports import Reports
from jal.db.operations import LedgerTransaction
from jal.db.operations_model import OperationsModel
from jal.ui.reports.ui_peer_report import Ui_PeerReportWidget
from jal.widgets.mdi import MdiWidget

JAL_REPORT_CLASS = "PeerReport"


# ----------------------------------------------------------------------------------------------------------------------
class PeerOperationsModel(OperationsModel):
    def __init__(self, parent_view):
        self._peer_id = 0
        super().__init__(parent_view)

    def setPeer(self, peer):
        self._peer_id = peer
        self.prepareData()

    def prepareData(self):
        self._data = []
        self._data = Ledger.get_operations_by_peer(self._begin, self._end, self._peer_id)
        self.modelReset.emit()


# ----------------------------------------------------------------------------------------------------------------------
class PeerReport(QObject):
    def __init__(self):
        super().__init__()
        self.group = self.tr("Operations")
        self.name = self.tr("by Peer")
        self.window_class = "PeerReportWindow"


# ----------------------------------------------------------------------------------------------------------------------
class PeerReportWindow(MdiWidget):
    def __init__(self, parent: Reports, settings: dict = None):
        super().__init__(parent.mdi_area())
        self.ui = Ui_PeerReportWidget()
        self.ui.setupUi(self)
        self._parent = parent

        self.peer_model = PeerOperationsModel(self.ui.ReportTableView)
        self.ui.ReportTableView.setModel(self.peer_model)
        self.peer_model.configureView()

        self.connect_signals_and_slots()

        if settings is not None:
            self.ui.ReportRange.setRange(settings['begin_ts'], settings['end_ts'])
            self.ui.ReportPeerEdit.selected_id = settings['peer_id']
            self.onPeerChange()

    def connect_signals_and_slots(self):
        self.ui.ReportRange.changed.connect(self.ui.ReportTableView.model().setDateRange)
        self.ui.ReportPeerEdit.changed.connect(self.onPeerChange)
        self.ui.ReportTableView.selectionModel().selectionChanged.connect(self.onOperationSelect)

    @Slot()
    def onPeerChange(self):
        self.ui.ReportTableView.model().setPeer(self.ui.ReportPeerEdit.selected_id)

    @Slot()
    def onOperationSelect(self, selected, _deselected):
        idx = selected.indexes()
        if idx:
            selected_row = idx[0].row()
            operation_type, operation_id = self.ui.ReportTableView.model().get_operation(selected_row)
            self.ui.OperationDetails.show_operation(operation_type, operation_id)
        else:
            self.ui.OperationDetails.show_operation(LedgerTransaction.NA, 0)
