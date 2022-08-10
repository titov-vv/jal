import logging
from datetime import datetime
from decimal import Decimal
from jal.db.db import JalDB


class JalAsset(JalDB):
    def __init__(self, id : int = 0):
        super().__init__()
        self._id = id
        self._data = self._readSQL("SELECT type_id, full_name, country_id FROM assets WHERE id=:id",
                                   [(":id", self._id)], named=True)
        self._type = self._data['type_id'] if self._data is not None else None
        self._name = self._data['full_name'] if self._data is not None else ''
        self._country_id = self._data['country_id'] if self._data is not None else None

    def id(self) -> int:
        return self._id

    def type(self):
        return self._type

    def name(self):
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
