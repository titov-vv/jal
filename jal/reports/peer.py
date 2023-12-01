from decimal import Decimal
from PySide6.QtCore import Qt, Slot, QObject
from jal.db.ledger import Ledger
from jal.db.asset import JalAsset
from jal.db.peer import JalPeer
from jal.reports.reports import Reports
from jal.reports.operations_base import ReportOperationsModel
from jal.db.operations import LedgerTransaction
from jal.ui.reports.ui_peer_report import Ui_PeerReportWidget
from jal.widgets.mdi import MdiWidget

JAL_REPORT_CLASS = "PeerReport"


# ----------------------------------------------------------------------------------------------------------------------
class PeerOperationsModel(ReportOperationsModel):
    def __init__(self, parent_view):
        self._peer_id = 0
        super().__init__(parent_view)

    def footerData(self, section: int, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and section == 3:
            return self.tr("Total with peer ") + f"'{JalPeer(self._peer_id).name()}':"
        return super().footerData(section, role)

    def updateView(self, peer_id: int, dates_range: tuple, total_currency_id: int):
        update = False
        if self._peer_id != peer_id:
            self._peer_id = peer_id
            update = True
        super().updateView(update, dates_range, total_currency_id)

    def prepareData(self):
        self._data = []
        self._total = Decimal('0')
        self._data = Ledger.get_operations_by_peer(self._begin, self._end, self._peer_id)
        operations = [LedgerTransaction().get_operation(x['op_type'], x['id'], x['subtype']) for x in self._data]
        # Take only Income/Spending data as we expect Asset operations to be not relevant for this kind of report
        operations = [x for x in operations if x.type() == LedgerTransaction.IncomeSpending]
        for op in operations:
            op_amount = Decimal('0')
            if op.peer() == self._peer_id:
                try:
                    op_amount += Decimal(op.amount())
                except:
                    pass
            account_currency = op.account().currency()
            if account_currency == self._total_currency:
                self._total += op_amount
            else:
                rate = JalAsset(account_currency).quote(op.timestamp(), self._total_currency)[1]
                self._total += op_amount * rate
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
        self.ui.TotalCurrencyCombo.setIndex(JalAsset.get_base_currency())
        self.peer_model.configureView()

        if settings is not None:
            self.ui.ReportRange.setRange(settings['begin_ts'], settings['end_ts'])
            self.ui.ReportPeerEdit.selected_id = settings['peer_id']
        self.connect_signals_and_slots()
        self.updateReport()

    def connect_signals_and_slots(self):
        self.ui.ReportRange.changed.connect(self.updateReport)
        self.ui.ReportPeerEdit.changed.connect(self.updateReport)
        self.ui.TotalCurrencyCombo.changed.connect(self.updateReport)
        self.ui.ReportTableView.selectionModel().selectionChanged.connect(self.onOperationSelect)

    @Slot()
    def updateReport(self):
        self.ui.ReportTableView.model().updateView(
            peer_id=self.ui.ReportPeerEdit.selected_id, dates_range=self.ui.ReportRange.getRange(),
            total_currency_id=self.ui.TotalCurrencyCombo.selected_id)

    @Slot()
    def onOperationSelect(self, selected, _deselected):
        idx = selected.indexes()
        if idx:
            selected_row = idx[0].row()
            operation_type, operation_id = self.ui.ReportTableView.model().get_operation(selected_row)
            self.ui.OperationDetails.show_operation(operation_type, operation_id)
        else:
            self.ui.OperationDetails.show_operation(LedgerTransaction.NA, 0)
