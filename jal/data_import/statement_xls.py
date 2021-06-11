import logging
import re
import pandas
from datetime import datetime, timezone, time
from zipfile import ZipFile

from jal.widgets.helpers import g_tr
from jal.data_import.statement import Statement, FOF


# -----------------------------------------------------------------------------------------------------------------------
class XLS_ParseError(Exception):
    pass


# -----------------------------------------------------------------------------------------------------------------------
# Base class to load Excel-format statements of russian brokers
class StatementXLS(Statement):
    Header = (0, 0, '')           # Header that is present in broker report  (x-pos, y-pos, header)
    PeriodPattern = (0, 0, r"с (?P<S>.*) - (?P<E>.*)")   # Patter that describes report period
    AccountPattern = (0, 0, '')
    HeaderCol = 0
    SummaryHeader = ''
    trade_columns = {}
    trades_header_height = 1
    trade_sections = []

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
                    raise XLS_ParseError(g_tr('StatementXLS', "Archive contains multiple files"))
                with zip_file.open(contents[0]) as r_file:
                    self._statement = pandas.read_excel(io=r_file.read(), header=None, na_filter=False)
        else:
            self._statement = pandas.read_excel(filename, header=None, na_filter=False)

        self._validate()
        self._load_currencies()
        self._load_accounts()
        self._load_trades()

    # Finds a row with header in column self.HeaderCol starting with 'header' and returns it's index.
    # Return -1 if header isn't found
    def find_row(self, header) -> int:
        for i, row in self._statement.iterrows():
            if re.match(f".*{header}.*", row[self.HeaderCol], re.IGNORECASE) is not None:
                return i
        logging.error(g_tr('StatementXLS', "Row header isn't found in PSB broker statement: ") + header)
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
                    logging.error(g_tr('StatementXLS', "Column not found in section ") + f"{section_header}: {idx}")
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
            raise XLS_ParseError(g_tr('StatementXLS', "Can't find expected report header: ") + f"'{self.Header[2]}'")

    def _get_statement_period(self):
        parts = re.match(self.PeriodPattern[2],
                         self._statement[self.PeriodPattern[0]][self.PeriodPattern[1]], re.IGNORECASE)
        if parts is None:
            raise XLS_ParseError(g_tr('StatementXLS', "Can't read report period"))
        statement_dates = parts.groupdict()
        start_day = datetime.strptime(statement_dates['S'], "%d.%m.%Y")
        self._data[FOF.PERIOD][0] = int(start_day.replace(tzinfo=timezone.utc).timestamp())
        end_day = datetime.combine(datetime.strptime(statement_dates['E'], "%d.%m.%Y"), time(23, 59, 59))
        self._data[FOF.PERIOD][1] = int(end_day.replace(tzinfo=timezone.utc).timestamp())

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
        substitutions = {
            "РУБ": "RUB",
            "RUR": "RUB"
        }

        amounts = {}
        currency_col = {}
        _header_row = self.find_row(self.SummaryHeader)
        _start_row = self.find_row("входящ")
        _end_row = self.find_row("исходящ")
        if (_header_row == -1) or (_start_row == -1) or (_end_row == -1):
            logging.warning(g_tr('StatementXLS', "Can't get currencies from summary section of statement"))
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
                    code = substitutions[currency]
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

    def _load_trades(self):
        for section in self.trade_sections:
            row, headers = self.find_section_start(section[0], self.trade_columns,
                                                   subtitle=section[1], header_height=self.trades_header_height)
            if row < 0:
                continue
