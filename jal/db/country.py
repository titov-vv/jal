from jal.db.db import JalDB
from jal.db.settings import JalSettings
from jal.universal_cache import UniversalCache


class JalCountry(JalDB):
    db_cache = UniversalCache()

    def __init__(self, country_id: int = 0, data: dict = None, search=False) -> None:
        super().__init__(cached=True)
        self._id = country_id
        if self._valid_data(data):
            if search:
                self._id = self._find_country(data)
        self._data = self.db_cache.get_data(self._load_country_data, (self._id,))  # Load country data from cache or DB
        self._name = self._data['name'] if self._data is not None else None
        self._code = self._data['code'] if self._data is not None else None
        self._iso_code = self._data['iso_code'] if self._data is not None else None

    def invalidate_cache(self):
        self.db_cache.clear_cache()

    # JalCountry maintains single cache available for all instances
    @classmethod
    def class_cache(cls) -> True:
        return True

    # Loads a single country row (as a dict) from the DB by its id, or None if there is no such country.
    # 'name' comes from the countries_ext view already localized to the current interface language.
    # Used as the loader function behind the shared UniversalCache (keyed by country id).
    @classmethod
    def _load_country_data(cls, country_id: int) -> dict:
        return cls._read("SELECT * FROM countries_ext WHERE id=:id", [(":id", country_id)], named=True)

    # Loads a country name in a specific (non-interface) language, or None if not translated.
    # Cached in the same shared UniversalCache (keyed by country id + language), so it is dropped
    # together with the rest of the cache on invalidate_cache() - e.g. on an interface language change.
    @classmethod
    def _load_country_name(cls, country_id: int, language: str) -> str:
        return cls._read(
            "SELECT c.name FROM country_names c LEFT JOIN languages l ON c.language_id=l.id "
            "WHERE country_id=:country_id AND l.language=:language",
            [(":country_id", country_id), (":language", language)])

    def id(self) -> int:
        return self._id

    # Returns country name in given language or in current interface language if no argument is given
    def name(self, language: str='') -> str:
        current_language = JalSettings().getLanguage()
        if not language or language == current_language:
            return self._name    # already loaded for current interface language via countries_ext
        return self.db_cache.get_data(self._load_country_name, (self._id, language))

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