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
# Function tries to get asset information online and add it into database using isin and reg_code
# ===================================================================================================================
def GetAssetInfoByISIN(isin, reg_code) -> dict:
    asset_type = {
        'stock_shares': PredefinedAsset.Stock,
        'stock_bonds': PredefinedAsset.Bond,
        'stock_etf': PredefinedAsset.ETF
    }

    asset = {}
    url = f"https://iss.moex.com/iss/securities.json?q={isin}&iss.meta=off"
    asset_data = json.loads(get_web_data(url))
    securities = asset_data['securities']
    columns = securities['columns']
    data = securities['data']
    for security in data:
        if security[columns.index('regnumber')] is None:
            security[columns.index('regnumber')] = ''
        if security[columns.index('isin')] == isin and security[columns.index('regnumber')] == reg_code:
            logging.warning(g_tr('Net', "Online data found for: ") + f"{isin}/{reg_code}")
            asset['symbol'] = security[columns.index('secid')]
            asset['name'] = security[columns.index('name')]
            asset['type'] = asset_type[security[columns.index('group')]]
            asset['source'] = MarketDataFeed.RU
            break
    return asset

