import logging
import re
from datetime import datetime, timezone

from jal.constants import PredefinedCategory
from jal.data_import.statement import FOF, Statement_ImportError
from jal.data_import.statement_xls import StatementXLS
from jal.db.asset import JalAsset

JAL_STATEMENT_CLASS = "StatementJ2T"


# ----------------------------------------------------------------------------------------------------------------------
class StatementJ2T(StatementXLS):
    PeriodPattern = (1, 0, r"Report by Client Accounts over a Period from (?P<S>\d\d\.\d\d\.\d\d\d\d) to (?P<E>\d\d\.\d\d\.\d\d\d\d)")
    AccountPattern = (5, 6, r"(?P<ACCOUNT>\S*)")
    HeaderCol = 1
    money_section = "Средства, доступные на конец периода"
    money_columns = {
        "settled_end": "Value \(Сумма\)",
        "bonus": "Bonus \(Сумма\)",
        "currency": "Account currency \(Валюта счета\)"
    }
    asset_section = "Открытые позиции на конец периода"
    asset_columns = {
        "name": "Instrument description \(Название инструмента\)",
        "isin": "ISIN",
        "symbol": "Symbol \(Символ\)",
        "currency": "Instrument сurrency \(валюта инструмента\)"
    }

    def __init__(self):
        super().__init__()
        self.name = self.tr("Just2Trade")
        self.icon_name = "j2t.png"
        self.filename_filter = self.tr("Just2Trade statement (*.xlsx)")
        self.asset_withdrawal = []

    def _load_currencies(self):
        pass

    def _load_money(self):
        cnt = 0
        row, headers = self.find_section_start(self.money_section, self.money_columns)
        if row < 0:
            return False
        while row < self._statement.shape[0]:
            if self._statement[self.HeaderCol][row] == '':
                break
            self._update_account_balance(self._statement[headers['currency']][row], 0, 0,
                                         self._statement[headers['settled_end']][row])
            cnt += 1
            row += 1
        logging.info(self.tr("Cash balances loaded: ") + f"{cnt}")

    def _load_assets(self):
        cnt = 0
        row, headers = self.find_section_start(self.asset_section, self.asset_columns)
        if row < 0:
            return False
        while row < self._statement.shape[0]:
            if self._statement[self.HeaderCol][row] == '':
                break
            asset_name = self._statement[headers['name']][row]
            if asset_name.endswith('*'):    # strip ending star if required
                asset_name = asset_name[:-1]
            currency_code = self.currency_id('USD')      # FIXME put account currency here
            if not self._statement[headers['isin']][row]:
                self.asset_id({'type': FOF.ASSET_CRYPTO, 'symbol': asset_name,
                               'name': asset_name, 'currency': currency_code})
            elif self._statement[headers['symbol']][row]:
                self.asset_id({'type': FOF.ASSET_STOCK, 'isin': self._statement[headers['isin']][row],
                               'symbol': self._statement[headers['symbol']][row],
                               'name': asset_name, 'currency': currency_code})
            else:
                self.asset_id({'type': FOF.ASSET_STOCK, 'isin': self._statement[headers['isin']][row],
                               'name': asset_name, 'currency': currency_code, 'search_online': "MOEX"})
            cnt += 1
            row += 1
        logging.info(self.tr("Securities loaded: ") + f"{cnt}")

    def _load_deals(self):
        self._load_stock_deals()
        self._load_crypto_deals()

    def _load_stock_deals(self):
        cnt = 0
        columns = {
            "number": "Номер сделки",
            "timestamp": "Дата сделки",
            "settlement": "дата расчетов",
            "asset_name": "Описание",
            "isin": "ISIN",
            "asset": "Symbol",
            "B/S": "Тип сделки",
            "qty": "Кол-во",
            "fee": "комиссия брокера в валюте счета",
            "amount": "Итого в валюте счета",
            "fee_ex": "прочие комиссии в валюте счета"
        }

        row, headers = self.find_section_start("Сделки с Акциями, Паями, Депозитарными расписками", columns,
                                               header_height=3)
        if row < 0:
            return
        while row < self._statement.shape[0]:
            if self._statement[self.HeaderCol][row] == '':
                break
            try:
                timestamp = int(self._statement[headers['timestamp']][row].replace(tzinfo=timezone.utc).timestamp())
            except ValueError:  # Skip 'Итого' and similar lines
                row += 1
                continue
            deal_number = str(self._statement[headers['number']][row])
            asset_id = self.asset_id({'type': FOF.ASSET_STOCK, 'isin': self._statement[headers['isin']][row],
                                      'symbol': self._statement[headers['asset']][row],
                                      'name': self._statement[headers['asset_name']][row],
                                      'currency': self.currency_id('USD')})  # FIXME - replace hardcoded 'USD'
            if self._statement[headers['B/S']][row].startswith('Купля'):
                qty = self._statement[headers['qty']][row]
            elif self._statement[headers['B/S']][row].startswith('Продажа'):
                qty = -self._statement[headers['qty']][row]
            else:
                row += 1
                logging.warning(self.tr("Unknown trade type: ") + self._statement[headers['B/S']][row])
                continue
            # Collect fees
            fee = self._statement[headers['fee']][row] if self._statement[headers['fee']][row] else 0.0
            if self._statement[headers['fee_ex']][row]:
                fee += self._statement[headers['fee_ex']][row]
            # Calculate price in account currency
            amount = self._statement[headers['amount']][row]
            price = -(amount + fee) / qty
            assert price > 0.0
            # Settlement is stored as date in Excel report file
            settlement = int(self._statement[headers['settlement']][row].replace(tzinfo=timezone.utc).timestamp())
            account_id = self._find_account_id(self._account_number, 'USD')   # FIXME - replace hardcoded 'USD'
            new_id = max([0] + [x['id'] for x in self._data[FOF.TRADES]]) + 1
            trade = {"id": new_id, "number": deal_number, "timestamp": timestamp, "settlement": settlement,
                     "account": account_id, "asset": asset_id, "quantity": qty, "price": price, "fee": fee}
            self._data[FOF.TRADES].append(trade)
            cnt += 1
            row += 1
        logging.info(self.tr("Stock trades loaded: ") + f"{cnt}")

    def _load_crypto_deals(self):
        cnt = 0
        columns = {
            "number": "Trade number \(Номер сделки\)",
            "timestamp": "Trade date \(Дата сделки\)",
            "settlement": "Settle date \(дата расчетов\)",
            "account_currency": "Account currency \(Валюта счета\)",
            "asset_name": "Description",
            "B/S": "Type of Transaction\(Тип сделки\)",
            "qty": "Quantity \(Кол-во\)",
            "fee": "Broker fees in account currency \(комиссия брокера в валюте счета\)",
            "amount": "Net Value in account currency \(Итого в валюте счета\)",
            "fee_ex": "Other fees in account currency \(прочие комиссии в валюте счета\)"
        }

        row, headers = self.find_section_start("Сделки c виртуальными \(крипто\) инструментами", columns,
                                               header_height=3)
        if row < 0:
            return
        while row < self._statement.shape[0]:
            if self._statement[self.HeaderCol][row] == '':
                break
            # Dates are stored as date in Excel report file for crypto deals
            timestamp = int(self._statement[headers['timestamp']][row].replace(tzinfo=timezone.utc).timestamp())
            settlement = int(self._statement[headers['settlement']][row].replace(tzinfo=timezone.utc).timestamp())
            deal_number = str(self._statement[headers['number']][row])
            asset_id = self.asset_id({'type': FOF.ASSET_CRYPTO, 'symbol': self._statement[headers['asset_name']][row],
                                      'name': self._statement[headers['asset_name']][row],
                                      'currency': self.currency_id('USD')})  # FIXME - replace hardcoded 'USD'
            if self._statement[headers['B/S']][row].startswith('Купля'):
                qty = self._statement[headers['qty']][row]
            elif self._statement[headers['B/S']][row].startswith('Продажа'):
                qty = -self._statement[headers['qty']][row]
            else:
                row += 1
                logging.warning(self.tr("Unknown trade type: ") + self._statement[headers['B/S']][row])
                continue
            # Collect fees
            fee = self._statement[headers['fee']][row] if self._statement[headers['fee']][row] else 0.0
            if self._statement[headers['fee_ex']][row]:
                fee += self._statement[headers['fee_ex']][row]
            # Calculate price in account currency
            amount = self._statement[headers['amount']][row]
            price = -(amount + fee) / qty
            assert price > 0.0
            account_id = self._find_account_id(self._account_number, self._statement[headers['account_currency']][row])
            new_id = max([0] + [x['id'] for x in self._data[FOF.TRADES]]) + 1
            trade = {"id": new_id, "number": deal_number, "timestamp": timestamp, "settlement": settlement,
                     "account": account_id, "asset": asset_id, "quantity": qty, "price": price, "fee": fee}
            self._data[FOF.TRADES].append(trade)
            cnt += 1
            row += 1
        logging.info(self.tr("Crypto trades loaded: ") + f"{cnt}")

    def _load_cash_transactions(self):
        self._load_money_table()
        self._load_fees()

    def _load_money_table(self):
        columns = {
            "date": "Дата",
            "type": "Зачисление/списание",
            "amount": "Сумма",
            "description": "Описание",
            "note": "Комментарий"
        }
        operations = {
            '': None,
            'Переоценка': None,
            'Корпоративные действия::Дивиденды': self.dividend,
            'Внешние затраты::Комиссия внешнего брокера::Удержанный налог': None,  # Loaded in 2nd loop later
            'Внешние затраты::Комиссия внешнего депозитария': self.fee,
            'Перевод на ТП': self.transfer_in,
            'Списание c ТП': self.transfer_out,
            'Корпоративные действия::Компенсации': self.skip_warning,
            'Корректировка': self.skip_warning
        }

        start_row, headers = self.find_section_start("Движение денежных средств", columns)
        if start_row < 0:
            return
        cnt = 0
        row = start_row   # Process dividend rows
        while row < self._statement.shape[0]:
            if self._statement[self.HeaderCol][row] == '':
                break
            try:
                timestamp = int(self._statement[headers['date']][row].replace(tzinfo=timezone.utc).timestamp())
            except TypeError:  # Skip 'Итого' and similar lines
                row += 1
                continue
            operation = self._statement[headers['description']][row]
            if operation not in operations:
                raise Statement_ImportError(self.tr("Unsuppported cash transaction ") + f"'{operation}'")
            account_id = self._find_account_id(self._account_number, 'USD')  # FIXME - replace hardcoded 'USD'
            if self._statement[headers['type']][row] == 'IN':
                amount = self._statement[headers['amount']][row]
            elif self._statement[headers['type']][row] == 'OUT':
                amount = -self._statement[headers['amount']][row]
            else:
                raise Statement_ImportError(self.tr("Unknown cash transaction type ") +
                                            f"'{self._statement[headers['type']][row]}'")
            if operations[operation] is not None:
                operations[operation](timestamp, account_id, amount, self._statement[headers['note']][row])
            cnt += 1
            row += 1

        row = start_row  # Process tax rows - should be done separately after all dividends
        while row < self._statement.shape[0]:
            if self._statement[self.HeaderCol][row] == '':
                break
            if self._statement[headers['description']][row] != "Внешние затраты::Комиссия внешнего брокера::Удержанный налог":
                row += 1
                continue
            assert self._statement[headers['type']][row] == 'OUT'  # Should be outgoing flow
            timestamp = int(self._statement[headers['date']][row].replace(tzinfo=timezone.utc).timestamp())
            amount = self._statement[headers['amount']][row]
            self.tax(timestamp, amount, self._statement[headers['note']][row])
            cnt += 1
            row += 1
        logging.info(self.tr("Cash operations loaded: ") + f"{cnt}")

    # Locate asset by its full name either in loaded JSON data (first) or in JAL database (next)
    def _find_asset_by_name(self, asset_name) -> int:
        candidates = [x for x in self._data[FOF.ASSETS] if 'name' in x and x['name'] == asset_name]
        if len(candidates) == 1:
            return candidates[0]["id"]
        asset_id = JalAsset(data={'name': asset_name}, search=True, create=False).id()
        return -asset_id  # Negative value to indicate that asset was found in db

    # This method finds dividend with given parameters in already loaded JSON data
    def _locate_dividend(self, asset_id, timestamp, ex_date):
        for dividend in self._data[FOF.ASSET_PAYMENTS]:
            if dividend['type'] == FOF.PAYMENT_DIVIDEND and dividend['timestamp'] == timestamp and \
                    dividend['ex_date'] == ex_date and dividend['asset'] == asset_id:
                return dividend
        return None

    def _load_fees(self):
        cnt = 0
        columns = {
            "date": "Дата",
            "amount": "Сумма",
            "currency": "Валюта",
            "note": "Комментарий"
        }
        row, headers = self.find_section_start("Брокерская комиссия, удержанная за период", columns)
        if row < 0:
            return
        while row < self._statement.shape[0]:
            if self._statement[self.HeaderCol][row] == '':
                break
            try:
                timestamp = int(self._statement[headers['date']][row].replace(tzinfo=timezone.utc).timestamp())
            except TypeError:
                break   # Stop processing if we encounter invalid date (supposed to be "Итого:" line)
            account_id = self._find_account_id(self._account_number, self._statement[headers['currency']][row])
            self.fee(timestamp, account_id, -self._statement[headers['amount']][row],
                     self._statement[headers['note']][row])
            cnt += 1
            row += 1

    def dividend(self, timestamp, account_id, amount, note):
        DividendPattern = r"Дивиденды;\s+(Начисление дивидендов полученных по счету.*\.\s+)?Инструмент\s+(?P<asset>.*);\s+Дата отсечки\s+(?P<date>.*)"
        parts = re.match(DividendPattern, note, re.IGNORECASE)  # FIXME - below code used in ibkr.py as well
        if parts is None:
            raise Statement_ImportError(self.tr("Can't parse Dividend description ") + f"'{note}'")
        dividend = parts.groupdict()
        if len(dividend) != DividendPattern.count("(?P<"):  # check that expected number of groups was matched
            raise Statement_ImportError(self.tr("Dividend description miss some data ") + f"'{note}'")
        asset_id = self._find_asset_by_name(dividend['asset'])
        ex_date = int(datetime.strptime(dividend['date'], "%d/%m/%Y").replace(tzinfo=timezone.utc).timestamp())
        new_id = max([0] + [x['id'] for x in self._data[FOF.ASSET_PAYMENTS]]) + 1
        payment = {"id": new_id, "type": FOF.PAYMENT_DIVIDEND, "account": account_id, "timestamp": timestamp,
                   "ex_date": ex_date, "asset": asset_id, "amount": amount, "description": note}
        self._data[FOF.ASSET_PAYMENTS].append(payment)

    def tax(self, timestamp, amount, note):
        TaxPattern = r"Налог на дивиденды;\s+(Начисление дивидендов полученных по счету.*\.\s+)?Инструмент\s+(?P<asset>.*);\s+Дата отсечки\s+(?P<date>.*)"
        parts = re.match(TaxPattern, note, re.IGNORECASE)  # FIXME - below code used in ibkr.py as well
        if parts is None:
            raise Statement_ImportError(self.tr("Can't parse Dividend description ") + f"'{note}'")
        tax = parts.groupdict()
        if len(tax) != TaxPattern.count("(?P<"):  # check that expected number of groups was matched
            raise Statement_ImportError(self.tr("Dividend description miss some data ") + f"'{note}'")
        asset_id = self._find_asset_by_name(tax['asset'])
        ex_date = int(datetime.strptime(tax['date'], "%d/%m/%Y").replace(tzinfo=timezone.utc).timestamp())
        dividend_record = self._locate_dividend(asset_id, timestamp, ex_date)
        if dividend_record is None:
            raise Statement_ImportError(self.tr("Dividend for tax was not found ") + f"'{note}'")
        else:
            dividend_record['tax'] = amount

    def fee(self, timestamp, account_id, amount, note):
        new_id = max([0] + [x['id'] for x in self._data[FOF.INCOME_SPENDING]]) + 1
        fee = {"id": new_id, "timestamp": timestamp, "account": account_id, "peer": 0,
               "lines": [{"amount": amount, "category": -PredefinedCategory.Fees, "description": note}]}
        self._data[FOF.INCOME_SPENDING].append(fee)

    def transfer_in(self, timestamp, account_id, amount, note):
        account = [x for x in self._data[FOF.ACCOUNTS] if x["id"] == account_id][0]
        new_id = max([0] + [x['id'] for x in self._data[FOF.TRANSFERS]]) + 1
        transfer = {"id": new_id, "account": [0, account_id, 0],
                    "asset": [account['currency'], account['currency']], "timestamp": timestamp,
                    "withdrawal": amount, "deposit": amount, "fee": 0.0, "description": note}
        self._data[FOF.TRANSFERS].append(transfer)

    def transfer_out(self, timestamp, account_id, amount, note):
        account = [x for x in self._data[FOF.ACCOUNTS] if x["id"] == account_id][0]
        new_id = max([0] + [x['id'] for x in self._data[FOF.TRANSFERS]]) + 1
        transfer = {"id": new_id, "account": [account_id, 0, 0],
                    "asset": [account['currency'], account['currency']], "timestamp": timestamp,
                    "withdrawal": -amount, "deposit": -amount, "fee": 0.0, "description": note}
        self._data[FOF.TRANSFERS].append(transfer)

    def skip_warning(self, _timestamp, _account_id, amount, note):
        logging.warning(self.tr("Import skipped of transaction: ") + f"'{note}' ({amount})")
