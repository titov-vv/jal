import json
import logging

from jal.widgets.helpers import g_tr
from jal.constants import MarketDataFeed, PredefinedAsset
from jal.db.update import JalDB
# -----------------------------------------------------------------------------------------------------------------------


class FOF:
    S_TIMESTAMP = "from"
    E_TIMESTAMP = "to"

    ACCOUNTS = "accounts"
    ASSETS = "assets"
    TRADES = "trades"
    TRANSFERS = "transfers"
    CORP_ACTIONS = "corporate_actions"
    ASSET_PAYMENTS = "asset_payments"
    INCOME_SPENDING = "income_spending"

    ASSET_MONEY = "money"
    ASSET_STOCK = "stock"
    ASSET_ADR = "adr"
    ASSET_ETF = "etf"
    ASSET_BOND = "bond"
    ASSET_FUTURES = "futures"
    ASSET_OPTION = "option"
    ASSET_WARRANT = "warrant"

    ACTION_MERGER = "merger"
    ACTION_SPLIT = "split"
    ACTION_SPINOFF = "spin-off"
    ACTION_SYMBOL_CHANGE = "symbol_change"
    ACTION_STOCK_DIVIDEND = "stock_dividend"

    PAYMENT_DIVIDEND = "dividend"
    PAYMENT_INTEREST = "interest"


# -----------------------------------------------------------------------------------------------------------------------
class Statement:
    _asset_types = {
        FOF.ASSET_MONEY: PredefinedAsset.Money,
        FOF.ASSET_STOCK: PredefinedAsset.Stock,
        FOF.ASSET_ADR: PredefinedAsset.Stock,
        FOF.ASSET_ETF: PredefinedAsset.ETF,
        FOF.ASSET_BOND: PredefinedAsset.Bond,
        FOF.ASSET_FUTURES: PredefinedAsset.Derivative,
        FOF.ASSET_OPTION: PredefinedAsset.Derivative,
        FOF.ASSET_WARRANT: PredefinedAsset.Stock,
    }
    _sources = {
        'NYSE': MarketDataFeed.US,
        'ARCA': MarketDataFeed.US,
        'NASDAQ': MarketDataFeed.US,
        'TSE': MarketDataFeed.CA,
        'SBF': MarketDataFeed.EU,
        'AMEX': MarketDataFeed.US
    }
    
    def __init__(self):
        self._data = {}

    def load(self, filename: str) -> None:
        self._data = {}
        try:
            with open(filename, 'r') as exchange_file:
                try:
                    self._data = json.load(exchange_file)
                except json.JSONDecodeError:
                    logging.error(g_tr('Statement', "Failed to read JSON from file: ") + filename)
        except Exception as err:
            logging.error(g_tr('Statement', "Failed to read file: ") + str(err))

    def match_db_ids(self, verbal=True):
        self._match_asset_ids(verbal)
        self._match_account_ids()

    def _match_asset_ids(self, verbal):
        for asset in self._data[FOF.ASSETS]:
            isin = asset['isin'] if 'isin' in asset else ''
            reg_code = asset['reg_code'] if 'reg_code' in asset else ''
            name = asset['name'] if 'name' in asset else ''
            asset_id = JalDB().get_asset_id(asset['symbol'], isin=isin, reg_code=reg_code, name=name, dialog_new=verbal)
            if asset_id:
                old_id, asset['id'] = asset['id'], -asset_id
                self._update_id("asset", old_id, asset_id)
                if asset['type'] == FOF.ASSET_MONEY:
                    self._update_id("currency", old_id, asset_id)

    def _match_account_ids(self):
        for account in self._data[FOF.ACCOUNTS]:
            account_id = JalDB().find_account(account['number'], -account['currency'])
            if account_id:
                old_id, account['id'] = account['id'], -account_id
                self._update_id("account", old_id, account_id)

    def _update_id(self, tag_name, old_value, new_value):
        for section in self._data:
            if type(self._data[section]) != list:
                continue
            for element in self._data[section]:
                for tag in element:
                    if tag == tag_name:
                        if type(element[tag]) == list:
                            element[tag] = [-new_value if x==old_value else x for x in element[tag]]
                        else:
                            element[tag] = -new_value if element[tag] == old_value else element[tag]
