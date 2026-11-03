import json
import logging
from decimal import Decimal
from PySide6.QtWidgets import QApplication

from jal.db.settings import JalSettings

REVIEWED_THROUGH = "reviewed_through"
TAX_TREATY = "tax_treaty"


# The tax parameters of one jurisdiction for one year, read from tax_reports/<code>.json. Every key but
# 'reviewed_through' maps the year a value starts to apply to that value; it holds until a later year replaces it.
class TaxParameters:
    DIVIDEND = "dividend"           # kinds of income a base rate is given for
    INTEREST = "interest"
    CAPITAL_GAIN = "capital_gain"

    def __init__(self, code: str, year: int):
        self._year = year
        self._data = {}
        file_path = JalSettings.path(JalSettings.PATH_TAX_REPORT_TEMPLATE) + code + ".json"
        try:
            with open(file_path, 'r', encoding='utf-8') as json_file:
                self._data = json.load(json_file)
        except Exception as e:
            logging.error(self.tr("Can't load tax report parameters from file ") + f"'{file_path}' ({type(e).__name__} {e})")

    @staticmethod
    def tr(text):
        return QApplication.translate("TaxParameters", text)

    # The value of a key for the year: that of the latest year not after it, None before the first one
    def value(self, key: str):
        years = [int(x) for x in self._data.get(key, {}) if int(x) <= self._year]
        return self._data[key][str(max(years))] if years else None

    # The last year the file was checked against the law, 0 if it doesn't say
    def reviewed_through(self) -> int:
        return int(self._data.get(REVIEWED_THROUGH, 0))

    # True if the year is past the one the file was last checked for
    def unreviewed(self) -> bool:
        return self._year > self.reviewed_through()

    # True if the source country (2-letter code) has a tax treaty with the jurisdiction in this year
    def treaty_with(self, country_code: str) -> bool:
        treaties = self.value(TAX_TREATY)
        if treaties is None:
            logging.warning(self.tr("There are no information about tax treaty in tax report parameters"))
            return False
        return country_code in treaties

    # The base tax rate of a kind of income in this year, None if the file gives none
    def rate(self, kind: str):
        rate = self.value("rate_" + kind)
        return None if rate is None else Decimal(rate)
