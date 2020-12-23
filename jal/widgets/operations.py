import logging

from jal.constants import Setup, TransactionType
from PySide2.QtCore import Qt, QObject, Signal, Slot, QDateTime
from PySide2.QtWidgets import QMessageBox, QMenu, QAction, QHeaderView
from jal.db.helpers import executeSQL
from jal.ui_custom.helpers import g_tr

INIT_NULL = 0
INIT_VALUE = 1
INIT_TIMESTAMP = 2
INIT_ACCOUNT = 3

IV_COPY = 0
IV_TYPE = 1
IV_VALUE = 2

LedgerInitValues = {
    TransactionType.Action: {
    # FieldName, True-Copy, TypeOfInitialization, DefaultValue
        'id': (False, INIT_NULL, None),
        'timestamp': (False, INIT_TIMESTAMP, None),
        'account_id': (True, INIT_ACCOUNT, None),
        'peer_id': (True, INIT_VALUE, 0),
        'alt_currency_id': (True, INIT_VALUE, None)
    },
    TransactionType.Trade: {
        'id': (False, INIT_NULL, None),
        'timestamp': (False, INIT_TIMESTAMP, None),
        'settlement': (True, INIT_VALUE, 0),
        'number': (False, INIT_VALUE, ''),
        'account_id': (True, INIT_ACCOUNT, None),
        'asset_id': (True, INIT_VALUE, 0),
        'qty': (True, INIT_VALUE, 0),
        'price': (True, INIT_VALUE, 0),
        'coupon': (True, INIT_VALUE, 0),
        'fee': (True, INIT_VALUE, 0)
    },
    TransactionType.Dividend: {
        'id': (False, INIT_NULL, None),
        'timestamp': (False, INIT_TIMESTAMP, None),
        'number': (False, INIT_VALUE, ''),
        'account_id': (True, INIT_ACCOUNT, None),
        'asset_id': (True, INIT_VALUE, 0),
        'sum': (True, INIT_VALUE, 0),
        'sum_tax': (True, INIT_VALUE, 0),
        'note': (True, INIT_VALUE, None),
        'tax_country_id': (True, INIT_VALUE, 0)
    },
    TransactionType.Transfer: {
        'id': (False, INIT_NULL, None),
        'from_id': (False, INIT_NULL, None),
        'from_timestamp': (False, INIT_TIMESTAMP, None),
        'from_acc_id': (True, INIT_ACCOUNT, None),
        'to_id': (False, INIT_NULL, None),
        'to_timestamp': (False, INIT_TIMESTAMP, None),
        'to_acc_id': (True, INIT_ACCOUNT, None),
        'fee_id': (False, INIT_NULL, None),
        'fee_timestamp': (True, INIT_VALUE, 0),
        'fee_acc_id': (True, INIT_VALUE, 0),
        'from_amount': (True, INIT_VALUE, 0),
        'to_amount': (True, INIT_VALUE, 0),
        'fee_amount': (True, INIT_VALUE, 0),
        'note': (True, INIT_VALUE, '')
    },
    TransactionType.CorporateAction: {
        'id': (False, INIT_NULL, None),
        'timestamp': (False, INIT_TIMESTAMP, None),
        'number': (False, INIT_VALUE, ''),
        'account_id': (True, INIT_ACCOUNT, None),
        'type': (True, INIT_VALUE, 1),
        'asset_id': (True, INIT_VALUE, 0),
        'qty': (True, INIT_VALUE, 0),
        'asset_id_new': (True, INIT_VALUE, 0),
        'qty_new': (True, INIT_VALUE, 0),
        'note': (True, INIT_VALUE, '')
    }
}


class LedgerOperationsView(QObject):
    activateOperationView = Signal(int)
    stateIsCommitted = Signal()
    stateIsModified = Signal()

    OP_NAME = 0
    OP_MAPPER = 1
    OP_MAPPER_TABLE = 2
    OP_CHILD_VIEW = 3
    OP_CHILD_TABLE = 4
    OP_INIT = 5
    
    def __init__(self, operations_table_view):
        super().__init__()

        self.p_account_id = 0
        self.p_search_text = ''
        self.start_date_of_view = 0
        self.table_view = operations_table_view
        self.operations = None
        self.modified_operation_type = None
        self.current_index = None   # this variable is used for reconciliation only

        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self.onOperationContextMenu)
        self.table_view.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)  # forces usage of sizeHint() from delegate

    def setOperationsDetails(self, operations_details):
        self.operations = operations_details
        for operation_type in self.operations:
            if self.operations[operation_type][self.OP_MAPPER]:  # if mapper defined for operation type
                self.operations[operation_type][self.OP_MAPPER].model().dataChanged.connect(self.onDataEdit)
            if self.operations[operation_type][self.OP_CHILD_VIEW]:  # if view defined for operation type
                self.operations[operation_type][self.OP_CHILD_VIEW].model().dataChanged.connect(self.onDataEdit)
        self.table_view.selectionModel().selectionChanged.connect(self.OnOperationChange)

    def setOperationsFilter(self):
        operations_filter = ""
        if self.start_date_of_view > 0:
            operations_filter = "all_operations.timestamp >= {}".format(self.start_date_of_view)

        if self.p_account_id != 0:
            self.p_account_id = self.p_account_id
            if operations_filter == "":
                operations_filter = "all_operations.account_id = {}".format(self.p_account_id)
            else:
                operations_filter = operations_filter + " AND all_operations.account_id = {}".format(
                    self.p_account_id)

        if self.p_search_text:
            operations_filter = operations_filter + " AND (num_peer LIKE '%{}%' OR asset LIKE '%{}%')".format(
                self.p_search_text, self.p_search_text)

        self.table_view.model().setFilter(operations_filter)

    def setAccountId(self, account_id):
        if self.p_account_id == account_id:
            return
        self.p_account_id = account_id
        self.setOperationsFilter()

    def setSearchText(self, search_text):
        if self.p_search_text == search_text:
            return
        self.p_search_text = search_text
        self.setOperationsFilter()

    def setOperationsRange(self, start_date_of_view):
        self.start_date_of_view = start_date_of_view
        self.setOperationsFilter()
        
    def addNewOperation(self, operation_type):
        self.checkForUncommittedChanges()
        self.activateOperationView.emit(operation_type)
        mapper = self.operations[operation_type][self.OP_MAPPER]
        mapper.submit()
        mapper.model().setFilter(f"{self.operations[operation_type][self.OP_MAPPER_TABLE]}.id = 0")
        new_record = mapper.model().record()
        new_record = self.prepareNewOperation(operation_type, new_record, copy_mode=False)
        assert mapper.model().insertRows(0, 1)
        mapper.model().setRecord(0, new_record)
        mapper.toLast()
        self.initChildDetails(operation_type)

    def deleteOperation(self):
        if QMessageBox().warning(None, g_tr('LedgerOperationsView', "Confirmation"),
                                 g_tr('LedgerOperationsView', "Are you sure to delete selected transacion?"),
                                 QMessageBox.Yes, QMessageBox.No) == QMessageBox.No:
            return
        index = self.table_view.currentIndex()
        operations_model = self.table_view.model()
        operation_type = operations_model.data(operations_model.index(index.row(), 0))
        mapper = self.operations[operation_type][self.OP_MAPPER]
        mapper.model().removeRow(0)
        mapper.model().submitAll()
        self.stateIsCommitted.emit()
        operations_model.select()

    @Slot()
    def copyOperation(self):
        self.checkForUncommittedChanges()
        index = self.table_view.currentIndex()
        operations_model = self.table_view.model()
        operation_type = operations_model.data(operations_model.index(index.row(), 0))
        mapper = self.operations[operation_type][self.OP_MAPPER]
        row = mapper.currentIndex()
        old_id = mapper.model().record(row).value(mapper.model().fieldIndex("id"))
        new_record = mapper.model().record(row)
        new_record = self.prepareNewOperation(operation_type, new_record, copy_mode=True)
        mapper.model().setFilter(f"{self.operations[operation_type][self.OP_MAPPER_TABLE]}.id = 0")
        assert mapper.model().insertRows(0, 1)
        mapper.model().setRecord(0, new_record)
        mapper.toLast()

        if self.operations[operation_type][self.OP_CHILD_VIEW]:
            child_view = self.operations[operation_type][self.OP_CHILD_VIEW]
            child_view.model().setFilter(f"{self.operations[operation_type][self.OP_CHILD_TABLE]}.pid = 0")
            query = executeSQL(mapper.model().database(),
                               f"SELECT * FROM {self.operations[operation_type][self.OP_CHILD_TABLE]} "
                               "WHERE pid = :pid ORDER BY id DESC", [(":pid", old_id)])
            while query.next():
                new_record = query.record()
                new_record.setNull("id")
                new_record.setNull("pid")
                assert child_view.model().insertRows(0, 1)
                child_view.model().setRecord(0, new_record)

    @Slot()
    def addOperationChild(self, operation_type):
        child_view = self.operations[operation_type][self.OP_CHILD_VIEW]
        new_record = child_view.model().record()
        child_view.model().insertRecord(-1, new_record)

    @Slot()
    def deleteOperationChild(self, operation_type):
        child_view = self.operations[operation_type][self.OP_CHILD_VIEW]
        idx = child_view.selectionModel().selection().indexes()
        selected_row = idx[0].row()
        child_view.model().removeRow(selected_row)
        child_view.setRowHidden(selected_row, True)
        self.stateIsModified.emit()
        
    def checkForUncommittedChanges(self):
        if self.modified_operation_type:
            reply = QMessageBox().warning(None, g_tr('LedgerOperationsView', "You have unsaved changes"),
                                          self.operations[self.modified_operation_type][self.OP_NAME] +
                                          g_tr('LedgerOperationsView', " has uncommitted changes,\ndo you want to save it?"),
                                          QMessageBox.Yes, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.commitOperation()
            else:
                self.revertOperation()

    @Slot()
    def revertOperation(self):
        if self.modified_operation_type:
            if self.operations[self.modified_operation_type][self.OP_MAPPER]:  # if mapper defined for operation type
                self.operations[self.modified_operation_type][self.OP_MAPPER].model().revertAll()
            if self.operations[self.modified_operation_type][self.OP_CHILD_VIEW]:  # if child view defined for operation type
                self.operations[self.modified_operation_type][self.OP_CHILD_VIEW].model().revertAll()
            self.modified_operation_type = None
            self.stateIsCommitted.emit()

    @Slot()
    def commitOperation(self):
        if self.modified_operation_type:
            self.beforeMapperCommit(self.modified_operation_type)
            if self.operations[self.modified_operation_type][self.OP_MAPPER]:  # if mapper defined for operation type
                if not self.operations[self.modified_operation_type][self.OP_MAPPER].model().submitAll():
                    logging.fatal(
                        g_tr('LedgerOperationsView', "Submit failed: ") + self.operations[self.modified_operation_type][self.OP_MAPPER].model().lastError().text())
                    return
            self.beforeChildViewCommit(self.modified_operation_type)
            if self.operations[self.modified_operation_type][self.OP_CHILD_VIEW]:  # if child view defined for operation type
                if not self.operations[self.modified_operation_type][self.OP_CHILD_VIEW].model().submitAll():
                    logging.fatal(
                        g_tr('LedgerOperationsView', "Details submit failed: ") + self.operations[self.modified_operation_type][
                            self.OP_CHILD_VIEW].model().lastError().text())
                    return
            self.modified_operation_type = None
            self.stateIsCommitted.emit()
            self.table_view.model().select()
        
    def beforeMapperCommit(self, operation_type):
        if operation_type == TransactionType.Transfer:
            transfer_mapper = self.operations[operation_type][self.OP_MAPPER]
            record = transfer_mapper.model().record(0)
            note = record.value(transfer_mapper.model().fieldIndex("note"))
            if not note:  # If we don't have note - set it to NULL value to fire DB trigger
                transfer_mapper.model().setData(transfer_mapper.model().index(0, transfer_mapper.model().fieldIndex("note")), None)
            fee_amount = record.value(transfer_mapper.model().fieldIndex("fee_amount"))
            if not fee_amount:
                fee_amount = 0
            if abs(float(fee_amount)) < Setup.CALC_TOLERANCE:  # If we don't have fee - set Fee Account to NULL to fire DB trigger
                transfer_mapper.model().setData(transfer_mapper.model().index(0, transfer_mapper.model().fieldIndex("fee_acc_id")), None)

    def beforeChildViewCommit(self, operation_type):
        if operation_type == TransactionType.Action:
            actions_mapper = self.operations[operation_type][self.OP_MAPPER]
            pid = actions_mapper.model().data(actions_mapper.model().index(0, actions_mapper.model().fieldIndex("id")))
            if pid is None:  # we just have saved new action record (mapper submitAll() is called before this signal)
                pid = actions_mapper.model().query().lastInsertId()
            action_details_view = self.operations[operation_type][self.OP_CHILD_VIEW]
            for row in range(action_details_view.model().rowCount()):
                action_details_view.model().setData(action_details_view.model().index(row, 1), pid)
                
    def initChildDetails(self, operation_type):
        view = self.operations[operation_type][self.OP_CHILD_VIEW]
        if view:
            view.model().setFilter(f"{self.operations[operation_type][self.OP_CHILD_TABLE]}.pid = 0")
            
    def prepareNewOperation(self, operation_type, new_operation_record, copy_mode=False):
        init_values = self.operations[operation_type][self.OP_INIT]
        for field in init_values:
            if copy_mode and init_values[field][IV_COPY]:
                continue
            if init_values[field][IV_TYPE] == INIT_NULL:
                new_operation_record.setNull(field)
            if init_values[field][IV_TYPE] == INIT_TIMESTAMP:
                new_operation_record.setValue(field, QDateTime.currentSecsSinceEpoch())
            if  init_values[field][IV_TYPE] == INIT_ACCOUNT:
                new_operation_record.setValue(field, self.p_account_id)
            if init_values[field][IV_TYPE] == INIT_VALUE:
                new_operation_record.setValue(field, init_values[field][IV_VALUE])
        return new_operation_record

    @Slot()
    def onOperationContextMenu(self, pos):
        self.current_index = self.table_view.indexAt(pos)
        contextMenu = QMenu(self.table_view)
        actionReconcile = QAction(text=g_tr('LedgerOperationsView', "Reconcile"), parent=self)
        actionReconcile.triggered.connect(self.reconcileAtCurrentOperation)
        actionCopy = QAction(text=g_tr('LedgerOperationsView', "Copy"), parent=self)
        actionCopy.triggered.connect(self.copyOperation)
        actionDelete = QAction(text=g_tr('LedgerOperationsView', "Delete"), parent=self)
        actionDelete.triggered.connect(self.deleteOperation)
        contextMenu.addAction(actionReconcile)
        contextMenu.addSeparator()
        contextMenu.addAction(actionCopy)
        contextMenu.addAction(actionDelete)
        contextMenu.popup(self.table_view.viewport().mapToGlobal(pos))

    @Slot()
    def reconcileAtCurrentOperation(self):
        model = self.current_index.model()
        timestamp = model.data(model.index(self.current_index.row(), 2), Qt.DisplayRole)
        account_id = model.data(model.index(self.current_index.row(), 3), Qt.DisplayRole)
        _ = executeSQL(model.database(), "UPDATE accounts SET reconciled_on=:timestamp WHERE id = :account_id",
                       [(":timestamp", timestamp), (":account_id", account_id)])
        model.select()

    @Slot()
    def OnOperationChange(self, selected, _deselected):
        self.checkForUncommittedChanges()
        idx = selected.indexes()
        if idx:
            selected_row = idx[0].row()
            operations_model = self.table_view.model()
            operation_type = operations_model.record(selected_row).value("type")
            operation_id = operations_model.record(selected_row).value("id")
            self.activateOperationView.emit(operation_type)

            if self.operations[operation_type][self.OP_MAPPER]:  # if mapper defined for operation type
                mapper = self.operations[operation_type][self.OP_MAPPER]
                mapper.model().setFilter(f"{self.operations[operation_type][self.OP_MAPPER_TABLE]}.id = {operation_id}")
                mapper.setCurrentModelIndex(mapper.model().index(0, 0))
            if self.operations[operation_type][self.OP_CHILD_VIEW]:  # if child view defined for operation type
                view = self.operations[operation_type][self.OP_CHILD_VIEW]
                view.model().setFilter(f"{self.operations[operation_type][self.OP_CHILD_TABLE]}.pid = {operation_id}")

    @Slot()
    def onDataEdit(self, index_start, _index_stop, _role):
        for operation_type in self.operations:
            if self.operations[operation_type][self.OP_MAPPER]:   # if mapper defined for operation type
                if self.operations[operation_type][self.OP_MAPPER].model().isDirty():
                    self.modified_operation_type = operation_type
                    break
            if self.operations[operation_type][self.OP_CHILD_VIEW]:     # if view defined for operation type
                if self.operations[operation_type][self.OP_CHILD_VIEW].model().isDirty():
                    self.modified_operation_type = operation_type
                    break
        self.stateIsModified.emit()
