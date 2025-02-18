import logging
from copy import deepcopy
from datetime import date, datetime, timezone
from decimal import Decimal
from PySide6.QtWidgets import QApplication


# ----------------------------------------------------------------------------------------------------------------------
# Basic 3-ndfl templates derived from dcX files
form_3nfl_template = {
    2020: {
        "header": "DLSG            Decl20200102FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF",
        "sections": {
            "@DeclInfo": ('', '', 0, 0, datetime(2021, 1, 29), 0, 5, 0, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, '', 0, '', '', 0),
            "@PersonName": ('', '', '', '', '', 0),
            "@PersonDocument": (0, '', '', datetime(1990, 1, 1), datetime(1977, 1, 1), '', '', 0),
            "@Foreigner": ('', "РОССИЯ", '', 643),
            "@PhoneForeignerHome": ('', ''),
            "@PhoneForeignerWork": ('', ''),
            "@PersonAddress": (0, '', 0, '', '', '', '', '', '', '', '', ''),
            "@HomePhone": ('', ''),
            "@WorkPhone": ('', ''),
            "@DeclInquiry": (0, 0, 0, 0, 0),
            "@DeclForeign": {
                # "@CurrencyIncome000": (13, 1530, "(01)Доходы от реализации ЦБ (обращ-ся на орг. рынке ЦБ)", "IBKR", 840,
                #                        datetime(2020, 1, 30), datetime(2020, 1, 30), 1, 840, 6239.34, 100, 6239.34, 100,
                #                        "Доллар США", 123, 7674.39, 11, 686.33, 201, 321, 0, 0, '', 0)
            },
            "@StandartDeduct": (0, ),
            "@SocialDeduct": (0, ),
            "@ConstructionDeduct": (0, ),
            "@CBDeduct": (0, ),
            "@InvDeduct": (0, )
        }
    },
    2021: {
        "header": "DLSG            Decl20210103FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF",
        "sections": {
            "@DeclInfo": ('', '', 0, 0, datetime(2022, 1, 29), 0, 5, 0, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, '', 0, '', '', 0),
            "@PersonName": ('', '', '', '', '', 0),
            "@PersonDocument": (0, '', '', datetime(1990, 1, 1), datetime(1977, 1, 1), '', '', 0),
            "@Foreigner": ('', "РОССИЯ", '', 643),
            "@PhoneForeignerHome": ('', ''),
            "@PhoneForeignerWork": ('', ''),
            "@PersonAddress": (0, '', 0, '', '', '', '', '', '', '', '', ''),
            "@HomePhone": ('', ''),
            "@WorkPhone": ('', ''),
            "@DeclInquiry": (0, 0, 0, 0, 0, 0),
            "@DeclForeign": {
                # "@CurrencyIncome0000": (0, 1530, "(01)Доходы от реализации ЦБ (обращ-ся на орг. рынке ЦБ)", "IBKR", 324,
                #     840, datetime(2021, 1, 29), datetime(2021, 1, 29), 1, 840, 7618.54, 100, 7618.54, 100, "Доллар США",
                #     123, 9370.8, 11, 838.04, 201, 321, 0, 0, 0, '', 0,)
            },
            "@StandartDeduct": (0, ),
            "@SocialDeduct": (0, ),
            "@ConstructionDeduct": (0, ),
            "@CBDeduct": (0, ),
            "@InvDeduct": (0, )
        }
    },
    2022: {
        "header": "DLSG            Decl20220103FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF",
        "sections": {
            "@DeclInfo": ('', '', 0, 0, datetime(2023, 4, 9), 0, 5, 0, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, '', 0, '', '', 0),
            "@PersonName": ('', '', '', '', '', 0),
            "@PersonDocument": (0, '', '', datetime(1990, 1, 1), datetime(1977, 1, 1), '', '', 0),
            "@Foreigner": ('', "РОССИЯ", '', 643),
            "@PhoneForeignerHome": ('', ''),
            "@PhoneForeignerWork": ('', ''),
            "@PersonAddress": (0, '', 0, '', '', '', '', '', '', '', '', ''),
            "@HomePhone": ('', ''),
            "@WorkPhone": ('', ''),
            "@DeclInquiry": (0, 0, 0, 0, 0, 0),
            "@DeclForeign": {
                # "@CurrencyIncome0000": (0, 1530, "(01)Доходы от реализации ЦБ (обращ-ся на орг. рынке ЦБ)", "IBKR", 324,
                #     840, datetime(2022, 1, 31), datetime(2022, 1, 31), 1, 840, 7618.54, 100, 7618.54, 100, "Доллар США",
                #     123, 9370.8, 11, 838.04, 201, 321, 0, 0, 0, '', 0,)
            },
            "@StandartDeduct": (0, ),
            "@SocialDeduct": (0, ),
            "@ConstructionDeduct": (0, ),
            "@CBDeduct": (0, ),
            "@InvDeduct": (0, )
        }
    },
    2023: {
        "header": "DLSG            Decl20230103FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF",
        "sections": {
            "@DeclInfo": ('', '', 0, 0, datetime(2024, 4, 9), 0, 5, 0, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, '', 0, '', '', 0),
            "@PersonName": ('', '', '', '', '', 0),
            "@PersonDocument": (0, '', '', datetime(1990, 1, 1), datetime(1977, 1, 1), '', '', 0),
            "@Foreigner": ('', "РОССИЯ", '', 643),
            "@PhoneForeignerHome": ('', ''),
            "@PhoneForeignerWork": ('', ''),
            "@PersonAddress": (0, '', 0, '', '', '', '', '', '', '', '', ''),
            "@HomePhone": ('', ''),
            "@WorkPhone": ('', ''),
            "@DeclInquiry": (0, 0, 0, 0, 0, 0),
            "@DeclForeign": {
                # "@CurrencyIncome0000": (0, 1530, "(01)Доходы от реализации ЦБ (обращ-ся на орг. рынке ЦБ)", "IBKR", 324,
                #     840, datetime(2022, 1, 31), datetime(2022, 1, 31), 1, 840, 7618.54, 100, 7618.54, 100, "Доллар США",
                #     123, 9370.8, 11, 838.04, 201, 321, 0, 0, 0, '', 0,)
            },
            "@StandartDeduct": (0, ),
            "@SocialDeduct": (0, ),
            "@ConstructionDeduct": (0, ),
            "@CBDeduct": (0, ),
            "@InvDeduct": (0, )
        }
    },
    2024: {
        "header": "DLSG            Decl20240103FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF",
        "sections": {
            "@DeclInfo": ('', '', 0, 0, datetime(2025, 4, 9), 0, 5, 0, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, '', 0, '', '', 0),
            "@PersonName": ('', '', '', '', '', 0),
            "@PersonDocument": (0, '', '', datetime(1990, 1, 1), datetime(1977, 1, 1), '', '', 0),
            "@Foreigner": ('', "РОССИЯ", '', 643),
            "@PhoneForeignerHome": ('', ''),
            "@PhoneForeignerWork": ('', ''),
            "@PersonAddress": (0, '', 0, '', '', '', '', '', '', '', '', ''),
            "@HomePhone": ('', ''),
            "@WorkPhone": ('', ''),
            "@DeclInquiry": (0, 0, 0, 0, 0, 0),
            "@DeclForeign": {
                # "@CurrencyIncome0000": (0, 1530, "(01)Доходы от реализации ЦБ (обращ-ся на орг. рынке ЦБ)", "IBKR", 324,
                #     840, datetime(2022, 1, 31), datetime(2022, 1, 31), 1, 840, 7618.54, 100, 7618.54, 100, "Доллар США",
                #     123, 9370.8, 11, 838.04, 201, 321, 0, 0, 0, '', 0,)
            },
            "@StandartDeduct": (0, ),
            "@SocialDeduct": (0, ),
            "@ConstructionDeduct": (0, ),
            "@CBDeduct": (0, ),
            "@InvDeduct": (0, ),
            "@DSDeduct": (0, )
        }
    }
}


# ----------------------------------------------------------------------------------------------------------------------
class DLSG:
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
        if year not in form_3nfl_template:
            raise ValueError(self.tr("3-NDFL form isn't supoorted for year: ") + f"{year}")
        self._only_dividends = only_dividends
        self._broker_as_income = broker_as_income
        self._year = year
        self.currency = None
        self.broker_name = ''
        self.broker_iso_country = "000"
        self._tax_form = deepcopy(form_3nfl_template[year])
        self.stored_data = {
            "Дивиденды": {"dividend": self.append_dividend},
            "Акции": {"trade": self.append_stock_trade},
            "Облигации": {"bond_trade": self.append_stock_trade, "bond_interest": self.append_bond_interest},
            "ПФИ": {"trade": self.append_derivative_trade},
            "Проценты": {"interest": self.append_other_income}
        }

        self._records = []
        self._sections = {}
        self._footer_len = 0  # if file ends with _footer_len 0x00 bytes

    def tr(self, text):
        return QApplication.translate("DLSG", text)

    # takes tax_report, generated by TaxesRus.prepare_tax_report(), and puts its data into tax form
    # Parameters contain auxiliary params of report
    def update_taxes(self, tax_report, parameters):
        try:
            self.currency = self.currencies[parameters['currency']]
        except KeyError:
            return logging.error(self.tr("Currency is not supported for 3-NDFL: ") + parameters['currency'])
        self.broker_name = parameters['broker_name']
        self.broker_iso_country = parameters['broker_iso_country']
        for section in tax_report:
            if section in self.stored_data:
                for template in self.stored_data[section]:
                    for item in tax_report[section]:
                        if item['report_template'] == template:
                            self.stored_data[section][template](item)

    # Save tax form in file format of russian tax software "Декларация" with given filename
    def save(self, filename):
        raw_data = self._tax_form['header']
        for section in self._tax_form['sections']:
            raw_data += self.convert_section(section, self._tax_form['sections'][section])
        with open(filename, "w", encoding='cp1251') as taxes:
            taxes.write(raw_data)

    # Converts one section of self._tax_form into text format of dcX-file
    # Returns a line of text with converted data
    def convert_section(self, section_name, section_data):
        data = self.convert_item(section_name)
        if type(section_data) == tuple:
            for item in section_data:
                data += self.convert_item(item)
        elif type(section_data) == dict:
            # Here is a subsection - need to put length and then process elements
            subitems_number = str(len(section_data))
            data += "{:04d}{}".format(len(subitems_number), subitems_number)
            for sub_item in section_data:
                data += self.convert_section(sub_item, section_data[sub_item])
        return data

    # Converts one field of self._tax_form into text format of dcX-file
    # returns converted value
    def convert_item(self, value):
        if type(value) == str:
            prepared_value = value
        elif type(value) == int or type(value) == float or type(value) == Decimal:
            prepared_value = str(value)
        elif type(value) == datetime:
            prepared_value = str((value.date() - date(1899, 12, 30)).days)
        else:
            raise TypeError(f"Unsupported type: {type(value)}")
        data = "{:04d}{}".format(len(prepared_value), prepared_value)
        return data

    def currency_rates_record(self, rate):
        currency_record = (0,  # Auto currency rate
                           self.currency['code'],
                           rate * self.currency['multiplier'],  # Currency rate for income
                           self.currency['multiplier'],  # Currency rate multiplier for income
                           rate * self.currency['multiplier'],  # Currency rate for tax
                           self.currency['multiplier'],  # Currency rate multiplier for tax
                           self.currency['name'])
        return currency_record

    def append_dividend(self, dividend):
        if self._broker_as_income:
            income_source = self.broker_name
            income_iso_country = self.broker_iso_country
            if income_iso_country == '000':
                logging.error(self.tr("Account country is not set for asset, dividend isn't exported into 3-NDFL ") + f"'{income_source}'")
                return
        else:
            income_source = f"Дивиденд от {dividend['symbol']} ({dividend['full_name']})"
            income_iso_country = dividend["country_iso"]
            if income_iso_country == '000':
                logging.error(self.tr("Country is not set for asset, dividend isn't exported into 3-NDFL ") + f"'{income_source}'")
                return
        if self._year == 2020:
            income = (14, '1010', 'Дивиденды', income_source, income_iso_country)
        else:
            income = (0, '1010', 'Дивиденды', income_source, income_iso_country, self.broker_iso_country)
        income += (datetime.fromtimestamp(dividend['payment_date'], tz=timezone.utc),  # Income date
                   datetime.fromtimestamp(dividend['payment_date'], tz=timezone.utc))  # Tax payment date
        income += self.currency_rates_record(dividend['rate'])
        income += (dividend['amount'], dividend['amount_rub'], dividend['tax'], dividend['tax_rub'])
        if self._year == 2020:
            income += ('0', 0, 0, 0, '', 0)
            items_number = len(self._tax_form['sections']['@DeclForeign'])
            next_label = "@CurrencyIncome{:03d}".format(items_number)
        else:
            income += ('0', 0, 0, 0, 0, '', 0)
            items_number = len(self._tax_form['sections']['@DeclForeign'])
            next_label = "@CurrencyIncome{:04d}".format(items_number)
        self._tax_form['sections']['@DeclForeign'][next_label] = income

    def append_stock_trade(self, trade):
        if trade['c_qty'] < 0:  # short position - swap close/open dates/rates
            trade['cs_date'] = trade['os_date']
            trade['cs_rate'] = trade['os_rate']
        if self._broker_as_income:
            income_source = self.broker_name
        else:
            income_source = f"Доход от сделки с {trade['c_symbol']} ({trade['c_isin']})"
        income_iso_country = self.broker_iso_country
        if self._year == 2020:
            income = (13, '1530', '(01)Доходы от реализации ЦБ (обращ-ся на орг. рынке ЦБ)',
                      income_source, income_iso_country)
        else:
            income = (0, '1530', '(01)Доходы от реализации ЦБ (обращ-ся на орг. рынке ЦБ)',
                      income_source, income_iso_country, income_iso_country)
        income += (datetime.fromtimestamp(trade['cs_date'], tz=timezone.utc),  # Income date
                   datetime.fromtimestamp(trade['cs_date'], tz=timezone.utc))  # Tax payment date
        income += self.currency_rates_record(trade['cs_rate'])
        income += (trade['income'], trade['income_rub'], 0, 0, '201', trade['spending_rub'])
        if self._year == 2020:
            income += (0, 0, '', 0)
            items_number = len(self._tax_form['sections']['@DeclForeign'])
            next_label = "@CurrencyIncome{:03d}".format(items_number)
        else:
            income += (0, 0, 0, '', 0)
            items_number = len(self._tax_form['sections']['@DeclForeign'])
            next_label = "@CurrencyIncome{:04d}".format(items_number)
        self._tax_form['sections']['@DeclForeign'][next_label] = income

    def append_bond_interest(self, interest):
        if self._broker_as_income:
            income_source = self.broker_name
        else:
            income_source = f"Купонный доход от {interest['symbol']} ({interest['isin']})"
        income_iso_country = self.broker_iso_country
        if self._year == 2020:
            income = (13, '1530', '(01)Доходы от реализации ЦБ (обращ-ся на орг. рынке ЦБ)',
                      income_source, income_iso_country)
        else:
            income = (0, '1530', '(01)Доходы от реализации ЦБ (обращ-ся на орг. рынке ЦБ)',
                      income_source, income_iso_country, income_iso_country)
        income += (datetime.fromtimestamp(interest['o_date'], tz=timezone.utc),  # Income date
                   datetime.fromtimestamp(interest['o_date'], tz=timezone.utc))  # Tax payment date
        income += self.currency_rates_record(interest['rate'])
        income += (interest['interest'], interest['interest_rub'])
        if self._year == 2020:
            income += (0, 0, '0', 0, 0, 0, '', 0)
            items_number = len(self._tax_form['sections']['@DeclForeign'])
            next_label = "@CurrencyIncome{:03d}".format(items_number)
        else:
            income += (0, 0, '0', 0, 0, 0, 0, '', 0)
            items_number = len(self._tax_form['sections']['@DeclForeign'])
            next_label = "@CurrencyIncome{:04d}".format(items_number)
        self._tax_form['sections']['@DeclForeign'][next_label] = income

    def append_derivative_trade(self, trade):
        if trade['c_qty'] < 0:  # short position - swap close/open dates/rates
            trade['cs_date'] = trade['os_date']
            trade['cs_rate'] = trade['os_rate']
        if self._broker_as_income:
            income_source = self.broker_name
        else:
            income_source = f"Доход от сделки с {trade['c_symbol']}"
        income_iso_country = self.broker_iso_country
        if self._year == 2020:
            income = (13, '1532',
                      '(06)Доходы по оп-циям с ПФИ (обращ-ся на орг. рынке ЦБ), баз. ак. по которым являются ЦБ',
                      income_source, income_iso_country)
        else:
            income = (0, '1532',
                      '(06)Доходы по оп-циям с ПФИ (обращ-ся на орг. рынке ЦБ), баз. ак. по которым являются ЦБ',
                      income_source, income_iso_country, income_iso_country)
        income += (datetime.fromtimestamp(trade['cs_date'], tz=timezone.utc),  # Income date
                   datetime.fromtimestamp(trade['cs_date'], tz=timezone.utc))  # Tax payment date
        income += self.currency_rates_record(trade['cs_rate'])
        income += (trade['income'], trade['income_rub'], 0, 0, '206', trade['spending_rub'])
        if self._year == 2020:
            income += (0, 0, '', 0)
            items_number = len(self._tax_form['sections']['@DeclForeign'])
            next_label = "@CurrencyIncome{:03d}".format(items_number)
        else:
            income += (0, 0, 0, '', 0)
            items_number = len(self._tax_form['sections']['@DeclForeign'])
            next_label = "@CurrencyIncome{:04d}".format(items_number)
        self._tax_form['sections']['@DeclForeign'][next_label] = income

    def append_other_income(self, payment):
        income_source = self.broker_name
        income_iso_country = self.broker_iso_country
        if self._year == 2020:
            income = (13, '4800', 'Иные доходы', income_source, income_iso_country)
        else:
            income = (0, '4800', 'Иные доходы', income_source, income_iso_country, income_iso_country)
        income += (datetime.fromtimestamp(payment['payment_date'], tz=timezone.utc),  # Income date
                   datetime.fromtimestamp(payment['payment_date'], tz=timezone.utc))  # Tax payment date
        income += self.currency_rates_record(payment['rate'])
        income += (payment['amount'], payment['amount_rub'])
        if self._year == 2020:
            income += (0, 0, '0', 0, 0, 0, '', 0)
            items_number = len(self._tax_form['sections']['@DeclForeign'])
            next_label = "@CurrencyIncome{:03d}".format(items_number)
        else:
            income += (0, 0, '0', 0, 0, 0, 0, '', 0)
            items_number = len(self._tax_form['sections']['@DeclForeign'])
            next_label = "@CurrencyIncome{:04d}".format(items_number)
        self._tax_form['sections']['@DeclForeign'][next_label] = income
