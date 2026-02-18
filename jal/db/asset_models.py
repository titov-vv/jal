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
            CmColumn("asset_id", self.tr("Asset"), hide=True),
            CmColumn("type_id", self.tr("Asset type"), hide=True, group=True),
            CmColumn("currency_id", self.tr("Currency"), hide=True),
            CmColumn("currency", self.tr("Currency")),
            CmColumn("location_id", self.tr("Location")),
            CmColumn("full_name", self.tr("Name"), width=CmWidth.WIDTH_STRETCH, details=True),
            CmColumn("icon", '')
        ]
        self._filter_by = ''
        self._filter_value = None
        self._default_name = 'symbol'
        self._base_query = "SELECT s.id, s.symbol, s.asset_id, a.type_id, s.currency_id, c.symbol AS currency, s.location_id, a.full_name, s.icon "\
                           "FROM asset_symbol s "\
                           "LEFT JOIN assets a ON a.id=s.asset_id "\
                           "LEFT JOIN asset_symbol c ON s.currency_id=c.asset_id"
        self._filter_clause = ''
        self._sort_clause = "ORDER BY s.symbol"
        self._current_query = self._base_query + " " + self._sort_clause
        self.setQuery(self._exec(self._current_query, forward_only=False))

        self._completion_model = QSqlTableModel(parent=parent, db=self.connection())
        self._completion_model.setTable("asset_symbol")
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

    def fieldIndex(self, field):
        column_data = [i for i, column in enumerate(self._columns) if column.name == field]
        if len(column_data) > 0:
            return column_data[0]
        else:
            return -1

    def setFilter(self, asset_type=None, currency_id=None, location_id=None, text=''):
        filter_clauses = []
        if asset_type is not None:
            filter_clauses.append(f"a.type_id={asset_type}")
        if currency_id is not None:
            filter_clauses.append(f"s.currency_id={currency_id}")
        if location_id is not None:
            filter_clauses.append(f"s.location_id={location_id}")
        if text:
            filter_clauses.append(f"(s.symbol LIKE '%{text}%' OR a.full_name LIKE '%{text}%')")
        self._filter_clause = ' AND '.join(filter_clauses)
        self._current_query = f"{self._base_query} WHERE {self._filter_clause} {self._sort_clause}"
        self.setQuery(self._exec(self._current_query, forward_only=False))

    def getId(self, index):
        return self.record(index.row()).value('id')

    def getName(self, index):
        return self._read("SELECT symbol FROM asset_symbol WHERE id=:id", [(":id", self.getId(index))])

    def getValue(self, item_id):
        return self._read("SELECT symbol FROM asset_symbol WHERE id=:id", [(":id", item_id)])

    def getValueDetails(self, item_id) -> str:
        return self._read("SELECT full_name FROM assets WHERE id=(SELECT asset_id FROM asset_symbol WHERE id=:id)", [(":id", item_id)])

    def locateItem(self, item_id):
        row = self._read(f"SELECT row_number FROM ("
                         f"SELECT ROW_NUMBER() OVER (ORDER BY symbol) AS row_number, id "
                         f"FROM ({self._current_query})) WHERE id=:id", [(":id", item_id)])
        if row is None:
            return QModelIndex()
        return self.index(row - 1, 0)

    def updateItemType(self, index, new_type):   # FIXME - needs adaptation to new query structure
        id = self.getId(index)
        self._exec(f"UPDATE {self._table} SET {self._group_by}=:new_type WHERE id=:id",
                   [(":new_type", new_type), (":id", id)])
