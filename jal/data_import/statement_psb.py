import logging
import re
from datetime import datetime, timezone, time
import pandas

from jal.widgets.helpers import g_tr
from jal.db.update import JalDB


# -----------------------------------------------------------------------------------------------------------------------
class PSB_Broker:
    Header = 'Брокер: ПАО "Промсвязьбанк"'
    AccountPattern = r"(?P<ACCOUNT>\S*)( от \d\d\.\d\d\.\d\d\d\d)?"
    PeriodPattern = r"с (?P<S>\d\d\.\d\d\.\d\d\d\d) по (?P<E>\d\d\.\d\d\.\d\d\d\d)"
    SummaryHeader = "Сводная информация по счетам клиента в валюте счета"
    StartingBalanceHeader = "ВХОДЯЩАЯ СУММА СРЕДСТВ НА СЧЕТЕ"
    EndingBalanceHeader = "ОСТАТОК СРЕДСТВ НА СЧЕТЕ"
    RateHeader = "Курс валют ЦБ РФ"
    SettledCashHeader = "ПЛАНОВЫЙ ИСХОДЯЩИЙ ОСТАТОК СРЕДСТВ НА СЧЕТЕ"

    def __init__(self, parent, filename):
        self._parent = parent
        self._filename = filename
        self._statement = None
        self._currencies = []
        self._accounts = {}
        self._settled_cash = {}
        self._report_start = 0
        self._report_end = 0

    def load(self):
        self._statement = pandas.read_excel(self._filename, header=None, na_filter=False)
        if not self.validate():
            return False
        self.load_cash_balance()
        logging.info(g_tr('PSB', "PSB broker statement loaded successfully"))
        for account in self._settled_cash:
            logging.info(g_tr('PSB', 'Planned cash: ') + f"{self._settled_cash[account]:.2f} " +
                         f"{JalDB().get_asset_name(JalDB().get_account_currency(account))}")
        return True

    def validate(self):
        if self._statement[2][3] != self.Header:
            logging.error(g_tr('PSB', "Can't find PSB broker report header"))
            return False
        parts = re.match(self.AccountPattern, self._statement[3][9], re.IGNORECASE)
        if parts is None:  # Old reports has only account number in field, newer reports has number and date
            account_name = self._statement[3][9]
        else:
            account_name = parts.groupdict()['ACCOUNT']
        parts = re.match(self.PeriodPattern, self._statement[3][6], re.IGNORECASE)
        if parts is None:
            logging.error(g_tr('PSB', "Can't parse PSB broker statement period"))
            return False
        statement_dates = parts.groupdict()
        self._report_start = int(datetime.strptime(statement_dates['S'],
                                                   "%d.%m.%Y").replace(tzinfo=timezone.utc).timestamp())
        end_day = datetime.strptime(statement_dates['E'], "%d.%m.%Y")
        self._report_end = int(datetime.combine(end_day, time(23, 59, 59)).replace(tzinfo=timezone.utc).timestamp())
        if not self._parent.checkStatementPeriod(account_name, self._report_start):
            return False
        if not self.get_currencies():
            return False
        logging.info(g_tr('PSB', "Loading PSB broker statement for account ") +
                     f"{account_name}: {statement_dates['S']} - {statement_dates['E']}")
        logging.info(g_tr('PSB', "Account currencies: ") + f"{self._currencies}")
        for currency in self._currencies:
            self._accounts[currency] = JalDB().get_account_id(account_name, currency)
            if self._accounts[currency] is None:
                return False
        return True

    # Finds a row with header and returns it's index.
    # Return -1 if header isn't found
    def find_row(self, header) -> int:
        for i, row in self._statement.iterrows():
            if row[1].startswith(header):
                return i
        logging.error(g_tr('PSB', "Header isn't found in PSB broker statement:") + header)
        return -1

    def get_currencies(self):
        amounts = {}
        summary_header = self.find_row(self.SummaryHeader)
        summary_start = self.find_row(self.StartingBalanceHeader)
        summary_end = self.find_row(self.EndingBalanceHeader)
        if (summary_header == -1) or (summary_start == -1) or (summary_end == -1):
            return False
        column = 5  # Start column of different currencies
        while column < self._statement.shape[1]:  # get currency names from each column
            if self._statement[column][summary_header + 1]:
                amounts[self._statement[column][summary_header + 1]] = 0
            column += 1
        for i, currency in enumerate(amounts):
            for j in range(summary_start, summary_end+1):
                if self._statement[1][j] == self.RateHeader:  # Skip currency rate if present as it doesn't change account balance
                    continue
                try:
                    amount = float(self._statement[5 + i][j])
                except ValueError:
                    amount = 0
                amounts[currency] += amount
        for currency in amounts:
            if amounts[currency]:
                self._currencies.append(currency)
        return True

    def load_cash_balance(self):
        summary_header = self.find_row(self.SummaryHeader)
        cash_row = self.find_row(self.SettledCashHeader)
        if (summary_header == -1) or (cash_row == -1):
            return
        column = 5  # Start column of different currencies
        while column < self._statement.shape[1]:  # get currency names from each column
            currency = self._statement[column][summary_header + 1]
            if currency in self._currencies:
                self._settled_cash[self._accounts[currency]] = self._statement[column][cash_row]
            column += 1
