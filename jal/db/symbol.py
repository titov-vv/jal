import logging
from jal.constants import SymbolId, BookAccount
from jal.db.db import JalDB
from jal.db.asset import JalAsset
from jal.universal_cache import UniversalCache


# ----------------------------------------------------------------------------------------------------------------------
# A single row of the 'asset_symbol' table: one listing/ticker of an asset in a given currency, together with the
# identifiers (ISIN/CUSIP/reg.code/... - see SymbolId) that belong to that specific listing (table 'symbol_ids').
# Operations reference a symbol (not an asset) via their symbol_id column, so this is the natural handle for them:
# the owning asset is available via asset(). An empty object (id 0, or an unknown/None id) has no asset - asset()
# returns JalAsset(0) - which keeps callers that pass a NULL symbol_id (e.g. cash transfers) working.
class JalSymbol(JalDB):
    db_cache = UniversalCache()

    def __init__(self, symbol_id: int = 0) -> None:
        super().__init__(cached=True)
        try:
            self._id = int(symbol_id)
        except (TypeError, ValueError):
            self._id = 0
        self._data = self.db_cache.get_data(self._load_symbol_data, (self._id,))  # Load symbol data from cache or DB
        self._symbol = self._data.get('symbol', '')
        self._asset_id = self._data.get('asset_id', 0)
        self._currency = self._data.get('currency_id', None)
        self._location = self._data.get('location_id', 0)
        self._active = self._data.get('active', 0)
        self._icon = self._data.get('icon', None)

    def invalidate_cache(self):
        self.db_cache.clear_cache()

    # JalSymbol maintains single cache available for all instances
    @classmethod
    def class_cache(cls) -> True:
        return True

    # Returns a list of {"symbol": JalSymbol, "currency": currency_id} that describes symbols involved into ledger
    # operations between begin and end timestamps or that have non-zero value in ledger. The 'symbol' is the active
    # listing for its currency, so its text, identifiers and location resolve against that exact listing. If an asset
    # has ledger activity but no active listing for the account currency the symbol is empty (JalSymbol(0)) - such
    # rows have no downloadable location and are skipped by the quote downloader.
    @classmethod
    def get_active_symbols(cls, begin: int, end: int) -> list:
        symbols = []
        query = cls._exec("SELECT DISTINCT l.asset_id, a.currency_id, s.id "
                          "FROM ledger l LEFT JOIN accounts a ON a.id=l.account_id "
                          "LEFT JOIN asset_symbol s ON s.asset_id=l.asset_id AND s.currency_id=a.currency_id AND s.active=1 "
                          "WHERE l.book_account=:assets "
                          "GROUP BY l.asset_id, a.currency_id, l.account_id, s.id "
                          "HAVING l.id = MAX(l.id) AND (l.amount_acc!='0' OR l.value_acc!='0' OR (l.timestamp>=:begin AND l.timestamp<=:end))",
                          [(":assets", BookAccount.Assets), (":begin", begin), (":end", end)])
        while query.next():
            try:
                # symbol_id may legitimately be NULL (no active asset_symbol row for this currency) -
                # default to 0 (empty symbol) rather than treating it like a malformed asset_id/currency_id
                _asset_id, currency_id, symbol_id = cls._read_record(
                    query, cast=[int, int, lambda x: int(x) if x is not None else 0])
            except TypeError:  # Skip if None is returned (i.e. there are no assets)
                continue
            symbols.append({"symbol": cls(symbol_id), "currency": currency_id})
        return symbols

    # Loads a single asset_symbol row (as a dict) plus its identifiers (in ['ID'] keyed by id_type), or an empty
    # dict if there is no such symbol. Used as the loader behind the shared UniversalCache (keyed by symbol id).
    @classmethod
    def _load_symbol_data(cls, symbol_id: int) -> dict:
        data = {}
        query = cls._exec("SELECT * FROM asset_symbol WHERE id=:id", [(":id", symbol_id)])
        if query is not None and query.next():
            data = cls._read_record(query, named=True)
            data['ID'] = {}  # Dictionary of identifiers (id_type -> id_value) linked to this symbol
            id_query = cls._exec("SELECT id_type, id_value FROM symbol_ids WHERE symbol_id=:id ORDER BY id_type",
                                 [(":id", symbol_id)])
            while id_query.next():
                id_type, id_value = cls._read_record(id_query)
                data['ID'][id_type] = id_value
        return data

    def id(self) -> int:
        return self._id

    # Returns the symbol (ticker) text
    def symbol(self) -> str:
        return self._symbol

    # Returns the asset that owns this symbol (JalAsset(0) if the symbol is empty/unknown)
    def asset(self) -> JalAsset:
        return JalAsset(self._asset_id)

    # Returns the id of the currency this listing is denominated in (may be None)
    def currency(self) -> int:
        return self._currency

    # Returns the location (data source, see AssetLocation) of this listing
    def location(self) -> int:
        return self._location

    def active(self) -> bool:
        return bool(self._active)

    def icon(self):
        return self._icon

    # Returns identifier of given type (see SymbolId) for this symbol, or '' if there is none
    def identifier(self, id_type: int) -> str:
        return self._data.get('ID', {}).get(id_type, '')

    # Returns a dict {id_type: id_value} of all identifiers linked to this symbol
    def identifiers(self) -> dict:
        return dict(self._data.get('ID', {}))

    # Attaches an identifier of given type (see SymbolId) to this symbol.
    def add_identifier(self, id_type: int, id_value: str) -> None:
        if not self._id:
            logging.error(self.tr("Can't add an identifier to an empty symbol: ") + f"{id_type} = {id_value}")
            return
        _ = self._exec("INSERT INTO symbol_ids (symbol_id, id_type, id_value) VALUES (:symbol_id, :id_type, :id_value)",
                       [(":symbol_id", self._id), (":id_type", id_type), (":id_value", id_value)])
        self._reload()  # Identifiers are part of JalAsset's cache too - refresh both

    # Adds identifier of given type to this symbol unless one is already present. An existing identifier is never
    # overwritten - a mismatching new value is only reported as an error.
    def update_identifier(self, id_type: int, id_value: str) -> None:
        existing = self.identifier(id_type)
        if existing:
            if existing != id_value:
                logging.error(self.tr("Unexpected attempt to update identifier for ")
                              + f"{self._symbol}: {existing} -> {id_value}")
            return
        self.add_identifier(id_type, id_value)

    # Applies asset details (e.g. downloaded from a data source): identifier fields (isin/reg_number/cusip) are
    # written to THIS symbol, while everything else (name/country/expiry/principal) is delegated to the owning
    # asset. This mirrors the split a symbol-scoped JalAsset.update_data used to perform.
    def update_data(self, data: dict) -> None:
        identifier_types = {'isin': SymbolId.ISIN, 'reg_number': SymbolId.REG_CODE, 'cusip': SymbolId.CUSIP}
        for key, id_type in identifier_types.items():
            if data.get(key):
                self.update_identifier(id_type, data[key])
        asset_data = {key: value for key, value in data.items() if key not in identifier_types}
        if asset_data:
            self.asset().update_data(asset_data)

    # Refreshes this symbol's data after a write. Identifiers also appear in JalAsset's cache (_data['ID']), so the
    # global invalidation is used to keep both caches consistent (mirrors JalTag.replace_with).
    def _reload(self) -> None:
        JalDB().invalidate_cache()
        self._data = self.db_cache.get_data(self._load_symbol_data, (self._id,))
