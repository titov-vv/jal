import re
import logging
from datetime import date, datetime
from jal.widgets.helpers import g_tr

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
                logging.error(g_tr('DLSG', "Invalid DeclForeign subsection:") + f" {section_name}")
                raise ValueError
            self.sections[i] = DLSGCurrencyIncome(i, records=records)

        self._tail_records = []
        while (len(records) > 0) and (records[0][:1] != SECTION_PREFIX):
            self._tail_records.append(records.pop(0))

    def add_income(self, code, country_code, description, timestamp, currency, amount, amount_rub, tax, tax_rub, rate,
                   deduction=0.0):
        income = DLSGCurrencyIncome(self.count, code=code)
        income.country_code = country_code
        income.description = description
        income.income_date = (datetime.utcfromtimestamp(timestamp).date() - date(1899, 12, 30)).days
        income.tax_payment_date = income.income_date
        income.currency_code = currency[0]
        income.currency_name = currency[1]
        income.income_units = income.tax_units = currency[2]
        income.income_rate = income.tax_rate = rate * currency[2]
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

    currencies = {
        'USD': ('840', 'Доллар США', 100),
        'EUR': ('978', 'Евро', 100),
        'GBP': ('826', 'Фунт стерлингов', 100),
        'CNY': ('156', 'Юань', 1000),
        'CAD': ('124', 'Канадский доллар', 1),
        'HKD': ('344', 'Гонконгский доллар', 10),
        'INR': ('356', 'Индийская рупия', 10),
        'JPY': ('392', 'Иена', 100),
        'SGD': ('702', 'Сингапурский доллар', 1),
        'CHF': ('756', 'Швейцарский франк', 1),
        'TRY': ('949', 'Турецкая лира', 10),
        'BRL': ('986', 'Бразильский реал', 1)
    }
    codes = {
        'dividend': ('14', '1010', 'Дивиденды', '0'),
        'stock': ('13', '1530', '(01)Доходы от реализации ЦБ (обращ-ся на орг. рынке ЦБ)', '201'),
        'derivative': ('13', '1532', '(06)Доходы по оп-циям с ПФИ (обращ-ся на орг. рынке ЦБ), баз. ак. по которым являются ЦБ', '206')
    }
    countries = {
        'ru': '643',
        'us': '840',
        'ie': '372',
        'ch': '756',
        'fr': '250',
        'ca': '124',
        'se': '752',
        'it': '380',
        'es': '724',
        'au': '036',
        'at': '040',
        'be': '056',
        'gb': '826',
        'de': '276',
        'cn': '156',
        'fi': '246',
        'nl': '528',
        'gr': '300',
        'bm': '060',
        'br': '076',
        'je': '832'
    }

    def __init__(self, only_dividends=False):
        self._only_dividends=only_dividends
        self._year = 0              # year of declaration
        self._records = []
        self._sections = {}
        self._footer_len = 0        # if file ends with _footer_len 0x00 bytes

    def add_dividend(self, country, description, timestamp, currency_name, amount, amount_rub, tax, tax_rub, rate):
        foreign_section = self.get_section('DeclForeign')
        if foreign_section is None:
            return
        try:
            country_code, currency_code = self.get_country_currency(country, currency_name)
        except ValueError:
            logging.warning(g_tr('DLSG', "Dividend wasn't written to russian tax form"))
            return
        source = "Дивиденд от " + description
        foreign_section.add_income(self.codes['dividend'], country_code, source, timestamp,
                                   currency_code, amount, amount_rub, tax, tax_rub, rate)

    def add_stock_profit(self, country, source, timestamp, currency_name, amount, income_rub, spending_rub, rate):
        if self._only_dividends:
            return
        foreign_section = self.get_section('DeclForeign')
        if foreign_section is None:
            return
        try:
            country_code, currency_code = self.get_country_currency(country, currency_name)
        except ValueError:
            logging.warning(g_tr('DLSG', "Operation with stock wasn't written to russian tax form"))
            return
        foreign_section.add_income(self.codes['stock'], country_code, source, timestamp,
                                   currency_code, amount, income_rub, 0.0, 0.0, rate, deduction=spending_rub)

    def add_derivative_profit(self, country, source, timestamp, currency_name, amount, income_rub, spending_rub, rate):
        if self._only_dividends:
            return
        foreign_section = self.get_section('DeclForeign')
        if foreign_section is None:
            return
        try:
            country_code, currency_code = self.get_country_currency(country, currency_name)
        except ValueError:
            logging.warning(g_tr('DLSG', "Operation with derivative wasn't written to russian tax form"))
            return
        foreign_section.add_income(self.codes['derivative'], country_code, source, timestamp,
                                   currency_code, amount, income_rub, 0.0, 0.0, rate, deduction=spending_rub)

    def get_country_currency(self, country, currency_name):
        try:
            currency_code = self.currencies[currency_name]
        except:
            logging.error(g_tr('DLSG', "Currency code isn't known for russian tax form:") + f" {currency_name}")
            raise ValueError
        try:
            country_code = self.countries[country]
        except:
            logging.error(g_tr('DLSG', "Country code isn't known for russian tax form (check account settings):") +
                          f" {country}")
            raise ValueError
        return country_code, currency_code

    def get_section(self, name):
        for section in self._sections:
            if self._sections[section].tag == name:
                return self._sections[section]
        logging.error(g_tr('DLSG', "Declaration file has no 'DeclForeign' section."))
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
            logging.error(g_tr('DLSG', "Unexpected declaration file header:") + f" {self.header}")
            raise ValueError
        self._year = int(parts.group(1))
        logging.info(g_tr('DLSG', "Declaration file is for year:") + f" {self._year}")

        self.split_records(raw_data[HEADER_LENGTH:])
        self.split_sections()

    # this method gets declaration data without header and splits it into a set of separate list of self._records
    def split_records(self, data):
        pos = 0

        while (pos < len(data)):
            length_field = data[pos : pos + SIZE_LENGTH]

            if length_field == (FOOTER * len(length_field)):
                self._footer_len = len(length_field)
                break

            try:
                length = int(length_field)
            except Exception as e:
                logging.error(g_tr('DLSG', "Invalid record size at position")
                              + f" {pos+HEADER_LENGTH}: '{length_field}'")
                raise ValueError
            pos += SIZE_LENGTH
            self._records.append(data[pos: pos + length])
            pos = pos + length

        logging.debug(g_tr('DLSG', "Declaration file content:") + f" {self._records}")

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

        logging.debug(g_tr('DLSG', "Sections loaded:") + f" {i}")
        for j in range(i):
            logging.debug(g_tr('DLSG', "Section ") + f" '{self._sections[j].tag}' "
                          + g_tr('DLSG', "loaded as ") + str(type(self._sections[j])))

    def write_file(self, filename):
        logging.info(g_tr('DLSG', "Writing file:") + f" {filename}")

        self._records = []

        for section in self._sections:
            self._sections[section].write(self._records)
        logging.debug(g_tr('DLSG', "Declaration to write:") + f" {self._records}")

        raw_data = self.header.format(self._year)
        for record in self._records:
            raw_data += "{:04d}{}".format(len(record), record)

        with open(filename, "w", encoding='cp1251') as taxes:
            taxes.write(raw_data)
