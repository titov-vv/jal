from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtSql import QSqlRelation, QSqlRelationalDelegate, QSqlIndex
from PySide6.QtWidgets import QToolBar, QAbstractItemView
from jal.constants import PredefindedAccountType, PredefinedAsset
from jal.db.helpers import readSQL
from jal.db.reference_models import AbstractReferenceListModel, SqlTreeModel
from jal.widgets.delegates import TimestampDelegate, BoolDelegate, FloatDelegate, \
    PeerSelectorDelegate, AssetSelectorDelegate
from jal.widgets.reference_data import ReferenceDataDialog
from jal.widgets.asset_dialog import AssetDialog
from jal.widgets.delegates import GridLinesDelegate
from jal.net.downloader import QuoteDownloader


# ----------------------------------------------------------------------------------------------------------------------
class AccountListModel(AbstractReferenceListModel):
    def __init__(self, table, parent_view):
        AbstractReferenceListModel.__init__(self, table, parent_view)
        self._columns = [("id", ''),
                         ("type_id", ''),
                         ("name", self.tr("Name")),
                         ("currency_id", self.tr("Currency")),
                         ("active", self.tr("Act.")),
                         ("number", self.tr("Account #")),
                         ("reconciled_on", self.tr("Reconciled @")),
                         ("organization_id", self.tr("Bank/Broker")),
                         ("country_id", self.tr("CC"))]
        self._sort_by = "name"
        self._group_by = "type_id"
        self._hidden = ["id", "type_id"]
        self._stretch = "name"
        self._lookup_delegate = None
        self._peer_delegate = None
        self._timestamp_delegate = None
        self._bool_delegate = None
        self._default_values = {'active': 1, 'reconciled_on': 0, 'country_id': 0}
        self.setRelation(self.fieldIndex("currency_id"), QSqlRelation("currencies", "id", "symbol"))
        self.setRelation(self.fieldIndex("country_id"), QSqlRelation("countries", "id", "code"))

    def configureView(self):
        super().configureView()
        self._view.setColumnWidth(self.fieldIndex("active"), 32)
        self._view.setColumnWidth(self.fieldIndex("reconciled_on"),
                                  self._view.fontMetrics().horizontalAdvance("00/00/0000 00:00:00") * 1.1)
        self._view.setColumnWidth(self.fieldIndex("country_id"), 50)

        self._lookup_delegate = QSqlRelationalDelegate(self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("currency_id"), self._lookup_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex("country_id"), self._lookup_delegate)
        self._peer_delegate = PeerSelectorDelegate()
        self._view.setItemDelegateForColumn(self.fieldIndex("organization_id"), self._peer_delegate)
        self._timestamp_delegate = TimestampDelegate(parent=self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("reconciled_on"), self._timestamp_delegate)
        self._bool_delegate = BoolDelegate(self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("active"), self._bool_delegate)

    def getAccountType(self, item_id: int) -> int:
        type_id = readSQL(f"SELECT type_id FROM {self._table} WHERE id=:id", [(":id", item_id)])
        type_id = 0 if type_id is None else type_id
        return type_id

    def locateItem(self, item_id, use_filter=''):
        row = readSQL(f"SELECT row_number FROM ("
                      f"SELECT ROW_NUMBER() OVER (ORDER BY {self._default_name}) AS row_number, id "
                      f"FROM {self._table} WHERE {use_filter}) WHERE id=:id", [(":id", item_id)])
        if row is None:
            return QModelIndex()
        return self.index(row-1, 0)


class AccountListDialog(ReferenceDataDialog):
    def __init__(self):
        ReferenceDataDialog.__init__(self)
        self.table = "accounts"
        self.model = AccountListModel(self.table, self.DataView)
        self.DataView.setModel(self.model)
        self.model.configureView()
        self.setup_ui()
        super()._init_completed()

    def setup_ui(self):
        self.search_field = "accounts.name"
        self.setWindowTitle(self.tr("Accounts"))
        self.SearchFrame.setVisible(True)
        self.Toggle.setVisible(True)
        self.toggle_field = "active"
        self.Toggle.setText(self.tr("Show inactive"))

        self.GroupLbl.setVisible(True)
        self.GroupLbl.setText(self.tr("Account type:"))
        self.GroupCombo.setVisible(True)
        self.group_field = self.model.group_by
        PredefindedAccountType().load2combo(self.GroupCombo)
        self.group_id = 1

    def locateItem(self, item_id):
        type_id = self.model.getAccountType(item_id)
        if type_id == 0:
            return
        self.GroupCombo.setCurrentIndex(type_id-1)
        item_idx = self.model.locateItem(item_id, use_filter=self._filter_text)
        self.DataView.setCurrentIndex(item_idx)


# ----------------------------------------------------------------------------------------------------------------------
class AssetListModel(AbstractReferenceListModel):
    def __init__(self, table, parent_view):
        AbstractReferenceListModel.__init__(self, table, parent_view)
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
        self._timestamp_delegate = None
        self._default_values = {'isin': '', 'country_id': 0, 'quote_source': -1}
        self.setRelation(self.fieldIndex("currency_id"), QSqlRelation("currencies", "id", "symbol"))
        self.setRelation(self.fieldIndex("country_id"), QSqlRelation("countries", "id", "name"))
        self.setRelation(self.fieldIndex("quote_source"), QSqlRelation("data_sources", "id", "name"))

    def configureView(self):
        super().configureView()
        self._lookup_delegate = QSqlRelationalDelegate(self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("country_id"), self._lookup_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex("quote_source"), self._lookup_delegate)

    def getAssetType(self, item_id: int) -> int:
        type_id = readSQL(f"SELECT type_id FROM {self._table} WHERE id=:id", [(":id", item_id)])
        type_id = 0 if type_id is None else type_id
        return type_id

    def locateItem(self, item_id, use_filter=''):
        row = readSQL(f"SELECT row_number FROM ("
                      f"SELECT ROW_NUMBER() OVER (ORDER BY {self._default_name}) AS row_number, id "
                      f"FROM {self._table} WHERE {use_filter}) WHERE id=:id", [(":id", item_id)])
        if row is None:
            return QModelIndex()
        return self.index(row-1, 0)


class AssetListDialog(ReferenceDataDialog):
    def __init__(self):
        ReferenceDataDialog.__init__(self)
        self.table = "assets_ext"
        self.model = AssetListModel(self.table, self.DataView)
        self.DataView.setModel(self.model)
        self.model.configureView()
        self.setup_ui()
        super()._init_completed()

    def setup_ui(self):
        self.search_field = "assets_ext.full_name"
        self.setWindowTitle(self.tr("Assets"))
        self.SearchFrame.setVisible(True)
        self.Toggle.setVisible(False)

        self.custom_editor = True
        self.DataView.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self.GroupLbl.setVisible(True)
        self.GroupLbl.setText(self.tr("Asset type:"))
        self.GroupCombo.setVisible(True)
        self.group_field = self.model.group_by
        PredefinedAsset().load2combo(self.GroupCombo)
        self.group_id = 1

        self.toolbar = QToolBar(self)
        self.search_layout.addWidget(self.toolbar)
        action = self.toolbar.addAction(self.tr("Update data"))
        action.setToolTip(self.tr("Update assets data from their exchanges"))
        action.triggered.connect(self.updateExchangeData)

    def locateItem(self, item_id):
        type_id = self.model.getAssetType(item_id)
        if type_id == 0:
            return
        self.GroupCombo.setCurrentIndex(type_id-1)
        item_idx = self.model.locateItem(item_id, use_filter=self._filter_text)
        self.DataView.setCurrentIndex(item_idx)

    def updateExchangeData(self):
        QuoteDownloader().updataData()

    def customEditor(self):
        return AssetDialog()


# ----------------------------------------------------------------------------------------------------------------------
class PeerTreeModel(SqlTreeModel):
    def __init__(self, table, parent_view):
        super().__init__(table, parent_view)
        self._columns = [("name", self.tr("Name")),
                         ("location", self.tr("Location")),
                         ("actions_count", self.tr("Docs count"))]
        self._stretch = "name"
        self._int_delegate = None
        self._grid_delegate = None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        item_id = index.internalId()
        if role == Qt.DisplayRole:
            if index.column() == 2:
                return readSQL("SELECT COUNT(d.id) FROM agents AS p "
                               "LEFT JOIN actions AS d ON d.peer_id=p.id WHERE p.id=:id", [(":id", item_id)])
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


class PeerListDialog(ReferenceDataDialog):
    def __init__(self):
        ReferenceDataDialog.__init__(self)
        self.table = "agents"
        self.model = PeerTreeModel(self.table, self.TreeView)
        self.TreeView.setModel(self.model)
        self.model.configureView()
        self.setup_ui()
        super()._init_completed()

    def setup_ui(self):
        self.search_field = "name"
        self.tree_view = True
        self.AddChildBtn.setVisible(True)
        self.SearchFrame.setVisible(True)
        self.setWindowTitle(self.tr("Peers"))
        self.Toggle.setVisible(False)

    def locateItem(self, item_id):
        self.model.locateItem(item_id)


# ----------------------------------------------------------------------------------------------------------------------
class CategoryTreeModel(SqlTreeModel):
    def __init__(self, table, parent_view):
        super().__init__(table, parent_view)
        self._columns = [("name", self.tr("Name")),
                         ("often", self.tr("Often"))]
        self._stretch = "name"
        self._bool_delegate = None
        self._grid_delegate = None

    def configureView(self):
        super().configureView()
        self._grid_delegate = GridLinesDelegate(self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("name"), self._grid_delegate)
        self._bool_delegate = BoolDelegate(self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("often"), self._bool_delegate)


class CategoryListDialog(ReferenceDataDialog):
    def __init__(self):
        ReferenceDataDialog.__init__(self)
        self.table = "categories"
        self.model = CategoryTreeModel(self.table, self.TreeView)
        self.TreeView.setModel(self.model)
        self.model.configureView()
        self.setup_ui()
        super()._init_completed()

    def setup_ui(self):
        self.search_field = "name"
        self.tree_view = True
        self.AddChildBtn.setVisible(True)
        self.SearchFrame.setVisible(True)
        self.setWindowTitle(self.tr("Categories"))
        self.Toggle.setVisible(False)

    def locateItem(self, item_id):
        self.model.locateItem(item_id)

# ----------------------------------------------------------------------------------------------------------------------
class TagListModel(AbstractReferenceListModel):
    def __init__(self, table, parent_view):
        AbstractReferenceListModel.__init__(self, table, parent_view)
        self._columns = [("id", ''),
                         ("tag", self.tr("Tag"))]
        self._default_name = "tag"
        self._sort_by = "tag"
        self._hidden = ["id"]
        self._stretch = "tag"

    def locateItem(self, item_id, use_filter=''):
        row = readSQL(f"SELECT row_number FROM (SELECT ROW_NUMBER() OVER (ORDER BY tag) AS row_number, id "
                      f"FROM {self._table}) WHERE id=:id", [(":id", item_id)])
        if row is None:
            return QModelIndex()
        return self.index(row - 1, 0)


class TagsListDialog(ReferenceDataDialog):
    def __init__(self):
        ReferenceDataDialog.__init__(self)
        self.table = "tags"
        self.model = TagListModel(self.table, self.DataView)
        self.DataView.setModel(self.model)
        self.model.configureView()
        self.setup_ui()
        super()._init_completed()

    def setup_ui(self):
        self.search_field = "tag"
        self.setWindowTitle(self.tr("Tags"))
        self.SearchFrame.setVisible(True)
        self.Toggle.setVisible(False)

    def locateItem(self, item_id):
        item_idx = self.model.locateItem(item_id)
        self.DataView.setCurrentIndex(item_idx)


# ----------------------------------------------------------------------------------------------------------------------
class CountryListModel(AbstractReferenceListModel):
    def __init__(self, table, parent_view):
        AbstractReferenceListModel.__init__(self, table, parent_view)
        self._columns = [("id", ''),
                         ("name", self.tr("Country")),
                         ("code", self.tr("Code")),
                         ("iso_code", self.tr("ISO code")),
                         ("tax_treaty", self.tr("Tax Treaty"))]
        self._sort_by = "name"
        self._hidden = ["id"]
        self._stretch = "name"
        self._default_values = {'tax_treaty': 0}
        self._bool_delegate = None

    def configureView(self):
        super().configureView()
        self._view.setColumnWidth(self.fieldIndex("code"), 50)

        self._bool_delegate = BoolDelegate(self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("tax_treaty"), self._bool_delegate)


class CountryListDialog(ReferenceDataDialog):
    def __init__(self):
        ReferenceDataDialog.__init__(self)
        self.table = "countries"
        self.model = CountryListModel(self.table, self.DataView)
        self.DataView.setModel(self.model)
        self.model.configureView()
        self.setup_ui()
        super()._init_completed()

    def setup_ui(self):
        self.search_field = "name"
        self.SearchFrame.setVisible(True)
        self.setWindowTitle(self.tr("Countries"))
        self.Toggle.setVisible(False)


# ----------------------------------------------------------------------------------------------------------------------
class QuotesListModel(AbstractReferenceListModel):
    def __init__(self, table, parent_view):
        AbstractReferenceListModel.__init__(self, table, parent_view)
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


class QuotesListDialog(ReferenceDataDialog):
    def __init__(self):
        ReferenceDataDialog.__init__(self)
        self.table = "quotes"
        self.model = QuotesListModel(self.table, self.DataView)
        self.DataView.setModel(self.model)
        self.model.configureView()
        self.setup_ui()
        super()._init_completed()

    def setup_ui(self):
        self.search_field = "asset_id-assets_ext-id-symbol"
        self.SearchFrame.setVisible(True)
        self.setWindowTitle(self.tr("Quotes"))
        self.Toggle.setVisible(False)

# ----------------------------------------------------------------------------------------------------------------------
