import logging
from decimal import Decimal
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QMessageBox, QHeaderView
from PySide6.QtSql import QSqlTableModel
from PySide6.QtGui import QFont
from jal.ui.widgets.ui_term_deposit_operation import Ui_TermDepositOperation
from jal.widgets.abstract_operation_details import AbstractOperationDetails
from jal.db.view_model import JalViewModel
from jal.db.operations import LedgerTransaction
from jal.db.helpers import load_icon, now_ts, localize_decimal, db_row2dict
from jal.widgets.delegates import FloatDelegate, TimestampDelegate


# ----------------------------------------------------------------------------------------------------------------------
class TermDepositWidget(AbstractOperationDetails):
    def __init__(self, parent=None):
        super().__init__(parent=parent, ui_class=Ui_TermDepositOperation)
        self.operation_type = LedgerTransaction.TermDeposit
        super()._init_db("term_deposits")

        self.timestamp_delegate = TimestampDelegate()
        self.float_delegate = FloatDelegate(2)

        self.ui.actions_table.horizontalHeader().setFont(self.bold_font)
        self.ui.add_button.setIcon(load_icon("add.png"))
        self.ui.del_button.setIcon(load_icon("remove.png"))

        self.ui.add_button.clicked.connect(self.add_action)
        self.ui.del_button.clicked.connect(self.remove_action)

        self.actions_model = DepositActionsModel(self.ui.actions_table, "deposit_actions")
        self.actions_model.setEditStrategy(QSqlTableModel.OnManualSubmit)
        self.ui.actions_table.setModel(self.actions_model)

        self.ui.account_widget.changed.connect(self.mapper.submit)

        self.mapper.addMapping(self.ui.account_widget, self.model.fieldIndex("account_id"))
        self.mapper.addMapping(self.ui.note, self.model.fieldIndex("note"))

        self.ui.actions_table.setItemDelegateForColumn(2, self.timestamp_delegate)
        self.ui.actions_table.setItemDelegateForColumn(4, self.float_delegate)

        self.model.select()
        self.actions_model.select()
        self.actions_model.configureView()

    def set_id(self, oid):
        self.actions_model.setFilter(f"deposit_actions.deposit_id = {oid}")  # First we need to select right children
        super().set_id(oid)

    @Slot()
    def add_action(self):
        new_record = self.actions_model.record()
        new_record.setValue("timestamp", now_ts())
        new_record.setValue("action_type", 0)
        new_record.setValue("amount", '0')
        if not self.actions_model.insertRecord(-1, new_record):
            logging.fatal(self.tr("Failed to add new record: ") + self.actions_model.lastError().text())
            return

    @Slot()
    def remove_action(self):
        selection = self.ui.actions_table.selectionModel().selection().indexes()
        for idx in selection:
            self.actions_model.removeRow(idx.row())
            self.onDataChange(idx, idx, None)

    def _validated(self):
        fields = db_row2dict(self.model, 0)
        if not fields['account_id']:
            return False
        if not self.actions_model.rowCount():
            QMessageBox().warning(self, self.tr("Incomplete data"), self.tr("Deposit contains no actions"), QMessageBox.Ok)
            return False
        for row in range(self.actions_model.rowCount()):
            fields = db_row2dict(self.actions_model, row)
            if fields['action_type'] is None or fields['action_type'] == 0:
                QMessageBox().warning(self, self.tr("Incomplete data"), self.tr("Deposit action type isn't set"), QMessageBox.Ok)
                return False
        return True

    def _save(self):
        self.model.database().transaction()
        try:
            if not self.model.submitAll():
                raise RuntimeError(self.tr("Operation submit failed: ") + self.model.lastError().text())
            oid = self.model.data(self.model.index(0, self.model.fieldIndex("id")))
            if oid is None:  # we just have saved new action record and need last inserted id
                oid = self.model.last_insert_id()
            for row in range(self.actions_model.rowCount()):   # Set PID for all child records
                self.actions_model.setData(self.actions_model.index(row, self.actions_model.fieldIndex("deposit_id")), oid)
            if not self.actions_model.submitAll():
                raise RuntimeError(self.tr("Operation details submit failed: ") + self.actions_model.lastError().text())
        except Exception as e:
            self.model.database().rollback()
            logging.fatal(e)
            return
        self.model.database().commit()
        self.modified = False
        self.ui.commit_button.setEnabled(False)
        self.ui.revert_button.setEnabled(False)
        self.dbUpdated.emit()

    @Slot()
    def revertChanges(self):
        self.model.revertAll()
        self.actions_model.revertAll()
        self.modified = False
        self.ui.commit_button.setEnabled(False)
        self.ui.revert_button.setEnabled(False)

    def createNew(self, account_id=0):
        super().createNew(account_id)
        self.actions_model.setFilter(f"deposit_actions.deposit_id = 0")

    def prepareNew(self, account_id):
        new_record = super().prepareNew(account_id)
        new_record.setValue("account_id", account_id)
        new_record.setValue("note", None)
        return new_record

    def copyNew(self):
        super().copyNew()
        child_records = []
        for row in range(self.actions_model.rowCount()):
            child_records.append(self.actions_model.record(row))
        self.actions_model.setFilter(f"deposit_actions.deposit_id = 0")
        for record in reversed(child_records):
            record.setNull("id")
            record.setNull("deposit_id")
            assert self.actions_model.insertRows(0, 1)
            self.actions_model.setRecord(0, record)

    def copyToNew(self, row):
        new_record = self.model.record(row)
        new_record.setNull("id")
        return new_record


# ----------------------------------------------------------------------------------------------------------------------
class DepositActionsModel(JalViewModel):
    def __init__(self, parent_view, table_name):
        super().__init__(parent_view, table_name)
        self._columns = ["id", "deposit_id", self.tr("Date/Time"), self.tr("Action"), self.tr("Amount")]

    def footerData(self, section, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if section == 3:
                return self.tr("Planned value:")
            elif section == 4:
                total = Decimal('0')
                return localize_decimal(total, precision=2, percent=True)
        elif role == Qt.FontRole:
            font = QFont()
            font.setBold(True)
            return font
        elif role == Qt.TextAlignmentRole:
            if section == 4:
                return Qt.AlignRight | Qt.AlignVCenter
            else:
                return Qt.AlignLeft | Qt.AlignVCenter
        return None

    def configureView(self):
        self._view.setColumnHidden(0, True)
        self._view.setColumnHidden(1, True)
        self._view.setColumnWidth(2, self._view.fontMetrics().horizontalAdvance("00/00/0000 00:00:00") * 1.25)
        self._view.setColumnWidth(4, 100)
        self._view.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
