from jal.db.db import JalDB


class JalCategory(JalDB):
    def __init__(self, id: int = 0):
        super().__init__()
        self._id = id
        self._data = self._readSQL("SELECT name FROM categories WHERE id=:category_id",
                                   [(":category_id", self._id)], named=True)
        self._name = self._data['name'] if self._data is not None else None

    def id(self) -> int:
        return self._id

    def name(self) -> str:
        return self._name
