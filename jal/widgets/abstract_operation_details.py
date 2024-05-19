import logging
from PySide6.QtCore import Slot, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QWidget, QDataWidgetMapper
from PySide6.QtSql import QSqlTableModel
from jal.db.db import JalModel
from jal.widgets.icons import JalIcon


class AbstractOperationDetails(QWidget):
    dbUpdated = Signal()

    # ui_class should be a widget class generated by Qt-designer.
    # This widget should have QLabel main_label, and 2 QPushButtons: commit_button and revert_button
    def __init__(self, parent=None, ui_class=None):
        super().__init__(parent)
        assert ui_class is not None, "Can't create operation class without UI provided"
        self.ui = ui_class()
        self.ui.setupUi(self)

        self.model = None
        self.table_name = ''
        self.mapper = None
        self.modified = False
        self.name = self.name = self.ui.main_label.text()
        self.operation_type = None

        self.bold_font = QFont()
        self.bold_font.setBold(True)

        self.ui.commit_button.setIcon(JalIcon[JalIcon.OK])
        self.ui.revert_button.setIcon(JalIcon[JalIcon.CANCEL])

    def _init_db(self, table_name):
        self.table_name = table_name
        self.model = JalModel(self, table_name)
        self.model.setEditStrategy(QSqlTableModel.OnManualSubmit)

        self.mapper = QDataWidgetMapper(self.model)
        self.mapper.setModel(self.model)
        self.mapper.setSubmitPolicy(QDataWidgetMapper.AutoSubmit)

        self.model.dataChanged.connect(self.onDataChange)
        self.ui.commit_button.clicked.connect(self.saveChanges)
        self.ui.revert_button.clicked.connect(self.revertChanges)

    def set_id(self, oid):
        self.model.setFilter(f"oid={oid}")
        self.mapper.setCurrentModelIndex(self.model.index(0, 0))

    @Slot()
    def onDataChange(self, _index_start, _index_stop, _role):
        self.modified = True
        self.ui.commit_button.setEnabled(True)
        self.ui.revert_button.setEnabled(True)

    @Slot()
    def saveChanges(self):
        if self._validated():
            self._save()

    def _validated(self):   # May be used in descendant classes
        return True

    def _save(self):
        if not self.model.submitAll():
            logging.fatal(self.tr("Operation submit failed: ") + self.model.lastError().text())
            return False
        self.modified = False
        self.ui.commit_button.setEnabled(False)
        self.ui.revert_button.setEnabled(False)
        self.dbUpdated.emit()

    @Slot()
    def revertChanges(self):
        self.model.revertAll()
        self.modified = False
        self.ui.commit_button.setEnabled(False)
        self.ui.revert_button.setEnabled(False)

    def createNew(self, account_id=0):
        if self.modified:
            self.revertChanges()
            logging.warning(self.tr("Unsaved changes were reverted to create new operation"))
        self.model.setFilter(f"{self.table_name}.oid = 0")
        new_record = self.prepareNew(account_id)
        assert self.model.insertRows(0, 1)
        self.model.setRecord(0, new_record)
        self.mapper.toLast()

    def prepareNew(self, account_id):
        new_record = self.model.record()
        new_record.setNull("oid")
        new_record.setValue("otype", self.operation_type)
        return new_record

    def copyNew(self):
        row = self.mapper.currentIndex()
        new_record = self.copyToNew(row)
        self.model.setFilter(f"{self.table_name}.oid = 0")
        assert self.model.insertRows(0, 1)
        self.model.setRecord(0, new_record)
        self.mapper.toLast()

    def copyToNew(self, row):
        new_record = self.model.record(row)
        return new_record

