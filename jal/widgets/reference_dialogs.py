import logging
from PySide6.QtCore import Qt, Slot, QDate
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QAbstractItemView, QMenu, QDialog, QMessageBox

from db.common_models import AccountListModel, SymbolsListModel, PeerTreeModel, CategoryTreeModel, TagTreeModel, \
    QuotesListModel, BaseCurrencyListModel
from jal.constants import PredefinedAsset
from jal.db.account import JalAccount
from jal.db.peer import JalPeer
from jal.db.category import JalCategory
from jal.db.tag import JalTag
from jal.widgets.reference_data import ReferenceDataDialog
# FIXME: re-enable AssetDialog import
# from jal.widgets.asset_dialog import AssetDialog
from jal.widgets.selection_dialog import SelectReferenceDialog
from jal.widgets.icons import JalIcon
from jal.widgets.delegates import LookupSelectorDelegate


# ----------------------------------------------------------------------------------------------------------------------
class AccountListDialog(ReferenceDataDialog):
    def __init__(self, parent=None):
        super().__init__(parent=parent, window_title=self.tr("Accounts"))
        self.table = "accounts"
        self._tag_model = TagTreeModel(self)
        self._tag_dialog = TagsListDialog(self)
        self._tag_delegate = LookupSelectorDelegate(self, self._tag_model, self._tag_dialog)
        self.model = AccountListModel(parent_view=self.ui.DataView)
        self.ui.DataView.setModel(self.model)
        self.model.configureView()
        self.setup_ui()
        super()._init_completed()

    def setup_ui(self):
        self.search_field = "accounts.name"
        self.ui.SearchFrame.setVisible(True)
        self.ui.Toggle.setVisible(True)
        self.toggle_field = "active"
        self.ui.Toggle.setText(self.tr("Show inactive"))

        self.ui.GroupLbl.setVisible(True)
        self.ui.GroupLbl.setText(self.tr("Account tag:"))
        self.ui.GroupCombo.setVisible(True)
        self.group_field = self.model.group_by
        self.ui.GroupCombo.clear()
        self.ui.GroupCombo.addItem(self.tr("All tags"), userData=None)
        for tag_id, tag in sorted(JalAccount.get_all_tags().items(), key=lambda x: x[1]):
            self.ui.GroupCombo.addItem(JalIcon[JalTag(tag_id).icon()], tag, tag_id)
        self.group_id = self.ui.GroupCombo.itemData(0)

    def locateItem(self, item_id):
        type_id = self.model.getGroupId(item_id)
        if type_id == 0:
            return
        self.ui.GroupCombo.setCurrentIndex(type_id-1)
        item_idx = self.model.locateItem(item_id, use_filter=self._filter_text)
        self.ui.DataView.setCurrentIndex(item_idx)

    def set_tag_delegate(self, column):
        self.ui.DataView.setItemDelegateForColumn(column, self._tag_delegate)


# ----------------------------------------------------------------------------------------------------------------------
class SymbolListDialog(ReferenceDataDialog):
    def __init__(self, parent=None):
        super().__init__(parent=parent, window_title=self.tr("Assets"))
        self.table = "symbols_ext"
        self.model = SymbolsListModel(parent_view=self.ui.DataView)
        self.ui.DataView.setModel(self.model)
        self.model.configureView()
        self.setup_ui()
        super()._init_completed()

    def setup_ui(self):
        self.search_field = "full_name"
        self.ui.SearchFrame.setVisible(True)
        self.ui.Toggle.setVisible(False)

        self.custom_editor = True
        self.ui.DataView.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self.ui.GroupLbl.setVisible(True)
        self.ui.GroupLbl.setText(self.tr("Asset type:"))
        self.ui.GroupCombo.setVisible(True)
        self.group_field = self.model.group_by
        PredefinedAsset().load2combo(self.ui.GroupCombo)
        self.group_id = 1

    def locateItem(self, item_id):
        type_id = self.model.getGroupId(item_id)
        if type_id == 0:
            return
        self.ui.GroupCombo.setCurrentIndex(type_id-1)
        item_idx = self.model.locateItem(item_id, use_filter=self._filter_text)
        self.ui.DataView.setCurrentIndex(item_idx)

    # def customEditor(self):
    #     return AssetDialog(self)   #FIXME make new custom SymbolsListDialog


# ----------------------------------------------------------------------------------------------------------------------
class PeerListDialog(ReferenceDataDialog):
    def __init__(self, parent=None):
        super().__init__(parent=parent, window_title=self.tr("Peers"))
        self.table = "agents"
        self.model = PeerTreeModel(parent_view=self.ui.TreeView)
        self.ui.TreeView.setModel(self.model)
        self.model.configureView()
        self.setup_ui()
        super()._init_completed()
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

    def locateItem(self, item_id):
        self.model.locateItem(item_id)
        
    def customizeContextMenu(self, menu: QMenu, index):
        self._menu_peer_id = self.model.getId(index)
        self._menu_peer_name = self.model.getName(index)
        menu.addAction(self.actionShowUsage)
        menu.addAction(self.actionReplace)

    @Slot()
    def showUsageReport(self):
        settings = {'begin_ts': 0, 'end_ts': QDate.currentDate().endOfDay(Qt.UTC).toSecsSinceEpoch(),
                    'peer_id': self._menu_peer_id}
        self._parent.reports.show_report("PeerReportWindow", settings, maximized=True)

    @Slot()
    def replacePeer(self):
        peer_model = PeerTreeModel(self)
        peer_dialog = PeerListDialog(self)
        dialog = SelectReferenceDialog(self, self.tr("Please select peer"),
                                       self.tr("Replace peer '") + self._menu_peer_name + self.tr("' with: "),
                                       peer_model, peer_dialog)
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
        self.table = "categories"
        self.model = CategoryTreeModel(parent_view=self.ui.TreeView)
        self.ui.TreeView.setModel(self.model)
        self.model.configureView()
        self.setup_ui()
        super()._init_completed()
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

    def locateItem(self, item_id):
        self.model.locateItem(item_id)

    def customizeContextMenu(self, menu: QMenu, index):
        self._menu_category_id = self.model.getId(index)
        self._menu_category_name = self.model.getName(index)
        menu.addAction(self.actionShowUsage)
        menu.addAction(self.actionReplace)

    @Slot()
    def showUsageReport(self):
        settings = {'begin_ts': 0, 'end_ts': QDate.currentDate().endOfDay(Qt.UTC).toSecsSinceEpoch(),
                    'category_id': self._menu_category_id}
        self._parent.reports.show_report("CategoryReportWindow", settings, maximized=True)

    @Slot()
    def replaceCategory(self):
        category_model = CategoryTreeModel(self)
        category_dialog = CategoryListDialog(self)
        dialog = SelectReferenceDialog(self, self.tr("Please select category"),
                                       self.tr("Replace category '") + self._menu_category_name + self.tr("' with: "),
                                       category_model, category_dialog)
        if dialog.exec() != QDialog.Accepted:
            return
        JalCategory(self._menu_category_id).replace_with(dialog.selected_id)
        logging.info(self.tr("Category '") + self._menu_category_name + self.tr("' was successfully replaced"))
        self.close()

# ----------------------------------------------------------------------------------------------------------------------
class TagsListDialog(ReferenceDataDialog):
    def __init__(self, parent=None):
        super().__init__(parent, window_title=self.tr("Tags"))
        self.table = "tags"
        self.model = TagTreeModel(parent_view=self.ui.TreeView)
        self.ui.TreeView.setModel(self.model)
        self.model.configureView()
        self.setup_ui()
        super()._init_completed()
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

    def locateItem(self, item_id):
        self.model.locateItem(item_id)

    def customizeContextMenu(self, menu: QMenu, index):
        self._menu_tag_id = self.model.getId(index)
        self._menu_tag_name = self.model.getName(index)
        menu.addAction(self.actionShowUsage)
        menu.addAction(self.actionReplace)

    @Slot()
    def showUsageReport(self):
        settings = {'begin_ts': 0, 'end_ts': QDate.currentDate().endOfDay(Qt.UTC).toSecsSinceEpoch(),
                    'tag_id': self._menu_tag_id}
        self._parent.reports.show_report("TagReportWindow", settings, maximized=True)

    @Slot()
    def replaceTag(self):
        tag_model = TagTreeModel(self)
        tag_dialog = TagsListDialog(self)
        dialog = SelectReferenceDialog(self, self.tr("Please select tag"),
                                       self.tr("Replace tag '") + self._menu_tag_name + self.tr("' with: "),
                                       tag_model, tag_dialog)
        if dialog.exec() != QDialog.Accepted:
            return
        JalTag(self._menu_tag_id).replace_with(dialog.selected_id)
        logging.info(self.tr("Tag '") + self._menu_tag_name + self.tr("' was successfully replaced"))
        self.close()


# ----------------------------------------------------------------------------------------------------------------------
class QuotesListDialog(ReferenceDataDialog):
    def __init__(self, parent=None):
        super().__init__(parent, window_title=self.tr("Quotes"))
        self.table = "quotes"
        self.model = QuotesListModel(parent_view=self.ui.DataView)
        self.ui.DataView.setModel(self.model)
        self.model.configureView()
        self.setup_ui()
        super()._init_completed()

    def setup_ui(self):
        self.search_field = "asset_id-asset_symbol-id-symbol"
        self.ui.SearchFrame.setVisible(True)
        self.ui.Toggle.setVisible(False)


# ----------------------------------------------------------------------------------------------------------------------
class BaseCurrencyDialog(ReferenceDataDialog):
    def __init__(self, parent=None):
        super().__init__(parent, window_title=self.tr("Base currency"))
        self.table = "base_currency"
        self.model = BaseCurrencyListModel(parent_view=self.ui.DataView)
        self.ui.DataView.setModel(self.model)
        self.model.configureView()
        self.setup_ui()
        super()._init_completed()

    def setup_ui(self):
        self.ui.Toggle.setVisible(False)
