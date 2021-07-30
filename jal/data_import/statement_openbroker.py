import logging
from datetime import datetime

from jal.widgets.helpers import g_tr
from jal.data_import.statement import FOF, Statement_ImportError
from jal.data_import.statement_xml import StatementXML
from jal.net.helpers import GetAssetInfoFromMOEX


class StatementOpenBroker(StatementXML):
    statements_path = '.'
    statement_tag = 'broker_report'

    def __init__(self):
        super().__init__()
        self.statement_name = g_tr('OpenBroker', "Open Broker statement")
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
                                                          ('security_type', 'type', str, None),
                                                          ('security_name', 'name', str, None),
                                                          ('isin', 'isin', str, ''),
                                                          ('security_grn_code', 'reg_code', str, ''),
                                                          ('board_name', 'exchange', str, '')],
                                               'loader': self.load_assets
                                               }
        }

    def load_header(self, header):
        self._data[FOF.PERIOD][0] = header['period_start']
        self._data[FOF.PERIOD][1] = header['period_end']
        logging.info(g_tr('OpenBroker', "Load Open Broker statement for account ") +
                     f"{header['account']}: {datetime.utcfromtimestamp(header['period_start']).strftime('%Y-%m-%d')}" +
                     f" - {datetime.utcfromtimestamp(header['period_end']).strftime('%Y-%m-%d')}")

    def load_assets(self, assets):
        security_types = {
            "Облигации": "bond"
        }
        exchanges = {
            "ПАО Московская биржа": "MOEX"
        }
        cnt = 0
        base = max([0] + [x['id'] for x in self._data[FOF.ASSETS]]) + 1
        for i, asset in enumerate(assets):
            asset['id'] = base + i
            try:
                asset['type'] = security_types[asset['type']]
            except KeyError:
                raise Statement_ImportError(
                    g_tr('OpenBroker', "Security type not supported: ") + f"{asset['type']}")
            if 'exchange' in asset:
                try:
                    asset['exchange'] = exchanges[asset['exchange']]
                except KeyError:
                    logging.warning(g_tr('OpenBroker', "Exchange not known: ") + asset['exchange'])
                    del asset['exchange']
                if asset['exchange'] == "MOEX":
                    asset_info = GetAssetInfoFromMOEX(
                        keys={"isin": asset['isin'], "regnumber": asset['reg_code'], "secid": asset['symbol']})
                    if len(asset_info):
                        asset_data = {'symbol': asset_info['symbol'], 'name': asset_info['name'],
                                      'isin': asset_info['isin']}
                        if asset_info['reg_code']:
                            asset_data['reg_code'] = asset_info['reg_code']
                        asset.update(asset_data)
            cnt += 1
            self._data[FOF.ASSETS].append(asset)
        logging.info(g_tr('OpenBroker', "Securities loaded: ") + f"{cnt} ({len(assets)})")
