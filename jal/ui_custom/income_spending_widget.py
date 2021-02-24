import logging
from datetime import datetime
from dateutil import tz

from PySide2.QtCore import Qt, Slot
from PySide2.QtWidgets import QLabel, QDateTimeEdit, QPushButton, QTableView, QLineEdit, QHeaderView
from PySide2.QtSql import QSqlTableModel, QSqlRelationalTableModel, QSqlRelation, QSqlRelationalDelegate
from jal.ui_custom.helpers import g_tr
from jal.ui_custom.abstract_operation_details import AbstractOperationDetails
from jal.ui_custom.reference_selector import AccountSelector, PeerSelector, CategorySelector, TagSelector
from jal.widgets.mapper_delegate import MapperDelegate, FloatDelegate
from jal.db.helpers import executeSQL


class IncomeSpendingWidget(AbstractOperationDetails):
    def __init__(self, parent=None):
        AbstractOperationDetails.__init__(self, parent)
        self.name = "Income/Spending"

        self.details_model = None
        self.category_delegate = CategoryDelegate()
        self.tag_delegate = TagDelegate()
        self.float_delegate = FloatDelegate()

        self.date_label = QLabel(self)
        self.details_label = QLabel(self)
        self.account_label = QLabel(self)
        self.peer_label = QLabel(self)

        self.main_label.setText(g_tr("IncomeSpendingWidget", "Income / Spending"))
        self.date_label.setText(g_tr("IncomeSpendingWidget", "Date/Time"))
        self.details_label.setText(g_tr("IncomeSpendingWidget", "Details"))
        self.account_label.setText(g_tr("IncomeSpendingWidget", "Account"))
        self.peer_label.setText(g_tr("IncomeSpendingWidget", "Peer"))

        self.timestamp_editor = QDateTimeEdit(self)
        self.timestamp_editor.setCalendarPopup(True)
        self.timestamp_editor.setTimeSpec(Qt.UTC)
        self.timestamp_editor.setFixedWidth(self.timestamp_editor.fontMetrics().width("00/00/0000 00:00:00") * 1.25)
        self.timestamp_editor.setDisplayFormat("dd/MM/yyyy hh:mm:ss")
        self.account_widget = AccountSelector(self)
        self.peer_widget = PeerSelector(self)
        self.add_button = QPushButton(self)
        self.add_button.setText(" +️ ")
        self.add_button.setFont(self.bold_font)
        self.add_button.setFixedWidth(self.add_button.fontMetrics().width("XXX"))
        self.del_button = QPushButton(self)
        self.del_button.setText(" — ️")
        self.del_button.setFont(self.bold_font)
        self.del_button.setFixedWidth(self.del_button.fontMetrics().width("XXX"))
        self.copy_button = QPushButton(self)
        self.copy_button.setText(" >> ️")
        self.copy_button.setFont(self.bold_font)
        self.copy_button.setFixedWidth(self.copy_button.fontMetrics().width("XXX"))
        self.details_table = QTableView(self)
        self.details_table.horizontalHeader().setFont(self.bold_font)
        self.details_table.setAlternatingRowColors(True)
        self.details_table.verticalHeader().setVisible(False)
        self.details_table.verticalHeader().setMinimumSectionSize(20)
        self.details_table.verticalHeader().setDefaultSectionSize(20)

        self.layout.addWidget(self.date_label, 1, 0, 1, 1, Qt.AlignLeft)
        self.layout.addWidget(self.details_label, 2, 0, 1, 1, Qt.AlignLeft)

        self.layout.addWidget(self.timestamp_editor, 1, 1, 1, 4)
        self.layout.addWidget(self.add_button, 2, 1, 1, 1)
        self.layout.addWidget(self.copy_button, 2, 2, 1, 1)
        self.layout.addWidget(self.del_button, 2, 3, 1, 1)

        self.layout.addWidget(self.account_label, 1, 5, 1, 1, Qt.AlignRight)
        self.layout.addWidget(self.peer_label, 2, 5, 1, 1, Qt.AlignRight)

        self.layout.addWidget(self.account_widget, 1, 6, 1, 1)
        self.layout.addWidget(self.peer_widget, 2, 6, 1, 1)

        self.layout.addWidget(self.commit_button, 0, 8, 1, 1)
        self.layout.addWidget(self.revert_button, 0, 9, 1, 1)

        self.layout.addWidget(self.details_table, 4, 0, 1, 10)
        self.layout.addItem(self.horizontalSpacer, 1, 7, 1, 1)

        self.add_button.clicked.connect(self.addChild)
        self.del_button.clicked.connect(self.delChild)

    def init_db(self, db):
        super().init_db(db, "actions")
        self.mapper.setItemDelegate(MapperDelegate(self.mapper))

        self.details_model = DetailsModel(self.details_table, db)
        self.details_model.setTable("action_details")
        self.details_model.setEditStrategy(QSqlTableModel.OnManualSubmit)
        self.details_model.setJoinMode(QSqlRelationalTableModel.LeftJoin)  # to work correctly with NULL values
        self.details_model.setRelation(self.details_model.fieldIndex("category_id"),
                                       QSqlRelation("categories", "id", "name"))
        self.details_model.setRelation(self.details_model.fieldIndex("tag_id"),
                                       QSqlRelation("tags", "id", "tag"))
        self.details_table.setModel(self.details_model)
        self.details_model.dataChanged.connect(self.onDataChange)

        self.account_widget.init_db(db)
        self.peer_widget.init_db(db)
        self.account_widget.changed.connect(self.mapper.submit)
        self.peer_widget.changed.connect(self.mapper.submit)

        self.mapper.addMapping(self.timestamp_editor, self.model.fieldIndex("timestamp"))
        self.mapper.addMapping(self.account_widget, self.model.fieldIndex("account_id"))
        self.mapper.addMapping(self.peer_widget, self.model.fieldIndex("peer_id"))

        self.details_table.setItemDelegateForColumn(2, self.category_delegate)
        self.details_table.setItemDelegateForColumn(3, self.tag_delegate)
        self.details_table.setItemDelegateForColumn(4, self.float_delegate)
        self.details_table.setItemDelegateForColumn(5, self.float_delegate)

        self.model.select()
        self.details_model.select()
        self.details_model.configureView()

    def setId(self, id):
        super().setId(id)
        self.details_model.setFilter(f"action_details.pid = {id}")

    @Slot()
    def addChild(self):
        new_record = self.details_model.record()
        if not self.details_model.insertRecord(-1, new_record):
            logging.fatal(
                g_tr('AbstractOperationDetails', "Failed to add new record: ") + self.details_model.lastError().text())
            return

    @Slot()
    def delChild(self):
        idx = self.details_table.selectionModel().selection().indexes()
        selected_row = idx[0].row()
        self.details_model.removeRow(selected_row)
        self.details_table.setRowHidden(selected_row, True)

    @Slot()
    def saveChanges(self):
        if not self.model.submitAll():
            logging.fatal(
                g_tr('AbstractOperationDetails', "Operation submit failed: ") + self.model.lastError().text())
            return
        pid = self.model.data(self.model.index(0, self.model.fieldIndex("id")))
        if pid is None:  # we just have saved new action record and need last insterted id
            pid = self.model.query().lastInsertId()
        for row in range(self.details_model.rowCount()):
            self.details_model.setData(self.details_model.index(row, self.details_model.fieldIndex("pid")), pid)
        if not self.details_model.submitAll():
            logging.fatal(g_tr('AbstractOperationDetails', "Operation details submit failed: ")
                          + self.details_model.lastError().text())
            return
        self.modified = False
        self.commit_button.setEnabled(False)
        self.revert_button.setEnabled(False)
        self.dbUpdated.emit()
        return

    def createNew(self, account_id=0):
        super().createNew(account_id)
        self.details_model.setFilter(f"action_details.pid = 0")

    def prepareNew(self, account_id):
        new_record = self.model.record()
        new_record.setNull("id")
        new_record.setValue("timestamp", int(datetime.now().replace(tzinfo=tz.tzutc()).timestamp()))
        new_record.setValue("account_id", account_id)
        new_record.setValue("peer_id", 0)
        new_record.setValue("alt_currency_id", None)
        return new_record

    def copyNew(self):
        old_id = self.model.record(self.mapper.currentIndex()).value(0)
        super().copyNew()
        self.details_model.setFilter(f"action_details.pid = 0")
        query = executeSQL(self._db, "SELECT * FROM action_details WHERE pid = :pid ORDER BY id DESC",
                           [(":pid", old_id)])
        while query.next():
            new_record = query.record()
            new_record.setNull("id")
            new_record.setNull("pid")
            assert self.details_model.insertRows(0, 1)
            self.details_model.setRecord(0, new_record)

    def copyToNew(self, row):
        new_record = self.model.record(row)
        new_record.setNull("id")
        new_record.setValue("timestamp", int(datetime.now().replace(tzinfo=tz.tzutc()).timestamp()))
        return new_record


class DetailsModel(QSqlRelationalTableModel):
    def __init__(self, parent_view, db):
        self._columns = ["id",
                         "pid",
                         g_tr('DetailsModel', "Category"),
                         g_tr('DetailsModel', "Tag"),
                         g_tr('DetailsModel', "Amount"),
                         g_tr('DetailsModel', "Amount *"),
                         g_tr('DetailsModel', "Note")]
        super().__init__(parent=parent_view, db=db)
        self._view = parent_view

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._columns[section]
        return None

    def configureView(self):
        self._view.setColumnHidden(0, True)
        self._view.setColumnHidden(1, True)
        self._view.setColumnWidth(2, 200)
        self._view.setColumnWidth(3, 200)
        self._view.setColumnWidth(4, 100)
        self._view.setColumnWidth(5, 100)
        self._view.horizontalHeader().setSectionResizeMode(6, QHeaderView.Stretch)
        self._view.horizontalHeader().moveSection(6, 0)

# -----------------------------------------------------------------------------------------------------------------------
# Delegate to display category editor
class CategoryDelegate(QSqlRelationalDelegate):
    def __init__(self, parent=None):
        QSqlRelationalDelegate.__init__(self, parent)

    def createEditor(self, aParent, option, index):
        category_selector = CategorySelector(aParent)
        category_selector.init_db(index.model().database())
        return category_selector

    def setModelData(self, editor, model, index):
        model.setData(index, editor.selected_id)

# -----------------------------------------------------------------------------------------------------------------------
# Delegate to display tag editor
class TagDelegate(QSqlRelationalDelegate):
    def __init__(self, parent=None):
        QSqlRelationalDelegate.__init__(self, parent)

    def createEditor(self, aParent, option, index):
        tag_selector = TagSelector(aParent)
        tag_selector.init_db(index.model().database())
        return tag_selector

    def setModelData(self, editor, model, index):
        model.setData(index, editor.selected_id)
