import logging
import re
import pandas
from datetime import datetime, timezone
from zipfile import ZipFile
from jal.data_import.statement import Statement, FOF, Statement_ImportError


# -----------------------------------------------------------------------------------------------------------------------
# Base class to load Excel-format statements of russian brokers
class StatementXLS(Statement):
    StatementName = ""
    Header = (0, 0, '')           # Header that is present in broker report  (x-pos, y-pos, header)
    PeriodPattern = (0, 0, r"с (?P<S>.*) - (?P<E>.*)")   # Patter that describes report period
    AccountPattern = (0, 0, '')
    HeaderCol = 0
    SummaryHeader = ''
    money_section = ''
    money_columns = {}
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
            FOF.SYMBOLS: [],
            FOF.ASSETS_DATA: [],
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
                with zip_file.open(contents[0]) as report_file:
                    self._statement = pandas.read_excel(report_file, header=None, na_filter=False)
        else:
            self._statement = pandas.read_excel(filename, header=None, na_filter=False)

        self._validate()
        self._load_currencies()
        self._load_accounts()
        self._load_money()
        self._load_assets()
        self._load_deals()
        self._load_asset_transactions()
        self._load_cash_transactions()
        self._strip_unused_data()

        logging.info(self.tr("Statement loaded successfully: ") + f"{self.StatementName}")

    # Finds a row with header in column self.HeaderCol starting with 'header' and returns its index.
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
                headers[str(self._statement[col][start_row+row])] = col  # store column number per header name
        for column in columns:
            for header in headers:
                if re.search(columns[column], header):
                    column_indices[column] = headers[header]
        if start_row > 0:
            for idx in column_indices:                         # Verify that all columns were found
                if column_indices[idx] < 0 and idx[0] != '*':  # * - means header is optional
                    raise Statement_ImportError(self.tr("Column not found in section ") + f"'{section_header}'\nColumn ID: {idx}, Column text: {columns[idx]}\nHeader: {headers}")
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
        parts = re.match(self.PeriodPattern[2], self._statement[self.PeriodPattern[0]][self.PeriodPattern[1]], re.IGNORECASE)
        if parts is None:
            raise Statement_ImportError(self.tr("Can't read report period"))
        statement_dates = parts.groupdict()
        start_day = int(datetime.strptime(statement_dates['S'], "%d.%m.%Y").replace(tzinfo=timezone.utc).timestamp())
        end_day = int(datetime.strptime(statement_dates['E'], "%d.%m.%Y").replace(tzinfo=timezone.utc).timestamp())
        self._data[FOF.PERIOD] = [start_day, self._end_of_date(end_day)]

    def _get_account_number(self):
        if self.AccountPattern[2] is None:
            self._account_number = str(self._statement[self.AccountPattern[0]][self.AccountPattern[1]])
        else:
            parts = re.match(self.AccountPattern[2], str(self._statement[self.AccountPattern[0]][self.AccountPattern[1]]), re.IGNORECASE)
            if parts is None:
                self._account_number = str(self._statement[self.AccountPattern[0]][self.AccountPattern[1]])
            else:
                self._account_number = parts.groupdict()['ACCOUNT']
        if not self._account_number:
            raise Statement_ImportError(self.tr("Empty account number"))

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
                self.currency_id(code)

    def _load_accounts(self):
        currencies = [x for x in self._data[FOF.ASSETS] if x['type'] == FOF.ASSET_MONEY]
        for currency in currencies:
            id = max([0] + [x['id'] for x in self._data[FOF.ACCOUNTS]]) + 1
            account = {"id": id, "number": self._account_number, "currency": currency['id']}
            self._data[FOF.ACCOUNTS].append(account)

    # Find section with start/end amounts of money per account
    def _load_money(self):
        cnt = 0
        row, headers = self.find_section_start(self.money_section, self.money_columns, header_height=2)
        if row < 0:
            return False
        while row < self._statement.shape[0]:
            if self._statement[self.HeaderCol][row].startswith('ИТОГО') or self._statement[self.HeaderCol][row] == '':
                break
            self._update_account_balance(self._statement[headers['name']][row],
                                         self._statement[headers['begin']][row],
                                         self._statement[headers['end']][row],
                                         self._statement[headers['settled_end']][row])
            cnt += 1
            row += 1
        logging.info(self.tr("Cash balances loaded: ") + f"{cnt}")

    # Update account data with cash balance values
    def _update_account_balance(self, currency, begin, end, settled_end):
        account_id = self._find_account_id(self._account_number, currency)
        account = [x for x in self._data[FOF.ACCOUNTS] if x['id'] == account_id][0]
        account["cash_begin"] = begin
        account["cash_end"] = end
        account["cash_end_settled"] = settled_end

    def _load_assets(self):
        cnt = 0
        row, headers = self.find_section_start(self.asset_section, self.asset_columns)
        if row < 0:
            return False
        while row < self._statement.shape[0]:
            if self._statement[self.HeaderCol][row].startswith('Итого') or self._statement[self.HeaderCol][row] == '':
                break
            #if not 'currency' in headers:        # Reports that don't have currency in assets table are defaulted to RUB
            currency_code = self.currency_id('RUB')
            self.asset_id({'isin': self._statement[headers['isin']][row],
                           'symbol': self._statement[headers['name']][row],
                           'reg_number': self._statement[headers['reg_number']][row],
                           'currency': currency_code, 'search_online': "MOEX"})
            cnt += 1
            row += 1
        logging.info(self.tr("Securities loaded: ") + f"{cnt}")

    def _load_deals(self):
        raise NotImplementedError("load_deals() method is not defined in subclass of StatementXLS")

    def _load_asset_transactions(self):
        raise NotImplementedError("load_deals() method is not defined in subclass of StatementXLS")

    def _load_cash_transactions(self):
        raise NotImplementedError("load_cash_transactions() method is not defined in subclass of StatementXLS")

    def _strip_unused_data(self):
        pass
