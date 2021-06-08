import json
import sys
import logging
from datetime import datetime

from jal.widgets.helpers import g_tr
from jal.constants import MarketDataFeed, PredefinedAsset
from jal.db.update import JalDB
if "pytest" not in sys.modules:
    from jal.data_import.statements import SelectAccountDialog
    from PySide2.QtWidgets import QDialog
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


class Statement_ImportError(Exception):
    pass


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
        self._last_selected_account = None

    # Loads JSON statement format from file defined by 'filename'
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

    # check are assets and accounts from self._data present in database
    # replace IDs in self._data with IDs from database (DB IDs will be negative, initial IDs will be positive)
    def match_db_ids(self, verbal=True):
        self._match_asset_ids(verbal)
        self._match_account_ids()

    # Check and replace IDs for Assets
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

    # Check and replace IDs for Accounts
    def _match_account_ids(self):
        for account in self._data[FOF.ACCOUNTS]:
            account_id = JalDB().find_account(account['number'], -account['currency'])
            if account_id:
                old_id, account['id'] = account['id'], -account_id
                self._update_id("account", old_id, account_id)

    # Replace 'old_value' with 'new_value' in keys 'tag_name' of self._data
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

    def import_into_db(self):
        sections = {
            FOF.S_TIMESTAMP: None,
            FOF.E_TIMESTAMP: None,
            FOF.ASSETS: self._import_assets,
            FOF.ACCOUNTS: self._import_accounts,
            FOF.INCOME_SPENDING: self._import_imcomes_and_spendings,
            FOF.TRANSFERS: self._import_transfers,
            FOF.TRADES: self._import_trades,
            FOF.ASSET_PAYMENTS: self._import_asset_payments,
            FOF.CORP_ACTIONS: self._import_corporate_actons
        }
        
        for section in sections:
            if section in self._data and sections[section]:
                sections[section](self._data[section])
        for section in self._data:
            if section not in sections:
                logging.warning(g_tr("Statement", "Section is not supported: ") + section)

    def _import_assets(self, assets):
        for asset in assets:
            if asset['id'] < 0:
                continue
            isin = asset['isin'] if 'isin' in asset else ''
            reg_code = asset['reg_code'] if 'reg_code' in asset else ''
            name = asset['name'] if 'name' in asset else ''
            try:
                source = self._sources[asset['exchange']]
            except KeyError:
                source = MarketDataFeed.NA
            asset_id = JalDB().add_asset(asset['symbol'], name, self._asset_types[asset['type']], isin,
                                         data_source=source, reg_code=reg_code)
            if asset_id:
                old_id, asset['id'] = asset['id'], -asset_id
                self._update_id("asset", old_id, asset_id)
                if asset['type'] == FOF.ASSET_MONEY:
                    self._update_id("currency", old_id, asset_id)
            else:
                raise Statement_ImportError(g_tr('Statement', "Can't create asset: ") + f"{asset}")
    
    def _import_accounts(self, accounts):
        for account in accounts:
            if account['id'] < 0:
                continue
            if account['currency'] > 0:
                raise Statement_ImportError(g_tr('Statement', "Unmatched currency for account: ") + f"{account}")
            account_id = JalDB().add_account(account['number'], -account['currency'])
            if account_id:
                old_id, account['id'] = account['id'], -account_id
                self._update_id("account", old_id, account_id)
            else:
                raise Statement_ImportError(g_tr('Statement', "Can't create account: ") + f"{account}")
    
    def _import_imcomes_and_spendings(self, actions):
        for action in actions:
            if action['account'] > 0:
                raise Statement_ImportError(g_tr('Statement', "Unmatched account for income/spending: ") + f"{action}")
            if action['peer'] > 0:
                raise Statement_ImportError(g_tr('Statement', "Unmatched peer for income/spending: ") + f"{action}")
            peer = JalDB().get_account_bank(-action['account']) if action['account'] == 0 else -action['account']
            if len(action['lines']) != 1:   # FIXME - need support for multilines here
                raise Statement_ImportError(g_tr('Statement', "Unsupported income/spending: ") + f"{action}")
            amount = action['lines'][0]['amount']
            category = -action['lines'][0]['category']
            if category <= 0:
                raise Statement_ImportError(g_tr('Statement', "Unmatched category for income/spending: ") + f"{action}")
            description = action['lines'][0]['description']
            JalDB().add_cash_transaction(-action['account'], peer, action['timestamp'], amount, category, description)
    
    def _import_transfers(self, transfers):
        for transfer in transfers:
            for account in transfer['account']:
                if account > 0:
                    raise Statement_ImportError(g_tr('Statement', "Unmatched account for transfer: ") + f"{transfer}")
            for asset in transfer['asset']:
                if asset > 0:
                    raise Statement_ImportError(g_tr('Statement', "Unmatched asset for transfer: ") + f"{asset}")
            if transfer['account'][0] == 0 or transfer['account'][1] == 0:
                text = ''
                pair_account = 1
                if "pytest" not in sys.modules:  # add dividends from database if we are in production
                    if transfer['account'][0] == 0:  # Deposit
                        text = g_tr('Statement', "Deposit of ") + f"{transfer['deposit']:.2f} " + \
                               f"{JalDB().get_asset_name(-transfer['asset'][1])} " + \
                               f"@{datetime.utcfromtimestamp(transfer['timestamp']).strftime('%d.%m.%Y')}\n" + \
                               g_tr('Statement', "Select account to withdraw from:")
                        pair_account = transfer['account'][1]
                    if transfer['account'][1] == 0:  # Withdrawal
                        text = g_tr('Statement', "Withdrawal of ") + f"{transfer['withdrawal']:.2f} " + \
                               f"{JalDB().get_asset_name(-transfer['asset'][0])} " + \
                               f"@{datetime.utcfromtimestamp(transfer['timestamp']).strftime('%d.%m.%Y')}\n" + \
                               g_tr('Statement', "Select account to deposit to:")
                        pair_account = transfer['account'][0]
                    pair_account = self.select_account(text, pair_account, self._last_selected_account)
                if pair_account == 0:
                    raise Statement_ImportError(g_tr('Statement', "Account not selected"))
                self._last_selected_account = pair_account
                if transfer['account'][0] == 0:
                    transfer['account'][0] = -pair_account
                if transfer['account'][1] == 0:
                    transfer['account'][1] = -pair_account

            description = transfer['description'] if 'description' in transfer else ''
            JalDB().add_transfer(transfer['timestamp'], -transfer['account'][0], transfer['withdrawal'],
                                 -transfer['account'][1], transfer['deposit'],
                                 -transfer['account'][2], transfer['fee'], description)

    def _import_trades(self, trades):
        for trade in trades:
            if trade['account'] > 0:
                raise Statement_ImportError(g_tr('Statement', "Unmatched account for trade: ") + f"{trade}")
            if trade['asset'] > 0:
                raise Statement_ImportError(g_tr('Statement', "Unmatched asset for trade: ") + f"{trade}")
            note = trade['note'] if 'note' in trade else ''
            JalDB().add_trade(-trade['account'], -trade['asset'], trade['timestamp'], trade['settlement'],
                              trade['number'], trade['quantity'], trade['price'], trade['fee'], note)

    def _import_asset_payments(self, payments):
        pass

    def _import_corporate_actons(self, actions):
        pass

    def select_account(self, text, account_id, recent_account_id=0):
        dialog = SelectAccountDialog(text, account_id, recent_account=recent_account_id)
        if dialog.exec_() != QDialog.Accepted:
            return 0
        else:
            return dialog.account_id
