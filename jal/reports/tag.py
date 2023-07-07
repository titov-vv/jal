from decimal import Decimal
from PySide6.QtCore import Qt, Slot, QObject
from PySide6.QtGui import QFont
from jal.db.ledger import Ledger
from jal.db.asset import JalAsset
from jal.db.tag import JalTag
from jal.db.helpers import localize_decimal
from jal.reports.reports import Reports
from jal.db.operations import LedgerTransaction
from jal.db.operations_model import OperationsModel
from jal.ui.reports.ui_tag_report import Ui_TagReportWidget
from jal.widgets.mdi import MdiWidget

JAL_REPORT_CLASS = "TagReport"


# ----------------------------------------------------------------------------------------------------------------------
class TagOperationsModel(OperationsModel):
    def __init__(self, parent_view):
        self._tag_id = 0
        self._total = Decimal('0')
        self._total_currency = 0
        self._total_currency_name = ''
        super().__init__(parent_view)

    def footerData(self, section: int, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if section == 3:
                return self.tr("Total with tag ") + f"'{JalTag(self._tag_id).name()}':"
            elif section == 4:
                return localize_decimal(self._total, precision=2)
            elif section == 5:
                return self._total_currency_name
        elif role == Qt.FontRole:
            font = QFont()
            font.setBold(True)
            return font
        elif role == Qt.TextAlignmentRole:
            if section ==3 or section == 4:
                return Qt.AlignRight | Qt.AlignVCenter
            else:
                return Qt.AlignLeft | Qt.AlignVCenter
        return None

    def updateView(self, tag_id: int, dates_range: tuple, total_currency_id: int):
        update = False
        if self._tag_id != tag_id:
            self._tag_id = tag_id
            update = True
        if self._begin != dates_range[0]:
            self._begin = dates_range[0]
            update = True
        if self._end != dates_range[1]:
            self._end = dates_range[1]
            update = True
        if self._total_currency != total_currency_id:
            self._total_currency = total_currency_id
            self._total_currency_name = JalAsset(total_currency_id).symbol()
            update = True
        if update:
            self.prepareData()
            self.configureView()

    def prepareData(self):
        self._data = []
        self._total = Decimal('0')
        self._data = Ledger.get_operations_by_tag(self._begin, self._end, self._tag_id)
        operations = [LedgerTransaction().get_operation(x['op_type'], x['id'], x['subtype']) for x in self._data]
        # Take only Income/Spending data as we expect Asset operations to be not relevant for this kind of report
        operations = [x for x in operations if x.type() == LedgerTransaction.IncomeSpending]
        for op in operations:
            op_amount = Decimal('0')
            for line in op.lines():
                if line['tag_id']== self._tag_id:
                    try:
                        op_amount += Decimal(line['amount'])
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
class TagReport(QObject):
    def __init__(self):
        super().__init__()
        self.group = self.tr("Operations")
        self.name = self.tr("by Tag")
        self.window_class = "TagReportWindow"


# ----------------------------------------------------------------------------------------------------------------------
class TagReportWindow(MdiWidget):
    def __init__(self, parent: Reports, settings: dict = None):
        super().__init__(parent.mdi_area())
        self.ui = Ui_TagReportWidget()
        self.ui.setupUi(self)
        self._parent = parent

        self.tag_model = TagOperationsModel(self.ui.ReportTableView)
        self.ui.ReportTableView.setModel(self.tag_model)
        self.ui.TotalCurrencyCombo.setIndex(JalAsset.get_base_currency())
        self.tag_model.configureView()

        if settings is not None:
            self.ui.ReportRange.setRange(settings['begin_ts'], settings['end_ts'])
            self.ui.ReportTagEdit.selected_id = settings['tag_id']
        self.connect_signals_and_slots()
        self.updateReport()

    def connect_signals_and_slots(self):
        self.ui.ReportRange.changed.connect(self.updateReport)
        self.ui.ReportTagEdit.changed.connect(self.updateReport)
        self.ui.TotalCurrencyCombo.changed.connect(self.updateReport)
        self.ui.ReportTableView.selectionModel().selectionChanged.connect(self.onOperationSelect)

    @Slot()
    def updateReport(self):
        self.ui.ReportTableView.model().updateView(
            tag_id=self.ui.ReportTagEdit.selected_id, dates_range=self.ui.ReportRange.getRange(),
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
