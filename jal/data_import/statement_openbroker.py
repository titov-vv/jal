import logging
from datetime import datetime

from jal.widgets.helpers import g_tr
from jal.data_import.statement import FOF
from jal.data_import.statement_xml import StatementXML
from jal.net.helpers import GetAssetInfoFromMOEX


# -----------------------------------------------------------------------------------------------------------------------
class OpenBroker_AssetType:
    NotSupported = -1
    _asset_types = {
        '': -1,
        'Облигации': FOF.ASSET_BOND
    }

    def __init__(self, asset_type):
        self.type = self.NotSupported
        try:
            self.type = self._asset_types[asset_type]
        except KeyError:
            logging.warning(g_tr('OpenBroker_AssetType', "Asset type isn't supported: ") + f"'{asset_type}'")


# -----------------------------------------------------------------------------------------------------------------------
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


# -----------------------------------------------------------------------------------------------------------------------
class StatementOpenBroker(StatementXML):
    statements_path = '.'
    statement_tag = 'broker_report'

    def __init__(self):
        super().__init__()
        self.statement_name = g_tr('OpenBroker', "Open Broker statement")
        open_loaders = {
            OpenBroker_AssetType: self.attr_asset_type,
            OpenBroker_Exchange: self.attr_exchange
        }
        self.attr_loader.update(open_loaders)
        self._sections = {
            StatementXML.STATEMENT_ROOT: {'tag': self.statement_tag,
                                          'level': '',
                                          'values': [('client_code', 'account', str, None),
                                                     ('date_from', 'period_start', datetime, None),
                                                     ('date_to', 'period_end', datetime, None)],
                                          'loader': self.load_header
                                          },
            'spot_portfolio_security_params': {'tag': 'item',
                                               'level': '',
                                               'values': [('ticker', 'symbol', str, None),
                                                          ('security_type', 'type', OpenBroker_AssetType, OpenBroker_AssetType.NotSupported),
                                                          ('security_name', 'name', str, None),
                                                          ('isin', 'isin', str, ''),
                                                          ('security_grn_code', 'reg_code', str, ''),
                                                          ('board_name', 'exchange', OpenBroker_Exchange, '')],
                                               'loader': self.load_assets
                                               }
        }

    # Convert attribute 'attr_name' value into json open-format asset type
    @staticmethod
    def attr_asset_type(xml_element, attr_name, default_value):
        if attr_name not in xml_element.attrib:
            return default_value
        return OpenBroker_AssetType(xml_element.attrib[attr_name]).type

    # Convert attribute 'attr_name' value into json open-format exchange name
    @staticmethod
    def attr_exchange(xml_element, attr_name, default_value):
        if attr_name not in xml_element.attrib:
            return default_value
        return OpenBroker_Exchange(xml_element.attrib[attr_name]).name

    def load_header(self, header):
        self._data[FOF.PERIOD][0] = header['period_start']
        self._data[FOF.PERIOD][1] = header['period_end']
        logging.info(g_tr('OpenBroker', "Load Open Broker statement for account ") +
                     f"{header['account']}: {datetime.utcfromtimestamp(header['period_start']).strftime('%Y-%m-%d')}" +
                     f" - {datetime.utcfromtimestamp(header['period_end']).strftime('%Y-%m-%d')}")

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
                if len(asset_info):
                    asset_data = {'symbol': asset_info['symbol'], 'name': asset_info['name'],
                                  'isin': asset_info['isin']}
                    if asset_info['reg_code']:
                        asset_data['reg_code'] = asset_info['reg_code']
                    asset.update(asset_data)
            if asset['exchange'] == '':  # don't store empty exchange
                asset.pop('exchange')
            cnt += 1
            self._data[FOF.ASSETS].append(asset)
        logging.info(g_tr('OpenBroker', "Securities loaded: ") + f"{cnt} ({len(assets)})")
