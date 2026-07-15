from jal.db.db import JalDB
from jal.constants import AssetData
from jal.universal_cache import UniversalCache

class JalTag(JalDB):
    db_cache = UniversalCache()

    def __init__(self, tag_id: int = 0) -> None:
        super().__init__(cached=True)
        self._id = tag_id
        self._data = self.db_cache.get_data(self._load_tag_data, (self._id,))  # Load tag data from cache or DB
        self._name = self._data['tag'] if self._data is not None else ''
        self._iconfile = self._data['icon_file'] if self._data is not None else ''

    def invalidate_cache(self):
        self.db_cache.clear_cache()

    # JalTag maintains single cache available for all instances
    @classmethod
    def class_cache(cls) -> True:
        return True

    # Loads a single tag row (as a dict) from the DB by its id, or None if there is no such tag.
    # Used as the loader function behind the shared UniversalCache (keyed by tag id).
    @classmethod
    def _load_tag_data(cls, tag_id: int) -> dict:
        return cls._read("SELECT * FROM tags WHERE id=:id", [(":id", tag_id)], named=True)

    # Returns a dict {tag_id: 'icon_filename'} of all tags that have icons assigned
    @classmethod
    def icon_files(cls) -> dict:
        icons = {}
        query = cls._exec("SELECT id, icon_file FROM tags WHERE icon_file!=''")
        while query.next():
            tag_id, filename = cls._read_record(query)
            icons[tag_id] = filename
        return icons

    def id(self) -> int:
        return self._id

    # Returns country name in given language or in current interface language if no argument is given
    def name(self) -> str:
        return self._name

    # Returns the name of icon file that is assigned to the tag
    def icon(self) -> str:
        return self._iconfile

    def replace_with(self, new_id):
        self._exec("UPDATE action_details SET tag_id=:new_id WHERE tag_id=:old_id",
                   [(":new_id", new_id), (":old_id", self._id)])
        self._exec("UPDATE asset_data SET value=:new_id WHERE datatype=:tag AND value=:old_id",
                   [(":tag", AssetData.Tag), (":new_id", str(new_id)), (":old_id", self._id)])
        self._exec("DELETE FROM tags WHERE id=:old_id", [(":old_id", self._id)], commit=True)
        JalDB().invalidate_cache()  # Full DB as it impacts JalAsset cache also
        self._id = 0
