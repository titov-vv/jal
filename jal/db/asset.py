from decimal import Decimal
from jal.db.db import JalDB


class JalAsset(JalDB):
    def __init__(self, id=0):
        super().__init__()
        self._id = id
        self._data = self._readSQL("SELECT type_id, country_id FROM assets WHERE id=:id",
                                   [(":id", self._id)], named=True)
        self._type = self._data['type_id'] if self._data is not None else None
        self._country_id = self._data['country_id'] if self._data is not None else None

    def id(self) -> int:
        return self._id

    def type(self):
        return self._type

    def country_name(self) -> str:
        return self._readSQL("SELECT name FROM countries WHERE id=:id", [(":id", self._country_id)])

    # Returns tuple in form of (timestamp:int, quote:Decimal) that contains last found quotation in given currency.
    # Returned timestamp might be less than given. Returns (0, 0) if no quotation information present in db.
    def quote(self, timestamp, currency_id) -> tuple:
        quote = self._readSQL("SELECT timestamp, quote FROM quotes WHERE asset_id=:asset_id "
                              "AND currency_id=:currency_id AND timestamp<=:timestamp ORDER BY timestamp DESC LIMIT 1",
                              [(":asset_id", self._id), (":currency_id", currency_id), (":timestamp", timestamp)])
        if quote is None:
            return 0, Decimal('0')
        return int(quote[0]), Decimal(quote[1])
