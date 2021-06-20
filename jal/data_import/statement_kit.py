import logging
from datetime import datetime, timezone, timedelta

from jal.widgets.helpers import g_tr
from jal.constants import Setup, PredefinedCategory
from jal.data_import.statement import FOF
from jal.data_import.statement_xls import StatementXLS


class StatementKIT(StatementXLS):
    Header = (4, 0, "КИТ Финанс (АО)")
    PeriodPattern = (5, 8, r"(?P<S>\d\d\.\d\d\.\d\d\d\d)\s.\s(?P<E>\d\d\.\d\d\.\d\d\d\d)")
    AccountPattern = (5, 5, r"(?P<ACCOUNT>.*)-(.*)")
    SummaryHeader = "Состояние денежных средств на счете"

    asset_section = "Состояние портфеля ценных бумаг"
    asset_columns = {
        "name": "Наименование\nЦБ ",
        "isin": "ISIN",
        "reg_code": "Код гос. регистрации"
    }

    def _load_deals(self):
        cnt = 0
        columns = {
            "number": "Номер\nсделки",
            "date": "Дата сделки",
            "time": "Время сделки",
            "asset": "Наименование\nЦБ",
            "isin": "ISIN",
            "B/S": "Тип операции",
            "price": "Цена сделки ",
            "qty": "Количество",
            "amount": "Сумма сделки",
            "currency": " Валюта\nзаключения\nсделки",
            "accrued_int": " НКД",
            "settlement": "Дата поставки\n\(план.\)",
            "fee_ex": "Комиссия\nТС",
            "fee_broker": "Комиссия\nброкера"
        }

        row, headers = self.find_section_start("Заключенные сделки с ценными бумагами", columns)
        if row < 0:
            return False
        while row < self._statement.shape[0]:
            if self._statement[0][row] == '' and self._statement[0][row + 1] == '':
                break
            isin = self._statement[headers['isin']][row]
            asset_id = self._find_asset_id(isin=self._statement[headers['isin']][row])
            if not asset_id:
                asset_id = self._add_asset(isin, '', '')
            if self._statement[headers['B/S']][row] == 'Покупка':
                amount = -self._statement[headers['amount']][row]
                qty = self._statement[headers['qty']][row]
                bond_interest = -self._statement[headers['accrued_int']][row]
            elif self._statement[headers['B/S']][row] == 'Продажа':
                amount = self._statement[headers['amount']][row]
                qty = -self._statement[headers['qty']][row]
                bond_interest = self._statement[headers['accrued_int']][row]
            else:
                row += 1
                logging.warning(g_tr('KIT', "Unknown trade type: ") + self._statement[headers['B/S']][row])
                continue
            price = self._statement[headers['price']][row]
            fee = round(abs(self._statement[headers['fee_ex']][row] + self._statement[headers['fee_broker']][row]), 8)
            if abs(abs(price * qty) - amount) >= Setup.DISP_TOLERANCE:
                price = abs(amount / qty)
            number = self._statement[headers['number']][row]
            # Dates are loaded as datetime objects but time is loaded as string
            t_date = self._statement[headers['date']][row]
            t_time = datetime.strptime(self._statement[headers['time']][row], "%H:%M:%S").time()
            trade_datetime = t_date + timedelta(hours=t_time.hour, minutes=t_time.minute, seconds=t_time.second)
            timestamp = int(trade_datetime.replace(tzinfo=timezone.utc).timestamp())
            settlement = int(self._statement[headers['settlement']][row].replace(tzinfo=timezone.utc).timestamp())
            account_id = self._find_account_id(self._account_number, self._statement[headers['currency']][row])
            new_id = max([0] + [x['id'] for x in self._data[FOF.TRADES]]) + 1
            trade = {"id": new_id, "number": str(number), "timestamp": timestamp, "settlement": settlement,
                     "account": account_id, "asset": asset_id, "quantity": qty, "price": price, "fee": fee}
            self._data[FOF.TRADES].append(trade)
            if bond_interest != 0:
                new_id = max([0] + [x['id'] for x in self._data[FOF.ASSET_PAYMENTS]]) + 1
                payment = {"id": new_id, "type": FOF.PAYMENT_INTEREST, "account": account_id, "timestamp": timestamp,
                           "number": str(number), "asset": asset_id, "amount": bond_interest, "description": "НКД"}
                self._data[FOF.ASSET_PAYMENTS].append(payment)
            cnt += 1
            row += 1
        logging.info(g_tr('KIT', "Trades loaded: ") + f"{cnt}")

    def _load_cash_transactions(self):
        cnt = 0
        columns = {
            "date": "Дата",
            "operation": "Тип операции",
            "amount": "Сумма",
            "currency": " Валюта",
            "reason": "Основание",
            "note": "Примечание",
            "market": "Секция"
        }
        operations = {
            'Внесение д/с в торг': self.transfer_in,
            'Вывод дс': self.transfer_out,
            'Ком бр аб плата спот': self.fee,
            'Комиссия НРД': self.fee
        }
        row, headers = self.find_section_start("Движение денежных средств по неторговым операциям", columns)
        if row < 0:
            return False
        while row < self._statement.shape[0]:
            if self._statement[0][row] == '':
                break
            operation = self._statement[headers['operation']][row]
            if operation not in operations:  # not supported type of operation
                row += 1
                continue
            timestamp = int(self._statement[headers['date']][row].replace(tzinfo=timezone.utc).timestamp())
            account_id = self._find_account_id(self._account_number, self._statement[headers['currency']][row])
            amount = self._statement[headers['amount']][row]
            reason = self._statement[headers['reason']][row]
            description = self._statement[headers['note']][row]
            operations[operation](timestamp, account_id, amount, reason, description)
            cnt += 1
            row += 1
        logging.info(g_tr('KIT', "Cash operations loaded: ") + f"{cnt}")

    def transfer_in(self, timestamp, account_id, amount, reason, note):
        account = [x for x in self._data[FOF.ACCOUNTS] if x["id"] == account_id][0]
        description = reason + ", " + note
        new_id = max([0] + [x['id'] for x in self._data[FOF.TRANSFERS]]) + 1
        transfer = {"id": new_id, "account": [0, account_id, 0],
                    "asset": [account['currency'], account['currency']], "timestamp": timestamp,
                    "withdrawal": amount, "deposit": amount, "fee": 0.0, "description": description}
        self._data[FOF.TRANSFERS].append(transfer)

    def transfer_out(self, timestamp, account_id, amount, reason, note):
        account = [x for x in self._data[FOF.ACCOUNTS] if x["id"] == account_id][0]
        description = reason + ", " + note  # amount is negative in XLSX file
        new_id = max([0] + [x['id'] for x in self._data[FOF.TRANSFERS]]) + 1
        transfer = {"id": new_id, "account": [account_id, 0, 0],
                    "asset": [account['currency'], account['currency']], "timestamp": timestamp,
                    "withdrawal": -amount, "deposit": -amount, "fee": 0.0, "description": description}
        self._data[FOF.TRANSFERS].append(transfer)

    def fee(self, timestamp, account_id, amount, _reason, description):
        new_id = max([0] + [x['id'] for x in self._data[FOF.INCOME_SPENDING]]) + 1
        tax = {"id": new_id, "timestamp": timestamp, "account": account_id, "peer": 0,
               "lines": [{"amount": amount, "category": -PredefinedCategory.Fees, "description": description}]}
        self._data[FOF.INCOME_SPENDING].append(tax)

# -----------------------------------------------------------------------------------------------------------------------
# class KITFinance:
#     Header = "КИТ Финанс (АО)"
#     AccountPattern = "(?P<ACCOUNT>.*)-(.*)"
#     PeriodPattern = r"(?P<S>\d\d\.\d\d\.\d\d\d\d) - (?P<E>\d\d\.\d\d\.\d\d\d\d)"
#
#     def __init__(self, parent, filename):
#         self._parent = parent
#         self._filename = filename
#         self._statement = None
#         self._account_id = 0
#         self._settled_cash = {}
#
#     def load(self):
#         self._statement = pandas.read_excel(self._filename, header=None, na_filter=False)
#         if not self.validate():
#             return False
#         self.load_cash_balance()
#         self.load_stock_deals()
#         self.load_cash_transactions()
#         logging.info(g_tr('KIT', "KIT Finance statement loaded; Planned cash: ")
#                      + f"{self._settled_cash[self._account_id]}")
#         return True
#
#     def validate(self):
#         if self._statement[4][0] != self.Header:
#             logging.error(g_tr('KIT', "Can't find KIT Finance report header"))
#             return False
#         parts = re.match(self.AccountPattern, self._statement[5][5], re.IGNORECASE)
#         if parts is None:
#             logging.error(g_tr('KIT', "Can't parse KIT Finance account number"))
#             return False
#         account_name = parts.groupdict()['ACCOUNT']
#         parts = re.match(self.PeriodPattern, self._statement[5][8], re.IGNORECASE)
#         if parts is None:
#             logging.error(g_tr('KIT', "Can't parse KIT Finance statement period"))
#             return False
#         statement_dates = parts.groupdict()
#         report_start = int(datetime.strptime(statement_dates['S'], "%d.%m.%Y").replace(tzinfo=timezone.utc).timestamp())
#         if not self._parent.checkStatementPeriod(account_name, report_start):
#             return False
#         logging.info(g_tr('KIT', "Loading KIT Finance statement for account ") +
#                      f"{account_name}: {statement_dates['S']} - {statement_dates['E']}")
#         self._account_id = JalDB().get_account_id(account_name)
#         return True
#
#     def find_section_start(self, header, columns) -> (int, dict):
#         start_row = -1
#         headers = {}
#         for i, row in self._statement.iterrows():
#             if row[0] == header:
#                 start_row = i + 1  # points to columns header row
#                 break
#         if start_row > 0:
#             for col in range(self._statement.shape[1]):  # Load section headers from next row
#                 headers[self._statement[col][start_row]] = col
#         column_indices = {column: headers.get(columns[column], -1) for column in columns}
#         if start_row > 0:
#             for idx in column_indices:
#                 if column_indices[idx] < 0:
#                     logging.error(g_tr('KIT', "Column not found in section ") + f"{header}: {idx}")
#                     start_row = -1
#         start_row += 1
#         return start_row, column_indices
#
#     def load_cash_balance(self):
#         row, headers = self.find_section_start("Состояние денежных средств на счете", {})
#         if row < 0:
#             return False
#         while row < self._statement.shape[0]:
#             if self._statement[0][row] == '':
#                 break
#             if self._statement[0][row] == 'Позиция по ДС на T+N':
#                 try:
#                     self._settled_cash[self._account_id] = float(self._statement[6][row])
#                 except (ValueError, TypeError):
#                     pass
#             row += 1
#
#     def load_stock_deals(self):
#         cnt = 0
#         columns = {
#             "number": "Номер\nсделки",
#             "date": "Дата сделки",
#             "time": "Время сделки",
#             "asset": "Наименование\nЦБ",
#             "isin": "ISIN",
#             "B/S": "Тип операции",
#             "price": "Цена сделки ",
#             "qty": "Количество",
#             "amount": "Сумма сделки",
#             "accrued_int": " НКД",
#             "settlement": "Дата поставки\n(план.)",
#             "fee_ex": "Комиссия\nТС",
#             "fee_broker": "Комиссия\nброкера"
#         }
#
#         row, headers = self.find_section_start("Заключенные сделки с ценными бумагами", columns)
#         if row < 0:
#             return False
#         while row < self._statement.shape[0]:
#             if self._statement[0][row] == '' and self._statement[0][row + 1] == '':
#                 break
#             asset_id = JalDB().get_asset_id('', isin=self._statement[headers['isin']][row],
#                                                 name=self._statement[headers['asset']][row])
#             if self._statement[headers['B/S']][row] == 'Покупка':
#                 amount = -self._statement[headers['amount']][row]
#                 qty = self._statement[headers['qty']][row]
#                 bond_interest = -self._statement[headers['accrued_int']][row]
#             elif self._statement[headers['B/S']][row] == 'Продажа':
#                 amount = self._statement[headers['amount']][row]
#                 qty = -self._statement[headers['qty']][row]
#                 bond_interest = self._statement[headers['accrued_int']][row]
#             else:
#                 row += 1
#                 logging.warning(g_tr('KIT', "Unknown trade type: ") + self._statement[headers['B/S']][row])
#                 continue
#             price = self._statement[headers['price']][row]
#             fee = round(abs(self._statement[headers['fee_ex']][row] + self._statement[headers['fee_broker']][row]), 8)
#             if abs(abs(price * qty) - amount) >= Setup.DISP_TOLERANCE:
#                 price = abs(amount / qty)
#             number = self._statement[headers['number']][row]
#             # Dates are loaded as datetime objects but time is loaded as string
#             t_date = self._statement[headers['date']][row]
#             t_time = datetime.strptime(self._statement[headers['time']][row], "%H:%M:%S").time()
#             trade_datetime = t_date + timedelta(hours=t_time.hour, minutes=t_time.minute, seconds=t_time.second)
#             timestamp = int(trade_datetime.replace(tzinfo=timezone.utc).timestamp())
#             settlement = int(self._statement[headers['settlement']][row].replace(tzinfo=timezone.utc).timestamp())
#             JalDB().add_trade(self._account_id, asset_id, timestamp, settlement, number, qty, price, fee)
#             if bond_interest != 0:
#                 JalDB().add_dividend(DividendSubtype.BondInterest, timestamp, self._account_id, asset_id,
#                                      bond_interest, "НКД", number)
#             cnt += 1
#             row += 1
#         logging.info(g_tr('KIT', "Trades loaded: ") + f"{cnt}")
#
#     def load_cash_transactions(self):
#         cnt = 0
#         columns = {
#             "date": "Дата",
#             "operation": "Тип операции",
#             "amount": "Сумма",
#             "currency": " Валюта",
#             "reason": "Основание",
#             "note": "Примечание",
#             "market": "Секция"
#         }
#         operations = {
#             'Внесение д/с в торг': self.transfer_in,
#             'Вывод дс': self.transfer_out,
#             'Ком бр аб плата спот': self.fee,
#             'Комиссия НРД': self.fee
#         }
#         row, headers = self.find_section_start("Движение денежных средств по неторговым операциям", columns)
#         if row < 0:
#             return False
#         while row < self._statement.shape[0]:
#             if self._statement[0][row] == '':
#                 break
#             operation = self._statement[headers['operation']][row]
#             if operation not in operations:  # not supported type of operation
#                 row += 1
#                 continue
#             timestamp = int(self._statement[headers['date']][row].replace(tzinfo=timezone.utc).timestamp())
#             amount = self._statement[headers['amount']][row]
#             reason = self._statement[headers['reason']][row]
#             description = self._statement[headers['note']][row]
#             operations[operation](timestamp, amount, reason, description)
#             cnt += 1
#             row += 1
#         logging.info(g_tr('KIT', "Cash operations loaded: ") + f"{cnt}")
#
#     def transfer_in(self, timestamp, amount, reason, note):
#         currency_name = JalDB().get_asset_name(JalDB().get_account_currency(self._account_id))
#         text = g_tr('KIT', "Deposit of ") + f"{amount:.2f} {currency_name} " + \
#                f"@{datetime.utcfromtimestamp(timestamp).strftime('%d.%m.%Y')}\n" + \
#                g_tr('KIT', "Select account to withdraw from:")
#         pair_account = self._parent.selectAccount(text, self._account_id)
#         if pair_account == 0:
#             return
#         description = reason + ", " + note
#         JalDB().add_transfer(timestamp, pair_account, amount, self._account_id, amount, 0, 0, description)
#
#     def transfer_out(self, timestamp, amount, reason, note):
#         currency_name = JalDB().get_asset_name(JalDB().get_account_currency(self._account_id))
#         text = g_tr('KIT', "Withdrawal of ") + f"{-amount:.2f} {currency_name} " + \
#                f"@{datetime.utcfromtimestamp(timestamp).strftime('%d.%m.%Y')}\n" + \
#                g_tr('KIT', "Select account to deposit to:")
#         pair_account = self._parent.selectAccount(text, self._account_id)
#         if pair_account == 0:
#             return
#         description = reason + ", " + note                # amount is negative in XLSX file
#         JalDB().add_transfer(timestamp, self._account_id, -amount, pair_account, -amount, 0, 0, description)
#
#     def fee(self, timestamp, amount, _reason, description):
#         JalDB().add_cash_transaction(self._account_id, self._parent.getAccountBank(self._account_id),
#                                      timestamp, amount, PredefinedCategory.Fees, description)
