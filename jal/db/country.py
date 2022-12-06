from jal.db.db import JalDB


class JalCountry(JalDB):
    def __init__(self, id: int = 0, data: dict = None, search=False) -> None:
        super().__init__()
        self._id = id
        if self._valid_data(data):
            if search:
                self._id = self._find_country(data)
        self._data = self.readSQL("SELECT name, code, iso_code, tax_treaty FROM countries WHERE id=:country_id",
                                  [(":country_id", self._id)], named=True)
        self._name = self._data['name'] if self._data is not None else None
        self._code = self._data['code'] if self._data is not None else None
        self._iso_code = self._data['iso_code'] if self._data is not None else None
        self._tax_treaty = self._data['tax_treaty'] == 1 if self._data is not None else False

    def id(self) -> int:
        return self._id

    def name(self) -> str:
        return self._name

    def code(self) -> str:
        return self._code

    def iso_code(self) -> str:
        return self._iso_code

    # Returns True/False status of Tax Treaty for this country
    def has_tax_treaty(self) -> bool:
        return self._tax_treaty

    def _valid_data(self, data: dict) -> bool:
        if data is None:
            return False
        if 'code' not in data:
            return False
        return True

    def _find_country(self, data: dict) -> int:
        country_id = self.readSQL("SELECT id FROM countries WHERE code=:code",
                                  [(":code", data['code'])], check_unique=True)
        if country_id is None:
            return 0
        else:
            return country_id