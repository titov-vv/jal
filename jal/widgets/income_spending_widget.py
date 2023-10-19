import logging
from datetime import datetime
from dateutil import tz
from decimal import Decimal

from PySide6.QtCore import Qt, Slot, QByteArray
from PySide6.QtWidgets import QMessageBox, QHeaderView
from PySide6.QtSql import QSqlTableModel
from PySide6.QtGui import QFont
from jal.ui.widgets.ui_income_spending_operation import Ui_IncomeSpendingOperation
from jal.widgets.abstract_operation_details import AbstractOperationDetails
from jal.db.view_model import JalViewModel
from jal.db.helpers import load_icon, localize_decimal, db_row2dict
from jal.db.operations import LedgerTransaction
from jal.widgets.delegates import WidgetMapperDelegateBase, FloatDelegate, CategorySelectorDelegate, TagSelectorDelegate


# ----------------------------------------------------------------------------------------------------------------------
class IncomeSpendingWidgetDelegate(WidgetMapperDelegateBase):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.delegates = {'timestamp': self.timestamp_delegate}


# ----------------------------------------------------------------------------------------------------------------------
class IncomeSpendingWidget(AbstractOperationDetails):
    def __init__(self, parent=None):
        super().__init__(parent=parent, ui_class=Ui_IncomeSpendingOperation)
        self.operation_type = LedgerTransaction.IncomeSpending
        super()._init_db("actions")

        self.category_delegate = CategorySelectorDelegate()
        self.tag_delegate = TagSelectorDelegate()
        self.float_delegate = FloatDelegate(2)

        self.ui.timestamp_editor.setFixedWidth(self.ui.timestamp_editor.fontMetrics().horizontalAdvance("00/00/0000 00:00:00") * 1.25)
        self.ui.a_currency.setText(self.tr("Paid in foreign currency:"))
        self.ui.details_table.horizontalHeader().setFont(self.bold_font)
        self.ui.add_button.setIcon(load_icon("add.png"))
        self.ui.del_button.setIcon(load_icon("remove.png"))
        self.ui.copy_button.setIcon(load_icon("copy.png"))

        self.ui.add_button.clicked.connect(self.add_child)
        self.ui.copy_button.clicked.connect(self.copy_child)
        self.ui.del_button.clicked.connect(self.delete_child)
        self.model.beforeInsert.connect(self.before_record_insert)
        self.model.beforeUpdate.connect(self.before_record_update)

        self.mapper.setItemDelegate(IncomeSpendingWidgetDelegate(self.mapper))

        self.details_model = DetailsModel(self.ui.details_table, "action_details")
        self.details_model.setEditStrategy(QSqlTableModel.OnManualSubmit)
        self.ui.details_table.setModel(self.details_model)
        self.details_model.dataChanged.connect(self.onDataChange)

        self.ui.account_widget.changed.connect(self.mapper.submit)
        self.ui.peer_widget.changed.connect(self.mapper.submit)
        self.ui.a_currency.changed.connect(self.mapper.submit)
        self.ui.a_currency.name_updated.connect(self.details_model.set_alternative_currency)

        self.mapper.addMapping(self.ui.timestamp_editor, self.model.fieldIndex("timestamp"))
        self.mapper.addMapping(self.ui.account_widget, self.model.fieldIndex("account_id"))
        self.mapper.addMapping(self.ui.currency, self.model.fieldIndex("account_id"))
        self.mapper.addMapping(self.ui.peer_widget, self.model.fieldIndex("peer_id"))
        self.mapper.addMapping(self.ui.a_currency, self.model.fieldIndex("alt_currency_id"), QByteArray("currency_id_str"))
        self.mapper.addMapping(self.ui.note, self.model.fieldIndex("note"))

        self.ui.details_table.setItemDelegateForColumn(2, self.category_delegate)
        self.ui.details_table.setItemDelegateForColumn(3, self.tag_delegate)
        self.ui.details_table.setItemDelegateForColumn(4, self.float_delegate)
        self.ui.details_table.setItemDelegateForColumn(5, self.float_delegate)

        self.model.select()
        self.details_model.select()
        self.details_model.configure_view()

    def set_id(self, oid):
        self.details_model.setFilter(f"action_details.pid = {oid}")  # First we need to select right children
        super().set_id(oid)

    @Slot()
    def add_child(self):
        new_record = self.details_model.record()
        new_record.setNull("tag_id")
        new_record.setValue("amount", '0')
        new_record.setValue("amount_alt", '0')
        if not self.details_model.insertRecord(-1, new_record):
            logging.fatal(self.tr("Failed to add new record: ") + self.details_model.lastError().text())
            return

    @Slot()
    def copy_child(self):
        idx = self.ui.details_table.selectionModel().selection().indexes()
        src_record = self.details_model.record(idx[0].row())
        new_record = self.details_model.record()
        new_record.setValue("category_id", src_record.value("category_id"))
        if src_record.value("tag_id"):
            new_record.setValue("tag_id", src_record.value("tag_id"))
        else:
            new_record.setNull("tag_id")
        new_record.setValue("amount", src_record.value("amount"))
        new_record.setValue("amount_alt", src_record.value("amount_alt"))
        new_record.setValue("note", src_record.value("note"))
        if not self.details_model.insertRecord(-1, new_record):
            logging.fatal(self.tr("Failed to add new record: ") + self.details_model.lastError().text())
            return

    @Slot()
    def delete_child(self):
        selection = self.ui.details_table.selectionModel().selection().indexes()
        for idx in selection:
            self.details_model.removeRow(idx.row())
            self.onDataChange(idx, idx, None)

    def _validated(self):
        fields = db_row2dict(self.model, 0)
        if not fields['account_id'] or not fields['peer_id']:
            return False
        if not self.details_model.rowCount():
            QMessageBox().warning(self, self.tr("Incomplete data"), self.tr("Operation contains no details"), QMessageBox.Ok)
            return False
        for row in range(self.details_model.rowCount()):
            fields = db_row2dict(self.details_model, row)
            if fields['category_id'] is None or fields['category_id'] == 0:
                QMessageBox().warning(self, self.tr("Incomplete data"),
                                      self.tr("Category isn't set for '{}' (Amount: {})".format(fields['note'], fields['amount'])), QMessageBox.Ok)
                return False
        return True

    def _save(self):
        self.model.database().transaction()
        try:
            if not self.model.submitAll():
                raise RuntimeError(self.tr("Operation submit failed: ") + self.model.lastError().text())
            pid = self.model.data(self.model.index(0, self.model.fieldIndex("id")))
            if pid is None:  # we just have saved new action record and need last inserted id
                pid = self.model.last_insert_id()
            for row in range(self.details_model.rowCount()):   # Set PID for all child records
                self.details_model.setData(self.details_model.index(row, self.details_model.fieldIndex("pid")), pid)
            if not self.details_model.submitAll():
                raise RuntimeError(self.tr("Operation details submit failed: ") + self.details_model.lastError().text())
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
        self.details_model.revertAll()
        self.modified = False
        self.ui.commit_button.setEnabled(False)
        self.ui.revert_button.setEnabled(False)

    def createNew(self, account_id=0):
        super().createNew(account_id)
        self.details_model.setFilter(f"action_details.pid = 0")

    def prepareNew(self, account_id):
        new_record = super().prepareNew(account_id)
        new_record.setValue("timestamp", int(datetime.now().replace(tzinfo=tz.tzutc()).timestamp()))
        new_record.setValue("account_id", account_id)
        new_record.setValue("peer_id", 0)
        new_record.setValue("alt_currency_id", None)
        return new_record

    def copyNew(self):
        super().copyNew()
        child_records = []
        for row in range(self.details_model.rowCount()):
            child_records.append(self.details_model.record(row))
        self.details_model.setFilter(f"action_details.pid = 0")
        for record in reversed(child_records):
            record.setNull("id")
            record.setNull("pid")
            if not record.value("tag_id"):
                record.setNull("tag_id")
            assert self.details_model.insertRows(0, 1)
            self.details_model.setRecord(0, record)

    def copyToNew(self, row):
        new_record = self.model.record(row)
        new_record.setNull("id")
        new_record.setValue("timestamp", int(datetime.now().replace(tzinfo=tz.tzutc()).timestamp()))
        return new_record

    def before_record_insert(self, record):
        if record.value("alt_currency_id") == 0 or record.value("alt_currency_id") == '':
            record.setNull("alt_currency_id")

    def before_record_update(self, _row, record):
        self.before_record_insert(record)   # processing is the same as before insert


# ----------------------------------------------------------------------------------------------------------------------
class DetailsModel(JalViewModel):
    def __init__(self, parent_view, table_name):
        super().__init__(parent_view, table_name)
        self._columns = ["id", "pid", self.tr("Category"), self.tr("Tag"),
                         self.tr("Amount"), self.tr("Amount"), self.tr("Note")]
        self.alt_currency_name = ''

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if section == 5 and orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._columns[section] + ', ' + self.alt_currency_name
        else:
            return super().headerData(section, orientation, role)

    def footerData(self, section, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if section == 6:
                return self.tr("Total")
            elif section == 4 or section == 5:
                total = Decimal('0')
                for row in range(self.rowCount()):
                    try:
                        value = Decimal(self.index(row, section).data())
                    except:
                        value = Decimal('0')
                    total += value
                return localize_decimal(total, precision=2)
        elif role == Qt.FontRole:
            font = QFont()
            font.setBold(True)
            return font
        elif role == Qt.TextAlignmentRole:
            if section == 6:
                return Qt.AlignLeft | Qt.AlignVCenter
            else:
                return Qt.AlignRight | Qt.AlignVCenter
        return None

    def configure_view(self):
        self._view.setColumnHidden(0, True)
        self._view.setColumnHidden(1, True)
        self._view.setColumnHidden(5, True)
        self._view.setColumnWidth(2, 200)
        self._view.setColumnWidth(3, 200)
        self._view.setColumnWidth(4, 100)
        self._view.setColumnWidth(5, 100)
        self._view.horizontalHeader().setSectionResizeMode(6, QHeaderView.Stretch)
        self._view.horizontalHeader().moveSection(6, 0)

    def set_alternative_currency(self, currency_name):
        if currency_name:
            self._view.setColumnHidden(5, False)
            self.alt_currency_name = currency_name
            self.headerDataChanged.emit(Qt.Horizontal, 5, 5)
        else:
            for row in range(self.rowCount()):
                self.setData(self.index(row, self.fieldIndex("amount_alt")), '0')  # Reset all alternative amounts
            self._view.setColumnHidden(5, True)
