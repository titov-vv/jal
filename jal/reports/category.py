from PySide6.QtCore import Qt, Slot, QObject
from jal.db.ledger import Ledger
from jal.db.asset import JalAsset
from jal.db.category import JalCategory
from jal.reports.reports import Reports
from jal.reports.operations_base import ReportOperationsModel
from jal.db.operations import LedgerTransaction
from jal.ui.reports.ui_category_report import Ui_CategoryReportWidget
from jal.widgets.mdi import MdiWidget

JAL_REPORT_CLASS = "CategoryReport"


# ----------------------------------------------------------------------------------------------------------------------
class CategoryOperationsModel(ReportOperationsModel):
    def __init__(self, parent_view):
        self._category_id = 0
        super().__init__(parent_view, hidden_column=3)

    def footerData(self, section: int, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and section == 5:
            return self.tr("Total with category ") + f"'{JalCategory(self._category_id).name()}':"
        return super().footerData(section, role)

    def updateView(self, category_id: int, dates_range: tuple, total_currency_id: int):
        update = False
        if self._category_id != category_id:
            self._category_id = category_id
            update = True
        super().updateView(update, dates_range, total_currency_id)

    def prepareData(self):
        self._data = []
        self._data = Ledger.get_operations_by_category(self._begin, self._end, self._category_id)
        super().prepareData()


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
        self.ui.TotalCurrencyCombo.setIndex(JalAsset.get_base_currency())
        self.category_model.configureView()

        if settings is not None:
            self.ui.ReportRange.setRange(settings['begin_ts'], settings['end_ts'])
            self.ui.ReportCategoryEdit.selected_id = settings['category_id']
        self.connect_signals_and_slots()
        self.updateReport()

    def connect_signals_and_slots(self):
        self.ui.ReportRange.changed.connect(self.updateReport)
        self.ui.ReportCategoryEdit.changed.connect(self.updateReport)
        self.ui.TotalCurrencyCombo.changed.connect(self.updateReport)
        self.ui.ReportTableView.selectionModel().selectionChanged.connect(self.onOperationSelect)

    @Slot()
    def updateReport(self):
        self.ui.ReportTableView.model().updateView(
            category_id=self.ui.ReportCategoryEdit.selected_id, dates_range=self.ui.ReportRange.getRange(),
            total_currency_id=self.ui.TotalCurrencyCombo.selected_id)

    @Slot()
    def onOperationSelect(self, selected, _deselected):
        idx = selected.indexes()
        if idx:
            selected_row = idx[0].row()
            operation_type, oid = self.ui.ReportTableView.model().get_operation(selected_row)
            self.ui.OperationDetails.show_operation(operation_type, oid)
        else:
            self.ui.OperationDetails.show_operation(LedgerTransaction.NA, 0)
