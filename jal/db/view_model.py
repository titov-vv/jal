from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from jal.db.db import JalModel


class JalViewModel(JalModel):
    def __init__(self, parent_view, table_name):
        super().__init__(parent_view, table_name)
        self._key_field = 'id'  # this is assumed to be an auto-increment field that us used to track rows existence
        self._columns = []
        self.deleted = []
        self._view = parent_view

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._columns[section]
        return None

    def footerData(self, section, role=Qt.DisplayRole):
        return None

    def removeRow(self, row, parent=None):
        if self.record(row).value(self._key_field):  # New rows have 0 in index key field - we may not track this rows
            self.deleted.append(row)                 # as Qt will remove them completely on its own
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

    def row_is_deleted(self, row):
        if row in self.deleted:
            return True
        else:
            return False
