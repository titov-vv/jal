from functools import partial

from PySide6.QtCore import Qt, Signal, Property, Slot
from PySide6.QtWidgets import QDialog, QMessageBox, QMenu, QWidgetAction, QLabel

from jal.ui.ui_reference_data_dlg import Ui_ReferenceDataDialog
from jal.db.helpers import load_icon


# --------------------------------------------------------------------------------------------------------------
# Class to display and edit table with reference data (accounts, categories, tags...)
# --------------------------------------------------------------------------------------------------------------
class ReferenceDataDialog(QDialog):
    # tree_view - table will be displayed as hierarchical tree with help of 2 columns: 'id', 'pid' in sql table
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_ReferenceDataDialog()
        self.ui.setupUi(self)
        self._parent = parent
        self.model = None
        self._view = None
        self._previous_row = -1
        self.selected_id = 0
        self.p_selected_name = ''
        self._filter_text = ''
        self.selection_enabled = False
        self.group_id = None
        self.group_field = None
        self.filter_field = None
        self._filter_value = ''
        self.toggle_state = False
        self.toggle_field = None
        self.search_field = None
        self.search_text = ""
        self.tree_view = False
        self.toolbar = None
        self.custom_editor = False
        self.custom_context_menu = False

        self.ui.AddChildBtn.setVisible(False)
        self.ui.GroupLbl.setVisible(False)
        self.ui.GroupCombo.setVisible(False)
        self.ui.SearchFrame.setVisible(False)

        self.ui.AddBtn.setIcon(load_icon("add.png"))
        self.ui.AddChildBtn.setIcon(load_icon("add_child.png"))
        self.ui.RemoveBtn.setIcon(load_icon("delete.png"))
        self.ui.CommitBtn.setIcon(load_icon("accept.png"))
        self.ui.RevertBtn.setIcon(load_icon("cancel.png"))

        self.ui.SearchString.textChanged.connect(self.OnSearchChange)
        self.ui.GroupCombo.currentIndexChanged.connect(self.OnGroupChange)
        self.ui.Toggle.stateChanged.connect(self.OnToggleChange)
        self.ui.AddBtn.clicked.connect(self.OnAdd)
        self.ui.AddChildBtn.clicked.connect(self.OnChildAdd)
        self.ui.RemoveBtn.clicked.connect(self.OnRemove)
        self.ui.CommitBtn.clicked.connect(self.OnCommit)
        self.ui.RevertBtn.clicked.connect(self.OnRevert)
        self.ui.DataView.doubleClicked.connect(self.OnDoubleClicked)
        self.ui.DataView.clicked.connect(self.OnClicked)
        self.ui.TreeView.doubleClicked.connect(self.OnDoubleClicked)
        self.ui.TreeView.clicked.connect(self.OnClicked)

    def _init_completed(self):
        self.ui.DataView.setVisible(not self.tree_view)
        self.ui.TreeView.setVisible(self.tree_view)
        self._view = self.ui.TreeView if self.tree_view else self.ui.DataView
        self._view.selectionModel().selectionChanged.connect(self.OnRowSelected)
        self._view.setContextMenuPolicy(Qt.CustomContextMenu)
        self._view.customContextMenuRequested.connect(self.onDataViewContextMenu)
        self.model.dataChanged.connect(self.OnDataChanged)
        self.setFilter()

    def onDataViewContextMenu(self, pos):
        contextMenu = QMenu(self._view)
        if self.custom_context_menu:
            self.customizeContextMenu(contextMenu, self._view.indexAt(pos))
        else:
            if not self.group_id:
                return
            index = self._view.indexAt(pos)
            menu_title = QWidgetAction(self._view)
            title_lbl = QLabel()
            title_lbl.setText(self.tr("Change type to:"))
            menu_title.setDefaultWidget(title_lbl)
            contextMenu.addAction(menu_title)
            contextMenu.addSeparator()
            for i in range(self.ui.GroupCombo.count()):
                contextMenu.addAction(self.ui.GroupCombo.itemText(i),
                                      partial(self.updateItemType, index, self.ui.GroupCombo.itemData(i)))
        contextMenu.popup(self._view.viewport().mapToGlobal(pos))

    @Slot()
    def updateItemType(self, index, new_type):
        self.model.updateItemType(index, new_type)
        self.ui.CommitBtn.setEnabled(True)
        self.ui.RevertBtn.setEnabled(True)

    @Slot()
    def closeEvent(self, event):
        if self.ui.CommitBtn.isEnabled():    # There are uncommitted changed in a table
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
        self.ui.CommitBtn.setEnabled(True)
        self.ui.RevertBtn.setEnabled(True)

    @Slot()
    def OnAdd(self):
        if self.custom_editor:
            editor = self.customEditor()
            editor.createNewRecord()
            editor.exec()
            self.model.select()
            self.locateItem(editor.selected_id)
        else:
            idx = self._view.selectionModel().selection().indexes()
            current_index = idx[0] if idx else self.model.index(0, 0)
            self.model.addElement(current_index, in_group=self.group_id)
            self.ui.CommitBtn.setEnabled(True)
            self.ui.RevertBtn.setEnabled(True)

    @Slot()
    def OnChildAdd(self):
        if self.tree_view:
            idx = self.ui.TreeView.selectionModel().selection().indexes()
            current_index = idx[0] if idx else self.model.index(0, 0)
            self.model.addChildElement(current_index)
            self.ui.CommitBtn.setEnabled(True)
            self.ui.RevertBtn.setEnabled(True)

    @Slot()
    def OnRemove(self):
        idx = self._view.selectionModel().selection().indexes()
        current_index = idx[0] if idx else self.model.index(0, 0)
        self.model.removeElement(current_index)
        self.ui.CommitBtn.setEnabled(True)
        self.ui.RevertBtn.setEnabled(True)

    @Slot()
    def OnCommit(self):
        if not self.model.submitAll():
            return
        self.model.invalidate_cache()
        self.ui.CommitBtn.setEnabled(False)
        self.ui.RevertBtn.setEnabled(False)

    @Slot()
    def OnRevert(self):
        self.model.revertAll()
        self.ui.CommitBtn.setEnabled(False)
        self.ui.RevertBtn.setEnabled(False)

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
            conditions.append(f"{self.table}.{self.group_field}={self.group_id}")

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
        self.search_text = self.ui.SearchString.text()
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
        self.group_id = self.ui.GroupCombo.itemData(list_id)
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

    def customEditor(self):
        raise NotImplementedError("Method customEditor() isn't implemented in a descendant of ReferenceDataDialog")

    # this method should fill given menu with actions for element at given index
    def customizeContextMenu(self, menu: QMenu, index):
        raise NotImplementedError(
            "Method customizeContextMenu() isn't implemented in a descendant of ReferenceDataDialog")
