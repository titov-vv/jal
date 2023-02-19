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
class PeerReportWindow(MdiWidget, Ui_PeerReportWidget):
    def __init__(self, parent: Reports, settings: dict = None):
        MdiWidget.__init__(self, parent.mdi_area())
        self.setupUi(self)
        self._parent = parent

        self.peer_model = PeerOperationsModel(self.ReportTableView)
        self.ReportTableView.setModel(self.peer_model)
        self.peer_model.configureView()

        self.connect_signals_and_slots()

        if settings is not None:
            self.ReportRange.setRange(settings['begin_ts'], settings['end_ts'])
            self.ReportPeerEdit.selected_id = settings['peer_id']
            self.onPeerChange()

    def connect_signals_and_slots(self):
        self.ReportRange.changed.connect(self.ReportTableView.model().setDateRange)
        self.ReportPeerEdit.changed.connect(self.onPeerChange)
        self.ReportTableView.selectionModel().selectionChanged.connect(self.onOperationSelect)

    @Slot()
    def onPeerChange(self):
        self.ReportTableView.model().setPeer(self.ReportPeerEdit.selected_id)

    @Slot()
    def onOperationSelect(self, selected, _deselected):
        idx = selected.indexes()
        if idx:
            selected_row = idx[0].row()
            operation_type, operation_id = self.ReportTableView.model().get_operation(selected_row)
            self.OperationDetails.show_operation(operation_type, operation_id)
        else:
            self.OperationDetails.show_operation(LedgerTransaction.NA, 0)
