import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from jal.constants import MarketDataFeed, AssetData, PredefinedAsset
from jal.db.db import JalDB
from jal.db.country import JalCountry


class JalAsset(JalDB):
    def __init__(self, id: int = 0, data: dict = None, search: bool = False, create: bool = False) -> None:
        super().__init__()
        self._id = id
        if self._valid_data(data, search, create):
            if search:
                self._id = self._find_asset(data)
            if create and not self._id:   # If we haven't found peer before and requested to create new record
                query = self._executeSQL(
                    "INSERT INTO assets (type_id, full_name, isin, country_id) "
                    "VALUES (:type, :full_name, :isin, coalesce((SELECT id FROM countries WHERE code=''), 0))",
                    [(":type", data['type']), (":full_name", data['name']),
                     (":isin", data['isin']), (":country_id", data['country'])], commit=True)
                self._id = query.lastInsertId()
        self._data = self._readSQL("SELECT type_id, full_name, isin, country_id FROM assets WHERE id=:id",
                                   [(":id", self._id)], named=True)
        self._type = self._data['type_id'] if self._data is not None else None
        self._name = self._data['full_name'] if self._data is not None else ''
        self._isin = self._data['isin'] if self._data is not None else None
        self._country_id = self._data['country_id'] if self._data is not None else None
        self._reg_number = self._readSQL("SELECT value FROM asset_data WHERE datatype=:datatype AND asset_id=:id",
                                         [(":datatype", AssetData.RegistrationCode), (":id", self._id)])

    def id(self) -> int:
        return self._id

    def type(self) -> int:
        return self._type

    def name(self) -> str:
        return self._name

    # Returns asset symbol for given currency or all symbols if no currency is given
    def symbol(self, currency: int = None) -> str:
        if currency is None:
            query = self._executeSQL("SELECT symbol FROM asset_tickers WHERE asset_id=:asset_id AND active=1",
                                     [(":asset_id", self._id)])
            symbols = []
            while query.next():
                symbols.append(self._readSQLrecord(query))
            return ','.join([x for x in symbols])  # concatenate all symbols via comma
        else:
            return self._readSQL("SELECT symbol FROM asset_tickers "
                                 "WHERE asset_id=:asset_id AND active=1 AND currency_id=:currency_id",
                                 [(":asset_id", self._id), (":currency_id", currency)])

    def add_symbol(self, symbol: str, currency_id: int, note: str, data_source: int = MarketDataFeed.NA) -> None:
        existing = self._readSQL("SELECT id, symbol, description, quote_source FROM asset_tickers "
                                 "WHERE asset_id=:asset_id AND symbol=:symbol AND currency_id=:currency",
                                 [(":asset_id", self._id), (":symbol", symbol), (":currency", currency_id)], named=True)
        if existing is None:  # Deactivate old symbols and create a new one
            _ = self._executeSQL("UPDATE asset_tickers SET active=0 WHERE asset_id=:asset_id AND currency_id=:currency",
                                 [(":asset_id", self._id), (":currency", currency_id)])
            _ = self._executeSQL(
                "INSERT INTO asset_tickers (asset_id, symbol, currency_id, description, quote_source) "
                "VALUES (:asset_id, :symbol, :currency, :note, :data_source)",
                [(":asset_id", self._id), (":symbol", symbol), (":currency", currency_id),
                 (":note", note), (":data_source", data_source)])
        else:  # Update data for existing symbol
            if not existing['description']:
                _ = self._executeSQL("UPDATE asset_tickers SET description=:note WHERE id=:id",
                                     [(":note", note), (":id", existing['id'])])
            if existing['quote_source'] == MarketDataFeed.NA:
                _ = self._executeSQL("UPDATE asset_tickers SET quote_source=:data_source WHERE id=:id",
                                     [(":data_source", data_source), (":id", existing['id'])])

    def country_name(self) -> str:
        return self._readSQL("SELECT name FROM countries WHERE id=:id", [(":id", self._country_id)])

    # Returns tuple in form of (timestamp:int, quote:Decimal) that contains last found quotation in given currency.
    # Returned timestamp might be less than given. Returns (0, 0) if no quotation information present in db.
    def quote(self, timestamp: int, currency_id: int) -> tuple:
        quote = self._readSQL("SELECT timestamp, quote FROM quotes WHERE asset_id=:asset_id "
                              "AND currency_id=:currency_id AND timestamp<=:timestamp ORDER BY timestamp DESC LIMIT 1",
                              [(":asset_id", self._id), (":currency_id", currency_id), (":timestamp", timestamp)])
        if quote is None:
            return 0, Decimal('0')
        return int(quote[0]), Decimal(quote[1])

    # Set quotations for given currency_id. Quotations is a list of {'timestamp':int, 'quote':Decimal} values
    def set_quotes(self, quotations: list, currency_id: int) -> None:
        data = [x for x in quotations if x['timestamp'] is not None and x['quote'] is not None]  # Drop Nones
        if data:
            for quote in quotations:
                _ = self._executeSQL("INSERT OR REPLACE INTO quotes (asset_id, currency_id, timestamp, quote) "
                                     "VALUES(:asset_id, :currency_id, :timestamp, :quote)",
                                     [(":asset_id", self._id), (":currency_id", currency_id),
                                      (":timestamp", quote['timestamp']), (":quote", quote['quote'])])  # FIXME quote['quote'] should be casted from Decimal to str, but tests are failing as something calls method with float values
            begin = min(data, key=lambda x: x['timestamp'])['timestamp']
            end = max(data, key=lambda x: x['timestamp'])['timestamp']
            logging.info(self.tr("Quotations were updated: ") +
                         f"{self.symbol(currency_id)} ({JalAsset(currency_id).symbol()}) "  
                         f"{datetime.utcfromtimestamp(begin).strftime('%d/%m/%Y')} - "
                         f"{datetime.utcfromtimestamp(end).strftime('%d/%m/%Y')}")

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
            _ = self._executeSQL("UPDATE assets SET isin=:new_isin WHERE id=:id",
                                 [(":new_isin", new_isin), (":id", self._id)])
            self._isin = new_isin

    def _update_name(self, new_name: str) -> None:
        if not self._name:
            _ = self._executeSQL("UPDATE assets SET full_name=:new_name WHERE id=:id",
                                 [(":new_name", new_name), (":id", self._id)])
            self._name = new_name

    def _update_country(self, new_code: str) -> None:
        country = JalCountry(self._country_id)
        if new_code.lower() != country.code().lower():
            new_country = JalCountry(data={'code': new_code.lower()}, search=True)
            if new_country.id():
                _ = self._executeSQL("UPDATE assets SET country_id=:new_country_id WHERE id=:asset_id",
                                     [(":new_country_id", new_country.id()), (":asset_id", self._id)])
                self._country_id = new_country.id()
                logging.info(self.tr("Country updated for ")
                             + f"{self.symbol()}: {country.name()} -> {new_country.name()}")

    def _update_reg_number(self, new_number: str) -> None:
        if new_number != self._reg_number:
            _ = self._executeSQL("INSERT OR REPLACE INTO asset_data(asset_id, datatype, value) "
                                 "VALUES(:asset_id, :datatype, :reg_number)",
                                 [(":asset_id", self._id), (":datatype", AssetData.RegistrationCode),
                                  (":reg_number", new_number)])
            self._reg_number = new_number
            logging.info(self.tr("Reg.number updated for ")
                         + f"{self.symbol()}: {self._reg_number} -> {new_number}")

    def _update_expiration(self, new_expiration: int) -> None:
        _ = self._executeSQL("INSERT OR REPLACE INTO asset_data(asset_id, datatype, value) "
                             "VALUES(:asset_id, :datatype, :expiry)",
                             [(":asset_id", self._id), (":datatype", AssetData.ExpiryDate),
                              (":expiry", str(new_expiration))])

    def _update_principal(self, principal: str) -> None:
        if self._type != PredefinedAsset.Bond:
            return
        try:
            principal = Decimal(principal)
        except InvalidOperation:
            return
        if principal > Decimal('0'):
            _ = self._executeSQL("INSERT OR REPLACE INTO asset_data(asset_id, datatype, value) "
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
            id = self._readSQL("SELECT id FROM assets_ext "
                               "WHERE ((isin=:isin OR isin='') AND symbol=:symbol) OR (isin=:isin AND :symbol='')",
                               [(":isin", data['isin']), (":symbol", data['symbol'])])
            if id is None:
                return 0
            else:
                return id
        if data['reg_number']:
            id = self._readSQL("SELECT asset_id FROM asset_data WHERE datatype=:datatype AND value=:reg_number",
                               [(":datatype", AssetData.RegistrationCode), (":reg_number", data['reg_number'])])
            if id is not None:
                return id
        if data['symbol']:
            if 'type' in data:
                if 'expiry' in data:
                    id = self._readSQL("SELECT a.id FROM assets_ext a "
                                       "LEFT JOIN asset_data d ON a.id=d.asset_id AND d.datatype=:datatype "
                                       "WHERE symbol=:symbol COLLATE NOCASE AND type_id=:type AND value=:value",
                                       [(":datatype", AssetData.ExpiryDate), (":symbol", data['symbol']),
                                        (":type", data['type']), (":value", data['expiry'])])
                else:
                    id = self._readSQL("SELECT id FROM assets_ext "
                                       "WHERE symbol=:symbol COLLATE NOCASE and type_id=:type",
                                       [(":symbol", data['symbol']), (":type", data['type'])])
            else:
                id = self._readSQL("SELECT id FROM assets_ext WHERE symbol=:symbol COLLATE NOCASE",
                                   [(":symbol", data['symbol'])])
            if id is not None:
                return id
        if data['name']:
            id = self._readSQL("SELECT id FROM assets_ext WHERE full_name=:name COLLATE NOCASE",
                               [(":name", data['name'])])
        if id is None:
            return 0
        else:
            return id
