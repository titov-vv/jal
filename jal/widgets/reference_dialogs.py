from PySide2.QtCore import Qt, QAbstractItemModel, QModelIndex
from PySide2.QtSql import QSqlTableModel, QSqlRelationalTableModel, QSqlRelation, QSqlRelationalDelegate
from PySide2.QtWidgets import QHeaderView
from jal.db.helpers import db_connection, executeSQL, readSQL
from jal.widgets.delegates import TimestampDelegate, BoolDelegate, FloatDelegate, PeerSelectorDelegate
from jal.widgets.helpers import g_tr
from jal.widgets.reference_data import ReferenceDataDialog
from jal.widgets.delegates import GridLinesDelegate


# ----------------------------------------------------------------------------------------------------------------------
class AbstractReferenceListModel(QSqlRelationalTableModel):
    @property
    def completion_model(self):
        return self._completion_model

    def __init__(self, table, parent_view):
        self._view = parent_view
        self._table = table
        self._columns = []
        self._default_name = "name"
        self._group_by = None
        self._sort_by = None
        self._hidden = []
        self._stretch = None
        QSqlRelationalTableModel.__init__(self, parent=parent_view, db=db_connection())
        self.setJoinMode(QSqlRelationalTableModel.LeftJoin)
        self.setTable(self._table)
        self.setEditStrategy(QSqlTableModel.OnManualSubmit)
        self.select()
        # This is auxiliary 'plain' model of the same table - to be given as QCompleter source of data
        self._completion_model = QSqlTableModel(parent=parent_view, db=db_connection())
        self._completion_model.setTable(self._table)
        self._completion_model.select()

    @property
    def group_by(self):
        return self._group_by

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

    def getId(self, index):
        return self.record(index.row()).value('id')

    def getName(self, index):
        return self.getFieldValue(self.getId(index), self._default_name)

    def getFieldValue(self, item_id, field_name):
        return readSQL(f"SELECT {field_name} FROM {self._table} WHERE id=:id", [(":id", item_id)])

    def addElement(self, index, in_group=0):
        row = index.row() if index.isValid() else 0
        assert self.insertRows(row, 1)
        new_record = self.record()
        if in_group != 0:
            new_record.setValue(self.fieldIndex(self._group_by), in_group)   # by index as it is lookup field
        self.setRecord(row, new_record)

    def removeElement(self, index):
        if index.isValid():
            row = index.row()
        else:
            return
        assert self.removeRow(row)

    def locateItem(self, item_id, use_filter=''):
        raise NotImplementedError("locateItem() method is not defined in subclass of AbstractReferenceListModel")

    def updateItemType(self, index, new_type):
        id = self.getId(index)
        executeSQL(f"UPDATE {self._table} SET {self._group_by}=:new_type WHERE id=:id",
                   [(":new_type", new_type), (":id", id)])


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
                         ("organization_id", g_tr('ReferenceDataDialog', "Bank/Broker")),
                         ("country_id", g_tr('ReferenceDataDialog', "CC"))]
        self._sort_by = "name"
        self._group_by = "type_id"
        self._hidden = ["id", "type_id"]
        self._stretch = "name"
        self._lookup_delegate = None
        self._peer_delegate = None
        self._timestamp_delegate = None
        self._bool_delegate = None
        self.setRelation(self.fieldIndex("type_id"), QSqlRelation("account_types", "id", "name"))
        self.setRelation(self.fieldIndex("currency_id"), QSqlRelation("currencies", "id", "name"))
        self.setRelation(self.fieldIndex("country_id"), QSqlRelation("countries", "id", "code"))

    def configureView(self):
        super().configureView()
        self._view.setColumnWidth(self.fieldIndex("active"), 32)
        self._view.setColumnWidth(self.fieldIndex("reconciled_on"),
                                  self._view.fontMetrics().width("00/00/0000 00:00:00") * 1.1)
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
        row = readSQL(f"SELECT row_number FROM (SELECT ROW_NUMBER() OVER (ORDER BY name) AS row_number, id "
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
        self.setWindowTitle(g_tr('ReferenceDataDialog', "Accounts"))
        self.SearchFrame.setVisible(True)
        self.Toggle.setVisible(True)
        self.toggle_field = "active"
        self.Toggle.setText(g_tr('ReferenceDataDialog', "Show inactive"))

        self.GroupLbl.setVisible(True)
        self.GroupLbl.setText(g_tr('ReferenceDataDialog', "Account type:"))
        self.GroupCombo.setVisible(True)
        self.group_key_field = self.model.group_by
        self.group_key_index = self.model.fieldIndex(self.model.group_by)
        self.group_fkey_field = "id"
        relation_model = self.model.relationModel(self.group_key_index)
        self.GroupCombo.setModel(relation_model)
        self.GroupCombo.setModelColumn(relation_model.fieldIndex("name"))
        self.group_id = relation_model.data(relation_model.index(0, relation_model.fieldIndex(self.group_fkey_field)))

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
        self._columns = [("id", ''),
                         ("name", g_tr('ReferenceDataDialog', "Symbol")),
                         ("type_id", ''),
                         ("full_name", g_tr('ReferenceDataDialog', "Name")),
                         ("isin", g_tr('ReferenceDataDialog', "ISIN")),
                         ("country_id", g_tr('ReferenceDataDialog', "Country")),
                         ("src_id", g_tr('ReferenceDataDialog', "Data source"))]
        self._sort_by = "name"
        self._group_by = "type_id"
        self._hidden = ["id", "type_id"]
        self._stretch = "full_name"
        self._lookup_delegate = None
        self.setRelation(self.fieldIndex("type_id"), QSqlRelation("asset_types", "id", "name"))
        self.setRelation(self.fieldIndex("country_id"), QSqlRelation("countries", "id", "name"))
        self.setRelation(self.fieldIndex("src_id"), QSqlRelation("data_sources", "id", "name"))

    def configureView(self):
        super().configureView()
        self._lookup_delegate = QSqlRelationalDelegate(self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("country_id"), self._lookup_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex("src_id"), self._lookup_delegate)

    def getAssetType(self, item_id: int) -> int:
        type_id = readSQL(f"SELECT type_id FROM {self._table} WHERE id=:id", [(":id", item_id)])
        type_id = 0 if type_id is None else type_id
        return type_id

    def locateItem(self, item_id, use_filter=''):
        row = readSQL(f"SELECT row_number FROM (SELECT ROW_NUMBER() OVER (ORDER BY name) AS row_number, id "
                      f"FROM {self._table} WHERE {use_filter}) WHERE id=:id", [(":id", item_id)])
        if row is None:
            return QModelIndex()
        return self.index(row-1, 0)


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
        self.group_key_field = self.model.group_by
        self.group_key_index = self.model.fieldIndex(self.model.group_by)
        self.group_fkey_field = "id"
        relation_model = self.model.relationModel(self.group_key_index)
        self.GroupCombo.setModel(relation_model)
        self.GroupCombo.setModelColumn(relation_model.fieldIndex("name"))
        self.group_id = relation_model.data(relation_model.index(0, relation_model.fieldIndex(self.group_fkey_field)))

    def locateItem(self, item_id):
        type_id = self.model.getAssetType(item_id)
        if type_id == 0:
            return
        self.GroupCombo.setCurrentIndex(type_id-1)
        item_idx = self.model.locateItem(item_id, use_filter=self._filter_text)
        self.DataView.setCurrentIndex(item_idx)


# ----------------------------------------------------------------------------------------------------------------------
class SqlTreeModel(QAbstractItemModel):
    ROOT_PID = 0

    @property
    def completion_model(self):
        return self._completion_model

    def __init__(self, table, parent_view):
        super().__init__(parent_view)
        self._table = table
        self._view = parent_view
        self._default_name = "name"
        self._stretch = None
        # This is auxiliary 'plain' model of the same table - to be given as QCompleter source of data
        self._completion_model = QSqlTableModel(parent=parent_view, db=db_connection())
        self._completion_model.setTable(self._table)
        self._completion_model.select()

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
        row = readSQL(f"SELECT row_number FROM ("
                      f"SELECT ROW_NUMBER() OVER (ORDER BY id) AS row_number, id, pid "
                      f"FROM {self._table} WHERE pid IN (SELECT pid FROM {self._table} WHERE id=:id)) "
                      f"WHERE id=:id", [(":id", parent_id)])
        return self.createIndex(row-1, 0, id=parent_id)

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

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsEditable | super().flags(index)

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

    def setData(self, index, value, role=Qt.EditRole):
        if role != Qt.EditRole:
            return False
        if not index.isValid():
            return False
        item_id = index.internalId()
        col = index.column()
        db_connection().transaction()
        _ = executeSQL(f"UPDATE {self._table} SET {self._columns[col][0]}=:value WHERE id=:id",
                       [(":id", item_id), (":value", value)])
        self.dataChanged.emit(index, index, Qt.DisplayRole | Qt.EditRole)
        return True

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

    def getId(self, index):
        if not index.isValid():
            return None
        return index.internalId()

    def getName(self, index):
        item_id = self.getId(index)
        if item_id is not None:
            self.getFieldValue(item_id, self._default_name)

    def getFieldValue(self, item_id, field_name):
        return readSQL(f"SELECT {field_name} FROM {self._table} WHERE id=:id", [(":id", item_id)])

    def deleteWithChilderen(self, parent_id: int) -> None:
        query = executeSQL(f"SELECT id FROM {self._table} WHERE pid=:pid", [(":pid", parent_id)])
        while query.next():
            self.deleteWithChilderen(query.value(0))
        _ = executeSQL(f"DELETE FROM {self._table} WHERE id=:id", [(":id", parent_id)])

    def insertRows(self, row, count, parent=None):
        if parent is None:
            return False
        if not parent.isValid():
            parent_id = self.ROOT_PID
        else:
            parent_id = parent.internalId()

        self.beginInsertRows(parent, row, row + count - 1)
        db_connection().transaction()
        _ = executeSQL(f"INSERT INTO {self._table}(pid, name) VALUES (:pid, '')", [(":pid", parent_id)])
        self.endInsertRows()
        self.layoutChanged.emit()
        return True

    def removeRows(self, row, count, parent=None):
        if parent is None:
            return False
        if not parent.isValid():
            parent_id = self.ROOT_PID
        else:
            parent_id = parent.internalId()

        self.beginRemoveRows(parent, row, row + count - 1)
        db_connection().transaction()
        query = executeSQL(f"SELECT id FROM {self._table} WHERE pid=:pid LIMIT :row_c OFFSET :row_n",
                           [(":pid", parent_id), (":row_c", count), (":row_n", row)])
        while query.next():
            self.deleteWithChilderen(query.value(0))
        self.endRemoveRows()
        self.layoutChanged.emit()
        return True

    def addElement(self, index, in_group=0):  # in_group is used for plain model only, not tree
        row = index.row()
        assert self.insertRows(row, 1, index.parent())

    def addChildElement(self, index):
        assert self.insertRows(0, 1, index)
        self._view.expand(index)

    def removeElement(self, index):
        row = index.row()
        assert self.removeRows(row, 1, index.parent())

    def submitAll(self):
        _ = executeSQL("COMMIT")
        self.layoutChanged.emit()
        return True

    def revertAll(self):
        _ = executeSQL("ROLLBACK")
        self.layoutChanged.emit()

    # expand all parent elements for tree element with given index
    def expand_parent(self, index):
        parent = index.parent()
        if parent.isValid():
            self.expand_parent(parent)
        self._view.expand(index)

    # find item by ID and make it selected in associated self._view
    def locateItem(self, item_id):
        row = readSQL(f"SELECT row_number FROM ("
                      f"SELECT ROW_NUMBER() OVER (ORDER BY id) AS row_number, id, pid "
                      f"FROM {self._table} WHERE pid IN (SELECT pid FROM {self._table} WHERE id=:id)) "
                      f"WHERE id=:id", [(":id", item_id)])
        if row is None:
            return
        item_idx = self.createIndex(row-1, 0, id=item_id)
        self.expand_parent(item_idx)
        self._view.setCurrentIndex(item_idx)

    def setFilter(self, filter_str):
        pass

# ----------------------------------------------------------------------------------------------------------------------
class PeerTreeModel(SqlTreeModel):
    def __init__(self, table, parent_view):
        super().__init__(table, parent_view)
        self._columns = [("name", g_tr('ReferenceDataDialog', "Name")),
                         ("location", g_tr('ReferenceDataDialog', "Location")),
                         ("actions_count", g_tr('ReferenceDataDialog', "Docs count"))]
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
        self.setWindowTitle(g_tr('ReferenceDataDialog', "Peers"))
        self.Toggle.setVisible(False)

    def locateItem(self, item_id):
        self.model.locateItem(item_id)


# ----------------------------------------------------------------------------------------------------------------------
class CategoryTreeModel(SqlTreeModel):
    def __init__(self, table, parent_view):
        super().__init__(table, parent_view)
        self._columns = [("name", g_tr('ReferenceDataDialog', "Name")),
                         ("often", g_tr('ReferenceDataDialog', "Often"))]
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
        self.setWindowTitle(g_tr('ReferenceDataDialog', "Categories"))
        self.Toggle.setVisible(False)

    def locateItem(self, item_id):
        self.model.locateItem(item_id)

# ----------------------------------------------------------------------------------------------------------------------
class TagListModel(AbstractReferenceListModel):
    def __init__(self, table, parent_view):
        AbstractReferenceListModel.__init__(self, table, parent_view)
        self._columns = [("id", ''),
                         ("tag", g_tr('ReferenceDataDialog', "Tag"))]
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
        self.setWindowTitle(g_tr('ReferenceDataDialog', "Tags"))
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
        self._default_name = "quote"
        self._lookup_delegate = None
        self._timestamp_delegate = None
        self.setRelation(self.fieldIndex("asset_id"), QSqlRelation("assets", "id", "name"))

    def configureView(self):
        super().configureView()
        self._view.setColumnWidth(self.fieldIndex("timestamp"),
                                  self._view.fontMetrics().width("00/00/0000 00:00:00") * 1.1)
        self._view.setColumnWidth(self.fieldIndex("quote"), 100)

        self._lookup_delegate = QSqlRelationalDelegate(self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("asset_id"), self._lookup_delegate)
        self._timestamp_delegate = TimestampDelegate(parent=self._view)
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
