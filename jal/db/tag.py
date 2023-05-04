from jal.db.db import JalDB


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

    def invalidate_cache(self):
        self._fetch_data()

    # JalCountry maintains single cache available for all instances
    @classmethod
    def class_cache(cls) -> True:
        return True

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

    def replace_with(self, new_id):
        self._exec("UPDATE action_details SET tag_id=:new_id WHERE tag_id=:old_id",
                   [(":new_id", new_id), (":old_id", self._id)])
        self._exec("DELETE FROM tags WHERE id=:old_id", [(":old_id", self._id)], commit=True)
        self._fetch_data()
        self._id = 0
