import logging
from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtSql import QSqlQueryModel, QSqlTableModel
from PySide6.QtWidgets import QCompleter
from jal.db.db import JalDB
from jal.constants import CmColumn, CmWidth


# ----------------------------------------------------------------------------------------------------------------------
class SymbolsListModel(QSqlQueryModel, JalDB):
    def __init__(self, parent=None):
        super().__init__(parent=parent, db=self.connection())
        self._columns = [
            CmColumn("id", '', hide=True),
            CmColumn("symbol", self.tr("Symbol"), default=True, sort=True),
            CmColumn("asset_id", self.tr("Asset")),
            CmColumn("type_id", self.tr("Asset type"), hide=True, group=True),
            CmColumn("currency_id", self.tr("Currency")),
            CmColumn("location_id", self.tr("Location")),
            CmColumn("full_name", self.tr("Name"), width=CmWidth.WIDTH_STRETCH, details=True),
            CmColumn("icon", '')
        ]
        self._table = 'symbols_ext'
        self._filter_by = ''
        self._filter_value = None
        self._default_name = 'symbol'
        self._query_text = f"SELECT * FROM {self._table}"
        # if self._sort_by:
        #     self.setSort(self.fieldIndex(self._sort_by), Qt.AscendingOrder)
        self.setQuery(self._exec(self._query_text, forward_only=False))

        self._completion_model = QSqlTableModel(parent=parent, db=self.connection())
        self._completion_model.setTable(self._table)
        self._completion_model.select()
        # Completer is used in widgets after call to bind_completer()
        self._completer = QCompleter(self._completion_model)
        self._completer.setCompletionColumn(self._completion_model.fieldIndex(self._default_name))
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)

    def column_meta(self) -> list[CmColumn]:
        return self._columns

    @property
    def completion_model(self):
        return self._completion_model

    # Binds completer to the given widget. Trigger completion_handler event handler when selection to be done.
    def bind_completer(self, widget, completion_handler):
        widget.setCompleter(self._completer)
        self._completer.activated[QModelIndex].connect(completion_handler)

    def headerData(self, section, orientation=Qt.Horizontal, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
                return self._columns[section].header
        return None

    @property
    def group_by(self):
        return self._group_by

    def setFilter(self, filter_text):
        self.setQuery(self._exec(f"{self._query_text} WHERE {filter_text}", forward_only=False))


    def getId(self, index):
        return self.record(index.row()).value('id')

    def getFieldValue(self, item_id, field_name):
        return self._read(f"SELECT {field_name} FROM {self._table} WHERE id=:id", [(":id", item_id)])

    def submitAll(self):
        pass

    def revertAll(self):
        pass

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
        group_id = 0 if not group_id or group_id is None else group_id
        return group_id