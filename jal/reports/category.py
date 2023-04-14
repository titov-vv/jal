from PySide6.QtCore import Slot, QObject
from jal.db.ledger import Ledger
from jal.reports.reports import Reports
from jal.db.operations import LedgerTransaction
from jal.db.operations_model import OperationsModel
from jal.ui.reports.ui_category_report import Ui_CategoryReportWidget
from jal.widgets.mdi import MdiWidget

JAL_REPORT_CLASS = "CategoryReport"


# ----------------------------------------------------------------------------------------------------------------------
class CategoryOperationsModel(OperationsModel):
    def __init__(self, parent_view):
        self._category_id = 0
        super().__init__(parent_view)

    def setCategory(self, category):
        self._category_id = category
        self.prepareData()

    def prepareData(self):
        self._data = []
        self._data = Ledger.get_operations_by_category(self._begin, self._end, self._category_id)
        self.modelReset.emit()


# ----------------------------------------------------------------------------------------------------------------------
class CategoryReport(QObject):
    def __init__(self):
        super().__init__()
        self.group = self.tr("Operations")
        self.name = self.tr("by Category")
        self.window_class = "CategoryReportWindow"


# ----------------------------------------------------------------------------------------------------------------------
class CategoryReportWindow(MdiWidget):
    def __init__(self, parent: Reports, settings: dict = None):
        super().__init__(parent.mdi_area())
        self.ui = Ui_CategoryReportWidget()
        self.ui.setupUi(self)
        self._parent = parent

        self.category_model = CategoryOperationsModel(self.ui.ReportTableView)
        self.ui.ReportTableView.setModel(self.category_model)
        self.category_model.configureView()

        self.connect_signals_and_slots()

        if settings is not None:
            self.ui.ReportRange.setRange(settings['begin_ts'], settings['end_ts'])
            self.ui.ReportCategoryEdit.selected_id = settings['category_id']
            self.onCategoryChange()

    def connect_signals_and_slots(self):
        self.ui.ReportRange.changed.connect(self.ui.ReportTableView.model().setDateRange)
        self.ui.ReportCategoryEdit.changed.connect(self.onCategoryChange)
        self.ui.ReportTableView.selectionModel().selectionChanged.connect(self.onOperationSelect)

    @Slot()
    def onCategoryChange(self):
        self.ui.ReportTableView.model().setCategory(self.ui.ReportCategoryEdit.selected_id)

    @Slot()
    def onOperationSelect(self, selected, _deselected):
        idx = selected.indexes()
        if idx:
            selected_row = idx[0].row()
            operation_type, operation_id = self.ui.ReportTableView.model().get_operation(selected_row)
            self.ui.OperationDetails.show_operation(operation_type, operation_id)
        else:
            self.ui.OperationDetails.show_operation(LedgerTransaction.NA, 0)
