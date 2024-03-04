from jal.db.db import JalDB
from jal.constants import AssetData

class JalTag(JalDB):
    db_cache = []

    def __init__(self, tag_id: int = 0) -> None:
        super().__init__(cached=True)
        if not JalTag.db_cache:
            self._fetch_data()
        self._id = tag_id
        try:
            self._data = [x for x in self.db_cache if x['id'] == self._id][0]
        except IndexError:
            self._data = None
        self._name = self._data['tag'] if self._data is not None else ''
        self._iconfile = self._data['icon_file'] if self._data is not None else ''

    def invalidate_cache(self):
        self._fetch_data()

    # JalCountry maintains single cache available for all instances
    @classmethod
    def class_cache(cls) -> True:
        return True

    # Returns a dict {tag_id: 'icon_filename'} of all tags that have icons assigned
    @classmethod
    def icon_files(cls) -> dict:
        icons = {}
        query = cls._exec("SELECT id, icon_file FROM tags WHERE icon_file!=''")
        while query.next():
            tag_id, filename = cls._read_record(query)
            icons[tag_id] = filename
        return icons

    def _fetch_data(self):
        JalTag.db_cache = []
        query = self._exec("SELECT * FROM tags ORDER BY id")
        while query.next():
            JalTag.db_cache.append(self._read_record(query, named=True))

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
