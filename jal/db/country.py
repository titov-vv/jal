from jal.db.db import JalDB
from jal.db.settings import JalSettings


class JalCountry(JalDB):
    db_cache = []

    def __init__(self, country_id: int = 0, data: dict = None, search=False) -> None:
        super().__init__(cached=True)
        if not JalCountry.db_cache:
            self._fetch_data()
        self._id = country_id
        if self._valid_data(data):
            if search:
                self._id = self._find_country(data)
        try:
            self._data = [x for x in self.db_cache if x['id'] == self._id][0]
        except IndexError:
            self._data = None
        self._name = self._data['name'] if self._data is not None else None
        self._code = self._data['code'] if self._data is not None else None
        self._iso_code = self._data['iso_code'] if self._data is not None else None

    def invalidate_cache(self):
        self._fetch_data()

    # JalCountry maintains single cache available for all instances
    @classmethod
    def class_cache(cls) -> True:
        return True

    def _fetch_data(self):
        JalCountry.db_cache = []
        query = self._exec("SELECT * FROM countries_ext ORDER BY id")
        while query.next():
            JalCountry.db_cache.append(self._read_record(query, named=True))

    def id(self) -> int:
        return self._id

    # Returns country name in given language or in current interface language if no argument is given
    def name(self, language: str='') -> str:
        if not language:
            language = JalSettings().getLanguage()
        return self._read("SELECT c.name FROM country_names c LEFT JOIN languages l ON c.language_id=l.id "
                          "WHERE country_id=:country_id AND l.language=:language",
                          [(":country_id", self._id), (":language", language)])

    def code(self) -> str:
        return self._code

    def iso_code(self) -> str:
        return self._iso_code

    def _valid_data(self, data: dict) -> bool:
        if data is None:
            return False
        if 'code' not in data:
            return False
        return True

    def _find_country(self, data: dict) -> int:
        country_id = self._read("SELECT id FROM countries WHERE code=:code",
                                [(":code", data['code'])], check_unique=True)
        if country_id is None:
            return 0
        else:
            return country_id