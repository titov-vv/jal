import logging
import math
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from PySide6.QtCore import Qt, QDate
from jal.constants import BookAccount, MarketDataFeed, AssetData, PredefinedAsset
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

    def __init__(self, asset_id: int = 0, data: dict = None, search: bool = False, create: bool = False) -> None:
        super().__init__(cached=True)
        try:
            self._id = int(asset_id)
        except (TypeError, ValueError):
            self._id = 0
        if self._valid_data(data, search, create):
            if search:
                self._id = self._find_asset(data)
            if create and not self._id:   # If we haven't found peer before and requested to create new record
                query = self._exec(
                    "INSERT INTO assets (type_id, full_name, isin, country_id) "
                    "VALUES (:type, :full_name, :isin, coalesce((SELECT id FROM countries WHERE code=:country), 0))",
                    [(":type", data['type']), (":full_name", data['name']),
                     (":isin", data['isin']), (":country", data['country'])], commit=True)
                self._id = query.lastInsertId()
        self._data = self.db_cache.get_data(self._load_asset_data, (self._id,))  # Load asset data from cache or DB
        self._type = self._data.get('type_id', None)
        self._name = self._data.get('full_name', '')
        self._isin = self._data.get('isin', None)
        self._country = JalCountry(self._data.get('country_id', 0))
        self._reg_number = self._data.get('data', {}).get(AssetData.RegistrationCode, '')
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
            symbols_query = self._exec("SELECT * FROM asset_tickers WHERE asset_id=:id", [(":id", asset_data['id'])])
            while symbols_query.next():
                symbol = self._read_record(symbols_query, named=True)
                del symbol['id']
                del symbol['asset_id']
                asset_data['symbols'].append(symbol)
            extra_data = {}
            data_query = self._exec("SELECT datatype, value FROM asset_data WHERE asset_id=:id ORDER BY datatype",
                                    [(":id", asset_data['id'])])
            while data_query.next():
                datatype, value = self._read_record(data_query)
                extra_data[datatype] = value
            if extra_data:
                asset_data['data'] = extra_data
        return asset_data

    def invalidate_cache(self):
        self.db_cache.clear_cache()

    # JalAsset maintains single cache available for all instances
    @classmethod
    def class_cache(cls) -> True:
        return True

    def dump(self) -> dict:
        return self._data

    def id(self) -> int:
        return self._id

    def type(self) -> int:
        return self._type

    def name(self) -> str:
        return self._name

    def isin(self) -> str:
        return self._isin

    # Returns asset symbol for given currency or all symbols if no currency is given
    def symbol(self, currency: int = None) -> str:
        if not self._data:
            return ''
        currency = None if self._type == PredefinedAsset.Money else currency  # Money have one unique symbol
        if currency is None:
            return ','.join([x['symbol'] for x in self._data['symbols'] if x['active'] == 1])  # concatenate all symbols via comma
        else:
            symbol = [x['symbol'] for x in self._data['symbols'] if x['active'] == 1 and x['currency_id'] == currency]
            return ''.join(x for x in symbol)   # return symbol or empty string (there shouldn't be more than one)

    def add_symbol(self, symbol: str, currency_id: int=None, note: str='', data_source: int=MarketDataFeed.NA) -> None:
        existing = self._read("SELECT id, symbol, description, quote_source FROM asset_tickers "
                              "WHERE asset_id=:asset_id AND symbol=:symbol AND currency_id IS :currency",
                              [(":asset_id", self._id), (":symbol", symbol), (":currency", currency_id)], named=True)
        if existing is None:  # Deactivate old symbols and create a new one
            _ = self._exec("UPDATE asset_tickers SET active=0 WHERE asset_id=:asset_id AND currency_id IS :currency",
                           [(":asset_id", self._id), (":currency", currency_id)])
            _ = self._exec(
                "INSERT INTO asset_tickers (asset_id, symbol, currency_id, description, quote_source) "
                "VALUES (:asset_id, :symbol, :currency, :note, :data_source)",
                [(":asset_id", self._id), (":symbol", symbol), (":currency", currency_id),
                 (":note", note), (":data_source", data_source)])
        else:  # Update data for existing symbol
            if not existing['description']:
                _ = self._exec("UPDATE asset_tickers SET description=:note WHERE id=:id",
                               [(":note", note), (":id", existing['id'])])
            if existing['quote_source'] == MarketDataFeed.NA:
                _ = self._exec("UPDATE asset_tickers SET quote_source=:data_source WHERE id=:id",
                               [(":data_source", data_source), (":id", existing['id'])])
        self._data = self.db_cache.update_data(self._load_asset_data, (self._id,))  # Reload asset data from DB

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
            else:
                logging.warning(self.tr("There are no quote/rate for ") +
                                f"{self.symbol(currency_id)} ({JalAsset(currency_id).symbol()}) {ts2d(timestamp)}")
                return 0, Decimal('0')
        return int(quote[0]), Decimal(quote[1])

    # Return a list of tuples (timestamp:int, quote:Decimal) of all quotes available for asset
    # for time interval begin-end
    # If adjust_splits is True then quotes will be corrected for each split
    def quotes(self, begin: int, end: int, currency_id: int, adjust_splits=False) -> list:
        quotes = []
        splits = {}  # Dictionary of timestamp:coefficient for splits
        if adjust_splits:  # Get all splits recorded for the asset and create and fill the dictionary
            query = self._exec("SELECT a.timestamp, a.qty AS x, r.qty AS y "
                               "FROM asset_actions AS a LEFT JOIN action_results AS r ON a.oid=r.action_id "
                               "WHERE a.asset_id=:asset_id AND a.type=:split ORDER BY a.timestamp",
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

    # Returns a quote source id defined for given currency (currency_id can be None)
    def quote_source(self, currency_id: int) -> int:
        source_id = self._read("SELECT quote_source FROM asset_tickers "
                               "WHERE asset_id=:asset AND currency_id IS :currency",
                               [(":asset", self._id), (":currency", currency_id)])
        if source_id is None:
            return MarketDataFeed.NA
        else:
            return source_id

    # Returns a dict (ID-Name) of all available data sources
    @classmethod
    def get_sources_list(cls) -> dict:
        return MarketDataFeed().get_all_names()

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

    def reg_number(self):
        return self._reg_number

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

    # Updates relevant asset data fields with information provided in data dictionary
    def update_data(self, data: dict) -> None:
        updaters = {
            'isin': self._update_isin,
            'name': self._update_name,
            'country': self._update_country,
            'reg_number': self._update_reg_number,
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

    def _update_isin(self, new_isin: str) -> None:
        if self._isin:
            if new_isin != self._isin:
                logging.error(self.tr("Unexpected attempt to update ISIN for ")
                              + f"{self.symbol()}: {self._isin} -> {new_isin}")
        else:
            _ = self._exec("UPDATE assets SET isin=:new_isin WHERE id=:id",
                           [(":new_isin", new_isin), (":id", self._id)])
            self._isin = new_isin

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

    def _update_reg_number(self, new_number: str) -> None:
        if new_number != self._reg_number:
            _ = self._exec("INSERT OR REPLACE INTO asset_data(asset_id, datatype, value) "
                           "VALUES(:asset_id, :datatype, :reg_number)",
                           [(":asset_id", self._id), (":datatype", AssetData.RegistrationCode),
                            (":reg_number", new_number)])
            self._reg_number = new_number
            logging.info(self.tr("Reg.number updated for ")
                         + f"{self.symbol()}: {self._reg_number} -> {new_number}")

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

    def _valid_data(self, data: dict, search: bool = False, create: bool = False) -> bool:
        if data is None:
            return False
        data['isin'] = data['isin'] if 'isin' in data else ''
        data['name'] = data['name'] if 'name' in data else ''
        data['country'] = data['country'] if 'country' in data else ''
        data['symbol'] = data['symbol'] if 'symbol' in data else ''
        data['reg_number'] = data['reg_number'] if 'reg_number' in data else ''
        return True

    def _find_asset(self, data: dict) -> int:
        id = None
        if data['isin']:
            # Select either by ISIN if no symbol given OR by both ISIN & symbol
            id = self._read("SELECT id FROM assets_ext "
                            "WHERE ((isin=:isin OR isin='') AND symbol=:symbol) OR (isin=:isin AND :symbol='')",
                            [(":isin", data['isin']), (":symbol", data['symbol'])])
            if id is None and data['symbol']:  # Make one more try by ISIN only if no match for ISIN+Symbol due to symbol change
                id = self._read("SELECT id FROM assets_ext WHERE isin=:isin", [(":isin", data['isin'])])
            if id is None:
                return 0
            else:
                return id
        if data['reg_number']:
            id = self._read("SELECT asset_id FROM asset_data WHERE datatype=:datatype AND value=:reg_number",
                            [(":datatype", AssetData.RegistrationCode), (":reg_number", data['reg_number'])])
            if id is not None:
                return id
        if data['symbol']:
            if 'type' in data:
                if 'expiry' in data:
                    id = self._read("SELECT a.id FROM assets_ext a "
                                    "LEFT JOIN asset_data d ON a.id=d.asset_id AND d.datatype=:datatype "
                                    "WHERE symbol=:symbol COLLATE NOCASE AND type_id=:type AND value=:value",
                                    [(":datatype", AssetData.ExpiryDate), (":symbol", data['symbol']),
                                     (":type", data['type']), (":value", data['expiry'])])
                else:
                    id = self._read("SELECT id FROM assets_ext "
                                    "WHERE symbol=:symbol COLLATE NOCASE and type_id=:type",
                                    [(":symbol", data['symbol']), (":type", data['type'])])
            else:
                id = self._read("SELECT id FROM assets_ext WHERE symbol=:symbol COLLATE NOCASE",
                                [(":symbol", data['symbol'])])
            if id is not None:
                return id
        if data['name']:
            id = self._read("SELECT id FROM assets_ext WHERE full_name=:name COLLATE NOCASE",
                            [(":name", data['name'])])
        if id is None:
            return 0
        else:
            return id

    # Method returns a list of {"asset": JalAsset, "currency" currency_id} that describes assets involved into ledger
    # operations between begin and end timestamps or that have non-zero value in ledger
    @classmethod
    def get_active_assets(cls, begin: int, end: int) -> list:
        assets = []
        query = cls._exec("SELECT DISTINCT l.asset_id, a.currency_id "
                          "FROM ledger l LEFT JOIN accounts a ON a.id=l.account_id "
                          "WHERE l.book_account=:assets "
                          "GROUP BY l.asset_id, a.currency_id, l.account_id "
                          "HAVING l.id = MAX(l.id) AND (l.amount_acc!='0' OR l.value_acc!='0' OR (l.timestamp>=:begin AND l.timestamp<=:end))",
                          [(":assets", BookAccount.Assets), (":begin", begin), (":end", end)])
        while query.next():
            try:
                asset_id, currency_id = super(JalAsset, JalAsset)._read_record(query, cast=[int, int])
            except TypeError:  # Skip if None is returned (i.e. there are no assets)
                continue
            assets.append({"asset": JalAsset(asset_id), "currency": currency_id})
        return assets

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
