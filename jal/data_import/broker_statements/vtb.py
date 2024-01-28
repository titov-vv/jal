import logging
from jal.data_import.statement_xls import StatementXLS


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

    def __init__(self):
        super().__init__()
        self.name = self.tr("VTB Investments")
        self.icon_name = "vtb.ico"
        self.filename_filter = self.tr("VTB statement (*.xls)")
        self.asset_withdrawal = []

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
            cnt += 1
            row += 1
        logging.info(self.tr("Account currencies loaded: ") + f"{cnt}")

    def _load_deals(self):
        pass

    def _load_cash_transactions(self):
        pass
