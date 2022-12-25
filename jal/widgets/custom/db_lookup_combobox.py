from PySide6.QtCore import Qt, Property
from PySide6.QtSql import QSqlTableModel
from PySide6.QtWidgets import QComboBox
from jal.db.db import JalDB


# Combobox to lookup in db tables:
# It is mandatory to setup 'table', 'key_field' and 'field' properties at design time
class DbLookupComboBox(QComboBox):
    def __init__(self, parent=None):
        QComboBox.__init__(self, parent)
        self._model = None
        self._table = ''
        self._key_field = ''
        self._field = ''
        self._selected_id = -1

    def getKey(self):
        return JalDB.get_db_value(self._table, self._key_field, self._field, self.currentText())

    def setKey(self, selected_id):
        if self._selected_id == selected_id:
            return
        self._selected_id = selected_id
        value = JalDB.get_db_value(self._table, self._field, self._key_field, selected_id)
        self.setCurrentIndex(self.findText(value))

    def getTable(self):
        return self._table

    def setTable(self, table):
        if self._table == table:
            return
        self._table = table
        self.setupDb()

    def getKeyField(self):
        return self._key_field

    def setKeyField(self, field_name):
        if self._key_field == field_name:
            return
        self._key_field = field_name

    def getField(self):
        return self._field

    def setField(self, field_name):
        if self._field == field_name:
            return
        self._field = field_name
        self.setupDb()

    key = Property(int, getKey, setKey, user=True)
    db_table = Property(str, getTable, setTable)
    key_field = Property(str, getKeyField, setKeyField)
    db_field = Property(str, getField, setField)

    def setupDb(self):
        if not self._table or not self._field:
            return
        self._model = QSqlTableModel(parent=self, db=JalDB.connection())
        self._model.setTable(self._table)
        field_idx = self._model.fieldIndex(self._field)
        self._model.setSort(field_idx, Qt.AscendingOrder)
        self._model.select()
        self.setModel(self._model)
        self.setModelColumn(field_idx)
