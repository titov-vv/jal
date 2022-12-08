import logging
from decimal import Decimal, InvalidOperation
from jal.constants import BookAccount, MarketDataFeed, AssetData, PredefinedAsset
from jal.db.db import JalDB
from jal.db.helpers import format_decimal
from jal.db.country import JalCountry
from jal.widgets.helpers import ts2d


# Helper function to convert db timestamp string into an integer and replace it as 0 if error happens
def db_timestamp2int(timestamp_string: str) -> int:
    try:
        timestamp = int(timestamp_string)
    except ValueError:
        timestamp = 0
    return timestamp


class JalAsset(JalDB):
    def __init__(self, id: int = 0, data: dict = None, search: bool = False, create: bool = False) -> None:
        super().__init__()
        self._id = id
        if self._valid_data(data, search, create):
            if search:
                self._id = self._find_asset(data)
            if create and not self._id:   # If we haven't found peer before and requested to create new record
                query = self.execSQL(
                    "INSERT INTO assets (type_id, full_name, isin, country_id) "
                    "VALUES (:type, :full_name, :isin, coalesce((SELECT id FROM countries WHERE code=:country), 0))",
                    [(":type", data['type']), (":full_name", data['name']),
                     (":isin", data['isin']), (":country", data['country'])], commit=True)
                self._id = query.lastInsertId()
        self._data = self.readSQL("SELECT type_id, full_name, isin, country_id FROM assets WHERE id=:id",
                                  [(":id", self._id)], named=True)
        self._type = self._data['type_id'] if self._data is not None else None
        self._name = self._data['full_name'] if self._data is not None else ''
        self._isin = self._data['isin'] if self._data is not None else None
        self._country_id = self._data['country_id'] if self._data is not None else 0
        self._reg_number = self.readSQL("SELECT value FROM asset_data WHERE datatype=:datatype AND asset_id=:id",
                                        [(":datatype", AssetData.RegistrationCode), (":id", self._id)])
        self._expiry = self.readSQL("SELECT value FROM asset_data WHERE datatype=:datatype AND asset_id=:id",
                                    [(":datatype", AssetData.ExpiryDate), (":id", self._id)])

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
        if currency is None:
            query = self.execSQL("SELECT symbol FROM asset_tickers WHERE asset_id=:asset_id AND active=1",
                                 [(":asset_id", self._id)])
            symbols = []
            while query.next():
                symbols.append(self.readSQLrecord(query))
            return ','.join([x for x in symbols])  # concatenate all symbols via comma
        else:
            return self.readSQL("SELECT symbol FROM asset_tickers "
                                 "WHERE asset_id=:asset_id AND active=1 AND currency_id=:currency_id",
                                [(":asset_id", self._id), (":currency_id", currency)])

    def add_symbol(self, symbol: str, currency_id: int, note: str, data_source: int = MarketDataFeed.NA) -> None:
        existing = self.readSQL("SELECT id, symbol, description, quote_source FROM asset_tickers "
                                 "WHERE asset_id=:asset_id AND symbol=:symbol AND currency_id=:currency",
                                [(":asset_id", self._id), (":symbol", symbol), (":currency", currency_id)], named=True)
        if existing is None:  # Deactivate old symbols and create a new one
            _ = self.execSQL("UPDATE asset_tickers SET active=0 WHERE asset_id=:asset_id AND currency_id=:currency",
                             [(":asset_id", self._id), (":currency", currency_id)])
            _ = self.execSQL(
                "INSERT INTO asset_tickers (asset_id, symbol, currency_id, description, quote_source) "
                "VALUES (:asset_id, :symbol, :currency, :note, :data_source)",
                [(":asset_id", self._id), (":symbol", symbol), (":currency", currency_id),
                 (":note", note), (":data_source", data_source)])
        else:  # Update data for existing symbol
            if not existing['description']:
                _ = self.execSQL("UPDATE asset_tickers SET description=:note WHERE id=:id",
                                 [(":note", note), (":id", existing['id'])])
            if existing['quote_source'] == MarketDataFeed.NA:
                _ = self.execSQL("UPDATE asset_tickers SET quote_source=:data_source WHERE id=:id",
                                 [(":data_source", data_source), (":id", existing['id'])])

    # Returns country_id for the asset
    def country(self) -> int:
        return self._country_id

    def country_name(self) -> str:
        return self.readSQL("SELECT name FROM countries WHERE id=:id", [(":id", self._country_id)])

    # Returns tuple in form of (timestamp:int, quote:Decimal) that contains last found quotation in given currency.
    # Returned timestamp might be less than given. Returns (0, 0) if no quotation information present in db.
    def quote(self, timestamp: int, currency_id: int) -> tuple:
        quote = self.readSQL("SELECT timestamp, quote FROM quotes WHERE asset_id=:asset_id "
                              "AND currency_id=:currency_id AND timestamp<=:timestamp ORDER BY timestamp DESC LIMIT 1",
                             [(":asset_id", self._id), (":currency_id", currency_id), (":timestamp", timestamp)])
        if quote is None:
            return 0, Decimal('0')
        return int(quote[0]), Decimal(quote[1])

    # Return a list of tuples (timestamp:int, quote:Decimal) of all quotes available for asset
    # for time interval begin-end
    def quotes(self, begin: int, end: int, currency_id: int) -> list:
        quotes = []
        query = self.execSQL(
            "SELECT timestamp, quote FROM quotes WHERE asset_id=:asset_id "
            "AND currency_id=:currency_id AND timestamp>=:begin AND timestamp<=:end ORDER BY timestamp",
            [(":asset_id", self._id), (":currency_id", currency_id), (":begin", begin), (":end", end)])
        while query.next():
            timestamp, quote = self.readSQLrecord(query)
            quotes.append((timestamp, Decimal(quote)))
        return quotes

    # Returns tuple (begin_timestamp: int, end_timestamp: int) that defines timestamp range for which quotest are
    # available in database for given currency
    def quotes_range(self, currency_id: int) -> tuple:
        try:
            begin, end = self.readSQL("SELECT MIN(timestamp), MAX(timestamp) FROM quotes "
                                       "WHERE asset_id=:asset_id AND currency_id=:currency_id",
                                      [(":asset_id", self._id), (":currency_id", currency_id)])
        except TypeError:
            begin = end = 0
        begin = db_timestamp2int(begin)
        end = db_timestamp2int(end)
        return begin, end

    # Returns a quote source id defined for given currency
    def quote_source(self, currency_id: int) -> int:
        source_id = self.readSQL("SELECT quote_source FROM asset_tickers "
                                  "WHERE asset_id=:asset AND currency_id=:currency",
                                 [(":asset", self._id), (":currency", currency_id)])
        if source_id is None:
            return MarketDataFeed.NA
        else:
            return source_id

    # Returns a dict (ID-Name) of all available data sources
    @staticmethod
    def get_sources_list() -> dict:
        sources = {}
        query = JalDB.execSQL("SELECT id, name FROM data_sources")
        while query.next():
            source_id, name = JalDB.readSQLrecord(query)
            sources[source_id] = name
        return sources

    # Set quotations for given currency_id. Quotations is a list of {'timestamp':int, 'quote':Decimal} values
    def set_quotes(self, quotations: list, currency_id: int) -> None:
        data = [x for x in quotations if x['timestamp'] is not None and x['quote'] is not None]  # Drop Nones
        if data:
            for quote in quotations:
                _ = self.execSQL("INSERT OR REPLACE INTO quotes (asset_id, currency_id, timestamp, quote) "
                                     "VALUES(:asset_id, :currency_id, :timestamp, :quote)",
                                 [(":asset_id", self._id), (":currency_id", currency_id),
                                      (":timestamp", quote['timestamp']), (":quote", format_decimal(quote['quote']))])
            begin = min(data, key=lambda x: x['timestamp'])['timestamp']
            end = max(data, key=lambda x: x['timestamp'])['timestamp']
            logging.info(self.tr("Quotations were updated: ") +
                         f"{self.symbol(currency_id)} ({JalAsset(currency_id).symbol()}) {ts2d(begin)} - {ts2d(end)}")

    def expiry(self):
        return self._expiry

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

    def _update_isin(self, new_isin: str) -> None:
        if self._isin:
            if new_isin != self._isin:
                logging.error(self.tr("Unexpected attempt to update ISIN for ")
                              + f"{self.symbol()}: {self._isin} -> {new_isin}")
        else:
            _ = self.execSQL("UPDATE assets SET isin=:new_isin WHERE id=:id",
                             [(":new_isin", new_isin), (":id", self._id)])
            self._isin = new_isin

    def _update_name(self, new_name: str) -> None:
        if not self._name:
            _ = self.execSQL("UPDATE assets SET full_name=:new_name WHERE id=:id",
                             [(":new_name", new_name), (":id", self._id)])
            self._name = new_name

    def _update_country(self, new_code: str) -> None:
        country = JalCountry(self._country_id)
        if new_code.lower() != country.code().lower():
            new_country = JalCountry(data={'code': new_code.lower()}, search=True)
            if new_country.id():
                _ = self.execSQL("UPDATE assets SET country_id=:new_country_id WHERE id=:asset_id",
                                 [(":new_country_id", new_country.id()), (":asset_id", self._id)])
                self._country_id = new_country.id()
                logging.info(self.tr("Country updated for ")
                             + f"{self.symbol()}: {country.name()} -> {new_country.name()}")

    def _update_reg_number(self, new_number: str) -> None:
        if new_number != self._reg_number:
            _ = self.execSQL("INSERT OR REPLACE INTO asset_data(asset_id, datatype, value) "
                                 "VALUES(:asset_id, :datatype, :reg_number)",
                             [(":asset_id", self._id), (":datatype", AssetData.RegistrationCode),
                                  (":reg_number", new_number)])
            self._reg_number = new_number
            logging.info(self.tr("Reg.number updated for ")
                         + f"{self.symbol()}: {self._reg_number} -> {new_number}")

    def _update_expiration(self, new_expiration: int) -> None:
        _ = self.execSQL("INSERT OR REPLACE INTO asset_data(asset_id, datatype, value) "
                             "VALUES(:asset_id, :datatype, :expiry)",
                         [(":asset_id", self._id), (":datatype", AssetData.ExpiryDate),
                              (":expiry", str(new_expiration))])
        self._expiry = new_expiration

    def _update_principal(self, principal: str) -> None:
        if self._type != PredefinedAsset.Bond:
            return
        try:
            principal = Decimal(principal)
        except InvalidOperation:
            return
        if principal > Decimal('0'):
            _ = self.execSQL("INSERT OR REPLACE INTO asset_data(asset_id, datatype, value) "
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
            id = self.readSQL("SELECT id FROM assets_ext "
                               "WHERE ((isin=:isin OR isin='') AND symbol=:symbol) OR (isin=:isin AND :symbol='')",
                              [(":isin", data['isin']), (":symbol", data['symbol'])])
            if id is None:
                return 0
            else:
                return id
        if data['reg_number']:
            id = self.readSQL("SELECT asset_id FROM asset_data WHERE datatype=:datatype AND value=:reg_number",
                              [(":datatype", AssetData.RegistrationCode), (":reg_number", data['reg_number'])])
            if id is not None:
                return id
        if data['symbol']:
            if 'type' in data:
                if 'expiry' in data:
                    id = self.readSQL("SELECT a.id FROM assets_ext a "
                                       "LEFT JOIN asset_data d ON a.id=d.asset_id AND d.datatype=:datatype "
                                       "WHERE symbol=:symbol COLLATE NOCASE AND type_id=:type AND value=:value",
                                      [(":datatype", AssetData.ExpiryDate), (":symbol", data['symbol']),
                                        (":type", data['type']), (":value", data['expiry'])])
                else:
                    id = self.readSQL("SELECT id FROM assets_ext "
                                       "WHERE symbol=:symbol COLLATE NOCASE and type_id=:type",
                                      [(":symbol", data['symbol']), (":type", data['type'])])
            else:
                id = self.readSQL("SELECT id FROM assets_ext WHERE symbol=:symbol COLLATE NOCASE",
                                  [(":symbol", data['symbol'])])
            if id is not None:
                return id
        if data['name']:
            id = self.readSQL("SELECT id FROM assets_ext WHERE full_name=:name COLLATE NOCASE",
                              [(":name", data['name'])])
        if id is None:
            return 0
        else:
            return id

    # Method returns a list of {"asset": JalAsset, "currency" currency_id} that describes assets involved into ledger
    # operations between begin and end timestamps or that have non-zero value in ledger
    @staticmethod
    def get_active_assets(begin: int, end: int) -> list:
        assets = []
        query = JalDB.execSQL("SELECT MAX(l.id) AS id, l.asset_id, a.currency_id "
                                  "FROM ledger l LEFT JOIN accounts a ON a.id=l.account_id "
                                  "WHERE l.book_account=:assets "
                                  "GROUP BY l.asset_id, a.currency_id "
                                  "HAVING l.amount_acc!='0' OR (l.timestamp>=:begin AND l.timestamp<=:end)",
                              [(":assets", BookAccount.Assets), (":begin", begin), (":end", end)])
        while query.next():
            try:
                _id, asset_id, currency_id = JalDB.readSQLrecord(query)
            except TypeError:  # Skip if None is returned (i.e. there are no assets)
                continue
            assets.append({"asset": JalAsset(int(asset_id)), "currency": int(currency_id)})
        return assets

    # Method returns a list of JalAsset objects that describe currencies defined in ledger
    @staticmethod
    def get_currencies() -> list:
        currencies = []
        query = JalDB.execSQL("SELECT id FROM currencies")
        while query.next():
            currencies.append(JalAsset(int(JalDB.readSQLrecord(query))))
        return currencies
