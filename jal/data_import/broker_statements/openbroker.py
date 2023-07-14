import logging
import re
import difflib
from datetime import datetime

from PySide6.QtWidgets import QApplication
from jal.constants import PredefinedCategory, PredefinedAsset
from jal.db.asset import JalAsset
from jal.data_import.statement import FOF, Statement_ImportError
from jal.data_import.statement_xml import StatementXML
from jal.net.downloader import QuoteDownloader
from jal.widgets.helpers import dt2ts

JAL_STATEMENT_CLASS = "StatementOpenBroker"


# ----------------------------------------------------------------------------------------------------------------------
class OpenBroker_AssetType:
    NotSupported = -1
    _asset_types = {
        '': -1,
        'Денежные средства': FOF.ASSET_MONEY,
        'Акции': FOF.ASSET_STOCK,
        'Облигации': FOF.ASSET_BOND,
        'ADR': FOF.ASSET_ADR
    }

    def __init__(self, asset_type):
        self.type = self.NotSupported
        try:
            self.type = self._asset_types[asset_type]
        except KeyError:
            logging.warning(QApplication.translate("OpenBroker", "Asset type isn't supported: ") + f"'{asset_type}'")


# ----------------------------------------------------------------------------------------------------------------------
class OpenBroker_Asset:
    pass


class OpenBroker_BrokerAsset:
    pass


# ----------------------------------------------------------------------------------------------------------------------
class OpenBroker_Currency:
    pass


# ----------------------------------------------------------------------------------------------------------------------
class OpenBroker_Exchange:
    _exchange_types = {
        '': '',
        "ПАО Московская биржа": "MOEX"
    }

    def __init__(self, exchange):
        self.name = ''
        try:
            self.name = self._exchange_types[exchange]
        except KeyError:
            logging.warning(QApplication.translate("OpenBroker", "Exchange isn't supported: ") + f"'{exchange}'")


# ----------------------------------------------------------------------------------------------------------------------
class StatementOpenBroker(StatementXML):
    statements_path = '.'
    statement_tag = 'broker_report'
    level_tag = 'asset_type_id'

    def __init__(self):
        super().__init__()
        self.name = self.tr("Open Broker")
        self.icon_name = "openbroker.ico"
        self.filename_filter = self.tr("Open Broker statement (*.xml)")

        self._account_number = ''
        self.asset_withdrawal = []
        open_loaders = {
            OpenBroker_AssetType: self.attr_asset_type,
            OpenBroker_Asset: self.attr_asset,
            OpenBroker_BrokerAsset: self.attr_broker_asset,
            OpenBroker_Currency: self.attr_currency,
            OpenBroker_Exchange: self.attr_exchange
        }
        self.attr_loader.update(open_loaders)
        self._sections = {
            StatementXML.STATEMENT_ROOT:
                {
                    'tag': self.statement_tag,
                    'level': '',
                    'values': [('client_code', 'account', str, None),
                               ('date_from', 'period_start', datetime, None),
                               ('date_to', 'period_end', datetime, None)],
                    'loader': self.load_header
                },
            'spot_portfolio_security_params':   # Section that describes assets present in the statement
                {
                    'tag': 'item',
                    'level': '',
                    'values': [('ticker', 'symbol', str, None),
                               ('security_type', 'type', OpenBroker_AssetType, OpenBroker_AssetType.NotSupported),
                               ('security_name', 'name', str, None),
                               ('isin', 'isin', str, ''),
                               ('security_grn_code', 'reg_number', str, ''),
                               ('nominal_curr', 'currency', OpenBroker_Currency, None),
                               ('board_name', 'exchange', OpenBroker_Exchange, '')],
                    'loader': self.load_assets
                },
            'spot_assets':    # Section describes end balances of account
                {
                    'tag': 'item',
                    'level': '2',   # Take only money
                    'values': [('asset_name', 'asset', OpenBroker_Asset, None),
                               ('opening_position_plan', 'cash_begin', float, 0),
                               ('closing_position_plan', 'cash_end', float, 0),           # -- this is planned
                               ('closing_position_fact', 'cash_end_settled', float, 0)],  # -- this is now
                    'loader': self.load_balances
                },
            'spot_main_deals_conclusion':    # Deals list
                {
                    'tag': 'item',
                    'level': '',
                    'values': [('security_name', 'asset', OpenBroker_Asset, None),
                               ('accounting_currency_code', 'currency', OpenBroker_Currency, None),
                               ('conclusion_time', 'timestamp', datetime, None),
                               ('execution_date', 'settlement', datetime, 0),
                               ('price', 'price', float, None),
                               ('buy_qnty', 'quantity_buy', float, -1),
                               ('sell_qnty', 'quantity_sell', float, -1),
                               ('volume_currency', 'proceeds', float, None),
                               ('broker_commission', 'fee', float, None),
                               ('deal_no', 'number', str, ''),
                               ('nkd', 'accrued_interest', float, 0)],
                    'loader': self.load_trades
                },
            'spot_non_trade_security_operations':    # this section should come before 'spot_non_trade_money_operations'
                {
                    'tag': 'item',
                    'level': '',
                    'values': [('operation_date', 'timestamp', datetime, None),
                               ('security_name', 'asset', OpenBroker_BrokerAsset, None),
                               ('quantity', 'quantity', float, None),
                               ('comment', 'description', str, '')],
                    'loader': self.load_asset_operations
                },
            'spot_non_trade_money_operations':
                {
                    'tag': 'item',
                    'level': '',
                    'values': [('operation_date', 'timestamp', datetime, None),
                               ('currency_code', 'currency', OpenBroker_Currency, None),
                               ('amount', 'amount', float, None),
                               ('comment', 'description', str, '')],
                    'loader': self.load_cash_operations
                },
            'spot_loan_deals_executed':
                {
                    'tag': 'item',
                    'level': '',
                    'values': [('operation_date', 'timestamp', datetime, None),
                               ('operation_number', 'number', str, ''),
                               ('instrument', 'ticker', str, None),
                               ('loan_return_qty', 'qty', float, None),
                               ('currency', 'currency', OpenBroker_Currency, None),
                               ('profit', 'profit', float, None),
                               ('brokers_fee', 'fee', float, None)],
                    'loader': self.load_loans
                }
        }

    def validate_file_header_attributes(self, attributes):
        if 'title' not in attributes:
            raise Statement_ImportError(self.tr("Open broker report title not found"))
        if not attributes['title'].startswith("Отчет АО «Открытие Брокер»"):
            raise Statement_ImportError(self.tr("Unexpected Open broker report header: ") + f"{attributes['title']}")

    # Convert attribute 'attr_name' value into json open-format asset type
    @staticmethod
    def attr_asset_type(xml_element, attr_name, default_value):
        if attr_name not in xml_element.attrib:
            return default_value
        return OpenBroker_AssetType(xml_element.attrib[attr_name]).type

    def attr_asset(self, xml_element, attr_name, default_value):
        if attr_name not in xml_element.attrib:
            return default_value
        asset_category = self.attr_asset_type(xml_element, 'asset_type', None)  # only for 'spot_assets'
        asset_data = {'type': asset_category}
        if asset_category == FOF.ASSET_MONEY:
            asset_data['symbol'] = xml_element.attrib['asset_code'].strip()
        else:
            if 'price_currency' in xml_element.attrib:
                asset_data['currency'] = self.currency_id(xml_element.attrib['price_currency'])
            elif 'price_currency_code' in xml_element.attrib:
                asset_data['currency'] = self.currency_id(xml_element.attrib['price_currency_code'])
            asset_data['symbol'] = xml_element.attrib[attr_name].strip()
            if xml_element.getparent().tag == 'spot_assets':   # need to check in which group we are now
                asset_data['reg_number'] = xml_element.attrib['asset_code'] if 'asset_code' in xml_element.attrib else ''
            else:
                asset_data['reg_number'] = xml_element.attrib['security_grn_code'] if 'security_grn_code' in xml_element.attrib else ''
        asset_id = self.asset_id(asset_data)
        return asset_id

    def attr_broker_asset(self, xml_element, attr_name, default_value):
        if attr_name not in xml_element.attrib:
            return default_value
        broker_name = xml_element.attrib[attr_name].strip()
        match = [x for x in self._data[FOF.SYMBOLS] if x['symbol'] == broker_name and "broker_symbol" in x]
        if match:
            if len(match) == 1:
                return match[0]['asset']
            else:
                raise Statement_ImportError(self.tr("Multiple match for broker symbol: ") + f"'{broker_name}'")
        # if not found via broker symbols then search through normal symbols
        match = [x for x in self._data[FOF.SYMBOLS] if x['symbol'] == broker_name]
        if match:
            if len(match) == 1:
                return match[0]['asset']
            else:
                raise Statement_ImportError(self.tr("Multiple match for symbol: ") + f"'{broker_name}'")

    # convert 'attr_name' currency code value into asset_id
    def attr_currency(self, xml_element, attr_name, default_value):
        if attr_name not in xml_element.attrib:
            if xml_element.getparent().tag == 'spot_portfolio_security_params':
                return self.currency_id("RUB")  # Currency might be missed for ADRs for example - let it be RUB
            return default_value
        currency_id = self.currency_id(xml_element.attrib[attr_name])
        if currency_id is None:
            return default_value
        else:
            return currency_id

    # Convert attribute 'attr_name' value into json open-format exchange name
    @staticmethod
    def attr_exchange(xml_element, attr_name, default_value):
        if attr_name not in xml_element.attrib:
            return default_value
        return OpenBroker_Exchange(xml_element.attrib[attr_name]).name

    def account_by_currency(self, currency_id):
        match = [x for x in self._data[FOF.ACCOUNTS] if
                 x['number'] == self._account_number and x['currency'] == currency_id]
        if match and len(match) == 1:
            return match[0]['id']
        else:
            return 0

    def load_header(self, header):
        self._data[FOF.PERIOD][0] = header['period_start']
        self._data[FOF.PERIOD][1] = self._end_of_date(header['period_end'])
        self._account_number = header['account']
        logging.info(self.tr("Load Open Broker statement for account ") +
                     f"{self._account_number}: {datetime.utcfromtimestamp(header['period_start']).strftime('%Y-%m-%d')}"
                     + f" - {datetime.utcfromtimestamp(header['period_end']).strftime('%Y-%m-%d')}")

    def load_assets(self, assets):
        cnt = 0
        for asset in assets:
            broker_symbol = asset['name'] if 'name' in asset else ''
            if asset['type'] == OpenBroker_AssetType.NotSupported:   # Skip not supported type of asset
                continue
            if asset['exchange'] == "MOEX":
                asset_info = QuoteDownloader.MOEX_info(symbol=asset['symbol'], isin=asset['isin'],
                                                       regnumber=asset['reg_number'])
                if asset_info:
                    asset.update(asset_info)
                    asset['type'] = FOF.convert_predefined_asset_type(asset['type'])
            if asset['exchange'] != '':  # don't store empty exchange
                asset['note'] = asset['exchange']
            asset.pop('exchange')
            asset_id = self.asset_id(asset)
            if broker_symbol:
                if not [x['id'] for x in self._data[FOF.SYMBOLS] if x['symbol'] == broker_symbol]:
                    symbol_id = max([0] + [x['id'] for x in self._data[FOF.SYMBOLS]]) + 1
                    symbol = {"id": symbol_id, "asset": asset_id, "symbol": broker_symbol,
                              "currency": asset['currency'], "broker_symbol": True}
                    self._data[FOF.SYMBOLS].append(symbol)
            cnt += 1
        logging.info(self.tr("Securities loaded: ") + f"{cnt} ({len(assets)})")

    def load_balances(self, balances):
        cnt = 0
        base = max([0] + [x['id'] for x in self._data[FOF.ACCOUNTS]]) + 1
        for balance in balances:
            asset = [x for x in self._data[FOF.ASSETS] if 'id' in x and x['id'] == balance['asset']][0]
            if asset['type'] == FOF.ASSET_MONEY:
                account = {'id': base+cnt, 'number': self._account_number, 'currency': balance['asset']}
                self.drop_extra_fields(balance, ["asset"])
                account.update(balance)
                self._data[FOF.ACCOUNTS].append(account)
                cnt += 1
        logging.info(self.tr("Accounts loaded: ") + f"{cnt}")

    def load_trades(self, trades):
        cnt = 0
        trade_base = max([0] + [x['id'] for x in self._data[FOF.TRADES]]) + 1
        for i, trade in enumerate(sorted(trades, key=lambda x: x['timestamp'])):
            trade['id'] = trade_base + i
            trade['account'] = self.account_by_currency(trade['currency'])
            if trade['account'] == 0:
                raise Statement_ImportError(self.tr("Can't find account for trade: ") + f"{trade}")
            if trade['quantity_buy'] < 0 and trade['quantity_sell'] < 0:
                raise Statement_ImportError(self.tr("Can't determine trade type/quantity: ") + f"{trade}")
            if trade['quantity_sell'] < 0:
                trade['quantity'] = trade['quantity_buy']
                trade['accrued_interest'] = -trade['accrued_interest']
            else:
                trade['quantity'] = -trade['quantity_sell']
            amount = trade['proceeds'] + trade['accrued_interest']
            if abs(abs(trade['price'] * trade['quantity']) - amount) >= self.RU_PRICE_TOLERANCE:
                trade['price'] = abs(amount / trade['quantity'])
            if abs(trade['accrued_interest']) > 0:
                new_id = max([0] + [x['id'] for x in self._data[FOF.ASSET_PAYMENTS]]) + 1
                payment = {"id": new_id, "type": FOF.PAYMENT_INTEREST, "account": trade['account'],
                           "timestamp": trade['timestamp'], "number": trade['number'], "asset": trade['asset'],
                           "amount": trade['accrued_interest'], "description": "НКД"}
                self._data[FOF.ASSET_PAYMENTS].append(payment)
            self.drop_extra_fields(trade, ["currency", "proceeds", "quantity_buy", "quantity_sell", "accrued_interest"])
            self._data[FOF.TRADES].append(trade)
            cnt += 1

    # this method loads only asset cancellations and puts it in self.asset_withdrawal for use in 'load_cash_operations'
    def load_asset_operations(self, asset_operations):
        for operation in asset_operations:
            if "Снятие ЦБ с учета. Погашение облигаций" in operation['description']:
                self.load_bond_repayment(operation)
            elif "Перевод ЦБ в" in operation['description']:
                self.load_asset_transfer_out(operation)
            else:
                raise Statement_ImportError(self.tr("Unknown non-trade operation: ") + operation['description'])

    def load_bond_repayment(self, operation):
        # Asset name is stored as alternative symbol and in self.asset_withdrawal[]
        bond_repayment_pattern = r"^Отчет депозитария.*от (?P<report_date>\d\d\.\d\d\.\d\d\d\d)\. Снятие ЦБ с учета\. Погашение облигаций - (?P<asset_name>.*)$"
        parts = re.match(bond_repayment_pattern, operation['description'], re.IGNORECASE)
        if parts is None:
            raise Statement_ImportError(
                self.tr("Can't parse bond repayment description ") + f"'{operation['description']}'")
        repayment_note = parts.groupdict()
        if len(repayment_note) != bond_repayment_pattern.count("(?P<"):  # check expected number of matches
            raise Statement_ImportError(
                self.tr("Can't detect bond name from description ") + f"'{repayment_note}'")
        ticker = self._find_in_list(self._data[FOF.SYMBOLS], 'asset', operation['asset'])
        if ticker['symbol'] != repayment_note['asset_name']:  # Store alternative depositary name
            ticker = ticker.copy()
            ticker['id'] = max([0] + [x['id'] for x in self._data[FOF.SYMBOLS]]) + 1
            ticker['symbol'] = repayment_note['asset_name']
            ticker['broker_symbol'] = True
            self._data[FOF.SYMBOLS].append(ticker)
        report_date = dt2ts(datetime.strptime(repayment_note['report_date'], "%d.%m.%Y"))
        new_id = max([0] + [x['id'] for x in self.asset_withdrawal]) + 1
        record = {"id": new_id, "timestamp": operation['timestamp'], "report_date": report_date,
                  "asset": operation['asset'], "symbol": ticker['symbol'],
                  "quantity": operation['quantity'], "note": operation['description']}
        self.asset_withdrawal.append(record)

    def load_asset_transfer_out(self, transfer):
        transfer['id'] = max([0] + [x['id'] for x in self._data[FOF.TRANSFERS]]) + 1
        ruble_id = JalAsset(data={'symbol': 'RUB', 'type_id': PredefinedAsset.Money}, search=True, create=False).id()
        transfer['account'] = [ruble_id, 0, 0]   # Assume russian ruble as default for Open Broker
        transfer['asset'] = [transfer['asset'], transfer['asset']]
        transfer['withdrawal'] = transfer['deposit'] = -transfer['quantity']   # Withdrawal quantity is negative
        transfer['fee'] = 0.0
        self.drop_extra_fields(transfer, ["quantity"])
        self._data[FOF.TRANSFERS].append(transfer)

    def load_cash_operations(self, cash_operations):
        cnt = 0
        operations = {
            'Комиссия Брокера / ': None,              # These data are duplicated in normal trade data
            'Комиссия Брокера за': self.cash_fee,
            'Удержан налог на доход': None,           # Tax information is included into dividend payment data
            'Удержан налог на купонный доход': None,  # Tax information is included into interest payment data
            'Поставлены на торги средства клиента': self.transfer_in,
            'Списаны средства клиента': self.transfer_out,
            'Выплата дохода': self.asset_payment,
            'Возврат излишне удержанного налога': self.tax_refund,
            'Проценты по предоставленным займам ЦБ': None,   # Loan payments are loaded in self.load_loans
            'Удержан налог на прочий доход': self.cash_tax,
            'Плата за остаток на счете': self.cash_interest,
            'Удержан налог с дарения по договору дарения': self.cash_tax,  # FIXME - better to combine with next operation
            'Поступили средства клиента': self.cash_interest
        }

        for cash in cash_operations:
            operation = [operation for operation in operations if cash['description'].startswith(operation)]
            if len(operation) != 1:
                raise Statement_ImportError(self.tr("Operation not supported: ") + cash['description'])
            for operation in operations:
                if cash['description'].startswith(operation):
                    if operations[operation] is not None:
                        account_id = self.account_by_currency(cash['currency'])
                        if account_id == 0:
                            raise Statement_ImportError(self.tr("Can't find account for cash operation: ") +
                                                        f"{cash}")
                        operations[operation](cash['timestamp'], account_id, cash['amount'], cash['description'])
                        cnt += 1
        logging.info(self.tr("Cash operations loaded: ") + f"{cnt}")

    def transfer_in(self, timestamp, account_id, amount, description):
        account = [x for x in self._data[FOF.ACCOUNTS] if x["id"] == account_id][0]
        new_id = max([0] + [x['id'] for x in self._data[FOF.TRANSFERS]]) + 1
        transfer = {"id": new_id, "account": [0, account_id, 0], "asset": [account['currency'], account['currency']],
                    "timestamp": timestamp, "withdrawal": amount, "deposit": amount, "fee": 0.0,
                    "description": description}
        self._data[FOF.TRANSFERS].append(transfer)

    def transfer_out(self, timestamp, account_id, amount, description):
        account = [x for x in self._data[FOF.ACCOUNTS] if x["id"] == account_id][0]
        new_id = max([0] + [x['id'] for x in self._data[FOF.TRANSFERS]]) + 1
        transfer = {"id": new_id, "account": [account_id, 0, 0], "asset": [account['currency'], account['currency']],
                    "timestamp": timestamp, "withdrawal": -amount, "deposit": -amount, "fee": 0.0,
                    "description": description}
        self._data[FOF.TRANSFERS].append(transfer)

    def asset_payment(self, timestamp, account_id, amount, description):
        payment_operations = {
            'НКД': self.interest_payment,
            'Погашение': self.bond_repayment
        }
        payment_pattern = r"^.*\((?P<type>\w+).*\).*$"
        parts = re.match(payment_pattern, description, re.IGNORECASE)
        if parts is None:
            payment_pattern = r"^Выплата дохода клиент (?P<type>\d+) дивиденды (?P<asset>.*) налог к удержанию (?P<tax>\d+\.\d+) рублей$"
            parts = re.match(payment_pattern, description, re.IGNORECASE)
            if parts is None:
                raise Statement_ImportError(self.tr("Unknown payment description: ") + f"'{description}'")
            dividend_data = parts.groupdict()
            asset_id = self.find_most_probable_asset(dividend_data['asset'])
            tax = float(dividend_data['tax'])
            self.dividend(timestamp, account_id, asset_id, amount, tax, description)
        else:
            try:
                payment_operations[parts.groupdict()['type']](timestamp, account_id, amount, description)
            except KeyError:
                raise Statement_ImportError(self.tr("Unknown payment type: ") + f"'{parts.groupdict()['type']}'")

    def tax_refund(self, timestamp, account_id, amount, description):
        new_id = max([0] + [x['id'] for x in self._data[FOF.INCOME_SPENDING]]) + 1
        payment = {'id': new_id, 'account': account_id, 'timestamp': timestamp, 'peer': 0,
                   'lines': [{'amount': amount, 'category': -PredefinedCategory.Taxes, 'description': description}]}
        self._data[FOF.INCOME_SPENDING].append(payment)

    def cash_fee(self, timestamp, account_id, amount, description):
        new_id = max([0] + [x['id'] for x in self._data[FOF.INCOME_SPENDING]]) + 1
        payment = {'id': new_id, 'account': account_id, 'timestamp': timestamp, 'peer': 0,
                   'lines': [{'amount': amount, 'category': -PredefinedCategory.Fees, 'description': description}]}
        self._data[FOF.INCOME_SPENDING].append(payment)

    def cash_tax(self, timestamp, account_id, amount, description):
        new_id = max([0] + [x['id'] for x in self._data[FOF.INCOME_SPENDING]]) + 1
        payment = {'id': new_id, 'account': account_id, 'timestamp': timestamp, 'peer': 0,
                   'lines': [{'amount': amount, 'category': -PredefinedCategory.Taxes, 'description': description}]}
        self._data[FOF.INCOME_SPENDING].append(payment)

    def cash_interest(self, timestamp, account_id, amount, description):
        new_id = max([0] + [x['id'] for x in self._data[FOF.INCOME_SPENDING]]) + 1
        payment = {'id': new_id, 'account': account_id, 'timestamp': timestamp, 'peer': 0,
                   'lines': [{'amount': amount, 'category': -PredefinedCategory.Interest, 'description': description}]}
        self._data[FOF.INCOME_SPENDING].append(payment)

    def dividend(self, timestamp, account_id, asset_id, amount, tax, description):
        new_id = max([0] + [x['id'] for x in self._data[FOF.ASSET_PAYMENTS]]) + 1
        payment = {"id": new_id, "type": FOF.PAYMENT_DIVIDEND, "account": account_id, "timestamp": timestamp,
                   "asset": asset_id, "amount": amount, "tax": tax, "description": description}
        self._data[FOF.ASSET_PAYMENTS].append(payment)

    def interest_payment(self, timestamp, account_id, amount, description):
        intrest_pattern = r"^Выплата дохода клиент (?P<account>\w+) \((?P<type>\w+) (?P<number>\d+) (?P<symbol>.*)\) налог.* (?P<tax>\d+\.\d+) рубл.*$"
        parts = re.match(intrest_pattern, description, re.IGNORECASE)
        if parts is None:
            raise Statement_ImportError(self.tr("Can't parse Interest description ") + f"'{description}'")
        interest = parts.groupdict()
        if len(interest) != intrest_pattern.count("(?P<"):  # check expected number of matches
            raise Statement_ImportError(self.tr("Interest description miss some data ") + f"'{description}'")
        asset_id = self.asset_id({'symbol': interest['symbol'], 'search_online': 'MOEX'})
        if asset_id is None:
            raise Statement_ImportError(self.tr("Can't find asset for bond interest ")
                                        + f"'{interest['symbol']}'")
        tax = float(interest['tax'])   # it has '\d+\.\d+' regex pattern so here shouldn't be an exception
        note = f"{interest['type']} {interest['number']}"
        new_id = max([0] + [x['id'] for x in self._data[FOF.ASSET_PAYMENTS]]) + 1
        payment = {"id": new_id, "type": FOF.PAYMENT_INTEREST, "account": account_id, "timestamp": timestamp,
                   "asset": asset_id, "amount": amount, "tax": tax, "description": note}
        self._data[FOF.ASSET_PAYMENTS].append(payment)

    def bond_repayment(self, timestamp, account_id, amount, description):
        repayment_pattern = r"^Выплата дохода клиент (?P<account>\w+) \((?P<type>\w+) (?P<asset>.*)\) налог не удерживается$"
        parts = re.match(repayment_pattern, description, re.IGNORECASE)
        if parts is None:
            raise Statement_ImportError(self.tr("Can't parse Bond Mature description ") + f"'{description}'")
        repayment = parts.groupdict()
        if len(repayment) != repayment_pattern.count("(?P<"):  # check expected number of matches
            raise Statement_ImportError(self.tr("Bond repayment description miss some data ")
                                        + f"'{description}'")
        match = [x for x in self.asset_withdrawal if
                 x['symbol'] == repayment['asset'] and (x['timestamp'] == timestamp or x['report_date'] == timestamp)]
        if not match:
            raise Statement_ImportError(self.tr("Can't find asset cancellation record for ")
                                        + f"'{description}'")
        if len(match) != 1:
            raise Statement_ImportError(self.tr("Multiple asset cancellation match for ")
                                        + f"'{description}'")
        asset_cancel = match[0]
        number = datetime.utcfromtimestamp(timestamp).strftime('%Y%m%d') + f"-{asset_cancel['id']}"
        qty = asset_cancel['quantity']
        price = abs(amount / qty)  # Price is always positive
        new_id = max([0] + [x['id'] for x in self._data[FOF.TRADES]]) + 1
        trade = {"id": new_id, "number": number, "timestamp": timestamp, "settlement": timestamp, "account": account_id,
                 "asset": asset_cancel['asset'], "quantity": qty, "price": price, "fee": 0.0,
                 "note": asset_cancel['note']}
        self._data[FOF.TRADES].append(trade)

    def load_loans(self, loans):
        for loan in loans:
            new_id = max([0] + [x['id'] for x in self._data[FOF.INCOME_SPENDING]]) + 1
            account_id = self.account_by_currency(loan['currency'])
            note = f"Доход по сделке займа #{loan['number']}: {loan['qty']} x {loan['ticker']}"
            fee_note = f"Комиссия за сделку займа #{loan['number']}: {loan['qty']} x {loan['ticker']}"
            payment = {'id': new_id, 'account': account_id, 'timestamp': loan['timestamp'], 'peer': 0,
                       'lines': [
                           {'amount': loan['profit'], 'category': -PredefinedCategory.Interest, 'description': note},
                           {'amount': -loan['fee'], 'category': -PredefinedCategory.Fees, 'description': fee_note}
                       ]}
            self._data[FOF.INCOME_SPENDING].append(payment)

    # Removes data that was used during XML processing but isn't needed in final output:
    # Drop any symbols with type "broker_symbol" as they are auxiliary for statement import only
    def strip_unused_data(self):
        self._data[FOF.SYMBOLS] = [x for x in self._data[FOF.SYMBOLS] if "broker_symbol" not in x]

    # Broker report contains vague asset names in dividends
    # This method tries to locate the best match in available assets and return asset_id if match is found
    def find_most_probable_asset(self, asset_name) -> int:
        match = difflib.get_close_matches(asset_name, [x['symbol'] for x in self._data[FOF.SYMBOLS]], 1)
        if match:
            asset = [x for x in self._data[FOF.SYMBOLS] if x['symbol'] == match[0]]
            return asset[0]['asset']
        match = difflib.get_close_matches(asset_name, [x['name'] for x in self._data[FOF.ASSETS]], 1)
        if match:
            asset = [x for x in self._data[FOF.ASSETS] if x['name'] == match[0]]
            return asset[0]['id']
        raise Statement_ImportError(self.tr("Can't match asset for ") + f"'{asset_name}'")
