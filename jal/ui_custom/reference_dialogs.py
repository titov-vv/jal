from PySide2.QtSql import QSqlTableModel, QSqlRelationalTableModel, QSqlRelation
from PySide2.QtWidgets import QHeaderView
from jal.db.helpers import db_connection
from jal.widgets.view_delegate import *
from jal.ui_custom.helpers import g_tr
from jal.ui_custom.reference_data import ReferenceDataDialog, ReferenceBoolDelegate, \
    ReferenceLookupDelegate, ReferenceTimestampDelegate, ReferenceTreeDelegate, ReferenceIntDelegate


# ----------------------------------------------------------------------------------------------------------------------
class AbstractReferenceListModel(QSqlRelationalTableModel):
    def __init__(self, table, parent_view):
        self._view = parent_view
        self._columns = []
        self._sort_by = None
        self._hidden = []
        self._stretch = None
        QSqlRelationalTableModel.__init__(self, parent=parent_view, db=db_connection())
        self.setJoinMode(QSqlRelationalTableModel.LeftJoin)
        self.setTable(table)
        self.setEditStrategy(QSqlTableModel.OnManualSubmit)

    def configureView(self):
        self.setColumnNames()
        self.setSorting()
        self.hideColumns()
        self.setStretching()
        font = self._view.horizontalHeader().font()
        font.setBold(True)
        self._view.horizontalHeader().setFont(font)

    def setColumnNames(self):
        for column in self._columns:
            self.setHeaderData(self.fieldIndex(column[0]), Qt.Horizontal, column[1])

    def setSorting(self):
        if self._sort_by:
            self.setSort(self.fieldIndex(self._sort_by), Qt.AscendingOrder)

    def hideColumns(self):
        for column_name in self._hidden:
            self._view.setColumnHidden(self.fieldIndex(column_name), True)

    def setStretching(self):
        if self._stretch:
            self._view.horizontalHeader().setSectionResizeMode(self.fieldIndex(self._stretch), QHeaderView.Stretch)

# ----------------------------------------------------------------------------------------------------------------------
class AccountTypeListModel(AbstractReferenceListModel):
    def __init__(self, table, parent_view):
        AbstractReferenceListModel.__init__(self, table, parent_view)
        self._columns = [("name", g_tr('ReferenceDataDialog', "Account Type"))]
        self._sort_by = "name"
        self._hidden = ["id"]
        self._stretch = "name"

    def configureView(self):
        super().configureView()

class AccountTypeListDialog(ReferenceDataDialog):
    def __init__(self):
        ReferenceDataDialog.__init__(self)
        self.table = "account_types"
        self.model = AccountTypeListModel(self.table, self.DataView)
        self.DataView.setModel(self.model)
        self.model.configureView()

        self.setWindowTitle(g_tr('ReferenceDataDialog', "Account Types"))
        self.Toggle.setVisible(False)
        super()._init_completed()

# ----------------------------------------------------------------------------------------------------------------------
class AccountListModel(AbstractReferenceListModel):
    def __init__(self, table, parent_view):
        AbstractReferenceListModel.__init__(self, table, parent_view)
        self._columns = [("name", g_tr('ReferenceDataDialog', "Name")),
                         ("currency_id", g_tr('ReferenceDataDialog', "Currency")),
                         ("active", g_tr('ReferenceDataDialog', "Act.")),
                         ("number", g_tr('ReferenceDataDialog', "Account #")),
                         ("reconciled_on", g_tr('ReferenceDataDialog', "Reconciled @")),
                         ("organization_id", g_tr('ReferenceDataDialog', "Bank")),
                         ("country_id", g_tr('ReferenceDataDialog', "CC"))]
        self._sort_by = "name"
        self._hidden = ["id", "type_id"]
        self._stretch = "name"
        self._lookup_delegate = None
        self._timestamp_delegate = None
        self._bool_delegate = None
        self.setRelation(self.fieldIndex("type_id"), QSqlRelation("account_types", "id", "name"))
        self.setRelation(self.fieldIndex("currency_id"), QSqlRelation("currencies", "id", "name"))
        self.setRelation(self.fieldIndex("organization_id"), QSqlRelation("agents", "id", "name"))
        self.setRelation(self.fieldIndex("country_id"), QSqlRelation("countries", "id", "code"))

    def configureView(self):
        super().configureView()
        self._view.setColumnWidth(self.fieldIndex("active"), 32)
        self._view.setColumnWidth(self.fieldIndex("reconciled_on"),
                                  self._view.fontMetrics().width("00/00/0000 00:00:00") * 1.1)
        self._view.setColumnWidth(self.fieldIndex("country_id"), 50)

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
        super()._init_completed()

    def setup_ui(self):
        self.search_field = "accounts.name"
        self.setWindowTitle(g_tr('ReferenceDataDialog', "Accounts"))
        self.SearchFrame.setVisible(True)
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
class AssetListModel(AbstractReferenceListModel):
    def __init__(self, table, parent_view):
        AbstractReferenceListModel.__init__(self, table, parent_view)
        self._columns = [("name", g_tr('ReferenceDataDialog', "Symbol")),
                         ("full_name", g_tr('ReferenceDataDialog', "Name")),
                         ("isin", g_tr('ReferenceDataDialog', "ISIN")),
                         ("country_id", g_tr('ReferenceDataDialog', "Country")),
                         ("src_id", g_tr('ReferenceDataDialog', "Data source"))]
        self._sort_by = "name"
        self._hidden = ["id", "type_id"]
        self._stretch = "full_name"
        self._lookup_delegate = None
        self.setRelation(self.fieldIndex("type_id"), QSqlRelation("asset_types", "id", "name"))
        self.setRelation(self.fieldIndex("country_id"), QSqlRelation("countries", "id", "name"))
        self.setRelation(self.fieldIndex("src_id"), QSqlRelation("data_sources", "id", "name"))

    def configureView(self):
        super().configureView()
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
        super()._init_completed()

    def setup_ui(self):
        self.search_field = "assets.full_name"
        self.setWindowTitle(g_tr('ReferenceDataDialog', "Assets"))
        self.SearchFrame.setVisible(True)
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
class PeerListModel(AbstractReferenceListModel):
    def __init__(self, table, parent_view):
        AbstractReferenceListModel.__init__(self, table, parent_view)
        self._columns = [("id", " "),
                         ("name", g_tr('ReferenceDataDialog', "Name")),
                         ("location", g_tr('ReferenceDataDialog', "Location")),
                         ("actions_count", g_tr('ReferenceDataDialog', "Docs count"))]
        self._sort_by = "name"
        self._hidden = ["pid", "children_count"]
        self._stretch = "name"
        self._tree_delegate = None
        self._int_delegate = None

    def configureView(self):
        super().configureView()
        self._view.setColumnWidth(self.fieldIndex("id"), 16)

        self._tree_delegate = ReferenceTreeDelegate(self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("id"), self._tree_delegate)
        self._int_delegate = ReferenceIntDelegate(self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("actions_count"), self._int_delegate)

class PeerListDialog(ReferenceDataDialog):
    def __init__(self):
        ReferenceDataDialog.__init__(self)
        self.table = "agents_ext"
        self.model = PeerListModel(self.table, self.DataView)
        self.DataView.setModel(self.model)
        self.model.configureView()
        self.setup_ui()
        super()._init_completed()

    def setup_ui(self):
        self.search_field = "name"
        self.tree_view = True
        self.SearchFrame.setVisible(True)
        self.UpBtn.setVisible(True)
        self.setWindowTitle(g_tr('ReferenceDataDialog', "Peers"))
        self.Toggle.setVisible(False)

# ----------------------------------------------------------------------------------------------------------------------
class CategoryListModel(AbstractReferenceListModel):
    def __init__(self, table, parent_view):
        AbstractReferenceListModel.__init__(self, table, parent_view)
        self._columns = [("id", " "),
                         ("name", g_tr('ReferenceDataDialog', "Name")),
                         ("often", g_tr('ReferenceDataDialog', "Often"))]
        self._sort_by = "name"
        self._hidden = ["pid", "special", "children_count"]
        self._stretch = "name"
        self._tree_delegate = None
        self._bool_delegate = None

    def configureView(self):
        super().configureView()
        self._view.setColumnWidth(self.fieldIndex("id"), 16)

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
        super()._init_completed()

    def setup_ui(self):
        self.search_field = "name"
        self.tree_view = True
        self.SearchFrame.setVisible(True)
        self.UpBtn.setVisible(True)
        self.setWindowTitle(g_tr('ReferenceDataDialog', "Categories"))
        self.Toggle.setVisible(False)

# ----------------------------------------------------------------------------------------------------------------------
class TagListModel(AbstractReferenceListModel):
    def __init__(self, table, parent_view):
        AbstractReferenceListModel.__init__(self, table, parent_view)
        self._columns = [("tag", g_tr('ReferenceDataDialog', "Tag"))]
        self._sort_by = "tag"
        self._hidden = ["id"]
        self._stretch = "tag"

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
        self.setWindowTitle(g_tr('ReferenceDataDialog', "Tags"))
        self.SearchFrame.setVisible(True)
        self.Toggle.setVisible(False)

# ----------------------------------------------------------------------------------------------------------------------
class CountryListModel(AbstractReferenceListModel):
    def __init__(self, table, parent_view):
        AbstractReferenceListModel.__init__(self, table, parent_view)
        self._columns = [("name", g_tr('ReferenceDataDialog', "Country")),
                         ("code", g_tr('ReferenceDataDialog', "Code")),
                         ("tax_treaty", g_tr('ReferenceDataDialog', "Tax Treaty"))]
        self._sort_by = "name"
        self._hidden = ["id"]
        self._stretch = "name"
        self._bool_delegate = None

    def configureView(self):
        super().configureView()
        self._view.setColumnWidth(self.fieldIndex("code"), 50)

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
        super()._init_completed()

    def setup_ui(self):
        self.search_field = "name"
        self.SearchFrame.setVisible(True)
        self.setWindowTitle(g_tr('ReferenceDataDialog', "Countries"))
        self.Toggle.setVisible(False)

# ----------------------------------------------------------------------------------------------------------------------
class QuotesListModel(AbstractReferenceListModel):
    def __init__(self, table, parent_view):
        AbstractReferenceListModel.__init__(self, table, parent_view)
        self._columns = [("timestamp", g_tr('ReferenceDataDialog', "Date")),
                         ("asset_id", g_tr('ReferenceDataDialog', "Asset")),
                         ("quote", g_tr('ReferenceDataDialog', "Quote"))]
        self._hidden = ["id"]
        self._lookup_delegate = None
        self._timestamp_delegate = None
        self.setRelation(self.fieldIndex("asset_id"), QSqlRelation("assets", "id", "name"))

    def configureView(self):
        super().configureView()
        self._view.setColumnWidth(self.fieldIndex("timestamp"),
                                  self._view.fontMetrics().width("00/00/0000 00:00:00") * 1.1)
        self._view.setColumnWidth(self.fieldIndex("quote"), 100)

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
        super()._init_completed()

    def setup_ui(self):
        self.search_field = "name"
        self.SearchFrame.setVisible(True)
        self.setWindowTitle(g_tr('ReferenceDataDialog', "Quotes"))
        self.Toggle.setVisible(False)

# ----------------------------------------------------------------------------------------------------------------------

