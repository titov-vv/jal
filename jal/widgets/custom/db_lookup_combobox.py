from PySide6.QtCore import Qt, Property, QSize
from PySide6.QtWidgets import QComboBox
from jal.constants import IconOwner
from jal.db.asset import JalAsset
from jal.db.db import JalModel
from jal.db.icon import JalIcons


# ----------------------------------------------------------------------------------------------------------------------
# What a row of a looked-up table is a picture of. Only the tables whose rows have icons are listed here; anything
# else is text alone, and a table that gains icons later (agents, when peers get them) is one branch more.
# Mind what the key of each table means: 'currencies' is a view over ASSETS, while an icon belongs to a listing of
# an asset - the same narrowing every other place makes (see JalAsset.listing_id).
def lookup_row_icon(table: str, row_id):
    if not row_id:
        return None
    if table == "currencies":
        return JalIcons.decoration(IconOwner.Symbol, JalAsset(int(row_id)).listing_id(), JalIcons.grid_size())
    return None


# ----------------------------------------------------------------------------------------------------------------------
# The model behind the combo box below: a plain table model that also answers with the icon of the element each row
# stands for, which is all a QComboBox needs to draw it - in the closed box and in the popup alike.
class LookupModel(JalModel):
    def __init__(self, parent, table_name, key_field):
        super().__init__(parent, table_name)
        self._key_field = key_field

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DecorationRole and index.isValid() and self._key_field:
            return lookup_row_icon(self._table, self.record(index.row()).value(self._key_field))
        return super().data(index, role)


# Combobox to lookup in db tables:
# It is mandatory to set up 'table', 'key_field' and 'field' properties at design time
class DbLookupComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._model = None
        self._table = ''
        self._key_field = ''
        self._field = ''
        self._selected_id = -1

    def getKey(self):
        if self._model is None:
            return 0
        # Nothing is selected, or what is shown has no row of its own in the looked-up table - the 'key' property
        # is an int and has to answer with one either way
        return self._model.get_value(self._key_field, self._field, self.currentText()) or 0

    def setKey(self, selected_id):
        if self._selected_id == selected_id:
            return
        self._selected_id = selected_id
        value = self._model.get_value(self._field, self._key_field, selected_id)
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
        self.setupDb()   # the model needs the key to know which element each row is, and so which icon it wears

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
        self._model = LookupModel(self, self._table, self._key_field)
        field_idx = self._model.fieldIndex(self._field)
        self._model.setSort(field_idx, Qt.AscendingOrder)
        self._model.select()
        self.setModel(self._model)
        self.setModelColumn(field_idx)
        # A combo box that was never told an icon size clamps every icon to the style's 16 px, exactly as a view
        # does - and this is the same size a grid paints an icon at, so a row of the popup keeps its height.
        self.setIconSize(QSize(JalIcons.grid_size(), JalIcons.grid_size()))
