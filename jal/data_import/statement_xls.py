import logging
import re
import pandas
from datetime import datetime, timezone
from zipfile import ZipFile

from jal.db.db import JalDB
from jal.data_import.statement import Statement, FOF, Statement_ImportError
from jal.net.downloader import QuoteDownloader


# -----------------------------------------------------------------------------------------------------------------------
# Base class to load Excel-format statements of russian brokers
class StatementXLS(Statement):
    StatementName = ""
    Header = (0, 0, '')           # Header that is present in broker report  (x-pos, y-pos, header)
    PeriodPattern = (0, 0, r"с (?P<S>.*) - (?P<E>.*)")   # Patter that describes report period
    AccountPattern = (0, 0, '')
    HeaderCol = 0
    SummaryHeader = ''
    asset_section = ''
    asset_columns = {}
    currency_substitutions = {
        "РУБ": "RUB",
        "RUR": "RUB"
    }
    keep_value_headers = []
    currency_values = {}

    def __init__(self):
        super().__init__()
        self._data = {}
        self._statement = None
        self._account_number = ''

    # Loads xls(x) or zipped xls(x) file into pandas dataset
    def load(self, filename: str) -> None:
        self._data = {
            FOF.PERIOD: [None, None],
            FOF.ACCOUNTS: [],
            FOF.ASSETS: [],
            FOF.TRADES: [],
            FOF.TRANSFERS: [],
            FOF.CORP_ACTIONS: [],
            FOF.ASSET_PAYMENTS: [],
            FOF.INCOME_SPENDING: []
        }

        if filename.endswith(".zip"):
            with ZipFile(filename) as zip_file:
                contents = zip_file.namelist()
                if len(contents) != 1:
                    raise Statement_ImportError(self.tr("Archive contains multiple files"))
                with zip_file.open(contents[0]) as r_file:
                    self._statement = pandas.read_excel(io=r_file.read(), header=None, na_filter=False)
        else:
            self._statement = pandas.read_excel(filename, header=None, na_filter=False)

        self._validate()
        self._load_currencies()
        self._load_accounts()
        self._load_assets()
        self._load_deals()
        self._load_cash_transactions()

        logging.info(self.tr("Statement loaded successfully: ") + f"{self.StatementName}")

    # Finds a row with header in column self.HeaderCol starting with 'header' and returns it's index.
    # Return -1 if header isn't found
    def find_row(self, header) -> int:
        for i, row in self._statement.iterrows():
            if re.match(f".*{header}.*", row[self.HeaderCol], re.IGNORECASE) is not None:
                return i
        return -1

    def find_section_start(self, title, columns, subtitle='', header_height=1) -> (int, dict):
        header_found = False
        start_row = -1
        column_indices = dict.fromkeys(columns, -1)  # initialize indexes to -1
        headers = {}
        section_header = ''
        for i, row in self._statement.iterrows():
            if not header_found and re.search(title, str(row[self.HeaderCol])):
                section_header = row[self.HeaderCol]
                header_found = True
            if header_found and ((subtitle == '') or (row[self.HeaderCol] == subtitle)):
                start_row = i + 1  # points to columns header row
                break
        if start_row < 0:
            return start_row, column_indices
        for col in range(self._statement.shape[1]):                 # Load section headers from next row
            for row in range(header_height):
                headers[self._statement[col][start_row+row]] = col  # store column number per header
        for column in columns:
            for header in headers:
                if re.search(columns[column], header):
                    column_indices[column] = headers[header]
        if start_row > 0:
            for idx in column_indices:                         # Verify that all columns were found
                if column_indices[idx] < 0 and idx[0] != '*':  # * - means header is optional
                    logging.error(self.tr("Column not found in section ") + f"{section_header}: {idx}")
                    start_row = -1
        start_row += header_height
        return start_row, column_indices

    # validates that loaded data looks good
    def _validate(self):
        self._check_statement_header()
        self._get_statement_period()
        self._get_account_number()

    def _check_statement_header(self):
        if self._statement[self.Header[0]][self.Header[1]] != self.Header[2]:
            raise Statement_ImportError(
                self.tr("Can't find expected report header: ") + f"'{self.Header[2]}'")

    def _get_statement_period(self):
        parts = re.match(self.PeriodPattern[2],
                         self._statement[self.PeriodPattern[0]][self.PeriodPattern[1]], re.IGNORECASE)
        if parts is None:
            raise Statement_ImportError(self.tr("Can't read report period"))
        statement_dates = parts.groupdict()
        start_day = int(datetime.strptime(statement_dates['S'], "%d.%m.%Y").replace(tzinfo=timezone.utc).timestamp())
        end_day = int(datetime.strptime(statement_dates['E'], "%d.%m.%Y").replace(tzinfo=timezone.utc).timestamp())
        self._data[FOF.PERIOD] = [start_day, self._end_of_date(end_day)]

    def _get_account_number(self):
        if self.AccountPattern[2] is None:
            self._account_number = str(self._statement[self.AccountPattern[0]][self.AccountPattern[1]])
            return

        parts = re.match(self.AccountPattern[2],
                         self._statement[self.AccountPattern[0]][self.AccountPattern[1]], re.IGNORECASE)
        if parts is None:
            self._account_number = self._statement[self.AccountPattern[0]][self.AccountPattern[1]]
        else:
            self._account_number = parts.groupdict()['ACCOUNT']

    def _load_currencies(self):
        amounts = {}
        currency_col = {}
        _header_row = self.find_row(self.SummaryHeader)
        _start_row = self.find_row("входящ")
        _end_row = self.find_row("исходящ")
        if (_header_row == -1) or (_start_row == -1) or (_end_row == -1):
            logging.warning(self.tr("Can't get currencies from summary section of statement"))
            return
        _rate_row = self.find_row("курс")

        column = 5  # there are no currencies before this column
        while column < self._statement.shape[1]:                     # Check every column header
            currency_code = str(self._statement[column][_header_row + 1])[-3:]  # assume it's a currency symbol
            if currency_code:
                amounts[currency_code] = 0
                currency_col[currency_code] = column
            column += 1

        for i, currency in enumerate(amounts):
            for j in range(_start_row, _end_row + 1):
                if j == _rate_row:
                    continue   # Skip currency rate if present as it doesn't change account balance
                try:
                    amount = float(self._statement[currency_col[currency]][j])
                except ValueError:
                    amount = 0
                amounts[currency] += amount

        for currency in amounts:
            if amounts[currency]:
                try:
                    code = self.currency_substitutions[currency]
                except KeyError:
                    code = currency
                self._add_currency(code)

    def _add_currency(self, currency_code):
        match = [x for x in self._data[FOF.ASSETS] if x['symbol'] == currency_code and x['type'] == FOF.ASSET_MONEY]
        if match:
            return
        id = max([0] + [x['id'] for x in self._data[FOF.ASSETS]]) + 1
        currency = {"id": id, "type": "money", "symbol": currency_code}
        self._data[FOF.ASSETS].append(currency)

    def _load_accounts(self):
        currencies = [x for x in self._data[FOF.ASSETS] if x['type'] == FOF.ASSET_MONEY]
        for currency in currencies:
            id = max([0] + [x['id'] for x in self._data[FOF.ACCOUNTS]]) + 1
            account = {"id": id, "number": self._account_number, "currency": currency['id']}
            self._data[FOF.ACCOUNTS].append(account)

    def _load_assets(self):
        cnt = 0
        row, headers = self.find_section_start(self.asset_section, self.asset_columns)
        if row < 0:
            return False
        while row < self._statement.shape[0]:
            if self._statement[self.HeaderCol][row].startswith('Итого') or self._statement[self.HeaderCol][row] == '':
                break
            self._add_asset(self._statement[headers['isin']][row], self._statement[headers['reg_code']][row],
                            self._statement[headers['name']][row])
            cnt += 1
            row += 1
        logging.info(self.tr("Securities loaded: ") + f"{cnt}")

    # Adds assets to self._data[FOF.ASSETS] by ISIN and registration code
    # Asset symbol and other parameters are loaded from MOEX exchange as class targets russian brokers
    # Returns True if asset was added successfully and false otherwise
    def _add_asset(self, isin, reg_code, symbol=''):
        if self._find_asset_id(symbol, isin, reg_code) != 0:
            raise Statement_ImportError(
                self.tr("Attempt to recreate existing asset: ") + f"{isin}/{reg_code}")
        asset_id = JalDB().get_asset_id('', isin=isin, reg_code=reg_code, dialog_new=False)
        if asset_id is None:
            asset = QuoteDownloader.MOEX_info(symbol=symbol, isin=isin, regnumber=reg_code)
            if asset:
                asset['id'] = asset_id = max([0] + [x['id'] for x in self._data[FOF.ASSETS]]) + 1
                asset['exchange'] = "MOEX"
                asset['type'] = FOF.convert_predefined_asset_type(asset['type'])
            else:
                raise Statement_ImportError(self.tr("Can't import asset: ") + f"{isin}/{reg_code}")
        else:
            asset = {"id": -asset_id, "symbol": JalDB().get_asset_name(asset_id),
                     "type": FOF.convert_predefined_asset_type(JalDB().get_asset_type(asset_id)),
                     'name': '', "isin": isin, "reg_code": reg_code}
            asset_id = -asset_id
        self._data[FOF.ASSETS].append(asset)
        return asset_id

    def _find_asset_id(self, symbol='', isin='', reg_code=''):
        if isin:
            try:
                match = [x for x in self._data[FOF.ASSETS] if 'isin' in x and x['isin'] == isin]
            except KeyError:
                match = []
        elif reg_code:
            try:
                match = [x for x in self._data[FOF.ASSETS] if 'reg_code' in x and x['reg_code'] == reg_code]
            except KeyError:
                match = []
        else:   # make match by symbol
            try:
                match = [x for x in self._data[FOF.ASSETS] if 'symbol' in x and x['symbol'] == symbol]
            except KeyError:
                match = []
        if match:
            if len(match) == 1:
                return match[0]['id']
            else:
                logging.error(self.tr("Multiple asset match for ") + f"'{isin}'")
        return 0

    def _find_account_id(self, number, currency):
        try:
            code = self.currency_substitutions[currency]
        except KeyError:
            code = currency
        match = [x for x in self._data[FOF.ASSETS] if
                 'symbol' in x and x['symbol'] == code and x['type'] == FOF.ASSET_MONEY]
        if match:
            if len(match) == 1:
                currency_id = match[0]['id']
            else:
                raise Statement_ImportError(self.tr("Multiple currency found: ") + f"{currency}")
        else:
            currency_id = max([0] + [x['id'] for x in self._data[FOF.ASSETS]]) + 1
            new_currency = {"id": currency_id, "symbol": code, 'name': '', 'type': FOF.ASSET_MONEY}
            self._data[FOF.ASSETS].append(new_currency)
        match = [x for x in self._data[FOF.ACCOUNTS] if
                 'number' in x and x['number'] == number and x['currency'] == currency_id]
        if match:
            if len(match) == 1:
                return match[0]['id']
            else:
                raise Statement_ImportError(self.tr("Multiple accounts found: ") + f"{number}/{currency}")
        new_id = max([0] + [x['id'] for x in self._data[FOF.ACCOUNTS]]) + 1
        new_account = {"id": new_id, "number": number, 'currency': currency_id}
        self._data[FOF.ACCOUNTS].append(new_account)
        return new_id

    def _load_deals(self):
        raise NotImplementedError("load_deals() method is not defined in subclass of StatementXLS")

    def _load_cash_transactions(self):
        raise NotImplementedError("load_cash_transactions() method is not defined in subclass of StatementXLS")
