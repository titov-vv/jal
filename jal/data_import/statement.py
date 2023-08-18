import json
from jsonschema import validate
from jsonschema.exceptions import ValidationError
import sys
import os
import logging
from datetime import datetime, timezone
from decimal import Decimal
from collections import defaultdict

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QDialog, QMessageBox
from jal.constants import Setup, MarketDataFeed, PredefinedAsset, PredefinedAccountType
from jal.db.helpers import get_app_path
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.operations import LedgerTransaction, Dividend, CorporateAction
from jal.widgets.helpers import ts2d
from jal.widgets.account_select import SelectAccountDialog
from jal.net.downloader import QuoteDownloader


class FOF:
    PERIOD = "period"
    ACCOUNTS = "accounts"
    ASSETS = "assets"
    SYMBOLS = "symbols"
    ASSETS_DATA = "assets_data"
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
    ASSET_RIGHTS = "right"
    ASSET_CRYPTO = "crypto"
    ASSET_CFD = "cfd"

    ACTION_MERGER = "merger"
    ACTION_SPLIT = "split"
    ACTION_SPINOFF = "spin-off"
    ACTION_SYMBOL_CHANGE = "symbol_change"
    ACTION_BOND_MATURITY = "bond_maturity"    # Isn't used in reality as will be put as ordinary sell operation
    ACTION_DELISTING = "delisting"
    ACTION_RIGHTS_ISSUE = "rights_issue"      # Not in use as doesn't create any financial consequences

    PAYMENT_DIVIDEND = "dividend"
    PAYMENT_INTEREST = "interest"
    PAYMENT_STOCK_DIVIDEND = "stock_dividend"
    PAYMENT_STOCK_VESTING = 'stock_vesting'

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

# Possible statement module capabilities
class Statement_Capabilities:
    MULTIPLE_LOAD = 1


# -----------------------------------------------------------------------------------------------------------------------
class Statement(QObject):   # derived from QObject to have proper string translation
    RU_PRICE_TOLERANCE = 1e-4   # TODO Probably need to switch imports to Decimal and remove it

    _asset_types = {
        FOF.ASSET_MONEY: PredefinedAsset.Money,
        FOF.ASSET_STOCK: PredefinedAsset.Stock,
        FOF.ASSET_ADR: PredefinedAsset.Stock,
        FOF.ASSET_ETF: PredefinedAsset.ETF,
        FOF.ASSET_BOND: PredefinedAsset.Bond,
        FOF.ASSET_FUTURES: PredefinedAsset.Derivative,
        FOF.ASSET_OPTION: PredefinedAsset.Derivative,
        FOF.ASSET_WARRANT: PredefinedAsset.Derivative,
        FOF.ASSET_CFD: PredefinedAsset.Derivative,
        FOF.ASSET_CRYPTO: PredefinedAsset.Crypto
    }
    _corp_actions = {
        FOF.ACTION_MERGER: CorporateAction.Merger,
        FOF.ACTION_SPLIT: CorporateAction.Split,
        FOF.ACTION_SPINOFF: CorporateAction.SpinOff,
        FOF.ACTION_SYMBOL_CHANGE: CorporateAction.SymbolChange,
        FOF.ACTION_DELISTING: CorporateAction.Delisting
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
        super().__init__()
        self._data = {}
        self._previous_accounts = {}
        self._last_selected_account = None
        self._section_loaders = {
            FOF.PERIOD: self._check_period,
            FOF.ASSETS: self._import_assets,
            FOF.SYMBOLS: self._import_symbol_tickers,
            FOF.ASSETS_DATA: self._import_asset_data,
            FOF.ACCOUNTS: self._import_accounts,
            FOF.INCOME_SPENDING: self._import_imcomes_and_spendings,
            FOF.TRANSFERS: self._import_transfers,
            FOF.TRADES: self._import_trades,
            FOF.ASSET_PAYMENTS: self._import_asset_payments,
            FOF.CORP_ACTIONS: self._import_corporate_actions
        }

    # If 'debug_info' is given as parameter it is saved in JAL main directory text file appened with timestamp
    def save_debug_info(self, **kwargs):
        if 'debug_info' in kwargs:
            dump_name = get_app_path() + os.sep + Setup.STATEMENT_DUMP + datetime.now().strftime("%y-%m-%d_%H-%M-%S") + ".txt"
            try:
                with open(dump_name, 'w') as dump_file:
                    dump_file.write(f"JAL statement dump, {datetime.now().strftime('%y/%m/%d %H:%M:%S')}\n")
                    dump_file.write("----------------------------------------------------------------\n")
                    dump_file.write(str(kwargs['debug_info']))
                logging.warning(self.tr("Debug information is saved in ") + dump_name)
            except Exception as e:
                logging.error(self.tr("Failed to write statement dump into: ") + dump_name + ": " + str(e))

    # Returns a specific capabilities that is supported by some statement modules
    @staticmethod
    def capabilities() -> set:
        return set()

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

    # Finds an account in jal database and returns its id
    def _map_db_account(self, account_id: int) -> int:
        account = [x for x in self._data[FOF.ACCOUNTS] if x["id"] == account_id][0]
        currency_symbol = [x for x in self._data[FOF.SYMBOLS] if x["asset"] == account['currency']][0]['symbol']
        db_currency = JalAsset(data={'symbol': currency_symbol, 'type': PredefinedAsset.Money}, search=True, create=False).id()
        db_account = JalAccount(data={'number': account['number'], 'currency': db_currency}, search=True, create=False).id()
        return db_account

    # Finds an asset in jal database and returns its id
    def _map_db_asset(self, asset_id: int) -> int:
        asset = self._asset(asset_id)
        isin = asset['isin'] if 'isin' in asset else ''
        symbols = [x for x in self._data[FOF.SYMBOLS] if x["asset"] == asset_id]
        db_asset = JalAsset(data={'isin': isin, 'symbol': symbols[0]['symbol']}, search=True, create=False).id()
        return db_asset

    # Loads JSON statement format from file defined by 'filename'
    def load(self, filename: str) -> None:
        self._data = {}
        try:
            with open(filename, 'r', encoding='utf-8') as exchange_file:
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
            logging.warning(self.tr("Some sections are not supported: ") + f"{unsupported_sections}")

    # check are assets and accounts from self._data present in database
    # replace IDs in self._data with IDs from database (DB IDs will be negative, initial IDs will be positive)
    def match_db_ids(self):
        self._match_currencies()
        self._match_asset_isin()
        self._match_asset_reg_number()
        self._match_asset_symbol()
        self._match_account_ids()

    def _match_currencies(self):
        for asset in self._data[FOF.ASSETS]:
            if asset['type'] != FOF.ASSET_MONEY:
                continue
            symbol = self._find_in_list(self._data[FOF.SYMBOLS], "asset", asset['id'])
            asset_id = JalAsset(data={'symbol': symbol['symbol'], 'type': self._asset_types[asset['type']]},
                                search=True, create=False).id()
            if asset_id:
                symbol['asset'] = -asset_id
                old_id, asset['id'] = asset['id'], -asset_id
                self._update_id("currency", old_id, asset_id)
                self._update_id("asset", old_id, asset_id)     # TRANSFERS section may have currency in asset list

    # Check and replace IDs for Assets matched by isin
    def _match_asset_isin(self):
        for asset in self._data[FOF.ASSETS]:
            if asset['id'] < 0:  # already matched
                continue
            if 'isin' in asset:
                asset_id = JalAsset(data={'isin': asset['isin']}, search=True, create=False).id()
                if asset_id:
                    old_id, asset['id'] = asset['id'], -asset_id
                    self._update_id("asset", old_id, asset_id)

    # Check and replace IDs for Assets matched by reg_number
    def _match_asset_reg_number(self):
        for asset in self._data[FOF.ASSETS_DATA]:
            if asset['asset'] < 0:  # already matched
                continue
            if 'reg_number' in asset:
                asset_id = JalAsset(data={'reg_number': asset['reg_number']}, search=True, create=False).id()
                if asset_id:
                    asset = self._find_in_list(self._data[FOF.ASSETS], "id", asset['asset'])
                    old_id, asset['id'] = asset['id'], -asset_id
                    self._update_id("asset", old_id, asset_id)

    def _match_asset_symbol(self):
        for symbol in self._data[FOF.SYMBOLS]:
            if symbol['asset'] < 0:  # already matched
                continue
            asset = self._find_in_list(self._data[FOF.ASSETS], "id", symbol['asset'])
            search_data = {'symbol': symbol['symbol'], 'type': self._asset_types[asset['type']]}
            self._uppend_keys_from(search_data, asset, ['isin'])
            data = self._find_in_list(self._data[FOF.ASSETS_DATA], "asset", symbol['asset'])
            reg_number = ''
            if data is not None:
                self._uppend_keys_from(search_data, data, ['expiry'])
                reg_number = data['reg_number'] if 'reg_number' in data else ''
            db_asset = JalAsset(data=search_data, search=True, create=False)
            db_id = db_asset.id()
            if db_id:
                if db_asset.isin() and 'isin' in asset and asset['isin'] and db_asset.isin() != asset['isin']:
                    continue  # verify that we don't have ISIN mismatch
                if db_asset.reg_number() and reg_number and db_asset.reg_number() != reg_number:
                    continue  # verify that we don't have reg.number mismatch
                old_id, asset['id'] = asset['id'], -db_id
                self._update_id("asset", old_id, db_id)

    # Check and replace IDs for Accounts
    def _match_account_ids(self):
        for account in self._data[FOF.ACCOUNTS]:
            account_data = account.copy()
            account_data['currency'] = -account['currency']
            account_id = JalAccount(data=account_data, search=True, create=False).id()
            if account_id:
                old_id, account['id'] = account['id'], -account_id
                self._update_id("account", old_id, account_id)

    # Replace 'old_value' with 'new_value' in keys 'tag_name' of sections listed in mutable_sections
    def _update_id(self, tag_name, old_value, new_value):
        mutable_sections = [FOF.ACCOUNTS, FOF.ASSETS, FOF.SYMBOLS, FOF.ASSETS_DATA, FOF.TRADES, FOF.TRANSFERS,
                            FOF.CORP_ACTIONS, FOF.ASSET_PAYMENTS, FOF.INCOME_SPENDING]
        for section in mutable_sections:
            if section not in self._data:
                continue
            for element in self._data[section]:
                if self._key_match(element, tag_name, old_value):
                    if type(element[tag_name]) == list:
                        element[tag_name] = [-new_value if x == old_value else x for x in element[tag_name]]
                    else:
                        element[tag_name] = -new_value if element[tag_name] == old_value else element[tag_name]
        for element in self._data[FOF.CORP_ACTIONS]:  # Corporate actions have 'outcome' subsection with assets
            for item in element['outcome']:
                if self._key_match(item, tag_name, old_value):
                    item[tag_name] = -new_value if item[tag_name] == old_value else item[tag_name]

    # Deletes element if it's 'tag_name' key matches 'value'
    def _delete_with_id(self, tag_name, value):
        mutable_sections = [FOF.ACCOUNTS, FOF.ASSETS, FOF.SYMBOLS, FOF.ASSETS_DATA, FOF.TRADES, FOF.TRANSFERS,
                            FOF.CORP_ACTIONS, FOF.ASSET_PAYMENTS, FOF.INCOME_SPENDING]
        for section in mutable_sections:
            self._data[section] = [x for x in self._data[section] if not self._key_match(x, tag_name, value)]

    # returns True if dictionary 'element' has 'key' that matches 'value' or is a list with 'value'
    def _key_match(self, element, key, value):
        for tag in element:
            if tag == key:
                if type(element[tag]) == list:
                    for x in element[tag]:
                        if x == value:
                            return True
                else:
                    if element[tag] == value:
                        return True
        return False

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
            raise Statement_ImportError(self.tr("Statement period is invalid"))
        if FOF.ACCOUNTS not in self._data:
            return
        accounts = self._data[FOF.ACCOUNTS]
        for account in accounts:
            if account['id'] < 0:  # Checks if report is after last transaction recorded for account.
                if period[0] < JalAccount(-account['id']).last_operation_date():
                    if QMessageBox().warning(None, self.tr("Confirmation"),
                                             self.tr("Statement period starts before last recorded operation for the account. Continue import?"),
                                             QMessageBox.Yes, QMessageBox.No) == QMessageBox.No:
                        raise Statement_ImportError(self.tr("Statement import was cancelled"))

    def _import_assets(self, assets):
        for asset in assets:
            if asset['id'] < 0:
                JalAsset(-asset['id']).update_data(asset)
                continue
            asset_data = asset.copy()
            asset_data['type'] = self._asset_types[asset_data['type']]
            new_asset = JalAsset(data=asset_data, search=False, create=True)
            if new_asset.id():
                old_id, asset['id'] = asset['id'], -new_asset.id()
                self._update_id("asset", old_id, new_asset.id())
                if asset['type'] == FOF.ASSET_MONEY:
                    self._update_id("currency", old_id, new_asset.id())
            else:
                raise Statement_ImportError(self.tr("Can't create asset: ") + f"{asset}")

    def _import_symbol_tickers(self, symbols):
        for symbol in symbols:
            if symbol['asset'] > 0:
                raise Statement_ImportError(self.tr("Symbol ticker isn't linked to asset: ") + f"{symbol}")
            if 'currency' in symbol and symbol['currency'] > 0:
                raise Statement_ImportError(self.tr("Symbol currency isn't linked to asset: ") + f"{symbol}")
            asset = self._find_in_list(self._data[FOF.ASSETS], "id", symbol['asset'])
            note = symbol['note'] if 'note' in symbol else ''
            if asset['type'] == FOF.ASSET_MONEY:
                currency = None
                source = MarketDataFeed.FX
            else:
                currency = -symbol['currency']
                try:
                    source = self._sources[symbol['note']]
                except KeyError:
                    source = MarketDataFeed.NA
            JalAsset(-symbol['asset']).add_symbol(symbol['symbol'], currency, note, data_source=source)

    def _import_asset_data(self, data):
        for detail in data:
            if detail['asset'] > 0:
                raise Statement_ImportError(self.tr("Asset data aren't linked to asset: ") + f"{detail}")
            JalAsset(-detail['asset']).update_data(detail)
    
    def _import_accounts(self, accounts):
        for account in accounts:
            if account['id'] < 0:
                continue
            if account['currency'] > 0:
                raise Statement_ImportError(self.tr("Unmatched currency for account: ") + f"{account}")
            account_data = account.copy()
            account_data['type'] = PredefinedAccountType.Investment if 'type' not in account_data else account_data['type']
            account_data['currency'] = -account_data['currency']  # all currencies are already in db
            new_account = JalAccount(data=account_data, search=True, create=True)
            if new_account.id():
                old_id, account['id'] = account['id'], -new_account.id()
                self._update_id("account", old_id, new_account.id())
            else:
                raise Statement_ImportError(self.tr("Can't create account: ") + f"{account}")
    
    def _import_imcomes_and_spendings(self, actions):
        for action in actions:
            if action['account'] > 0:
                raise Statement_ImportError(self.tr("Unmatched account for income/spending: ") + f"{action}")
            action['account_id'] = -action.pop('account')
            if action['peer'] > 0:
                raise Statement_ImportError(self.tr("Unmatched peer for income/spending: ") + f"{action}")
            action['peer_id'] = -action.pop('peer')
            if action['peer_id'] == 0:
                action['peer_id'] = JalAccount(action['account_id']).organization()
            for line in action['lines']:
                if line['category'] >= 0:
                    raise Statement_ImportError(self.tr("Unmatched category for income/spending: ") + f"{action}")
                line['category_id'] = -line.pop('category')
                line['note'] = line.pop('description')
            LedgerTransaction.create_new(LedgerTransaction.IncomeSpending, action)
    
    def _import_transfers(self, transfers):
        for transfer in transfers:
            for account in transfer['account']:
                if account > 0:
                    raise Statement_ImportError(self.tr("Unmatched account for transfer: ") + f"{transfer}")
            for asset in transfer['asset']:
                if asset > 0:
                    raise Statement_ImportError(self.tr("Unmatched asset for transfer: ") + f"{transfer}")
            asset_types = [JalAsset(-x).type() for x in transfer['asset']]
            if asset_types[0] != asset_types[1]:
                raise Statement_ImportError(self.tr("Impossible to convert asset type in transfer: ") + f"{transfer}")
            if transfer['account'][0] == 0 or transfer['account'][1] == 0:
                text = ''
                pair_account = 1
                if transfer['account'][0] == 0:  # Deposit
                    text = self.tr("Deposit of ") + f"{transfer['deposit']:.2f} " + \
                           f"{JalAsset(-transfer['asset'][1]).symbol()} @{ts2d(transfer['timestamp'])}\n" + \
                           self.tr("Select account to withdraw from:")
                    pair_account = -transfer['account'][1]
                if transfer['account'][1] == 0:  # Withdrawal
                    text = self.tr("Withdrawal of ") + f"{transfer['withdrawal']:.2f} " + \
                           f"{JalAsset(-transfer['asset'][0]).symbol()} @{ts2d(transfer['timestamp'])}\n" + \
                           self.tr("Select account to deposit to:")
                    pair_account = -transfer['account'][0]
                try:
                    chosen_account = self._previous_accounts[JalAccount(pair_account).currency()]
                except KeyError:
                    chosen_account = self.select_account(text, pair_account, self._last_selected_account)
                if chosen_account == 0:
                    raise Statement_ImportError(self.tr("Account not selected"))
                self._last_selected_account = chosen_account
                if transfer['account'][0] == 0:
                    transfer['account'][0] = -chosen_account
                if transfer['account'][1] == 0:
                    transfer['account'][1] = -chosen_account
            if asset_types[0] != PredefinedAsset.Money:
                transfer['asset'] = -transfer['asset'][0]
            else:
                transfer.pop('asset')
            if 'description' in transfer:
                transfer['note'] = transfer.pop('description')
            transfer['withdrawal_timestamp'] = transfer['deposit_timestamp'] = transfer.pop('timestamp')
            transfer['withdrawal_account'] = -transfer['account'][0]
            transfer['deposit_account'] = -transfer['account'][1]
            transfer['fee_account'] = -transfer['account'][2]
            transfer.pop('account')
            if abs(transfer['fee']) < 1e-10:  # FIXME  Need to refactor this module for decimal usage
                transfer.pop('fee_account')
                transfer.pop('fee')
            LedgerTransaction.create_new(LedgerTransaction.Transfer, transfer)

    def _import_trades(self, trades):
        for trade in trades:
            if trade['account'] > 0:
                raise Statement_ImportError(self.tr("Unmatched account for trade: ") + f"{trade}")
            trade['account_id'] = -trade.pop('account')
            if trade['asset'] > 0:
                raise Statement_ImportError(self.tr("Unmatched asset for trade: ") + f"{trade}")
            trade['asset_id'] = -trade.pop('asset')
            trade['qty'] = trade.pop('quantity')
            if 'cancelled' in trade and trade['cancelled']:
                del trade['cancelled']          # Remove extra data
                trade['qty'] = -trade['qty']    # Change side as cancellation is an opposite operation
                oid = LedgerTransaction().find_operation(LedgerTransaction.Trade, trade)
                if oid:
                    LedgerTransaction.get_operation(LedgerTransaction.Trade, oid).delete()
                continue
            LedgerTransaction.create_new(LedgerTransaction.Trade, trade)

    def _import_asset_payments(self, payments):
        for payment in payments:
            if payment['account'] > 0:
                raise Statement_ImportError(self.tr("Unmatched account for payment: ") + f"{payment}")
            payment['account_id'] = -payment.pop('account')
            if payment['asset'] > 0:
                raise Statement_ImportError(self.tr("Unmatched asset for payment: ") + f"{payment}")
            payment['asset_id'] = -payment.pop('asset')
            payment['note'] = payment.pop('description')
            if 'price' in payment:
                JalAsset(payment['asset_id']).set_quotes(
                    [{'timestamp': payment['timestamp'], 'quote': Decimal(payment.pop('price'))}],
                    JalAccount(payment['account_id']).currency())
            if payment['type'] == FOF.PAYMENT_DIVIDEND:
                if payment['id'] > 0:  # New dividend
                    payment['type'] = Dividend.Dividend
                    LedgerTransaction.create_new(LedgerTransaction.Dividend, payment)
                else:  # Dividend exists, only tax to be updated
                    dividend = LedgerTransaction.get_operation(LedgerTransaction.Dividend, -payment['id'])
                    dividend.update_tax(payment['tax'])
            elif payment['type'] == FOF.PAYMENT_INTEREST:
                payment['type'] = Dividend.BondInterest
                LedgerTransaction.create_new(LedgerTransaction.Dividend, payment)
            elif payment['type'] == FOF.PAYMENT_STOCK_DIVIDEND:
                if payment['id'] > 0:  # New dividend
                    payment['type'] = Dividend.StockDividend
                    LedgerTransaction.create_new(LedgerTransaction.Dividend, payment)
                else:  # Dividend exists, only tax to be updated
                    dividend = LedgerTransaction.get_operation(LedgerTransaction.Dividend, -payment['id'])
                    dividend.update_tax(payment['tax'])
            elif payment['type'] == FOF.PAYMENT_STOCK_VESTING:
                payment['type'] = Dividend.StockVesting
                LedgerTransaction.create_new(LedgerTransaction.Dividend, payment)
            else:
                raise Statement_ImportError(self.tr("Unsupported payment type: ") + f"{payment}")

    def _import_corporate_actions(self, actions):
        for action in actions:
            if action['account'] > 0:
                raise Statement_ImportError(self.tr("Unmatched account for corporate action: ") + f"{action}")
            action['account_id'] = -action.pop('account')
            if action['asset'] > 0:
                raise Statement_ImportError(self.tr("Unmatched asset for corporate action: ") + f"{action}")
            action['asset_id'] = -action.pop('asset')
            action['qty'] = action.pop('quantity')
            action['note'] = action.pop('description')
            for item in action['outcome']:
                if item['asset'] > 0:
                    raise Statement_ImportError(self.tr("Unmatched asset for corporate action: ") + f"{action}")
                item['asset_id'] = -item.pop('asset')
                item['qty'] = item.pop('quantity')
                item['value_share'] = item.pop('share')
            try:
                action['type'] = self._corp_actions[action.pop('type')]
            except KeyError:
                raise Statement_ImportError(self.tr("Unsupported corporate action: ") + f"{action}")
            LedgerTransaction.create_new(LedgerTransaction.CorporateAction, action)

    def select_account(self, text, account_id, recent_account_id=0):
        if "pytest" in sys.modules:
            return 1    # Always return 1st account if we are in testing mode
        dialog = SelectAccountDialog(text, account_id, recent_account=recent_account_id)
        if dialog.exec() != QDialog.Accepted:
            return 0
        else:
            if dialog.store_account:
                self._previous_accounts[JalAccount(dialog.account_id).currency()] = dialog.account_id
            return dialog.account_id

    # Returns asset dictionary by asset id
    def _asset(self, asset_id) -> dict:
        asset = self._find_in_list(self._data[FOF.ASSETS], 'id', asset_id)
        if asset is None:
            raise Statement_ImportError(self.tr("Asset id not found") + f"{asset_id}")
        return asset

    # Helper function that takes list of dictionaries and returns one element where key=value
    # exception is raised if multiple elements found
    # Returns None if nothing was found in the list
    def _find_in_list(self, data_list, key, value):
        filtered = [x for x in data_list if key in x and x[key] == value]
        if filtered:
            if len(filtered) == 1:
                return filtered[0]
            else:
                raise Statement_ImportError(self.tr("Multiple match for ") + f"'{key}'='{value}': {filtered}")

    # Method finds currency in current statement data. New currency is created if no currency was found.
    # Returns currency id
    def currency_id(self, currency_symbol) -> int:
        match = [x for x in self._data[FOF.SYMBOLS] if
                 x['symbol'] == currency_symbol and self._asset(x['asset'])['type'] == FOF.ASSET_MONEY]
        if match:
            if len(match) == 1:
                return match[0]["asset"]
            else:
                raise Statement_ImportError(self.tr("Multiple currency match for ") + f"{currency_symbol}")
        else:
            asset_id = max([0] + [x['id'] for x in self._data[FOF.ASSETS]]) + 1
            self._data[FOF.ASSETS].append({"id": asset_id, "type": "money", "name": ""})
            symbol_id = max([0] + [x['id'] for x in self._data[FOF.SYMBOLS]]) + 1
            currency = {"id": symbol_id, "asset": asset_id, "symbol": currency_symbol}
            self._data[FOF.SYMBOLS].append(currency)
            return asset_id

    # Method finds asset in current statement data. New asset is created if no asset was found.
    # Returns asset id
    def asset_id(self, asset_info) -> int:
        asset = None
        asset_info = {k: v for k, v in asset_info.items() if v}  # drop keys with empty values
        if 'isin' in asset_info:
            asset = self._find_in_list(self._data[FOF.ASSETS], 'isin', asset_info['isin'])
        if asset is None and 'reg_number' in asset_info:
            asset_data = self._find_in_list(self._data[FOF.ASSETS_DATA], 'reg_number', asset_info['reg_number'])
            if asset_data is not None:
                asset = self._find_in_list(self._data[FOF.ASSETS], 'id', asset_data['asset'])
        if asset is None and 'symbol' in asset_info:
            symbol = self._find_in_list(self._data[FOF.SYMBOLS], 'symbol', asset_info['symbol'])
            if symbol is not None:
                asset = self._find_in_list(self._data[FOF.ASSETS], 'id', symbol['asset'])
                if 'isin' in asset and 'isin' in asset_info and asset['isin'] != asset_info['isin']:
                    asset = None
        if asset_info.get('search_offline', False):   # If allowed fetch asset data from database
            db_asset = JalAsset(data=asset_info, search=True, create=False)
            if db_asset.id():
                asset = {'id': -db_asset.id(), 'type': FOF.convert_predefined_asset_type(db_asset.type()), 'name': db_asset.name(), 'isin': db_asset.isin()}
                self._data[FOF.ASSETS].append(asset)
                symbol_id = max([0] + [x['id'] for x in self._data[FOF.SYMBOLS]]) + 1
                symbol = {"id": symbol_id, "asset": -db_asset.id(), 'symbol': db_asset.symbol(asset_info['currency']), 'currency': asset_info['currency']}
                self._data[FOF.SYMBOLS].append(symbol)
                return asset['id']
        if asset is None and 'search_online' in asset_info:
            if asset_info['search_online'] == "MOEX":
                search_data = {}
                self._uppend_keys_from(search_data, asset_info, ['isin', 'reg_number'])
                if 'symbol' in asset_info:
                    search_data['name'] = asset_info['symbol']   # Search as by name as it is more flexible
                symbol = QuoteDownloader.MOEX_find_secid(**search_data)
                if not symbol and 'symbol' in asset_info:
                    symbol = asset_info['symbol']
                currency = asset_info['currency'] if 'currency' in asset_info else None  # Keep currency
                asset_info = QuoteDownloader.MOEX_info(symbol=symbol)
                asset_info['type'] = FOF.convert_predefined_asset_type(asset_info['type'])
                if currency is not None:
                    asset_info['currency'] = currency
                asset_info['note'] = "MOEX"
                return self.asset_id(asset_info)  # Call itself once again to cross-check downloaded data
        if asset is None:
            if asset_info.get('should_exist', False):
                raise Statement_ImportError(self.tr("Can't locate asset in statement data: ") + f"'{asset_info}'")
            asset_id = max([0] + [x['id'] for x in self._data[FOF.ASSETS]]) + 1
            asset = {"id": asset_id}
            self._uppend_keys_from(asset, asset_info, ['type', 'name', 'isin', 'country'])
            self._data[FOF.ASSETS].append(asset)
            if 'symbol' in asset_info:
                symbol_id = max([0] + [x['id'] for x in self._data[FOF.SYMBOLS]]) + 1
                symbol = {"id": symbol_id, "asset": asset_id}
                self._uppend_keys_from(symbol, asset_info, ['symbol', 'currency', 'note'])
                self._data[FOF.SYMBOLS].append(symbol)
            data = {}
            self._uppend_keys_from(data, asset_info, ['reg_number', 'expiry', 'principal'])
            if data:
                data_id = max([0] + [x['id'] for x in self._data[FOF.ASSETS_DATA]]) + 1
                data['id'] = data_id
                data['asset'] = asset_id
                self._data[FOF.ASSETS_DATA].append(data)
        else:
            if 'type' in asset and asset['type'] != FOF.ASSET_MONEY:
                self.update_asset_data(asset['id'], asset_info)
        return asset['id']

    # takes key from keys one by one and copies it from src to dst if it exists in src
    def _uppend_keys_from(self, dst, src, keys):
        for key in keys:
            if key in src:
                dst[key] = src[key]

    def update_asset_data(self, asset_id, asset_info):
        asset = self._find_in_list(self._data[FOF.ASSETS], "id", asset_id)
        self._uppend_keys_from(asset, asset_info, ['name', 'isin', 'country'])
        # Add new asset symbol if information provided
        if 'symbol' in asset_info:
            symbol_exists = False
            symbols = [x for x in self._data[FOF.SYMBOLS] if "asset" in x and x["asset"] == asset_id]
            if symbols:
                for symbol in symbols:
                    if symbol['symbol'] == asset_info['symbol'] and (
                            'currency' not in asset_info or symbol['currency'] == asset_info['currency']):
                        symbol_exists = True
            if not symbol_exists:
                symbol_id = max([0] + [x['id'] for x in self._data[FOF.SYMBOLS]]) + 1
                symbol = {"id": symbol_id, "asset": asset_id}
                self._uppend_keys_from(symbol, asset_info, ['symbol', 'currency', 'note', 'alt_symbol'])
                self._data[FOF.SYMBOLS].append(symbol)
        # Update the rest of asset data
        asset_data = self._find_in_list(self._data[FOF.ASSETS_DATA], "asset", asset_id)
        if asset_data is None:
            if {'reg_number', 'expiry', 'principal'}.intersection(set(asset_info)):  # if keys are present in info
                asset_data = {}
                data_id = max([0] + [x['id'] for x in self._data[FOF.ASSETS_DATA]]) + 1
                asset_data['id'] = data_id
                asset_data['asset'] = asset_id
                self._data[FOF.ASSETS_DATA].append(asset_data)
            else:
                return
        self._uppend_keys_from(asset_data, asset_info, ['reg_number', 'expiry'])

    # Removes asset and all links to it from self._data
    def remove_asset(self, asset_id):
        self._delete_with_id("asset", asset_id)
        self._data[FOF.ASSETS] = [x for x in self._data[FOF.ASSETS] if x['id'] != asset_id]

    # Removes all keys listed in extra_keys_list from operation_dict
    def drop_extra_fields(self, operation_dict, extra_keys_list):
        for key in extra_keys_list:
            if key in operation_dict:
                del operation_dict[key]
