from functools import partial

from PySide6.QtCore import Qt, Signal, Property, Slot
from PySide6.QtWidgets import QDialog, QMessageBox, QMenu, QWidgetAction, QLabel

from jal.ui.ui_reference_data_dlg import Ui_ReferenceDataDialog
from jal.db.helpers import load_icon


# --------------------------------------------------------------------------------------------------------------
# Class to display and edit table with reference data (accounts, categories, tags...)
# --------------------------------------------------------------------------------------------------------------
class ReferenceDataDialog(QDialog, Ui_ReferenceDataDialog):
    # tree_view - table will be displayed as hierarchical tree with help of 2 columns: 'id', 'pid' in sql table
    def __init__(self):
        QDialog.__init__(self)
        self.setupUi(self)

        self.model = None
        self._previous_row = -1
        self.selected_id = 0
        self.p_selected_name = ''
        self._filter_text = ''
        self.selection_enabled = False
        self.group_id = None
        self.group_key_field = None
        self.group_key_index = None
        self.group_fkey_field = None
        self.filter_field = None
        self._filter_value = ''
        self.toggle_state = False
        self.toggle_field = None
        self.search_field = None
        self.search_text = ""
        self.tree_view = False
        self.toolbar = None
        self.custom_editor = False

        self.AddChildBtn.setVisible(False)
        self.GroupLbl.setVisible(False)
        self.GroupCombo.setVisible(False)
        self.SearchFrame.setVisible(False)

        self.AddBtn.setIcon(load_icon("add.png"))
        self.AddChildBtn.setIcon(load_icon("add_child.png"))
        self.RemoveBtn.setIcon(load_icon("delete.png"))
        self.CommitBtn.setIcon(load_icon("accept.png"))
        self.RevertBtn.setIcon(load_icon("cancel.png"))

        self.SearchString.textChanged.connect(self.OnSearchChange)
        self.GroupCombo.currentIndexChanged.connect(self.OnGroupChange)
        self.Toggle.stateChanged.connect(self.OnToggleChange)
        self.AddBtn.clicked.connect(self.OnAdd)
        self.AddChildBtn.clicked.connect(self.OnChildAdd)
        self.RemoveBtn.clicked.connect(self.OnRemove)
        self.CommitBtn.clicked.connect(self.OnCommit)
        self.RevertBtn.clicked.connect(self.OnRevert)
        self.DataView.doubleClicked.connect(self.OnDoubleClicked)
        self.DataView.clicked.connect(self.OnClicked)
        self.TreeView.doubleClicked.connect(self.OnDoubleClicked)
        self.TreeView.clicked.connect(self.OnClicked)

    def _init_completed(self):
        self.DataView.setVisible(not self.tree_view)
        self.TreeView.setVisible(self.tree_view)
        if self.tree_view:
            self.TreeView.selectionModel().selectionChanged.connect(self.OnRowSelected)
        else:
            self.DataView.selectionModel().selectionChanged.connect(self.OnRowSelected)
            self.DataView.setContextMenuPolicy(Qt.CustomContextMenu)
            self.DataView.customContextMenuRequested.connect(self.onDataViewContextMenu)
        self.model.dataChanged.connect(self.OnDataChanged)
        self.setFilter()

    def onDataViewContextMenu(self, pos):
        if not self.group_id:
            return
        index = self.DataView.indexAt(pos)
        menu_title = QWidgetAction(self.DataView)
        title_lbl = QLabel()
        title_lbl.setText(self.tr("Change type to:"))
        menu_title.setDefaultWidget(title_lbl)
        contextMenu = QMenu(self.DataView)
        contextMenu.addAction(menu_title)
        contextMenu.addSeparator()
        combo_model = self.GroupCombo.model()
        for i in range(self.GroupCombo.count()):
            type_id = combo_model.data(combo_model.index(i, combo_model.fieldIndex(self.group_fkey_field)))
            contextMenu.addAction(self.GroupCombo.itemText(i), partial(self.updateItemType, index, type_id))
        contextMenu.popup(self.DataView.viewport().mapToGlobal(pos))

    @Slot()
    def updateItemType(self, index, new_type):
        self.model.updateItemType(index, new_type)
        self.CommitBtn.setEnabled(True)
        self.RevertBtn.setEnabled(True)

    @Slot()
    def closeEvent(self, event):
        if self.CommitBtn.isEnabled():    # There are uncommitted changed in a table
            if QMessageBox().warning(self, self.tr("Confirmation"),
                                     self.tr("You have uncommitted changes. Do you want to close?"),
                                     QMessageBox.Yes, QMessageBox.No) == QMessageBox.No:
                event.ignore()
                return
            else:
                self.model.revertAll()
        event.accept()

    # Overload ancestor method to activate/deactivate filters for table view
    def exec(self, enable_selection=False, selected=0):
        self.selection_enabled = enable_selection
        self.setFilter()
        if enable_selection:
            self.locateItem(selected)
        res = super().exec()
        self.resetFilter()
        return res

    def getSelectedName(self):
        if self.selected_id == 0:
            return self.tr("ANY")
        else:
            return self.p_selected_name

    def setSelectedName(self, selected_id):
        pass

    @Signal
    def selected_name_changed(self):
        pass

    SelectedName = Property(str, getSelectedName, setSelectedName, notify=selected_name_changed)

    @Slot()
    def OnDataChanged(self):
        self.CommitBtn.setEnabled(True)
        self.RevertBtn.setEnabled(True)

    @Slot()
    def OnAdd(self):
        if self.custom_editor:
            editor = self.customEditor()
            editor.createNewRecord()
            editor.exec()
            self.model.select()   # TODO better to make self.beginInsertRows/endInsertRows
        else:
            if self.tree_view:
                idx = self.TreeView.selectionModel().selection().indexes()
            else:
                idx = self.DataView.selectionModel().selection().indexes()
            current_index = idx[0] if idx else self.model.index(0, 0)
            self.model.addElement(current_index, in_group=self.group_id)
            self.CommitBtn.setEnabled(True)
            self.RevertBtn.setEnabled(True)

    @Slot()
    def OnChildAdd(self):
        if self.tree_view:
            idx = self.TreeView.selectionModel().selection().indexes()
            current_index = idx[0] if idx else self.model.index(0, 0)
            self.model.addChildElement(current_index)
            self.CommitBtn.setEnabled(True)
            self.RevertBtn.setEnabled(True)

    @Slot()
    def OnRemove(self):
        if self.tree_view:
            idx = self.TreeView.selectionModel().selection().indexes()
        else:
            idx = self.DataView.selectionModel().selection().indexes()
        current_index = idx[0] if idx else self.model.index(0, 0)
        self.model.removeElement(current_index)
        self.CommitBtn.setEnabled(True)
        self.RevertBtn.setEnabled(True)

    @Slot()
    def OnCommit(self):
        if not self.model.submitAll():
            return
        self.CommitBtn.setEnabled(False)
        self.RevertBtn.setEnabled(False)

    @Slot()
    def OnRevert(self):
        self.model.revertAll()
        self.CommitBtn.setEnabled(False)
        self.RevertBtn.setEnabled(False)

    def setFilterValue(self, filter_value):
        if self.filter_field is None:
            return
        self._filter_value = filter_value
        self.setFilter()

    def resetFilter(self):
        self.model.setFilter("")

    def setFilter(self):
        conditions = []
        if self.search_text and self.search_field is not None:
            search = self.search_field.split('-')
            if len(search) == 1:    # Simple search by given text field
                conditions.append(f"{self.search_field} LIKE '%{self.search_text}%'")
            elif len(search) == 4:  # Complex search by relation from another table
                # Here search[0] is a field in current table that binds with search[2] field in lookup table search[1]
                # search[3] is a name in lookup table which is used for searching.
                # I.e. self.search_field has format: f_key-lookup_table_name-lookup_id-lookup_field
                conditions.append(f"{search[0]} IN (SELECT {search[2]} FROM {search[1]} "
                                  f"WHERE {search[3]} LIKE '%{self.search_text}%')")
            else:
                assert False, f"Unsupported format of search field: {self.search_field}"

        if self.group_id:
            conditions.append(f"{self.table}.{self.group_key_field}={self.group_id}")

        if self.filter_field is not None and self._filter_value:
            conditions.append(f"{self.table}.{self.filter_field} = {self._filter_value}")
            # completion model needs only this filter, others are for dialog
            self.model.completion_model.setFilter(f"{self.table}.{self.filter_field} = {self._filter_value}")

        if self.toggle_field:
            if not self.toggle_state:
                conditions.append(f"{self.table}.{self.toggle_field}=1")

        self._filter_text = ""
        for line in conditions:
            self._filter_text += line + " AND "
        self._filter_text = self._filter_text[:-len(" AND ")]

        self.model.setFilter(self._filter_text)

    @Slot()
    def OnSearchChange(self):
        self.search_text = self.SearchString.text()
        self.setFilter()

    @Slot()
    def OnRowSelected(self, selected, _deselected):
        idx = selected.indexes()
        if idx:
            self.selected_id = self.model.getId(idx[0])
            self.p_selected_name = self.model.getName(idx[0])

    @Slot()
    def OnClicked(self, index):
        if self.custom_editor:
            if self._previous_row == index.row():
                editor = self.customEditor()
                editor.selected_id = self.selected_id
                editor.exec()
            else:
                self._previous_row = index.row()

    @Slot()
    def OnDoubleClicked(self, index):
        self.selected_id = self.model.getId(index)
        self.p_selected_name = self.model.getName(index)
        if self.selection_enabled:
            self.setResult(QDialog.Accepted)
            self.close()

    @Slot()
    def OnGroupChange(self, list_id):
        self.OnRevert()  # Discard all possible changes

        model = self.GroupCombo.model()
        self.group_id = model.data(model.index(list_id, model.fieldIndex(self.group_fkey_field)))
        self.setFilter()

    @Slot()
    def OnToggleChange(self, state):
        if state == 0:
            self.toggle_state = False
        else:
            self.toggle_state = True
        self.setFilter()

    def locateItem(self, item_id):
        raise NotImplementedError("locateItem() method is not defined in subclass ReferenceDataDialog")
