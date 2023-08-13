import logging
from PySide6.QtCore import Qt, QAbstractItemModel, QModelIndex, QMimeData, QByteArray, QDataStream, QIODevice
from PySide6.QtSql import QSqlTableModel, QSqlRelationalTableModel
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHeaderView, QMessageBox, QAbstractItemView
from jal.db.db import JalDB, JalSqlError


# ----------------------------------------------------------------------------------------------------------------------
class AbstractReferenceListModel(QSqlRelationalTableModel, JalDB):
    @property
    def completion_model(self):
        return self._completion_model

    def __init__(self, table, parent_view, **kwargs):
        self._view = parent_view
        self._table = table
        self._columns = []
        self._deleted_rows = []
        self._default_name = "name"
        self._group_by = None
        self._filter_by = ''
        self._filter_value = None
        self._sort_by = None
        self._hidden = []
        self._stretch = None
        self._default_values = {}   # To fill in default values for fields allowed to be NULL
        super().__init__(parent=parent_view, db=self.connection())
        self.setJoinMode(QSqlRelationalTableModel.LeftJoin)
        self.setTable(self._table)
        self.setEditStrategy(QSqlTableModel.OnManualSubmit)
        self.select()
        # This is auxiliary 'plain' model of the same table - to be given as QCompleter source of data
        self._completion_model = QSqlTableModel(parent=parent_view, db=self.connection())
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

    def headerData(self, section, orientation=Qt.Horizontal, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                return self._columns[section][1]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.FontRole and (index.row() in self._deleted_rows):  # Strike-out deleted items
            font = QFont()
            font.setStrikeOut(True)
            return font
        return super().data(index, role)

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
        return self._read(f"SELECT {field_name} FROM {self._table} WHERE id=:id", [(":id", item_id)])

    def addElement(self, index, in_group=0):
        row = index.row() if index.isValid() else 0
        assert self.insertRows(row, 1)
        new_record = self.record()
        if in_group != 0:
            new_record.setValue(self.fieldIndex(self._group_by), in_group)   # by index as it is lookup field
        for field in self._default_values:
            new_record.setValue(self.fieldIndex(field), self._default_values[field])
        if self._filter_by:
            new_record.setValue(self.fieldIndex(self._filter_by), self._filter_value)
        self.setRecord(row, new_record)

    def removeElement(self, index):
        if index.isValid():
            row = index.row()
        else:
            return
        assert self.removeRow(row)
        self._deleted_rows.append(row)

    def submitAll(self):
        result = super().submitAll()
        if result:
            self._deleted_rows = []
        else:
            error_code = self.lastError().nativeErrorCode()
            null_pfx = "NOT NULL constraint failed: " + self.tableName() + "."
            if error_code == '1299' and self.lastError().databaseText().startswith(null_pfx):
                    field_name = self.lastError().databaseText()[len(null_pfx):]
                    header_title = self.tableName() + ":" + self.headerData(self.fieldIndex(field_name))
                    QMessageBox().warning(self._view, self.tr("Data are incomplete"),
                                          self.tr("Column has no valid value: " + header_title), QMessageBox.Ok)
            else:
                error = JalSqlError(self.lastError().databaseText())
                if error.custom():
                    error.show()
                else:
                    logging.fatal(self.tr("Submit failed: ") + error.message())
        return result

    def revertAll(self):
        self._deleted_rows = []
        super().revertAll()

    def locateItem(self, item_id, use_filter=''):
        if use_filter:
            use_filter = f"WHERE {use_filter}"
        row = self._read(f"SELECT row_number FROM ("
                         f"SELECT ROW_NUMBER() OVER (ORDER BY {self._default_name}) AS row_number, id "
                         f"FROM {self._table} {use_filter}) WHERE id=:id", [(":id", item_id)])
        if row is None:
            return QModelIndex()
        return self.index(row - 1, 0)

    def updateItemType(self, index, new_type):
        id = self.getId(index)
        self._exec(f"UPDATE {self._table} SET {self._group_by}=:new_type WHERE id=:id",
                   [(":new_type", new_type), (":id", id)])

    def filterBy(self, field_name, value):
        self._filter_by = field_name
        self._filter_value = value
        self.setFilter(f"{self._table}.{field_name} = {value}")

    # returns group id for given item
    def getGroupId(self, item_id: int) -> int:
        group_id = self._read(f"SELECT {self._group_by} FROM {self._table} WHERE id=:id", [(":id", item_id)])
        group_id = 0 if group_id is None else group_id
        return group_id


# ----------------------------------------------------------------------------------------------------------------------
class SqlTreeModel(QAbstractItemModel, JalDB):
    ROOT_PID = 0
    DRAG_DROP_MIME_TYPE = "application/vnd.tree_item"

    @property
    def completion_model(self):
        return self._completion_model

    def __init__(self, table, parent_view):
        super().__init__(parent=parent_view)
        self._table = table
        self._columns = []
        self._drag_and_drop = False  # This is required to prevent deletion of initial element after drag&drop movement
        self._view = parent_view
        self._default_name = "name"
        self._stretch = None
        self._sort_by = None
        self._filter_text = ''
        # This is auxiliary 'plain' model of the same table - to be given as QCompleter source of data
        self._completion_model = QSqlTableModel(parent=parent_view, db=self.connection())
        self._completion_model.setTable(self._table)
        self._completion_model.select()

    def index(self, row, column, parent=None):
        if parent is None:
            return QModelIndex()
        if not parent.isValid():
            parent_id = self.ROOT_PID
        else:
            parent_id = parent.internalId()
        order_by = f"ORDER BY {self._sort_by}" if self._sort_by is not None else ''
        if not self._filter_text:
            child_id = self._read(f"SELECT id FROM {self._table} WHERE pid=:pid {order_by} LIMIT 1 OFFSET :row_n",
                                  [(":pid", parent_id), (":row_n", row)])
        else:  # display a plain list in a filter mode
            child_id = self._read(f"SELECT id FROM {self._table} WHERE {self._filter_text} {order_by} "
                                  "LIMIT 1 OFFSET :row_n", [(":row_n", row)])
        if child_id:
            return self.createIndex(row, column, id=child_id)
        return QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()
        child_id = index.internalId()
        parent_id = self._read(f"SELECT pid FROM {self._table} WHERE id=:id", [(":id", child_id)])
        if parent_id == self.ROOT_PID:
            return QModelIndex()
        order_by = f"ORDER BY {self._sort_by}" if self._sort_by is not None else ''
        row = self._read(f"SELECT row_number FROM ("
                         f"SELECT ROW_NUMBER() OVER ({order_by}) AS row_number, id, pid "
                         f"FROM {self._table} WHERE pid IN (SELECT pid FROM {self._table} WHERE id=:id)) "
                         f"WHERE id=:id", [(":id", parent_id)])
        return self.createIndex(row-1, 0, id=parent_id)

    def rowCount(self, parent=None):
        if not parent.isValid():
            parent_id = self.ROOT_PID
        else:
            parent_id = parent.internalId()
        if not self._filter_text:
            count = self._read(f"SELECT COUNT(id) FROM {self._table} WHERE pid=:pid", [(":pid", parent_id)])
        else:
            if parent_id:  # no children if we are in filter mode and display a plain list
                return 0
            count = self._read(f"SELECT COUNT(id) FROM {self._table} WHERE {self._filter_text}")
        if count:
            return int(count)
        else:
            return 0

    def columnCount(self, parent=None):
        return len(self._columns)

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.ItemIsDropEnabled
        return Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsDropEnabled | Qt.ItemFlag.ItemIsDragEnabled | super().flags(index)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        item_id = index.internalId()
        if role == Qt.DisplayRole or role == Qt.EditRole:
            col = index.column()
            if (col >= 0) and (col < len(self._columns)):
                return self._read(f"SELECT {self._columns[col][0]} FROM {self._table} WHERE id=:id",
                                  [(":id", item_id)])
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
        self.connection().transaction()
        _ = self._exec(f"UPDATE {self._table} SET {self._columns[col][0]}=:value WHERE id=:id",
                       [(":id", item_id), (":value", value)])
        self.dataChanged.emit(index, index, Qt.DisplayRole | Qt.EditRole)
        self.layoutChanged.emit()   # Emit unconditionally as item order may be changed after editing
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

    def supportedDragActions(self) -> Qt.DropAction:
        return Qt.DropAction.MoveAction

    def supportedDropActions(self) -> Qt.DropAction:
        return Qt.DropAction.MoveAction

    def mimeTypes(self) -> list:
        return [self.DRAG_DROP_MIME_TYPE]

    # This method encodes tree element 'id' field and returns it as QMimeData for Drag&Drop operation
    def mimeData(self, indexes: list) -> QMimeData:
        item_data = QMimeData()
        encoded_data = QByteArray()
        stream = QDataStream(encoded_data, QIODevice.WriteOnly)
        for index in indexes:
            stream.writeUInt64(index.internalId())
        item_data.setData(self.DRAG_DROP_MIME_TYPE, encoded_data)
        return item_data

    def canDropMimeData(self, data: QMimeData, action: Qt.DropAction, row: int, column: int, parent: QModelIndex) -> bool:
        if action != Qt.DropAction.MoveAction or not data.hasFormat(self.DRAG_DROP_MIME_TYPE):
            return False
        return True

    def dropMimeData(self, data: QMimeData, action: Qt.DropAction, row: int, column: int, parent: QModelIndex) -> bool:
        if not self.canDropMimeData(data, action, row, column, parent):
            return False
        encoded_data = data.data(self.DRAG_DROP_MIME_TYPE)
        stream = QDataStream(encoded_data, QIODevice.ReadOnly)
        item_id = stream.readUInt64()
        self.connection().transaction()
        if parent.isValid():
            self._exec(f"UPDATE {self._table} SET pid=:pid WHERE id=:id",
                       [(":id", item_id), (":pid", parent.internalId())])
        else:
            self._exec(f"UPDATE {self._table} SET pid=0 WHERE id=:id", [(":id", item_id)])
        self._drag_and_drop = True
        return True

    def configureView(self):
        self.setStretching()
        font = self._view.header().font()
        font.setBold(True)
        self._view.header().setFont(font)
        self._view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._view.setDragEnabled(True)
        self._view.setAcceptDrops(True)
        self._view.setDropIndicatorShown(True)
        self._view.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._view.setDefaultDropAction(Qt.DropAction.MoveAction)

    def setStretching(self):
        if self._stretch:
            self._view.header().setSectionResizeMode(self.fieldIndex(self._stretch), QHeaderView.Stretch)

    def getId(self, index):
        if not index.isValid():
            return None
        return index.internalId()

    def getName(self, index):
        return self.getFieldValue(self.getId(index), self._default_name)

    def getFieldValue(self, item_id, field_name):
        return self._read(f"SELECT {field_name} FROM {self._table} WHERE id=:id", [(":id", item_id)])

    def deleteWithChilderen(self, parent_id: int) -> None:
        query = self._exec(f"SELECT id FROM {self._table} WHERE pid=:pid", [(":pid", parent_id)])
        while query.next():
            self.deleteWithChilderen(query.value(0))
        _ = self._exec(f"DELETE FROM {self._table} WHERE id=:id", [(":id", parent_id)])

    def insertRows(self, row, count, parent=None):
        if parent is None:
            return False
        if not parent.isValid():
            parent_id = self.ROOT_PID
        else:
            parent_id = parent.internalId()

        self.beginInsertRows(parent, row, row + count - 1)
        self.connection().transaction()
        _ = self._exec(f"INSERT INTO {self._table}(pid, {self._default_name}) VALUES (:pid, '')", [(":pid", parent_id)])
        self.endInsertRows()
        self.layoutChanged.emit()
        return True

    def removeRows(self, row, count, parent=None):
        if self._drag_and_drop:  # This is an automatically triggered action - keep the element but refresh the view
            self._drag_and_drop = False
            self.dataChanged.emit(QModelIndex(), QModelIndex(), Qt.DisplayRole)  # the call is required to enable commit/rollback buttons in UI
            self.layoutChanged.emit()
            return True
        if parent is None:
            return False
        if not parent.isValid():
            parent_id = self.ROOT_PID
        else:
            parent_id = parent.internalId()

        self.beginRemoveRows(parent, row, row + count - 1)
        self.connection().transaction()
        order_by = f"ORDER BY {self._sort_by}" if self._sort_by is not None else ''  # FIXME - this line repeats several times over the class - refactor
        query = self._exec(f"SELECT id FROM {self._table} WHERE pid=:pid {order_by} LIMIT :row_c OFFSET :row_n",
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
        _ = self._exec("COMMIT")
        self.layoutChanged.emit()
        return True

    def revertAll(self):
        _ = self._exec("ROLLBACK")
        self.layoutChanged.emit()

    # expand all parent elements for tree element with given index
    def expand_parent(self, index):
        parent = index.parent()
        if parent.isValid():
            self.expand_parent(parent)
        self._view.expand(index)

    # find item by ID and make it selected in associated self._view
    def locateItem(self, item_id):
        order_by = f"ORDER BY {self._sort_by}" if self._sort_by is not None else ''
        row = self._read(f"SELECT row_number FROM ("
                         f"SELECT ROW_NUMBER() OVER ({order_by}) AS row_number, id, pid "
                         f"FROM {self._table} WHERE pid IN (SELECT pid FROM {self._table} WHERE id=:id)) "
                         f"WHERE id=:id", [(":id", item_id)])
        if row is None:
            return
        item_idx = self.createIndex(row-1, 0, id=item_id)
        self.expand_parent(item_idx)
        self._view.setCurrentIndex(item_idx)

    def setFilter(self, text):
        self._filter_text = text
        self.layoutChanged.emit()
