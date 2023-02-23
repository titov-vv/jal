from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHeaderView
from PySide6.QtGui import QFont
from jal.db.db import JalModel


class JalViewModel(JalModel):
    def __init__(self, parent_view, table_name):
        super().__init__(parent_view, table_name)
        self._columns = []
        self.deleted = []
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
