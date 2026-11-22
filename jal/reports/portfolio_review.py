from PySide6.QtCore import Qt, Slot, QObject, QAbstractTableModel
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QHeaderView, QMenu, QDialog
from jal.constants import Setup
from jal.reports.reports import Reports
from jal.db.common_models import TagTreeModel
from jal.db.operations import LedgerTransaction
from jal.db.portfolio import JalPortfolio, PortfolioReview
from jal.db.tag import JalTag
from jal.ui.reports.ui_portfolio_review_report import Ui_PortfolioReviewWidget
from jal.widgets.custom.portfolio_combo import PortfolioCombo
from jal.widgets.delegates import FloatDelegate
from jal.widgets.helpers import ts2dt, set_grids_metrics, restore_columns, TableSelectionRestorer
from jal.widgets.mdi import MdiWidget
from jal.widgets.reference_dialogs import TagsListDialog
from jal.widgets.selection_dialog import SelectReferenceDialog

JAL_REPORT_CLASS = "PortfolioReviewReport"


# ----------------------------------------------------------------------------------------------------------------------
class PortfolioReviewModel(QAbstractTableModel):
    def __init__(self, parent_view):
        super().__init__(parent_view)
        self._columns = [self.tr("Date"), self.tr("Issue"), self.tr("Account"), self.tr("Asset"), self.tr("Qty"),
                         self.tr("Portfolio"), self.tr("Other portfolios")]
        self._view = parent_view
        self._data = []
        self._qty_delegate = None

    def rowCount(self, parent=None):
        return len(self._data)

    def columnCount(self, parent=None):
        return len(self._columns)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._columns[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        item = self._data[index.row()]
        if role == Qt.DisplayRole:
            return self.data_text(item, index.column())
        if role == Qt.DecorationRole and index.column() == 0:
            return item['operation'].icon()
        if role == Qt.ToolTipRole and index.column() == 1:
            return self._issue_hint(item['issue'])
        return None

    def data_text(self, item: dict, column: int):
        operation = item['operation']
        if column == 0:
            return ts2dt(operation.timestamp(), operation.timestamp_is_day())
        if column == 1:
            return self._issue_name(item['issue'])
        if column == 2:
            return item['account'].name()
        if column == 3:
            return item['asset'].symbol(item['account'].currency())
        if column == 4:
            return item['qty']
        if column == 5:
            return self._portfolio_name(item['portfolio'])
        if column == 6:
            return ", ".join(sorted(self._portfolio_name(x) for x in item['others']))
        return ''

    def _issue_name(self, issue: int) -> str:
        if issue == PortfolioReview.Spill:
            return self.tr("Spill")
        return self.tr("Unassigned")

    def _issue_hint(self, issue: int) -> str:
        if issue == PortfolioReview.Spill:
            return self.tr("The operation took lots of other portfolios: its own portfolio had too few")
        return self.tr("Unassigned lots in a position that holds assigned lots too")

    def _portfolio_name(self, tag_id: int) -> str:
        return JalTag(tag_id).name() if tag_id else self.tr("Unassigned")

    def item(self, row: int) -> dict:
        return self._data[row]

    def refresh(self):
        self.beginResetModel()
        self._data = PortfolioReview.items()
        self.endResetModel()

    def configureView(self):
        self._view.setColumnWidth(0, self._view.fontMetrics().horizontalAdvance("00/00/0000 00:00:00") * 1.2)
        self._view.horizontalHeader().setSectionResizeMode(6, QHeaderView.Stretch)
        self._qty_delegate = FloatDelegate(0, allow_tail=True, parent=self._view)
        self._view.setItemDelegateForColumn(4, self._qty_delegate)
        restore_columns(self._view, Setup.COLUMNS_STATE_PREFIX)


# ----------------------------------------------------------------------------------------------------------------------
class PortfolioReviewReport(QObject):
    def __init__(self):
        super().__init__()
        self.name = self.tr("Portfolio re&view")
        self.window_class = "PortfolioReviewReportWindow"


# ----------------------------------------------------------------------------------------------------------------------
class PortfolioReviewReportWindow(MdiWidget):
    def __init__(self, parent: Reports, settings: dict = None):
        super().__init__(parent.mdi_area())
        self.ui = Ui_PortfolioReviewWidget()
        self.ui.setupUi(self)
        set_grids_metrics(self)
        self._parent = parent
        self.name = self.tr("Portfolio assignments to review")

        self.model = PortfolioReviewModel(self.ui.ReportTableView)
        self.ui.ReportTableView.setModel(self.model)
        self.model.configureView()
        self.ui.ReportTableView.setContextMenuPolicy(Qt.CustomContextMenu)

        self._selection_restorer = TableSelectionRestorer(self.ui.ReportTableView)
        self.ui.RefreshButton.clicked.connect(self.refresh)
        self.ui.ReportTableView.customContextMenuRequested.connect(self.onContextMenu)
        self.ui.ReportTableView.selectionModel().selectionChanged.connect(self.onItemSelect)
        self.refresh()

    @Slot()
    def refresh(self):
        PortfolioCombo.prepare_lots(self)
        self.model.refresh()
        self.ui.SummaryLbl.setText(self.tr("{count} to review").format(count=self.model.rowCount()))

    def selected_items(self) -> list:
        return [self.model.item(x.row()) for x in self.ui.ReportTableView.selectionModel().selectedRows()]

    @Slot()
    def onContextMenu(self, pos):
        items = self.selected_items()
        if not items:
            return
        menu = QMenu(self.ui.ReportTableView)
        action = QAction(self.tr("Set portfolio…"), self)
        action.triggered.connect(lambda: self.assign_portfolio(items))
        menu.addAction(action)
        action = QAction(self.tr("Remove from portfolio"), self)
        action.triggered.connect(lambda: self.set_portfolio(items, JalPortfolio.Unassigned))
        menu.addAction(action)
        menu.popup(self.ui.ReportTableView.viewport().mapToGlobal(pos))

    def assign_portfolio(self, items):
        dialog = SelectReferenceDialog(self, self.tr("Please select portfolio"),
                                       self.tr("Portfolio for {count} operation(s):").format(count=len(items)),
                                       TagTreeModel, TagsListDialog)
        if dialog.exec() == QDialog.Accepted:
            self.set_portfolio(items, dialog.selected_id)

    # The assignment goes to the operation of each row: the lots' opener, or the disposal that spilled
    def set_portfolio(self, items, tag_id: int):
        for item in items:
            JalPortfolio.assign(item['operation'].id(), tag_id)
        self.refresh()

    @Slot()
    def onItemSelect(self, selected, deselected):
        if self._selection_restorer.busy():
            return
        rows = self.ui.ReportTableView.selectionModel().selectedRows()
        if rows:
            operation = self.model.item(rows[0].row())['operation']
            shown = self.ui.OperationDetails.show_operation(operation.type(), operation.id())
        else:
            shown = self.ui.OperationDetails.show_operation(LedgerTransaction.NA, 0)
        if not shown:
            self._selection_restorer.restore(deselected)
