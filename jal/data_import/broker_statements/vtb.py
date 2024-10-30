import logging
import re
from datetime import timezone
from jal.data_import.statement_xls import StatementXLS
from jal.data_import.statement import FOF, Statement_ImportError


JAL_STATEMENT_CLASS = "StatementVTB"

MAX_T_DELTA = 3  # Maximum allowed days between bond maturity and money transfer

# ----------------------------------------------------------------------------------------------------------------------
class StatementVTB(StatementXLS):
    AccountPattern = None  # to be set during validation
    PeriodPattern = None  # to be set during validation
    HeaderCol = 1
    money_section = "^Отчет об остатках денежных средств"
    money_columns = {
        "name": "Валюта",
        "cash_end": "Плановый",
    }
    asset_section = "^Отчет об остатках ценных бумаг"
    asset_columns = {
        "name": "Наименование ценной бумаги, \n№ гос. регистрации, ISIN",
        "currency": r"Валюта цены \n\(номинала для облигаций\)"
    }

    def __init__(self):
        super().__init__()
        self.name = self.tr("VTB Investments")
        self.icon_name = "vtb.ico"
        self.filename_filter = self.tr("VTB statement (*.xlsx)")
        self.account_end_balance = {}
        self.asset_withdrawal = []

    def _validate(self):
        shift = 0   # Check how header is shifted to the right
        for i in range(self._statement.shape[1]):
            if self._statement[i][4].startswith("Клиент"):  # Starting cell is found
                shift = 1
                continue
            if self._statement[i][4].startswith("ИНН"):   # Next header reached - something went wrong
                shift = 0
                break
            if not shift:
                continue
            if self._statement[i][4]:  # Client name found - we may break here
                break
            shift += 1
        if not shift:
            raise Statement_ImportError(self.tr("Can't determine VTB statement header format"))
        shift = shift - 6
        self.AccountPattern = (7 + shift, 7, None)
        self.PeriodPattern = (5 + shift, 1, r"Отчет Банка ВТБ \(ПАО\) за период с (?P<S>\d\d\.\d\d\.\d\d\d\d) по (?P<E>\d\d\.\d\d\.\d\d\d\d) о сделках, .*")
        super()._validate()

    def _strip_unused_data(self):
        for asset in self._data[FOF.ASSETS]:
            self.drop_extra_fields(asset, ['broker_name'])

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
            return
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
                                      'currency': self.currency_id(currency_code), 'search_offline': True,
                                      'search_online': "MOEX"})
            asset = self._find_in_list(self._data[FOF.ASSETS], 'id', asset_id)
            asset['broker_name'] = asset_name
            cnt += 1
            row += 1
        logging.info(self.tr("Securities loaded: ") + f"{cnt}")

    def _strip_unused_data(self):
        for asset in self._data[FOF.ASSETS]:
            self.drop_extra_fields(asset, ['broker_name'])

    def _load_deals(self):
        self._load_deals_main_market()
        self._load_deals_derivatives_market()

    def _load_deals_main_market(self):
        cnt = 0
        columns = {
            "asset_name": r"Наименование ценной бумаги, \n№ гос\. Регистрации, ISIN",
            "number": "№ сделки",
            "datetime": "Дата и время заключения сделки",
            "B/S": "Вид сделки",
            "price": r"Цена\n\(% для облигаций\)",
            "currency": r"Валюта цены\n \(номинала для облигаций\)",
            "qty": r"Количество \n\(шт\)",
            "amount": r"Сумма сделки в валюте расчетов\n \(с учетом НКД для облигаций\)  ",
            "accrued_int": "НКД\nпо сделке в валюте расчетов",
            "settlement": " Плановая дата поставки",
            "fee1": "Комиссия Банка за расчет по сделке",
            "fee2": "Комиссия Банка за заключение сделки"
        }
        row, headers = self.find_section_start(r"^Заключенные в отчетном периоде сделки с ценными бумагами", columns)
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

    def _load_deals_derivatives_market(self):
        cnt = 0
        columns = {
            "symbol": " Фьючерсный контракт / опцион, код",
            "number": "№ сделки",
            "datetime": "Дата и время заключения сделки",
            "B/S": "Вид сделки",
            "price": r"Цена контракта /\n размер премии \n\(пункты\)",
            "qty": r"Количество \n\(шт\)",
            "fee1": "Комиссия Банка за расчет по сделке",
            "fee2": "Комиссия Банка за заключение сделки"
        }
        row, headers = self.find_section_start(r"^Сделки с Производными финансовыми инструментами в отчетном периоде", columns)
        if row < 0:
            return
        while row < self._statement.shape[0]:
            if self._statement[self.HeaderCol][row] == '':
                break
            asset_id = self.asset_id({'symbol': self._statement[headers['symbol']][row], 'search_online': "MOEX"})
            if self._statement[headers['B/S']][row] == 'Покупка':
                qty = self._statement[headers['qty']][row]
            elif self._statement[headers['B/S']][row] == 'Продажа':
                qty = -self._statement[headers['qty']][row]
            else:
                row += 1
                logging.warning(self.tr("Unknown trade type: ") + self._statement[headers['B/S']][row])
                continue
            deal_number = self._statement[headers['number']][row]
            price = self._statement[headers['price']][row]
            fee = self._statement[headers['fee1']][row] + self._statement[headers['fee2']][row]
            timestamp = int(self._statement[headers['datetime']][row].replace(tzinfo=timezone.utc).timestamp())
            account_id = self._find_account_id(self._account_number, 'RUR')
            new_id = max([0] + [x['id'] for x in self._data[FOF.TRADES]]) + 1
            trade = {"id": new_id, "number": deal_number, "timestamp": timestamp,
                     "account": account_id, "asset": asset_id, "quantity": qty, "price": price, "fee": fee}
            self._data[FOF.TRADES].append(trade)
            cnt += 1
            row += 1
        logging.info(self.tr("Trades loaded: ") + f"{cnt}")

    def _load_asset_transactions(self):
        cnt = 0
        columns = {
            "asset_name": "Наименование ценной бумаги, № гос. Регистрации, ISIN",
            "date": "Дата операции",
            "qty": r"Количество \n\(шт\.\)",
            "type": "Тип операции"
        }
        operations = {
            'Покупка': None,
            'Продажа': None,
            'Погашение ЦБ': self.asset_cancellation,
        }
        row, headers = self.find_section_start("^Движение ценных бумаг", columns)
        if row < 0:
            return False
        while row < self._statement.shape[0]:
            if self._statement[self.HeaderCol][row] == '':  # Stop if there are no next date available
                break
            operation = self._statement[headers['type']][row]
            if operation not in operations:
                raise Statement_ImportError(self.tr("Unsuppported asset transaction ") + f"'{operation}'")
            asset_name = self._statement[headers['asset_name']][row]   # FIXME the same piece of code is in load_deals
            assets = [x for x in self._data[FOF.ASSETS] if x.get('broker_name') == asset_name]
            if len(assets) != 1:
                raise Statement_ImportError(self.tr("No asset match in asset transactions ") + f"'{asset_name}'")
            asset_id = assets[0]['id']
            timestamp = int(self._statement[headers['date']][row].replace(tzinfo=timezone.utc).timestamp())
            try:
                qty = float(self._statement[headers['qty']][row])
            except ValueError:
                raise Statement_ImportError(self.tr("Failed to convert asset amount ") + f"'{self._statement[headers['qty']][row]}'")
            if operations[operation] is not None:
                operations[operation](timestamp, asset_id, qty)
            cnt += 1
            row += 1
        logging.info(self.tr("Asset transactions loaded: ") + f"{cnt}")

    def asset_cancellation(self, timestamp, asset_id, qty):
        # Statement has negative value for cancellation - will be used to create sell trade
        self.asset_withdrawal.append({"timestamp": timestamp, "asset": asset_id, "quantity": qty})

    def _load_cash_transactions(self):
        cnt = 0
        columns = {
            "date": "Дата",
            "type": "Тип операции",
            "amount": "Сумма",
            "currency": "Валюта",
            "description": "Комментарий"
        }
        operations = {
            'Зачисление денежных средств': self.transfer_in,
            'Списание денежных средств': self.transfer_out,
            'Купонный доход': self.interest,
            'Погашение ценных бумаг': self.bond_maturity,
            'Сальдо расчётов по сделкам с ценными бумагами': None,  # These operations are results of trades
            'Вознаграждение Брокера': None,
            'Дивиденды': self.dividend,
            'Сальдо расчётов по сделкам с иностранной валютой': None,  # These operation are results of currency exchange
            'Перевод денежных средств': None,   # TODO - to be implemented
            'Вариационная маржа': None
        }
        row, headers = self.find_section_start("^Движение денежных средств", columns)
        if row < 0:
            return False
        while row < self._statement.shape[0]:
            if self._statement[self.HeaderCol][row] == '':  # Stop if there are no next date available
                break
            operation = self._statement[headers['type']][row]
            if operation == '':  # Skip market header as of now
                row += 1
                continue
            if operation not in operations:
                raise Statement_ImportError(self.tr("Unsuppported cash transaction ") + f"'{operation}'")
            timestamp = int(self._statement[headers['date']][row].replace(tzinfo=timezone.utc).timestamp())
            amount = self._statement[headers['amount']][row]
            description = self._statement[headers['description']][row]
            account_id = self._find_account_id(self._account_number, self._statement[headers['currency']][row])
            if operations[operation] is not None:
                operations[operation](timestamp, account_id, amount, description)
            cnt += 1
            row += 1
        logging.info(self.tr("Cash operations loaded: ") + f"{cnt}")

    def transfer_in(self, timestamp, account_id, amount, description):
        account = [x for x in self._data[FOF.ACCOUNTS] if x["id"] == account_id][0]
        new_id = max([0] + [x['id'] for x in self._data[FOF.TRANSFERS]]) + 1
        transfer = {"id": new_id, "account": [0, account_id, 0],
                    "asset": [account['currency'], account['currency']], "timestamp": timestamp,
                    "withdrawal": amount, "deposit": amount, "fee": 0.0, "description": description}
        self._data[FOF.TRANSFERS].append(transfer)

    def transfer_out(self, timestamp, account_id, amount, description):
        account = [x for x in self._data[FOF.ACCOUNTS] if x["id"] == account_id][0]
        new_id = max([0] + [x['id'] for x in self._data[FOF.TRANSFERS]]) + 1
        transfer = {"id": new_id, "account": [account_id, 0, 0],
                    "asset": [account['currency'], account['currency']], "timestamp": timestamp,
                    "withdrawal": -amount, "deposit": -amount, "fee": 0.0, "description": description}
        self._data[FOF.TRANSFERS].append(transfer)

    def interest(self, timestamp, account_id, amount, description):
        BondInterestPattern = r"^Куп\. дох\. по обл\. .* (?P<reg_number>\S*), \S*\..*$"
        parts = re.match(BondInterestPattern, description, re.IGNORECASE)
        if parts is None:
            raise Statement_ImportError(self.tr("Can't parse bond interest description ") + f"'{description}'")
        interest_data = parts.groupdict()
        asset_id = self._find_in_list(self._data[FOF.ASSETS_DATA], 'reg_number', interest_data['reg_number'])['asset']
        new_id = max([0] + [x['id'] for x in self._data[FOF.ASSET_PAYMENTS]]) + 1
        payment = {"id": new_id, "type": FOF.PAYMENT_INTEREST, "account": account_id, "timestamp": timestamp,
                   "asset": asset_id, "amount": amount, "description": description}
        self._data[FOF.ASSET_PAYMENTS].append(payment)

    def dividend(self, timestamp, account_id, amount, description):
        DividendPattern = r"^Дивиденды .* (?P<reg_number>\S*), .*. Удержан налог в размере (?P<tax>\d+\.\d\d) руб.$"
        parts = re.match(DividendPattern, description, re.IGNORECASE)
        if parts is None:
            raise Statement_ImportError(self.tr("Can't parse dividend description ") + f"'{description}'")
        dividend_data = parts.groupdict()
        asset_id = self._find_in_list(self._data[FOF.ASSETS_DATA], 'reg_number', dividend_data['reg_number'])['asset']
        try:
            tax = float(dividend_data['tax'])
            amount += tax
        except ValueError:
            raise Statement_ImportError(self.tr("Failed to convert dividend tax ") + f"'{description}'")
        new_id = max([0] + [x['id'] for x in self._data[FOF.ASSET_PAYMENTS]]) + 1
        payment = {"id": new_id, "type": FOF.PAYMENT_DIVIDEND, "account": account_id, "timestamp": timestamp,
                   "asset": asset_id, "amount": amount, "tax": tax, "description": description}
        self._data[FOF.ASSET_PAYMENTS].append(payment)

    def bond_maturity(self, timestamp, account_id, amount, description):
        MaturityPattern = r"^Ден\.ср-ва от погаш\. номин\.ст-ти обл\. .* (?P<reg_number>\S*), .* Налог не удерживается\.$"
        parts = re.match(MaturityPattern, description, re.IGNORECASE)
        if parts is None:
            raise Statement_ImportError(self.tr("Can't parse bond maturity description ") + f"'{description}'")
        bond_maturity = parts.groupdict()
        asset_id = self._find_in_list(self._data[FOF.ASSETS_DATA], 'reg_number', bond_maturity['reg_number'])['asset']
        match = [x for x in self.asset_withdrawal if x['asset'] == asset_id and (timestamp - x['timestamp']) <= MAX_T_DELTA*86400]
        if not match:
            breakpoint()
            raise Statement_ImportError(self.tr("Can't find asset cancellation record for ") + f"'{description}'")
        if len(match) != 1:
            raise Statement_ImportError(self.tr("Multiple asset cancellation match for ") + f"'{description}'")
        asset_cancel = match[0]
        qty = asset_cancel['quantity']
        price = abs(amount / qty)  # Price is always positive
        new_id = max([0] + [x['id'] for x in self._data[FOF.TRADES]]) + 1
        trade = {"id": new_id, "timestamp": timestamp, "settlement": timestamp, "account": account_id,
                 "asset": asset_id, "quantity": qty, "price": price, "fee": 0.0, "note": description}
        self._data[FOF.TRADES].append(trade)
