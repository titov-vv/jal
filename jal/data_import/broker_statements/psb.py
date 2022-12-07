import logging
from datetime import datetime, timezone

from jal.data_import.statement import FOF
from jal.data_import.statement_xls import StatementXLS

JAL_STATEMENT_CLASS = "StatementPSB"


# ----------------------------------------------------------------------------------------------------------------------
class StatementPSB(StatementXLS):
    Header = (2, 3, 'Брокер: ПАО "Промсвязьбанк"')
    PeriodPattern = (3, 6, r"с (?P<S>\d\d\.\d\d\.\d\d\d\d) по (?P<E>\d\d\.\d\d\.\d\d\d\d)")
    AccountPattern = (3, 9, r"(?P<ACCOUNT>\S*)( от \d\d\.\d\d\.\d\d\d\d)?")
    HeaderCol = 1
    SummaryHeader = "Сводная информация по счетам клиента в валюте счета"
    money_section = "Позиция денежных средств по биржевым площадкам"
    money_columns = {
        "name": "Валюта",
        "begin": "Входящие лимиты",
        "end": "Плановый исходящий остаток",
        "settled_end": "Исходящие лимиты"
    }
    asset_section = r"^Портфель на конец дня.*"
    asset_columns = {
        "name": r"Наименование эмитента, вид, категория \(тип\), выпуск, транш ЦБ",
        "isin": "ISIN",
        "reg_number": r"Номер гос\.регистрации"
    }

    def __init__(self):
        super().__init__()
        self.name = self.tr("PSB Broker")
        self.icon_name = "psb.ico"
        self.filename_filter = self.tr("PSB broker statement (*.xlsx *.xls)")

    def _load_deals(self):
        cnt = 0
        sections = [
            r"Сделки, .* с ЦБ на биржевых торговых .* с расчетами в дату заключения",
            r"Сделки, .* с ЦБ на биржевых торговых .* с расчетами Т\+, незавершенные в отчетном периоде",
            r"Сделки, .* с ЦБ на биржевых торговых .* с расчетами Т\+, рассчитанные в отчетном периоде"
        ]
        columns = {
            "timestamp": "Дата и время совершения сделки",
            "*settlement": r".*ая дата исполнения сделки",
            "number": "Номер сделки в ТС",
            "isin": "ISIN",
            "reg_number": r"Номер гос\. регистрации",
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
                if self._statement[self.HeaderCol][row].startswith('Итого') or \
                        self._statement[self.HeaderCol][row] == '':
                    break
                deal_number = self._statement[headers['number']][row]
                deal_currency = self._statement[headers['currency']][row].split('/')[0].strip()    # <- 'deal / payment'
                try:
                    code = self.currency_id(self.currency_substitutions[deal_currency])
                except KeyError:
                    code = self.currency_id(deal_currency)
                asset_id = self.asset_id({'isin': self._statement[headers['isin']][row],
                                          'reg_number': self._statement[headers['reg_number']][row],
                                          'currency': code, 'search_online': "MOEX"})
                if self._statement[headers['B/S']][row] == 'покупка':
                    qty = self._statement[headers['qty']][row]
                    bond_interest = -self._statement[headers['accrued_int']][row]
                elif self._statement[headers['B/S']][row] == 'продажа':
                    qty = -self._statement[headers['qty']][row]
                    bond_interest = self._statement[headers['accrued_int']][row]
                else:
                    row += 1
                    logging.warning(self.tr("Unknown trade type: ") + self._statement[headers['B/S']][row])
                    continue

                price = self._statement[headers['price']][row]
                currencies = [x.strip() for x in self._statement[headers['currency']][row].split('/')]
                if currencies[0] != currencies[1]:
                    row += 1
                    logging.warning(self.tr("Unsupported trade with different currencies: ") + currencies)
                    continue
                currency = currencies[0]
                fee = self._statement[headers['fee1']][row] + self._statement[headers['fee2']][row] + \
                      self._statement[headers['fee3']][row] + self._statement[headers['fee_broker']][row]
                amount = self._statement[headers['amount']][row]
                if abs(abs(price * qty) - amount) >= self.RU_PRICE_TOLERANCE:
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
                account_id = self._find_account_id(self._account_number, currency)
                new_id = max([0] + [x['id'] for x in self._data[FOF.TRADES]]) + 1
                trade = {"id": new_id, "number": deal_number, "timestamp": timestamp, "settlement": settlement,
                         "account": account_id, "asset": asset_id, "quantity": qty, "price": price, "fee": fee}
                self._data[FOF.TRADES].append(trade)
                if bond_interest != 0:
                    new_id = max([0] + [x['id'] for x in self._data[FOF.ASSET_PAYMENTS]]) + 1
                    payment = {"id": new_id, "type": FOF.PAYMENT_INTEREST, "account": account_id,
                               "timestamp": timestamp,
                               "number": deal_number, "asset": asset_id, "amount": bond_interest, "description": "НКД"}
                    self._data[FOF.ASSET_PAYMENTS].append(payment)
                cnt += 1
                row += 1
        logging.info(self.tr("Trades loaded: ") + f"{cnt}")

    def _load_cash_transactions(self):
        self.load_cash_transactions()
        self.load_coupons()
        self.load_dividends()

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
            if self._statement[self.HeaderCol][row] == '':
                break
            if self._statement[headers['note']][row].startswith("Дивиденды") or \
                    self._statement[headers['note']][row].startswith("Погашение купона"):
                row += 1   # These data present in separate tables to load
                continue
            if self._statement[headers['note']][row] != '':
                logging.warning(self.tr("Unknown cash transaction: ") + self._statement[headers['note']][row])
                row += 1
                continue

            timestamp = int(datetime.strptime(self._statement[headers['date']][row],
                                              "%d.%m.%Y").replace(tzinfo=timezone.utc).timestamp())
            amount = self._statement[headers['amount']][row]
            account_id = self._find_account_id(self._account_number, self._statement[headers['currency']][row])
            if self._statement[headers['operation']][row] == 'Зачислено на счет':
                self.transfer_in(timestamp, account_id, amount)
            elif self._statement[headers['operation']][row] == 'Списано со счета':
                self.transfer_out(timestamp, account_id, amount)
            else:
                logging.warning(self.tr("Unknown cash operation: ") + self._statement[headers['operation']][row])
                row += 1
                continue
            cnt += 1
            row += 1
        logging.info(self.tr("Cash transactions loaded: ") + f"{cnt}")

    def transfer_in(self, timestamp, account_id, amount):
        account = [x for x in self._data[FOF.ACCOUNTS] if x["id"] == account_id][0]
        new_id = max([0] + [x['id'] for x in self._data[FOF.TRANSFERS]]) + 1
        transfer = {"id": new_id, "account": [0, account_id, 0],
                    "asset": [account['currency'], account['currency']], "timestamp": timestamp,
                    "withdrawal": amount, "deposit": amount, "fee": 0.0}
        self._data[FOF.TRANSFERS].append(transfer)

    def transfer_out(self, timestamp, account_id, amount):
        account = [x for x in self._data[FOF.ACCOUNTS] if x["id"] == account_id][0]
        new_id = max([0] + [x['id'] for x in self._data[FOF.TRANSFERS]]) + 1
        transfer = {"id": new_id, "account": [account_id, 0, 0],
                    "asset": [account['currency'], account['currency']], "timestamp": timestamp,
                    "withdrawal": -amount, "deposit": -amount, "fee": 0.0}
        self._data[FOF.TRANSFERS].append(transfer)

    def load_coupons(self):
        cnt = 0
        columns = {
            "date": "Дата операции",
            "operation": "Вид операции",
            "asset_name": r"Наименование эмитента, вид, категория \(тип\), выпуск, транш ЦБ",
            "isin": "ISIN",
            "reg_number": "Регистрационный номер ЦБ",
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
                logging.warning(self.tr("Unsupported payment: ") + self._statement[headers['operation']][row])
                row += 1
                continue
            timestamp = int(datetime.strptime(self._statement[headers['date']][row],
                                              "%d.%m.%Y").replace(tzinfo=timezone.utc).timestamp())
            amount = float(self._statement[headers['coupon']][row])
            tax = float(self._statement[headers['tax']][row])
            account_id = self._find_account_id(self._account_number, self._statement[headers['currency']][row])
            try:
                code = self.currency_id(self.currency_substitutions[self._statement[headers['currency']][row]])
            except KeyError:
                code = self.currency_id(self._statement[headers['currency']][row])
            asset_id = self.asset_id({'isin': self._statement[headers['isin']][row],
                                      'reg_number': self._statement[headers['reg_number']][row],
                                      'currency': code, 'search_online': "MOEX"})
            note = self._statement[headers['operation']][row] + " " + self._statement[headers['asset_name']][row]
            new_id = max([0] + [x['id'] for x in self._data[FOF.ASSET_PAYMENTS]]) + 1
            payment = {"id": new_id, "type": FOF.PAYMENT_INTEREST, "account": account_id, "timestamp": timestamp,
                       "asset": asset_id, "amount": amount, "tax": tax, "description": note}
            self._data[FOF.ASSET_PAYMENTS].append(payment)
            cnt += 1
            row += 1
        logging.info(self.tr("Bond interests loaded: ") + f"{cnt}")

    def load_dividends(self):
        cnt = 0
        columns = {
            "date": "Дата операции",
            "isin": "ISIN",
            "reg_number": r"Номер гос\. регистрации",
            "currency": "Валюта Выплаты",
            "amount": "Сумма дивидендов",
            "tax": "Сумма удержанного налога"
        }

        row, headers = self.find_section_start("Выплата дивидендов", columns)
        if row < 0:
            return False
        while row < self._statement.shape[0]:
            if self._statement[self.HeaderCol][row] == '':
                break

            timestamp = int(datetime.strptime(self._statement[headers['date']][row],
                                              "%d.%m.%Y").replace(tzinfo=timezone.utc).timestamp())
            amount = float(self._statement[headers['amount']][row])
            tax = float(self._statement[headers['tax']][row])
            account_id = self._find_account_id(self._account_number, self._statement[headers['currency']][row])
            try:
                code = self.currency_id(self.currency_substitutions[self._statement[headers['currency']][row]])
            except KeyError:
                code = self.currency_id(self._statement[headers['currency']][row])
            asset_id = self.asset_id({'isin': self._statement[headers['isin']][row],
                                      'reg_number': self._statement[headers['reg_number']][row],
                                      'currency': code, 'search_online': "MOEX"})
            new_id = max([0] + [x['id'] for x in self._data[FOF.ASSET_PAYMENTS]]) + 1
            payment = {"id": new_id, "type": FOF.PAYMENT_DIVIDEND, "account": account_id, "timestamp": timestamp,
                       "asset": asset_id, "amount": amount, "tax": tax, "description": ''}
            self._data[FOF.ASSET_PAYMENTS].append(payment)
            cnt += 1
            row += 1
        logging.info(self.tr("Dividends loaded: ") + f"{cnt}")
