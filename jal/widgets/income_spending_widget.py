import logging
from datetime import datetime
from dateutil import tz

from PySide2.QtCore import Qt, Slot
from PySide2.QtWidgets import QLabel, QDateTimeEdit, QPushButton, QTableView, QHeaderView
from PySide2.QtSql import QSqlTableModel
from jal.widgets.helpers import g_tr
from jal.widgets.abstract_operation_details import AbstractOperationDetails
from jal.widgets.reference_selector import AccountSelector, PeerSelector
from jal.widgets.account_select import OptionalCurrencyComboBox
from jal.db.helpers import db_connection, executeSQL
from jal.widgets.delegates import WidgetMapperDelegateBase, FloatDelegate, CategorySelectorDelegate, TagSelectorDelegate


# ----------------------------------------------------------------------------------------------------------------------
class IncomeSpendingWidgetDelegate(WidgetMapperDelegateBase):
    def __init__(self, parent=None):
        WidgetMapperDelegateBase.__init__(self, parent)
        self.delegates = {1: self.timestamp_delegate}


# ----------------------------------------------------------------------------------------------------------------------
class IncomeSpendingWidget(AbstractOperationDetails):
    def __init__(self, parent=None):
        AbstractOperationDetails.__init__(self, parent)
        self.name = "Income/Spending"

        self.details_model = None
        self.category_delegate = CategorySelectorDelegate()
        self.tag_delegate = TagSelectorDelegate()
        self.float_delegate = FloatDelegate(2)

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
        self.a_currency = OptionalCurrencyComboBox(self)
        self.a_currency.setText(g_tr("IncomeSpendingWidget", "Paid in foreign currency:"))
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

        self.layout.addWidget(self.a_currency, 1, 7, 1, 1)

        self.layout.addWidget(self.commit_button, 0, 9, 1, 1)
        self.layout.addWidget(self.revert_button, 0, 10, 1, 1)

        self.layout.addWidget(self.details_table, 4, 0, 1, 11)
        self.layout.addItem(self.horizontalSpacer, 1, 8, 1, 1)

        self.add_button.clicked.connect(self.addChild)
        self.del_button.clicked.connect(self.delChild)

        super()._init_db("actions")
        self.mapper.setItemDelegate(IncomeSpendingWidgetDelegate(self.mapper))

        self.details_model = DetailsModel(self.details_table, db_connection())
        self.details_model.setTable("action_details")
        self.details_model.setEditStrategy(QSqlTableModel.OnManualSubmit)
        self.details_table.setModel(self.details_model)
        self.details_model.dataChanged.connect(self.onDataChange)

        self.account_widget.changed.connect(self.mapper.submit)
        self.peer_widget.changed.connect(self.mapper.submit)
        self.a_currency.changed.connect(self.mapper.submit)
        self.a_currency.updated.connect(self.details_model.setAltCurrency)

        self.mapper.addMapping(self.timestamp_editor, self.model.fieldIndex("timestamp"))
        self.mapper.addMapping(self.account_widget, self.model.fieldIndex("account_id"))
        self.mapper.addMapping(self.peer_widget, self.model.fieldIndex("peer_id"))
        self.mapper.addMapping(self.a_currency, self.model.fieldIndex("alt_currency_id"))

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
        new_record.setNull("tag_id")
        new_record.setValue("amount", 0)
        new_record.setValue("amount_alt", 0)
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
        if pid is None:  # we just have saved new action record and need last inserted id
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
        query = executeSQL("SELECT * FROM action_details WHERE pid = :pid ORDER BY id DESC",
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


class DetailsModel(QSqlTableModel):
    def __init__(self, parent_view, db):
        self._columns = ["id",
                         "pid",
                         g_tr('DetailsModel', "Category"),
                         g_tr('DetailsModel', "Tag"),
                         g_tr('DetailsModel', "Amount"),
                         g_tr('DetailsModel', "Amount"),
                         g_tr('DetailsModel', "Note")]
        super().__init__(parent=parent_view, db=db)
        self.alt_currency = ''
        self._view = parent_view

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if section == 5:
                return self._columns[section] + ', ' + self.alt_currency
            else:
                return self._columns[section]
        return None

    def configureView(self):
        self._view.setColumnHidden(0, True)
        self._view.setColumnHidden(1, True)
        self._view.setColumnHidden(5, True)
        self._view.setColumnWidth(2, 200)
        self._view.setColumnWidth(3, 200)
        self._view.setColumnWidth(4, 100)
        self._view.setColumnWidth(5, 100)
        self._view.horizontalHeader().setSectionResizeMode(6, QHeaderView.Stretch)
        self._view.horizontalHeader().moveSection(6, 0)

    def setAltCurrency(self, currency):
        if currency:
            self._view.setColumnHidden(5, False)
            self.alt_currency = currency
            self.headerDataChanged.emit(Qt.Horizontal, 5, 5)
        else:
            self._view.setColumnHidden(5, True)
