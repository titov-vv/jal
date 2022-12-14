from PySide6.QtCore import Qt, Slot, QObject, QAbstractTableModel
from jal.db.ledger import Ledger
from jal.db.operations import LedgerTransaction
from jal.ui.reports.ui_tag_report import Ui_TagReportWidget
from jal.widgets.delegates import FloatDelegate, TimestampDelegate
from jal.widgets.mdi import MdiWidget

JAL_REPORT_CLASS = "TagReport"


# ----------------------------------------------------------------------------------------------------------------------
class TagReportModel(QAbstractTableModel):
    def __init__(self, parent_view):
        super().__init__(parent_view)
        self._columns = [self.tr("Timestamp"), self.tr("Account"), self.tr("Peer Name"), self.tr("Amount"),
                         self.tr("Currency")]
        self._view = parent_view
        self._data = []
        self._timestamp_delegate = None
        self._float_delegate = None
        self._begin = 0
        self._end = 0
        self._tag_id = 0

    def rowCount(self, parent=None):
        return len(self._data)

    def columnCount(self, parent=None):
        return len(self._columns)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._columns[section]

    def resetDelegates(self):
        for i, column in enumerate(self._columns):
            self._view.setItemDelegateForColumn(i, None)

    def data(self, index, role=Qt.DisplayRole, field=''):
        row = index.row()
        if not index.isValid():
            return None
        operation = LedgerTransaction().get_operation(self._data[row]['op_type'], self._data[row]['id'])
        if role == Qt.DisplayRole:
            return self.data_text(operation, index.column())

    def data_text(self, operation, column):
        if column == 0:
            return operation.timestamp()
        elif column == 1:
            return operation.account_name()
        elif column == 2:
            return operation.description()
        elif column == 3:
            return operation.amount()
        elif column == 4:
            return operation.value_currency()
        else:
            assert False, "Unexpected column number"

    def get_operation(self, row):
        if (row >= 0) and (row < self.rowCount()):
            return self._data[row]['op_type'], self._data[row]['id']
        else:
            return [0, 0]

    def configureView(self):
        self.resetDelegates()
        font = self._view.horizontalHeader().font()
        font.setBold(True)
        self._view.horizontalHeader().setFont(font)
        self._view.setColumnWidth(0, self._view.fontMetrics().horizontalAdvance("00/00/0000 00:00:00") * 1.1)
        self._view.setColumnWidth(1, 200)
        self._view.setColumnWidth(2, 200)
        self._view.setColumnWidth(3, 200)
        self._view.setColumnWidth(4, 100)
        self._timestamp_delegate = TimestampDelegate()
        self._view.setItemDelegateForColumn(0, self._timestamp_delegate)
        self._float_delegate = FloatDelegate(2, allow_tail=False)
        self._view.setItemDelegateForColumn(3, self._float_delegate)

    def setDatesRange(self, begin, end):
        self._begin = begin
        self._end = end
        self.prepareData()

    def setTag(self, tag):
        self._tag_id = tag
        self.prepareData()

    def prepareData(self):
        self._data = Ledger.get_operations_by_tag(self._begin, self._end, self._tag_id)
        self.modelReset.emit()


# ----------------------------------------------------------------------------------------------------------------------
class TagReport(QObject):
    def __init__(self):
        super().__init__()
        self.name = self.tr("Operations by Tag")
        self.window_class = "TagReportWindow"


# ----------------------------------------------------------------------------------------------------------------------
class TagReportWindow(MdiWidget, Ui_TagReportWidget):
    def __init__(self, parent=None):
        MdiWidget.__init__(self, parent)
        self.setupUi(self)
        self.parent_mdi = parent

        self.tag_model = TagReportModel(self.ReportTableView)
        self.ReportTableView.setModel(self.tag_model)
        self.tag_model.configureView()
        self.IncomeSpendingDetails.setId(0)  # Reset details widget

        self.connect_signals_and_slots()

    def connect_signals_and_slots(self):
        self.ReportRange.changed.connect(self.ReportTableView.model().setDatesRange)
        self.ReportTagEdit.changed.connect(self.onTagChange)
        self.ReportTableView.selectionModel().selectionChanged.connect(self.onOperationSelect)

    @Slot()
    def onTagChange(self):
        self.ReportTableView.model().setTag(self.ReportTagEdit.selected_id)

    @Slot()
    def onOperationSelect(self, selected, _deselected):
        idx = selected.indexes()
        if idx:
            selected_row = idx[0].row()
            _operation_type, operation_id = self.ReportTableView.model().get_operation(selected_row)
            self.IncomeSpendingDetails.setId(operation_id)
        else:
            self.IncomeSpendingDetails.setId(0)
