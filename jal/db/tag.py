from jal.db.db import JalDB
from jal.constants import AccountData, AssetData
from jal.db.cache import DbCache

class JalTag(JalDB):
    db_cache = DbCache()

    def __init__(self, tag_id: int = 0) -> None:
        super().__init__()
        self._id = tag_id
        self._data = self.db_cache.get_data(self._load_tag_data, (self._id,))  # Load tag data from cache or DB
        self._name = self._data['tag'] if self._data is not None else ''

    # Loads a single tag row (as a dict) from the DB by its id, or None if there is no such tag.
    # Used as the loader function behind the shared DbCache (keyed by tag id).
    @classmethod
    def _load_tag_data(cls, tag_id: int) -> dict:
        return cls._read("SELECT * FROM tags WHERE id=:id", [(":id", tag_id)], named=True)

    def id(self) -> int:
        return self._id

    # Returns country name in given language or in current interface language if no argument is given
    def name(self) -> str:
        return self._name

    def replace_with(self, new_id):
        self._exec("UPDATE action_details SET tag_id=:new_id WHERE tag_id=:old_id",
                   [(":new_id", new_id), (":old_id", self._id)])
        self._exec("UPDATE asset_data SET value=:new_id WHERE datatype=:tag AND value=:old_id",
                   [(":tag", AssetData.Tag), (":new_id", str(new_id)), (":old_id", self._id)])
        self._exec("UPDATE account_data SET value=:new_id WHERE datatype=:tag AND value=:old_id",
                   [(":tag", AccountData.Tag), (":new_id", str(new_id)), (":old_id", self._id)])
        self._exec("UPDATE receipt_items SET tag_id=:new_id WHERE tag_id=:old_id",
                   [(":new_id", new_id), (":old_id", self._id)])
        self._exec("DELETE FROM tags WHERE id=:old_id", [(":old_id", self._id)], commit=True)
        JalDB().invalidate_cache()  # Full DB as it impacts JalAsset cache also
        self._id = 0
