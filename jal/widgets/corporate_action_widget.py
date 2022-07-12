import logging
from datetime import datetime
from dateutil import tz

from PySide6.QtCore import Qt, Slot, QStringListModel, QByteArray
from PySide6.QtWidgets import QLabel, QDateTimeEdit, QLineEdit, QComboBox, QTableView, QHeaderView, QPushButton
from PySide6.QtSql import QSqlTableModel
from PySide6.QtGui import QFont
from jal.widgets.abstract_operation_details import AbstractOperationDetails
from jal.widgets.reference_selector import AccountSelector, AssetSelector
from jal.widgets.delegates import WidgetMapperDelegateBase, AssetSelectorDelegate, FloatDelegate
from jal.db.helpers import db_connection, load_icon, executeSQL
from jal.db.operations import LedgerTransaction


# ----------------------------------------------------------------------------------------------------------------------
class CorporateActionWidgetDelegate(WidgetMapperDelegateBase):
    def __init__(self, parent=None):
        WidgetMapperDelegateBase.__init__(self, parent)
        self.delegates = {'timestamp': self.timestamp_delegate,
                          'asset_id': self.symbol_delegate,
                          'qty': self.float_delegate}


# ----------------------------------------------------------------------------------------------------------------------
class CorporateActionWidget(AbstractOperationDetails):
    def __init__(self, parent=None):
        AbstractOperationDetails.__init__(self, parent)
        self.name = "Corporate action"
        self.operation_type = LedgerTransaction.CorporateAction
        self.combo_model = None

        self.asset_delegate = AssetSelectorDelegate()
        self.float_delegate = FloatDelegate(2)
        self.percent_delegate = FloatDelegate(2, percent=True)

        self.date_label = QLabel(self)
        self.account_label = QLabel(self)
        self.type_label = QLabel(self)
        self.number_label = QLabel(self)
        self.before_label = QLabel(self)
        self.asset_label = QLabel(self)
        self.qty_label = QLabel(self)
        self.after_label = QLabel(self)
        self.comment_label = QLabel(self)
        self.arrow = QLabel(self)

        self.main_label.setText(self.tr("Corporate Action"))
        self.date_label.setText(self.tr("Date/Time"))
        self.account_label.setText(self.tr("Account"))
        self.type_label.setText(self.tr("Type"))
        self.number_label.setText(self.tr("#"))
        self.asset_label.setText(self.tr("Asset"))
        self.qty_label.setText(self.tr("Qty"))
        self.comment_label.setText(self.tr("Note"))
        self.arrow.setText(" 🡆 ")

        self.timestamp_editor = QDateTimeEdit(self)
        self.timestamp_editor.setCalendarPopup(True)
        self.timestamp_editor.setTimeSpec(Qt.UTC)
        self.timestamp_editor.setFixedWidth(self.timestamp_editor.fontMetrics().horizontalAdvance("00/00/0000 00:00:00") * 1.25)
        self.timestamp_editor.setDisplayFormat("dd/MM/yyyy hh:mm:ss")
        self.type = QComboBox(self)
        self.account_widget = AccountSelector(self)
        self.asset_widget = AssetSelector(self)
        self.qty_edit = QLineEdit(self)
        self.number = QLineEdit(self)
        self.comment = QLineEdit(self)
        self.add_button = QPushButton(load_icon("add.png"), '', self)
        self.add_button.setToolTip(self.tr("Add asset"))
        self.del_button = QPushButton(load_icon("remove.png"), '', self)
        self.del_button.setToolTip(self.tr("Remove asset"))
        self.results_table = QTableView(self)
        self.results_table.horizontalHeader().setFont(self.bold_font)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.verticalHeader().setMinimumSectionSize(20)
        self.results_table.verticalHeader().setDefaultSectionSize(20)

        self.layout.addWidget(self.date_label, 1, 0, 1, 1, Qt.AlignLeft)
        self.layout.addWidget(self.type_label, 2, 0, 1, 1, Qt.AlignLeft)
        self.layout.addWidget(self.number_label, 3, 0, 1, 1, Qt.AlignRight)
        self.layout.addWidget(self.comment_label, 4, 0, 1, 6, Qt.AlignLeft)

        self.layout.addWidget(self.timestamp_editor, 1, 1, 1, 1)
        self.layout.addWidget(self.type, 2, 1, 1, 1)
        self.layout.addWidget(self.number, 3, 1, 1, 1)
        self.layout.addWidget(self.comment, 4, 1, 1, 3)

        self.layout.addWidget(self.account_label, 1, 2, 1, 1, Qt.AlignRight)
        self.layout.addWidget(self.asset_label, 2, 2, 1, 1, Qt.AlignRight)
        self.layout.addWidget(self.qty_label, 3, 2, 1, 1, Qt.AlignRight)

        self.layout.addWidget(self.account_widget, 1, 3, 1, 1)
        self.layout.addWidget(self.asset_widget, 2, 3, 1, 1)
        self.layout.addWidget(self.qty_edit, 3, 3, 1, 1)

        self.layout.addWidget(self.arrow, 2, 4, 2, 1)
        self.layout.addWidget(self.results_table, 2, 5, 3, 4)

        self.layout.addWidget(self.commit_button, 0, 7, 1, 1)
        self.layout.addWidget(self.revert_button, 0, 8, 1, 1)
        self.layout.addWidget(self.add_button, 1, 7, 1, 1)
        self.layout.addWidget(self.del_button, 1, 8, 1, 1)

        self.layout.addItem(self.verticalSpacer, 7, 5, 1, 1)
        self.layout.addItem(self.horizontalSpacer, 1, 6, 1, 1)

        self.add_button.clicked.connect(self.addResult)
        self.del_button.clicked.connect(self.delResult)

        super()._init_db("asset_actions")
        self.combo_model = QStringListModel([self.tr("N/A"),
                                             self.tr("Merger"),
                                             self.tr("Spin-Off"),
                                             self.tr("Symbol change"),
                                             self.tr("Split"),
                                             self.tr("Delisting")])
        self.type.setModel(self.combo_model)

        self.mapper.setItemDelegate(CorporateActionWidgetDelegate(self.mapper))

        self.results_model = ResultsModel(self.results_table, db_connection())
        self.results_model.setTable("action_results")
        self.results_model.setEditStrategy(QSqlTableModel.OnManualSubmit)
        self.results_table.setModel(self.results_model)
        self.results_model.dataChanged.connect(self.onDataChange)

        self.account_widget.changed.connect(self.mapper.submit)
        self.asset_widget.changed.connect(self.mapper.submit)

        self.mapper.addMapping(self.timestamp_editor, self.model.fieldIndex("timestamp"))
        self.mapper.addMapping(self.account_widget, self.model.fieldIndex("account_id"))
        self.mapper.addMapping(self.asset_widget, self.model.fieldIndex("asset_id"))
        self.mapper.addMapping(self.number, self.model.fieldIndex("number"))
        self.mapper.addMapping(self.qty_edit, self.model.fieldIndex("qty"))
        self.mapper.addMapping(self.comment, self.model.fieldIndex("note"))
        self.mapper.addMapping(self.type, self.model.fieldIndex("type"), QByteArray().setRawData("currentIndex", 12))

        self.results_table.setItemDelegateForColumn(2, self.asset_delegate)
        self.results_table.setItemDelegateForColumn(3, self.float_delegate)
        self.results_table.setItemDelegateForColumn(4, self.percent_delegate)

        self.model.select()
        self.results_model.select()
        self.results_model.configureView()

    def setId(self, id):
        super().setId(id)
        self.results_model.setFilter(f"action_results.action_id = {id}")

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
        selection = self.results_table.selectionModel().selection().indexes()
        for idx in selection:
            self.results_model.removeRow(idx.row())
            self.onDataChange(idx, idx, None)

    @Slot()
    def saveChanges(self):
        if not self.model.submitAll():
            logging.fatal(self.tr("Operation submit failed: ") + self.model.lastError().text())
            return
        oid = self.model.data(self.model.index(0, self.model.fieldIndex("id")))
        if oid is None:  # we just have saved new action record and need last inserted id
            oid = self.model.query().lastInsertId()
        for row in range(self.results_model.rowCount()):
            self.results_model.setData(self.results_model.index(row, self.results_model.fieldIndex("action_id")), oid)
        if not self.results_model.submitAll():
            logging.fatal(self.tr("Operation details submit failed: ") + self.results_model.lastError().text())
            return
        self.modified = False
        self.commit_button.setEnabled(False)
        self.revert_button.setEnabled(False)
        self.dbUpdated.emit()

    @Slot()
    def revertChanges(self):
        self.model.revertAll()
        self.results_model.revertAll()
        self.modified = False
        self.commit_button.setEnabled(False)
        self.revert_button.setEnabled(False)

    def createNew(self, account_id=0):
        super().createNew(account_id)
        self.results_model.setFilter(f"action_results.action_id = 0")

    def prepareNew(self, account_id):
        new_record = super().prepareNew(account_id)
        new_record.setValue("timestamp", int(datetime.now().replace(tzinfo=tz.tzutc()).timestamp()))
        new_record.setValue("number", '')
        new_record.setValue("account_id", account_id)
        new_record.setValue("type", 0)
        new_record.setValue("asset_id", 0)
        new_record.setValue("qty", 0)
        new_record.setValue("note", None)
        return new_record

    def copyNew(self):
        old_id = self.model.record(self.mapper.currentIndex()).value(0)
        super().copyNew()
        self.results_model.setFilter(f"action_results.action_id = 0")
        query = executeSQL("SELECT * FROM action_results WHERE action_id = :oid ORDER BY id DESC", [(":oid", old_id)])
        while query.next():
            new_record = query.record()
            new_record.setNull("id")
            new_record.setNull("action_id")
            assert self.results_model.insertRows(0, 1)
            self.results_model.setRecord(0, new_record)

    def copyToNew(self, row):
        new_record = self.model.record(row)
        new_record.setNull("id")
        new_record.setValue("timestamp", int(datetime.now().replace(tzinfo=tz.tzutc()).timestamp()))
        new_record.setValue("number", '')
        return new_record


# FIXME - class ResultsModel has common elements with DetailsModel class of income_spending_widget.py
# Probably both should have common ancestor
class ResultsModel(QSqlTableModel):
    def __init__(self, parent_view, db):
        super().__init__(parent=parent_view, db=db)
        self._columns = ["id", "action_id", self.tr("Asset"), self.tr("Qty"), self.tr("Share, %")]
        self.deleted = []   # FIXME - this list isn't properly cleaned after deletion and change of an operation
        self._view = parent_view

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._columns[section]
        return None

    def removeRow(self, row, parent=None):
        self.deleted.append(row)
        super().removeRow(row)

    def submitAll(self):
        result = super().submitAll()
        if result:
            self.deleted = []
        return result

    def revertAll(self):
        self.deleted = []
        super().revertAll()

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.FontRole and (index.row() in self.deleted):
            font = QFont()
            font.setStrikeOut(True)
            return font
        return super().data(index, role)

    def configureView(self):
        self._view.setColumnHidden(0, True)
        self._view.setColumnHidden(1, True)
        self._view.setColumnWidth(3, 100)
        self._view.setColumnWidth(4, 100)
        self._view.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
