import logging
import re
from datetime import datetime, timezone, time
import pandas

from jal.widgets.helpers import g_tr
from jal.db.update import JalDB
from jal.constants import Setup, DividendSubtype


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
        self.load_securities()
        self.load_cash_transactions()
        self.load_deals()
        self.load_coupons()
        self.load_dividends()
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

    def find_section_start(self, header_pattern, columns) -> (int, dict):
        start_row = -1
        headers = {}
        section_header = ''
        for i, row in self._statement.iterrows():
            if re.search(header_pattern, row[1]):
                section_header = row[1]
                start_row = i + 1  # points to columns header row
                break
        if start_row > 0:
            for col in range(self._statement.shape[1]):          # Load section headers from next row
                headers[self._statement[col][start_row]] = col   # store column number per header
        column_indices = dict.fromkeys(columns, -1)   # initialize indexes to -1
        for column in columns:
            for header in headers:
                if re.search(columns[column], header):
                    column_indices[column] = headers[header]
        if start_row > 0:
            for idx in column_indices:                         # Verify that all columns were found
                if column_indices[idx] < 0 and idx[0] != '*':  # * - means header is optional
                    logging.error(g_tr('PSB', "Column not found in section ") + f"{section_header}: {idx}")
                    start_row = -1
            start_row += 1
        return start_row, column_indices

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
            logging.error(g_tr('PSB', "Can't load cash balances"))
            return
        column = 5  # Start column of different currencies
        while column < self._statement.shape[1]:  # get currency names from each column
            currency = self._statement[column][summary_header + 1]
            if currency in self._currencies:
                self._settled_cash[self._accounts[currency]] = self._statement[column][cash_row]
            column += 1

    def load_securities(self):
        cnt = 0
        loaded = 0
        columns = {
            "name": r"Наименование эмитента, вид, категория \(тип\), выпуск, транш ЦБ",
            "isin": "ISIN",
            "reg_code": r"Номер гос\.регистрации"
        }

        row, headers = self.find_section_start(r"^Портфель на конец дня.*", columns)
        if row < 0:
            return False

        while row < self._statement.shape[0]:
            if self._statement[1][row].startswith('Итого') or self._statement[1][row] == '':
                break
            asset_id = JalDB().get_asset_id('', isin=self._statement[headers['isin']][row],
                                            reg_code=self._statement[headers['reg_code']][row], get_online=True)
            if asset_id is not None:
                loaded += 1
            cnt += 1
            row += 1
        logging.info(g_tr('PSB', "Securities loaded: ") + f"{loaded} ({cnt})")

    def load_cash_transactions(self):
        cnt = 0
        columns = {
            "date": "Дата",
            "currency": "Валюта счета",
            "amount": "Сумма",
            "operation": "Операция",
            "note": "Комментарий"
        }

        row, headers = self.find_section_start("Внешнее движение денежных средств в валюте счета", columns)
        if row < 0:
            return False
        while row < self._statement.shape[0]:
            if self._statement[1][row] == '':
                break
            if self._statement[headers['note']][row].startswith("Дивиденды") or \
                    self._statement[headers['note']][row].startswith("Погашение купона"):
                row += 1
                continue
            if self._statement[headers['note']][row] != '':
                logging.warning(g_tr('PSB', "Unknown cash transaction: ") + self._statement[headers['note']][row])
                row += 1
                continue

            timestamp = int(datetime.strptime(self._statement[headers['date']][row],
                                              "%d.%m.%Y").replace(tzinfo=timezone.utc).timestamp())
            amount = self._statement[headers['amount']][row]
            account_id = self._accounts[self._statement[headers['currency']][row]]
            if self._statement[headers['operation']][row] == 'Зачислено на счет':
                self.transfer_in(timestamp, account_id, amount)
            elif self._statement[headers['operation']][row] == 'Списано со счета':
                self.transfer_out(timestamp, account_id, amount)
            else:
                logging.warning(g_tr('PSB', "Unknown cash operation: ") + self._statement[headers['operation']][row])
                row += 1
                continue
            cnt += 1
            row += 1
        logging.info(g_tr('PSB', "Cash transactions loaded: ") + f"{cnt}")

    def load_deals(self):
        cnt = 0
        sections = [
            r"Сделки, .* с ЦБ на биржевых торговых .* с расчетами в дату заключения",
            r"Сделки, .* с ЦБ на биржевых торговых .* с расчетами Т\+, незавершенные в отчетном периоде",
            r"Сделки, .* с ЦБ на биржевых торговых .* с расчетами Т\+, рассчитанные в отчетном периоде"
        ]
        columns = {
            "timestamp": "Дата и время совершения сделки",
            "*settlement": "Фактическая дата исполнения сделки",
            "number": "Номер сделки в ТС",
            "isin": "ISIN",
            "reg_code": r"Номер гос\. регистрации",
            "B/S": r"Вид сделки \(покупка\/продажа\)",
            "qty": r"Кол-во ЦБ, шт\.",
            "currency": r"Валюта сделки \/ Валюта платежа",
            "price": r"Цена \(% для обл\)",
            "amount": "Сумма сделки без НКД",
            "accrued_int": "НКД",
            "fee1": r"Комиссия торговой системы( \(без НДС\))?, руб",
            "fee2": r"Клиринговая комиссия( \(без НДС\))?, руб",
            "fee3": r"Комиссия за ИТС( \(в т.ч. НДС\))?, руб",
            "fee_broker": r"Ком\. брокера"
        }
        for section in sections:
            row, headers = self.find_section_start(section, columns)
            if row < 0:
                continue
            while row < self._statement.shape[0]:
                if self._statement[1][row].startswith('Итого') or self._statement[1][row] == '':
                    break
                deal_number = self._statement[headers['number']][row]
                asset_id = JalDB().get_asset_id('', isin=self._statement[headers['isin']][row],
                                                reg_code=self._statement[headers['reg_code']][row])
                if self._statement[headers['B/S']][row] == 'покупка':
                    qty = self._statement[headers['qty']][row]
                    bond_interest = -self._statement[headers['accrued_int']][row]
                elif self._statement[headers['B/S']][row] == 'продажа':
                    qty = -self._statement[headers['qty']][row]
                    bond_interest = self._statement[headers['accrued_int']][row]
                else:
                    row += 1
                    logging.warning(g_tr('PSB', "Unknown trade type: ") + self._statement[headers['B/S']][row])
                    continue
                price = self._statement[headers['price']][row]
                currencies = [x.strip() for x in self._statement[headers['currency']][row].split('/')]
                if currencies[0] != currencies [1]:
                    row += 1
                    logging.warning(g_tr('PSB', "Unsupported trade with different currencies: ") + currencies)
                    continue
                currency = currencies[0]
                fee = self._statement[headers['fee1']][row] + self._statement[headers['fee2']][row] + \
                      self._statement[headers['fee3']][row] + self._statement[headers['fee_broker']][row]
                amount = self._statement[headers['amount']][row]
                if abs(abs(price * qty) - amount) >= Setup.DISP_TOLERANCE:
                    price = abs(amount / qty)
                timestamp = int(datetime.strptime(self._statement[headers['timestamp']][row],
                                                  "%d.%m.%Y %H:%M:%S").replace(tzinfo=timezone.utc).timestamp())
                if headers['*settlement'] == -1:
                    settlement = int(
                        datetime.strptime(self._statement[headers['timestamp']][row], "%d.%m.%Y %H:%M:%S").replace(
                            tzinfo=timezone.utc).replace(hour=0, minute=0, second=0).timestamp())
                else:
                    settlement = int(datetime.strptime(self._statement[headers['*settlement']][row],
                                                       "%d.%m.%Y").replace(tzinfo=timezone.utc).timestamp())
                JalDB().add_trade(self._accounts[currency], asset_id, timestamp, settlement, deal_number, qty, price,
                                  -fee)
                if bond_interest != 0:
                    JalDB().add_dividend(DividendSubtype.BondInterest, timestamp, self._accounts[currency], asset_id,
                                         bond_interest, "НКД", deal_number)

                cnt += 1
                row += 1
        logging.info(g_tr('PSB', "Trades loaded: ") + f"{cnt}")

    def load_coupons(self):
        cnt = 0
        columns = {
            "date": "Дата операции",
            "operation": "Вид операции",
            "asset_name": r"Наименование эмитента, вид, категория \(тип\), выпуск, транш ЦБ",
            "isin": "ISIN",
            "reg_code": "Регистрационный номер ЦБ",
            "currency": "Валюта Выплаты",
            "coupon": "НКД",
            "tax": r"Сумма удержанного налога, руб.*"
        }

        row, headers = self.find_section_start("Погашение купонов и ЦБ", columns)
        if row < 0:
            return False
        while row < self._statement.shape[0]:
            if self._statement[2][row] == '':  # Row may contain comment in cell [1]
                break
            if self._statement[headers['operation']][row] != 'Погашение купона':
                logging.warning(g_tr('PSB', "Unsupported payment: ") + self._statement[headers['operation']][row])
                row += 1
                continue
            timestamp = int(datetime.strptime(self._statement[headers['date']][row],
                                              "%d.%m.%Y").replace(tzinfo=timezone.utc).timestamp())
            amount = float(self._statement[headers['coupon']][row])
            tax = float(self._statement[headers['tax']][row])
            account_id = self._accounts[self._statement[headers['currency']][row]]
            asset_id = JalDB().get_asset_id('', isin=self._statement[headers['isin']][row],
                                            reg_code=self._statement[headers['reg_code']][row])
            note = self._statement[headers['operation']][row] + " " + self._statement[headers['asset_name']][row]
            if asset_id is None:
                logging.error(g_tr('PSB', "Can't find asset for coupon ") +
                              f"{self._statement[headers['isin']][row]}/{self._statement[headers['reg_code']][row]}")
                continue
            JalDB().add_dividend(DividendSubtype.BondInterest, timestamp, account_id, asset_id, amount, note, tax=tax)
            cnt += 1
            row += 1
        logging.info(g_tr('PSB', "Bond interests loaded: ") + f"{cnt}")

    def load_dividends(self):
        cnt = 0
        columns = {
            "date": "Дата операции",
            "isin": "ISIN",
            "reg_code": r"Номер гос\. регистрации",
            "currency": "Валюта Выплаты",
            "amount": "Сумма дивидендов",
            "tax": "Сумма удержанного налога"
        }

        row, headers = self.find_section_start("Выплата дивидендов", columns)
        if row < 0:
            return False
        while row < self._statement.shape[0]:
            if self._statement[1][row] == '':
                break

            timestamp = int(datetime.strptime(self._statement[headers['date']][row],
                                              "%d.%m.%Y").replace(tzinfo=timezone.utc).timestamp())
            amount = float(self._statement[headers['amount']][row])
            tax = float(self._statement[headers['tax']][row])
            account_id = self._accounts[self._statement[headers['currency']][row]]
            asset_id = JalDB().get_asset_id('', isin=self._statement[headers['isin']][row],
                                            reg_code=self._statement[headers['reg_code']][row])
            if asset_id is None:
                logging.error(g_tr('PSB', "Can't find asset for dividend ") +
                              f"{self._statement[headers['isin']][row]}/{self._statement[headers['reg_code']][row]}")
                continue
            JalDB().add_dividend(DividendSubtype.Dividend, timestamp, account_id, asset_id, amount, '', tax=tax)
            cnt += 1
            row += 1
        logging.info(g_tr('PSB', "Dividends loaded: ") + f"{cnt}")

    def transfer_in(self, timestamp, account_id, amount):
        currency_name = JalDB().get_asset_name(JalDB().get_account_currency(account_id))
        text = g_tr('PSB', "Deposit of ") + f"{amount:.2f} {currency_name} " + \
               f"@{datetime.utcfromtimestamp(timestamp).strftime('%d.%m.%Y')}\n" + \
               g_tr('PSB', "Select account to withdraw from:")
        pair_account = self._parent.selectAccount(text, account_id)
        if pair_account == 0:
            return
        JalDB().add_transfer(timestamp, pair_account, amount, account_id, amount, 0, 0, '')

    def transfer_out(self, timestamp, account_id, amount):
        currency_name = JalDB().get_asset_name(JalDB().get_account_currency(account_id))
        text = g_tr('PSB', "Withdrawal of ") + f"{-amount:.2f} {currency_name} " + \
               f"@{datetime.utcfromtimestamp(timestamp).strftime('%d.%m.%Y')}\n" + \
               g_tr('PSB', "Select account to deposit to:")
        pair_account = self._parent.selectAccount(text, account_id)
        if pair_account == 0:
            return                                       # amount is negative in XLS file
        JalDB().add_transfer(timestamp, account_id, -amount, pair_account, -amount, 0, 0, '')
