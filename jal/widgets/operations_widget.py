from functools import partial

from PySide6.QtCore import Qt, Slot, Signal, QDateTime, QSortFilterProxyModel
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QMessageBox, QDialog
from jal.ui.ui_operations_widget import Ui_OperationsWidget
from jal.widgets.mdi import MdiWidget
from jal.widgets.selection_dialog import SelectTagDialog
from jal.widgets.helpers import ManipulateDate
from jal.widgets.icons import JalIcon
from jal.db.settings import JalSettings
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.balances_model import BalancesModel
from jal.db.operations_model import OperationsModel
from jal.db.operations import LedgerTransaction


# ----------------------------------------------------------------------------------------------------------------------
class OperationsWidget(MdiWidget):
    dbUpdated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_OperationsWidget()
        self.ui.setupUi(self)
        self._parent = parent  # Main window

        self.current_index = None  # this is used in onOperationContextMenu() to track item for menu

        # Set icons
        self.ui.NewOperationBtn.setIcon(JalIcon[JalIcon.ADD])
        self.ui.CopyOperationBtn.setIcon(JalIcon[JalIcon.COPY])
        self.ui.DeleteOperationBtn.setIcon(JalIcon[JalIcon.REMOVE])

        # Customize UI configuration
        self.balances_model = BalancesModel(self.ui.BalancesTreeView)
        self.ui.BalancesTreeView.setModel(self.balances_model)
        self.ui.BalancesTreeView.setContextMenuPolicy(Qt.CustomContextMenu)

        self.operations_model = OperationsModel(self.ui.OperationsTableView)
        self.operations_filtered_model = QSortFilterProxyModel(self.ui.OperationsTableView)
        self.operations_filtered_model.setSourceModel(self.operations_model)
        self.operations_filtered_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.ui.OperationsTableView.setModel(self.operations_filtered_model)
        self.operations_model.configureView()
        self.ui.OperationsTableView.setContextMenuPolicy(Qt.CustomContextMenu)

        self.connect_signals_and_slots()

        self.NewOperationMenu = QMenu()
        self.ui.OperationsTabs.dbUpdated.connect(self.dbUpdated)
        self.ui.OperationsTabs.dbUpdated.connect(self.operations_model.refresh)
        for key, name in self.ui.OperationsTabs.get_operations_list().items():
            self.NewOperationMenu.addAction(name, partial(self.create_operation, key))
        self.ui.NewOperationBtn.setMenu(self.NewOperationMenu)

        # Setup balance and holdings parameters
        current_time = QDateTime.currentDateTime()
        current_time.setTimeSpec(Qt.UTC)  # We use UTC everywhere so need to force TZ info
        self.ui.BalanceDate.setDateTime(current_time)
        self.ui.BalancesCurrencyCombo.setIndex(JalAsset.get_base_currency())

        self.ui.OperationsTableView.selectRow(0)
        self.ui.DateRange.setCurrentIndex(0)

    def connect_signals_and_slots(self):
        self.ui.BalanceDate.dateChanged.connect(self.ui.BalancesTreeView.model().setDate)
        self.ui.BalancesCurrencyCombo.changed.connect(self.ui.BalancesTreeView.model().setCurrency)
        self.ui.BalancesTreeView.doubleClicked.connect(self.balance_double_click)
        self.ui.BalancesTreeView.customContextMenuRequested.connect(self.balances_context_menu)
        self.ui.DateRange.changed.connect(self.operations_model.setDateRange)
        self.ui.ChooseAccountBtn.changed.connect(self.operations_model.setAccount)
        self.ui.SearchString.editingFinished.connect(self.update_operations_filter)
        self.ui.OperationsTableView.selectionModel().selectionChanged.connect(self.operation_selection_change)
        self.operations_model.modelReset.connect(partial(self.operation_selection_change, None, None))  # Use the same slot with NULL-parameters to clean operation view
        self.ui.OperationsTableView.customContextMenuRequested.connect(self.operation_context_menu)
        self.ui.DeleteOperationBtn.clicked.connect(self.delete_operation)
        self.ui.CopyOperationBtn.clicked.connect(self.ui.OperationsTabs.copy_operation)

    @Slot()
    def delete_operation(self):
        if QMessageBox().warning(None, self.tr("Confirmation"),
                                 self.tr("Are you sure to delete selected transaction(s)?"),
                                 QMessageBox.Yes, QMessageBox.No) == QMessageBox.No:
            return
        rows = []
        for index in self.ui.OperationsTableView.selectionModel().selectedRows():
            rows.append(index.row())
        self.operations_model.delete_rows(rows)
        self.dbUpdated.emit()

    @Slot()
    def create_operation(self, operation_type):
        self.ui.OperationsTabs.new_operation(operation_type, self.operations_model.getAccount())

    @Slot()
    def update_operations_filter(self):
        self.ui.OperationsTableView.model().setFilterFixedString(self.ui.SearchString.text())
        self.ui.OperationsTableView.model().setFilterKeyColumn(-1)

    @Slot()
    def balance_double_click(self, index):
        self.ui.ChooseAccountBtn.account_id = index.model().getAccountId(index)

    @Slot()
    def operation_selection_change(self, selected, _deselected):
        otype = LedgerTransaction.NA
        oid = 0
        if len(self.ui.OperationsTableView.selectionModel().selectedRows()) == 1:
            idx = selected.indexes()
            if idx:
                selected_row = self.operations_filtered_model.mapToSource(idx[0]).row()
                otype, oid = self.operations_model.get_operation(selected_row)
        self.ui.OperationsTabs.show_operation(otype, oid)

    @Slot()
    def operation_context_menu(self, pos):
        contextMenu = QMenu(self.ui.OperationsTableView)
        actionReconcile = QAction(JalIcon[JalIcon.OK], self.tr("Reconcile"), self)
        actionReconcile.triggered.connect(self.reconcile_at_current_operation)
        actionTag = QAction(JalIcon[JalIcon.TAG], self.tr("Assign tag"), self)
        actionTag.triggered.connect(self.assign_tag)
        actionCopy = QAction(JalIcon[JalIcon.COPY], self.tr("Copy"), self)
        actionCopy.triggered.connect(self.ui.OperationsTabs.copy_operation)
        actionDelete = QAction(JalIcon[JalIcon.REMOVE], self.tr("Delete"), self)
        actionDelete.triggered.connect(self.delete_operation)
        contextMenu.addAction(actionReconcile)
        contextMenu.addSeparator()
        contextMenu.addAction(actionTag)
        contextMenu.addSeparator()
        contextMenu.addAction(actionCopy)
        contextMenu.addAction(actionDelete)
        self.current_index = self.ui.OperationsTableView.indexAt(pos)
        if len(self.ui.OperationsTableView.selectionModel().selectedRows()) != 1:
            actionReconcile.setEnabled(False)
            actionCopy.setEnabled(False)
        else:
            actionReconcile.setEnabled(True)
            actionCopy.setEnabled(True)
        contextMenu.popup(self.ui.OperationsTableView.viewport().mapToGlobal(pos))

    @Slot()
    def balances_context_menu(self, pos):
        index = self.ui.BalancesTreeView.indexAt(pos)
        account_id = self.balances_model.data(index, BalancesModel.ACCOUNT_ROLE) if index.isValid() else 0
        contextMenu = QMenu(self.ui.BalancesTreeView)
        # Create a menu item to toggle active/inactive accounts
        actionToggleInactive = QAction(self.tr("Show inactive"), self)
        actionToggleInactive.setCheckable(True)
        actionToggleInactive.setChecked(JalSettings().getValue("ShowInactiveAccountBalances", False))
        actionToggleInactive.toggled.connect(self.ui.BalancesTreeView.model().showInactiveAccounts)
        contextMenu.addAction(actionToggleInactive)
        # Create a menu item to show account balance with/without credit limit
        actionUseCreditLimit = QAction(self.tr("Use credit limits"), self)
        actionUseCreditLimit.setCheckable(True)
        actionUseCreditLimit.setChecked(JalSettings().getValue("UseAccountCreditLimit", True))
        actionUseCreditLimit.toggled.connect(self.ui.BalancesTreeView.model().useCreditLimits)
        contextMenu.addAction(actionUseCreditLimit)
        contextMenu.addSeparator()
        actionBalanceHistory = QAction(JalIcon[JalIcon.CHART], self.tr("Balance history chart"), self)
        actionBalanceHistory.triggered.connect(partial(self.show_balance_history_chart, account_id))
        if account_id:
            actionBalanceHistory.setEnabled(True)
        else:
            actionBalanceHistory.setEnabled(False)
        contextMenu.addAction(actionBalanceHistory)
        contextMenu.addSeparator()
        actionExpandAll = QAction(text=self.tr("Expand all"), parent=self)
        actionExpandAll.triggered.connect(self.ui.BalancesTreeView.expandAll)
        contextMenu.addAction(actionExpandAll)
        actionCollapseAll = QAction(text=self.tr("Collapse all"), parent=self)
        actionCollapseAll.triggered.connect(self.ui.BalancesTreeView.collapseAll)
        contextMenu.addAction(actionCollapseAll)
        contextMenu.popup(self.ui.BalancesTreeView.viewport().mapToGlobal(pos))

    @Slot()
    def reconcile_at_current_operation(self):
        idx = self.operations_model.index(self.current_index.row(), 0)  # we need only row to address fields by name
        timestamp = self.operations_model.data(idx, Qt.UserRole, field="timestamp")
        account_id = self.operations_model.data(idx, Qt.UserRole, field="account_id")
        JalAccount(account_id).reconcile(timestamp)
        self.operations_model.refresh()

    def refresh(self):
        self.balances_model.update()

    @Slot()
    def assign_tag(self):
        rows = []
        for index in self.ui.OperationsTableView.selectionModel().selectedRows():
            rows.append(index.row())
        dialog = SelectTagDialog(parent=self, description=self.tr("Choose tag to be assigned to selected operations:"))
        if dialog.exec() != QDialog.Accepted:
            return
        self.operations_model.assign_tag_to_rows(rows, dialog.selected_id)
        self.dbUpdated.emit()

    @Slot()
    def show_balance_history_chart(self, account_id):
        begin, end = ManipulateDate.PreviousQuarter()
        details = {'begin_ts': begin, 'end_ts': end, 'account_id': account_id}
        self._parent.reports.show_report("AccountBalanceHistoryReportWindow", details)
