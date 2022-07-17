import logging
import re
from datetime import datetime
from itertools import groupby

from PySide6.QtWidgets import QApplication
from jal.constants import PredefinedCategory
from jal.widgets.helpers import ManipulateDate
from jal.db.db import JalDB
from jal.db.helpers import executeSQL, readSQLrecord
from jal.db.operations import Dividend
from jal.data_import.statement import FOF, Statement_ImportError
from jal.data_import.statement_xml import StatementXML

JAL_STATEMENT_CLASS = "StatementIBKR"


# -----------------------------------------------------------------------------------------------------------------------
class IBKRCashOp:
    Dividend = 0
    TaxWithhold = 1
    DepositWithdrawal = 2
    Fee = 3
    Interest = 4
    BondInterest = 5


# -----------------------------------------------------------------------------------------------------------------------
class IBKR_AssetType:
    NotSupported = -1
    _asset_types = {
        '': -1,
        'CASH': FOF.ASSET_MONEY,
        'STK': FOF.ASSET_STOCK,
        'ETF': FOF.ASSET_ETF,
        'ADR': FOF.ASSET_ADR,
        'BOND': FOF.ASSET_BOND,
        'OPT': FOF.ASSET_OPTION,
        'FUT': FOF.ASSET_FUTURES,
        'WAR': FOF.ASSET_WARRANT,
        'RIGHT': FOF.ASSET_RIGHTS
    }

    def __init__(self, asset_type, subtype):
        self.type = self.NotSupported
        try:
            self.type = self._asset_types[asset_type]
        except KeyError:
            logging.warning(QApplication.translate("IBKR", "Asset type isn't supported: ") + f"'{asset_type}'")
        if self.type == FOF.ASSET_STOCK and subtype:  # distinguish ADR and ETF from stocks
            try:
                self.type = self._asset_types[subtype]
            except KeyError:
                pass


# -----------------------------------------------------------------------------------------------------------------------
class IBKR_CorpActionType:
    NotSupported = -1
    _corporate_action_types = {
        'BM': FOF.ACTION_BOND_MATURITY,    # No separate value as will be converted to ordinary bond sell operation
        'DW': FOF.ACTION_DELISTING,        # Delisting with loss of value
        'FS': FOF.ACTION_SPLIT,            # Forward split
        'HI': FOF.PAYMENT_STOCK_DIVIDEND,  # Choice dividend
        'IC': FOF.ACTION_SYMBOL_CHANGE,    # Issue change
        'RI': FOF.ACTION_RIGHTS_ISSUE,     # Subscribable Rights Issue
        'RS': FOF.ACTION_SPLIT,            # Reverse split
        'SO': FOF.ACTION_SPINOFF,          # Spin-off of new company
        'SD': FOF.PAYMENT_STOCK_DIVIDEND,  # Dividend paid in stocks
        'TC': FOF.ACTION_MERGER,           # Conversion of one stock into another
        'TO': FOF.ACTION_MERGER            # Voluntary conversion of one asset into another
    }

    def __init__(self, action_type):
        self.type = self.NotSupported
        try:
            self.type = self._corporate_action_types[action_type]
        except KeyError:
            logging.warning(QApplication.translate("IBKR", "Corporate action isn't supported: ") + f"{action_type}")


# -----------------------------------------------------------------------------------------------------------------------
class IBKR_Currency:
    pass

# -----------------------------------------------------------------------------------------------------------------------
class IBKR_Asset:
    BondPrincipal = 1000


# -----------------------------------------------------------------------------------------------------------------------
class IBKR_Account:
    def __init__(self, accounts_list, number, currency_ids):
        self.id = None
        account_ids = []
        for currency in currency_ids:
            match = [x for x in accounts_list if x['number'] == number and x['currency'] == currency]
            if match:
                if len(match) == 1:
                    account_ids.append(match[0]["id"])
                else:
                    logging.error(QApplication.translate("IBKR", "Multiple account match for ") + f"{number}")
            else:
                new_id = max([0] + [x['id'] for x in accounts_list]) + 1
                account_ids.append(new_id)
                account = {"id": new_id, "number": number, "currency": currency}
                accounts_list.append(account)
        if account_ids:
            if len(account_ids) == 1:
                self.id = account_ids[0]
            else:
                self.id = account_ids


# -----------------------------------------------------------------------------------------------------------------------
# Class for Loading Interactive Brokers XML Flex report
class StatementIBKR(StatementXML):
    statements_path = '/*/FlexStatement'
    statement_tag = 'FlexStatement'
    level_tag = 'levelOfDetail'
    CancelledFlag = 'Ca'

    def __init__(self):
        super().__init__()
        self.name = self.tr("Interactive Brokers")
        self.icon_name = "ibkr.png"
        self.filename_filter = self.tr("IBKR flex-query (*.xml)")

        ibkr_loaders = {
            IBKR_Currency: self.attr_currency,
            IBKR_AssetType: self.attr_asset_type,
            IBKR_Asset: self.attr_asset,
            IBKR_Account: self.attr_account,
            IBKR_CorpActionType: self.attr_corp_action_type
        }
        self.attr_loader.update(ibkr_loaders)
        self._sections = {   # Order of load is important - accounts and assets should be loaded first
            StatementXML.STATEMENT_ROOT: {'tag': self.statement_tag,
                                          'level': '',
                                          'values': [('accountId', 'account', str, None),
                                                     ('fromDate', 'period_start', datetime, None),
                                                     ('toDate', 'period_end', datetime, None)],
                                          'loader': self.load_header
                                          },
            'CashReport': {'tag': 'CashReportCurrency',
                           'level': 'Currency',
                           'values': [('accountId', 'number', str, None),
                                      ('currency', 'currency', IBKR_Currency, None),
                                      ('startingCash', 'cash_begin', float, None),
                                      ('endingCash', 'cash_end', float, None),                   # -- this is planned
                                      ('endingSettledCash', 'cash_end_settled', float, None)],   # -- this is now
                           'loader': self.load_accounts},
            'SecuritiesInfo': {'tag': 'SecurityInfo',
                               'level': '',
                               'values': [('symbol', 'symbol', str, None),
                                          ('currency', 'currency', IBKR_Currency, None),
                                          ('assetCategory', 'type', IBKR_AssetType, IBKR_AssetType.NotSupported),
                                          ('description', 'name', str, None),
                                          ('isin', 'isin', str, ''),
                                          ('cusip', 'reg_number', str, ''),
                                          ('expiry', 'expiry', datetime, 0),
                                          ('maturity', 'maturity', datetime, 0),
                                          ('listingExchange', 'exchange', str, '')],
                               'loader': self.load_assets},
            'Trades': {'tag': 'Trade',
                       'level': 'EXECUTION',
                       'values': [('assetCategory', 'type', IBKR_AssetType, IBKR_AssetType.NotSupported),
                                  ('symbol', 'asset', IBKR_Asset, None),
                                  ('accountId', 'account', IBKR_Account, None),
                                  ('dateTime', 'timestamp', datetime, None),
                                  ('settleDateTarget', 'settlement', datetime, 0),
                                  ('tradePrice', 'price', float, None),
                                  ('quantity', 'quantity', float, None),
                                  ('proceeds', 'proceeds', float, None),
                                  ('multiplier', 'multiplier', float, None),
                                  ('ibCommission', 'fee', float, None),
                                  ('tradeID', 'number', str, ''),
                                  ('exchange', 'exchange', str, ''),
                                  ('notes', 'notes', str, '')],
                       'loader': self.load_ib_trades},
            'OptionEAE': {'tag': 'OptionEAE',
                          'level': '',
                          'values': [('transactionType', 'operation', str, None),
                                     ('symbol', 'asset', IBKR_Asset, None),
                                     ('accountId', 'account', IBKR_Account, None),
                                     ('date', 'timestamp', datetime, None),
                                     ('tradePrice', 'price', float, None),
                                     ('quantity', 'quantity', float, None),
                                     ('multiplier', 'multiplier', float, None),
                                     ('commisionsAndTax', 'fee', float, None),
                                     ('tradeID', 'number', str, ''),
                                     ('notes', 'notes', str, '')],
                          'loader': self.load_options},
            'CorporateActions': {'tag': 'CorporateAction',
                                 'level': 'DETAIL',
                                 'values': [('type', 'type', IBKR_CorpActionType, IBKR_CorpActionType.NotSupported),
                                            ('accountId', 'account', IBKR_Account, None),
                                            ('symbol', 'asset', IBKR_Asset, None),
                                            ('assetCategory', 'asset_type', IBKR_AssetType, IBKR_AssetType.NotSupported),
                                            ('dateTime', 'timestamp', datetime, None),
                                            ('transactionID', 'number', str, ''),
                                            ('description', 'description', str, None),
                                            ('quantity', 'quantity', float, None),
                                            ('value', 'value', float, None),
                                            ('proceeds', 'proceeds', float, None),
                                            ('code', 'code', str, '')],
                                 'loader': self.load_corporate_actions},
            'CashTransactions': {'tag': 'CashTransaction',
                                 'level': 'DETAIL',
                                 'values': [('type', 'type', str, None),
                                            ('accountId', 'account', IBKR_Account, None),
                                            ('symbol', 'asset', IBKR_Asset, 0),
                                            ('currency', 'currency', IBKR_Currency, None),
                                            ('dateTime', 'timestamp', datetime, None),
                                            ('amount', 'amount', float, None),
                                            ('tradeID', 'number', str, ''),
                                            ('description', 'description', str, None)],
                                 'loader': self.load_cash_transactions},
            'StockGrantActivities': {'tag': 'StockGrantActivity',
                                     'level': '',
                                     'values': [('accountId', 'account', IBKR_Account, None),
                                                ('symbol', 'asset', IBKR_Asset, None),
                                                ('awardDate', 'timestamp', datetime, None),
                                                ('activityDescription', 'description', str, None),
                                                ('quantity', 'amount', float, None),
                                                ('price', 'price', float, None)],
                                     'loader': self.load_vestings},
            'TransactionTaxes': {'tag': 'TransactionTax',
                                 'level': 'SUMMARY',
                                 'values': [('accountId', 'account', IBKR_Account, None),
                                            ('symbol', 'symbol', str, None),
                                            ('date', 'timestamp', datetime, None),
                                            ('taxAmount', 'amount', float, None),
                                            ('description', 'description', str, None),
                                            ('taxDescription', 'tax_description', str, None)],
                                 'loader': self.load_taxes}
        }

    def tr(self, text):
        return QApplication.translate("IBKR", text)

    def validate_file_header_attributes(self, attributes):
        if 'type' not in attributes:
            raise Statement_ImportError(self.tr("Interactive Brokers report type not found"))
        if attributes['type'] == "TCF":
            raise Statement_ImportError(self.tr("You try to import Trade confimation report, not Activity report"))
        if attributes['type'] != 'AF':
            raise Statement_ImportError(self.tr("Unknown Interactive Brokers report type: ") + f"{attributes['type']}")

    # Convert attribute 'attr_name' value into json open-format asset type
    @staticmethod
    def attr_asset_type(xml_element, attr_name, default_value):
        if attr_name not in xml_element.attrib:
            return default_value
        sub_type = xml_element.attrib['subCategory'] if 'subCategory' in xml_element.attrib else ''
        return IBKR_AssetType(xml_element.attrib[attr_name], sub_type).type

    # Convert attribute 'attr_name' value into JAL corporate action
    def attr_corp_action_type(self, xml_element, attr_name, default_value):
        if attr_name not in xml_element.attrib:
            return default_value
        asset_category = self.attr_asset_type(xml_element, 'assetCategory', None)
        if asset_category not in [FOF.ASSET_STOCK, FOF.ASSET_BOND, FOF.ASSET_WARRANT]:
            logging.error(self.tr("Corporate action isn't supported for asset type: ") + f"'{asset_category}'")
            return default_value
        return IBKR_CorpActionType(xml_element.attrib[attr_name]).type

    def attr_currency(self, xml_element, attr_name, default_value):
        if attr_name not in xml_element.attrib:
            return default_value
        currency_id = self.currency_id(xml_element.attrib[attr_name])
        if currency_id is None:
            return default_value
        else:
            return currency_id

    def attr_asset(self, xml_element, attr_name, default_value):
        if attr_name not in xml_element.attrib:
            return default_value
        if xml_element.attrib[attr_name] == '':
            return default_value
        if xml_element.tag == 'CashTransaction' and attr_name == 'currency':
            asset_category = FOF.ASSET_MONEY
        else:
            asset_category = self.attr_asset_type(xml_element, 'assetCategory', None)
        if xml_element.tag == 'Trade' and asset_category == FOF.ASSET_MONEY:
            currency = xml_element.attrib[attr_name].split('.')
            asset_id = [self.currency_id(code) for code in currency]
            if not asset_id:
                return default_value
        else:
            symbol = xml_element.attrib[attr_name]
            if symbol.endswith('.OLD'):
                symbol = symbol[:-len('.OLD')]
            if asset_category == IBKR_AssetType.NotSupported:
                raise Statement_ImportError(self.tr("Asset type isn't supported: ") + f"'{asset_category}' ({symbol})")
            asset_data = {'symbol': symbol, 'type': asset_category}
            if xml_element.tag not in ['CorporateAction', 'CashTransaction'] and 'description' in xml_element.attrib:
                asset_data['name'] = xml_element.attrib['description']
            if asset_category != FOF.ASSET_MONEY:
                asset_data['currency'] = self.currency_id(xml_element.attrib['currency'])
            if 'isin' in xml_element.attrib and xml_element.attrib['isin']:
                asset_data['isin'] = xml_element.attrib['isin']
            if 'cusip' in xml_element.attrib and xml_element.attrib['cusip']:
                asset_data['reg_number'] = xml_element.attrib['cusip']
            if 'listingExchange' in xml_element.attrib and xml_element.attrib['listingExchange'] \
                    and xml_element.attrib['listingExchange'] != 'VALUE':  # don't store 'VALUE' or empty exchange
                asset_data['note'] = xml_element.attrib['listingExchange']
            asset_id = self.asset_id(asset_data)
        return asset_id

    def attr_account(self, xml_element, attr_name, default_value):
        if attr_name not in xml_element.attrib:
            return default_value
        if xml_element.tag == 'Trade' and self.attr_asset_type(xml_element, 'assetCategory', None) == FOF.ASSET_MONEY:
            if 'symbol' not in xml_element.attrib or 'ibCommissionCurrency' not in xml_element.attrib:
                if default_value is None:
                    logging.error(self.tr("Can't get currencies for currency exchange: ") + f"{xml_element}")
                return default_value
            currency = xml_element.attrib['symbol'].split('.')
            currency.append(xml_element.attrib['ibCommissionCurrency'])
        else:
            if 'currency' not in xml_element.attrib:
                if default_value is None:
                    logging.error(self.tr("Can't get account currency for account: ") + f"{xml_element}")
                return default_value
            currency = [xml_element.attrib['currency']]
        currency_ids = [self.currency_id(code) for code in currency]
        account_id = IBKR_Account(self._data[FOF.ACCOUNTS], xml_element.attrib[attr_name], currency_ids).id
        if account_id is None:
            return default_value
        else:
            return account_id

    def locate_asset(self, symbol, isin) -> int:
        candidates = [x for x in self._data[FOF.ASSETS] if 'isin' in x and x['isin'] == isin]
        if len(candidates) == 1:
            return candidates[0]["id"]
        candidates = [x for x in self._data[FOF.SYMBOLS] if 'symbol' in x and x['symbol'] == symbol]
        if len(candidates) == 1:
            return candidates[0]["asset"]
        return 0

    def set_asset_counry(self, asset_id, country):
        assets = [x for x in self._data[FOF.ASSETS] if 'id' in x and x['id'] == asset_id]
        if len(assets) != 1:
            return
        assets[0]["country"] = country

    def load_header(self, header):
        self._data[FOF.PERIOD][0] = header['period_start']
        self._data[FOF.PERIOD][1] = self._end_of_date(header['period_end'])
        logging.info(self.tr("Load IB Flex-statement for account ") +
                     f"{header['account']}: {datetime.utcfromtimestamp(header['period_start']).strftime('%Y-%m-%d')}" +
                     f" - {datetime.utcfromtimestamp(header['period_end']).strftime('%Y-%m-%d')}")

    def load_accounts(self, balances):
        for i, balance in enumerate(sorted(balances, key=lambda x: x['currency'])):
            balance['id'] = i + 1
            self._data[FOF.ACCOUNTS].append(balance)

    def load_assets(self, assets):
        asset_count = 0
        for asset in assets:
            if asset['type'] == IBKR_AssetType.NotSupported:   # Skip not supported type of asset
                continue
            # IB may use '.OLD' suffix if asset is being replaced
            asset['symbol'] = asset['symbol'][:-len('.OLD')] if asset['symbol'].endswith('.OLD') else asset['symbol']
            if asset['exchange'] and asset['exchange'] != 'VALUE':  # don't store 'VALUE' or empty exchange
                asset['note'] = asset['exchange']
            if asset['maturity']:
                asset['expiry'] = asset['maturity']
            if asset['expiry'] == 0:
                asset.pop('expiry')
            asset.pop('maturity')
            asset.pop('exchange')
            self.asset_id(asset)
            asset_count += 1
        logging.info(self.tr("Securities loaded: ") + f"{asset_count} ({len(assets)})")

    def load_ib_trades(self, ib_trades):
        trades = [trade for trade in ib_trades if type(trade['asset']) == int]
        trades_loaded = self.load_trades(trades)

        transfers = [transfer for transfer in ib_trades if type(transfer['asset']) == list]
        transfers_loaded = self.load_transfers(transfers)

        logging.info(self.tr("Trades loaded: ") + f"{trades_loaded + transfers_loaded} ({len(ib_trades)})")

    def load_trades(self, trades):
        trade_base = max([0] + [x['id'] for x in self._data[FOF.TRADES]]) + 1
        cnt = 0
        for i, trade in enumerate(sorted(trades, key=lambda x: x['timestamp'])):
            trade['id'] = trade_base + i
            trade['quantity'] = trade['quantity'] * trade['multiplier']
            if trade['settlement'] == 0:
                trade['settlement'] = trade['timestamp']
            asset = [x for x in self._data[FOF.ASSETS] if x['id'] == trade['asset']][0]
            if asset['type'] == FOF.ASSET_BOND:
                trade['quantity'] = trade['quantity'] / IBKR_Asset.BondPrincipal
                trade['price'] = trade['price'] * IBKR_Asset.BondPrincipal / 100.0  # Bonds are priced in percents of principal
            trade['fee'] = -trade['fee'] if trade['fee'] != 0 else 0.0  # otherwise we may have negative 0.0
            if trade['notes'] == StatementIBKR.CancelledFlag:
                trade['cancelled'] = True
            self.drop_extra_fields(trade, ["type", "proceeds", "multiplier", "exchange", "notes"])
            self._data[FOF.TRADES].append(trade)
            cnt += 1
        return cnt

    def load_transfers(self, transfers):
        transfer_base = max([0] + [x['id'] for x in self._data[FOF.TRANSFERS]]) + 1
        cnt = 0
        for i, transfer in enumerate(sorted(transfers, key=lambda x: x['timestamp'])):
            transfer['id'] = transfer_base + i
            if transfer['quantity'] > 0:
                transfer['account'][0], transfer['account'][1] = transfer['account'][1], transfer['account'][0]
                transfer['asset'][0], transfer['asset'][1] = transfer['asset'][1], transfer['asset'][0]
                transfer['quantity'], transfer['proceeds'] = transfer['proceeds'], transfer['quantity']
            transfer['withdrawal'] = abs(transfer.pop('quantity'))
            transfer['deposit'] = abs(transfer.pop('proceeds'))
            transfer['fee'] = -transfer['fee'] if transfer['fee'] != 0 else 0.0  # otherwise we may have negative 0.0
            transfer['description'] = transfer['exchange']
            self.drop_extra_fields(transfer, ["type", "settlement", "price", "multiplier", "exchange", "notes"])
            self._data[FOF.TRANSFERS].append(transfer)
            cnt += 1
        return cnt

    def load_options(self, options):
        transaction_desctiption = {
            "Assignment": self.tr("Option assignment"),
            "Exercise": self.tr("Option exercise"),
            "Expiration": self.tr("Option expiration"),
            "Buy": self.tr("Option assignment/exercise"),
            "Sell": self.tr("Option assignment/exercise"),
        }
        cnt = 0
        for option in options:
            description = ''
            try:
                description = transaction_desctiption[option['operation']]
            except KeyError:
                logging.error(
                    self.tr("Option E&A&E action isn't implemented: ") + f"{option['transactionType']}")
            if description:
                trade = [x for x in self._data[FOF.TRADES] if x['account'] == option['account']
                         and x['asset'] == option['asset'] and x['number'] == option['number']]
                if len(trade) == 1:
                    trade[0]['note'] = description
                else:
                    logging.warning(self.tr("Original trade not found for Option E&A&E operation: ") + f"{option}")
                cnt += 1
        logging.info(self.tr("Options E&A&E loaded: ") + f"{cnt} ({len(options)})")

    def load_corporate_actions(self, actions):
        action_loaders = {
            FOF.ACTION_MERGER: self.load_merger,
            FOF.ACTION_SPINOFF: self.load_spinoff,
            FOF.ACTION_SYMBOL_CHANGE: self.load_symbol_change,
            FOF.PAYMENT_STOCK_DIVIDEND: self.load_stock_dividend,
            FOF.ACTION_SPLIT: self.load_split,
            FOF.ACTION_BOND_MATURITY: self.load_bond_maturity,
            FOF.ACTION_DELISTING: self.load_delisting,
            FOF.ACTION_RIGHTS_ISSUE: self.load_none
        }

        cnt = 0
        self.remove_cancelled_corporate_actions(actions)

        # If stocks were bought/sold on a corporate action day IBKR may put several records for one corporate
        # action. So first step is to aggregate quantity.
        key_func = lambda x: (x['account'], x['asset'], x['type'], x['description'], x['timestamp'])
        actions_sorted = sorted(actions, key=key_func)
        actions_aggregated = []
        for k, group in groupby(actions_sorted, key=key_func):
            group_list = list(group)
            part = group_list[0]  # Take fist of several actions as a basis
            part['quantity'] = sum(action['quantity'] for action in group_list)  # and update quantity in it
            part['jal_processed'] = False  # This flag will be used to mark already processed records
            actions_aggregated.append(part)
            cnt += len(group_list) - 1
        # Now split in 2 parts: A for new stocks deposit, B for old stocks withdrawal
        # There might be 0 quantity value - it should be ignored
        parts_a = [action for action in actions_aggregated if action['quantity'] > 0]
        parts_b = [action for action in actions_aggregated if action['quantity'] < 0]
        # Process sequentially '+' and '-', 'jal_processed' will set True when '+' has pair record in '-'
        for action in parts_a + parts_b:
            if action['jal_processed']:
                continue
            if action['type'] in action_loaders:
                cnt += action_loaders[action['type']](action, parts_b)
            else:
                raise Statement_ImportError(
                    self.tr("Corporate action type is not supported: ") + f"{action}")
        logging.info(self.tr("Corporate actions loaded: ") + f"{cnt} ({len(actions)})")

    # Find record in list 'parts_b' (second parts of corporate actions) which matches
    # given asset and description with more details from corp_action itself
    def find_corp_action_pair(self, asset, description, action, parts_b):
        paired_record = list(filter(
            lambda pair: pair['asset'] == asset
                         and (pair['description'].startswith(description + ", ")
                              or pair['description'].startswith(description + ".OLD, "))
                         and pair['type'] == action['type']
                         and pair['timestamp'] == action['timestamp'], parts_b))
        if len(paired_record) != 1:
            raise Statement_ImportError(self.tr("Can't find paired record for ") + f"{action}")
        return paired_record

    # Takes cancelled corporate actions and tries to find and remove original one form actions list
    def remove_cancelled_corporate_actions(self, actions):
        delete_elements = []
        cancelled_actions = [(idx, action) for idx, action in enumerate(actions) if action['code'] == StatementIBKR.CancelledFlag]
        for c_id, c_action in cancelled_actions:
            matched = [idx for (idx, action) in enumerate(actions) if
                       action["type"] == c_action["type"] and action["account"] == c_action["account"] and
                       action["asset"] == c_action["asset"] and action["timestamp"] == c_action["timestamp"] and
                       action["description"] == c_action["description"] and action["quantity"] == -c_action["quantity"]]
            if len(matched) == 1:
                delete_elements += [c_id, matched[0]]
        for idx in sorted(delete_elements, reverse=True):
            del actions[idx]
        for action in actions:
            if action['code'] == StatementIBKR.CancelledFlag:
                raise Statement_ImportError(self.tr("Can't process cancelled corporate action") + f" '{action}'")

    # Dummy loader to skip some corporate actions
    def load_none(self, action, parts_b) -> int:
        return 0

    def load_merger(self, action, parts_b) -> int:
        MergerPatterns = [
            r"^(?P<symbol_old>.*)(.OLD)?\((?P<isin_old>\w+)\) +MERGED\([\w ]+\) +WITH +(?P<isin_new>\w+) +(?P<X>\d+) +FOR +(?P<Y>\d+) +\((?P<symbol>.*)(.OLD)?, (?P<name>.*), (?P<id>\w+)\)$",
            r"^(?P<symbol_old>.*)(.OLD)?\((?P<isin_old>\w+)\) +CASH and STOCK MERGER +\([\w ]+\) +(?P<isin_new>[\w ]+) +(?P<X>\d+) +FOR +(?P<Y>\d+) +AND +(?P<currency>\w+) +(\d+(\.\d+)?) +\((?P<symbol>[\w ]+)(.OLD)?, (?P<name>.*), (?P<id>\w+)\)$",
            r"^(?P<symbol_old>.*)(.OLD)?\((?P<isin_old>\w+)\) +CASH and STOCK MERGER +\([\w ]+\) +(?P<isin_new>[\w ]+) +(?P<X>\d+) +FOR +(?P<Y>\d+), +(?P<isin_new2>[\w ]+) +(?P<X2>\d+) +FOR +(?P<Y2>\d+) +AND +(?P<currency>\w+) +(\d+(\.\d+)?) +\((?P<symbol>[\w ]+)(.OLD)?, (?P<name>.*), (?P<id>\w+)\)$",
            r"^(?P<symbol_old>.*)\((?P<isin_old>\w+)\) +TENDERED TO +(?P<isin_new>\w+) +(?P<X>\d+) +FOR +(?P<Y>\d+) +\((?P<symbol>.*), +(?P<name>.*), +(?P<id>.*)\)$",
            r"^(?P<symbol_old>.*)\((?P<isin_old>\w+)\) +MERGED\([\w ]+\) +FOR (?P<currency>\w+) (?P<price>\d+\.\d+) PER SHARE +\((?P<symbol>.*), (?P<name>.*)( - TENDER ODD LOT)?, (?P<id>\w+)\)$",  # "TENDER ODD LOT" part is optional
            r"^(?P<symbol_old>.*)(.OLD)?\((?P<isin_old>\w+)\) +MERGED\([\w ]+\) +WITH +(?P<isin_new>.*) +(?P<X>\d+) +FOR +(?P<Y>\d+), +(?P<isin_new2>.*) +(?P<X2>\d+) +FOR +(?P<Y2>\d+) +\((?P<symbol>.*)(.OLD)?, (?P<name>.*), (?P<id>\w+)\)$"
            ]

        parts = None
        pattern_id = -1
        for pattern_id, pattern in enumerate(MergerPatterns):
            parts = re.match(pattern, action['description'], re.IGNORECASE)
            if parts:
                break

        if parts is None:
            raise Statement_ImportError(self.tr("Can't parse Merger description ") + f"'{action}'")
        merger_a = parts.groupdict()

        if len(merger_a) != MergerPatterns[pattern_id].count("(?P<"):  # check expected number of matches
            raise Statement_ImportError(self.tr("Merger description miss some data ") + f"'{action}'")

        description_b = action['description'][:parts.span('symbol')[0]] + merger_a['symbol_old']
        asset_b = self.locate_asset(merger_a['symbol_old'], merger_a['isin_old'])

        if pattern_id == 4:  # Asset converted to money -> store it as a sell trade
            action['id'] = max([0] + [x['id'] for x in self._data[FOF.TRADES]]) + 1
            action['settlement'] = action['timestamp']
            action['price'] = action['proceeds'] / (-action['quantity'])
            action['note'] = action.pop('description')
            action['fee'] = 0.0
            self.drop_extra_fields(action, ["type", "value", "proceeds", "code", "asset_type", "jal_processed"])
            self._data[FOF.TRADES].append(action)
            return 1

        paired_record = self.find_corp_action_pair(asset_b, description_b, action, parts_b)
        # Adjust quantity for bonds
        adj_factor = IBKR_Asset.BondPrincipal if action['asset_type'] == FOF.ASSET_BOND else 1.0
        existing_action = None
        # Special processing if 1 asset is converted into two other assets
        if pattern_id == 2 or pattern_id == 5:
            existing_action = self.locate_existing_merger(action['timestamp'],
                                                          action['account'], paired_record[0]['asset'])
        if existing_action is None:
            action['id'] = max([0] + [x['id'] for x in self._data[FOF.CORP_ACTIONS]]) + 1
            action['outcome'] = [{'asset': action['asset'], 'quantity': action['quantity']/adj_factor, 'share': 0.0}]
            action['asset'] = paired_record[0]['asset']
            action['quantity'] = -paired_record[0]['quantity']/adj_factor
            # Process cash payment if it is present as part of corporate action
            if pattern_id == 1 or pattern_id == 2:
                payment = {'asset': self.currency_id(parts['currency']),
                           'quantity': paired_record[0]['proceeds'], 'share': 0.0}
                action['outcome'].insert(0, payment)
            self.drop_extra_fields(action, ["value", "proceeds", "code", "asset_type", "jal_processed"])
            self._data[FOF.CORP_ACTIONS].append(action)
        else:
            next_outcome = {'asset': action['asset'], 'quantity': action['quantity']/adj_factor, 'share': 0.0}
            existing_action['outcome'].append(next_outcome)
        paired_record[0]['jal_processed'] = True
        return 2

    def locate_existing_merger(self, timestamp, account, asset):
        existing_merger = list(filter(
            lambda merger: merger['type'] == FOF.ACTION_MERGER and merger['timestamp'] == timestamp
                           and merger['account'] == account and merger['asset'] == asset, self._data[FOF.CORP_ACTIONS]))
        if len(existing_merger) == 0:
            return None
        if len(existing_merger) != 1:
            raise Statement_ImportError(self.tr("Multiple merger records already exist at ") + f"{timestamp}")
        return existing_merger[0]

    def load_spinoff(self, action, _parts_b) -> int:
        SpinOffPattern = r"^(?P<symbol_old>.*)\((?P<isin_old>\w+)\) +SPINOFF +(?P<X>\d+) +FOR +(?P<Y>\d+) +\((?P<symbol>.*), (?P<name>.*), (?P<id>\w+)\)$"

        parts = re.match(SpinOffPattern, action['description'], re.IGNORECASE)
        if parts is None:
            raise Statement_ImportError(self.tr("Can't parse Spin-off description ") + f"'{action}'")
        spinoff = parts.groupdict()
        if len(spinoff) != SpinOffPattern.count("(?P<"):  # check that expected number of groups was matched
            raise Statement_ImportError(self.tr("Spin-off description miss some data ") + f"'{action}'")
        asset_old = self.locate_asset(spinoff['symbol_old'], spinoff['isin_old'])
        if not asset_old:
            raise Statement_ImportError(self.tr("Spin-off initial asset not found ") + f"'{action}'")
        qty_old = int(spinoff['Y']) * action['quantity'] / int(spinoff['X'])
        if abs(round(qty_old) - qty_old) > 0.01:
            raise Statement_ImportError(self.tr("Spin-off rounding error is too big ") + f"'{action}'")
        qty_old = round(qty_old)
        action['id'] = max([0] + [x['id'] for x in self._data[FOF.CORP_ACTIONS]]) + 1
        action['outcome'] = [{'asset': asset_old, 'quantity': qty_old, 'share': 0.0},
                             {'asset': action['asset'], 'quantity': action['quantity'], 'share': 0.0}]
        action['asset'] = asset_old
        action['quantity'] = qty_old
        self.drop_extra_fields(action, ["value", "proceeds", "code", "asset_type", "jal_processed"])
        self._data[FOF.CORP_ACTIONS].append(action)
        return 1

    def load_symbol_change(self, action, parts_b) -> int:
        SymbolChangePattern = r"^(?P<symbol_old>.*)\((?P<isin_old>\w+)\) +CUSIP\/ISIN CHANGE TO +\((?P<isin_new>\w+)\) +\((?P<symbol>.*), (?P<name>.*), (?P<id>\w+)\)$"

        parts = re.match(SymbolChangePattern, action['description'], re.IGNORECASE)
        if parts is None:
            raise Statement_ImportError(self.tr("Can't parse Symbol Change description ") + f"'{action}'")
        isin_change = parts.groupdict()
        if len(isin_change) != SymbolChangePattern.count("(?P<"):  # check that expected number of groups was matched
            raise Statement_ImportError(self.tr("Spin-off description miss some data ") + f"'{action}'")
        description_b = action['description'][:parts.span('symbol')[0]] + isin_change['symbol_old']
        asset_b = self.locate_asset(isin_change['symbol_old'], isin_change['isin_old'])
        paired_record = self.find_corp_action_pair(asset_b, description_b, action, parts_b)
        action['id'] = max([0] + [x['id'] for x in self._data[FOF.CORP_ACTIONS]]) + 1
        action['outcome'] = [{'asset': action['asset'], 'quantity': action['quantity'], 'share': 1.0}]
        action['asset'] = paired_record[0]['asset']
        action['quantity'] = -paired_record[0]['quantity']
        self.drop_extra_fields(action, ["value", "proceeds", "code", "asset_type", "jal_processed"])
        self._data[FOF.CORP_ACTIONS].append(action)
        paired_record[0]['jal_processed'] = True
        return 2

    def load_stock_dividend(self, action, parts_b) -> int:
        StockDividendPattern = r"^(?P<description>.*) +(?P<tail>\(.*\))$"

        parts = re.match(StockDividendPattern, action['description'], re.IGNORECASE)
        if parts is None:
            raise Statement_ImportError(self.tr("Can't parse Stock Dividend description ") + f"'{action}'")
        action['description'] = parts.groupdict()['description']

        action['id'] = max([0] + [x['id'] for x in self._data[FOF.ASSET_PAYMENTS]]) + 1
        action['amount'] = action['quantity']
        action['price'] = action['value'] / action['quantity']
        action['tax'] = 0
        self.drop_extra_fields(action, ["quantity", "value", "proceeds", "code", "asset_type", "jal_processed"])
        self._data[FOF.ASSET_PAYMENTS].append(action)
        return 1

    def load_split(self, action, parts_b) -> int:
        SplitPattern = r"^(?P<symbol_old>.*)\((?P<isin_old>\w+)\) +SPLIT +(?P<X>\d+) +FOR +(?P<Y>\d+) +\((?P<symbol>.*), (?P<name>.*), (?P<id>\w+)\)$"

        parts = re.match(SplitPattern, action['description'], re.IGNORECASE)
        if parts is None:
            raise Statement_ImportError(self.tr("Can't parse Split description ") + f"'{action}'")
        split = parts.groupdict()
        if len(split) != SplitPattern.count("(?P<"):  # check that expected number of groups was matched
            raise Statement_ImportError(self.tr("Split description miss some data ") + f"'{action}'")
        if parts['isin_old'] == parts['id']:  # Simple split without ISIN change
            qty_delta = action['quantity']
            qty_old = qty_delta / (int(split['X']) / int(split['Y']) - 1)
            qty_new = qty_old + qty_delta
            action['id'] = max([0] + [x['id'] for x in self._data[FOF.CORP_ACTIONS]]) + 1
            action['outcome'] = [{'asset': action['asset'], 'quantity': qty_new, 'share': 1.0}]
            action['quantity'] = qty_old
            self.drop_extra_fields(action, ["value", "proceeds", "code", "asset_type", "jal_processed"])
            self._data[FOF.CORP_ACTIONS].append(action)
            return 1
        else:  # Split together with ISIN change and there should be 2nd record available
            description_b = action['description'][:parts.span('symbol')[0]] + split['symbol_old']
            asset_b = self.locate_asset(split['symbol_old'], split['isin_old'])
            paired_record = self.find_corp_action_pair(asset_b, description_b, action, parts_b)
            action['id'] = max([0] + [x['id'] for x in self._data[FOF.CORP_ACTIONS]]) + 1
            action['outcome'] = [{'asset': action['asset'], 'quantity': action['quantity'], 'share': 1.0}]
            action['asset'] = paired_record[0]['asset']
            action['quantity'] = -paired_record[0]['quantity']
            self.drop_extra_fields(action, ["value", "proceeds", "code", "asset_type", "jal_processed"])
            self._data[FOF.CORP_ACTIONS].append(action)
            paired_record[0]['jal_processed'] = True
            return 2

    # Bond maturity is processed as ordinary bond
    def load_bond_maturity(self, action, parts_b) -> int:
        action['id'] = max([0] + [x['id'] for x in self._data[FOF.TRADES]]) + 1
        action['quantity'] = action['quantity'] / IBKR_Asset.BondPrincipal
        action['price'] = action['proceeds'] / (-action['quantity'])  # Quantity is negative, bonds are withdrawn
        action['settlement'] = action['timestamp']                    # Settled by the same date
        action['note'] = action['description']
        action['fee'] = 0.0
        self.drop_extra_fields(action, ["description", "value", "proceeds", "type", "code", "asset_type",
                                        "jal_processed"])
        self._data[FOF.TRADES].append(action)
        return 1

    def load_delisting(self, action, parts_b) -> int:
        # There might be delisting for issued rights - we don't need to store it as it isn't a real asset
        asset = [x for x in self._data[FOF.ASSETS] if x['id'] == action['asset']][0]
        if asset['type'] == FOF.ASSET_RIGHTS:
            return 0
        action['id'] = max([0] + [x['id'] for x in self._data[FOF.CORP_ACTIONS]]) + 1
        action['asset'] = action['asset']
        action['quantity'] = -action['quantity']
        action['outcome'] = []
        self.drop_extra_fields(action, ["value", "proceeds", "code", "asset_type", "jal_processed"])
        self._data[FOF.CORP_ACTIONS].append(action)
        return 1

    def load_vestings(self, vestings):
        cnt = 0
        asset_payments_base = max([0] + [x['id'] for x in self._data[FOF.ASSET_PAYMENTS]]) + 1
        for i, vesting in enumerate(vestings):
            vesting['id'] = asset_payments_base + i
            vesting['type'] = FOF.PAYMENT_STOCK_VESTING
            # self.drop_extra_fields(action, ["quantity", "value", "proceeds", "code", "asset_type", "jal_processed"])
            self._data[FOF.ASSET_PAYMENTS].append(vesting)
            cnt += 1
        logging.info(self.tr("Stock vestings loaded: ") + f"{cnt} ({len(vestings)})")

    def load_cash_transactions(self, cash):
        cnt = 0
        dividends = list(filter(lambda tr: tr['type'] in ['Dividends', 'Payment In Lieu Of Dividends'], cash))
        asset_payments_base = max([0] + [x['id'] for x in self._data[FOF.ASSET_PAYMENTS]]) + 1
        for i, dividend in enumerate(dividends):
            dividend['id'] = asset_payments_base + i
            dividend['type'] = FOF.PAYMENT_DIVIDEND
            self.drop_extra_fields(dividend, ["currency"])
            self._data[FOF.ASSET_PAYMENTS].append(dividend)
            cnt += 1
        asset_payments_base += cnt
        bond_interests = list(filter(lambda tr: tr['type'] in ['Bond Interest Paid', 'Bond Interest Received'], cash))
        for i, bond_interest in enumerate(bond_interests):
            bond_interest['id'] = asset_payments_base + i
            bond_interest['type'] = FOF.PAYMENT_INTEREST
            self.drop_extra_fields(bond_interest, ["currency"])
            self._data[FOF.ASSET_PAYMENTS].append(bond_interest)
            cnt += 1

        taxes = list(filter(lambda tr: tr['type'] == 'Withholding Tax', cash))
        for tax in taxes:
            cnt += self.apply_tax_withheld(tax)

        transfer_base = max([0] + [x['id'] for x in self._data[FOF.TRANSFERS]]) + 1
        transfers = list(filter(lambda tr: tr['type'] == 'Deposits/Withdrawals', cash))
        for i, transfer in enumerate(transfers):
            transfer['id'] = transfer_base + i
            transfer['asset'] = [transfer['currency'], transfer['currency']]
            if transfer['amount'] >= 0:  # Deposit
                transfer['account'] = [0, transfer['account'], 0]
                transfer['withdrawal'] = transfer['deposit'] = transfer['amount']
            else:  # Withdrawal
                transfer['account'] = [transfer['account'], 0, 0]
                transfer['withdrawal'] = transfer['deposit'] = -transfer['amount']
            transfer['fee'] = 0.0
            self.drop_extra_fields(transfer, ["type", "amount", "currency"])
            self._data[FOF.TRANSFERS].append(transfer)
            cnt += 1

        payment_base = max([0] + [x['id'] for x in self._data[FOF.INCOME_SPENDING]]) + 1
        fees = list(filter(lambda tr: 'type' in tr and tr['type'] in ['Other Fees',
                                                                      'Commission Adjustments',  #FIXME Link this fee with asset
                                                                      'Broker Interest Paid',
                                                                      'Broker Interest Received'], cash))
        for i, fee in enumerate(fees):
            fee['id'] = payment_base + i
            fee['peer'] = 0
            if fee['type'] == 'Broker Interest Received':
                category = -PredefinedCategory.Interest
            else:
                category = -PredefinedCategory.Fees
            fee['lines'] = [{'amount': fee['amount'], 'category': category, 'description': fee['description']}]
            self.drop_extra_fields(fee, ["type", "amount", "description", "asset", "number", "currency"])
            self._data[FOF.INCOME_SPENDING].append(fee)
            cnt += 1

        logging.info(self.tr("Cash transactions loaded: ") + f"{cnt} ({len(cash)})")

    def load_taxes(self, taxes):
        cnt = 0   #FIXME Link this tax with asset
        tax_base = max([0] + [x['id'] for x in self._data[FOF.INCOME_SPENDING]]) + 1
        for i, tax in enumerate(taxes):
            tax['id'] = tax_base + i
            tax['peer'] = 0
            note = f"{tax['symbol']} ({tax['description']}) - {tax['tax_description']}"
            tax['lines'] = [{'amount': tax['amount'], 'category': -PredefinedCategory.Taxes, 'description': note}]
            self.drop_extra_fields(tax, ["symbol", "amount", "description", "tax_description"])
            self._data[FOF.INCOME_SPENDING].append(tax)
            cnt += 1
        logging.info(self.tr("Taxes loaded: ") + f"{cnt} ({len(taxes)})")

    # Applies tax to matching dividend:
    # if tax < 0: apply it to dividend without tax
    # otherwise: it is a correction and there should be dividend with exactly the same tax that will be set to 0
    def apply_tax_withheld(self, tax) -> int:
        TaxFullPattern = r"^(?P<description>.*) - (?P<country>\w\w) TAX$"

        parts = re.match(TaxFullPattern, tax['description'], re.IGNORECASE)
        if not parts:
            logging.warning(self.tr("*** MANUAL ENTRY REQUIRED ***"))
            logging.warning(self.tr("Unhandled tax country pattern found: ") + f"{tax['description']}")
            return 0
        parts = parts.groupdict()
        self.set_asset_counry(tax['asset'], parts['country'].lower())
        description = parts['description']
        previous_tax = tax['amount'] if tax['amount'] >= 0 else 0
        new_tax = -tax['amount'] if tax['amount'] < 0 else 0

        dividend = self.find_dividend4tax(tax['timestamp'], tax['account'], tax['asset'], previous_tax, new_tax, description)
        if dividend is None:
            logging.warning(self.tr("Dividend not found for withholding tax: ") + f"{tax}, {previous_tax}")
            return 0
        dividend["tax"] = new_tax
        # append new dividend if it came from DB and haven't been loaded in self._data yet
        if len([1 for x in self._data[FOF.ASSET_PAYMENTS] if x['id'] == dividend['id']]) == 0:
            dividend['type'] = FOF.PAYMENT_DIVIDEND
            self._data[FOF.ASSET_PAYMENTS].append(dividend)
        return 1

    # Searches for divident that matches tax in the best way:
    # - it should have exactly the same account_id and asset_id
    # - tax amount withheld from dividend should be equal to provided 'tax' value
    # - timestamp should be the same or within previous year for weak match of Q1 taxes
    # - note should be exactly the same or contain the same key elements
    def find_dividend4tax(self, timestamp, account_id, asset_id, prev_tax, new_tax, note):
        PaymentInLiueOfDividend = 'PAYMENT IN LIEU OF DIVIDEND'
        TaxNotePattern = r"^(?P<symbol>.*\w) ?\((?P<isin>\w+)\)(?P<prefix>( \w*)+) +(?P<amount>\d+\.\d+)?(?P<suffix>.*)$"
        DividendNotePattern = r"^(?P<symbol>.*\w) ?\((?P<isin>\w+)\)(?P<prefix>( \w*)+) +(?P<amount>\d+\.\d+)?(?P<suffix>.*) \(.*\)$"

        dividends = [x for x in self._data[FOF.ASSET_PAYMENTS] if
                     (x['type'] == FOF.PAYMENT_DIVIDEND or x['type'] == FOF.PAYMENT_STOCK_DIVIDEND)
                     and x['asset'] == asset_id and x['account'] == account_id]
        account = [x for x in self._data[FOF.ACCOUNTS] if x["id"] == account_id][0]
        currency = [x for x in self._data[FOF.ASSETS] if x["id"] == account['currency']][0]
        currency_symbol = [x for x in self._data[FOF.SYMBOLS] if x["asset"] == currency['id']][0]
        db_account = JalDB().get_account_id(account['number'], currency_symbol['symbol'])
        asset = [x for x in self._data[FOF.ASSETS] if x["id"] == asset_id][0]
        isin = asset['isin'] if 'isin' in asset else ''
        symbols = [x for x in self._data[FOF.SYMBOLS] if x["asset"] == asset_id]
        db_asset = JalDB().get_asset_id({'isin': isin, 'symbol': symbols[0]['symbol']})
        if db_account is not None and db_asset is not None:
            query = executeSQL(
                "SELECT -id AS id, -account_id AS account, timestamp, number, "
                "-asset_id AS asset, amount, tax, note as description FROM dividends "
                "WHERE type=:div AND account_id=:account_id AND asset_id=:asset_id",
                [(":div", Dividend.Dividend), (":account_id", db_account), (":asset_id", db_asset)],
                forward_only=True)
            while query.next():
                db_dividend = readSQLrecord(query, named=True)
                db_dividend['asset'] = asset_id
                db_dividend['account'] = account_id
                dividends.append(db_dividend)
        if datetime.utcfromtimestamp(timestamp).timetuple().tm_yday < 75:
            # We may have wrong date in taxes before March, 15 due to tax correction
            range_start, _range_end = ManipulateDate.PreviousYear(day=datetime.utcfromtimestamp(timestamp))
            dividends = [x for x in dividends if x['timestamp'] >= range_start]
        else:
            # For any other day - use exact time match
            dividends = [x for x in dividends if x['timestamp'] == timestamp]
        dividends = [x for x in dividends if 'tax' not in x or (abs(x['tax'] - prev_tax) < 0.0001)]
        dividends = sorted(dividends, key=lambda x: x['timestamp'])

        # Choose either Dividends or Payments in liue with regards to note of the matching tax
        if PaymentInLiueOfDividend in note.upper():
            dividends = list(filter(lambda item: PaymentInLiueOfDividend in item['description'], dividends))
            # we don't check for full match as there are a lot of records without amount
        else:
            dividends = list(filter(lambda item: PaymentInLiueOfDividend not in item['description'], dividends))
            # Check for full match
            for dividend in dividends:
                if (dividend['timestamp'] == timestamp) and (note.upper() == dividend['description'][:len(note)].upper()):
                    return dividend
        if len(dividends) == 0:
            return None

        # Chose most probable dividend - by amount, timestamp and description
        parts = re.match(TaxNotePattern, note, re.IGNORECASE)
        if not parts:
            logging.warning(self.tr("*** MANUAL ENTRY REQUIRED ***"))
            logging.warning(self.tr("Unhandled tax pattern found: ") + f"{note}")
            return None
        parts = parts.groupdict()
        note_prefix = parts['prefix']
        note_suffix = parts['suffix']
        try:
            note_amount = float(parts['amount'])
        except (ValueError, TypeError):
            note_amount = 0
        score = [0] * len(dividends)
        for i, dividend in enumerate(dividends):
            parts = re.match(DividendNotePattern, dividend['description'], re.IGNORECASE)
            if not parts:
                logging.warning(self.tr("*** MANUAL ENTRY REQUIRED ***"))
                logging.warning(self.tr("Unhandled dividend pattern found: ") + f"{dividend['description']}")
                return None
            parts = parts.groupdict()
            try:
                amount = float(parts['amount'])
            except (ValueError, TypeError):
                amount = 0
            if abs(amount - note_amount) <= 0.000005:            # Description has very similar amount +++++
                score[i] += 5
            if dividend['timestamp'] == timestamp:               # Timestamp exact match gives ++
                score[i] += 2
            if abs(0.1 * dividend['amount'] - new_tax) <= 0.01:  # New tax is 10% of dividend gives +
                score[i] += 1
            if parts['prefix'] == note_prefix:                   # Prefix part of description match gives +
                score[i] += 1
            if parts['suffix'] == note_suffix:                   # Suffix part of description match gives +
                score[i] += 1
        for i, vote in enumerate(score):
            if (vote == max(score)) and (vote > 0):
                return dividends[i]
        # Final check - if only one found, return it
        if len(dividends) == 1:
            return dividends[0]
        return None

    # Removes data that was used during XML processing but isn't needed in final output:
    # Drop any assets with type 'right' as JAL won't import them
    def strip_unused_data(self):
        rights_id = [x['id'] for x in self._data[FOF.ASSETS] if x['type'] == FOF.ASSET_RIGHTS]
        for asset_id in rights_id:
            self.remove_asset(asset_id)
