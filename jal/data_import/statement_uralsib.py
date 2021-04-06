import logging
import re
from datetime import datetime, timezone, time
from zipfile import ZipFile
import pandas

from jal.widgets.helpers import g_tr
from jal.db.update import JalDB
from jal.constants import Setup, DividendSubtype, PredefinedCategory, PredefinedAsset


# -----------------------------------------------------------------------------------------------------------------------
class UralsibCapital:
    Header = '  Брокер: ООО "УРАЛСИБ Брокер"'
    PeriodPattern = "  за период с (?P<S>\d\d\.\d\d\.\d\d\d\d) по (?P<E>\d\d\.\d\d\.\d\d\d\d)"
    DividendPattern = "> (?P<DESCR1>.*) \((?P<REG_CODE>.*)\) (?P<DESCR2>.*) налог в размере (?P<TAX>\d+\.\d\d) удержан. НДС не облагается."
    BondInterestPattern = "Погашение купона №( -?\d+)? (?P<NAME>.*)"

    def __init__(self, parent, filename):
        self._parent = parent
        self._filename = filename
        self._statement = None
        self._account_id = 0
        self._settled_cash = {}
        self._report_start = 0
        self._report_end = 0

    def load(self):
        self._settled_cash = {}
        with ZipFile(self._filename) as zip_file:
            contents = zip_file.namelist()
            if len(contents) != 1:
                logging.error(g_tr('Uralsib', "Archive contains multiple files, only one is expected for import"))
                return False
            with zip_file.open(contents[0]) as r_file:
                self._statement = pandas.read_excel(io=r_file.read(), header=None, na_filter=False)
        if not self.validate():
            return False
        self.load_cash_balance()
        self.load_broker_fee()
        self.load_stock_deals()
        self.load_futures_deals()
        self.load_cash_transactions()
        logging.info(g_tr('Uralsib', "Uralsib Capital statement loaded; Planned cash: ")
                     + f"{self._settled_cash[self._account_id]}")
        return True

    def validate(self):
        if self._statement[2][0] != self.Header:
            logging.error(g_tr('Uralsib', "Can't find Uralsib Capital report header"))
            return False
        account_name = self._statement[2][7]
        parts = re.match(self.PeriodPattern, self._statement[2][2], re.IGNORECASE)
        if parts is None:
            logging.error(g_tr('Uralsib', "Can't parse Uralsib Capital statement period"))
            return False
        statement_dates = parts.groupdict()
        self._report_start = int(datetime.strptime(statement_dates['S'],
                                                   "%d.%m.%Y").replace(tzinfo=timezone.utc).timestamp())
        end_day = datetime.strptime(statement_dates['E'], "%d.%m.%Y")
        self._report_end = int(datetime.combine(end_day, time(23, 59, 59)).replace(tzinfo=timezone.utc).timestamp())
        if not self._parent.checkStatementPeriod(account_name, self._report_start):
            return False
        logging.info(g_tr('Uralsib', "Loading Uralsib Capital statement for account ") +
                     f"{account_name}: {statement_dates['S']} - {statement_dates['E']}")
        self._account_id = JalDB().get_account_id(account_name)
        if self._account_id is None:
            return False
        return True

    def find_section_start(self, header, subtitle, columns, header_height=2) -> (int, dict):
        header_found = False
        start_row = -1
        headers = {}
        for i, row in self._statement.iterrows():
            if not header_found and (row[0] == header):
                header_found = True
            if header_found and ((subtitle == '') or (row[0] == subtitle)):
                start_row = i + 1  # points to columns header row
                break
        if start_row > 0:
            for col in range(self._statement.shape[1]):  # Load section headers from next row
                for row in range(header_height):
                    headers[self._statement[col][start_row+row]] = col
            start_row += header_height
        column_indices = {column: headers.get(columns[column], -1) for column in columns}
        if start_row > 0:
            for idx in column_indices:
                if column_indices[idx] < 0:
                    logging.error(g_tr('Uralsib', "Column not found in section ") + f"{header}: {idx}")
                    start_row = -1
        return start_row, column_indices

    def load_stock_deals(self):
        cnt = 0
        columns = {
            "number": "Номер сделки",
            "date": "Дата сделки",
            "time": "Время сделки",
            "isin": "ISIN",
            "B/S": "Вид сделки",
            "price": "Цена одной ЦБ",
            "qty": "Количество ЦБ, шт.",
            "amount": "Сумма сделки",
            "accrued_int": "НКД",
            "settlement": "Дата поставки, плановая",
            "fee_ex": "Комиссия ТС"
        }

        row, headers = self.find_section_start("СДЕЛКИ С ЦЕННЫМИ БУМАГАМИ",
                                               "Биржевые сделки с ценными бумагами в отчетном периоде", columns)
        if row < 0:
            return False
        asset_name = ''
        while row < self._statement.shape[0]:
            if self._statement[0][row] == '' and self._statement[0][row + 1] == '':
                break
            if self._statement[0][row] == 'Итого по выпуску:' or self._statement[0][row] == '':
                row += 1
                continue
            try:
                deal_number = int(self._statement[0][row])
            except ValueError:
                asset_name = self._statement[0][row]
                row += 1
                continue

            asset_id = JalDB().get_asset_id('', isin=self._statement[headers['isin']][row], name=asset_name)
            if self._statement[headers['B/S']][row] == 'Покупка':
                qty = self._statement[headers['qty']][row]
                bond_interest = -self._statement[headers['accrued_int']][row]
            elif self._statement[headers['B/S']][row] == 'Продажа':
                qty = -self._statement[headers['qty']][row]
                bond_interest = self._statement[headers['accrued_int']][row]
            else:
                row += 1
                logging.warning(g_tr('Uralsib', "Unknown trade type: ") + self._statement[headers['B/S']][row])
                continue

            price = self._statement[headers['price']][row]
            fee = self._statement[headers['fee_ex']][row]
            amount = self._statement[headers['amount']][row]
            if abs(abs(price * qty) - amount) >= Setup.DISP_TOLERANCE:
                price = abs(amount / qty)
            ts_string = self._statement[headers['date']][row] + ' ' + self._statement[headers['time']][row]
            timestamp = int(datetime.strptime(ts_string, "%d.%m.%Y %H:%M:%S").replace(tzinfo=timezone.utc).timestamp())
            settlement = int(datetime.strptime(self._statement[headers['settlement']][row],
                                               "%d.%m.%Y").replace(tzinfo=timezone.utc).timestamp())
            JalDB().add_trade(self._account_id, asset_id, timestamp, settlement, deal_number, qty, price, -fee)
            if bond_interest != 0:
                JalDB().add_dividend(DividendSubtype.BondInterest, timestamp, self._account_id, asset_id,
                                     bond_interest, "НКД", deal_number)
            cnt += 1
            row += 1
        logging.info(g_tr('Uralsib', "Trades loaded: ") + f"{cnt}")

    def load_futures_deals(self):
        cnt = 0
        columns = {
            "number": "Номер сделки",
            "date": "Дата сделки",
            "time": "Время сделки",
            "symbol": "Код контракта",
            "B/S": "Вид сделки",
            "price": "Цена фьючерса",
            "qty": "Количество контрактов, шт.",
            "amount": "Сумма",
            "settlement": "Дата расчетов по сделке",
            "fee_broker": "Комиссия брокера, руб.",
            "fee_ex": "Комиссия ТС, руб."
        }

        row, headers = self.find_section_start("СДЕЛКИ С ФЬЮЧЕРСАМИ И ОПЦИОНАМИ",
                                               "Сделки с фьючерсами", columns)
        if row < 0:
            return False
        while row < self._statement.shape[0]:
            if self._statement[0][row] == '' and self._statement[0][row + 1] == '':
                break
            if self._statement[0][row].startswith("Входящая позиция по контракту") or \
                    self._statement[0][row].startswith("Итого по контракту") or self._statement[0][row] == '':
                row += 1
                continue
            try:
                deal_number = int(self._statement[0][row])
            except ValueError:
                row += 1
                continue

            asset_id = JalDB().get_asset_id(self._statement[headers['symbol']][row])
            if self._statement[headers['B/S']][row] == 'Покупка':
                qty = self._statement[headers['qty']][row]
            elif self._statement[headers['B/S']][row] == 'Продажа':
                qty = -self._statement[headers['qty']][row]
            else:
                row += 1
                logging.warning(g_tr('Uralsib', "Unknown trade type: ") + self._statement[headers['B/S']][row])
                continue

            price = self._statement[headers['price']][row]
            fee = self._statement[headers['fee_broker']][row] + self._statement[headers['fee_ex']][row]
            amount = self._statement[headers['amount']][row]
            if abs(abs(price * qty) - amount) >= Setup.DISP_TOLERANCE:
                price = abs(amount / qty)
            ts_string = self._statement[headers['date']][row] + ' ' + self._statement[headers['time']][row]
            timestamp = int(datetime.strptime(ts_string, "%d.%m.%Y %H:%M:%S").replace(tzinfo=timezone.utc).timestamp())
            settlement = int(datetime.strptime(self._statement[headers['settlement']][row],
                                               "%d.%m.%Y").replace(tzinfo=timezone.utc).timestamp())
            JalDB().add_trade(self._account_id, asset_id, timestamp, settlement, deal_number, qty, price, -fee)
            cnt += 1
            row += 1
        logging.info(g_tr('Uralsib', "Futures trades loaded: ") + f"{cnt}")

    def load_cash_transactions(self):
        cnt = 0
        columns = {
            "number": "№ операции",
            "date": "Дата",
            "type": "Тип операции",
            "amount": "Сумма",
            "description": "Комментарий"
        }
        operations = {
            'Ввод ДС': self.transfer_in,
            'Вывод ДС': self.transfer_out,
            'Налог': self.tax,
            'Доход по финансовым инструментам': self.dividend,
            'Погашение купона': self.interest
        }

        row, headers = self.find_section_start("ДВИЖЕНИЕ ДЕНЕЖНЫХ СРЕДСТВ ЗА ОТЧЕТНЫЙ ПЕРИОД", '',
                                               columns, header_height=1)
        if row < 0:
            return False

        while row < self._statement.shape[0]:
            if self._statement[0][row] == '' and self._statement[0][row + 1] == '':
                break

            operation = self._statement[headers['type']][row]
            if operation not in operations:   # not supported type of operation
                row += 1
                continue
            number = self._statement[headers['number']][row]
            timestamp = int(datetime.strptime(self._statement[headers['date']][row],
                                              "%d.%m.%Y").replace(tzinfo=timezone.utc).timestamp())
            amount = self._statement[headers['amount']][row]
            description = self._statement[headers['description']][row]

            operations[operation](timestamp, number, amount, description)

            cnt += 1
            row += 1
        logging.info(g_tr('Uralsib', "Cash operations loaded: ") + f"{cnt}")

    def transfer_in(self, timestamp, _number, amount, description):
        currency_name = JalDB().get_asset_name(JalDB().get_account_currency(self._account_id))
        text = g_tr('Uralsib', "Deposit of ") + f"{amount:.2f} {currency_name} " + \
               f"@{datetime.utcfromtimestamp(timestamp).strftime('%d.%m.%Y')}\n" + \
               g_tr('Uralsib', "Select account to withdraw from:")
        pair_account = self._parent.selectAccount(text, self._account_id)
        if pair_account == 0:
            return
        JalDB().add_transfer(timestamp, pair_account, amount, self._account_id, amount, 0, 0, description)

    def transfer_out(self, timestamp, _number, amount, description):
        currency_name = JalDB().get_asset_name(JalDB().get_account_currency(self._account_id))
        text = g_tr('Uralsib', "Withdrawal of ") + f"{-amount:.2f} {currency_name} " + \
               f"@{datetime.utcfromtimestamp(timestamp).strftime('%d.%m.%Y')}\n" + \
               g_tr('Uralsib', "Select account to deposit to:")
        pair_account = self._parent.selectAccount(text, self._account_id)
        if pair_account == 0:
            return                                       # amount is negative in XLS file
        JalDB().add_transfer(timestamp, self._account_id, -amount, pair_account, -amount, 0, 0, description)

    def dividend(self, timestamp, number, amount, description):
        parts = re.match(self.DividendPattern, description, re.IGNORECASE)
        if parts is None:
            logging.error(g_tr('Uralsib', "Can't parse dividend description ") + f"'{description}'")
            return
        dividend_data = parts.groupdict()
        asset_id = JalDB().get_asset_id('', reg_code=dividend_data['REG_CODE'])
        if asset_id is None:
            logging.error(g_tr('Uralsib', "Can't find asset for dividend ") + f"'{description}'")
            return
        try:
            tax = float(dividend_data['TAX'])
        except ValueError:
            logging.error(g_tr('Uralsib', "Failed to convert dividend tax ") + f"'{description}'")
            return
        amount = amount + tax   # Statement contains value after taxation while JAL stores value before tax
        shortened_description = dividend_data['DESCR1'] + ' ' + dividend_data['DESCR2']
        JalDB().add_dividend(DividendSubtype.Dividend, timestamp, self._account_id, asset_id,
                             amount, shortened_description, trade_number=number, tax=tax)

    def interest(self, timestamp, number, amount, description):
        parts = re.match(self.BondInterestPattern, description, re.IGNORECASE)
        if parts is None:
            logging.error(g_tr('Uralsib', "Can't parse bond interest description ") + f"'{description}'")
            return
        interest_data = parts.groupdict()
        asset_id = JalDB().find_asset_like_name(interest_data['NAME'], asset_type=PredefinedAsset.Bond)
        if asset_id is None:
            logging.error(g_tr('Uralsib', "Can't find asset for bond interest ") + f"'{description}'")
            return
        JalDB().add_dividend(DividendSubtype.BondInterest, timestamp, self._account_id, asset_id,
                             amount, description, number)

    def tax(self, timestamp, _number, amount, description):
        JalDB().add_cash_transaction(self._account_id, self._parent.getAccountBank(self._account_id), timestamp,
                                     amount, PredefinedCategory.Taxes, description)

    def load_cash_balance(self):
        columns = {
            "settled_cash": "Плановый исходящий остаток"
        }
        row, headers = self.find_section_start("ПОЗИЦИЯ ПО ДЕНЕЖНЫМ СРЕДСТВАМ", '', columns)
        if row < 0:
            return False
        self._settled_cash[self._account_id] = self._statement[headers['settled_cash']][row]

    def load_broker_fee(self):
        cnt = 0
        header_found = False
        for i, row in self._statement.iterrows():
            if (not header_found) and (row[0] == "Уплаченная комиссия, в том числе"):
                header_found = True  # Start of broker fees list
                continue
            if header_found:
                if row[0] != "":     # End of broker fee list
                    break
                try:
                    fee = float(row[6])
                except (ValueError, TypeError):
                    continue
                if fee == 0:
                    continue
                JalDB().add_cash_transaction(self._account_id, self._parent.getAccountBank(self._account_id),
                                             self._report_end, fee, PredefinedCategory.Fees, row[1])
                cnt += 1
        logging.info(g_tr('Uralsib', "Fees loaded: ") + f"{cnt}")
