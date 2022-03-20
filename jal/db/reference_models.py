import logging
from PySide6.QtCore import Qt, QAbstractItemModel, QModelIndex
from PySide6.QtSql import QSqlTableModel, QSqlRelationalTableModel
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHeaderView, QMessageBox
from jal.db.helpers import db_connection, executeSQL, readSQL
from jal.widgets.helpers import decodeError


# ----------------------------------------------------------------------------------------------------------------------
class AbstractReferenceListModel(QSqlRelationalTableModel):
    @property
    def completion_model(self):
        return self._completion_model

    def __init__(self, table, parent_view):
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
        return readSQL(f"SELECT {field_name} FROM {self._table} WHERE id=:id", [(":id", item_id)])

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
            if error_code == '1299':
                prefix = "NOT NULL constraint failed: " + self.tableName() + "."
                if self.lastError().databaseText().startswith(prefix):
                    field_name = self.lastError().databaseText()[len(prefix):]
                    header_title = self.tableName() + ":" + self.headerData(self.fieldIndex(field_name))
                    QMessageBox().warning(self._view, self.tr("Data are incomplete"),
                                          self.tr("Column has no valid value: " + header_title), QMessageBox.Ok)
                else:
                    logging.fatal(self.tr("Submit failed: ") + decodeError(self.lastError().text()))
            elif error_code == '1811':   # Foreign key constraint failed
                QMessageBox().warning(self._view, self.tr("Data are in use"),
                                      self.tr("Data are referenced in another place and can't be modified"),
                                      QMessageBox.Ok)
            else:
                logging.fatal(self.tr("Submit failed: ") + decodeError(self.lastError().text()))
        return result

    def revertAll(self):
        self._deleted_rows = []
        super().revertAll()

    def locateItem(self, item_id, use_filter=''):
        raise NotImplementedError(f"locateItem() method is not defined  in {type(self).__name__} class")

    def updateItemType(self, index, new_type):
        id = self.getId(index)
        executeSQL(f"UPDATE {self._table} SET {self._group_by}=:new_type WHERE id=:id",
                   [(":new_type", new_type), (":id", id)])

    def filterBy(self, field_name, value):
        self._filter_by = field_name
        self._filter_value = value
        self.setFilter(f"{self._table}.{field_name} = {value}")


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