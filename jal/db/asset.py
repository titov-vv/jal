from jal.db.db import JalDB


class JalAsset(JalDB):
    def __init__(self, id=0):
        super().__init__()
        self._id = id
        self._data = self._readSQL("SELECT type_id, country_id FROM assets WHERE id=:id",
                                   [(":id", self._id)], named=True)
        self._type = self._data['type_id'] if self._data is not None else None
        self._country_id = self._data['country_id'] if self._data is not None else None

    def id(self):
        return self._id

    def type(self):
        return self._type

    def country_name(self):
        return self._readSQL("SELECT name FROM countries WHERE id=:id", [(":id", self._country_id)])
