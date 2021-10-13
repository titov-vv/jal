import logging
from PySide6.QtCore import Qt, Slot, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QWidget, QGridLayout, QLabel, QPushButton, QSpacerItem, QSizePolicy, QDataWidgetMapper
from PySide6.QtSql import QSqlTableModel
from jal.db.helpers import db_connection, load_icon


class AbstractOperationDetails(QWidget):
    dbUpdated = Signal()

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.model = None
        self.table_name = ''
        self.mapper = None
        self.modified = False
        self.name = "N/A"

        self.layout = QGridLayout(self)
        self.layout.setContentsMargins(2, 2, 2, 2)

        self.bold_font = QFont()
        self.bold_font.setBold(True)

        self.main_label = QLabel(self)
        self.main_label.setFont(self.bold_font)
        self.layout.addWidget(self.main_label, 0, 0, 1, 1, Qt.AlignLeft)

        self.commit_button = QPushButton(load_icon("accept.png"), '', self)
        self.commit_button.setToolTip(self.tr("Commit changes"))
        self.commit_button.setEnabled(False)
        self.revert_button = QPushButton(load_icon("cancel.png"), '', self)
        self.revert_button.setToolTip(self.tr("Cancel changes"))
        self.revert_button.setEnabled(False)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

    def _init_db(self, table_name):
        self.table_name = table_name
        self.model = QSqlTableModel(parent=self, db=db_connection())
        self.model.setTable(table_name)
        self.model.setEditStrategy(QSqlTableModel.OnManualSubmit)

        self.mapper = QDataWidgetMapper(self.model)
        self.mapper.setModel(self.model)
        self.mapper.setSubmitPolicy(QDataWidgetMapper.AutoSubmit)

        self.model.dataChanged.connect(self.onDataChange)
        self.commit_button.clicked.connect(self.saveChanges)
        self.revert_button.clicked.connect(self.revertChanges)

    def isCustom(self):
        return True

    def setId(self, id):
        self.model.setFilter(f"id={id}")
        self.mapper.setCurrentModelIndex(self.model.index(0, 0))

    @Slot()
    def onDataChange(self, _index_start, _index_stop, _role):
        self.modified = True
        self.commit_button.setEnabled(True)
        self.revert_button.setEnabled(True)

    @Slot()
    def saveChanges(self):
        if not self.model.submitAll():
            logging.fatal(self.tr("Operation submit failed: ") + self.model.lastError().text())
            return False
        self.modified = False
        self.commit_button.setEnabled(False)
        self.revert_button.setEnabled(False)
        self.dbUpdated.emit()

    @Slot()
    def revertChanges(self):
        self.model.revertAll()
        self.modified = False
        self.commit_button.setEnabled(False)
        self.revert_button.setEnabled(False)

    def createNew(self, account_id=0):
        if self.modified:
            self.revertChanges()
            logging.warning(self.tr("Unsaved changes were reverted to create new operation"))
        self.model.setFilter(f"{self.table_name}.id = 0")
        new_record = self.prepareNew(account_id)
        assert self.model.insertRows(0, 1)
        self.model.setRecord(0, new_record)
        self.mapper.toLast()

    def prepareNew(self, account_id):
        new_record = self.model.record()
        return new_record

    def copyNew(self):
        row = self.mapper.currentIndex()
        new_record = self.copyToNew(row)
        self.model.setFilter(f"{self.table_name}.id = 0")
        assert self.model.insertRows(0, 1)
        self.model.setRecord(0, new_record)
        self.mapper.toLast()

    def copyToNew(self, row):
        new_record = self.model.record(row)
        return new_record

