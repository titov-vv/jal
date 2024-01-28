import logging
import re
from jal.data_import.statement_xls import StatementXLS
from jal.data_import.statement import FOF, Statement_ImportError


JAL_STATEMENT_CLASS = "StatementVTB"

# ----------------------------------------------------------------------------------------------------------------------
class StatementVTB(StatementXLS):
    PeriodPattern = (7, 1, r"Отчет Банка ВТБ \(ПАО\) за период с (?P<S>\d\d\.\d\d\.\d\d\d\d) по (?P<E>\d\d\.\d\d\.\d\d\d\d) о сделках, .*")
    AccountPattern = (9, 7, None)
    HeaderCol = 1
    money_section = "Отчет об остатках денежных средств"
    money_columns = {
        "name": "Валюта",
        "cash_end": "Плановый",
    }
    asset_section = "Отчет об остатках ценных бумаг"
    asset_columns = {
        "name": "Наименование ценной бумаги, \n№ гос. регистрации, ISIN",
        "currency": "Валюта цены \n\(номинала для облигаций\)"
    }

    def __init__(self):
        super().__init__()
        self.name = self.tr("VTB Investments")
        self.icon_name = "vtb.ico"
        self.filename_filter = self.tr("VTB statement (*.xls)")
        self.account_end_balance = {}

    def _load_currencies(self):
        cnt = 0
        row, headers = self.find_section_start(self.money_section, self.money_columns, header_height=3)
        if row < 0:
            return False
        while row < self._statement.shape[0]:
            if self._statement[self.HeaderCol][row].startswith('Сумма') or self._statement[self.HeaderCol][row] == '':
                break
            currency = self._statement[headers['name']][row]
            try:
                code = self.currency_substitutions[currency]
            except KeyError:
                code = currency
            self.currency_id(code)
            self.account_end_balance[code] = self._statement[headers['cash_end']][row]
            cnt += 1
            row += 1
        logging.info(self.tr("Account currencies loaded: ") + f"{cnt}")

    # Planned money amount already loaded in _load_currencies(). Here it is only put in account data
    def _load_money(self):
        for currency in self.account_end_balance:
            account_id = self._find_account_id(self._account_number, currency)
            account = [x for x in self._data[FOF.ACCOUNTS] if x['id'] == account_id][0]
            account["cash_end"] = self.account_end_balance[currency]

    def _load_assets(self):
        AssetPattern = r"^(?P<name>.*), (?P<reg_number>.*), (?P<isin>.*)$"
        cnt = 0
        asset_type = ''
        row, headers = self.find_section_start(self.asset_section, self.asset_columns)
        if row < 0:
            return False
        while row < self._statement.shape[0]:
            if self._statement[self.HeaderCol][row].startswith('ИТОГО') or self._statement[self.HeaderCol][row] == '':
                break
            asset_name = self._statement[headers['name']][row]
            parts = re.match(AssetPattern, asset_name, re.IGNORECASE)
            if parts is None:
                asset_type = asset_name
                row += 1
                continue
            asset_data = parts.groupdict()
            if len(asset_data) != AssetPattern.count("(?P<"):  # check that expected number of groups was matched
                raise Statement_ImportError(self.tr("Asset name miss some data ") + f"'{asset_name}'")
            currency = self._statement[headers['currency']][row]
            try:
                currency_code = self.currency_substitutions[currency]
            except KeyError:
                currency_code = currency
            _ = self.asset_id({'isin': asset_data['isin'], 'reg_number': asset_data['reg_number'],
                               'currency': currency_code, 'search_offline': True, 'search_online': "MOEX"})
            cnt += 1
            row += 1
        logging.info(self.tr("Securities loaded: ") + f"{cnt}")

    def _load_deals(self):
        pass

    def _load_cash_transactions(self):
        pass
