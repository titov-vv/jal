import logging

from constants import *
from PySide2.QtCore import Qt, QObject, Signal, Slot, QDateTime
from PySide2.QtWidgets import QMessageBox, QMenu, QAction
from PySide2.QtSql import QSqlQuery


class LedgerOperationsView(QObject):
    activateOperationView = Signal(int)
    stateIsCommitted = Signal()

    OP_NAME = 0
    OP_MAPPER = 1
    OP_MAPPER_TABLE = 2
    OP_CHILD_VIEW = 3
    OP_CHILD_TABLE = 4
    
    def __init__(self, operations_table_view):
        super().__init__()

        self.p_account_id = 0
        self.p_search_text = ''
        self.start_date_of_view = 0
        self.table_view = operations_table_view
        self.operations = None
        self.current_index = None   # this variable is used for reconciliation only

        self.table_view.customContextMenuRequested.connect(self.onOperationContextMenu)

    def setOperationsDetails(self, operations_details):
        self.operations = operations_details

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
        self.prepareNewOperation(operation_type, new_record)
        assert mapper.model().insertRows(0, 1)
        mapper.model().setRecord(0, new_record)
        mapper.toLast()
        self.initChildDetails(operation_type)

    def deleteOperation(self):
        if QMessageBox().warning(None, "Confirmation",
                                 "Are you sure to delete selected transacion?",
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
        
    def checkForUncommittedChanges(self):
        for operation_type in self.operations:
            if self.operations[operation_type][self.OP_MAPPER]:   # if mapper defined for operation type
                if self.operations[operation_type][self.OP_MAPPER].model().isDirty():
                    self.askToCommitChanges(operation_type)
            if self.operations[operation_type][self.OP_CHILD_VIEW]:     # if view defined for operatation type
                if self.operations[operation_type][self.OP_CHILD_VIEW].model().isDirty():
                    self.askToCommitChanges(operation_type)

    def askToCommitChanges(self, operation_type):
        reply = QMessageBox().warning(None, "You have unsaved changes",
                                      self.operations[operation_type][self.OP_NAME] +
                                      " has uncommitted changes,\ndo you want to save it?",
                                      QMessageBox.Yes, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.commitOperation(operation_type)
        else:
            self.revertOperation(operation_type)

    def revertOperation(self, operation_type):
        if self.operations[operation_type][self.OP_MAPPER]:  # if mapper defined for operation type
            self.operations[operation_type][self.OP_MAPPER].model().revertAll()
        if self.operations[operation_type][self.OP_CHILD_VIEW]:  # if mapper defined for operation type
            self.operations[operation_type][self.OP_CHILD_VIEW].model().revertAll()
        self.stateIsCommitted.emit()

    def commitOperation(self, operation_type):
        self.beforeMapperCommit(operation_type)
        if self.operations[operation_type][self.OP_MAPPER]:  # if mapper defined for operation type
            if not self.operations[operation_type][self.OP_MAPPER].model().submitAll():
                logging.fatal(
                    self.tr("Action submit failed: ") + self.operations[operation_type][self.OP_MAPPER].model().lastError().text())
                return
        self.beforeChildViewCommit(operation_type)
        if self.operations[operation_type][self.OP_CHILD_VIEW]:  # if mapper defined for operation type
            if not self.operations[operation_type][self.OP_CHILD_VIEW].model().submitAll():
                logging.fatal(
                    self.tr("Action details submit failed: ") + self.operations[operation_type][
                        self.OP_CHILD_VIEW].model().lastError().text())
                return
        self.stateIsCommitted.emit()
        self.table_view.model().select()
        
    def beforeMapperCommit(self, operation_type):
        if operation_type == TRANSACTION_TRANSFER:
            transfer_mapper = self.operations[operation_type][self.OP_MAPPER]
            record = transfer_mapper.model().record(0)
            note = record.value(transfer_mapper.model().fieldIndex("note"))
            if not note:  # If we don't have note - set it to NULL value to fire DB trigger
                transfer_mapper.model().setData(transfer_mapper.model().index(0, transfer_mapper.model().fieldIndex("note")), None)
            fee_amount = record.value(transfer_mapper.model().fieldIndex("fee_amount"))
            if not fee_amount:
                fee_amount = 0
            if abs(float(fee_amount)) < CALC_TOLERANCE:  # If we don't have fee - set Fee Account to NULL to fire DB trigger
                transfer_mapper.model().setData(transfer_mapper.model().index(0, transfer_mapper.model().fieldIndex("fee_acc_id")), None)

    def beforeChildViewCommit(self, operation_type):
        if operation_type == TRANSACTION_ACTION:
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
            
    def prepareNewOperation(self, operation_type, new_operation_record):
        if operation_type == TRANSACTION_ACTION or operation_type == TRANSACTION_TRADE or operation_type == TRANSACTION_DIVIDEND:
            new_operation_record.setValue("timestamp", QDateTime.currentSecsSinceEpoch())
            if self.p_account_id != 0:
                new_operation_record.setValue("account_id", self.p_account_id)
        if operation_type == TRANSACTION_TRANSFER:
            new_operation_record.setValue("from_timestamp", QDateTime.currentSecsSinceEpoch())
            if self.p_account_id != 0:
                new_operation_record.setValue("from_acc_id", self.p_account_id)
            new_operation_record.setValue("to_timestamp", QDateTime.currentSecsSinceEpoch())
            new_operation_record.setValue("fee_timestamp", 0)

    @Slot()
    def onOperationContextMenu(self, pos):
        self.current_index = self.table_view.indexAt(pos)
        contextMenu = QMenu(self.table_view)
        actionReconcile = QAction(text="Reconcile", parent=self)
        actionReconcile.triggered.connect(self.reconcileAtCurrentOperation)
        actionCopy = QAction(text="Copy", parent=self)
        actionCopy.triggered.connect(self.copyOperation)
        actionDelete = QAction(text="Delete", parent=self)
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
        query = QSqlQuery(model.database())
        query.prepare("UPDATE accounts SET reconciled_on=:timestamp WHERE id = :account_id")
        query.bindValue(":timestamp", timestamp)
        query.bindValue(":account_id", account_id)
        assert query.exec_()
        model.select()

    @Slot()
    def copyOperation(self):
        pass