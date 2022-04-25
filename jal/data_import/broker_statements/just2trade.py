import logging

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
            if self._statement[headers['symbol']][row]:
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
        pass

    def _load_cash_transactions(self):
        pass
