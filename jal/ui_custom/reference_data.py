import logging
from datetime import datetime

from PySide2.QtCore import Qt, Signal, Property, Slot, QEvent
from PySide2.QtSql import QSqlRelationalDelegate
from PySide2.QtWidgets import QDialog, QMessageBox, QStyledItemDelegate

from jal.ui.ui_reference_data_dlg import Ui_ReferenceDataDialog
import jal.ui_custom.reference_selector as ui     # Full import due to "cyclic" reference
from jal.ui_custom.helpers import g_tr
from jal.db.helpers import readSQL


# --------------------------------------------------------------------------------------------------------------
# Class to display and edit table with reference data (accounts, categories, tags...)
# --------------------------------------------------------------------------------------------------------------
class ReferenceDataDialog(QDialog, Ui_ReferenceDataDialog):
    # tree_view - table will be displayed as hierarchical tree with help of 3 columns: 'id', 'pid' and 'children_count'
    #  ('pid' will identify parent row for current row, and '+' will be displayed for row with 'children_count'>0
    def __init__(self):
        QDialog.__init__(self)
        self.setupUi(self)

        self.selected_id = 0
        self.p_selected_name = ''
        self.dialog_visible = False
        self.selection_enabled = False
        self.parent = 0
        self.last_parent = 0
        self.group_id = None
        self.group_key_field = None
        self.group_key_index = None
        self.group_fkey_field = None
        self.toggle_state = False
        self.toggle_field = None
        self.search_field = None
        self.search_text = ""
        self.tree_view = False

        self.GroupLbl.setVisible(False)
        self.GroupCombo.setVisible(False)
        self.SearchFrame.setVisible(False)
        self.UpBtn.setVisible(False)

        self.SearchString.textChanged.connect(self.OnSearchChange)
        self.UpBtn.clicked.connect(self.OnUpClick)
        self.GroupCombo.currentIndexChanged.connect(self.OnGroupChange)
        self.Toggle.stateChanged.connect(self.OnToggleChange)
        self.AddBtn.clicked.connect(self.OnAdd)
        self.RemoveBtn.clicked.connect(self.OnRemove)
        self.CommitBtn.clicked.connect(self.OnCommit)
        self.RevertBtn.clicked.connect(self.OnRevert)
        self.DataView.clicked.connect(self.OnClicked)
        self.DataView.doubleClicked.connect(self.OnDoubleClicked)

    def _init_completed(self):
        self.DataView.selectionModel().selectionChanged.connect(self.OnRowSelected)
        self.model.dataChanged.connect(self.OnDataChanged)
        self.model.select()
        self.setFilter()

    @Slot()
    def closeEvent(self, event):
        if self.CommitBtn.isEnabled():    # There are uncommitted changed in a table
            if QMessageBox().warning(None, g_tr('ReferenceDataDialog', "Confirmation"),
                                     g_tr('ReferenceDataDialog', "You have uncommited changes. Do you want to close?"),
                                     QMessageBox.Yes, QMessageBox.No) == QMessageBox.No:
                event.ignore()
                return
            else:
                self.model.revertAll()
        event.accept()

    # Overload ancestor method to activate/deactivate filters for table view
    def exec_(self, enable_selection=False):
        self.dialog_visible = True
        self.selection_enabled = enable_selection
        self.setFilter()
        res = super().exec_()
        self.dialog_visible = False
        self.resetFilter()
        return res

    def getSelectedName(self):
        if self.selected_id == 0:
            return g_tr('ReferenceDataDialog', "ANY")
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
        new_record = self.model.record()
        if self.tree_view:
            new_record.setValue('pid', self.parent)  # set current parent
        assert self.model.insertRows(0, 1)
        self.model.setRecord(0, new_record)
        self.CommitBtn.setEnabled(True)
        self.RevertBtn.setEnabled(True)

    @Slot()
    def OnRemove(self):
        idx = self.DataView.selectionModel().selection().indexes()
        selected_row = idx[0].row()
        assert self.model.removeRow(selected_row)
        self.CommitBtn.setEnabled(True)
        self.RevertBtn.setEnabled(True)

    @Slot()
    def OnCommit(self):
        if self.group_key_index is not None:
            record = self.model.record(0)
            group_field = record.value(self.model.fieldIndex(self.group_key_field))
            if not group_field:
                self.model.setData(self.model.index(0, self.group_key_index), self.group_id)
        if not self.model.submitAll():
            logging.fatal(g_tr('ReferenceDataDialog', "Submit failed: ") + self.model.lastError().text())
            return
        self.CommitBtn.setEnabled(False)
        self.RevertBtn.setEnabled(False)

    @Slot()
    def OnRevert(self):
        self.model.revertAll()
        self.CommitBtn.setEnabled(False)
        self.RevertBtn.setEnabled(False)

    def resetFilter(self):
        self.DataView.model().setFilter("")

    def setFilter(self):  # TODO: correctly combine different conditions
        if not self.dialog_visible:
            return

        conditions = []
        if self.search_text:
            conditions.append(f"{self.search_field} LIKE '%{self.search_text}%'")
        else:
            if self.tree_view:
                conditions.append(f"pid={self.parent}")

        if self.group_id:
            conditions.append(f"{self.table}.{self.group_key_field}={self.group_id}")

        if self.toggle_field:
            if not self.toggle_state:
                conditions.append(f"{self.table}.{self.toggle_field}=1")

        condition = ""
        for line in conditions:
            condition += line + " AND "
        condition = condition[:-len(" AND ")]

        self.DataView.model().setFilter(condition)

    @Slot()
    def OnSearchChange(self):
        self.search_text = self.SearchString.text()
        self.setFilter()

    @Slot()
    def OnRowSelected(self, selected, _deselected):
        idx = selected.indexes()
        if idx:
            selected_row = idx[0].row()
            self.selected_id = self.DataView.model().record(selected_row).value('id')
            self.p_selected_name = self.DataView.model().record(selected_row).value('name')

    @Slot()
    def OnClicked(self, index):
        if index.column() == 0:
            selected_row = index.row()
            self.parent = self.DataView.model().record(selected_row).value('id')
            self.last_parent = self.DataView.model().record(selected_row).value('pid')
            if self.search_text:
                self.SearchString.setText('')  # it will also call self.setFilter()
            else:
                self.setFilter()

    @Slot()
    def OnDoubleClicked(self, index):
        self.selected_id = self.DataView.model().record(index.row()).value('id')
        self.p_selected_name = self.DataView.model().record(index.row()).value('name')
        if self.selection_enabled:
            self.setResult(QDialog.Accepted)
            self.close()

    @Slot()
    def OnUpClick(self):
        if self.search_text:  # list filtered by search string
            return
        current_id = self.DataView.model().record(0).value('id')
        if current_id is None:
            pid = self.last_parent
        else:
            pid = readSQL(f"SELECT c2.pid FROM {self.table} AS c1 LEFT JOIN {self.table} AS c2 ON c1.pid=c2.id "\
                          f"WHERE c1.id = :current_id", [(":current_id", current_id)])
            if pid == '':
                pid = 0
        self.parent = pid
        self.setFilter()

    @Slot()
    def OnGroupChange(self, list_id):
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

# ===================================================================================================================
# Delegates to customize view of columns
# ===================================================================================================================

# -------------------------------------------------------------------------------------------------------------------
# Display '+' if element have children
class ReferenceTreeDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        painter.save()
        model = index.model()
        children_count = model.data(model.index(index.row(), model.fieldIndex('children_count')), Qt.DisplayRole)
        text = ''
        if children_count:
            text = '+'
        painter.drawText(option.rect, Qt.AlignHCenter, text)
        painter.restore()

# -------------------------------------------------------------------------------------------------------------------
# Display '*' if true and empty cell if false
# Toggle True/False by mouse click
class ReferenceBoolDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        painter.save()
        model = index.model()
        status = model.data(index, Qt.DisplayRole)
        if status:
            text = ' * '
        else:
            text = ''
        painter.drawText(option.rect, Qt.AlignHCenter, text)
        painter.restore()

    def editorEvent(self, event, model, option, index):
        if event.type() == QEvent.MouseButtonPress:
            if model.data(index, Qt.DisplayRole):  # Toggle value - from 1 to 0 and from 0 to 1
                model.setData(index, 0)
            else:
                model.setData(index, 1)
        return True

# -------------------------------------------------------------------------------------------------------------------
# Make integer alignment to the right
class ReferenceIntDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        painter.save()
        model = index.model()
        value = model.data(index, Qt.DisplayRole)
        painter.drawText(option.rect, Qt.AlignRight, f"{value} ")
        painter.restore()

# -------------------------------------------------------------------------------------------------------------------
# Format unix timestamp into readable form '%d/%m/%Y %H:%M:%S'
class ReferenceTimestampDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        painter.save()
        model = index.model()
        timestamp = model.data(index, Qt.DisplayRole)
        if timestamp:
            text = datetime.utcfromtimestamp(timestamp).strftime('%d/%m/%Y %H:%M:%S')
        else:
            text = ""
        painter.drawText(option.rect, Qt.AlignLeft, text)
        painter.restore()

# -------------------------------------------------------------------------------------------------------------------
# The class itself is empty but it activates built-in editors for lookup tables
class ReferenceLookupDelegate(QSqlRelationalDelegate):
    def __init__(self, parent=None):
        QSqlRelationalDelegate.__init__(self, parent)

# -----------------------------------------------------------------------------------------------------------------------
# Delegate to display tag editor
class ReferencePeerDelegate(QSqlRelationalDelegate):
    def __init__(self, parent=None):
        QSqlRelationalDelegate.__init__(self, parent)

    def createEditor(self, aParent, option, index):
        peer_selector = ui.PeerSelector(aParent)
        return peer_selector

    def setModelData(self, editor, model, index):
        model.setData(index, editor.selected_id)