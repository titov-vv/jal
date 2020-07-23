import logging

from PySide2.QtCore import Qt, Signal, Property, Slot, QModelIndex
from PySide2.QtSql import QSqlTableModel
from PySide2.QtWidgets import QDialog

from UI.ui_reference_data_dlg import Ui_ReferenceDataDialog
from CustomUI.helpers import UseSqlTable, ConfigureTableView

# --------------------------------------------------------------------------------------------------------------
# Class to display and edit table with reference data (accounts, categories, tags...)
# --------------------------------------------------------------------------------------------------------------
class ReferenceDataDialog(QDialog, Ui_ReferenceDataDialog):
    def __init__(self, db, table, columns, title='', search_field=None):
        QDialog.__init__(self)
        self.setupUi(self)

        self.selected_id = 0
        self.search_text = ""
        self.search_field = search_field

        self.db = db
        self.Model = UseSqlTable(self.db, table, columns)
        ConfigureTableView(self.DataView, self.Model, columns)

        self.setWindowTitle(title)
        if self.search_field is not None:
            self.SearchFrame.setVisible(True)
        else:
            self.SearchFrame.setVisible(False)

        self.SearchString.textChanged.connect(self.OnSearchChange)
        self.AddBtn.clicked.connect(self.OnAdd)
        self.RemoveBtn.clicked.connect(self.OnRemove)
        self.CommitBtn.clicked.connect(self.OnCommit)
        self.RevertBtn.clicked.connect(self.OnRevert)
        self.DataView.selectionModel().selectionChanged.connect(self.OnRowSelected)
        self.Model.dataChanged.connect(self.OnDataChanged)

        self.Model.select()

    @Slot()
    def OnDataChanged(self):
        self.CommitBtn.setEnabled(True)
        self.RevertBtn.setEnabled(True)

    @Slot()
    def OnAdd(self):
        assert self.Model.insertRows(0, 1)
        self.CommitBtn.setEnabled(True)
        self.RevertBtn.setEnabled(True)

    @Slot()
    def OnRemove(self):
        idx = self.TagsList.selectionModel().selection().indexes()
        selected_row = idx[0].row()
        assert self.Model.removeRow(selected_row)
        self.CommitBtn.setEnabled(True)
        self.RevertBtn.setEnabled(True)

    @Slot()
    def OnCommit(self):
        if not self.Model.submitAll():
            logging.fatal(self.tr("Action submit failed: ") + self.Model.lastError().text())
            return
        self.CommitBtn.setEnabled(False)
        self.RevertBtn.setEnabled(False)

    @Slot()
    def OnRevert(self):
        self.Model.revertAll()
        self.CommitBtn.setEnabled(False)
        self.RevertBtn.setEnabled(False)

    def setFilter(self):
        if self.search_text:
            self.DataView.model().setFilter(f"{self.search_field} LIKE '%{self.search_text}%'")
        else:
            self.DataView.model().setFilter("")

    @Slot()
    def OnSearchChange(self):
        self.search_text = self.SearchString.text()
        self.setFilter()

    @Slot()
    def OnRowSelected(self, selected, _deselected):
        idx = selected.indexes()
        if idx:
            selected_row = idx[0].row()
            self.selected_id = self.DataView.model().record(selected_row).value(0)