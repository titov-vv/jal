# File to fetch asset data from MOEX (except quotes)

import logging
import re
import json
from datetime import datetime, timezone
from PySide6.QtWidgets import QApplication
from jal.widgets.helpers import is_english
from jal.constants import PredefinedAsset
from jal.net.web_request import WebRequest

# ===================================================================================================================
class MOEX:
    mapping = {
        'SECID': 'symbol',
        'NAME': 'name',
        'SHORTNAME': 'short_name',
        'ISIN': 'isin',
        'REGNUMBER': 'reg_number',
        'FACEVALUE': 'principal',
        'MATDATE': 'expiry',
        'LSTDELDATE': 'expiry',
        'GROUP': 'type'
    }
    asset_type = {
        'stock_shares': PredefinedAsset.Stock,
        'stock_dr': PredefinedAsset.Stock,
        'stock_bonds': PredefinedAsset.Bond,
        'stock_etf': PredefinedAsset.ETF,
        'stock_ppif': PredefinedAsset.ETF,
        'futures_forts': PredefinedAsset.Derivative,
        'currency_metal': PredefinedAsset.Commodity
    }
    FuturesPattern = r'^(?P<base_asset>\w+)-\d{1,2}\.\d{2}$'

    def __init__(self):
        pass

    # Searches for asset info on http://www.moex.com/ identified by info provided:
    # kwargs - dict with one of the following keys: 'reg_number', 'isin' or 'name'
    # Returns symbol ('secid' of MOEX) if asset was found and empty string otherwise
    def find_asset(self, **kwargs) -> str:
        asset_data = []
        if reg_nbr := kwargs.get('reg_number', ''):
            asset_data = self.__lookup_asset('reg_number', reg_nbr)
        if not asset_data and (isin := kwargs.get('isin', '')):
            asset_data = self.__lookup_asset('isin', isin)
        if not asset_data and (name := kwargs.get('name', '')):
            asset_data = self.__lookup_asset('name', name)
            if not asset_data and (match := re.match(self.FuturesPattern, name)):
                asset_data = self.__lookup_futures(name, match.group('base_asset')) # not found by name - try extended search if it is a futures contract
        if asset_data and 'secid' in asset_data:
            return asset_data['secid']
        else:
            return ''

    # Searches for asset via MOEX main search: https://iss.moex.com/iss/securities.json
    # key - key to search for (isin, reg_number, name)
    # search_value - value to search for, like ISIN, registration number or asset name
    # Returns dictionary with available asset data or empty dictionary if asset not found
    def __lookup_asset(self, key, search_value) -> dict:
        # Define which columns to search for given value
        fields = {'isin': ['isin'], 'reg_number': ['regnumber'], 'name': ['name', 'shortname']}
        if key not in fields:
            return {}
        request = WebRequest(WebRequest.GET, "https://iss.moex.com/iss/securities.json",
                             params={'q': search_value, 'iss.meta': 'off', 'limit': '10'})
        while request.isRunning():
            QApplication.processEvents()
        moex_search_data = json.loads(request.data())
        securities = moex_search_data['securities']
        data = []
        for field in fields[key]:
            key_col = securities['columns'].index(field)
            if data := [x for x in securities['data'] if x[key_col] == search_value or x[key_col] is None]:
                break
        data = self.__validate_search_data(data, securities['columns'], key, search_value)
        if not data:
            return {}
        return dict(zip(securities['columns'], data[0]))

    def __lookup_futures(self, name, base_asset) -> dict:
        request = WebRequest(WebRequest.GET, "https://iss.moex.com/iss/statistics/engines/futures/markets/forts/series.json",
                             params={'asset_code': base_asset, 'show_expired': '1'})
        while request.isRunning():
            QApplication.processEvents()
        moex_search_data = json.loads(request.data())
        futures = moex_search_data['series']
        key_col = futures['columns'].index('name')
        data = [x for x in futures['data'] if x[key_col] == name or x[key_col] is None]
        data = self.__validate_search_data(data, futures['columns'], 'name', name)
        if not data:
            return {}
        return dict(zip(futures['columns'], data[0]))

    def __validate_search_data(self, data, columns, key, search_value) -> list:
        if not data:
            logging.info(QApplication.translate("MOEX", "No MOEX assets found for ") + f"{key} = {search_value}")
            return []
        if len(data) > 1:  # remove not traded assets if there are any outdated doubles present
            data = [x for x in data if x[columns.index('is_traded')] == 1]
            if not data:
                logging.info(QApplication.translate("MOEX", "Multiple MOEX non-traded assets found for ") + f"{key} = {search_value}: {data}")
                return []
        if len(data) > 1:  # still have multiple matches for the same asset data
            logging.info(QApplication.translate("MOEX", "Multiple MOEX assets found for ") + f"{key} = {search_value}: {data}")
            return []
        return data

    # Fetches asset information from http://moex.com/ for asset identified by kwargs
    # kwargs - dict that can contains:
    # - one of the following mandatory keys: 'symbol', 'isin', 'reg_number'
    # - optional 'currency' key to get info in specific currency
    # - optional 'special' key to get moex specific 'engine', 'market' and 'board' parameters of the asset
    # Returns dictionary with asset data or empty dictionary if asset not found
    def asset_info(self, **kwargs) -> dict:
        data = {}
        if 'symbol' in kwargs and not is_english(kwargs['symbol']):
            del kwargs['symbol']
        currency = kwargs['currency'] if 'currency' in kwargs else ''
        # First try to load with symbol or isin from asset details API
        if 'symbol' in kwargs:
            data = self.__get_info(kwargs['symbol'], currency=currency)
        if not data and 'isin' in kwargs:
            data = self.__get_info(kwargs['isin'], currency=currency)
        # If not found try to use search API with regnumber or isin
        if not data and 'reg_number' in kwargs:
            data = self.__get_info(MOEX().find_asset(reg_number=kwargs['reg_number']))
        if not data and 'isin' in kwargs:
            data = self.__get_info(MOEX().find_asset(isin=kwargs['isin']))
        if 'special' not in kwargs:
            for key in ['engine', 'market', 'board']:
                try:
                    del data[key]
                except KeyError:
                    pass
        return data

    def __get_info(self, asset_code, currency='') -> dict:
        asset = {}
        if not asset_code:
            return asset
        request = WebRequest(WebRequest.GET, f"http://iss.moex.com/iss/securities/{asset_code}.json")
        while request.isRunning():
            QApplication.processEvents()
        moex_data = json.loads(request.data())
        boards = [dict(zip(moex_data['boards']['columns'], x)) for x in moex_data['boards']['data']]
        if not boards:
            return asset
        for row in moex_data['description']['data']:
            value = dict(zip(moex_data['description']['columns'], row))
            asset[value['name']] = value['value']
        asset = {self.mapping[x]: asset[x] for x in asset if x in self.mapping}  # map keys to internal names
        if 'isin' in asset:  # replace symbol with short name if we have isin in place of symbol
            asset['symbol'] = asset['short_name'] if asset['symbol'] == asset['isin'] else asset['symbol']
        if 'short_name' in asset:
            del asset['short_name']  # drop short name as we won't use it further
        if 'principal' in asset:  # Convert principal into float if possible or drop otherwise
            try:
                asset['principal'] = float(asset['principal'])
            except ValueError:
                del asset['principal']
        if 'expiry' in asset:  # convert YYYY-MM-DD into timestamp
            date_value = datetime.strptime(asset['expiry'], "%Y-%m-%d")
            asset['expiry'] = int(date_value.replace(tzinfo=timezone.utc).timestamp())
        try:
            asset['type'] = self.asset_type[asset['type']]
        except KeyError:
            logging.error(QApplication.translate("MOEX", "Unsupported MOEX security type: ") + f"{asset['type']}")
            return {}
        primary_board = [x for x in boards if "is_primary" in x and x["is_primary"] == 1]
        if primary_board:
            assert len(primary_board) == 1, "Unexpected multiple primary boards"
            board_id = primary_board[0]['boardid']
            if primary_board[0]['currencyid'] != currency and primary_board[0]['market'] != 'bonds':
                currency_suffix = {'USD': 'D', 'EUR': 'E', 'CNY': 'Y'}
                board_id = board_id[:-1] + currency_suffix[currency] if currency in currency_suffix else board_id
            board = [x for x in boards if 'boardid' in x and x['boardid'] == board_id]
            if board:
                asset.update({'engine': board[0]['engine'],
                              'market': board[0]['market'],
                              'board': board[0]['boardid']})
        return asset
