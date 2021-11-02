import logging
import re
from datetime import datetime

from PySide6.QtWidgets import QApplication
from jal.constants import Setup
from jal.data_import.statement import FOF, Statement_ImportError
from jal.data_import.statement_xml import StatementXML
from jal.net.downloader import QuoteDownloader


# ----------------------------------------------------------------------------------------------------------------------
class OpenBroker_AssetType:
    NotSupported = -1
    _asset_types = {
        '': -1,
        'Денежные средства': FOF.ASSET_MONEY,
        'Облигации': FOF.ASSET_BOND
    }

    def __init__(self, asset_type):
        self.type = self.NotSupported
        try:
            self.type = self._asset_types[asset_type]
        except KeyError:
            logging.warning(QApplication.translate("OpenBroker", "Asset type isn't supported: ") + f"'{asset_type}'")


# ----------------------------------------------------------------------------------------------------------------------
class OpenBroker_Asset:
    def __init__(self, assets_list, symbol, reg_code=''):
        self.id = None

        # Try to find asset in list first by reg.code, next by symbol and as last resort by alt_symbol if it exists
        if reg_code:
            match = [x for x in assets_list if
                     ('symbol' in x and 'reg_code' in x) and (x['symbol'] == symbol and x['reg_code'] == reg_code)]
            if match:
                if len(match) == 1:
                    self.id = match[0]['id']
                    return
                else:
                    logging.error(QApplication.translate("OpenBroker", "Multiple asset match for ")
                                  + f"'{symbol}':'{reg_code}'")
                    return
        match = [x for x in assets_list if 'symbol' in x and x['symbol'] == symbol]
        if match:
            if len(match) == 1:
                self.id = match[0]['id']
                return
            else:
                logging.error(QApplication.translate("OpenBroker", "Multiple asset match for ") + f"'{symbol}'")
        match = [x for x in assets_list if 'alt_symbol' in x and x['alt_symbol'] == symbol]
        if match:
            if len(match) == 1:
                self.id = match[0]['id']
                return
            else:
                logging.error(QApplication.translate("OpenBroker", "Multiple asset match for ") + f"'{symbol}'")

# ----------------------------------------------------------------------------------------------------------------------
class OpenBroker_Currency:
    def __init__(self, assets_list, symbol):
        self.id = None
        match = [x for x in assets_list if 'symbol' in x and x['symbol'] == symbol and x['type'] == FOF.ASSET_MONEY]
        if match and len(match) == 1:
            self.id = match[0]['id']


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

    def __init__(self):
        super().__init__()
        self.statement_name = self.tr("Open Broker statement")
        self._account_number = ''
        self.asset_withdrawal = []
        open_loaders = {
            OpenBroker_AssetType: self.attr_asset_type,
            OpenBroker_Asset: self.attr_asset,
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
            'spot_portfolio_security_params':
                {
                    'tag': 'item',
                    'level': '',
                    'values': [('ticker', 'symbol', str, None),
                               ('security_type', 'type', OpenBroker_AssetType, OpenBroker_AssetType.NotSupported),
                               ('security_name', 'name', str, None),
                               ('isin', 'isin', str, ''),
                               ('security_grn_code', 'reg_code', str, ''),
                               ('board_name', 'exchange', OpenBroker_Exchange, '')],
                    'loader': self.load_assets
                },
            'spot_assets':
                {
                    'tag': 'item',
                    'level': '',
                    'values': [('asset_name', 'asset', OpenBroker_Asset, None),
                               ('opening_position_plan', 'cash_begin', float, 0),
                               ('closing_position_plan', 'cash_end', float, 0),
                               ('closing_position_fact', 'cash_end_settled', float, 0)],
                    'loader': self.load_balances
                },
            'spot_main_deals_conclusion':
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
                               ('security_name', 'asset', OpenBroker_Asset, None),
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
                }
        }

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
        if asset_category == FOF.ASSET_MONEY:
            symbol = xml_element.attrib['asset_code'].strip()
            reg_code = ''
        else:
            symbol = xml_element.attrib[attr_name].strip()
            if xml_element.tag == 'spot_assets':
                reg_code = xml_element.attrib['asset_code'] if 'asset_code' in xml_element.attrib else ''
            else:
                reg_code = xml_element.attrib['security_grn_code'] if 'security_grn_code' in xml_element.attrib else ''
        asset_id = OpenBroker_Asset(self._data[FOF.ASSETS], symbol, reg_code).id
        if asset_id is None:
            if asset_category == FOF.ASSET_MONEY:
                asset_id = max([0] + [x['id'] for x in self._data[FOF.ASSETS]]) + 1
                asset = {'id': asset_id, 'type': asset_category, 'symbol': symbol}
                self._data[FOF.ASSETS].append(asset)
            else:
                return default_value
        return asset_id

    # convert 'attr_name' currency code value into asset_id
    def attr_currency(self, xml_element, attr_name, default_value):
        if attr_name not in xml_element.attrib:
            return default_value
        return OpenBroker_Currency(self._data[FOF.ASSETS], xml_element.attrib[attr_name]).id

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
        base = max([0] + [x['id'] for x in self._data[FOF.ASSETS]]) + 1
        for i, asset in enumerate(assets):
            if asset['type'] == OpenBroker_AssetType.NotSupported:   # Skip not supported type of asset
                continue
            asset['id'] = base + i
            if asset['exchange'] == "MOEX":
                asset_info = QuoteDownloader.MOEX_info(symbol=asset['symbol'], isin=asset['isin'],
                                                       regnumber=asset['reg_code'])
                if asset_info:
                    asset.update(asset_info)
                    asset['type'] = FOF.convert_predefined_asset_type(asset['type'])
            if asset['exchange'] == '':  # don't store empty exchange
                asset.pop('exchange')
            cnt += 1
            self._data[FOF.ASSETS].append(asset)
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
            if abs(abs(trade['price'] * trade['quantity']) - amount) >= Setup.DISP_TOLERANCE:
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
        # Asset name is stored as 'alt_symbol' in self.assets[] and self.asset_withdrawal[]
        bond_repayment_pattern = r"^.*Снятие ЦБ с учета\. Погашение облигаций - (?P<asset_name>.*)$"
        for operation in asset_operations:
            if "Снятие ЦБ с учета. Погашение облигаций" not in operation['description']:
                raise Statement_ImportError(self.tr("Unknown non-trade operation: ")
                                            + operation['description'])
            parts = re.match(bond_repayment_pattern, operation['description'], re.IGNORECASE)
            if parts is None:
                raise Statement_ImportError(
                    self.tr("Can't parse bond repayment description ") + f"'{operation['description']}'")
            repayment_note = parts.groupdict()
            if len(repayment_note) != bond_repayment_pattern.count("(?P<"):  # check expected number of matches
                raise Statement_ImportError(
                    self.tr("Can't detect bond name from description ") + f"'{repayment_note}'")
            asset = [x for x in self._data[FOF.ASSETS] if 'id' in x and x['id'] == operation['asset']][0]
            if asset['symbol'] != repayment_note['asset_name']:    # Store alternative depositary name
                asset['alt_symbol'] = repayment_note['asset_name']
            new_id = max([0] + [x['id'] for x in self.asset_withdrawal]) + 1
            record = {"id": new_id, "timestamp": operation['timestamp'], "asset": operation['asset'],
                      "symbol": asset['symbol'], "alt_symbol": repayment_note['asset_name'],
                      "quantity": operation['quantity'], "note": operation['description']}
            self.asset_withdrawal.append(record)

    def load_cash_operations(self, cash_operations):
        cnt = 0
        operations = {
            'Комиссия Брокера / ': None,              # These operations are included of trade's data
            'Удержан налог на купонный доход': None,  # Tax information is included into interest payment data
            'Поставлены на торги средства клиента': self.transfer_in,
            'Выплата дохода': self.asset_payment
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

    def asset_payment(self, timestamp, account_id, amount, description):
        payment_operations = {
            'НКД': self.interest_payment,
            'Погашение': self.bond_repayment
        }
        payment_pattern = r"^.*\((?P<type>\w+).*\).*$"
        parts = re.match(payment_pattern, description, re.IGNORECASE)
        if parts is None:
            raise Statement_ImportError(self.tr("Unknown payment description: ") + f"'{description}'")
        try:
            payment_operations[parts.groupdict()['type']](timestamp, account_id, amount, description)
        except KeyError:
            raise Statement_ImportError(self.tr("Unknown payment type: ") + f"'{parts.groupdict()['type']}'")

    def interest_payment(self, timestamp, account_id, amount, description):
        intrest_pattern = r"^Выплата дохода клиент (?P<account>\w+) \((?P<type>\w+) (?P<number>\d+) (?P<symbol>.*)\) налог.* (?P<tax>\d+\.\d+) рубл.*$"
        parts = re.match(intrest_pattern, description, re.IGNORECASE)
        if parts is None:
            raise Statement_ImportError(self.tr("Can't parse Interest description ") + f"'{description}'")
        interest = parts.groupdict()
        if len(interest) != intrest_pattern.count("(?P<"):  # check expected number of matches
            raise Statement_ImportError(self.tr("Interest description miss some data ") + f"'{description}'")
        asset_id = OpenBroker_Asset(self._data[FOF.ASSETS], interest['symbol']).id
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
        match = [x for x in self.asset_withdrawal
                 if (x['symbol'] == repayment['asset'] or x['alt_symbol'] == repayment['asset'])
                    and x['timestamp'] == timestamp]
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
