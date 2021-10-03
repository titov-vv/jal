import re
import logging
from datetime import date, datetime
from PySide6.QtWidgets import QApplication

# standard header is "DLSG            DeclYYYY0102FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF", where YYYY is year of declaration
HEADER_LENGTH = 60
SIZE_LENGTH = 4
FOOTER = '\0'
SECTION_PREFIX = '@'


class DLSGrecord:
    def __init__(self):
        self.name = ''

class DLSGsection:
    def __init__(self, tag, records):
        self.tag = tag
        self._records = []
        while (len(records) > 0) and (records[0][:1] != SECTION_PREFIX):
            self._records.append(records.pop(0))

    def write(self, records):
        records.append(SECTION_PREFIX + self.tag)
        records.extend(self._records)


class DLSGCurrencyIncome:
    tag = 'CurrencyIncome'

    def __init__(self, id, records=None, code=None):
        if code is not None:
            self.id = id
            self.type = code[0]
            self.income_code = code[1]
            self.income_description = code[2]
            self.description = ''
            self.country_code = ''
            self.income_date = 0
            self.tax_payment_date = 0
            self.auto_currency_rate = '0'  # '0' = no auto currency rates
            self.currency_code = ''
            self.income_rate = 0.0
            self.income_units = 0
            self.tax_rate = 0.0
            self.tax_units = 0
            self.currency_name = ''
            self.income_currency = 0.0
            self.income_rub = 0.0
            self.tax_currency = 0.0
            self.tax_rub = 0.0
            self.deduction_code = code[3]
            self.deduction = 0.0
            self._kik_records = ['0', '0', '', '0']
        elif records is not None:
            self.id = id
            self.type = records.pop(0)
            self.income_code = records.pop(0)
            self.income_description = records.pop(0)
            self.description = records.pop(0)
            self.country_code = records.pop(0)
            self.income_date = int(records.pop(0))
            self.tax_payment_date = int(records.pop(0))
            self.auto_currency_rate = records.pop(0)   # '0' = no auto currency rates
            self.currency_code = records.pop(0)
            self.income_rate = float(records.pop(0))
            self.income_units = int(records.pop(0))
            self.tax_rate = float(records.pop(0))
            self.tax_units = int(records.pop(0))
            self.currency_name = records.pop(0)
            self.income_currency = float(records.pop(0))
            self.income_rub = float(records.pop(0))
            self.tax_currency = float(records.pop(0))
            self.tax_rub = float(records.pop(0))
            self.deduction_code = records.pop(0)
            self.deduction = float(records.pop(0))
            self._kik_records = records[:4]
            [records.pop(0) for _ in range(4)]
        else:
            raise ValueError

    def write(self, records):
        records.append(SECTION_PREFIX + self.tag + f"{self.id:03d}")
        records.append(self.type)
        records.append(self.income_code)
        records.append(self.income_description)
        records.append(self.description)
        records.append(self.country_code)
        records.append(str(self.income_date))
        records.append(str(self.tax_payment_date))
        records.append(self.auto_currency_rate)
        records.append(self.currency_code)
        records.append(f"{self.income_rate:.2f}")
        records.append(str(self.income_units))
        records.append(f"{self.tax_rate:.2f}")
        records.append(str(self.tax_units))
        records.append(self.currency_name)
        records.append(str(self.income_currency))
        records.append(str(self.income_rub))
        records.append(str(self.tax_currency))
        records.append(str(self.tax_rub))
        records.append(self.deduction_code)
        records.append(str(self.deduction))
        records.extend(self._kik_records)


class DLSGDeclForeign(DLSGsection):
    tag = 'DeclForeign'

    def __init__(self, records):
        self.count = int(records.pop(0))
        self.sections = {}

        for i in range(self.count):
            section_name = records.pop(0)

            if section_name != SECTION_PREFIX + DLSGCurrencyIncome.tag + f"{i:03d}":
                logging.error(self.tr("Invalid DeclForeign subsection:") + f" {section_name}")
                raise ValueError
            self.sections[i] = DLSGCurrencyIncome(i, records=records)

        self._tail_records = []
        while (len(records) > 0) and (records[0][:1] != SECTION_PREFIX):
            self._tail_records.append(records.pop(0))

    def tr(self, text):
        return QApplication.translate("DLSG", text)

    def add_income(self, code, country_code, description, timestamp, currency, amount, amount_rub, tax, tax_rub, rate,
                   deduction=0.0):
        income = DLSGCurrencyIncome(self.count, code=code)
        income.country_code = country_code
        income.description = description
        income.income_date = (datetime.utcfromtimestamp(timestamp).date() - date(1899, 12, 30)).days
        income.tax_payment_date = income.income_date
        income.currency_code = currency['code']
        income.currency_name = currency['name']
        income.income_units = income.tax_units = currency['multiplier']
        income.income_rate = income.tax_rate = rate * currency['multiplier']
        income.income_currency = amount
        income.income_rub = amount_rub
        income.tax_currency = tax
        income.tax_rub = tax_rub
        if deduction == 0.0:
            income.deduction_code = '0'
        income.deduction = deduction
        self.sections[self.count] = income
        self.count += 1

    def write(self, records):
        records.append(SECTION_PREFIX + self.tag)
        records.append(str(self.count))
        for section in self.sections:
            self.sections[section].write(records)
        records.extend(self._tail_records)


class DLSG:
    header_pattern = "DLSG            Decl(\d{4})0102FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"
    header = "DLSG            Decl{:04d}0102FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"
    DIVIDEND_INCOME = 'dividend'
    STOCK_INCOME = 'stock'
    DERIVATIVE_INCOME = 'derivative'

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

    def __init__(self, only_dividends=False):
        self._only_dividends=only_dividends
        self._year = 0              # year of declaration
        self._records = []
        self._sections = {}
        self._footer_len = 0        # if file ends with _footer_len 0x00 bytes

        self.codes = {
            self.DIVIDEND_INCOME: ('14', '1010', 'Дивиденды', '0'),
            self.STOCK_INCOME: ('13', '1530', '(01)Доходы от реализации ЦБ (обращ-ся на орг. рынке ЦБ)', '201'),
            self.DERIVATIVE_INCOME: ('13', '1532', '(06)Доходы по оп-циям с ПФИ (обращ-ся на орг. рынке ЦБ), баз. ак. по которым являются ЦБ', '206')
        }

    def tr(self, text):
        return QApplication.translate("DLSG", text)

    # Create an income record of given 'type' in tax declaration
    # timestamp - date of income, country_code - 3-digit ISO country code, currency - 3-letter ISO currency code
    # rate - currency rate for given date, note - description of the income, amount and tax are currency and rubles
    def add_foreign_income(self, type, timestamp, country_code, currency,
                           rate, amount, amount_rub, tax, tax_rub, note, spending_rub=0.0):
        if type != DLSG.DIVIDEND_INCOME and self._only_dividends:
            return
        foreign_section = self.get_section('DeclForeign')
        if foreign_section is None:
            return
        try:
            tax_codes = self.codes[type]
        except KeyError:
            raise(self.tr("Unknown income type for russian tax form: ") + type)
        try:
            currency_data = self.currencies[currency]
        except KeyError:
            logging.error(self.tr("Currency isn't supported for russian tax form: ") + currency)
            return
        foreign_section.add_income(tax_codes, country_code, note, timestamp,
                                   currency_data, amount, amount_rub, tax, tax_rub, rate, deduction=spending_rub)

    def get_section(self, name):
        for section in self._sections:
            if self._sections[section].tag == name:
                return self._sections[section]
        logging.error(self.tr("Declaration file has no 'DeclForeign' section."))
        return None

    # Method reads declaration form a file with given filename
    # Header of file is being validated
    def read_file(self, filename):
        logging.info(f"Loading file: {filename}")

        with open(filename, "r", encoding='cp1251') as taxes:
            raw_data = taxes.read()

        self.header = raw_data[:HEADER_LENGTH]

        parts = re.match(self.header_pattern, self.header)
        if not parts:
            logging.error(self.tr("Unexpected declaration file header:") + f" {self.header}")
            raise ValueError
        self._year = int(parts.group(1))
        logging.info(self.tr("Declaration file is for year:") + f" {self._year}")

        self.split_records(raw_data[HEADER_LENGTH:])
        self.split_sections()

    # this method gets declaration data without header and splits it into a set of separate list of self._records
    def split_records(self, data):
        pos = 0

        while pos < len(data):
            length_field = data[pos : pos + SIZE_LENGTH]

            if length_field == (FOOTER * len(length_field)):
                self._footer_len = len(length_field)
                break

            try:
                length = int(length_field)
            except Exception as e:
                logging.error(self.tr("Invalid record size at position")
                              + f" {pos+HEADER_LENGTH}: '{length_field}'")
                raise ValueError
            pos += SIZE_LENGTH
            self._records.append(data[pos: pos + length])
            pos = pos + length

        logging.debug(self.tr("Declaration file content:") + f" {self._records}")

    def split_sections(self):
        i = 0
        while len(self._records) > 0:
            section_name = self._records.pop(0)
            if section_name[0] != SECTION_PREFIX:
                logging.error(f"Invalid section prefix: {section_name}")
                raise ValueError
            section_name = section_name[1:]
            if section_name == DLSGDeclForeign.tag:
                section = DLSGDeclForeign(self._records)
            else:
                section = DLSGsection(section_name, self._records)

            self._sections[i] = section
            i += 1

        logging.debug(self.tr("Sections loaded:") + f" {i}")
        for j in range(i):
            logging.debug(self.tr("Section ") + f" '{self._sections[j].tag}' "
                          + self.tr("loaded as ") + str(type(self._sections[j])))

    def write_file(self, filename):
        logging.info(self.tr("Writing file:") + f" {filename}")

        self._records = []

        for section in self._sections:
            self._sections[section].write(self._records)
        logging.debug(self.tr("Declaration to write:") + f" {self._records}")

        raw_data = self.header.format(self._year)
        for record in self._records:
            raw_data += "{:04d}{}".format(len(record), record)

        with open(filename, "w", encoding='cp1251') as taxes:
            taxes.write(raw_data)
