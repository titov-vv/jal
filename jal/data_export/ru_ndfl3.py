import os
import json
from PySide6.QtWidgets import QApplication
from jal.constants import Setup
from jal.db.settings import JalSettings

# ----------------------------------------------------------------------------------------------------------------------
class Ru_NDFL3:
    currencies = {
        'AUD': {'code': '036', 'name': 'Австралийский доллар', 'multiplier': 100},
        'AZN': {'code': '944', 'name': 'Азербайджанский манат', 'multiplier': 100},
        'GBP': {'code': '826', 'name': 'Фунт стерлингов', 'multiplier': 100},
        'AMD': {'code': '051', 'name': 'Армянский драм', 'multiplier': 10000},
        'BYN': {'code': '933', 'name': 'Белорусский рубль', 'multiplier': 100},
        'BGN': {'code': '975', 'name': 'Болгарский лев', 'multiplier': 100},
        'BRL': {'code': '986', 'name': 'Бразильский реал', 'multiplier': 100},
        'HUF': {'code': '348', 'name': 'Форинт', 'multiplier': 10000},
        'HKD': {'code': '344', 'name': 'Гонконгский доллар', 'multiplier': 1000},
        'DKK': {'code': '208', 'name': 'Датская крона', 'multiplier': 100},
        'USD': {'code': '840', 'name': 'Доллар США', 'multiplier': 100},
        'EUR': {'code': '978', 'name': 'Евро', 'multiplier': 100},
        'INR': {'code': '356', 'name': 'Индийская рупия', 'multiplier': 10000},
        'KZT': {'code': '398', 'name': 'Тенге', 'multiplier': 10000},
        'CAD': {'code': '124', 'name': 'Канадский доллар', 'multiplier': 100},
        'KGS': {'code': '417', 'name': 'Сом', 'multiplier': 10000},
        'CNY': {'code': '156', 'name': 'Юань', 'multiplier': 100},
        'MDL': {'code': '498', 'name': 'Молдавский лей', 'multiplier': 1000},
        'NOK': {'code': '578', 'name': 'Норвежская крона', 'multiplier': 1000},
        'PLN': {'code': '985', 'name': 'Злотый', 'multiplier': 100},
        'RON': {'code': '946', 'name': 'Румынский лей', 'multiplier': 100},
        'RUB': {'code': '648', 'name': 'Российский рубль', 'multiplier': 1},
        'SGD': {'code': '702', 'name': 'Сингапурский доллар', 'multiplier': 100},
        'TJS': {'code': '972', 'name': 'Сомони', 'multiplier': 1000},
        'TRY': {'code': '949', 'name': 'Турецкая лира', 'multiplier': 100},
        'TMT': {'code': '934', 'name': 'Новый туркменский манат', 'multiplier': 100},
        'UZS': {'code': '860', 'name': 'Узбекский сум', 'multiplier': 1000000},
        'UAH': {'code': '980', 'name': 'Гривна', 'multiplier': 1000},
        'CZK': {'code': '203', 'name': 'Чешская крона', 'multiplier': 1000},
        'SEK': {'code': '752', 'name': 'Шведская крона', 'multiplier': 1000},
        'CHF': {'code': '756', 'name': 'Швейцарский франк', 'multiplier': 100},
        'ZAR': {'code': '710', 'name': 'Рэнд', 'multiplier': 1000},
        'KRW': {'code': '410', 'name': 'Вона', 'multiplier': 100000},
        'JPY': {'code': '392', 'name': 'Иена', 'multiplier': 10000}
    }

    def __init__(self, year, broker_as_income=False, only_dividends=False):
        template_path = JalSettings.path(JalSettings.PATH_TEMPLATES) + Setup.NDFL3_TEMPLATE_PATH
        template_file = template_path + os.sep + f"{year}.json"
        try:
            with open(template_file, 'r', encoding='utf-8') as json_template:
                self._tax_form = json.load(json_template)
        except FileNotFoundError:
            raise ValueError(self.tr("3-NDFL template not found for given year: ") + f"{year}")
        self._only_dividends = only_dividends
        self._broker_as_income = broker_as_income
        self._year = year
        self.currency = None
        self.broker_name = ''
        self.broker_iso_country = "000"
        self.stored_data = {
            "Дивиденды": {"dividend": self.append_dividend},
            "Акции": {"trade": self.append_stock_trade},
            "Облигации": {"bond_trade": self.append_stock_trade, "bond_interest": self.append_bond_interest},
            "ПФИ": {"trade": self.append_derivative_trade},
            "Проценты": {"interest": self.append_other_income}
        }

    def tr(self, text):
        return QApplication.translate("NDFL3", text)
