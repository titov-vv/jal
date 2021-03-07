from PySide2.QtCore import QAbstractItemModel, QModelIndex
from PySide2.QtSql import QSqlTableModel, QSqlRelationalTableModel, QSqlRelation, QSqlRecord, QSqlField
from PySide2.QtWidgets import QHeaderView
from jal.db.helpers import db_connection, readSQL
from jal.widgets.view_delegate import *
from jal.ui_custom.helpers import g_tr
from jal.ui_custom.reference_data import ReferenceDataDialog, ReferenceBoolDelegate, \
    ReferenceLookupDelegate, ReferenceTimestampDelegate, ReferenceIntDelegate


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
        self.select()

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                return self._columns[section][1]
        return None

    def configureView(self):
        self.setSorting()
        self.hideColumns()
        self.setStretching()
        font = self._view.horizontalHeader().font()
        font.setBold(True)
        self._view.horizontalHeader().setFont(font)

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
        self._columns = [("id", ''),
                         ("name", g_tr('ReferenceDataDialog', "Account Type"))]
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
        self._columns = [("id", ''),
                         ("type_id", ''),
                         ("name", g_tr('ReferenceDataDialog', "Name")),
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
        self._columns = [("id", ''),
                         ("type_id", ''),
                         ("name", g_tr('ReferenceDataDialog', "Symbol")),
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
class SqlTreeModel(QAbstractItemModel):
    ROOT_PID = 0

    def __init__(self, table, parent_view):
        super().__init__(parent_view)
        self._table = table
        self._view = parent_view
        self._stretch = None

    def index(self, row, column, parent=None):
        if parent is None:
            return QModelIndex()
        if not parent.isValid():
            parent_id = self.ROOT_PID
        else:
            parent_id = parent.internalId()
        child_id = readSQL(f"SELECT id FROM {self._table} WHERE pid=:pid LIMIT 1 OFFSET :row_n",
                           [(":pid", parent_id), (":row_n", row)])
        if child_id:
            return self.createIndex(row, column, id=child_id)
        return QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()
        child_id = index.internalId()
        parent_id = readSQL(f"SELECT pid FROM {self._table} WHERE id=:id", [(":id", child_id)])
        if parent_id == self.ROOT_PID:
            return QModelIndex()
        return self.createIndex(0, 0, id=parent_id)

    def rowCount(self, parent=None):
        if not parent.isValid():
            parent_id = self.ROOT_PID
        else:
            parent_id = parent.internalId()
        count = readSQL(f"SELECT COUNT(id) FROM {self._table} WHERE pid=:pid", [(":pid", parent_id)])
        if count:
            return int(count)
        else:
            return 0

    def columnCount(self, parent=None):
        return len(self._columns)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        item_id = index.internalId()
        if role == Qt.DisplayRole:
            col = index.column()
            if (col >= 0) and (col < len(self._columns)):
                return readSQL(f"SELECT {self._columns[col][0]} FROM {self._table} WHERE id=:id", [(":id", item_id)])
            else:
                return None
        return None

    def fieldIndex(self, field):
        column_data = [i for i, column in enumerate(self._columns) if column[0] == field]
        if len(column_data) > 0:
            return column_data[0]
        else:
            return -1

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                return self._columns[section][1]
        return None

    def configureView(self):
        self.setStretching()
        font = self._view.header().font()
        font.setBold(True)
        self._view.header().setFont(font)

    def setStretching(self):
        if self._stretch:
            self._view.header().setSectionResizeMode(self.fieldIndex(self._stretch), QHeaderView.Stretch)

# ----------------------------------------------------------------------------------------------------------------------
class PeerTreeModel(SqlTreeModel):
    def __init__(self, table, parent_view):
        super().__init__(table, parent_view)
        self._columns = [("name", g_tr('ReferenceDataDialog', "Name")),
                         ("location", g_tr('ReferenceDataDialog', "Location")),
                         ("actions_count", g_tr('ReferenceDataDialog', "Docs count"))]
        self._stretch = "name"
        self._int_delegate = None

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
        self._int_delegate = ReferenceIntDelegate(self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("actions_count"), self._int_delegate)

    def record(self, row):
        a = QSqlRecord()
        a.append(QSqlField("id"))
        a.append(QSqlField("name"))
        a.append(QSqlField("location"))
        return a

    def setFilter(self, filter_str):
        pass


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
        self.SearchFrame.setVisible(True)
        self.setWindowTitle(g_tr('ReferenceDataDialog', "Peers"))
        self.Toggle.setVisible(False)


# ----------------------------------------------------------------------------------------------------------------------
class CategoryTreeModel(SqlTreeModel):
    def __init__(self, table, parent_view):
        super().__init__(table, parent_view)
        self._columns = [("name", g_tr('ReferenceDataDialog', "Name")),
                         ("often", g_tr('ReferenceDataDialog', "Often"))]
        self._stretch = "name"
        self._bool_delegate = None

    def configureView(self):
        super().configureView()
        self._bool_delegate = ReferenceBoolDelegate(self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("often"), self._bool_delegate)

    def record(self, row):
        a = QSqlRecord()
        a.append(QSqlField("id"))
        a.append(QSqlField("name"))
        a.append(QSqlField("often"))
        return a

    def setFilter(self, filter_str):
        pass


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
        self.SearchFrame.setVisible(True)
        self.setWindowTitle(g_tr('ReferenceDataDialog', "Categories"))
        self.Toggle.setVisible(False)


# ----------------------------------------------------------------------------------------------------------------------
class TagListModel(AbstractReferenceListModel):
    def __init__(self, table, parent_view):
        AbstractReferenceListModel.__init__(self, table, parent_view)
        self._columns = [("id", ''),
                         ("tag", g_tr('ReferenceDataDialog', "Tag"))]
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
        self._columns = [("id", ''),
                         ("name", g_tr('ReferenceDataDialog', "Country")),
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
        self._columns = [("id", ''),
                         ("timestamp", g_tr('ReferenceDataDialog', "Date")),
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
