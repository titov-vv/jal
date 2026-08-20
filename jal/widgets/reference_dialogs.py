import base64
import logging
from PySide6.QtCore import Qt, Slot, Signal, Property, QDate, QPoint
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QDialog, QDialogButtonBox, QMessageBox, QHeaderView, QAbstractItemView
from PySide6.QtSql import QSqlRelationalDelegate
from jal.constants import CmWidth, CmDelegate, CmReference
from jal.db.common_models import AccountListModel, PeerTreeModel, CategoryTreeModel, TagTreeModel, QuotesListModel, \
    ResidenceListModel, TokenBlacklistModel
from jal.db.asset_models import SymbolsListModel
from jal.db.account import JalAccount
from jal.db.peer import JalPeer
from jal.db.category import JalCategory
from jal.db.tag import JalTag
from jal.widgets.selection_dialog import SelectReferenceDialog
from jal.ui.ui_reference_data_dlg import Ui_ReferenceDataDialog
from jal.widgets.delegates import BoolDelegate, FloatDelegate, GridLinesDelegate, TimestampDelegate, LookupSelectorDelegate, AssetSelectorDelegate, ConstantLookupDelegate, TimezoneDelegate
from jal.widgets.icons import JalIcon
from jal.db.settings import JalSettings
from jal.widgets.assets_dialogs import SymbolListDialog
from jal.widgets.account_dialog import AccountDialog
from jal.widgets.helpers import set_tables_row_height


# --------------------------------------------------------------------------------------------------------------
# Class to display and edit table with reference data (accounts, categories, tags...)
# Child classes are defined below
# --------------------------------------------------------------------------------------------------------------
class ReferenceDataDialog(QDialog):
    selection_done = Signal(int)

    # tree_view - table will be displayed as hierarchical tree with help of 2 columns: 'id', 'pid' in SQL table
    def __init__(self, parent=None, window_title=''):
        super().__init__(parent)
        self.ui = Ui_ReferenceDataDialog()
        self.ui.setupUi(self)
        set_tables_row_height(self)
        self._parent = parent
        self.model = None
        self._view = None
        self._view_header = None
        self._previous_row = -1
        self.selected_id = 0
        self.dialog_window_name = window_title
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
        self.custom_context_menu = False
        self._delegates = []  # to keep references to delegates to avoid garbage collection

        self.ui.AddChildBtn.setVisible(False)
        self.ui.EditBtn.setVisible(False)
        self.ui.GroupLbl.setVisible(False)
        self.ui.GroupCombo.setVisible(False)
        self.ui.SearchFrame.setVisible(False)

        self.ui.AddBtn.setIcon(JalIcon[JalIcon.ADD])
        self.ui.AddChildBtn.setIcon(JalIcon[JalIcon.ADD_CHILD])
        self.ui.EditBtn.setIcon(JalIcon[JalIcon.DETAILS])
        self.ui.RemoveBtn.setIcon(JalIcon[JalIcon.REMOVE])
        self.ui.CommitBtn.setIcon(JalIcon[JalIcon.OK])
        self.ui.RevertBtn.setIcon(JalIcon[JalIcon.CANCEL])

        self.ui.SearchString.textChanged.connect(self.OnSearchChange)
        self.ui.GroupCombo.currentIndexChanged.connect(self.OnGroupChange)
        self.ui.Toggle.stateChanged.connect(self.OnToggleChange)
        self.ui.AddBtn.clicked.connect(self.OnAdd)
        self.ui.AddChildBtn.clicked.connect(self.OnChildAdd)
        self.ui.EditBtn.clicked.connect(self.OnEdit)
        self.ui.RemoveBtn.clicked.connect(self.OnRemove)
        self.ui.CommitBtn.clicked.connect(self.OnCommit)
        self.ui.RevertBtn.clicked.connect(self.OnRevert)
        self.ui.DataView.doubleClicked.connect(self.OnDoubleClicked)
        self.ui.TreeView.doubleClicked.connect(self.OnDoubleClicked)
        self.ui.DialogButtonBox.accepted.connect(self.onDialogAccept)
        self.ui.DialogButtonBox.rejected.connect(self.onDialogReject)

    def setup_ui(self):
        self.ui.DataView.setVisible(not self.tree_view)
        self.ui.TreeView.setVisible(self.tree_view)
        if self.tree_view:
            self._view = self.ui.TreeView
            self._view_header = self._view.header()
        else:
            self._view = self.ui.DataView
            self._view_header = self._view.horizontalHeader()
        self._view.selectionModel().selectionChanged.connect(self.OnRowSelected)
        self._view.setContextMenuPolicy(Qt.CustomContextMenu)
        self._view.customContextMenuRequested.connect(self.onDataViewContextMenu)
        self._view_header.setContextMenuPolicy(Qt.CustomContextMenu)
        self._view_header.customContextMenuRequested.connect(self.onHeaderContextMenu)
        self.configureColumns()
        self.configureDelegates()
        self.model.dataChanged.connect(self.OnDataChanged)
        self.setFilter()
        self.setWindowTitle(self.dialog_window_name)
        self.restoreGeometry(base64.decodebytes(JalSettings().getValue('DlgGeometry_' + self.dialog_window_name, '').encode('utf-8')))
        self._view_header.restoreState(base64.decodebytes(JalSettings().getValue('DlgViewState_' + self.dialog_window_name, '').encode('utf-8')))

    @Slot()
    def onDataViewContextMenu(self, pos):
        contextMenu = QMenu(self._view)
        if self.custom_context_menu:
            self.customizeContextMenu(contextMenu, self._view.indexAt(pos))
        contextMenu.popup(self._view.viewport().mapToGlobal(pos))

    @Slot()
    def onHeaderContextMenu(self, pos):
        contextMenu = QMenu(self._view_header)
        contextMenu.addAction(QAction(self.tr("Reset columns"), self, triggered=self.configureColumns))
        contextMenu.popup(self._view.viewport().mapToGlobal(pos))

    @Slot()
    def updateItemType(self, index, new_type):
        self.model.updateItemType(index, new_type)
        self.ui.CommitBtn.setEnabled(True)
        self.ui.RevertBtn.setEnabled(True)

    @Slot()
    def showEvent(self, event):
        super().showEvent(event)
        if self.selection_enabled:  # It works better here than in exec()
            current_index = self._view.currentIndex().siblingAtColumn(self.model.fieldIndex("ID"))  # Column #0 is hidden, so we scroll to column #1
            if current_index.isValid():
                self._view.scrollTo(current_index, QAbstractItemView.PositionAtCenter)

    # The dialog does two jobs: it edits a reference table, where the only thing left to do is close it, and it
    # picks a row for someone else, where it has an answer to return. The button box says which one is running.
    # Commit and Revert stay in the toolbar above - they save and undo edits to the table, they do not end the dialog.
    def _setup_dialog_buttons(self):
        if self.selection_enabled:
            self.ui.DialogButtonBox.setStandardButtons(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        else:
            self.ui.DialogButtonBox.setStandardButtons(QDialogButtonBox.Close)
        self._update_accept_button()

    # There is nothing to return until a row is picked, so OK stays unavailable rather than accepting an empty answer
    def _update_accept_button(self):
        accept_button = self.ui.DialogButtonBox.button(QDialogButtonBox.Ok)
        if accept_button is not None:
            accept_button.setEnabled(self._view is not None and self._view.currentIndex().isValid())

    # Both exits go through close() rather than accept()/reject(): closeEvent() is what stores the window geometry,
    # the column layout and the unsaved-changes prompt, and QDialog.accept() hides the dialog without sending one.
    @Slot()
    def onDialogAccept(self):
        self.setResult(QDialog.Accepted)
        self.close()

    @Slot()
    def onDialogReject(self):
        self.setResult(QDialog.Rejected)
        self.close()

    @Slot()
    def closeEvent(self, event):
        if self.ui.CommitBtn.isEnabled():    # There are uncommitted changes in the table
            answer = QMessageBox().warning(self, self.tr("Confirmation"),
                                           self.tr("You have unsaved changes. Do you want to save them?"),
                                           QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                                           QMessageBox.Save)
            if answer == QMessageBox.Cancel:
                self.setResult(QDialog.Rejected)   # the exit was called off, so it must not report a selection
                event.ignore()
                return
            if answer == QMessageBox.Save:
                self.OnCommit()
                if self.ui.CommitBtn.isEnabled():   # submitAll() refused - the edits are still pending
                    self.setResult(QDialog.Rejected)
                    event.ignore()
                    return
            else:
                self.model.revertAll()
        JalSettings().setValue('DlgGeometry_' + self.dialog_window_name, base64.encodebytes(self.saveGeometry().data()).decode('utf-8'))
        JalSettings().setValue('DlgViewState_' + self.dialog_window_name, base64.encodebytes(self._view_header.saveState().data()).decode('utf-8'))
        event.accept()

    @Slot(int, QPoint)
    def dialog_requested(self, selected_id: int, position: QPoint, _params: dict):
        self.setGeometry(position.x(), position.y(), self.width(), self.height())
        self.exec(enable_selection=True, selected=selected_id)

    # Overload ancestor method to activate/deactivate filters for table view
    def exec(self, enable_selection=False, selected=0):
        self.selection_enabled = enable_selection
        self._setup_dialog_buttons()
        self.setFilter()             # TODO Check filters, if it work correctly
        if self.selection_enabled:
            item_index = self.model.locateItem(selected)
            if self.tree_view and item_index.isValid():
                self.expand_parent_items(item_index)
            self._view.setCurrentIndex(item_index)
        res = super().exec()
        if res:
            self.selection_done.emit(self.selected_id)
        self.resetFilter()
        return res

    # expand all parent tree items so that item at given index becomes visible in self._view
    def expand_parent_items(self, index):
        parent = index.parent()
        if parent.isValid():
            self.expand_parent_items(parent)
        self._view.expand(index)

    def configureColumns(self):
        specs = self.model.column_meta()
        for col, spec in enumerate(specs):
            if spec.hide:
                self._view.setColumnHidden(col, True)
            if spec.width:
                if spec.width == CmWidth.WIDTH_STRETCH:
                    self._view_header.setSectionResizeMode(col, QHeaderView.Stretch)
                elif spec.width == CmWidth.WIDTH_DATETIME:
                    self._view.setColumnWidth(col, self._view.fontMetrics().horizontalAdvance("00/00/0000 00:00:00") * 1.1)
                else:
                    self._view.setColumnWidth(col, spec.width)

    def configureDelegates(self):
        specs = self.model.column_meta()
        for col, spec in enumerate(specs):
            if not spec.delegate_type:
                continue
            if spec.delegate_type == CmDelegate.BOOL:
                delegate = BoolDelegate(self._view)
            elif spec.delegate_type == CmDelegate.CONSTANT:
                delegate = ConstantLookupDelegate(spec.delegate_details, self._view)
            elif spec.delegate_type == CmDelegate.FLOAT:
                delegate = FloatDelegate(spec.delegate_details, parent=self._view)
            elif spec.delegate_type == CmDelegate.GRID:
                delegate = GridLinesDelegate(self._view)
            elif spec.delegate_type == CmDelegate.LOOKUP:
                delegate = QSqlRelationalDelegate(self._view)
            elif spec.delegate_type == CmDelegate.REFERENCE:
                delegate_class = LookupSelectorDelegate
                if spec.delegate_details == CmReference.TAG:
                    model_class, dialog_class = TagTreeModel, TagsListDialog
                elif spec.delegate_details == CmReference.PEER:
                    model_class, dialog_class = PeerTreeModel, PeerListDialog
                elif spec.delegate_details == CmReference.SYMBOL:
                    model_class, dialog_class = SymbolsListModel, SymbolListDialog
                elif spec.delegate_details == CmReference.ASSET_VIA_SYMBOL:
                    model_class, dialog_class = SymbolsListModel, SymbolListDialog
                    delegate_class = AssetSelectorDelegate
                else:
                    raise NotImplementedError(f"Unsupported reference delegate type {spec.delegate_details}")
                delegate = delegate_class(self._view, model_class, dialog_class, self)
            elif spec.delegate_type == CmDelegate.TIMESTAMP:
                delegate = TimestampDelegate(parent=self._view)
            elif spec.delegate_type == CmDelegate.DATE:
                delegate = TimestampDelegate(date_only=True, parent=self._view)
            elif spec.delegate_type == CmDelegate.TIMEZONE:
                delegate = TimezoneDelegate(self._view)
            else:
                continue
            self._view.setItemDelegateForColumn(col, delegate)
            self._delegates.append(delegate)

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
            self.ui.TreeView.expand(current_index)
            self.ui.CommitBtn.setEnabled(True)
            self.ui.RevertBtn.setEnabled(True)

    # 'EditBtn' is hidden by default; child classes that edit records via a modal dialog make it visible and
    # override this slot. The base grid edits cells in-line, so there is nothing to do here.
    @Slot()
    def OnEdit(self):
        pass

    @Slot()
    def OnRemove(self):
        idx = self._view.selectionModel().selection().indexes()
        current_index = idx[0] if idx else self.model.index(0, 0)
        if self.model.removeElement(current_index):
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
            conditions.append(f"{self.group_field}={self.group_id}")

        if self.filter_field is not None and self._filter_value:
            conditions.append(f"{self.filter_field} = {self._filter_value}")
            # completion model needs only this filter, others are for dialog
            self.model.completion_model.setFilter(f"{self.filter_field} = {self._filter_value}")

        if self.toggle_field:
            if not self.toggle_state:
                conditions.append(f"{self.toggle_field}=1")

        self._filter_text = ' AND '.join(conditions)
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
        self._update_accept_button()

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

    # this method should fill given menu with actions for element at given index
    def customizeContextMenu(self, menu: QMenu, index):
        raise NotImplementedError(
            "Method customizeContextMenu() isn't implemented in a descendant of ReferenceDataDialog")


# ----------------------------------------------------------------------------------------------------------------------
class AccountListDialog(ReferenceDataDialog):
    # 'include_hidden' opens the dialog on the account types the user never picks by hand (a deposit or a staking
    # box). It exists for the one caller that assigns a transfer leg TO such a box, and is meant to be used together
    # with 'filter_field'/'filter_value' narrowing the list to the single type that caller means - see
    # TransferAssignDialog. The narrowing is given here, and not set on the dialog afterwards, because the dialog is
    # built by the selector widget on the first click of its "..." button - there is no instance to configure before.
    def __init__(self, parent=None, include_hidden: bool = False, filter_field: str = None, filter_value=None):
        super().__init__(parent=parent, window_title=self.tr("Accounts"))
        self.model = AccountListModel(self, include_hidden=include_hidden)
        self.ui.DataView.setModel(self.model)
        self.setup_ui()
        if filter_field is not None:
            self.filter_field = filter_field
            self.setFilterValue(filter_value)

    def setup_ui(self):
        self.search_field = "accounts.name"
        self.ui.SearchFrame.setVisible(True)
        self.ui.Toggle.setVisible(True)
        self.toggle_field = "active"
        self.ui.Toggle.setText(self.tr("Show inactive"))

        self.ui.GroupLbl.setVisible(True)
        self.ui.GroupLbl.setText(self.tr("Account type:"))
        self.ui.GroupCombo.setVisible(True)
        self.group_field = self.model.group_by
        self.ui.GroupCombo.clear()
        self.ui.GroupCombo.addItem(self.tr("All types"), userData=None)
        for type_id, type_name in sorted(JalAccount.get_all_types().items(), key=lambda x: x[1]):
            self.ui.GroupCombo.addItem(JalIcon[JalAccount.get_type_icon(type_id)], type_name, type_id)
        self.group_id = self.ui.GroupCombo.itemData(0)
        super().setup_ui()
        # Accounts (and their account_data attributes) are edited in the modal AccountDialog.
        self.ui.EditBtn.setVisible(True)
        self.ui.DataView.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.ui.CommitBtn.setVisible(False)
        self.ui.RevertBtn.setVisible(False)

    # Add/Edit open the modal AccountDialog to create/edit an account and its account_data attributes.
    @Slot()
    def OnAdd(self):
        dialog = AccountDialog(self)
        dialog.createNewRecord()
        if dialog.exec() == QDialog.Accepted:
            self._reload()

    @Slot()
    def OnEdit(self):
        idx = self._view.currentIndex()
        if not idx.isValid():
            return
        account_id = self.model.getId(idx)
        dialog = AccountDialog(self)
        dialog.setSelectedId(account_id)
        if dialog.exec() == QDialog.Accepted:
            self._reload()

    @Slot()
    def OnRemove(self):
        idx = self._view.selectionModel().selection().indexes()
        current_index = idx[0] if idx else self.model.index(0, 0)
        if self.model.removeElement(current_index):  # AccountListModel.removeElement asks for confirmation
            self.model.submitAll()                   # accounts are removed immediately, there is no pending state
            self._reload()

    # In management mode a double-click opens the editor; in selection mode it keeps the base 'pick & close' behavior
    @Slot()
    def OnDoubleClicked(self, index):
        if self.selection_enabled:
            super().OnDoubleClicked(index)
        else:
            self.OnEdit()

    def _reload(self):
        self.model.invalidate_cache()
        self.setFilter()


# ----------------------------------------------------------------------------------------------------------------------
class PeerListDialog(ReferenceDataDialog):
    def __init__(self, parent=None):
        super().__init__(parent=parent, window_title=self.tr("Peers"))
        self.model = PeerTreeModel(self)
        self.ui.TreeView.setModel(self.model)
        self.setup_ui()
        self._menu_peer_id = 0
        self._menu_peer_name = ''
        self.actionShowUsage = QAction(text=self.tr("Show operations with Peer"), parent=self)
        self.actionReplace = QAction(text=self.tr("Replace with..."), parent=self)
        self.actionShowUsage.triggered.connect(self.showUsageReport)
        self.actionReplace.triggered.connect(self.replacePeer)

    def setup_ui(self):
        self.search_field = "name"
        self.tree_view = True
        self.ui.AddChildBtn.setVisible(True)
        self.ui.SearchFrame.setVisible(True)
        self.ui.Toggle.setVisible(False)
        if hasattr(self._parent, "reports"):  # Activate menu only if dialog is called from main window menu
            self.custom_context_menu = True
        super().setup_ui()
        
    def customizeContextMenu(self, menu: QMenu, index):
        self._menu_peer_id = self.model.getId(index)
        self._menu_peer_name = self.model.getName(index)
        menu.addAction(self.actionShowUsage)
        menu.addAction(self.actionReplace)

    @Slot()
    def showUsageReport(self):
        settings = {'begin_ts': 0, 'end_ts': QDate.currentDate().endOfDay(Qt.UTC).toSecsSinceEpoch(),
                    'peer_id': self._menu_peer_id}
        self._parent.reports.show_report("PeerReportWindow", settings, floating=False)

    @Slot()
    def replacePeer(self):
        dialog = SelectReferenceDialog(self, self.tr("Please select peer"),
                                       self.tr("Replace peer '") + self._menu_peer_name + self.tr("' with: "),
                                       PeerTreeModel, PeerListDialog)
        if dialog.exec() != QDialog.Accepted:
            return
        reply = QMessageBox().warning(self, '', self.tr("Keep old name in notes?"), QMessageBox.Yes, QMessageBox.No)
        if reply == QMessageBox.Yes:
            JalPeer(self._menu_peer_id).replace_with(dialog.selected_id, old_name=self._menu_peer_name)
        else:
            JalPeer(self._menu_peer_id).replace_with(dialog.selected_id)
        logging.info(self.tr("Peer '") + self._menu_peer_name + self.tr("' was successfully replaced"))
        self.close()


# ----------------------------------------------------------------------------------------------------------------------
class CategoryListDialog(ReferenceDataDialog):
    def __init__(self, parent=None):
        super().__init__(parent=parent, window_title=self.tr("Categories"))
        self.model = CategoryTreeModel(self)
        self.ui.TreeView.setModel(self.model)
        self.setup_ui()
        self._menu_category_id = 0
        self._menu_category_name = ''
        self.actionShowUsage = QAction(text=self.tr("Show operations with Category"), parent=self)
        self.actionReplace = QAction(text=self.tr("Replace with..."), parent=self)
        self.actionShowUsage.triggered.connect(self.showUsageReport)
        self.actionReplace.triggered.connect(self.replaceCategory)

    def setup_ui(self):
        self.search_field = "name"
        self.tree_view = True
        self.ui.AddChildBtn.setVisible(True)
        self.ui.SearchFrame.setVisible(True)
        self.ui.Toggle.setVisible(False)
        if hasattr(self._parent, "reports"):  # Activate menu only if dialog is called from main window menu
            self.custom_context_menu = True
        super().setup_ui()

    def customizeContextMenu(self, menu: QMenu, index):
        self._menu_category_id = self.model.getId(index)
        self._menu_category_name = self.model.getName(index)
        menu.addAction(self.actionShowUsage)
        menu.addAction(self.actionReplace)

    @Slot()
    def showUsageReport(self):
        settings = {'begin_ts': 0, 'end_ts': QDate.currentDate().endOfDay(Qt.UTC).toSecsSinceEpoch(),
                    'category_id': self._menu_category_id}
        self._parent.reports.show_report("CategoryReportWindow", settings, floating=False)

    @Slot()
    def replaceCategory(self):
        dialog = SelectReferenceDialog(self, self.tr("Please select category"),
                                       self.tr("Replace category '") + self._menu_category_name + self.tr("' with: "),
                                       CategoryTreeModel, CategoryListDialog)
        if dialog.exec() != QDialog.Accepted:
            return
        JalCategory(self._menu_category_id).replace_with(dialog.selected_id)
        logging.info(self.tr("Category '") + self._menu_category_name + self.tr("' was successfully replaced"))
        self.close()

# ----------------------------------------------------------------------------------------------------------------------
class TagsListDialog(ReferenceDataDialog):
    def __init__(self, parent=None):
        super().__init__(parent, window_title=self.tr("Tags"))
        self.model = TagTreeModel(parent=self)
        self.ui.TreeView.setModel(self.model)
        self.setup_ui()
        self._menu_tag_id = 0
        self._menu_tag_name = ''
        self.actionShowUsage = QAction(text=self.tr("Show operations with Tag"), parent=self)
        self.actionReplace = QAction(text=self.tr("Replace with..."), parent=self)
        self.actionShowUsage.triggered.connect(self.showUsageReport)
        self.actionReplace.triggered.connect(self.replaceTag)

    def setup_ui(self):
        self.search_field = "tag"
        self.tree_view = True
        self.ui.AddChildBtn.setVisible(True)
        self.ui.SearchFrame.setVisible(True)
        self.ui.Toggle.setVisible(False)
        if hasattr(self._parent, "reports"):  # Activate menu only if dialog is called from main window menu
            self.custom_context_menu = True
        super().setup_ui()

    def customizeContextMenu(self, menu: QMenu, index):
        self._menu_tag_id = self.model.getId(index)
        self._menu_tag_name = self.model.getName(index)
        menu.addAction(self.actionShowUsage)
        menu.addAction(self.actionReplace)

    @Slot()
    def showUsageReport(self):
        settings = {'begin_ts': 0, 'end_ts': QDate.currentDate().endOfDay(Qt.UTC).toSecsSinceEpoch(),
                    'tag_id': self._menu_tag_id}
        self._parent.reports.show_report("TagReportWindow", settings, floating=False)

    @Slot()
    def replaceTag(self):
        dialog = SelectReferenceDialog(self, self.tr("Please select tag"),
                                       self.tr("Replace tag '") + self._menu_tag_name + self.tr("' with: "),
                                       TagTreeModel, TagsListDialog)
        if dialog.exec() != QDialog.Accepted:
            return
        JalTag(self._menu_tag_id).replace_with(dialog.selected_id)
        logging.info(self.tr("Tag '") + self._menu_tag_name + self.tr("' was successfully replaced"))
        self.close()


# ----------------------------------------------------------------------------------------------------------------------
class QuotesListDialog(ReferenceDataDialog):
    def __init__(self, parent=None):
        super().__init__(parent, window_title=self.tr("Quotes"))
        self.model = QuotesListModel(self)
        self.ui.DataView.setModel(self.model)
        self.setup_ui()

    def setup_ui(self):
        self.search_field = "asset_id-asset_symbol-asset_id-symbol"
        self.ui.SearchFrame.setVisible(True)
        self.ui.Toggle.setVisible(False)
        super().setup_ui()


# ----------------------------------------------------------------------------------------------------------------------
class ResidenceDialog(ReferenceDataDialog):
    def __init__(self, parent=None):
        super().__init__(parent, window_title=self.tr("Residence"))
        self.model = ResidenceListModel(self)
        self.ui.DataView.setModel(self.model)
        self.setup_ui()

    def setup_ui(self):
        self.ui.Toggle.setVisible(False)
        super().setup_ui()


# ----------------------------------------------------------------------------------------------------------------------
# Tokens that were found in a wallet but are never imported (unsolicited dust airdrops, scam tokens or tokens
# rejected by the user). Removing a record here un-blacklists the token and it will be imported by the next
# fetch from the blockchain.
class TokenBlacklistDialog(ReferenceDataDialog):
    def __init__(self, parent=None):
        super().__init__(parent, window_title=self.tr("Token blacklist"))
        self.model = TokenBlacklistModel(self)
        self.ui.DataView.setModel(self.model)
        self.setup_ui()

    def setup_ui(self):
        self.search_field = "address"
        self.ui.SearchFrame.setVisible(True)
        self.ui.Toggle.setVisible(False)
        super().setup_ui()
