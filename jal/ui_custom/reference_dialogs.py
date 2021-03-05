from PySide2.QtSql import QSqlTableModel, QSqlRelationalTableModel, QSqlRelation
from PySide2.QtWidgets import QHeaderView
from jal.db.helpers import db_connection
from jal.widgets.view_delegate import *
from jal.constants import ColumnWidth
from jal.ui_custom.helpers import g_tr
from jal.ui_custom.reference_data import ReferenceDataDialog, ReferenceBoolDelegate, \
    ReferenceLookupDelegate, ReferenceTimestampDelegate, ReferenceTreeDelegate, ReferenceIntDelegate


# ----------------------------------------------------------------------------------------------------------------------
class AccountTypeListModel(QSqlTableModel):
    def __init__(self, table, parent_view):
        self._view = parent_view
        QSqlTableModel.__init__(self, parent=parent_view, db=db_connection())
        self.setTable(table)
        self.setEditStrategy(QSqlTableModel.OnManualSubmit)
        self.setSort(self.fieldIndex("name"), Qt.AscendingOrder)
        self.setHeaderData(self.fieldIndex("name"), Qt.Horizontal, g_tr('ReferenceDataDialog', "Account Type"))

    def configureView(self):
        self._view.setColumnHidden(self.fieldIndex("id"), True)
        self._view.horizontalHeader().setSectionResizeMode(self.fieldIndex("name"), QHeaderView.Stretch)
        font = self._view.horizontalHeader().font()
        font.setBold(True)
        self._view.horizontalHeader().setFont(font)

class AccountTypeListDialog(ReferenceDataDialog):
    def __init__(self):
        self.relations = None

        ReferenceDataDialog.__init__(self)
        self.table = "account_types"
        self.model = AccountTypeListModel(self.table, self.DataView)
        self.DataView.setModel(self.model)
        self.model.configureView()

        self.search_field = None
        self.tree_view = False
        self.setup_ui()
        self.setWindowTitle(g_tr('ReferenceDataDialog', "Account Types"))
        self.Toggle.setVisible(False)

        self.model.select()
        self.setFilter()

# ----------------------------------------------------------------------------------------------------------------------
class AccountListModel(QSqlRelationalTableModel):
    def __init__(self, table, parent_view):
        self._view = parent_view
        self._lookup_delegate = None
        self._timestamp_delegate = None
        self._bool_delegate = None
        QSqlRelationalTableModel.__init__(self, parent=parent_view, db=db_connection())
        self.setJoinMode(QSqlRelationalTableModel.LeftJoin)
        self.setTable(table)
        self.setRelation(self.fieldIndex("type_id"), QSqlRelation("account_types", "id", "name"))
        self.setRelation(self.fieldIndex("currency_id"), QSqlRelation("currencies", "id", "name"))
        self.setRelation(self.fieldIndex("organization_id"), QSqlRelation("agents", "id", "name"))
        self.setRelation(self.fieldIndex("country_id"), QSqlRelation("countries", "id", "code"))
        self.setEditStrategy(QSqlTableModel.OnManualSubmit)
        self.setSort(self.fieldIndex("name"), Qt.AscendingOrder)
        self.setHeaderData(self.fieldIndex("name"), Qt.Horizontal, g_tr('ReferenceDataDialog', "Name"))
        self.setHeaderData(self.fieldIndex("currency_id"), Qt.Horizontal, g_tr('ReferenceDataDialog', "Currency"))
        self.setHeaderData(self.fieldIndex("active"), Qt.Horizontal, g_tr('ReferenceDataDialog', "Act."))
        self.setHeaderData(self.fieldIndex("number"), Qt.Horizontal, g_tr('ReferenceDataDialog', "Account #"))
        self.setHeaderData(self.fieldIndex("reconciled_on"), Qt.Horizontal, g_tr('ReferenceDataDialog', "Reconciled @"))
        self.setHeaderData(self.fieldIndex("organization_id"), Qt.Horizontal, g_tr('ReferenceDataDialog', "Bank"))
        self.setHeaderData(self.fieldIndex("country_id"), Qt.Horizontal, g_tr('ReferenceDataDialog', "CC"))

    def configureView(self):
        self._view.setColumnHidden(self.fieldIndex("id"), True)
        self._view.setColumnHidden(self.fieldIndex("type_id"), True)
        self._view.horizontalHeader().setSectionResizeMode(self.fieldIndex("name"), QHeaderView.Stretch)
        self._view.setColumnWidth(self.fieldIndex("active"), 32)
        self._view.setColumnWidth(self.fieldIndex("reconciled_on"),
                                  self._view.fontMetrics().width("00/00/0000 00:00:00") * 1.1)
        self._view.setColumnWidth(self.fieldIndex("country_id"), 50)
        font = self._view.horizontalHeader().font()
        font.setBold(True)
        self._view.horizontalHeader().setFont(font)

        self._lookup_delegate = ReferenceLookupDelegate(self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("currency_id"), self._lookup_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex("organization_id"), self._lookup_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex("country_id"), self._lookup_delegate)
        self._timestamp_delegate = ReferenceTimestampDelegate(self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("reconciled_on"), self._timestamp_delegate)
        self._bool_delegate = ReferenceBoolDelegate(self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("active"), self._bool_delegate)

class AccountListDialog(ReferenceDataDialog):
    def __init__(self):
        ReferenceDataDialog.__init__(self)
        self.table = "accounts"
        self.model = AccountListModel(self.table, self.DataView)
        self.DataView.setModel(self.model)
        self.model.configureView()
        self.setup_ui()

        self.model.select()
        self.setFilter()

    def setup_ui(self):
        self.search_field = "accounts.name"
        super().setup_ui()
        self.setWindowTitle(g_tr('ReferenceDataDialog', "Accounts"))
        self.Toggle.setVisible(True)
        self.toggle_field = "active"
        self.Toggle.setText(g_tr('ReferenceDataDialog', "Show inactive"))

        self.GroupLbl.setVisible(True)
        self.GroupLbl.setText(g_tr('ReferenceDataDialog', "Account type:"))
        self.GroupCombo.setVisible(True)
        self.group_key_field = "type_id"
        self.group_key_index = self.model.fieldIndex("type_id")
        self.group_fkey_field = "id"
        relation_model = self.model.relationModel(self.group_key_index)
        self.GroupCombo.setModel(relation_model)
        self.GroupCombo.setModelColumn(relation_model.fieldIndex("name"))
        self.group_id = relation_model.data(relation_model.index(0, relation_model.fieldIndex(self.group_fkey_field)))


# ----------------------------------------------------------------------------------------------------------------------
class AssetListModel(QSqlRelationalTableModel):
    def __init__(self, table, parent_view):
        self._view = parent_view
        self._lookup_delegate = None
        QSqlRelationalTableModel.__init__(self, parent=parent_view, db=db_connection())
        self.setJoinMode(QSqlRelationalTableModel.LeftJoin)
        self.setTable(table)
        self.setRelation(self.fieldIndex("type_id"), QSqlRelation("asset_types", "id", "name"))
        self.setRelation(self.fieldIndex("country_id"), QSqlRelation("countries", "id", "name"))
        self.setRelation(self.fieldIndex("src_id"), QSqlRelation("data_sources", "id", "name"))
        self.setEditStrategy(QSqlTableModel.OnManualSubmit)
        self.setSort(self.fieldIndex("name"), Qt.AscendingOrder)
        self.setHeaderData(self.fieldIndex("name"), Qt.Horizontal, g_tr('ReferenceDataDialog', "Symbol"))
        self.setHeaderData(self.fieldIndex("full_name"), Qt.Horizontal, g_tr('ReferenceDataDialog', "Name"))
        self.setHeaderData(self.fieldIndex("isin"), Qt.Horizontal, g_tr('ReferenceDataDialog', "ISIN"))
        self.setHeaderData(self.fieldIndex("country_id"), Qt.Horizontal, g_tr('ReferenceDataDialog', "Country"))
        self.setHeaderData(self.fieldIndex("src_id"), Qt.Horizontal, g_tr('ReferenceDataDialog', "Data source"))

    def configureView(self):
        self._view.setColumnHidden(self.fieldIndex("id"), True)
        self._view.setColumnHidden(self.fieldIndex("type_id"), True)
        self._view.horizontalHeader().setSectionResizeMode(self.fieldIndex("full_name"), QHeaderView.Stretch)
        font = self._view.horizontalHeader().font()
        font.setBold(True)
        self._view.horizontalHeader().setFont(font)

        self._lookup_delegate = ReferenceLookupDelegate(self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("country_id"), self._lookup_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex("src_id"), self._lookup_delegate)

class AssetListDialog(ReferenceDataDialog):
    def __init__(self):
        ReferenceDataDialog.__init__(self)
        self.table = "assets"
        self.model = AssetListModel(self.table, self.DataView)
        self.DataView.setModel(self.model)
        self.model.configureView()
        self.setup_ui()

        self.model.select()
        self.setFilter()

    def setup_ui(self):
        self.search_field = "assets.full_name"
        super().setup_ui()
        self.setWindowTitle(g_tr('ReferenceDataDialog', "Assets"))
        self.Toggle.setVisible(False)

        self.GroupLbl.setVisible(True)
        self.GroupLbl.setText(g_tr('ReferenceDataDialog', "Asset type:"))
        self.GroupCombo.setVisible(True)
        self.group_key_field = "type_id"
        self.group_key_index = self.model.fieldIndex("type_id")
        self.group_fkey_field = "id"
        relation_model = self.model.relationModel(self.group_key_index)
        self.GroupCombo.setModel(relation_model)
        self.GroupCombo.setModelColumn(relation_model.fieldIndex("name"))
        self.group_id = relation_model.data(relation_model.index(0, relation_model.fieldIndex(self.group_fkey_field)))

# ----------------------------------------------------------------------------------------------------------------------
class PeerListModel(QSqlRelationalTableModel):
    def __init__(self, table, parent_view):
        self._view = parent_view
        self._tree_delegate = None
        self._int_delegate = None
        QSqlRelationalTableModel.__init__(self, parent=parent_view, db=db_connection())
        self.setJoinMode(QSqlRelationalTableModel.LeftJoin)
        self.setTable(table)
        self.setEditStrategy(QSqlTableModel.OnManualSubmit)
        self.setSort(self.fieldIndex("name"), Qt.AscendingOrder)
        self.setHeaderData(self.fieldIndex("id"), Qt.Horizontal, " ")
        self.setHeaderData(self.fieldIndex("name"), Qt.Horizontal, g_tr('ReferenceDataDialog', "Name"))
        self.setHeaderData(self.fieldIndex("location"), Qt.Horizontal, g_tr('ReferenceDataDialog', "Location"))
        self.setHeaderData(self.fieldIndex("actions_count"), Qt.Horizontal, g_tr('ReferenceDataDialog', "Docs count"))

    def configureView(self):
        self._view.setColumnHidden(self.fieldIndex("pid"), True)
        self._view.setColumnHidden(self.fieldIndex("children_count"), True)
        self._view.horizontalHeader().setSectionResizeMode(self.fieldIndex("name"), QHeaderView.Stretch)
        self._view.setColumnWidth(self.fieldIndex("id"), 16)
        font = self._view.horizontalHeader().font()
        font.setBold(True)
        self._view.horizontalHeader().setFont(font)

        self._tree_delegate = ReferenceTreeDelegate(self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("id"), self._tree_delegate)
        self._int_delegate = ReferenceIntDelegate(self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("actions_count"), self._bool_delegate)

class PeerListDialog(ReferenceDataDialog):
    def __init__(self):
        ReferenceDataDialog.__init__(self)
        self.table = "agents_ext"
        self.model = CategoryListModel(self.table, self.DataView)
        self.DataView.setModel(self.model)
        self.model.configureView()
        self.setup_ui()

        self.model.select()
        self.setFilter()

    def setup_ui(self):
        self.search_field = "name"
        self.tree_view = True
        super().setup_ui()
        self.setWindowTitle(g_tr('ReferenceDataDialog', "Peers"))
        self.Toggle.setVisible(False)

# ----------------------------------------------------------------------------------------------------------------------
class CategoryListModel(QSqlRelationalTableModel):
    def __init__(self, table, parent_view):
        self._view = parent_view
        self._tree_delegate = None
        self._bool_delegate = None
        QSqlRelationalTableModel.__init__(self, parent=parent_view, db=db_connection())
        self.setJoinMode(QSqlRelationalTableModel.LeftJoin)
        self.setTable(table)
        self.setEditStrategy(QSqlTableModel.OnManualSubmit)
        self.setSort(self.fieldIndex("name"), Qt.AscendingOrder)
        self.setHeaderData(self.fieldIndex("id"), Qt.Horizontal, " ")
        self.setHeaderData(self.fieldIndex("name"), Qt.Horizontal, g_tr('ReferenceDataDialog', "Name"))
        self.setHeaderData(self.fieldIndex("often"), Qt.Horizontal, g_tr('ReferenceDataDialog', "Often"))

    def configureView(self):
        self._view.setColumnHidden(self.fieldIndex("pid"), True)
        self._view.setColumnHidden(self.fieldIndex("special"), True)
        self._view.setColumnHidden(self.fieldIndex("children_count"), True)
        self._view.horizontalHeader().setSectionResizeMode(self.fieldIndex("name"), QHeaderView.Stretch)
        self._view.setColumnWidth(self.fieldIndex("id"), 16)
        font = self._view.horizontalHeader().font()
        font.setBold(True)
        self._view.horizontalHeader().setFont(font)

        self._tree_delegate = ReferenceTreeDelegate(self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("id"), self._tree_delegate)
        self._bool_delegate = ReferenceBoolDelegate(self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("often"), self._bool_delegate)

class CategoryListDialog(ReferenceDataDialog):
    def __init__(self):
        ReferenceDataDialog.__init__(self)
        self.table = "categories_ext"
        self.model = CategoryListModel(self.table, self.DataView)
        self.DataView.setModel(self.model)
        self.model.configureView()
        self.setup_ui()

        self.model.select()
        self.setFilter()

    def setup_ui(self):
        self.search_field = "name"
        self.tree_view = True
        super().setup_ui()
        self.setWindowTitle(g_tr('ReferenceDataDialog', "Categories"))
        self.Toggle.setVisible(False)

# ----------------------------------------------------------------------------------------------------------------------
class TagListModel(QSqlRelationalTableModel):
    def __init__(self, table, parent_view):
        self._view = parent_view
        QSqlRelationalTableModel.__init__(self, parent=parent_view, db=db_connection())
        self.setJoinMode(QSqlRelationalTableModel.LeftJoin)
        self.setTable(table)
        self.setEditStrategy(QSqlTableModel.OnManualSubmit)
        self.setSort(self.fieldIndex("tag"), Qt.AscendingOrder)
        self.setHeaderData(self.fieldIndex("tag"), Qt.Horizontal, g_tr('ReferenceDataDialog', "Tag"))

    def configureView(self):
        self._view.setColumnHidden(self.fieldIndex("id"), True)
        self._view.horizontalHeader().setSectionResizeMode(self.fieldIndex("tag"), QHeaderView.Stretch)
        font = self._view.horizontalHeader().font()
        font.setBold(True)
        self._view.horizontalHeader().setFont(font)

class TagsListDialog(ReferenceDataDialog):
    def __init__(self):
        ReferenceDataDialog.__init__(self)
        self.table = "tags"
        self.model = TagListModel(self.table, self.DataView)
        self.DataView.setModel(self.model)
        self.model.configureView()
        self.setup_ui()

        self.model.select()
        self.setFilter()

    def setup_ui(self):
        self.search_field = "tag"
        self.tree_view = False
        super().setup_ui()
        self.setWindowTitle(g_tr('ReferenceDataDialog', "Tags"))
        self.Toggle.setVisible(False)

# ----------------------------------------------------------------------------------------------------------------------
class CountryListModel(QSqlRelationalTableModel):
    def __init__(self, table, parent_view):
        self._view = parent_view
        self._bool_delegate = None
        QSqlRelationalTableModel.__init__(self, parent=parent_view, db=db_connection())
        self.setJoinMode(QSqlRelationalTableModel.LeftJoin)
        self.setTable(table)
        self.setEditStrategy(QSqlTableModel.OnManualSubmit)
        self.setSort(self.fieldIndex("name"), Qt.AscendingOrder)
        self.setHeaderData(self.fieldIndex("name"), Qt.Horizontal, g_tr('ReferenceDataDialog', "Country"))
        self.setHeaderData(self.fieldIndex("code"), Qt.Horizontal, g_tr('ReferenceDataDialog', "Code"))
        self.setHeaderData(self.fieldIndex("tax_treaty"), Qt.Horizontal, g_tr('ReferenceDataDialog', "Tax Treaty"))

    def configureView(self):
        self._view.setColumnHidden(self.fieldIndex("id"), True)
        self._view.horizontalHeader().setSectionResizeMode(self.fieldIndex("name"), QHeaderView.Stretch)
        self._view.setColumnWidth(self.fieldIndex("code"), 50)
        font = self._view.horizontalHeader().font()
        font.setBold(True)
        self._view.horizontalHeader().setFont(font)

        self._bool_delegate = ReferenceBoolDelegate(self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("tax_treaty"), self._bool_delegate)

class CountryListDialog(ReferenceDataDialog):
    def __init__(self):
        ReferenceDataDialog.__init__(self)
        self.table = "countries"
        self.model = CountryListModel(self.table, self.DataView)
        self.DataView.setModel(self.model)
        self.model.configureView()
        self.setup_ui()

        self.model.select()
        self.setFilter()

    def setup_ui(self):
        self.search_field = "name"
        self.tree_view = False
        super().setup_ui()
        self.setWindowTitle(g_tr('ReferenceDataDialog', "Countries"))
        self.Toggle.setVisible(False)

# ----------------------------------------------------------------------------------------------------------------------
class QuotesListModel(QSqlRelationalTableModel):
    def __init__(self, table, parent_view):
        self._view = parent_view
        self._lookup_delegate = None
        self._timestamp_delegate = None
        QSqlRelationalTableModel.__init__(self, parent=parent_view, db=db_connection())
        self.setJoinMode(QSqlRelationalTableModel.LeftJoin)
        self.setTable(table)
        self.setRelation(self.fieldIndex("asset_id"), QSqlRelation("assets", "id", "name"))
        self.setEditStrategy(QSqlTableModel.OnManualSubmit)
        self.setHeaderData(self.fieldIndex("timestamp"), Qt.Horizontal, g_tr('ReferenceDataDialog', "Date"))
        self.setHeaderData(self.fieldIndex("asset_id"), Qt.Horizontal, g_tr('ReferenceDataDialog', "Asset"))
        self.setHeaderData(self.fieldIndex("quote"), Qt.Horizontal, g_tr('ReferenceDataDialog', "Quote"))

    def configureView(self):
        self._view.setColumnHidden(self.fieldIndex("id"), True)
        self._view.setColumnWidth(self.fieldIndex("timestamp"),
                                  self._view.fontMetrics().width("00/00/0000 00:00:00") * 1.1)
        self._view.setColumnWidth(self.fieldIndex("quote"), 100)
        font = self._view.horizontalHeader().font()
        font.setBold(True)
        self._view.horizontalHeader().setFont(font)

        self._lookup_delegate = ReferenceLookupDelegate(self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("asset_id"), self._lookup_delegate)
        self._timestamp_delegate = ReferenceTimestampDelegate(self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("timestamp"), self._timestamp_delegate)

class QuotesListDialog(ReferenceDataDialog):
    def __init__(self):
        ReferenceDataDialog.__init__(self)
        self.table = "quotes"
        self.model = QuotesListModel(self.table, self.DataView)
        self.DataView.setModel(self.model)
        self.model.configureView()
        self.setup_ui()

        self.model.select()
        self.setFilter()

    def setup_ui(self):
        self.search_field = "name"
        self.tree_view = False
        super().setup_ui()
        self.setWindowTitle(g_tr('ReferenceDataDialog', "Quotes"))
        self.Toggle.setVisible(False)

# ----------------------------------------------------------------------------------------------------------------------

