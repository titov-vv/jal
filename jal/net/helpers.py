import requests
import logging
import json
import platform
from jal import __version__
from jal.constants import MarketDataFeed, PredefinedAsset
from jal.widgets.helpers import g_tr


# ===================================================================================================================
# Function returns custom User Agent for web requests
def make_user_agent() -> str:
    return f"JAL/{__version__} ({platform.system()} {platform.release()})"


# ===================================================================================================================
# Retrieve URL from web with given method and params
def request_url(method, url, params=None, json_params=None):
    session = requests.Session()
    session.headers['User-Agent'] = make_user_agent()
    if method == "GET":
        response = session.get(url)
    elif method == "POST":
        if params:
            response = session.post(url, data=params)
        elif json_params:
            response = session.post(url, json=json_params)
        else:
            response = session.post(url)
    else:
        raise ValueError("Unknown download method for URL")
    if response.status_code == 200:
        return response.text
    else:
        logging.error(f"URL: {url}" + g_tr('Net', " failed: ") + f"{response.status_code}: {response.text}")
        return ''


# ===================================================================================================================
# Function download URL and return it content as string or empty string if site returns error
def get_web_data(url):
    return request_url("GET", url)


# ===================================================================================================================
# Function download URL and return it content as string or empty string if site returns error
def post_web_data(url, params=None, json_params=None):
    return request_url("POST", url, params=params, json_params=json_params)

# ===================================================================================================================
# Function tries to get asset information online from http://www.moex.com
# Dictionary keys contains search keys that should match for found security
# ===================================================================================================================
def GetAssetInfoFromMOEX(keys) -> dict:
    asset_type = {
        'stock_shares': PredefinedAsset.Stock,
        'stock_dr': PredefinedAsset.Stock,
        'stock_bonds': PredefinedAsset.Bond,
        'stock_etf': PredefinedAsset.ETF,
        'stock_ppif': PredefinedAsset.ETF,
        'futures_forts': PredefinedAsset.Derivative
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
    if not matched:
        search_set = set(keys)
        for key in search_set:
            subset = [x for x in data if
                      (not x[columns.index(key)] is None) and (x[columns.index(key)].lower() == keys[key].lower())]
            if len(subset) == 1:
                matched = True
                asset_data = dict(zip(columns, subset[0]))
                break
    if matched:   # Sometimes symbol is "absent" - for example bonds have ISIN instead
        asset['symbol'] = asset_data['shortname'] if asset_data['secid'] == asset_data['isin'] else asset_data['secid']
        asset['name'] = asset_data['name']
        asset['isin'] = asset_data['isin'] if 'isin' in asset_data else ''
        asset['reg_code'] = asset_data['regnumber'] if 'regnumber' in asset_data else ''
        try:
            asset['type'] = asset_type[asset_data['group']]
        except KeyError:
            logging.error(g_tr('Net', "Unsupported MOEX security type: ") + f"{asset_data['group']}")
            return {}
        asset['source'] = MarketDataFeed.RU
    return asset
