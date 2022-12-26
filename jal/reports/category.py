from PySide6.QtCore import Slot, QObject
from jal.db.ledger import Ledger
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
        self.name = self.tr("Operations by Category")
        self.window_class = "CategoryReportWindow"


# ----------------------------------------------------------------------------------------------------------------------
class CategoryReportWindow(MdiWidget, Ui_CategoryReportWidget):
    def __init__(self, parent=None):
        MdiWidget.__init__(self, parent)
        self.setupUi(self)
        self.parent_mdi = parent

        self.category_model = CategoryOperationsModel(self.ReportTableView)
        self.ReportTableView.setModel(self.category_model)
        self.category_model.configureView()

        self.connect_signals_and_slots()

    def connect_signals_and_slots(self):
        self.ReportRange.changed.connect(self.ReportTableView.model().setDateRange)
        self.ReportCategoryEdit.changed.connect(self.onCategoryChange)
        self.ReportTableView.selectionModel().selectionChanged.connect(self.onOperationSelect)

    @Slot()
    def onCategoryChange(self):
        self.ReportTableView.model().setCategory(self.ReportCategoryEdit.selected_id)

    @Slot()
    def onOperationSelect(self, selected, _deselected):
        idx = selected.indexes()
        if idx:
            selected_row = idx[0].row()
            operation_type, operation_id = self.ReportTableView.model().get_operation(selected_row)
            self.OperationDetails.show_operation(operation_type, operation_id)
        else:
            self.OperationDetails.show_operation(LedgerTransaction.NA, 0)
