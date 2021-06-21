import requests
import logging
import json
from jal.constants import MarketDataFeed, PredefinedAsset
from jal.widgets.helpers import g_tr


# ===================================================================================================================
# Function download URL and return it content as string or empty string if site returns error
# ===================================================================================================================
def get_web_data(url):
    response = requests.get(url)
    if response.status_code == 200:
        return response.text
    else:
        logging.error(f"URL: {url}" + g_tr('Net', " failed: ") + f"{response.status_code}: {response.text}")
        return ''


# ===================================================================================================================
# Function download URL and return it content as string or empty string if site returns error
# ===================================================================================================================
def post_web_data(url, params):
    s = requests.Session()
    response = s.post(url, json=params)
    if response.status_code == 200:
        return response.text
    else:
        logging.error(f"URL: {url}" + g_tr('Net', " failed: ") + f"{response.status_code}: {response.text}")
        return ''


# ===================================================================================================================
# Function tries to get asset information online from http://www.moex.com
# Dictionary keys contains search keys that should match for found security
# ===================================================================================================================
def GetAssetInfoFromMOEX(keys) -> dict:
    asset_type = {
        'stock_shares': PredefinedAsset.Stock,
        'stock_bonds': PredefinedAsset.Bond,
        'stock_etf': PredefinedAsset.ETF,
        'stock_ppif': PredefinedAsset.ETF,
        'futures': PredefinedAsset.Derivative
    }

    asset = {}
    keys = {x: keys[x] for x in keys if keys[x]}   # Drop empty values from keys
    priority_list = ['isin', 'regnumber', 'secid']
    try:
        search_key = keys[sorted(keys, key=lambda x: priority_list.index(x))[0]]
    except ValueError:
        logging.error(g_tr('Net', "Unknown MOEX search key"))
        return asset
    except IndexError:
        logging.error(g_tr('Net', "No valid MOEX search key provided"))
        return asset
    if not search_key:
        logging.error(g_tr('Net', "Empty MOEX search key"))
        return asset

    url = f"https://iss.moex.com/iss/securities.json?q={search_key}&iss.meta=off&limit=10"
    asset_data = json.loads(get_web_data(url))
    securities = asset_data['securities']
    columns = securities['columns']
    data = securities['data']
    matched = False
    asset_found = None
    search_set = set(keys)
    if 'secid' in keys:
        search_set.remove('secid')
    if len(search_set):
        for security in data:
            asset_data = dict(zip(columns, security))
            asset_data = {x: asset_data[x] for x in asset_data if asset_data[x]}  # Drop empty values from keys
            matched = True
            for key in search_set:
                if key in asset_data and asset_data[key] == keys[key]:
                    continue
                matched = False
            if matched:
                break
    if not matched and len(data) == 1:
        search_set = set(keys)
        asset_data = dict(zip(columns, data[0]))
        asset_data = {x: asset_data[x] for x in asset_data if asset_data[x]}  # Drop empty values from keys
        for key in search_set:
            if key in asset_data and asset_data[key] == keys[key]:
                matched = True
                break
    if matched:
        asset['symbol'] = asset_data['secid']
        asset['name'] = asset_data['name']
        asset['isin'] = asset_data['isin'] if 'isin' in asset_data else ''
        asset['reg_code'] = asset_data['regnumber'] if 'regnumber' in asset_data else ''
        try:
            asset['type'] = asset_type[asset_data['group']]
        except KeyError:
            logging.error(g_tr('Net', "Unsupported MOEX security type: ") + f"{asset_found['group']}")
        asset['source'] = MarketDataFeed.RU
    return asset
