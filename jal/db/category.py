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

    @staticmethod
    def add_or_update_mapped_name(name: str, category_id: int) -> None:  # TODO Review, should it be not static or not
        _ = JalDB._executeSQL("INSERT OR REPLACE INTO map_category (value, mapped_to) "
                              "VALUES (:item_name, :category_id)",
                              [(":item_name", name), (":category_id", category_id)], commit=True)

    # Returns a list of all names that were mapped to some category in for of {"value", "mapped_to"}
    @staticmethod
    def get_mapped_names() -> list:
        mapped_list = []
        query = JalDB._executeSQL("SELECT value, mapped_to FROM map_category")
        while query.next():
            mapped_list.append(JalDB._readSQLrecord(query, named=True))
        return mapped_list
