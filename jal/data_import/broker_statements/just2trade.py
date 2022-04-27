import logging
from datetime import datetime, timezone

from jal.data_import.statement import FOF
from jal.data_import.statement_xls import StatementXLS

JAL_STATEMENT_CLASS = "StatementJ2T"


# ----------------------------------------------------------------------------------------------------------------------
class StatementJ2T(StatementXLS):
    PeriodPattern = (1, 0, r"Отчет по счету клиента за период с (?P<S>\d\d\.\d\d\.\d\d\d\d) по (?P<E>\d\d\.\d\d\.\d\d\d\d)")
    AccountPattern = (5, 4, r"(?P<ACCOUNT>\S*)\\.*")
    HeaderCol = 1
    money_section = "ДС на конец периода"
    money_columns = {
        "settled_end": "Сумма",
        "bonus": "Бонус",
        "currency": "Валюта"
    }
    asset_section = "Открытые позиции на конец периода"
    asset_columns = {
        "name": "Наименование инструмента",
        "isin": "ISIN",
        "symbol": "Symbol",
        "currency": "Валюта инструмента"
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
            "settlement": "Дата расчетов",
            "asset_name": "Наименование",
            "isin": "ISIN",
            "asset": "Symbol",
            "B/S": "Тип сделки",
            "qty": "Кол-во",
            "fee": "Комиссия брокера в валюте счета",
            "amount": "Итого в валюте счета",
            "fee_ex": "Прочие комиссии в валюте счета"
        }

        row, headers = self.find_section_start("Сделки с Акциями, Паями, Депозитарными расписками ", columns,
                                               header_height=3)
        if row < 0:
            return
        while row < self._statement.shape[0]:
            if self._statement[self.HeaderCol][row] == '':
                break
            try:
                ts_string = self._statement[headers['timestamp']][row]
                timestamp = int(datetime.strptime(ts_string,
                                                  "%d.%m.%Y %H:%M:%S, %Z%z").replace(tzinfo=timezone.utc).timestamp())
            except ValueError:  # Skip 'Итого' and similar lines
                row += 1
                continue
            deal_number = str(self._statement[headers['number']][row])
            asset_id = self.asset_id({'type': FOF.ASSET_STOCK, 'isin': self._statement[headers['isin']][row],
                                      'symbol': self._statement[headers['asset']][row],
                                      'name': self._statement[headers['asset_name']][row],
                                      'currency': self.currency_id('USD')})  # FIXME - replace hardcoded 'USD'
            if self._statement[headers['B/S']][row] == 'Купля':
                qty = self._statement[headers['qty']][row]
            elif self._statement[headers['B/S']][row] == 'Продажа':
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
            "number": "Номер сделки",
            "timestamp": "Дата сделки",
            "settlement": "Дата расчетов",
            "account_currency": "Валюта счета",
            "asset_name": "Description",
            "B/S": "Тип сделки",
            "qty": "Кол-во",
            "fee": "комиссия брокера в валюте счета",
            "amount": "Итого в валюте счета",
            "fee_ex": "Прочие комиссии в валюте счета"
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
        pass
