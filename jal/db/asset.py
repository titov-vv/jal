import logging
import math
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from PySide6.QtCore import Qt, QDate
from jal.constants import AssetLocation, AssetData, PredefinedAsset, SymbolId
from jal.db.db import JalDB
from jal.db.helpers import format_decimal, year_begin, year_end, day_begin
from jal.db.country import JalCountry
from jal.db.tag import JalTag
from jal.widgets.helpers import ts2d
from jal.universal_cache import UniversalCache


# Helper function to convert db timestamp string into an integer and replace it as 0 if error happens
def db_timestamp2int(timestamp_string: str) -> int:
    try:
        timestamp = int(timestamp_string)
    except ValueError:
        timestamp = 0
    return timestamp


class JalAsset(JalDB):
    db_cache = UniversalCache()

    def __init__(self, asset_id: int = 0) -> None:
        super().__init__(cached=True)
        try:
            self._id = int(asset_id)
        except (TypeError, ValueError):
            self._id = 0
        self._data = self.db_cache.get_data(self._load_asset_data, (self._id,))  # Load asset data from cache or DB
        self._type = self._data.get('type_id', None)
        self._name = self._data.get('full_name', '')
        self._country = JalCountry(self._data.get('country_id', 0))
        self._expiry = int(self._data.get('data', {}).get(AssetData.ExpiryDate, 0))
        self._principal = self._data.get('data', {}).get(AssetData.PrincipalValue, '')
        self._principal = Decimal(self._principal) if self._principal else Decimal('0')
        try:
            self._tag = JalTag(int(self._data.get('data', {}).get(AssetData.Tag, 0)))
        except (AttributeError, ValueError, TypeError):
            self._tag = JalTag(0)

    def _load_asset_data(self, asset_id: int) -> dict:
        asset_data = {}
        query = self._exec("SELECT * FROM assets WHERE id=:id", [(":id", asset_id)])
        if query.next():
            asset_data = self._read_record(query, named=True)
            asset_data['symbols'] = []
            asset_data['ID'] = {}  # Dictionary of various asset IDs linked to symbols
            symbols_query = self._exec("SELECT * FROM asset_symbol WHERE asset_id=:id", [(":id", asset_data['id'])])
            while symbols_query.next():
                symbol = self._read_record(symbols_query, named=True)
                del symbol['asset_id']
                asset_data['symbols'].append(symbol)
                id_query = self._exec("SELECT id_type, id_value FROM symbol_ids WHERE symbol_id=:id ORDER BY id_type",
                                        [(":id", symbol['id'])])
                while id_query.next():
                    it_type, id_value = self._read_record(id_query)
                    asset_data['ID'][(symbol['id'], it_type)] = id_value
            extra_data = {}
            data_query = self._exec("SELECT datatype, value FROM asset_data WHERE asset_id=:id ORDER BY datatype",
                                    [(":id", asset_data['id'])])
            while data_query.next():
                datatype, value = self._read_record(data_query)
                extra_data[datatype] = value
            if extra_data:
                asset_data['data'] = extra_data
        return asset_data

    # returns a list of IDs of given type that are defined for this asset
    def _get_id(self, id_type: int) -> list:
        return [value for (key, value) in self._data['ID'].items() if key[1] == id_type]

    def invalidate_cache(self):
        self.db_cache.clear_cache()

    # JalAsset maintains single cache available for all instances
    @classmethod
    def class_cache(cls) -> True:
        return True

    # Creates a JalAsset object from a symbol id by resolving the owning asset (see also JalSymbol.asset())
    @classmethod
    def from_symbol(cls, symbol_id: int) -> "JalAsset":
        asset_id = cls._read("SELECT asset_id FROM asset_symbol WHERE id=:id", [(":id", symbol_id)])
        return cls(asset_id)

    def dump(self) -> dict:
        return self._data

    def id(self) -> int:
        return self._id

    def type(self) -> int:
        return self._type

    def name(self) -> str:
        return self._name

    # Returns the first identifier of given type found across any of the asset's symbols ('' if not present).
    # For an identifier scoped to a specific listing use JalSymbol.identifier().
    def symbol_id(self, id_type: int) -> str:
        matches = self._get_id(id_type)
        return matches[0] if matches else ''

    # Returns asset symbol for given currency or all symbols if no currency is given.
    # For a specific listing's symbol text use JalSymbol.symbol().
    def symbol(self, currency: int = None) -> str:
        if not self._data:
            return ''
        currency = None if self._type == PredefinedAsset.Money else currency  # Money have one unique symbol
        if currency is None:
            return ','.join([x['symbol'] for x in self._data['symbols'] if x['active'] == 1])  # concatenate all symbols via comma
        else:
            symbol = [x['symbol'] for x in self._data['symbols'] if x['active'] == 1 and x['currency_id'] == currency]
            return ''.join(x for x in symbol)   # return symbol or empty string (there shouldn't be more than one)

    # Returns list of ids of asset's active symbols
    def active_symbol_ids(self) -> list:
        return [x['id'] for x in self._data.get('symbols', []) if x['active'] == 1]

    # A symbol/identifier write touches both this (asset-keyed) cache and the separate JalSymbol (symbol-keyed)
    # cache - e.g. add_symbol deactivates sibling symbols and add_identifier changes a symbol's identifiers.
    # JalSymbol can't be imported here (it imports JalAsset), so the global invalidation is used to clear every
    # JalDB cache at once (mirrors JalTag.replace_with); this asset's data is then reloaded for continued use.
    def _refresh_after_symbol_write(self) -> None:
        JalDB().invalidate_cache()
        self._data = self.db_cache.get_data(self._load_asset_data, (self._id,))

    # Adds a new symbol to the asset (or returns the existing one's id if it already exists).
    # Returns the id of the resulting asset_symbol row.
    def add_symbol(self, symbol: str, currency_id, location_id: int) -> int:
        # A traditional security is a single listing no matter which venue a statement happens to name (the exchange
        # is informational), so it is matched by (asset, symbol, currency) with the location ignored and the
        # first-seen location kept. A blockchain token is a genuinely separate listing per chain - keyed by its own
        # contract address - so for a chain location the match and the deactivation are scoped by location too, and a
        # new chain adds a second active symbol rather than replacing the existing one.
        on_chain = location_id in AssetLocation.BLOCKCHAINS
        scope = [(":asset_id", self._id), (":currency", currency_id)]
        location_clause = " AND location_id=:location_id" if on_chain else ""
        if on_chain:
            scope.append((":location_id", location_id))
        existing = self._read("SELECT id FROM asset_symbol "
                              "WHERE asset_id=:asset_id AND symbol=:symbol AND currency_id IS :currency" + location_clause,
                              scope + [(":symbol", symbol)], named=True)
        if existing is None:  # Deactivate the superseded symbol(s) and create a new one
            _ = self._exec("UPDATE asset_symbol SET active=0 "
                           "WHERE asset_id=:asset_id AND currency_id IS :currency" + location_clause, scope)
            query = self._exec(
                "INSERT INTO asset_symbol (asset_id, symbol, currency_id, location_id) "
                "VALUES (:asset_id, :symbol, :currency, :location_id)",
                [(":asset_id", self._id), (":symbol", symbol), (":currency", currency_id),
                 (":location_id", location_id)])
            new_id = query.lastInsertId() if query is not None else 0
        else:
            new_id = existing['id']
        self._refresh_after_symbol_write()  # add_symbol may deactivate sibling symbols - refresh JalSymbol cache too
        return new_id

    # Attaches an identifier of given type (see SymbolId) to a specific, caller-supplied symbol id.
    # Never guesses which symbol an identifier belongs to - the caller must know it already.
    def add_identifier(self, symbol_id: int, id_type: int, id_value: str) -> None:
        _ = self._exec("INSERT INTO symbol_ids (symbol_id, id_type, id_value) VALUES (:symbol_id, :id_type, :id_value)",
                       [(":symbol_id", symbol_id), (":id_type", id_type), (":id_value", id_value)])
        self._refresh_after_symbol_write()  # identifiers are part of the JalSymbol cache too - refresh it

    # Adds identifier of given type to given symbol of the asset unless the symbol already has one.
    # An existing identifier is never overwritten - a mismatching new value is only reported as an error.
    def update_identifier(self, symbol_id: int, id_type: int, id_value: str) -> None:
        if not symbol_id:
            logging.error(self.tr("No exact symbol to link identifier with: ")
                          + f"{self.symbol()}: {id_type} = {id_value}")
            return
        existing = self._data['ID'].get((symbol_id, id_type), '')
        if existing:
            if existing != id_value:
                logging.error(self.tr("Unexpected attempt to update identifier for ")
                              + f"{self.symbol()}: {existing} -> {id_value}")
            return
        self.add_identifier(symbol_id, id_type, id_value)

    # Returns country object for the asset
    def country(self) -> JalCountry:
        return self._country

    def country_name(self) -> str:
        return self._country.name()

    # Returns tuple in form of (timestamp:int, quote:Decimal) that contains last found quotation in given currency.
    # Returns (timestamp, 1) if quotation is requested relative to itself
    # Returned timestamp might be less than given.
    # Returns (0, 0) if no quotation information present in db. Return value (timestamp, 0) is a valid quote
    def quote(self, timestamp: int, currency_id: int) -> tuple:
        if self._id == currency_id:
            return timestamp, Decimal('1')
        quote = self._read("SELECT timestamp, quote FROM quotes WHERE asset_id=:asset_id "
                           "AND currency_id=:currency_id AND timestamp<=:timestamp ORDER BY timestamp DESC LIMIT 1",
                           [(":asset_id", self._id), (":currency_id", currency_id), (":timestamp", timestamp)])
        if quote is None:
            if self._type == PredefinedAsset.Money and currency_id != self.get_base_currency(timestamp):  # find a cross-rate
                rate1 = self.quote(timestamp, self.get_base_currency(timestamp))[1]
                rate2 = JalAsset(currency_id).quote(timestamp, self.get_base_currency(timestamp))[1]
                rate = 0 if rate2 == Decimal('0') else rate1 / rate2
                return timestamp, rate
            if self._type != PredefinedAsset.Money:
                cross_quote = self._cross_currency_quote(timestamp, currency_id)
                if cross_quote is not None:
                    return cross_quote
            logging.warning(self.tr("There are no quote/rate for ") +
                            f"{self.symbol(currency_id)} ({JalAsset(currency_id).symbol()}) {ts2d(timestamp)}")
            return 0, Decimal('0')
        return int(quote[0]), Decimal(quote[1])

    # A non-Money asset is often quoted in one currency only while it may be held in an account denominated in
    # any other - crypto sources, for example.
    # The value is taken from the asset's own most recent quote in whatever currency it exists and converted with
    # the Money cross-rate of that currency. Without this the asset values at zero for every consumer - balances,
    # holdings and reports alike - whenever the account currency differs from the currency of the source.
    # Returns None when the asset has no quote at all, leaving the caller to report the miss.
    # Only ever called for a non-Money asset: currencies resolve through the base-currency cross-rate above, and
    # letting a currency in here could recurse endlessly between two currencies that quote each other.
    def _cross_currency_quote(self, timestamp: int, currency_id: int):
        quote = self._read("SELECT timestamp, quote, currency_id FROM quotes WHERE asset_id=:asset_id "
                           "AND timestamp<=:timestamp ORDER BY timestamp DESC LIMIT 1",
                           [(":asset_id", self._id), (":timestamp", timestamp)])
        if quote is None:
            return None
        quote_timestamp, value, quote_currency = int(quote[0]), Decimal(quote[1]), int(quote[2])
        # The pivot is a currency, so this recursion always lands in the Money branch above and never comes back here
        rate = JalAsset(quote_currency).quote(timestamp, currency_id)[1]
        if rate == Decimal('0'):
            return None
        return quote_timestamp, value * rate

    # Return a list of tuples (timestamp:int, quote:Decimal) of all quotes available for asset
    # for time interval begin-end
    # If adjust_splits is True then quotes will be corrected for each split
    def quotes(self, begin: int, end: int, currency_id: int, adjust_splits=False) -> list:
        quotes = []
        splits = {}  # Dictionary of timestamp:coefficient for splits
        if adjust_splits:  # Get all splits recorded for the asset and create and fill the dictionary
            query = self._exec("SELECT a.timestamp, a.qty AS x, r.qty AS y "
                               "FROM asset_actions AS a LEFT JOIN asset_action_results AS r ON a.oid=r.action_id "
                               "LEFT JOIN asset_symbol AS s ON a.symbol_id=s.id "
                               "WHERE s.asset_id=:asset_id AND a.type=:split ORDER BY a.timestamp",
                               [(":asset_id", self._id), (":split", 4)])  #FIXME 4->CorporateAction.Split
            while query.next():
                timestamp, x, y = self._read_record(query, cast=[int, Decimal, Decimal])
                splits[timestamp] = x / y
        query = self._exec(
            "SELECT timestamp, quote FROM quotes WHERE asset_id=:asset_id "
            "AND currency_id=:currency_id AND timestamp>=:begin AND timestamp<=:end ORDER BY timestamp",
            [(":asset_id", self._id), (":currency_id", currency_id), (":begin", begin), (":end", end)])
        while query.next():
            timestamp, quote = self._read_record(query, cast=[int, Decimal])
            quotes.append((timestamp, quote))
        quotes = [(t_q, q * math.prod([splits[t_s] for t_s in splits if day_begin(t_s) > t_q])) for t_q, q in quotes]
        return quotes

    # Returns tuple (begin_timestamp: int, end_timestamp: int) that defines timestamp range for which quotations are
    # available in database for given currency
    def quotes_range(self, currency_id: int) -> tuple:
        try:
            begin, end = self._read("SELECT MIN(timestamp), MAX(timestamp) FROM quotes "
                                    "WHERE asset_id=:asset_id AND currency_id=:currency_id",
                                    [(":asset_id", self._id), (":currency_id", currency_id)])
        except TypeError:
            begin = end = 0
        begin = db_timestamp2int(begin)
        end = db_timestamp2int(end)
        return begin, end

    # Returns the location (see AssetLocation) of the symbol defined for given currency (currency_id can be None).
    # For a specific listing's location use JalSymbol.location().
    def location(self, currency_id: int) -> int:
        location_id = self._read("SELECT location_id FROM asset_symbol "
                                 "WHERE asset_id=:asset AND currency_id IS :currency",
                                 [(":asset", self._id), (":currency", currency_id)])
        return location_id

    # Returns a dict (ID-Name) of all available locations
    @classmethod
    def get_sources_list(cls) -> dict:
        return AssetLocation().get_all_names()

    # Set quotations for given currency_id. Quotations is a list of {'timestamp':int, 'quote':Decimal} values
    def set_quotes(self, quotations: list, currency_id: int) -> None:
        data = [x for x in quotations if x['timestamp'] is not None and x['quote'] is not None]  # Drop Nones
        if data:
            for quote in quotations:
                _ = self._exec("INSERT OR REPLACE INTO quotes (asset_id, currency_id, timestamp, quote) "
                               "VALUES(:asset_id, :currency_id, :timestamp, :quote)",
                               [(":asset_id", self._id), (":currency_id", currency_id),
                                (":timestamp", quote['timestamp']), (":quote", format_decimal(quote['quote']))])
            begin = min(data, key=lambda x: x['timestamp'])['timestamp']
            end = max(data, key=lambda x: x['timestamp'])['timestamp']
            self.commit()
            logging.info(self.tr("Quotations were updated: ") +
                         f"{self.symbol(currency_id)} ({JalAsset(currency_id).symbol()}) {ts2d(begin)} - {ts2d(end)}")

    # returns expiration timestamp
    def expiry(self) -> int:
        return self._expiry

    # Returns number of days before expiration (negative value if asset is expired)
    def days2expiration(self) -> int:
        if self._expiry == 0:
            return 0
        expiry_date = datetime.fromtimestamp(self._expiry, tz=timezone.utc)
        days_remaining = int((expiry_date - datetime.now(tz=timezone.utc)).total_seconds() / 86400)
        return days_remaining

    def principal(self) -> Decimal:
        return self._principal

    def tag(self) -> JalTag:
        return self._tag

    def set_tag(self, tag_id: int) -> None:
        if self._tag.id() == tag_id:
            return
        _ = self._exec("INSERT OR REPLACE INTO asset_data(asset_id, datatype, value) "
                       "VALUES(:asset_id, :datatype, :expiry)",
                       [(":asset_id", self._id), (":datatype", AssetData.Tag), (":expiry", str(tag_id))])
        self._tag = JalTag(tag_id)
        self._data = self.db_cache.update_data(self._load_asset_data, (self._id,))  # Reload asset data from DB

    # Updates asset-level data fields with information provided in data dictionary. Per-symbol identifiers
    # (isin/reg_number/cusip) are NOT handled here - they belong to a listing and are written via JalSymbol.
    def update_data(self, data: dict) -> None:
        updaters = {
            'name': self._update_name,
            'country': self._update_country,
            'expiry': self._update_expiration,
            'principal': self._update_principal
        }
        if not self._id:
            return
        for key in data:
            if data[key]:
                try:
                    updaters[key](data[key])
                except KeyError:  # No updater for this key is present
                    continue
        self._data = self.db_cache.update_data(self._load_asset_data, (self._id,))  # Reload asset data from DB

    def _update_name(self, new_name: str) -> None:
        if not self._name:
            _ = self._exec("UPDATE assets SET full_name=:new_name WHERE id=:id",
                           [(":new_name", new_name), (":id", self._id)])
            self._name = new_name

    def _update_country(self, new_code: str) -> None:
        if new_code.lower() != self._country.code().lower():
            new_country = JalCountry(data={'code': new_code.lower()}, search=True)
            if new_country.id():
                _ = self._exec("UPDATE assets SET country_id=:new_country_id WHERE id=:asset_id",
                               [(":new_country_id", new_country.id()), (":asset_id", self._id)])
                self._country_id = new_country.id()
                logging.info(self.tr("Country updated for ")
                             + f"{self.symbol()}: {self._country.name()} -> {new_country.name()}")

    def _update_expiration(self, new_expiration: int) -> None:
        _ = self._exec("INSERT OR REPLACE INTO asset_data(asset_id, datatype, value) "
                       "VALUES(:asset_id, :datatype, :expiry)",
                       [(":asset_id", self._id), (":datatype", AssetData.ExpiryDate), (":expiry", str(new_expiration))])
        self._expiry = new_expiration

    def _update_principal(self, principal: str) -> None:
        if self._type != PredefinedAsset.Bond:
            return
        try:
            principal = Decimal(principal)
        except InvalidOperation:
            return
        if principal > Decimal('0'):
            _ = self._exec("INSERT OR REPLACE INTO asset_data(asset_id, datatype, value) "
                           "VALUES(:asset_id, :datatype, :principal)",
                           [(":asset_id", self._id), (":datatype", AssetData.PrincipalValue),
                            (":principal", str(principal))])

    # Searches for an asset matching the given heuristic data (isin -> reg_number -> symbol(+type+expiry) -> name,
    # in that priority order) and returns a JalAsset for it (whose .id() is 0 if nothing was found).
    @classmethod
    def find(cls, data: dict) -> "JalAsset":
        data = dict(data)   # don't pollute caller's dict with the defaults below
        for key in ('isin', 'name', 'country', 'symbol', 'reg_number', 'cusip'):
            data.setdefault(key, '')
        return cls(cls._find_asset(data))

    @classmethod
    def _find_asset(cls, data: dict) -> int:
        aid = None
        if data['isin']:
            query = cls._exec("SELECT s.asset_id, s.symbol FROM symbol_ids i LEFT JOIN asset_symbol s ON s.id=i.symbol_id WHERE id_type=:datatype AND id_value=:isin",
                               [(":datatype", SymbolId.ISIN), (":isin", data['isin'])])
            while query.next():
                aid, symbol = cls._read_record(query, cast=[int, str])
                if data['symbol'] and data['symbol'] == symbol:  # Try to match by ISIN and symbol first
                    return aid
            if aid is not None:
                return aid
            # Unknown ISIN - fall through to the remaining criteria (callers like _match_asset_symbol
            # guard against ISIN conflicts themselves after the match)
        if data['reg_number']:
            aid = cls._read("SELECT s.asset_id FROM symbol_ids i LEFT JOIN asset_symbol s ON s.id=i.symbol_id WHERE id_type=:datatype AND id_value=:reg_code",
                            [(":datatype", SymbolId.REG_CODE), (":reg_code", data['reg_number'])], check_unique=True)
            if aid is not None:
                return aid
        if data['cusip']:
            aid = cls._read("SELECT s.asset_id FROM symbol_ids i LEFT JOIN asset_symbol s ON s.id=i.symbol_id WHERE id_type=:datatype AND id_value=:cusip",
                            [(":datatype", SymbolId.CUSIP), (":cusip", data['cusip'])], check_unique=True)
            if aid is not None:
                return aid
        if data['symbol']:
            symbols = cls._read_to_list("SELECT s.asset_id, a.type_id, d.value AS expiry FROM asset_symbol s "
                                         "LEFT JOIN assets a ON s.asset_id=a.id "
                                         "LEFT JOIN asset_data d ON s.asset_id=d.asset_id AND d.datatype=:datatype "
                                         "WHERE s.symbol=:symbol COLLATE NOCASE",
                                         [(":datatype", AssetData.ExpiryDate), (":symbol", data['symbol'])], named=True)
            if 'type' in data:
                if 'expiry' in data:
                    def expiry_match(x):  # asset_data values are stored as strings while statement provides int timestamp
                        try:
                            return int(x['expiry']) == int(data['expiry'])
                        except (TypeError, ValueError):
                            return False
                    symbols = list(filter(lambda x: x['type_id'] == data['type'] and expiry_match(x), symbols))
                else:
                    symbols = list(filter(lambda x: x['type_id'] == data['type'], symbols))
            if len(symbols) == 1:
                aid = symbols[0]['asset_id']
            if aid is not None:
                return aid
        if data['name']:
            aid = cls._read("SELECT id FROM assets WHERE full_name=:name COLLATE NOCASE", [(":name", data['name'])])
        if aid is None:
            return 0
        else:
            return aid

    # Returns the ids of crypto assets that carry an active listing with the given ticker (case-insensitive). Used to
    # spot a possible cross-chain duplicate when a fetched token has no contract-address match but reuses a ticker
    # that a known crypto asset already uses - matching by ticker alone is never safe (tickers are attacker-chosen),
    # so the caller only offers these as candidates for a user-confirmed merge.
    @classmethod
    def get_crypto_assets_by_symbol(cls, symbol: str) -> list:
        asset_ids = []
        query = cls._exec("SELECT DISTINCT s.asset_id FROM asset_symbol s LEFT JOIN assets a ON a.id=s.asset_id "
                          "WHERE s.symbol=:symbol COLLATE NOCASE AND a.type_id=:crypto AND s.active=1",
                          [(":symbol", symbol), (":crypto", PredefinedAsset.Crypto)])
        while query is not None and query.next():
            asset_ids.append(cls._read_record(query, cast=[int]))
        return asset_ids

    # Method returns a list of JalAsset objects that describe all assets defined in ledger
    @classmethod
    def get_assets(cls) -> list:
        assets = []
        query = cls._exec("SELECT id FROM assets")
        while query.next():
            asset_id = cls._read_record(query, cast=[int])
            assets.append(JalAsset(asset_id))
        return assets

    # Method returns a list of JalAsset objects that describe currencies defined in ledger
    @classmethod
    def get_currencies(cls) -> list:
        currencies = []
        query = cls._exec("SELECT id FROM currencies")
        while query.next():
            currencies.append(JalAsset(super(JalAsset, JalAsset)._read_record(query, cast=[int])))
        return currencies

    # Returns id of the base currency that was in effect for given timestamp or current base currency (for now) if
    # timestamp isn't given
    @classmethod
    def get_base_currency(cls, timestamp: int=None) -> int:
        if timestamp is None:
            timestamp = QDate.currentDate().startOfDay(Qt.UTC).toSecsSinceEpoch()
        base_id = cls._read("SELECT currency_id FROM base_currency WHERE since_timestamp<=:timestamp "
                            "ORDER BY since_timestamp DESC LIMIT 1", [(":timestamp", timestamp)])
        try:
            base_id = int(base_id)
        except TypeError:
            base_id = 0
        return base_id

    # Return a list of (timestamp, currency_id) tuples that represent currency valid currency IDs that were in force
    # after between beginning_of_the_year(begin) and end_of_the_year(end) timestamps.
    # Begin and end of year it required to cover full tax year.
    @classmethod
    def get_base_currency_history(cls, begin: int, end: int) -> list:
        history = [(year_begin(begin), cls.get_base_currency(year_begin(begin)))]
        query = cls._exec("SELECT since_timestamp, currency_id FROM base_currency "
                          "WHERE since_timestamp>:begin AND since_timestamp<=:end ORDER BY since_timestamp",
                          [(":begin", year_begin(begin)), (":end", year_end(end))])
        while query.next():
            history.append(cls._read_record(query, cast=[int, int]))
        return history


# ----------------------------------------------------------------------------------------------------------------------
# Stages a brand-new asset (assets row + symbol(s) + identifiers) before it becomes a real JalAsset.
# Deliberately NOT a JalAsset subclass: JalAsset carries a shared, class-level cache keyed by asset id
# (db_cache / class_cache()), and touching that cache mid-assembly would risk handing an incomplete asset
# to unrelated code that just does JalAsset(id) for some other purpose. This class talks to the DB directly
# and only ever creates a real, cacheable JalAsset once commit() is called.
class JalAssetCreator(JalDB):
    def __init__(self, type_id: int, name: str, country: str = '') -> None:
        super().__init__(cached=False)
        query = self._exec(
            "INSERT INTO assets (type_id, full_name, country_id) "
            "VALUES (:type, :full_name, coalesce((SELECT id FROM countries WHERE code=:country), 0))",
            [(":type", type_id), (":full_name", name), (":country", country)])
        self._id = query.lastInsertId() if query is not None else 0

    def id(self) -> int:
        return self._id

    # Returns the id of the newly created asset_symbol row.
    def add_symbol(self, symbol: str, currency_id, location_id: int) -> int:
        query = self._exec(
            "INSERT INTO asset_symbol (asset_id, symbol, currency_id, location_id) "
            "VALUES (:asset_id, :symbol, :currency, :location_id)",
            [(":asset_id", self._id), (":symbol", symbol), (":currency", currency_id),
             (":location_id", location_id)])
        return query.lastInsertId() if query is not None else 0

    # Attaches an identifier to a specific symbol id (obtained from add_symbol() above) - never guesses.
    def add_identifier(self, symbol_id: int, id_type: int, id_value: str) -> None:
        self._exec("INSERT INTO symbol_ids (symbol_id, id_type, id_value) VALUES (:symbol_id, :id_type, :id_value)",
                   [(":symbol_id", symbol_id), (":id_type", id_type), (":id_value", id_value)])

    # Finalizes staging and returns a normal, cacheable JalAsset for subsequent use.
    def commit(self) -> JalAsset:
        return JalAsset(self._id)
