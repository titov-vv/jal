import logging
import re
from datetime import timezone
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
        row, headers = self.find_section_start(self.asset_section, self.asset_columns)
        if row < 0:
            return False
        while row < self._statement.shape[0]:
            if self._statement[self.HeaderCol][row].startswith('ИТОГО') or self._statement[self.HeaderCol][row] == '':
                break
            if self._statement[self.HeaderCol][row].startswith(('АКЦИЯ', 'ОБЛИГАЦИЯ', 'ПАЙ')):
                row += 1  # This is an asset class separator - move to the next row
                continue
            asset_name = self._statement[headers['name']][row]
            parts = re.match(AssetPattern, asset_name, re.IGNORECASE)
            if parts is None:
                raise Statement_ImportError(self.tr("Can't parse asset name ") + f"'{asset_name}'")
            asset_data = parts.groupdict()
            if len(asset_data) != AssetPattern.count("(?P<"):  # check that expected number of groups was matched
                raise Statement_ImportError(self.tr("Asset name miss some data ") + f"'{asset_name}'")
            currency = self._statement[headers['currency']][row]
            try:
                currency_code = self.currency_substitutions[currency]
            except KeyError:
                currency_code = currency
            asset_id = self.asset_id({'isin': asset_data['isin'], 'reg_number': asset_data['reg_number'],
                                      'currency': currency_code, 'search_offline': True, 'search_online': "MOEX"})
            asset = self._find_in_list(self._data[FOF.ASSETS], 'id', asset_id)
            asset['broker_name'] = asset_name
            cnt += 1
            row += 1
        logging.info(self.tr("Securities loaded: ") + f"{cnt}")

    def _strip_unused_data(self):
        for asset in self._data[FOF.ASSETS]:
            self.drop_extra_fields(asset, ['broker_name'])

    def _load_deals(self):
        cnt = 0
        columns = {
            "asset_name": "Наименование ценной бумаги, \n№ гос\. Регистрации, ISIN",
            "number": "№ сделки",
            "datetime": "Дата и время заключения сделки",
            "B/S": "Вид сделки",
            "price": "Цена\n\(% для облигаций\)",
            "currency": "Валюта цены\n \(номинала для облигаций\)",
            "qty": "Количество \n\(шт\)",
            "amount": "Сумма сделки в валюте расчетов\n \(с учетом НКД для облигаций\)  ",
            "accrued_int": "НКД\nпо сделке в валюте расчетов",
            "settlement": " Плановая дата поставки",
            "fee1": "Комиссия Банка за расчет по сделке",
            "fee2": "Комиссия Банка за заключение сделки"
        }
        row, headers = self.find_section_start("Заключенные в отчетном периоде сделки с ценными бумагами", columns)
        if row < 0:
            return
        while row < self._statement.shape[0]:
            if self._statement[self.HeaderCol][row] == '':
                break
            asset_name = self._statement[headers['asset_name']][row]
            assets = [x for x in self._data[FOF.ASSETS] if x.get('broker_name') == asset_name]
            if len(assets) != 1:
                raise Statement_ImportError(self.tr("No asset match in deals for ") + f"'{asset_name}'")
            asset_id = assets[0]['id']
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
            deal_number = self._statement[headers['number']][row]
            price = self._statement[headers['price']][row]
            currency = self._statement[headers['currency']][row]
            fee = self._statement[headers['fee1']][row] + self._statement[headers['fee2']][row]
            amount = self._statement[headers['amount']][row]
            if abs(abs(price * qty) - amount) >= self.RU_PRICE_TOLERANCE:
                price = abs(amount / qty)
            timestamp = int(self._statement[headers['datetime']][row].replace(tzinfo=timezone.utc).timestamp())
            settlement = int(self._statement[headers['settlement']][row].replace(tzinfo=timezone.utc).timestamp())
            account_id = self._find_account_id(self._account_number, currency)
            new_id = max([0] + [x['id'] for x in self._data[FOF.TRADES]]) + 1
            trade = {"id": new_id, "number": deal_number, "timestamp": timestamp, "settlement": settlement,
                     "account": account_id, "asset": asset_id, "quantity": qty, "price": price, "fee": fee}
            self._data[FOF.TRADES].append(trade)
            if bond_interest != 0:
                new_id = max([0] + [x['id'] for x in self._data[FOF.ASSET_PAYMENTS]]) + 1
                payment = {"id": new_id, "type": FOF.PAYMENT_INTEREST, "account": account_id, "timestamp": timestamp,
                           "number": deal_number, "asset": asset_id, "amount": bond_interest, "description": "НКД"}
                self._data[FOF.ASSET_PAYMENTS].append(payment)
            cnt += 1
            row += 1
        logging.info(self.tr("Trades loaded: ") + f"{cnt}")

    def _load_cash_transactions(self):
        pass
