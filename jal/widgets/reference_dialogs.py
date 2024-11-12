import logging
from PySide6.QtCore import Qt, Slot, QDate
from PySide6.QtGui import QAction
from PySide6.QtSql import QSqlRelation, QSqlRelationalDelegate, QSqlIndex
from PySide6.QtWidgets import QAbstractItemView, QMenu, QDialog, QMessageBox
from jal.constants import PredefinedAsset, MarketDataFeed
from jal.db.account import JalAccount
from jal.db.peer import JalPeer
from jal.db.category import JalCategory
from jal.db.tag import JalTag
from jal.db.reference_models import AbstractReferenceListModel, SqlTreeModel
from jal.widgets.delegates import TimestampDelegate, BoolDelegate, FloatDelegate, PeerSelectorDelegate, \
    AssetSelectorDelegate, ConstantLookupDelegate, TagSelectorDelegate
from jal.widgets.reference_data import ReferenceDataDialog
from jal.widgets.asset_dialog import AssetDialog
from jal.widgets.delegates import GridLinesDelegate
from jal.widgets.selection_dialog import SelectPeerDialog, SelectCategoryDialog, SelectTagDialog
from jal.widgets.icons import JalIcon


# ----------------------------------------------------------------------------------------------------------------------
class AccountListModel(AbstractReferenceListModel):
    def __init__(self, table, parent_view, **kwargs):
        super().__init__(table=table, parent_view=parent_view)
        self._columns = [("id", ''),
                         ("name", self.tr("Name")),
                         ("currency_id", self.tr("Currency")),
                         ("active", self.tr("Act.")),
                         ("investing", self.tr("Invest.")),
                         ("tag_id", 'Tag'),
                         ("number", self.tr("Account #")),
                         ("reconciled_on", self.tr("Reconciled @")),
                         ("organization_id", self.tr("Bank/Broker")),
                         ("country_id", self.tr("Country")),
                         ("precision", self.tr("Precision")),
                         ("credit", self.tr("Credit limit"))]
        self._sort_by = "name"
        self._group_by = "tag_id"
        self._hidden = ["id"]
        self._stretch = "name"
        self._lookup_delegate = None
        self._peer_delegate = None
        self._timestamp_delegate = None
        self._bool_delegate = None
        self._tag_delegate = None
        self._float_delegate = None
        self._default_values = {'active': 1, 'reconciled_on': 0, 'country_id': 0, 'precision': 2, 'credit': '0'}
        self.setRelation(self.fieldIndex("currency_id"), QSqlRelation("currencies", "id", "symbol"))
        self.setRelation(self.fieldIndex("country_id"), QSqlRelation("countries", "id", "code"))

    def data(self, index, role=Qt.DisplayRole):   # Display tag icon as decoration role
        if not index.isValid():
            return None
        if role == Qt.DecorationRole and index.column() == self.fieldIndex('tag_id'):
            return JalIcon[JalTag(super().data(index, Qt.DisplayRole)).icon()]
        return super().data(index, role)

    def configureView(self):
        super().configureView()
        self._view.setColumnWidth(self.fieldIndex("active"), 64)
        self._view.setColumnWidth(self.fieldIndex("investing"), 64)
        self._view.setColumnWidth(self.fieldIndex("reconciled_on"),
                                  self._view.fontMetrics().horizontalAdvance("00/00/0000 00:00:00") * 1.1)
        self._view.setColumnWidth(self.fieldIndex("country_id"), 80)
        self._lookup_delegate = QSqlRelationalDelegate(self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("currency_id"), self._lookup_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex("country_id"), self._lookup_delegate)
        self._peer_delegate = PeerSelectorDelegate()
        self._view.setItemDelegateForColumn(self.fieldIndex("organization_id"), self._peer_delegate)
        self._timestamp_delegate = TimestampDelegate(parent=self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("reconciled_on"), self._timestamp_delegate)
        self._bool_delegate = BoolDelegate(self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("active"), self._bool_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex("investing"), self._bool_delegate)
        self._tag_delegate = TagSelectorDelegate(self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("tag_id"), self._tag_delegate)
        self._float_delegate = FloatDelegate(2, parent=self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("credit"), self._float_delegate)

    def removeElement(self, index) -> bool:
        reply = QMessageBox().warning(None, self.tr("Warning"), self.tr("All transactions related with this account will be deleted.\n"
                                                                        "Do you want to delete the account anyway?"),
                                      QMessageBox.Yes, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return False
        return super().removeElement(index)


class AccountListDialog(ReferenceDataDialog):
    def __init__(self, parent=None):
        super().__init__(parent=parent, window_title=self.tr("Accounts"))
        self.table = "accounts"
        self.model = AccountListModel(table=self.table, parent_view=self.ui.DataView)
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


# ----------------------------------------------------------------------------------------------------------------------
class AssetListModel(AbstractReferenceListModel):
    def __init__(self, table, parent_view, **kwargs):
        super().__init__(table=table, parent_view=parent_view)
        pk = QSqlIndex()   # Manual primary key setup is required as we use underlying sql view instead of sql table
        pk.append(self.record().field("id"))
        self.setPrimaryKey(pk)
        self._columns = [("id", ''),
                         ("type_id", ''),
                         ("symbol", self.tr("Symbol")),
                         ("full_name", self.tr("Name")),
                         ("isin", self.tr("ISIN")),
                         ("currency_id", self.tr("Currency")),
                         ("country_id", self.tr("Country")),
                         ("quote_source", self.tr("Data source"))]
        self._default_name = "symbol"
        self._sort_by = "symbol"
        self._group_by = "type_id"
        self._hidden = ["id", "type_id"]
        self._stretch = "full_name"
        self._lookup_delegate = None
        self._constant_lookup_delegate = None
        self._default_values = {'isin': '', 'country_id': 0, 'quote_source': -1}
        self.setRelation(self.fieldIndex("currency_id"), QSqlRelation("currencies", "id", "symbol"))
        self.setRelation(self.fieldIndex("country_id"), QSqlRelation("countries_ext", "id", "name"))

    def configureView(self):
        super().configureView()
        self._lookup_delegate = QSqlRelationalDelegate(self._view)
        self._constant_lookup_delegate = ConstantLookupDelegate(MarketDataFeed, self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("country_id"), self._lookup_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex("quote_source"), self._constant_lookup_delegate)

    def removeElement(self, index) -> bool:
        used_by_accounts = JalAccount().get_all_accounts(active_only=False, currency_id=self.getId(index))
        if len(used_by_accounts):
            QMessageBox().warning(None, self.tr("Warning"),
                                  self.tr("You can't delete currency that is used by account:\n") +
                                  '\n'.join([x.name() for i, x in enumerate(used_by_accounts) if i < 10]),  # Display first 10 accounts that use the currency
                                  QMessageBox.Ok)
            return False
        reply = QMessageBox().warning(None, self.tr("Warning"),
                                      self.tr("All transactions related with this asset will be deleted.\n"
                                              "Do you want to delete the asset anyway?"),
                                      QMessageBox.Yes, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return False
        return super().removeElement(index)


class AssetListDialog(ReferenceDataDialog):
    def __init__(self, parent=None):
        super().__init__(parent=parent, window_title=self.tr("Assets"))
        self.table = "assets_ext"
        self.model = AssetListModel(self.table, self.ui.DataView)
        self.ui.DataView.setModel(self.model)
        self.model.configureView()
        self.setup_ui()
        super()._init_completed()

    def setup_ui(self):
        self.search_field = "assets_ext.full_name"
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

    def customEditor(self):
        return AssetDialog(self)


# ----------------------------------------------------------------------------------------------------------------------
class PeerTreeModel(SqlTreeModel):
    def __init__(self, table, parent_view, **kwargs):
        super().__init__(table=table, parent_view=parent_view)
        self._columns = [("name", self.tr("Name")),
                         ("location", self.tr("Location")),
                         ("actions_count", self.tr("Docs count"))]
        self._default_value = self.tr("New peer")
        self._sort_by = "name"
        self._stretch = "name"
        self._int_delegate = None
        self._grid_delegate = None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        item_id = index.internalId()
        if role == Qt.DisplayRole or role == Qt.EditRole:
            if index.column() == self.fieldIndex("actions_count"):
                return JalPeer(item_id).number_of_documents()
            else:
                return super().data(index, role)
        return None

    def configureView(self):
        super().configureView()
        self._grid_delegate = GridLinesDelegate(self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("name"), self._grid_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex("location"), self._grid_delegate)
        self._int_delegate = FloatDelegate(0, parent=self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("actions_count"), self._int_delegate)

    def removeElement(self, index) -> bool:
        peer = JalPeer(self.getId(index))
        if peer.is_predefined():
            QMessageBox().warning(None, self.tr("Warning"), self.tr("You can't delete a predefined peer."), QMessageBox.Ok)
            return False
        if peer.is_in_use():
            reply = QMessageBox().warning(None, self.tr("Warning"), self.tr("Peer or one of its child peers are in use.\n"
                                                                            "All related transactions will be deleted together with the peer.\n"
                                                                            "Do you want to delete the peer anyway?"),
                                          QMessageBox.Yes, QMessageBox.No)
            if reply != QMessageBox.Yes:
                return False
        return super().removeElement(index)


class PeerListDialog(ReferenceDataDialog):
    def __init__(self, parent=None):
        super().__init__(parent=parent, window_title=self.tr("Peers"))
        self.table = "agents"
        self.model = PeerTreeModel(self.table, self.ui.TreeView)
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
        dialog = SelectPeerDialog(self.tr("Replace peer '") + self._menu_peer_name + self.tr("' with: "))
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
class CategoryTreeModel(SqlTreeModel):
    def __init__(self, table, parent_view, **kwargs):
        super().__init__(table=table, parent_view=parent_view)
        self._columns = [("name", self.tr("Name"))]
        self._default_value = self.tr("New category")
        self._sort_by = "name"
        self._stretch = "name"
        self._bool_delegate = None
        self._grid_delegate = None

    def configureView(self):
        super().configureView()
        self._grid_delegate = GridLinesDelegate(self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("name"), self._grid_delegate)

    def removeElement(self, index) -> bool:
        category = JalCategory(self.getId(index))
        if category.is_predefined():
            QMessageBox().warning(None, self.tr("Warning"), self.tr("You can't delete a predefined category."), QMessageBox.Ok)
            return False
        if category.is_in_use():
            reply = QMessageBox().warning(None, self.tr("Warning"), self.tr("Category or one of its subcategories are in use.\n"
                                                                            "All related transactions will be deleted together with the category.\n"
                                                                            "Do you want to delete the category anyway?"),
                                          QMessageBox.Yes, QMessageBox.No)
            if reply != QMessageBox.Yes:
                return False
        return super().removeElement(index)


class CategoryListDialog(ReferenceDataDialog):
    def __init__(self, parent=None):
        super().__init__(parent=parent, window_title=self.tr("Categories"))
        self.table = "categories"
        self.model = CategoryTreeModel(self.table, self.ui.TreeView)
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
        dialog = SelectCategoryDialog(parent=self,
                                      description=self.tr("Replace category '") + self._menu_category_name + self.tr("' with: "))
        if dialog.exec() != QDialog.Accepted:
            return
        JalCategory(self._menu_category_id).replace_with(dialog.selected_id)
        logging.info(self.tr("Category '") + self._menu_category_name + self.tr("' was successfully replaced"))
        self.close()

# ----------------------------------------------------------------------------------------------------------------------
class TagTreeModel(SqlTreeModel):
    def __init__(self, table, parent_view, **kwargs):
        super().__init__(table=table, parent_view=parent_view)
        self._columns = [("tag", self.tr("Tag")), ("icon_file", self.tr("Icon filename"))]
        self._default_value = self.tr("New tag")
        self._default_name = "tag"
        self._sort_by = "tag"
        self._stretch = "tag"

    def data(self, index, role=Qt.DisplayRole):   # Display tag icon as decoration role
        if not index.isValid():
            return None
        if role == Qt.DecorationRole and index.column() == self.fieldIndex('icon_file'):
            return JalIcon[super().data(index, Qt.DisplayRole)]
        return super().data(index, role)

    def configureView(self):
        super().configureView()
        self._grid_delegate = GridLinesDelegate(self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("tag"), self._grid_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex("icon_file"), self._grid_delegate)

class TagsListDialog(ReferenceDataDialog):
    def __init__(self, parent=None):
        super().__init__(parent, window_title=self.tr("Tags"))
        self.table = "tags"
        self.model = TagTreeModel(self.table, self.ui.TreeView)
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
        dialog = SelectTagDialog(parent=self,
                                 description=self.tr("Replace tag '") + self._menu_tag_name + self.tr("' with: "))
        if dialog.exec() != QDialog.Accepted:
            return
        JalTag(self._menu_tag_id).replace_with(dialog.selected_id)
        logging.info(self.tr("Tag '") + self._menu_tag_name + self.tr("' was successfully replaced"))
        self.close()


# ----------------------------------------------------------------------------------------------------------------------
class QuotesListModel(AbstractReferenceListModel):
    def __init__(self, table, parent_view):
        super().__init__(table=table, parent_view=parent_view)
        self._columns = [("id", ''),
                         ("timestamp", self.tr("Date")),
                         ("asset_id", self.tr("Asset")),
                         ("currency_id", self.tr("Currency")),
                         ("quote", self.tr("Quote"))]
        self._hidden = ["id"]
        self._default_name = "quote"
        self._sort_by = "timestamp"
        self._stretch = "asset_id"
        self._asset_delegate = None
        self._timestamp_delegate = None
        self._lookup_delegate = None
        self._float_delegate = None
        self.setRelation(self.fieldIndex("currency_id"), QSqlRelation("currencies", "id", "symbol"))

    def configureView(self):
        super().configureView()
        self._view.setColumnWidth(self.fieldIndex("timestamp"),
                                  self._view.fontMetrics().horizontalAdvance("00/00/0000 00:00:00") * 1.1)
        self._view.setColumnWidth(self.fieldIndex("quote"), 100)

        self._asset_delegate = AssetSelectorDelegate()
        self._view.setItemDelegateForColumn(self.fieldIndex("asset_id"), self._asset_delegate)
        self._timestamp_delegate = TimestampDelegate(parent=self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("timestamp"), self._timestamp_delegate)
        self._lookup_delegate = QSqlRelationalDelegate(self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("currency_id"), self._lookup_delegate)
        self._float_delegate = FloatDelegate(4, allow_tail=True, parent=self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("quote"), self._float_delegate)


class QuotesListDialog(ReferenceDataDialog):
    def __init__(self, parent=None):
        super().__init__(parent, window_title=self.tr("Quotes"))
        self.table = "quotes"
        self.model = QuotesListModel(self.table, self.ui.DataView)
        self.ui.DataView.setModel(self.model)
        self.model.configureView()
        self.setup_ui()
        super()._init_completed()

    def setup_ui(self):
        self.search_field = "asset_id-assets_ext-id-symbol"
        self.ui.SearchFrame.setVisible(True)
        self.ui.Toggle.setVisible(False)


# ----------------------------------------------------------------------------------------------------------------------
class BaseCurrencyListModel(AbstractReferenceListModel):
    def __init__(self, table, parent_view):
        super().__init__(table=table, parent_view=parent_view)
        self._columns = [("id", ''),
                         ("since_timestamp", self.tr("Date")),
                         ("currency_id", self.tr("Currency"))]
        self._hidden = ["id"]
        self._sort_by = "since_timestamp"
        self._default_name = "currency_id"
        self._timestamp_delegate = None
        self._lookup_delegate = None
        self.setRelation(self.fieldIndex("currency_id"), QSqlRelation("currencies", "id", "symbol"))

    def configureView(self):
        super().configureView()
        self._view.setColumnWidth(self.fieldIndex("since_timestamp"),
                                  self._view.fontMetrics().horizontalAdvance("00/00/0000") * 1.1)
        self._view.setColumnWidth(self.fieldIndex("currency_id"), 100)

        self._timestamp_delegate = TimestampDelegate(display_format='%d/%m/%Y', parent=self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("since_timestamp"), self._timestamp_delegate)
        self._lookup_delegate = QSqlRelationalDelegate(self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("currency_id"), self._lookup_delegate)


class BaseCurrencyDialog(ReferenceDataDialog):
    def __init__(self, parent=None):
        super().__init__(None, window_title=self.tr("Base currency"))
        self.table = "base_currency"
        self.model = BaseCurrencyListModel(self.table, self.ui.DataView)
        self.ui.DataView.setModel(self.model)
        self.model.configureView()
        self.setup_ui()
        super()._init_completed()

    def setup_ui(self):
        self.ui.Toggle.setVisible(False)

# ----------------------------------------------------------------------------------------------------------------------
