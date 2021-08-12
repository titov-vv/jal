import logging
from datetime import datetime

from jal.widgets.helpers import g_tr
from jal.constants import Setup, PredefinedAsset
from jal.data_import.statement import FOF, Statement_ImportError
from jal.data_import.statement_xml import StatementXML
from jal.net.helpers import GetAssetInfoFromMOEX


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
            logging.warning(g_tr('OpenBroker_AssetType', "Asset type isn't supported: ") + f"'{asset_type}'")


# ----------------------------------------------------------------------------------------------------------------------
class OpenBroker_Asset:
    def __init__(self, assets_list, symbol, reg_code=''):
        self.id = None
        if reg_code:
            match = [x for x in assets_list if
                     ('symbol' in x and 'reg_code' in x) and (x['symbol'] == symbol and x['reg_code'] == reg_code)]
            if match:
                if len(match) == 1:
                    self.id = match[0]['id']
                    return
                else:
                    logging.error(g_tr('OpenBroker', "Multiple asset match for ") + f"'{symbol}':'{reg_code}'")
                    return
        match = [x for x in assets_list if 'symbol' in x and x['symbol'] == symbol]
        if match:
            if len(match) == 1:
                self.id = match[0]['id']
                return
            else:
                logging.error(g_tr('OpenBroker', "Multiple asset match for ") + f"'{symbol}'")


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
            logging.warning(g_tr('OpenBroker_Exchange', "Exchange isn't supported: ") + f"'{exchange}'")


# ----------------------------------------------------------------------------------------------------------------------
class StatementOpenBroker(StatementXML):
    statements_path = '.'
    statement_tag = 'broker_report'

    def __init__(self):
        super().__init__()
        self.statement_name = g_tr('OpenBroker', "Open Broker statement")
        self._account_number = ''
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
                               ('board_name', 'exchange', OpenBroker_Exchange, ''),
                               ('nominal', 'bond_principal', float, 0)],
                    'loader': self.load_assets
                },
            'spot_assets':
                {
                    'tag': 'item',
                    'level': '',
                    'values': [('asset_name', 'asset', OpenBroker_Asset, None),
                               ('opening_position_fact', 'cash_begin', float, 0),
                               ('closing_position_fact', 'cash_end', float, 0),
                               ('closing_position_plan', 'cash_end_settled', float, 0)],
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
        logging.info(g_tr('OpenBroker', "Load Open Broker statement for account ") +
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
                asset_info = GetAssetInfoFromMOEX(
                    keys={"isin": asset['isin'], "regnumber": asset['reg_code'], "secid": asset['symbol']})
                if asset_info:
                    asset.update(asset_info)
                    asset['type'] = FOF.convert_predefined_asset_type(asset['type'])
            if asset['exchange'] == '':  # don't store empty exchange
                asset.pop('exchange')
            cnt += 1
            self._data[FOF.ASSETS].append(asset)
        logging.info(g_tr('OpenBroker', "Securities loaded: ") + f"{cnt} ({len(assets)})")

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
        logging.info(g_tr('OpenBroker', "Accounts loaded: ") + f"{cnt}")

    def load_trades(self, trades):
        cnt = 0
        trade_base = max([0] + [x['id'] for x in self._data[FOF.TRADES]]) + 1
        for i, trade in enumerate(sorted(trades, key=lambda x: x['timestamp'])):
            trade['id'] = trade_base + i
            trade['account'] = self.account_by_currency(trade['currency'])
            if trade['account'] == 0:
                raise Statement_ImportError(g_tr('OpenBroker', "Can't find account for trade: ") + f"{trade}")
            if trade['quantity_buy'] < 0 and trade['quantity_sell'] < 0:
                raise Statement_ImportError(g_tr('OpenBroker', "Can't determine trade type/quantity: ") + f"{trade}")
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

    def load_cash_operations(self, cash_operations):
        cnt = 0
        operations = {
            'Комиссия Брокера / ': None,  # These operations are included of trade's data
            'Поставлены на торги средства клиента': self.transfer_in
        }

        for cash in cash_operations:
            for operation in operations:
                if cash['description'].startswith(operation):
                    if operations[operation] is not None:
                        account_id = self.account_by_currency(cash['currency'])
                        if account_id == 0:
                            raise Statement_ImportError(g_tr('OpenBroker', "Can't find account for cash operation: ") +
                                                        f"{cash}")
                        operations[operation](cash['timestamp'], account_id, cash['amount'], cash['description'])
                        cnt += 1
        logging.info(g_tr('Uralsib', "Cash operations loaded: ") + f"{cnt}")

    def transfer_in(self, timestamp, account_id, amount, description):
        account = [x for x in self._data[FOF.ACCOUNTS] if x["id"] == account_id][0]
        new_id = max([0] + [x['id'] for x in self._data[FOF.TRANSFERS]]) + 1
        transfer = {"id": new_id, "account": [0, account_id, 0], "asset": [account['currency'], account['currency']],
                    "timestamp": timestamp, "withdrawal": amount, "deposit": amount, "fee": 0.0,
                    "description": description}
        self._data[FOF.TRANSFERS].append(transfer)