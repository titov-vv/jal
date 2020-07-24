import logging

from PySide2.QtCore import Qt, Signal, Property, Slot, QModelIndex, QEvent
from PySide2.QtSql import QSqlQuery, QSqlRelationalDelegate
from PySide2.QtWidgets import QDialog
from PySide2.QtWidgets import QStyledItemDelegate

from UI.ui_reference_data_dlg import Ui_ReferenceDataDialog
from CustomUI.helpers import UseSqlTable, ConfigureTableView, hcol_idx


# --------------------------------------------------------------------------------------------------------------
# Class to display and edit table with reference data (accounts, categories, tags...)
# --------------------------------------------------------------------------------------------------------------
class ReferenceDataDialog(QDialog, Ui_ReferenceDataDialog):
    # ----------------------------------------------------------------------------------------------------------
    # Params:
    # db - QSqlDatabase object for DB operations
    # table - name of the table to display/edit
    # columns - list of tuples - see helpers.py for details
    # title - title of dialog window
    # search_field - field name which will be used for search from GUI
    # tree_view - table will be displayed as hierarchical tree with help of 3 columns: 'id', 'pid' and 'children_count'
    #  ('pid' will identify parent row for current row, and '+' will be displayed for row with 'children_count'>0
    def __init__(self, db, table, columns, title='', search_field=None, tree_view=False):
        QDialog.__init__(self)
        self.setupUi(self)

        self.selected_id = 0
        self.tree_view = tree_view
        self.parent = 0
        self.last_parent = 0
        self.search_text = ""
        self.search_field = search_field

        self.db = db
        self.table = table
        self.Model = UseSqlTable(self.db, self.table, columns)
        ConfigureTableView(self.DataView, self.Model, columns)
        if self.tree_view:
            self.DataView.setItemDelegateForColumn(self.Model.fieldIndex("id"), ReferenceTreeDelegate(self.DataView))
        for column in columns:
            if column[hcol_idx.DELEGATE] is not None:
                self.DataView.setItemDelegateForColumn(self.Model.fieldIndex(column[hcol_idx.DB_NAME]),
                                                       column[hcol_idx.DELEGATE](self.DataView))

        self.setWindowTitle(title)
        if self.search_field is not None:
            self.SearchFrame.setVisible(True)
        else:
            self.SearchFrame.setVisible(False)
        self.UpBtn.setVisible(self.tree_view)

        self.SearchString.textChanged.connect(self.OnSearchChange)
        self.UpBtn.clicked.connect(self.OnUpClick)
        self.AddBtn.clicked.connect(self.OnAdd)
        self.RemoveBtn.clicked.connect(self.OnRemove)
        self.CommitBtn.clicked.connect(self.OnCommit)
        self.RevertBtn.clicked.connect(self.OnRevert)
        self.DataView.clicked.connect(self.OnClicked)
        self.DataView.selectionModel().selectionChanged.connect(self.OnRowSelected)
        self.Model.dataChanged.connect(self.OnDataChanged)

        self.Model.select()
        self.setFilter()

    @Slot()
    def OnDataChanged(self):
        self.CommitBtn.setEnabled(True)
        self.RevertBtn.setEnabled(True)

    @Slot()
    def OnAdd(self):
        new_record = self.Model.record()
        if self.tree_view:
            new_record.setValue("pid", self.parent)  # set current parent
        assert self.Model.insertRows(0, 1)
        self.Model.setRecord(0, new_record)
        self.CommitBtn.setEnabled(True)
        self.RevertBtn.setEnabled(True)

    @Slot()
    def OnRemove(self):
        idx = self.DataView.selectionModel().selection().indexes()
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
            if self.tree_view:
                self.DataView.model().setFilter(f"pid={self.parent}")
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
            self.selected_id = self.DataView.model().record(selected_row).value("id")

    @Slot()
    def OnClicked(self, index):
        if index.column() == 0:
            selected_row = index.row()
            self.parent = self.DataView.model().record(selected_row).value("id")
            self.last_parent = self.DataView.model().record(selected_row).value("pid")
            if self.search_text:
                self.SearchString.setText("")  # it will also call self.setFilter()
            else:
                self.setFilter()

    @Slot()
    def OnUpClick(self):
        if self.search_text:  # list filtered by search string
            return
        query = QSqlQuery(self.db)
        query.prepare(f"SELECT c2.pid FROM {self.table} AS c1 LEFT JOIN {self.table} AS c2 ON c1.pid=c2.id "
                      f"WHERE c1.id = :current_id")
        current_id = self.DataView.model().record(0).value("id")
        if current_id is None:
            pid = self.last_parent
        else:
            query.bindValue(":current_id", current_id)
            query.exec_()
            query.next()
            pid = query.value(0)
            if pid == '':
                pid = 0
        self.parent = pid
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
        children_count = model.data(model.index(index.row(), model.fieldIndex("children_count")), Qt.DisplayRole)
        text = ""
        if children_count:
            text = "+"
        painter.drawText(option.rect, Qt.AlignHCenter, text)
        painter.restore()

# -------------------------------------------------------------------------------------------------------------------
# Display '*' if true and empty cell if false
# Toggle True/False by mouse click
class ReferenceBoolDelegate(QSqlRelationalDelegate):
    def __init__(self, parent=None):
        QSqlRelationalDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        painter.save()
        model = index.model()
        status = model.data(index, Qt.DisplayRole)
        if status:
            text = " * "
        else:
            text = ""
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
class ReferenceIntDelegate(QSqlRelationalDelegate):
    def __init__(self, parent=None):
        QSqlRelationalDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        painter.save()
        model = index.model()
        value = model.data(index, Qt.DisplayRole)
        painter.drawText(option.rect, Qt.AlignRight, f"{value} ")
        painter.restore()