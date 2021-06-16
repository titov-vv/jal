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
        'stock_etf': PredefinedAsset.ETF,
        'stock_ppif': PredefinedAsset.ETF
    }

    asset = {}
    if isin:
        url = f"https://iss.moex.com/iss/securities.json?q={isin}&iss.meta=off"
    else:
        url = f"https://iss.moex.com/iss/securities.json?q={reg_code}&iss.meta=off"
    asset_data = json.loads(get_web_data(url))
    securities = asset_data['securities']
    columns = securities['columns']
    data = securities['data']
    for security in data:
        matched = False
        if security[columns.index('regnumber')] is None:
            if len(data) == 1:
                if security[columns.index('isin')] == isin:
                    logging.info(g_tr('Net', "Online data found for: ") + f"{isin}")
                    matched = True
            else:
                security[columns.index('regnumber')] = ''
        if security[columns.index('isin')] == isin and security[columns.index('regnumber')] == reg_code:
            logging.info(g_tr('Net', "Online data found for: ") + f"{isin}/{reg_code}")
            matched = True
        if not isin:
            if len(data) == 1 and security[columns.index('regnumber')] == reg_code:
                logging.info(g_tr('Net', "Online data found for: ") + f"{reg_code}")
                matched = True
        if matched:
            asset['symbol'] = security[columns.index('secid')]
            asset['name'] = security[columns.index('name')]
            asset['isin'] = security[columns.index('isin')]
            asset['reg_code'] = security[columns.index('regnumber')]
            try:
                asset['type'] = asset_type[security[columns.index('group')]]
            except KeyError:
                logging.error(g_tr('Net', "Unsupported MOEX security type: ") + f"{security[columns.index('group')]}")
                continue
            asset['source'] = MarketDataFeed.RU
            break
    return asset
