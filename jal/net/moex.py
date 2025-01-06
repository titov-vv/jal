# File to fetch asset data from MOEX (except quotes)

import logging
import re
import json
from PySide6.QtWidgets import QApplication
from jal.net.web_request import WebRequest

# ===================================================================================================================
class MOEX:
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
        if len(data) > 1: # remove not traded assets if there are any outdated doubles present
            data = [x for x in data if x[securities['columns'].index('is_traded')] == 1]
        if len(data) > 1: # still have multiple matches for the same asset data
            logging.info(QApplication.translate("MOEX", "Multiple MOEX assets found for ") + f"{key} = {search_value}: {data}")
            return {}
        if not data:
            logging.info(QApplication.translate("MOEX", "No MOEX assets found for ") + f"{key} = {search_value}")
            return {}
        asset_data = dict(zip(securities['columns'], data[0]))
        return asset_data

    def __lookup_futures(self, name, base_asset) -> dict:
        request = WebRequest(WebRequest.GET, "https://iss.moex.com/iss/statistics/engines/futures/markets/forts/series.json",
                             params={'asset_code': base_asset, 'show_expired': '1'})
        while request.isRunning():
            QApplication.processEvents()
        moex_search_data = json.loads(request.data())
        futures = moex_search_data['series']
        key_col = futures['columns'].index('name')
        data = [x for x in futures['data'] if x[key_col] == name or x[key_col] is None]
        if len(data) > 1: # remove not traded futures if there are any outdated doubles present
            data = [x for x in data if x[futures['columns'].index('is_traded')] == 1]
        if len(data) > 1: # still have multiple matches for the same asset data
            logging.info(QApplication.translate("MOEX", "Multiple MOEX futures found for ") + f"{name}: {data}")
            return {}
        if not data:
            logging.info(QApplication.translate("MOEX", "No MOEX futures found for ") + f"{name}")
            return {}
        asset_data = dict(zip(futures['columns'], data[0]))
        return asset_data

    def asset_info(self, **kwargs) -> dict:
        pass

    def __get_info(self, asset_code, currency='') -> dict:
        pass