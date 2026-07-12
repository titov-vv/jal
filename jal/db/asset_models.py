from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtSql import QSqlQueryModel, QSqlTableModel
from PySide6.QtWidgets import QCompleter, QMessageBox
from jal.db.db import JalDB
from jal.db.common_models_abstract import AbstractReferenceListModel
from jal.db.asset import JalAsset
from jal.db.tag import JalTag
from jal.constants import CmColumn, CmWidth, AssetData, SymbolId


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
                           "LEFT JOIN asset_symbol c ON s.currency_id=c.asset_id AND c.active=1"
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

    # Returns True if given symbol is the only symbol its asset has
    def is_last_symbol(self, symbol_id) -> bool:
        other_symbols = self._read("SELECT COUNT(id) FROM asset_symbol WHERE "
                                   "asset_id=(SELECT asset_id FROM asset_symbol WHERE id=:id) AND id!=:id",
                                   [(":id", symbol_id)])
        return not other_symbols

    # Deletes given symbol. If it was the last symbol of its asset, deletes the (now empty) asset too, together
    # with its attributes and cached trade history (asset_data/trades_opened/trades_closed cascade via FK,
    # ledger.asset_id is set to NULL instead of a cascading delete - see jal_init.sql).
    # Both deletes run in a single transaction: if dropping the (now empty) asset fails - e.g. it is still
    # referenced elsewhere as accounts.currency_id, which is ON DELETE RESTRICT - the symbol deletion is rolled
    # back too, so we never leave a still-referenced asset with zero symbols behind.
    # Returns True if deletion succeeded.
    def remove_symbol(self, symbol_id) -> bool:
        asset_id = self._read("SELECT asset_id FROM asset_symbol WHERE id=:id", [(":id", symbol_id)])
        drop_asset = self.is_last_symbol(symbol_id)
        self.connection().transaction()
        if self._exec("DELETE FROM asset_symbol WHERE id=:id", [(":id", symbol_id)]) is None:
            self.connection().rollback()
            return False
        if drop_asset:
            if self._exec("DELETE FROM assets WHERE id=:id", [(":id", asset_id)]) is None:
                self.connection().rollback()
                return False
        self.connection().commit()
        return True


# ----------------------------------------------------------------------------------------------------------------------
# Editable single-row model of the 'assets' table itself - used together with QDataWidgetMapper to edit
# top-level asset fields (name/type/country) in SymbolDialog.
class AssetRecordModel(AbstractReferenceListModel):
    def __init__(self, parent=None):
        columns = [
            CmColumn("id", '', hide=True),
            CmColumn("type_id", self.tr("Type")),
            CmColumn("full_name", self.tr("Name"), default=True, width=CmWidth.WIDTH_STRETCH),
            CmColumn("country_id", self.tr("Country"))
        ]
        super().__init__("assets", columns, parent)


# ----------------------------------------------------------------------------------------------------------------------
# Editable model of 'asset_symbol' table - list of symbols (tickers) that belong to a single asset.
# Use filterBy("asset_id", asset_id) to bind it to a particular asset.
class AssetSymbolsModel(AbstractReferenceListModel):
    def __init__(self, parent=None):
        columns = [
            CmColumn("id", '', hide=True),
            CmColumn("asset_id", '', hide=True),
            CmColumn("symbol", self.tr("Symbol"), default=True, sort=True, width=CmWidth.WIDTH_STRETCH),
            CmColumn("currency_id", self.tr("Currency")),
            CmColumn("location_id", self.tr("Location")),
            CmColumn("active", self.tr("Act.")),
            CmColumn("icon", '', hide=True)
        ]
        super().__init__("asset_symbol", columns, parent)
        self.set_default_values({'symbol': '', 'currency_id': JalAsset.get_base_currency(), 'location_id': 0, 'active': 1})

    # 'symbol' is left blank for the user to fill in right away. As (asset_id, symbol, currency_id) must be
    # unique, only one blank-symbol row (with the default currency) may exist per asset at a time - adding
    # another one is refused until the pending row is given a real symbol.
    def addElement(self, index, in_group=0):
        if self._read("SELECT id FROM asset_symbol WHERE asset_id=:aid AND symbol='' AND currency_id=:currency",
                      [(":aid", self._filter_value), (":currency", self._default_values['currency_id'])]) is not None:
            QMessageBox().warning(None, self.tr("Row not added"),
                                  self.tr("Please fill in the previously added symbol before adding a new one"), QMessageBox.Ok)
            return
        super().addElement(index, in_group)

    # Returns id of the row most recently created via addElement() (call after submitAll()+select())
    def id_of_last_added(self):
        return self._read("SELECT id FROM asset_symbol WHERE asset_id=:aid AND symbol='' AND currency_id=:currency",
                          [(":aid", self._filter_value), (":currency", self._default_values['currency_id'])])


# ----------------------------------------------------------------------------------------------------------------------
# Editable model of 'symbol_ids' table - list of various identifiers (ISIN/FIGI/CUSIP/...) that belong to a
# particular symbol (not to the asset as a whole). Use filterBy("symbol_id", symbol_id) to bind it.
class SymbolIdentifiersModel(AbstractReferenceListModel):
    def __init__(self, parent=None):
        columns = [
            CmColumn("id", '', hide=True),
            CmColumn("symbol_id", '', hide=True),
            CmColumn("id_type", self.tr("Type")),
            CmColumn("id_value", self.tr("Value"), default=True, width=CmWidth.WIDTH_STRETCH)
        ]
        super().__init__("symbol_ids", columns, parent)
        self.set_default_values({'id_type': SymbolId.ISIN, 'id_value': ''})


# ----------------------------------------------------------------------------------------------------------------------
# Editable model of 'asset_data' table - a flexible set of typed attributes that belong to an asset as a whole
# (registration code, expiry date, principal value, tag, ...). Use filterBy("asset_id", asset_id) to bind it.
class AssetDataModel(AbstractReferenceListModel):
    def __init__(self, parent=None):
        columns = [
            CmColumn("id", '', hide=True),
            CmColumn("asset_id", '', hide=True),
            CmColumn("datatype", self.tr("Attribute"), default=True),
            CmColumn("value", self.tr("Value"), width=CmWidth.WIDTH_STRETCH)
        ]
        super().__init__("asset_data", columns, parent)
        self._types = AssetData()
        self.set_default_values({'datatype': AssetData.ExpiryDate, 'value': ''})

    # (asset_id, datatype) must be unique, so adding another row with the default attribute type is refused
    # while one already exists for this asset - the user has to change its type first.
    def addElement(self, index, in_group=0):
        if self._read("SELECT id FROM asset_data WHERE asset_id=:aid AND datatype=:dt",
                      [(":aid", self._filter_value), (":dt", self._default_values['datatype'])]) is not None:
            QMessageBox().warning(None, self.tr("Row not added"),
                                  self.tr("Please fill in the previously added attribute before adding a new one"), QMessageBox.Ok)
            return
        super().addElement(index, in_group)

    # Displays translated attribute name and value formatted according to its type
    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and index.isValid():
            if index.column() == self.fieldIndex("datatype"):
                return self._types.get_name(super().data(index, role))
            if index.column() == self.fieldIndex("value"):
                datatype = super().data(index.sibling(index.row(), self.fieldIndex("datatype")), role)
                return self._format_value(datatype, super().data(index, role))
        return super().data(index, role)

    def _format_value(self, datatype, value):
        datatype_of = self._types.get_type(datatype)
        try:
            if datatype_of == "str" or datatype_of == "int":
                return value
            elif datatype_of == "date":
                return datetime.fromtimestamp(int(value), tz=timezone.utc).strftime("%d/%m/%Y")
            elif datatype_of == "float":
                return f"{Decimal(value):.2f}"
            elif datatype_of == "tag":
                return JalTag(int(value)).name()
        except (ValueError, InvalidOperation, TypeError):
            return ''
        return value
