import json
from jsonschema import validate
from jsonschema.exceptions import ValidationError
import sys
import os
import logging
from datetime import datetime, timezone
from collections import defaultdict

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox
from jal.constants import Setup, MarketDataFeed, PredefinedAsset, DividendSubtype, CorporateAction
from jal.db.helpers import account_last_date, get_app_path
from jal.db.db import JalDB
from jal.widgets.account_select import SelectAccountDialog


class FOF:
    PERIOD = "period"
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

    def __init__(self):
        pass

    @staticmethod
    def convert_predefined_asset_type(asset_type):
        asset_types = {
            PredefinedAsset.Stock: FOF.ASSET_STOCK,
            PredefinedAsset.Bond: FOF.ASSET_BOND,
            PredefinedAsset.ETF: FOF.ASSET_ETF,
            PredefinedAsset.Derivative: FOF.ASSET_FUTURES
        }
        return asset_types[asset_type]


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
        FOF.ASSET_WARRANT: PredefinedAsset.Derivative,
    }
    _corp_actions = {
        FOF.ACTION_MERGER: CorporateAction.Merger,
        FOF.ACTION_SPLIT: CorporateAction.Split,
        FOF.ACTION_SPINOFF: CorporateAction.SpinOff,
        FOF.ACTION_SYMBOL_CHANGE: CorporateAction.SymbolChange,
        FOF.ACTION_STOCK_DIVIDEND: CorporateAction.StockDividend
    }
    _sources = {
        'NYSE': MarketDataFeed.US,
        'ARCA': MarketDataFeed.US,
        'NASDAQ': MarketDataFeed.US,
        'TSE': MarketDataFeed.CA,
        'SBF': MarketDataFeed.EU,
        'AMEX': MarketDataFeed.US,
        'MOEX': MarketDataFeed.RU
    }
    
    def __init__(self):
        self._data = {}
        self._previous_accounts = {}
        self._last_selected_account = None
        self._section_loaders = {
            FOF.PERIOD: self._check_period,
            FOF.ASSETS: self._import_assets,
            FOF.ACCOUNTS: self._import_accounts,
            FOF.INCOME_SPENDING: self._import_imcomes_and_spendings,
            FOF.TRANSFERS: self._import_transfers,
            FOF.TRADES: self._import_trades,
            FOF.ASSET_PAYMENTS: self._import_asset_payments,
            FOF.CORP_ACTIONS: self._import_corporate_actions
        }

    def tr(self, text):
        return QApplication.translate("Statement", text)

        # returns tuple (start_timestamp, end_timestamp)
    def period(self):
        if FOF.PERIOD in self._data:
            return self._data[FOF.PERIOD][0], self._data[FOF.PERIOD][1]
        else:
            return 0, 0

    # returns timestamp that is equal to the last second of initial timestamp
    def _end_of_date(self, timestamp) -> int:
        end_of_day = datetime.utcfromtimestamp(timestamp).replace(hour=23, minute=59, second=59)
        return int(end_of_day.replace(tzinfo=timezone.utc).timestamp())

    # Loads JSON statement format from file defined by 'filename'
    def load(self, filename: str) -> None:
        self._data = {}
        try:
            with open(filename, 'r') as exchange_file:
                try:
                    self._data = json.load(exchange_file)
                except json.JSONDecodeError:
                    logging.error(self.tr("Failed to read JSON from file: ") + filename)
        except Exception as err:
            raise Statement_ImportError(self.tr("Failed to read file: ") + str(err))
        unsupported_sections = [x for x in self._data if x not in self._section_loaders]
        if unsupported_sections:
            for section in unsupported_sections:
                self._data.pop(section)
            logging.warning(self.tr("Some sections are not supported: ") + unsupported_sections)

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
            country_code = asset['country'] if 'country' in asset else ''
            expiry = asset['expiry'] if 'expiry' in asset else 0
            asset_id = JalDB().get_asset_id(asset['symbol'], isin=isin, reg_code=reg_code, name=name, expiry=expiry,
                                            dialog_new=verbal)
            if asset_id is not None:
                JalDB().update_asset_data(asset_id, asset['symbol'], isin, reg_code, country_code)
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

    # Replace 'old_value' with 'new_value' in keys 'tag_name' of sections listed in mutable_sections
    def _update_id(self, tag_name, old_value, new_value):
        mutable_sections = [FOF.ACCOUNTS, FOF.ASSETS, FOF.TRADES, FOF.TRANSFERS, FOF.CORP_ACTIONS, FOF.ASSET_PAYMENTS,
                            FOF.INCOME_SPENDING]
        for section in mutable_sections:
            for element in self._data[section]:
                for tag in element:
                    if tag == tag_name:
                        if type(element[tag]) == list:
                            element[tag] = [-new_value if x == old_value else x for x in element[tag]]
                        else:
                            element[tag] = -new_value if element[tag] == old_value else element[tag]

    def validate_format(self):
        schema_name = get_app_path() + Setup.IMPORT_PATH + os.sep + Setup.IMPORT_SCHEMA_NAME
        try:
            with open(schema_name, 'r') as schema_file:
                try:
                    statement_schema = json.load(schema_file)
                except json.JSONDecodeError:
                    raise Statement_ImportError(self.tr("Failed to read JSON schema from: ") + schema_name)
        except Exception as err:
            raise Statement_ImportError(self.tr("Failed to read file: ") + str(err))
        try:
            validate(instance=self._data, schema=statement_schema)
        except ValidationError:
            raise Statement_ImportError(self.tr("Statement validation failed"))

    # Store content of JSON statement into database
    # Returns a dict of dict with amounts:
    # { account_1: { asset_1: X, asset_2: Y, ...}, account_2: { asset_N: Z, ...}, ... }
    def import_into_db(self):
        for section in self._section_loaders:
            if section in self._data:
                self._section_loaders[section](self._data[section])

        totals = defaultdict(dict)
        for account in self._data[FOF.ACCOUNTS]:
            if 'cash_end' in account:
                totals[-account['id']][-account['currency']] = account['cash_end']
        return totals

    def _check_period(self, period):
        if len(period) != 2:
            logging.warning(self.tr("Statement period is invalid"))
        if not FOF.ACCOUNTS in self._data:
            return
        accounts = self._data[FOF.ACCOUNTS]
        for account in accounts:
            if account['id'] < 0:  # Checks if report is after last transaction recorded for account.
                if period[0] < account_last_date(-account['id']):
                    if QMessageBox().warning(None, self.tr("Confirmation"),
                                             self.tr("Statement period starts before last recorded operation for the account. Continue import?"),
                                             QMessageBox.Yes, QMessageBox.No) == QMessageBox.No:
                        raise Statement_ImportError(self.tr("Statement import was cancelled"))

    def _import_assets(self, assets):
        for asset in assets:
            if asset['id'] < 0:
                continue
            isin = asset['isin'] if 'isin' in asset else ''
            reg_code = asset['reg_code'] if 'reg_code' in asset else ''
            name = asset['name'] if 'name' in asset else ''
            country_code = asset['country'] if 'country' in asset else ''
            expiry = asset['expiry'] if 'expiry' in asset else 0
            try:
                source = self._sources[asset['exchange']]
            except KeyError:
                source = MarketDataFeed.NA
            asset_id = JalDB().add_asset(asset['symbol'], name, self._asset_types[asset['type']], isin, expiry=expiry,
                                         data_source=source, reg_code=reg_code, country_code=country_code)
            if asset_id:
                old_id, asset['id'] = asset['id'], -asset_id
                self._update_id("asset", old_id, asset_id)
                if asset['type'] == FOF.ASSET_MONEY:
                    self._update_id("currency", old_id, asset_id)
            else:
                raise Statement_ImportError(self.tr("Can't create asset: ") + f"{asset}")
    
    def _import_accounts(self, accounts):
        for account in accounts:
            if account['id'] < 0:
                continue
            if account['currency'] > 0:
                raise Statement_ImportError(self.tr("Unmatched currency for account: ") + f"{account}")
            account_id = JalDB().add_account(account['number'], -account['currency'])
            if account_id:
                old_id, account['id'] = account['id'], -account_id
                self._update_id("account", old_id, account_id)
            else:
                raise Statement_ImportError(self.tr("Can't create account: ") + f"{account}")
    
    def _import_imcomes_and_spendings(self, actions):
        for action in actions:
            if action['account'] > 0:
                raise Statement_ImportError(self.tr("Unmatched account for income/spending: ") + f"{action}")
            if action['peer'] > 0:
                raise Statement_ImportError(self.tr("Unmatched peer for income/spending: ") + f"{action}")
            peer = JalDB().get_account_bank(-action['account']) if action['peer'] == 0 else -action['peer']
            if len(action['lines']) != 1:   # FIXME - need support for multilines here
                raise Statement_ImportError(self.tr("Unsupported income/spending: ") + f"{action}")
            amount = action['lines'][0]['amount']
            category = -action['lines'][0]['category']
            if category <= 0:
                raise Statement_ImportError(self.tr("Unmatched category for income/spending: ") + f"{action}")
            description = action['lines'][0]['description']
            JalDB().add_cash_transaction(-action['account'], peer, action['timestamp'], amount, category, description)
    
    def _import_transfers(self, transfers):
        for transfer in transfers:
            for account in transfer['account']:
                if account > 0:
                    raise Statement_ImportError(self.tr("Unmatched account for transfer: ") + f"{transfer}")
            for asset in transfer['asset']:
                if asset > 0:
                    raise Statement_ImportError(self.tr("Unmatched asset for transfer: ") + f"{transfer}")
            if transfer['account'][0] == 0 or transfer['account'][1] == 0:
                text = ''
                pair_account = 1
                if transfer['account'][0] == 0:  # Deposit
                    text = self.tr("Deposit of ") + f"{transfer['deposit']:.2f} " + \
                           f"{JalDB().get_asset_name(-transfer['asset'][1])} " + \
                           f"@{datetime.utcfromtimestamp(transfer['timestamp']).strftime('%d.%m.%Y')}\n" + \
                           self.tr("Select account to withdraw from:")
                    pair_account = -transfer['account'][1]
                if transfer['account'][1] == 0:  # Withdrawal
                    text = self.tr("Withdrawal of ") + f"{transfer['withdrawal']:.2f} " + \
                           f"{JalDB().get_asset_name(-transfer['asset'][0])} " + \
                           f"@{datetime.utcfromtimestamp(transfer['timestamp']).strftime('%d.%m.%Y')}\n" + \
                           self.tr("Select account to deposit to:")
                    pair_account = -transfer['account'][0]
                try:
                    chosen_account = self._previous_accounts[JalDB().get_account_currency(pair_account)]
                except KeyError:
                    chosen_account = self.select_account(text, pair_account, self._last_selected_account)
                if chosen_account == 0:
                    raise Statement_ImportError(self.tr("Account not selected"))
                self._last_selected_account = chosen_account
                if transfer['account'][0] == 0:
                    transfer['account'][0] = -chosen_account
                if transfer['account'][1] == 0:
                    transfer['account'][1] = -chosen_account

            description = transfer['description'] if 'description' in transfer else ''
            JalDB().add_transfer(transfer['timestamp'], -transfer['account'][0], transfer['withdrawal'],
                                 -transfer['account'][1], transfer['deposit'],
                                 -transfer['account'][2], transfer['fee'], description)

    def _import_trades(self, trades):
        for trade in trades:
            if trade['account'] > 0:
                raise Statement_ImportError(self.tr("Unmatched account for trade: ") + f"{trade}")
            if trade['asset'] > 0:
                raise Statement_ImportError(self.tr("Unmatched asset for trade: ") + f"{trade}")
            note = trade['note'] if 'note' in trade else ''
            if 'cancelled' in trade and trade['cancelled']:
                JalDB().del_trade(-trade['account'], -trade['asset'], trade['timestamp'], trade['settlement'],
                                  trade['number'], trade['quantity'], trade['price'], trade['fee'])
                continue
            JalDB().add_trade(-trade['account'], -trade['asset'], trade['timestamp'], trade['settlement'],
                              trade['number'], trade['quantity'], trade['price'], trade['fee'], note)

    def _import_asset_payments(self, payments):
        for payment in payments:
            if payment['account'] > 0:
                raise Statement_ImportError(self.tr("Unmatched account for payment: ") + f"{payment}")
            if payment['asset'] > 0:
                raise Statement_ImportError(self.tr("Unmatched asset for payment: ") + f"{payment}")
            tax = payment['tax'] if 'tax' in payment else 0
            if payment['type'] == FOF.PAYMENT_DIVIDEND:
                if payment['id'] > 0:  # New dividend
                    JalDB().add_dividend(DividendSubtype.Dividend, payment['timestamp'], -payment['account'],
                                         -payment['asset'], payment['amount'], payment['description'], tax=tax)
                else:  # Dividend exists, only tax to be updated
                    JalDB().update_dividend_tax(-payment['id'], payment['tax'])
            elif payment['type'] == FOF.PAYMENT_INTEREST:
                if 'number' not in payment:
                    payment['number'] = ''
                JalDB().add_dividend(DividendSubtype.BondInterest, payment['timestamp'], -payment['account'],
                                     -payment['asset'], payment['amount'], payment['description'], payment['number'],
                                     tax=tax)
            else:
                raise Statement_ImportError(self.tr("Unsupported payment type: ") + f"{payment}")

    def _import_corporate_actions(self, actions):
        for action in actions:
            if action['account'] > 0:
                raise Statement_ImportError(self.tr("Unmatched account for corporate action: ") + f"{action}")
            if type(action['asset']) == list:
                asset_old = -action['asset'][0]
                asset_new = -action['asset'][1]
            else:
                asset_old = asset_new = -action['asset']
            if asset_old < 0 or asset_new < 0:
                raise Statement_ImportError(self.tr("Unmatched asset for corporate action: ") + f"{action}")
            if type(action['quantity']) == list:
                qty_old = action['quantity'][0]
                qty_new = action['quantity'][1]
            else:
                qty_old = -1
                qty_new = action['quantity']
            try:
                action_type = self._corp_actions[action['type']]
            except KeyError:
                raise Statement_ImportError(self.tr("Unsupported corporate action: ") + f"{action}")
            JalDB().add_corporate_action(-action['account'], action_type, action['timestamp'], action['number'],
                                         asset_old, qty_old, asset_new, qty_new,
                                         action['cost_basis'], action['description'])

    def select_account(self, text, account_id, recent_account_id=0):
        if "pytest" in sys.modules:
            return 1    # Always return 1st account if we are in testing mode
        dialog = SelectAccountDialog(text, account_id, recent_account=recent_account_id)
        if dialog.exec() != QDialog.Accepted:
            return 0
        else:
            if dialog.store_account:
                self._previous_accounts[JalDB().get_account_currency(dialog.account_id)] = dialog.account_id
            return dialog.account_id
