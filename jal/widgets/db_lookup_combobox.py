from PySide6.QtCore import Qt, Property
from PySide6.QtSql import QSqlTableModel
from PySide6.QtWidgets import QComboBox
from jal.db.db import JalDB


# Base class to display lookup table as a combobox
# Shouldn't be used alone as requires setupDb() call to set table and field names
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

    key = Property(int, getKey, setKey, user=True)

    def setupDb(self, table, key_field, field):
        self._table = table
        self._field = field
        self._key_field = key_field
        self._model = QSqlTableModel(parent=self, db=JalDB.connection())
        self._model.setTable(table)
        field_idx = self._model.fieldIndex(field)
        self._model.setSort(field_idx, Qt.AscendingOrder)
        self._model.select()
        self.setModel(self._model)
        self.setModelColumn(field_idx)


# Provides country lookup combobox
# It is based on "countries" db table and uses 'id' field as a key displaying 'name' field in combo list
class CountryCombo(DbLookupComboBox):     #TODO check if currency comboboxes may be done the same way
    def __init__(self, parent=None):
        DbLookupComboBox.__init__(self, parent)
        self.setupDb("countries", "id", "name")
