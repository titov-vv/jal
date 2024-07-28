import logging
from decimal import Decimal

from PySide6.QtCore import Qt, Slot, QStringListModel, QByteArray
from PySide6.QtWidgets import QMessageBox, QHeaderView
from PySide6.QtSql import QSqlTableModel
from PySide6.QtGui import QFont
from jal.ui.widgets.ui_corporate_action_operation import Ui_CorporateActionOperation
from jal.widgets.abstract_operation_details import AbstractOperationDetails
from jal.widgets.icons import JalIcon
from jal.widgets.delegates import WidgetMapperDelegateBase, AssetSelectorDelegate, FloatDelegate
from jal.db.view_model import JalViewModel
from jal.db.helpers import localize_decimal, db_row2dict, now_ts
from jal.db.operations import LedgerTransaction, CorporateAction


# ----------------------------------------------------------------------------------------------------------------------
class CorporateActionWidgetDelegate(WidgetMapperDelegateBase):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.delegates = {'timestamp': self.timestamp_delegate,
                          'asset_id': self.symbol_delegate,
                          'qty': self.decimal_delegate}


# ----------------------------------------------------------------------------------------------------------------------
class CorporateActionWidget(AbstractOperationDetails):
    def __init__(self, parent=None):
        super().__init__(parent=parent, ui_class=Ui_CorporateActionOperation)
        self.operation_type = LedgerTransaction.CorporateAction
        self.combo_model = None

        self.asset_delegate = AssetSelectorDelegate()
        self.float_delegate = FloatDelegate(2)
        self.percent_delegate = FloatDelegate(2, percent=True)

        self.ui.timestamp_editor.setFixedWidth(self.ui.timestamp_editor.fontMetrics().horizontalAdvance("00/00/0000 00:00:00") * 1.25)
        self.ui.add_button.setIcon(JalIcon[JalIcon.ADD])
        self.ui.del_button.setIcon(JalIcon[JalIcon.REMOVE])
        self.ui.results_table.horizontalHeader().setFont(self.bold_font)
        self.ui.arrow.setText(" 🡆 ")  # it crashes if added via Qt-Designer

        self.ui.add_button.clicked.connect(self.addResult)
        self.ui.del_button.clicked.connect(self.delResult)

        super()._init_db("asset_actions")
        self.combo_model = QStringListModel([self.tr("N/A"),
                                             self.tr("Merger"),
                                             self.tr("Spin-Off"),
                                             self.tr("Symbol change"),
                                             self.tr("Split"),
                                             self.tr("Delisting")])
        self.ui.type.setModel(self.combo_model)

        self.mapper.setItemDelegate(CorporateActionWidgetDelegate(self.mapper))

        self.results_model = ResultsModel(self.ui.results_table, "action_results")
        self.results_model.setEditStrategy(QSqlTableModel.OnManualSubmit)
        self.ui.results_table.setModel(self.results_model)

        self.results_model.dataChanged.connect(self.onDataChange)
        self.ui.account_widget.changed.connect(self.mapper.submit)
        self.ui.asset_widget.changed.connect(self.mapper.submit)

        self.mapper.addMapping(self.ui.timestamp_editor, self.model.fieldIndex("timestamp"))
        self.mapper.addMapping(self.ui.account_widget, self.model.fieldIndex("account_id"))
        self.mapper.addMapping(self.ui.asset_widget, self.model.fieldIndex("asset_id"))
        self.mapper.addMapping(self.ui.number, self.model.fieldIndex("number"))
        self.mapper.addMapping(self.ui.qty_edit, self.model.fieldIndex("qty"))
        self.mapper.addMapping(self.ui.note, self.model.fieldIndex("note"))
        self.mapper.addMapping(self.ui.type, self.model.fieldIndex("type"), QByteArray().setRawData("currentIndex", 12))

        self.ui.results_table.setItemDelegateForColumn(2, self.asset_delegate)
        self.ui.results_table.setItemDelegateForColumn(3, self.float_delegate)
        self.ui.results_table.setItemDelegateForColumn(4, self.percent_delegate)

        self.model.select()
        self.results_model.select()
        self.results_model.configureView()

    def set_id(self, oid):
        self.results_model.setFilter(f"action_results.action_id = {oid}")  # First we need to select right children
        super().set_id(oid)

    @Slot()
    def addResult(self):
        new_record = self.results_model.record()
        new_record.setValue("qty", 0)
        new_record.setValue("value_share", 0)
        if not self.results_model.insertRecord(-1, new_record):
            logging.fatal(self.tr("Failed to add new record: ") + self.results_model.lastError().text())
            return

    @Slot()
    def delResult(self):
        selection = self.ui.results_table.selectionModel().selection().indexes()
        for idx in selection:
            self.results_model.removeRow(idx.row())
            self.onDataChange(idx, idx, None)

    def _validated(self):
        constraints = {  # number of mandatory records in results_model for given action type
            CorporateAction.Delisting:    (0, self.tr("There can't be results of Delisting")),
            CorporateAction.SpinOff:      (2, self.tr("Spin-off should have exactly 2 result rows:\none for ParentCo and second for Subsidiary")),
            CorporateAction.Split:        (1, self.tr("Split should have only 1 result row")),
            CorporateAction.SymbolChange: (1, self.tr("Symbol change should have only 1 result row"))
        }
        fields = db_row2dict(self.model, 0)
        results = [db_row2dict(self.results_model, x) for x in range(self.results_model.rowCount()) if not self.results_model.row_is_deleted(x)]
        # Validate that number of result records is correct for a given action type
        if len(results) == 0 and fields['type'] != CorporateAction.Delisting:
            QMessageBox().warning(self, self.tr("Wrong data"), self.tr("You can't have zero results unless it is Delisting"), QMessageBox.Ok)
            return False
        if fields['type'] in constraints and constraints[fields['type']][0] != len(results):
            QMessageBox().warning(self, self.tr("Wrong data"), constraints[fields['type']][1], QMessageBox.Ok)
            return False
        # Split should have the same asset before and after the operation
        if fields['type'] == CorporateAction.Split and fields['asset_id'] != results[0]['asset_id']:
            QMessageBox().warning(self, self.tr("Wrong data"), self.tr("You can't change asset during Split"), QMessageBox.Ok)
            return False
        # Everything after corporate action should add up to 100% of initial asset value
        total_share = sum([Decimal(x['value_share']) for x in results])
        if total_share != Decimal('1'):
            QMessageBox().warning(self, self.tr("Incomplete data"), self.tr("Total results share doesn't sum up to 100%"), QMessageBox.Ok)
            return False
        return True

    def _save(self):
        self.model.database().transaction()
        try:
            if not self.model.submitAll():
                raise RuntimeError(self.tr("Operation submit failed: ") + self.model.lastError().text())
            oid = self.model.data(self.model.index(0, self.model.fieldIndex("oid")))
            if oid is None:  # we just have saved new action record and need last inserted id
                oid = self.model.last_insert_id()
            for row in range(self.results_model.rowCount()):
                self.results_model.setData(self.results_model.index(row, self.results_model.fieldIndex("action_id")), oid)
            if not self.results_model.submitAll():
                raise RuntimeError(self.tr("Operation details submit failed: ") + self.results_model.lastError().text())
        except Exception as e:
            self.model.database().rollback()
            logging.fatal(e)
            return
        self.modified = False
        self.ui.commit_button.setEnabled(False)
        self.ui.revert_button.setEnabled(False)
        self.dbUpdated.emit()

    @Slot()
    def revertChanges(self):
        self.model.revertAll()
        self.results_model.revertAll()
        self.modified = False
        self.ui.commit_button.setEnabled(False)
        self.ui.revert_button.setEnabled(False)

    def createNew(self, account_id=0):
        super().createNew(account_id)
        self.results_model.setFilter(f"action_results.action_id = 0")

    def prepareNew(self, account_id):
        new_record = super().prepareNew(account_id)
        new_record.setValue("timestamp", now_ts())
        new_record.setValue("number", '')
        new_record.setValue("account_id", account_id)
        new_record.setValue("type", 0)
        new_record.setValue("asset_id", 0)
        new_record.setValue("qty", '0')
        new_record.setValue("note", None)
        return new_record

    def copyNew(self):
        super().copyNew()
        child_records = []
        for row in range(self.results_model.rowCount()):
            child_records.append(self.results_model.record(row))
        self.results_model.setFilter(f"action_results.action_id = 0")
        for record in reversed(child_records):
            record.setNull("id")
            record.setNull("action_id")
            assert self.results_model.insertRows(0, 1)
            self.results_model.setRecord(0, record)

    def copyToNew(self, row):
        new_record = self.model.record(row)
        new_record.setNull("oid")
        new_record.setValue("timestamp", now_ts())
        new_record.setValue("number", '')
        return new_record


# ----------------------------------------------------------------------------------------------------------------------
class ResultsModel(JalViewModel):
    def __init__(self, parent_view, table_name):
        super().__init__(parent_view, table_name)
        self._columns = ["id", "action_id", self.tr("Asset"), self.tr("Qty"), self.tr("Share, %")]

    def footerData(self, section, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if section == 2:
                return self.tr("Total")
            elif section == 4:
                total = Decimal('0')
                for row in range(self.rowCount()):
                    try:
                        value = Decimal(self.index(row, section).data())
                    except:
                        value = Decimal('0')
                    total += value
                return localize_decimal(total, precision=2, percent=True)
        elif role == Qt.FontRole:
            font = QFont()
            font.setBold(True)
            return font
        elif role == Qt.TextAlignmentRole:
            if section == 2:
                return Qt.AlignLeft | Qt.AlignVCenter
            else:
                return Qt.AlignRight | Qt.AlignVCenter
        return None

    def configureView(self):
        self._view.setColumnHidden(0, True)
        self._view.setColumnHidden(1, True)
        self._view.setColumnWidth(3, 100)
        self._view.setColumnWidth(4, 100)
        self._view.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
