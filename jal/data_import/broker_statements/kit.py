import logging
from datetime import datetime, timezone, timedelta

from jal.constants import Setup, PredefinedCategory
from jal.data_import.statement import FOF, Statement_ImportError
from jal.data_import.statement_xls import StatementXLS

JAL_STATEMENT_CLASS = "StatementKIT"


# ----------------------------------------------------------------------------------------------------------------------
class StatementKIT(StatementXLS):
    Header = (4, 0, "КИТ Финанс (АО)")
    PeriodPattern = (5, 8, r"(?P<S>\d\d\.\d\d\.\d\d\d\d)\s.\s(?P<E>\d\d\.\d\d\.\d\d\d\d)")
    AccountPattern = (5, 5, r"(?P<ACCOUNT>.*)-(.*)")
    SummaryHeader = "Состояние денежных средств на счете"

    asset_section = "Состояние портфеля ценных бумаг"
    asset_columns = {
        "name": "Наименование\nЦБ ",
        "isin": "ISIN",
        "reg_number": "Код гос. регистрации"
    }

    def __init__(self):
        super().__init__()
        self.name = self.tr("KIT Finance")
        self.icon_name = "kit.png"
        self.filename_filter = self.tr("KIT Finance statement (*.xlsx)")

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
            try:
                code = self.currency_id(self.currency_substitutions[self._statement[headers['currency']][row]])
            except KeyError:
                code = self.currency_id(self._statement[headers['currency']][row])
            asset_id = self.asset_id({'isin': self._statement[headers['isin']][row],
                                      'currency': code, 'search_online': "MOEX"})
            if self._statement[headers['B/S']][row] == 'Покупка':
                amount = -self._statement[headers['amount']][row]
                qty = self._statement[headers['qty']][row]
                bond_interest = -self._statement[headers['accrued_int']][row]
            elif self._statement[headers['B/S']][row] == 'Продажа':
                amount = self._statement[headers['amount']][row]
                qty = self._statement[headers['qty']][row]
                bond_interest = self._statement[headers['accrued_int']][row]
            else:
                row += 1
                logging.warning(self.tr("Unknown trade type: ") + self._statement[headers['B/S']][row])
                continue
            price = self._statement[headers['price']][row]
            fee = round(abs(self._statement[headers['fee_ex']][row] + self._statement[headers['fee_broker']][row]), 8)
            if abs(abs(price * qty) - amount) >= self.RU_PRICE_TOLERANCE:
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
        logging.info(self.tr("Trades loaded: ") + f"{cnt}")

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
            'Комиссия НРД': self.fee,
            'Delta-long': self.fee,
            '% по займу ЦБ': self.interest,
            'Налог с див.доход ФЛ': self.tax
        }
        row, headers = self.find_section_start("Движение денежных средств по неторговым операциям", columns)
        if row < 0:
            return False
        while row < self._statement.shape[0]:
            if self._statement[0][row] == '':
                break
            operation = self._statement[headers['operation']][row]
            if operation not in operations:  # not supported type of operation
                raise Statement_ImportError(self.tr("Unsuppported cash transaction ") + f"'{operation}'")
            timestamp = int(self._statement[headers['date']][row].replace(tzinfo=timezone.utc).timestamp())
            account_id = self._find_account_id(self._account_number, self._statement[headers['currency']][row])
            amount = self._statement[headers['amount']][row]
            reason = self._statement[headers['reason']][row]
            description = self._statement[headers['note']][row]
            operations[operation](timestamp, account_id, amount, reason, description)
            cnt += 1
            row += 1
        logging.info(self.tr("Cash operations loaded: ") + f"{cnt}")

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
        fee = {"id": new_id, "timestamp": timestamp, "account": account_id, "peer": 0,
               "lines": [{"amount": amount, "category": -PredefinedCategory.Fees, "description": description}]}
        self._data[FOF.INCOME_SPENDING].append(fee)

    def interest(self, timestamp, account_id, amount, _reason, description):
        new_id = max([0] + [x['id'] for x in self._data[FOF.INCOME_SPENDING]]) + 1
        interest = {"id": new_id, "timestamp": timestamp, "account": account_id, "peer": 0,
                    "lines": [{"amount": amount, "category": -PredefinedCategory.Interest, "description": description}]}
        self._data[FOF.INCOME_SPENDING].append(interest)

    def tax(self, timestamp, account_id, amount, _reason, description):
        logging.info(self.tr("Dividend taxes are not supported for KIT broker statements yet"))
