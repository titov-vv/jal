import logging
import re
from datetime import datetime, timezone

from jal.constants import Setup, PredefinedCategory
from jal.data_import.statement import FOF, Statement_ImportError
from jal.data_import.statement_xls import StatementXLS


class StatementUKFU(StatementXLS):
    Header = (2, 0, '  Брокер: ООО "УРАЛСИБ Брокер"')
    PeriodPattern = (2, 2, r"  за период с (?P<S>\d\d\.\d\d\.\d\d\d\d) по (?P<E>\d\d\.\d\d\.\d\d\d\d)")
    AccountPattern = (2, 7, None)
    SummaryHeader = "СОСТОЯНИЕ ДЕНЕЖНЫХ СРЕДСТВ НА СЧЕТЕ"
    trade_columns = {
        "number": "Номер сделки",
        "date": "Дата сделки",
        "time": "Время сделки",
        "settlement": "Дата поставки, плановая",
        "isin": "ISIN",
        "B/S": "Вид сделки",
        "price": "Цена одной ЦБ",
        "qty": "Количество ЦБ, шт.",
        "amount": "Сумма сделки",
        "accrued_int": "НКД",
        "fee_ex": "Комиссия ТС",
        "currency": "Валюта цены"
    }

    asset_section = "СОСТОЯНИЕ ПОРТФЕЛЯ ЦЕННЫХ БУМАГ"
    asset_columns = {
        "name": "Наименование ЦБ",
        "isin": "ISIN",
        "reg_code": "Номер гос. регистрации / CFI код"
    }

    def __init__(self):
        super().__init__()
        self.StatementName = self.tr("Uralsib broker")
        self.asset_withdrawal = []

    def _load_deals(self):
        self.load_stock_deals()
        self.load_futures_deals()
        self.load_asset_cancellations()

    def _load_cash_transactions(self):
        self.load_cash_transactions()
        self.load_broker_fee()

    def load_stock_deals(self):
        cnt = 0
        columns = {
            "number": "Номер сделки",
            "date": "Дата сделки",
            "time": "Время сделки",
            "isin": "ISIN",
            "B/S": "Вид сделки",
            "price": "Цена одной ЦБ",
            "currency": "Валюта цены",
            "qty": r"Количество ЦБ, шт\.",
            "amount": "Сумма сделки",
            "accrued_int": "НКД",
            "settlement": "Дата поставки, плановая",
            "fee_ex": "Комиссия ТС"
        }

        row, headers = self.find_section_start("СДЕЛКИ С ЦЕННЫМИ БУМАГАМИ", columns,
                                               subtitle="Биржевые сделки с ценными бумагами в отчетном периоде",
                                               header_height=2)
        if row < 0:
            return
        while row < self._statement.shape[0]:
            if self._statement[self.HeaderCol][row] == '' and self._statement[self.HeaderCol][row + 1] == '':
                break
            if self._statement[self.HeaderCol][row].startswith('Итого по выпуску:') or \
                    self._statement[self.HeaderCol][row] == '':
                row += 1
                continue
            try:
                deal_number = int(self._statement[self.HeaderCol][row])
            except ValueError:
                row += 1
                continue
            isin = self._statement[headers['isin']][row]
            asset_id = self._find_asset_id(isin=isin)
            if not asset_id:
                asset_id = self._add_asset(isin, '', '')
            if self._statement[headers['B/S']][row] == 'Покупка':
                qty = self._statement[headers['qty']][row]
                bond_interest = -self._statement[headers['accrued_int']][row]
            elif self._statement[headers['B/S']][row] == 'Продажа':
                qty = -self._statement[headers['qty']][row]
                bond_interest = self._statement[headers['accrued_int']][row]
            else:
                row += 1
                logging.warning(self.tr("Unknown trade type: ") + self._statement[headers['B/S']][row])
                continue

            price = self._statement[headers['price']][row]
            currency = self._statement[headers['currency']][row]
            fee = self._statement[headers['fee_ex']][row]
            amount = self._statement[headers['amount']][row]
            if abs(abs(price * qty) - amount) >= Setup.DISP_TOLERANCE:
                price = abs(amount / qty)
            ts_string = self._statement[headers['date']][row] + ' ' + self._statement[headers['time']][row]
            timestamp = int(datetime.strptime(ts_string, "%d.%m.%Y %H:%M:%S").replace(tzinfo=timezone.utc).timestamp())
            settlement = int(datetime.strptime(self._statement[headers['settlement']][row],
                                               "%d.%m.%Y").replace(tzinfo=timezone.utc).timestamp())
            account_id = self._find_account_id(self._account_number, currency)
            new_id = max([0] + [x['id'] for x in self._data[FOF.TRADES]]) + 1
            trade = {"id": new_id, "number": str(deal_number), "timestamp": timestamp, "settlement": settlement,
                     "account": account_id, "asset": asset_id, "quantity": qty, "price": price, "fee": fee}
            self._data[FOF.TRADES].append(trade)
            if bond_interest != 0:
                new_id = max([0] + [x['id'] for x in self._data[FOF.ASSET_PAYMENTS]]) + 1
                payment = {"id": new_id, "type": FOF.PAYMENT_INTEREST, "account": account_id, "timestamp": timestamp,
                           "number": str(deal_number), "asset": asset_id, "amount": bond_interest, "description": "НКД"}
                self._data[FOF.ASSET_PAYMENTS].append(payment)
            cnt += 1
            row += 1
        logging.info(self.tr("Trades loaded: ") + f"{cnt}")

    def load_futures_deals(self):
        cnt = 0
        columns = {
            "number": "Номер сделки",
            "date": "Дата сделки",
            "time": "Время сделки",
            "symbol": "Код контракта",
            "B/S": "Вид сделки",
            "price": "Цена фьючерса",
            "currency": "Валюта цены",
            "qty": r"Количество контрактов, шт\.",
            "amount": "Сумма",
            "settlement": "Дата расчетов по сделке",
            "fee_broker": r"Комиссия брокера, руб\.",
            "fee_ex": r"Комиссия ТС, руб\."
        }

        row, headers = self.find_section_start("СДЕЛКИ С ФЬЮЧЕРСАМИ И ОПЦИОНАМИ", columns,
                                               subtitle="Сделки с фьючерсами")
        if row < 0:
            return False
        while row < self._statement.shape[0]:
            if self._statement[self.HeaderCol][row] == '' and self._statement[self.HeaderCol][row + 1] == '':
                break
            if self._statement[self.HeaderCol][row].startswith("Входящая позиция по контракту") or \
                    self._statement[self.HeaderCol][row].startswith("Итого по контракту") or \
                    self._statement[self.HeaderCol][row] == '':
                row += 1
                continue
            try:
                deal_number = int(self._statement[self.HeaderCol][row])
            except ValueError:
                row += 1
                continue

            symbol = self._statement[headers['symbol']][row]
            asset_id = self._find_asset_id(symbol=symbol)
            if not asset_id:
                asset_id = self._add_asset('', '', symbol=symbol)
            if self._statement[headers['B/S']][row] == 'Покупка':
                qty = self._statement[headers['qty']][row]
            elif self._statement[headers['B/S']][row] == 'Продажа':
                qty = -self._statement[headers['qty']][row]
            else:
                row += 1
                logging.warning(self.tr("Unknown trade type: ") + self._statement[headers['B/S']][row])
                continue

            price = self._statement[headers['price']][row]
            currency = self._statement[headers['currency']][row]
            fee = self._statement[headers['fee_broker']][row] + self._statement[headers['fee_ex']][row]
            amount = self._statement[headers['amount']][row]
            if abs(abs(price * qty) - amount) >= Setup.DISP_TOLERANCE:
                price = abs(amount / qty)
            ts_string = self._statement[headers['date']][row] + ' ' + self._statement[headers['time']][row]
            timestamp = int(datetime.strptime(ts_string, "%d.%m.%Y %H:%M:%S").replace(tzinfo=timezone.utc).timestamp())
            settlement = int(datetime.strptime(self._statement[headers['settlement']][row],
                                               "%d.%m.%Y").replace(tzinfo=timezone.utc).timestamp())
            account_id = self._find_account_id(self._account_number, currency)
            new_id = max([0] + [x['id'] for x in self._data[FOF.TRADES]]) + 1
            trade = {"id": new_id, "number": deal_number, "timestamp": timestamp, "settlement": settlement,
                     "account": account_id, "asset": asset_id, "quantity": qty, "price": price, "fee": fee}
            self._data[FOF.TRADES].append(trade)
            cnt += 1
            row += 1
        logging.info(self.tr("Futures trades loaded: ") + f"{cnt}")

    def load_asset_cancellations(self):
        columns = {
            "number": "№ операции",
            "date": "Дата",
            "type": "Тип операции",
            "asset": "Наименование ЦБ",
            "reg_code": r"Номер гос\. регистрации",
            "qty": "Количество ЦБ",
            "note": "Комментарий"
        }

        row, headers = self.find_section_start("ДВИЖЕНИЕ ЦЕННЫХ БУМАГ ЗА ОТЧЕТНЫЙ ПЕРИОД", columns)
        if row < 0:
            return False
        while row < self._statement.shape[0]:
            if self._statement[self.HeaderCol][row] == '' and self._statement[self.HeaderCol][row + 1] == '':
                break

            if self._statement[headers['type']][row] != "Списание ЦБ после погашения":
                row += 1
                continue

            reg_code = self._statement[headers['reg_code']][row]
            asset_id = self._find_asset_id(reg_code=reg_code)
            if not asset_id:
                asset_id = self._add_asset('', reg_code)

            number = self._statement[headers['number']][row]
            timestamp = int(datetime.strptime(self._statement[headers['date']][row],
                                              "%d.%m.%Y").replace(tzinfo=timezone.utc).timestamp())
            # Statement has negative value for cancellation - will be used to create sell trade
            qty = self._statement[headers['qty']][row]
            note = self._statement[headers['note']][row]
            record = {"timestamp": timestamp, "asset": asset_id, "number": number, "quantity": qty, "note": note}
            self.asset_withdrawal.append(record)
            row += 1

    def load_cash_transactions(self):
        cnt = 0
        columns = {
            "number": "№ операции",
            "date": "Дата",
            "type": "Тип операции",
            "amount": "Сумма",
            "currency": "Валюта",
            "description": "Комментарий"
        }
        operations = {
            'Ввод ДС': self.transfer_in,
            'Вывод ДС': self.transfer_out,
            'Перевод ДС': self.transfer,
            'Налог': self.tax,
            'Доход по финансовым инструментам': self.dividend,
            'Погашение купона': self.interest,
            'Погашение номинала': self.bond_repayment,
            'Списано по сделке': None,   # These operations are results of trades
            'Получено по сделке': None,
            "Вариационная маржа": None,  # These are non-trade operations for derivatives
            "Заблокировано средств ГО": None
        }

        row, headers = self.find_section_start("ДВИЖЕНИЕ ДЕНЕЖНЫХ СРЕДСТВ ЗА ОТЧЕТНЫЙ ПЕРИОД",  columns)
        if row < 0:
            return False

        while row < self._statement.shape[0]:
            if self._statement[self.HeaderCol][row] == '' and self._statement[self.HeaderCol][row + 1] == '':
                break
            operation = self._statement[headers['type']][row]
            if operation not in operations:
                raise Statement_ImportError(self.tr("Unsuppported cash transaction ") + f"'{operation}'")
            number = self._statement[headers['number']][row]
            timestamp = int(datetime.strptime(self._statement[headers['date']][row],
                                              "%d.%m.%Y").replace(tzinfo=timezone.utc).timestamp())
            amount = self._statement[headers['amount']][row]
            description = self._statement[headers['description']][row]
            account_id = self._find_account_id(self._account_number, self._statement[headers['currency']][row])
            if operations[operation] is not None:
                operations[operation](timestamp, number, account_id, amount, description)
            cnt += 1
            row += 1
        logging.info(self.tr("Cash operations loaded: ") + f"{cnt}")

    def transfer(self, timestamp, number, account_id, amount, description):
        TransferPattern = r"^Перевод ДС на с\/с (?P<account_to>[\w|\/]+) с с\/с (?P<account_from>[\w|\/]+)\..*$"
        if amount < 0:  # there should be positive paired record
            return
        parts = re.match(TransferPattern, description, re.IGNORECASE)
        if parts is None:
            raise Statement_ImportError(self.tr("Can't parse transfer description ") + f"'{description}'")
        transfer = parts.groupdict()
        if len(transfer) != TransferPattern.count("(?P<"):  # check that expected number of groups was matched
            raise Statement_ImportError(self.tr("Transfer description miss some data ") + f"'{description}'")
        if transfer['account_from'] == transfer['account_to']:  # It is a technical record for incoming transfer
            return
        currency_id = [x for x in self._data[FOF.ACCOUNTS] if x["id"] == account_id][0]['currency']
        currency_name = [x for x in self._data[FOF.ASSETS] if x["id"] == currency_id][0]['symbol']
        account_from = self._find_account_id(transfer['account_from'], currency_name)
        account_to = self._find_account_id(transfer['account_to'], currency_name)
        new_id = max([0] + [x['id'] for x in self._data[FOF.TRANSFERS]]) + 1
        transfer = {"id": new_id, "account": [account_from, account_to, 0], "number": number,
                    "asset": [currency_id, currency_id], "timestamp": timestamp,
                    "withdrawal": amount, "deposit": amount, "fee": 0.0, "description": description}
        self._data[FOF.TRANSFERS].append(transfer)

    def transfer_in(self, timestamp, number, account_id, amount, description):
        account = [x for x in self._data[FOF.ACCOUNTS] if x["id"] == account_id][0]
        new_id = max([0] + [x['id'] for x in self._data[FOF.TRANSFERS]]) + 1
        transfer = {"id": new_id, "account": [0, account_id, 0], "number": number,
                    "asset": [account['currency'], account['currency']], "timestamp": timestamp,
                    "withdrawal": amount, "deposit": amount, "fee": 0.0, "description": description}
        self._data[FOF.TRANSFERS].append(transfer)

    def transfer_out(self, timestamp, number, account_id, amount, description):
        account = [x for x in self._data[FOF.ACCOUNTS] if x["id"] == account_id][0]
        new_id = max([0] + [x['id'] for x in self._data[FOF.TRANSFERS]]) + 1
        transfer = {"id": new_id, "account": [account_id, 0, 0], "number": number,
                    "asset": [account['currency'], account['currency']], "timestamp": timestamp,
                    "withdrawal": -amount, "deposit": -amount, "fee": 0.0, "description": description}
        self._data[FOF.TRANSFERS].append(transfer)

    def dividend(self, timestamp, number, account_id, amount, description):
        DividendPattern = r"> (?P<DESCR1>.*) \((?P<REG_CODE>.*)\)((?P<DESCR2> .*)? налог в размере (?P<TAX>\d+\.\d\d) удержан)?\. НДС не облагается\."
        ISINPattern = r"[A-Z]{2}.{9}\d"

        parts = re.match(DividendPattern, description, re.IGNORECASE)
        if parts is None:
            raise Statement_ImportError(self.tr("Can't parse dividend description ") + f"'{description}'")
        dividend_data = parts.groupdict()
        isin_match = re.match(ISINPattern, dividend_data['REG_CODE'])
        if isin_match:
            asset_id = self._find_asset_id(isin=dividend_data['REG_CODE'])
            if not asset_id:
                asset_id = self._add_asset(isin=dividend_data['REG_CODE'], reg_code='')
        else:
            asset_id = self._find_asset_id(reg_code=dividend_data['REG_CODE'])
            if not asset_id:
                asset_id = self._add_asset(isin='', reg_code=dividend_data['REG_CODE'])

        if dividend_data['TAX']:
            try:
                tax = float(dividend_data['TAX'])
            except ValueError:
                raise Statement_ImportError(self.tr("Failed to convert dividend tax ") + f"'{description}'")
        else:
            tax = 0
        amount = amount + tax   # Statement contains value after taxation while JAL stores value before tax
        if dividend_data['DESCR2']:
            short_description = dividend_data['DESCR1'] + ' ' + dividend_data['DESCR2'].strip()
        else:
            short_description = dividend_data['DESCR1']
        new_id = max([0] + [x['id'] for x in self._data[FOF.ASSET_PAYMENTS]]) + 1
        payment = {"id": new_id, "type": FOF.PAYMENT_DIVIDEND, "account": account_id, "timestamp": timestamp,
                   "number": number, "asset": asset_id, "amount": amount, "tax": tax, "description": short_description}
        self._data[FOF.ASSET_PAYMENTS].append(payment)

    def interest(self, timestamp, number, account_id, amount, description):
        BondInterestPattern = r"Погашение купона №( -?\d+)? (?P<NAME>.*)"

        parts = re.match(BondInterestPattern, description, re.IGNORECASE)
        if parts is None:
            logging.error(self.tr("Can't parse bond interest description ") + f"'{description}'")
            return
        interest_data = parts.groupdict()
        asset_id = self._find_asset_id(symbol=interest_data['NAME'])
        if asset_id is None:
            raise Statement_ImportError(self.tr("Can't find asset for bond interest ") + f"'{description}'")
        new_id = max([0] + [x['id'] for x in self._data[FOF.ASSET_PAYMENTS]]) + 1
        payment = {"id": new_id, "type": FOF.PAYMENT_INTEREST, "account": account_id, "timestamp": timestamp,
                   "number": number, "asset": asset_id, "amount": amount, "description": description}
        self._data[FOF.ASSET_PAYMENTS].append(payment)

    def bond_repayment(self, timestamp, _number, account_id, amount, description):
        BondRepaymentPattern = r"Погашение номинала (?P<NAME>.*)"

        parts = re.match(BondRepaymentPattern, description, re.IGNORECASE)
        if parts is None:
            logging.error(self.tr("Can't parse bond repayment description ") + f"'{description}'")
            return
        interest_data = parts.groupdict()
        asset_id = self._find_asset_id(symbol=interest_data['NAME'])
        if not asset_id:
            raise Statement_ImportError(self.tr("Can't find asset for bond repayment ") + f"'{description}'")
        match = [x for x in self.asset_withdrawal if x['asset'] == asset_id and x['timestamp'] == timestamp]
        if not match:
            logging.error(self.tr("Can't find asset cancellation record for ") + f"'{description}'")
            return
        if len(match) != 1:
            logging.error(self.tr("Multiple asset cancellation match for ") + f"'{description}'")
            return
        asset_cancel = match[0]

        qty = asset_cancel['quantity']
        price = abs(amount / qty)   # Price is always positive
        note = description + ", " + asset_cancel['note']
        new_id = max([0] + [x['id'] for x in self._data[FOF.TRADES]]) + 1
        trade = {"id": new_id, "number": asset_cancel['number'], "timestamp": timestamp, "settlement": timestamp,
                 "account": account_id, "asset": asset_id, "quantity": qty, "price": price, "fee": 0.0, "note": note}
        self._data[FOF.TRADES].append(trade)

    def tax(self, timestamp, _number, account_id, amount, description):
        new_id = max([0] + [x['id'] for x in self._data[FOF.INCOME_SPENDING]]) + 1
        tax = {"id": new_id, "timestamp": timestamp, "account": account_id, "peer": 0,
               "lines": [{"amount": amount, "category": -PredefinedCategory.Taxes, "description": description}]}
        self._data[FOF.INCOME_SPENDING].append(tax)

    def load_broker_fee(self):
        header_row = self.find_row(self.SummaryHeader) + 1
        if header_row < 0:
            logging.warning(self.tr("Can't get header to find fees"))
            return
        header_found = False
        for i, row in self._statement.iterrows():
            if (not header_found) and (row[self.HeaderCol] == "Уплаченная комиссия, в том числе"):
                header_found = True  # Start of broker fees list
                continue
            if header_found:
                if row[self.HeaderCol] != "":     # End of broker fee list
                    break
                for col in range(6, self._statement.shape[1]):
                    if not self._statement[col][header_row]:
                        break
                    try:
                        fee = float(row[col])
                    except (ValueError, TypeError):
                        continue
                    if fee == 0:
                        continue
                    if row[1] == 'комиссия торговой системы':  # Exchange fee is part of trades
                        continue
                    account_id = self._find_account_id(self._account_number, self._statement[col][header_row])
                    new_id = max([0] + [x['id'] for x in self._data[FOF.INCOME_SPENDING]]) + 1
                    fee = {"id": new_id, "timestamp": self._data[FOF.PERIOD][1], "account": account_id, "peer": 0,
                           "lines": [{"amount": fee, "category": -PredefinedCategory.Fees, "description": row[1]}]}
                    self._data[FOF.INCOME_SPENDING].append(fee)
