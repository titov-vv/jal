import logging
import re
from copy import deepcopy
from datetime import datetime, timezone
from itertools import groupby
from decimal import Decimal
from lxml import etree

from PySide6.QtWidgets import QApplication
from jal.constants import Setup, PredefinedCategory
from jal.widgets.helpers import ts2dt, ts2d
from jal.db.helpers import format_decimal, remove_exponent
from jal.db.account import JalAccount
from jal.db.operations import AssetPayment, AssetIncome
from jal.data_import.statement import JSF, Statement_ImportError, Statement_Capabilities
from jal.data_import.statement_xml import StatementXML

JAL_STATEMENT_CLASS = "StatementIBKR"
IBKR_CALCULATION_PRECISION = 10
DIVIDENDS_TABLE_ASSET_FIELD = 8

# The end-of-day stamps IBKR puts on an accounting day. They are not times of day, and they are IBKR's alone - an
# evening entry on a cash account can legitimately read 20:20 (or other), so they are never part of the common
# set that is_day_marker() knows by itself.
IBKR_DAY_MARKERS = (20 * 3600 + 20 * 60, 20 * 3600 + 24 * 60, 20 * 3600 + 25 * 60, 20 * 3600 + 26 * 60)

# -----------------------------------------------------------------------------------------------------------------------
class IBKR_AssetType:
    NotSupported = -1
    _asset_types = {
        '': -1,
        'CASH': JSF.ASSET_MONEY,
        'STK': JSF.ASSET_STOCK,
        'ETF': JSF.ASSET_ETF,
        'ADR': JSF.ASSET_ADR,
        'BOND': JSF.ASSET_BOND,
        'BILL': JSF.ASSET_BOND,
        'OPT': JSF.ASSET_OPTION,
        'FUT': JSF.ASSET_FUTURES,
        'WAR': JSF.ASSET_WARRANT,
        'RIGHT': JSF.ASSET_RIGHTS,
        'CFD': JSF.ASSET_CFD,
        'MLP': JSF.ASSET_MLP
    }

    def __init__(self, asset_type, subtype):
        self.type = self.NotSupported
        try:
            self.type = self._asset_types[asset_type]
        except KeyError:
            raise Statement_ImportError(
                QApplication.translate("StatementIBKR", "Asset type isn't supported: ") + f"'{asset_type}'")
        if self.type == JSF.ASSET_STOCK and subtype:  # distinguish ADR and ETF from stocks
            try:
                self.type = self._asset_types[subtype]
            except KeyError:
                pass


# -----------------------------------------------------------------------------------------------------------------------
class IBKR_CorpActionType:
    NotSupported = -1
    _corporate_action_types = {
        'BM': JSF.ACTION_BOND_MATURITY,    # Bond maturity (will be converted to bond sell operation)
        'DW': JSF.ACTION_DELISTING,        # Delisting with loss of value
        'FS': JSF.ACTION_SPLIT,            # Forward split
        'HI': JSF.PAYMENT_STOCK_DIVIDEND,  # Choice dividend
        'IC': JSF.ACTION_SYMBOL_CHANGE,    # Issue change
        'RI': JSF.ACTION_RIGHTS_ISSUE,     # Subscribable Rights Issue
        'RS': JSF.ACTION_SPLIT,            # Reverse split
        'SO': JSF.ACTION_SPINOFF,          # Spin-off of new company
        'SD': JSF.PAYMENT_STOCK_DIVIDEND,  # Dividend paid in stocks
        'TC': JSF.ACTION_MERGER,           # Conversion of one stock into another
        'TM': JSF.ACTION_BOND_MATURITY,    # T-Bill maturity (will be converted to bond sell operation)
        'TO': JSF.ACTION_MERGER            # Voluntary conversion of one asset into another
    }

    def __init__(self, action_type):
        self.type = self.NotSupported
        try:
            self.type = self._corporate_action_types[action_type]
        except KeyError:
            raise Statement_ImportError(
                QApplication.translate("StatementIBKR", "Corporate action isn't supported: ") + f"{action_type}")


# -----------------------------------------------------------------------------------------------------------------------
class IBKR_Currency:
    pass

# -----------------------------------------------------------------------------------------------------------------------
class IBKR_Asset:
    BondPrincipal = 1000

# -----------------------------------------------------------------------------------------------------------------------
# Returns True if masked value ('U***XXXX') matches with given account number.
def is_account(masked_value, account_number) -> bool:
    return re.fullmatch(masked_value.replace('*', '.'), account_number) is not None

# -----------------------------------------------------------------------------------------------------------------------
class IBKR_Account:
    pass


# -----------------------------------------------------------------------------------------------------------------------
# Class for Loading Interactive Brokers XML Flex report
class StatementIBKR(StatementXML):
    # IBKR have special timestamps for after hours - like 20:20, 20:24 (see IBKR_DAY_MARKERS).
    # That marker is not a time of day and is never converted - attr_timestamp() stores what states a day as the day
    # it states, so the day a payment is taxed in survives the conversion of everything that IS a moment.
    source_timezone = 'America/New_York'
    source_day_markers = IBKR_DAY_MARKERS
    statements_path = './*/FlexStatement'
    statement_tag = 'FlexStatement'
    level_tag = 'levelOfDetail'
    CancelledFlag = 'Ca'
    ReversalCode = 'Re'
    ReversalSuffix = " - REVERSAL"
    CancelPrefix = "CANCEL "
    ReplacedSuffix = '.OLD'     # IB may add it to a symbol of an asset that is being replaced
    NoAsset = -1
    NoActionID = '<missing>'    # stands for 'actionID' of a corporate action that has no such attribute at all
    FormerCorpActionsTag = 'ibkr-corp-actions-by-description'
    CashTransactionTypes = ['Dividends', 'Payment In Lieu Of Dividends', 'Bond Interest Paid', 'Bond Interest Received',
                            'Withholding Tax', 'Deposits/Withdrawals', 'Other Fees', 'Commission Adjustments',
                            'Broker Interest Paid', 'Broker Interest Received']   # the ones that are imported

    def __init__(self):
        super().__init__()
        self.name = self.tr("&Interactive Brokers")
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
                                      ('startingCash', 'cash_begin', Decimal, None),
                                      ('endingCash', 'cash_end', Decimal, None),                 # -- this is planned
                                      ('endingSettledCash', 'cash_end_settled', Decimal, None)],  # -- this is now
                           'loader': self.load_accounts},
            'SecuritiesInfo': {'tag': 'SecurityInfo',
                               'level': '',
                               'values': [('symbol', 'symbol', str, None),
                                          ('currency', 'currency', IBKR_Currency, None),
                                          ('assetCategory', 'type', IBKR_AssetType, IBKR_AssetType.NotSupported),
                                          ('description', 'name', str, None),
                                          ('isin', 'isin', str, ''),
                                          ('figi', 'figi', str, ''),
                                          ('cusip', 'cusip', str, ''),
                                          ('expiry', 'expiry', datetime, 0),
                                          ('maturity', 'maturity', datetime, 0),
                                          ('principalAdjustFactor', 'principal', str, ''),
                                          ('listingExchange', 'exchange', str, '')],
                               'loader': self.load_assets},
            'Trades': {'tag': 'Trade',
                       'level': 'EXECUTION',
                       'values': [('assetCategory', 'type', IBKR_AssetType, IBKR_AssetType.NotSupported),
                                  ('symbol', 'symbol', IBKR_Asset, None),
                                  ('accountId', 'account', IBKR_Account, None),
                                  ('dateTime', 'timestamp', datetime, None),
                                  ('settleDateTarget', 'settlement', datetime, 0),
                                  ('tradePrice', 'price', Decimal, None),
                                  ('quantity', 'quantity', Decimal, None),
                                  ('proceeds', 'proceeds', Decimal, None),
                                  ('multiplier', 'multiplier', Decimal, None),
                                  ('ibCommission', 'fee', Decimal, None),
                                  ('tradeID', 'number', str, ''),
                                  ('exchange', 'exchange', str, ''),
                                  ('notes', 'notes', str, '')],
                       'loader': self.load_ib_trades},
            'OptionEAE': {'tag': 'OptionEAE',
                          'level': '',
                          'values': [('transactionType', 'operation', str, None),
                                     ('symbol', 'symbol', IBKR_Asset, None),
                                     ('accountId', 'account', IBKR_Account, None),
                                     ('date', 'timestamp', datetime, None),
                                     ('tradePrice', 'price', Decimal, None),
                                     ('quantity', 'quantity', Decimal, None),
                                     ('multiplier', 'multiplier', Decimal, None),
                                     ('commisionsAndTax', 'fee', Decimal, None),
                                     ('tradeID', 'number', str, ''),
                                     ('notes', 'notes', str, '')],
                          'loader': self.load_options},
            'CorporateActions': {'tag': 'CorporateAction',
                                 'level': 'DETAIL',
                                 'values': [('type', 'type', IBKR_CorpActionType, IBKR_CorpActionType.NotSupported),
                                            ('accountId', 'account', IBKR_Account, None),
                                            ('symbol', 'symbol', IBKR_Asset, None),
                                            ('assetCategory', 'asset_type', IBKR_AssetType, IBKR_AssetType.NotSupported),
                                            ('dateTime', 'timestamp', datetime, None),
                                            ('transactionID', 'number', str, ''),
                                            ('actionID', 'action_id', str, self.NoActionID),
                                            ('currency', 'currency', str, None),
                                            ('description', 'description', str, None),
                                            ('quantity', 'quantity', Decimal, None),
                                            ('multiplier', 'multiplier', Decimal, Decimal('1')),
                                            ('figi', 'figi', str, ''),
                                            ('value', 'value', Decimal, None),
                                            ('proceeds', 'proceeds', Decimal, None),
                                            ('code', 'code', str, '')],
                                 'loader': self.load_corporate_actions},
            'CashTransactions': {'tag': 'CashTransaction',
                                 'level': 'DETAIL',
                                 'values': [('type', 'type', str, None),
                                            ('accountId', 'account', IBKR_Account, None),
                                            ('symbol', 'symbol', IBKR_Asset, 0),
                                            ('currency', 'currency', IBKR_Currency, None),
                                            ('dateTime', 'timestamp', datetime, None),
                                            ('dateTime', 'timestamp_day_only', bool, False),
                                            ('reportDate', 'reported', datetime, None),
                                            ('amount', 'amount', Decimal, None),
                                            ('tradeID', 'number', str, ''),
                                            ('transactionID', 'tid', str, ''),
                                            ('actionID', 'action_id', str, ''),
                                            ('description', 'description', str, None)],
                                 'loader': self.load_cash_transactions},
            'ChangeInDividendAccruals': {'tag': 'ChangeInDividendAccrual',
                                         'level': 'DETAIL',
                                         'values': [('code', 'code', str, None),
                                                    ('accountId', 'account', IBKR_Account, None),
                                                    ('symbol', 'symbol', IBKR_Asset, 0),
                                                    ('currency', 'currency', IBKR_Currency, None),
                                                    ('date', 'timestamp', datetime, None),
                                                    ('exDate', 'ex_date', datetime, None),
                                                    ('grossAmount', 'amount', Decimal, None),
                                                    ('grossRate', 'rate', Decimal, 0)],
                                         'loader': self.load_dividend_accruals},
            'StockGrantActivities': {'tag': 'StockGrantActivity',
                                     'level': '',
                                     'values': [('accountId', 'account', IBKR_Account, None),
                                                ('symbol', 'symbol', IBKR_Asset, None),
                                                ('awardDate', 'award_date', datetime, None),
                                                ('vestingDate', 'vesting_date', datetime, None),
                                                ('activityDescription', 'description', str, None),
                                                ('quantity', 'amount', Decimal, None),
                                                ('price', 'price', str, None)],
                                     'loader': self.load_granted_stocks},
            'TransactionTaxes': {'tag': 'TransactionTax',
                                 'level': 'SUMMARY',
                                 'values': [('accountId', 'account', IBKR_Account, None),
                                            ('symbol', 'symbol', IBKR_Asset, None),
                                            ('date', 'timestamp', datetime, None),
                                            ('taxAmount', 'amount', Decimal, None),
                                            ('taxDescription', 'description', str, None),
                                            ('source', 'source', str, None),
                                            ('tradeId', 'number', str, None)],
                                 'loader': self.load_taxes},
            'SalesTaxes': {'tag': 'SalesTax',
                           'level': '',
                           'values': [('accountId', 'account', IBKR_Account, None),
                                      ('currency', 'currency', str, None),
                                      ('date', 'timestamp', datetime, None),
                                      ('salesTax', 'amount', Decimal, None),
                                      ('taxableDescription', 'description', str, None),
                                      ('country', 'country', str, None),
                                      ('taxType', 'tax_type', str, None),
                                      ('taxableAmount', 'taxable_amount', Decimal, None),
                                      ('taxRate', 'tax_rate', str, None)],
                           'loader': self.load_sales_taxes},
            'CFDCharges': {'tag': 'CFDCharge',
                           'level': '',
                           'values': [('accountId', 'account', IBKR_Account, None),
                                      ('symbol', 'symbol', IBKR_Asset, self.NoAsset),
                                      ('date', 'timestamp', datetime, None),
                                      ('total', 'amount', Decimal, None),
                                      ('transactionID', 'number', str, ''),
                                      ('activityDescription', 'description', str, None)],
                           'loader': self.load_cfd_charges},
            'Transfers': {'tag': 'Transfer',
                          'level': '',
                          'values': [('accountId', 'account', IBKR_Account, None),
                                     ('symbol', 'symbol', IBKR_Asset, self.NoAsset),
                                     ('account', 'account2', IBKR_Account, 0),
                                     ('dateTime', 'timestamp', datetime, None),
                                     ('quantity', 'quantity', Decimal, None),
                                     ('cashTransfer', 'amount', Decimal, None),
                                     ('type', 'type', str, None),
                                     ('description', 'description', str, None),
                                     ('direction', 'direction', str, None),
                                     ('company', 'company', str, None),
                                     ('transactionID', 'number', str, '')],
                          'loader': self.load_transfers}
        }

    @staticmethod
    def capabilities() -> set:
        return {Statement_Capabilities.MULTIPLE_LOAD}

    # Saves information from XML that is related with a given symbol's asset
    def save_debug_info(self, account, symbol):
        # Dump statement info relevant to given symbol's asset
        debug_info = 'Statement data:\n----------------------------------------------------------------\n'
        assert self._statement is not None
        debug_info += self._masked_xml(self._asset_elements(symbol))
        debug_info += "----------------------------------------------------------------\n"
        # Dump asset_payments info from database for the given symbol's asset
        db_account = self._map_db_account(account)
        db_asset = self._map_db_asset_by_symbol(symbol)
        payments = JalAccount(db_account).dump_asset_payments() + JalAccount(db_account).dump_asset_incomes()
        payments = [x for x in payments if x[DIVIDENDS_TABLE_ASSET_FIELD] == db_asset]
        debug_info += "Database data:\n----------------------------------------------------------------\n"
        debug_info += str(payments)
        debug_info += "\n----------------------------------------------------------------\n"
        super().save_debug_info(debug_info=debug_info)

    # Statement records that mention any symbol of the given symbol's asset
    def _asset_elements(self, symbol) -> list:
        elements = []
        for symbol_name in [x['symbol'] for x in self._symbol_asset(symbol)[JSF.SYMBOLS]]:
            elements += self._statement.findall(f".//*[@symbol='{symbol_name}']")
        return elements

    # XML text of the given statement records with the account number, its alias and the cash balance wiped out
    @staticmethod
    def _masked_xml(elements) -> str:
        xml_text = ''
        for element in elements:
            # The dump is written to be sent on to someone who has no business knowing whose account it is, so
            # what names the account goes, and so does the running balance - it says nothing about the records
            # that could not be reconciled, and it is the one figure in them that describes the whole portfolio.
            for attribute, replacement in (('accountId', 'U7654321'), ('acctAlias', ''), ('balance', '')):
                if attribute in element.attrib:
                    element.attrib[attribute] = replacement
            xml_text += etree.tostring(element).decode("utf-8")
        return xml_text

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
        return IBKR_CorpActionType(xml_element.attrib[attr_name]).type

    def attr_currency(self, xml_element, attr_name, default_value):
        if attr_name not in xml_element.attrib:
            return default_value
        return self.currency_id(xml_element.attrib[attr_name])

    def attr_asset(self, xml_element, attr_name, default_value):
        if attr_name not in xml_element.attrib:
            return default_value
        if xml_element.attrib[attr_name] == '':
            return default_value
        asset_category = self.attr_asset_type(xml_element, 'assetCategory', None)
        if xml_element.tag == 'Trade' and asset_category == JSF.ASSET_MONEY:
            currency = xml_element.attrib[attr_name].split('.')
            symbol_id = [self.currency_symbol_id(code) for code in currency]
        elif xml_element.tag == 'Transfer' and asset_category == JSF.ASSET_MONEY:
            symbol_id = self.currency_symbol_id(xml_element.attrib['currency'])
        else:
            symbol = xml_element.attrib[attr_name].removesuffix(self.ReplacedSuffix)
            if asset_category == IBKR_AssetType.NotSupported:
                raise Statement_ImportError(self.tr("Asset type isn't supported: ") + f"'{asset_category}' ({symbol})")
            asset_data = {'symbol': symbol, 'type': asset_category}
            if xml_element.tag not in ['CorporateAction', 'CashTransaction'] and 'description' in xml_element.attrib:
                asset_data['name'] = xml_element.attrib['description']
            if asset_category != JSF.ASSET_MONEY:
                asset_data['currency'] = self.currency_id(xml_element.attrib['currency'])
            if 'isin' in xml_element.attrib and xml_element.attrib['isin']:
                asset_data['isin'] = xml_element.attrib['isin']
            if 'cusip' in xml_element.attrib and xml_element.attrib['cusip']:
                asset_data['cusip'] = xml_element.attrib['cusip']
            if xml_element.attrib.get('figi', ''):
                asset_data['figi'] = xml_element.attrib['figi']
            if self._is_exchange(xml_element.attrib.get('listingExchange', '')):
                asset_data['note'] = xml_element.attrib['listingExchange']
            if xml_element.tag == 'CashTransaction' and 'isin' not in asset_data and 'cusip' not in asset_data:
                asset_data.update(self._ids_by_action(xml_element))
            symbol_id = self.symbol_id(asset_data)
        return symbol_id

    # 'VALUE' and an empty name aren't stored as an exchange of a symbol
    @staticmethod
    def _is_exchange(name: str) -> bool:
        return bool(name) and name != 'VALUE'

    # ISIN and CUSIP for a cash transaction that has none: the ones that other records of its actionID agree on
    def _ids_by_action(self, xml_element) -> dict:
        action_id = xml_element.attrib.get('actionID', '')
        if not action_id or self._statement is None:
            return {}
        records = self._statement.findall(f".//CashTransaction[@actionID='{action_id}']")
        ids = {(x.attrib.get('isin', ''), x.attrib.get('cusip', '')) for x in records} - {('', '')}
        if len(ids) != 1:
            return {}
        return {key: value for key, value in zip(('isin', 'cusip'), ids.pop()) if value}

    def attr_account(self, xml_element, attr_name, default_value):
        if attr_name not in xml_element.attrib:
            return default_value
        if xml_element.tag == 'Trade' and self.attr_asset_type(xml_element, 'assetCategory', None) == JSF.ASSET_MONEY:
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
        account_ids = [self._account_id(xml_element.attrib[attr_name], self.currency_id(code)) for code in currency]
        return account_ids[0] if len(account_ids) == 1 else account_ids

    # Id of the account with the given (probably masked) number and currency, the account is created if there is none
    def _account_id(self, number, currency) -> int:
        match = [x for x in self._data[JSF.ACCOUNTS] if is_account(number, x['number']) and x['currency'] == currency]
        if len(match) > 1:
            raise Statement_ImportError(self.tr("Multiple account match for ") + f"{number}")
        if match:
            return match[0]['id']
        account = {"id": self._next_id(JSF.ACCOUNTS), "number": number, "currency": currency,
                   "precision": IBKR_CALCULATION_PRECISION}
        self._data[JSF.ACCOUNTS].append(account)
        return account['id']

    # Returns the id of the exact symbol record matching given ticker/isin (0 if not found).
    # Ambiguity (an isin-matched asset trading under several symbols, none matching the ticker) is a hard failure.
    def locate_symbol(self, symbol, isin) -> int:
        assets = [x for x in self._data[JSF.ASSETS] if any(s.get('isin') == isin for s in x[JSF.SYMBOLS])]
        if len(assets) == 1:
            candidates = assets[0][JSF.SYMBOLS]
            if len(candidates) == 1:
                return candidates[0]['id']
            named = [x for x in candidates if x['symbol'] == symbol]
            if len(named) == 1:
                return named[0]['id']
            raise Statement_ImportError(self.tr("Can't resolve an exact symbol for: ") + f"'{symbol}' ({isin})")
        candidates = [s for a in self._data[JSF.ASSETS] for s in a[JSF.SYMBOLS] if s['symbol'] == symbol]
        if len(candidates) == 1:
            return candidates[0]["id"]
        return 0

    def set_asset_country(self, symbol_id, country):
        self._symbol_asset(symbol_id)["country"] = country

    # IB report may be in form U***XXXX where XXXX are last account number digits.
    # In this case account number is fetched from database or error is thrown if account not found
    def unmask_account(self, masked_account: str) -> str:
        if not '*' in masked_account:
            return masked_account
        account_numbers = [x.number() for x in JalAccount.get_all_accounts() if is_account(masked_account, x.number())]
        if account_numbers:
            return account_numbers[0]
        raise Statement_ImportError(self.tr("Can't find account for a given masked account: ") +
                                    f"'{masked_account}'. " + self.tr("Please create one."))

    def load_header(self, header):
        self._data[JSF.PERIOD][0] = header['period_start']
        self._data[JSF.PERIOD][1] = self._end_of_date(header['period_end'])
        logging.info(self.tr("Load IB Flex-statement for account ") +
                     f"{header['account']}: {datetime.fromtimestamp(header['period_start'], tz=timezone.utc).strftime('%Y-%m-%d')}" +
                     f" - {datetime.fromtimestamp(header['period_end'], tz=timezone.utc).strftime('%Y-%m-%d')}")

    def load_accounts(self, balances):
        for i, balance in enumerate(sorted(balances, key=lambda x: x['currency'])):
            balance['id'] = i + 1
            balance['number'] = self.unmask_account(balance['number'])
            balance['precision'] = IBKR_CALCULATION_PRECISION
            self._data[JSF.ACCOUNTS].append(balance)

    def load_assets(self, assets):
        asset_count = 0
        for asset in assets:
            if asset['type'] == IBKR_AssetType.NotSupported:   # Skip not supported type of asset
                continue
            asset['symbol'] = asset['symbol'].removesuffix(self.ReplacedSuffix)
            if self._is_exchange(asset['exchange']):
                asset['note'] = asset['exchange']
            if asset['maturity']:
                asset['expiry'] = asset['maturity']
            if asset['expiry'] == 0:
                asset.pop('expiry')
            if asset['type'] == JSF.ASSET_BOND:
                asset['principal'] = int(asset['principal']) * IBKR_Asset.BondPrincipal if asset['principal'] else IBKR_Asset.BondPrincipal
            self.drop_extra_fields(asset,['maturity', 'exchange'])
            self.asset_id(asset)
            asset_count += 1
        logging.info(self.tr("Securities loaded: ") + f"{asset_count} ({len(assets)})")

    def load_ib_trades(self, ib_trades):
        trades = [trade for trade in ib_trades if type(trade['symbol']) == int]
        trades_loaded = self.load_trades(trades)

        transfers = [transfer for transfer in ib_trades if type(transfer['symbol']) == list]
        transfers_loaded = self.load_cash_deposits_withdrawals(transfers)

        logging.info(self.tr("Trades loaded: ") + f"{trades_loaded + transfers_loaded} ({len(ib_trades)})")

    def load_trades(self, trades):
        trade_base = self._next_id(JSF.TRADES)
        cnt = 0
        for i, trade in enumerate(sorted(trades, key=lambda x: x['timestamp'])):
            trade['id'] = trade_base + i
            trade['quantity'] = trade['quantity'] * trade['multiplier']
            if trade['settlement'] == 0:
                trade['settlement'] = trade['timestamp']
            asset = self._symbol_asset(trade['symbol'])
            if asset['type'] == JSF.ASSET_BOND:
                trade['quantity'] = trade['quantity'] / IBKR_Asset.BondPrincipal
                trade['price'] = trade['price'] * IBKR_Asset.BondPrincipal / Decimal('100')  # Bonds are priced in percents of principal
            trade['fee'] = -trade['fee'] if trade['fee'] != 0 else Decimal('0')  # otherwise we may have negative zero
            if trade['notes'] == StatementIBKR.CancelledFlag:
                trade['cancelled'] = True
            self.drop_extra_fields(trade, ["type", "proceeds", "multiplier", "exchange", "notes"])
            self._data[JSF.TRADES].append(trade)
            cnt += 1
        return cnt

    def load_cash_deposits_withdrawals(self, transfers):
        transfer_base = self._next_id(JSF.TRANSFERS)
        cnt = 0
        for i, transfer in enumerate(sorted(transfers, key=lambda x: x['timestamp'])):
            transfer['id'] = transfer_base + i
            if transfer['quantity'] > 0:
                transfer['account'][0], transfer['account'][1] = transfer['account'][1], transfer['account'][0]
                transfer['symbol'][0], transfer['symbol'][1] = transfer['symbol'][1], transfer['symbol'][0]
                transfer['quantity'], transfer['proceeds'] = transfer['proceeds'], transfer['quantity']
            transfer['withdrawal'] = abs(transfer.pop('quantity'))
            transfer['deposit'] = abs(transfer.pop('proceeds'))
            transfer['fee'] = -transfer['fee'] if transfer['fee'] != 0 else Decimal('0')  # otherwise we may have negative zero
            transfer['description'] = transfer['exchange']
            self.drop_extra_fields(transfer, ["type", "settlement", "price", "multiplier", "exchange", "notes"])
            self._data[JSF.TRANSFERS].append(transfer)
            cnt += 1
        return cnt

    def load_transfers(self, transfers):
        transfer_base = self._next_id(JSF.TRANSFERS)
        cnt = 0
        for i, transfer in enumerate(transfers):
            transfer['id'] = transfer_base + i
            if transfer['type'] != "INTERNAL":
                raise Statement_ImportError(self.tr("Only internal transfers are supported: ") + f"{transfer}")
            if self._symbol_asset(transfer['symbol'])['type'] == JSF.ASSET_MONEY:
                if transfer['direction'] == "OUT":
                    transfer['account'] = [transfer['account'], transfer.pop('account2'), 0]
                    transfer['withdrawal'] = transfer['deposit'] = -transfer.pop('amount')
                elif transfer['direction'] == "IN":
                    transfer['account'] = [transfer.pop('account2'), transfer['account'], 0]
                    transfer['withdrawal'] = transfer['deposit'] = transfer.pop('amount')
                else:
                    raise Statement_ImportError(self.tr("Unknown transfer direction: ") + f"{transfer}")
                transfer['symbol'] = [transfer['symbol'], transfer['symbol']]
                transfer['description'] = transfer.pop('type') + ' ' + transfer['description']
                transfer['fee'] = Decimal('0')
                self.drop_extra_fields(transfer, ["direction", "company", "quantity"])
            else:
                if transfer['direction'] != "IN":
                    raise Statement_ImportError(self.tr("Outgoing asset transfer not implemented yet: ") + f"{transfer}")
                transfer['account'] = [transfer.pop('account2'), transfer['account'], 0]
                transfer['symbol'] = [transfer['symbol'], transfer['symbol']]
                transfer['withdrawal'] = transfer['deposit'] = transfer.pop('quantity')
                transfer['description'] = transfer.pop('type') + f" TRANSFER ({transfer.pop('company')})"
                transfer['fee'] = Decimal('0')
                self.drop_extra_fields(transfer, ["direction", "amount"])
            self._data[JSF.TRANSFERS].append(transfer)
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
            if option['operation'] not in transaction_desctiption:
                raise Statement_ImportError(self.tr("Option E&A&E action isn't implemented: ") + f"{option['operation']}")
            trade = [x for x in self._data[JSF.TRADES] if x['account'] == option['account']
                     and x['symbol'] == option['symbol'] and x['number'] == option['number']]
            if len(trade) != 1:
                raise Statement_ImportError(
                    self.tr("Original trade not found for Option E&A&E operation: ") + f"{option}")
            trade[0]['note'] = transaction_desctiption[option['operation']]
            cnt += 1
        logging.info(self.tr("Options E&A&E loaded: ") + f"{cnt} ({len(options)})")

    def load_corporate_actions(self, actions):
        # A corporate action takes effect for a whole day
        for action in actions:
            action['timestamp_day_only'] = True
            action['quantity'] *= action.pop('multiplier')   # an option is counted in contracts
        self.check_corporate_action_ids(actions)
        self.remove_cancelled_corporate_actions(actions)
        cnt = 0
        for withdrawn, received in self.corporate_action_legs(actions):
            cnt += self.load_corporate_action(withdrawn, received)
        logging.info(self.tr("Corporate actions loaded: ") + f"{cnt} ({len(actions)})")

    # The actionID is the only link between the records of one corporate action, so every record has to carry it
    def check_corporate_action_ids(self, actions):
        missing = [x for x in actions if x['action_id'] == self.NoActionID]
        if missing:
            self._refuse_corp_action(missing, self.tr("every record has an 'actionID' attribute"),
                                     self.tr("Enable the field 'Action ID' for the section 'Corporate Actions' in "
                                             "the configuration of your Flex Query and get the statement again."))
        empty = [x for x in actions if not x['action_id']]
        if empty:
            self._refuse_corp_action(empty, self.tr("'actionID' attribute of every record has a value"))
        # An adjusted option gets another symbol, and FIGI is the only thing that tells it is the same option
        no_figi = [x for x in actions if x['asset_type'] == JSF.ASSET_OPTION and not x['figi']]
        if no_figi:
            self._refuse_corp_action(no_figi, self.tr("every record of an option has a 'figi' attribute"),
                                     self.tr("Enable the field 'FIGI' for the sections 'Corporate Actions', 'Trades' "
                                             "and 'Financial Instrument Information' in the configuration of your "
                                             "Flex Query and get the statement again."))

    # Records of one corporate action share an actionID - returns a (withdrawn, received) pair of record lists per action.
    # An option adjusted by an action of its underlying asset has the actionID of that action: it is an action of its own.
    def corporate_action_legs(self, actions) -> list:
        key_func = lambda x: (x['account'], x['symbol'], x['type'], x['description'], x['timestamp'])
        option_of = lambda x: self._symbol_asset(x['symbol'])['id'] if x['asset_type'] == JSF.ASSET_OPTION else 0
        groups = {}
        for action in sorted(actions, key=key_func):
            if action['quantity'] != 0:   # There might be 0 quantity value - it should be ignored
                groups.setdefault((action['action_id'], option_of(action)), []).append(action)
        legs = [([x for x in group if x['quantity'] < 0], [x for x in group if x['quantity'] > 0])
                for group in groups.values()]
        # Actions that give an asset go first, the ones that only take it away are after them
        return sorted(legs, key=lambda x: (not x[1], key_func((x[1] + x[0])[0])))

    # Checks that the records of an action are what its type has to have and stores the action
    def load_corporate_action(self, withdrawn, received) -> int:
        # Loader and the allowed numbers of (withdrawn, received) records for every type of action
        action_loaders = {
            JSF.ACTION_MERGER: (self.load_merger, [(1, 0), (1, 1), (1, 2)]),
            JSF.ACTION_SPINOFF: (self.load_spinoff, [(0, 1)]),
            JSF.ACTION_SYMBOL_CHANGE: (self.load_symbol_change, [(1, 1)]),
            JSF.PAYMENT_STOCK_DIVIDEND: (self.load_stock_dividend, [(0, 1)]),
            JSF.ACTION_SPLIT: (self.load_split, [(1, 0), (0, 1), (1, 1)]),
            JSF.ACTION_BOND_MATURITY: (self.load_bond_maturity, [(1, 0)]),
            JSF.ACTION_DELISTING: (self.load_delisting, [(1, 0)]),
            JSF.ACTION_RIGHTS_ISSUE: (self.load_none, [(1, 0), (0, 1)])
        }
        legs = withdrawn + received
        if any(len({x[field] for x in legs}) != 1 for field in ('type', 'account', 'timestamp')):
            self._refuse_corp_action(legs, self.tr("records of one action have the same type, account and date"))
        if len({x['symbol'] for x in legs}) != len(legs):
            self._refuse_corp_action(legs, self.tr("an action has one record per asset"))
        if legs[0]['type'] not in action_loaders:
            raise Statement_ImportError(self.tr("Corporate action type is not supported: ") + f"{legs[0]}")
        loader, allowed = action_loaders[legs[0]['type']]
        if (len(withdrawn), len(received)) not in allowed:
            self._refuse_corp_action(legs, self.tr("number of withdrawn (-) / received (+) records is ") +
                                     self.tr(" or ").join([f"{x}/{y}" for x, y in allowed]))
        return loader(withdrawn, received)

    # Stops the import: tells what was expected from the records of a corporate action and shows them as they are.
    # With no 'advice' given the user is asked to report the case and gets a dump of these records to attach.
    def _refuse_corp_action(self, legs, expected: str, advice: str = '') -> None:
        if not advice:
            advice = self.tr("Please create an issue at ") + f"{Setup.REPO_URL}/issues" + \
                     self.tr(" and attach the statement dump (its file name is in the log, the account number is "
                             "masked in it) - it helps to make JAL better. The former way of import, that matched "
                             "records by description, is kept under the git tag ") + f"'{self.FormerCorpActionsTag}'."
            try:
                self.save_corp_action_dump(legs)
            except Exception as e:
                logging.error(self.tr("Failed to collect debug information: ") + f"{e}")
        found = [f"    {ts2d(x['timestamp'])} quantity {remove_exponent(x['quantity'])}"
                 f" proceeds {remove_exponent(x['proceeds'])} actionID '{x['action_id']}'"
                 f" transactionID '{x['number']}' code '{x['code']}': {x['description']}" for x in legs]
        raise Statement_ImportError("\n".join([self.tr("Corporate action isn't what JAL expects it to be."),
                                               self.tr("Expected: ") + expected, self.tr("Found:")] + found + [advice]))

    # Saves statement records of the given corporate action and of the assets it mentions
    def save_corp_action_dump(self, legs):
        assert self._statement is not None
        elements = []
        for action_id in {x['action_id'] for x in legs if x['action_id'] and x['action_id'] != self.NoActionID}:
            elements += self._statement.findall(f".//CorporateAction[@actionID='{action_id}']")
        for symbol in {x['symbol'] for x in legs}:
            elements += [x for x in self._asset_elements(symbol) if x not in elements]
        debug_info = 'Statement data:\n----------------------------------------------------------------\n'
        debug_info += self._masked_xml(elements)
        debug_info += "----------------------------------------------------------------\n"
        super().save_debug_info(debug_info=debug_info)

    @staticmethod
    def normalize_corp_action_symbol(symbol: str) -> str:
        # Some IBKR descriptions prefix the old symbol with a 14-digit timestamp-like value.
        normalized = re.sub(r"^\d{14}(?=\w)", "", symbol)
        return normalized if normalized else symbol

    # Takes cancelled corporate actions and tries to find and remove original one form actions list
    def remove_cancelled_corporate_actions(self, actions):
        delete_elements = []
        cancelled_actions = [(idx, action) for idx, action in enumerate(actions) if action['code'] == StatementIBKR.CancelledFlag]
        for c_id, c_action in cancelled_actions:
            matched = [idx for (idx, action) in enumerate(actions) if
                       action["type"] == c_action["type"] and action["account"] == c_action["account"] and
                       action["symbol"] == c_action["symbol"] and action["timestamp"] == c_action["timestamp"] and
                       action["description"] == c_action["description"] and action["quantity"] == -c_action["quantity"]]
            if len(matched) == 1:
                delete_elements += [c_id, matched[0]]
        for idx in sorted(delete_elements, reverse=True):
            del actions[idx]
        if delete_elements:
            logging.warning(self.tr("A cancelled corporate action was dropped together with its cancellation. "
                                    "JAL has no example of such statement, please share yours at ") +
                            f"{Setup.REPO_URL}/issues")
        unmatched = [x for x in actions if x['code'] == StatementIBKR.CancelledFlag]
        if unmatched:
            self._refuse_corp_action(unmatched, self.tr("a cancellation repeats the record it cancels with an "
                                                        "opposite quantity"))

    # Dummy loader to skip some corporate actions
    def load_none(self, _withdrawn, _received) -> int:
        return 0

    # Quantity of a corporate action record in pieces (IBKR gives bonds by their face value)
    @staticmethod
    def _corp_action_qty(leg) -> Decimal:
        return leg['quantity'] / (IBKR_Asset.BondPrincipal if leg['asset_type'] == JSF.ASSET_BOND else Decimal('1'))

    # Stores a corporate action record that was already given its 'symbol', 'quantity' and 'outcome'
    def _store_corp_action(self, action) -> None:
        action['id'] = self._next_id(JSF.CORP_ACTIONS)
        self.drop_extra_fields(action, ["value", "proceeds", "code", "asset_type", "action_id", "currency", "figi"])
        self._data[JSF.CORP_ACTIONS].append(action)

    # Stores an asset that was withdrawn for money as a sell trade, at the price that its proceeds give
    def _store_sale(self, record) -> None:
        record['id'] = self._next_id(JSF.TRADES)
        record['quantity'] = self._corp_action_qty(record)
        record['settlement'] = record['timestamp']    # Settled by the same date
        record['price'] = self._derived_price(record['proceeds'], record['quantity'])
        record['note'] = record.pop('description')
        record['fee'] = Decimal('0')
        self.drop_extra_fields(record, ["type", "value", "proceeds", "code", "asset_type", "action_id", "currency",
                                        "timestamp_day_only", "figi"])
        self._data[JSF.TRADES].append(record)

    def load_merger(self, withdrawn, received) -> int:
        old = withdrawn[0]
        if not received:  # Asset converted to money -> store it as a sell trade
            if not old['proceeds']:
                self._refuse_corp_action(withdrawn, self.tr("an asset withdrawn for nothing in exchange has proceeds"))
            self._store_sale(old)
            return 1
        action = received[0]
        action['outcome'] = [{'symbol': x['symbol'], 'quantity': self._corp_action_qty(x), 'share': Decimal('0')}
                             for x in received]
        if old['proceeds']:  # Cash payment is a part of corporate action
            if 'CASH' not in old['description'].upper():
                self._refuse_corp_action(withdrawn + received,
                                         self.tr("a merger that pays proceeds has 'CASH' in its description"))
            payment = {'symbol': self.currency_symbol_id(old['currency']),
                       'quantity': old['proceeds'], 'share': Decimal('0')}
            action['outcome'].insert(0, payment)
        action['symbol'] = old['symbol']
        action['quantity'] = -self._corp_action_qty(old)
        self._store_corp_action(action)
        return len(withdrawn) + len(received)

    def load_spinoff(self, _withdrawn, received) -> int:
        SpinOffPattern = r"^(?P<symbol_old>.*)\((?P<isin_old>\w+)\) +SPINOFF +(?P<X>\d+) +FOR +(?P<Y>\d+) +\((?P<symbol>.*), (?P<name>.*), (?P<id>\w+)\)$"

        action = received[0]
        parts = re.match(SpinOffPattern, action['description'], re.IGNORECASE)
        if parts is None:
            raise Statement_ImportError(self.tr("Can't parse Spin-off description ") + f"'{action}'")
        spinoff = parts.groupdict()
        spinoff['symbol_old'] = self.normalize_corp_action_symbol(spinoff['symbol_old'])
        symbol_old = self.locate_symbol(spinoff['symbol_old'], spinoff['isin_old'])
        if not symbol_old:
            raise Statement_ImportError(self.tr("Spin-off initial asset not found ") + f"'{action}'")
        qty_old = int(spinoff['Y']) * action['quantity'] / int(spinoff['X'])
        rounded_qty_old = round(qty_old)
        # IBKR may report a rounded whole-number spin-off quantity after dropping fractional entitlements.
        implied_spinoff_qty = Decimal(rounded_qty_old) * int(spinoff['X']) / int(spinoff['Y'])
        if abs(rounded_qty_old - qty_old) > Decimal('0.01') and abs(implied_spinoff_qty - action['quantity']) >= Decimal('1'):
            raise Statement_ImportError(self.tr("Spin-off rounding error is too big ") + f"'{action}'")
        qty_old = rounded_qty_old
        action['outcome'] = [{'symbol': symbol_old, 'quantity': qty_old, 'share': Decimal('0')},
                             {'symbol': action['symbol'], 'quantity': action['quantity'], 'share': Decimal('0')}]
        action['symbol'] = symbol_old
        action['quantity'] = qty_old
        self._store_corp_action(action)
        return 1

    def load_symbol_change(self, withdrawn, received) -> int:
        action = received[0]
        action['outcome'] = [{'symbol': action['symbol'], 'quantity': action['quantity'], 'share': Decimal('1')}]
        action['symbol'] = withdrawn[0]['symbol']
        action['quantity'] = -withdrawn[0]['quantity']
        self._store_corp_action(action)
        return 2

    def load_stock_dividend(self, _withdrawn, received) -> int:
        StockDividendPattern = r"^(?P<description>.*) +(?P<tail>\(.*\))$"

        action = received[0]
        parts = re.match(StockDividendPattern, action['description'], re.IGNORECASE)
        if parts is None:
            raise Statement_ImportError(self.tr("Can't parse Stock Dividend description ") + f"'{action}'")
        action['description'] = parts.groupdict()['description']

        action['id'] = self._next_id(JSF.ASSET_PAYMENTS)
        action['amount'] = action['quantity']
        action['price'] = self._derived_price(action['value'], action['quantity'])
        action['tax'] = Decimal('0')
        self.drop_extra_fields(action, ["quantity", "value", "proceeds", "code", "asset_type", "action_id", "currency",
                                        "figi"])
        self._data[JSF.ASSET_PAYMENTS].append(action)
        return 1

    def load_split(self, withdrawn, received) -> int:
        SplitPattern = r"^(?P<symbol_old>.*)\((?P<isin_old>\w+)\) +SPLIT +(?P<X>\d+) +FOR +(?P<Y>\d+) +\((?P<symbol>.*), (?P<name>.*), (?P<id>\w+)*\)$"

        action = (received + withdrawn)[0]
        if withdrawn and received:  # Split together with ISIN change: old asset is withdrawn and new one is received
            action['outcome'] = [{'symbol': action['symbol'], 'quantity': action['quantity'], 'share': Decimal('1')}]
            action['symbol'] = withdrawn[0]['symbol']
            action['quantity'] = -withdrawn[0]['quantity']
        else:  # Simple split without ISIN change: the only record is a change of quantity
            parts = re.match(SplitPattern, action['description'], re.IGNORECASE)
            if parts is None:
                raise Statement_ImportError(self.tr("Can't parse Split description ") + f"'{action}'")
            if parts['id'] is not None and parts['isin_old'] != parts['id']:
                self._refuse_corp_action([action], self.tr("a split that changes ISIN has a withdrawn (-) and "
                                                           "a received (+) record"))
            qty_delta = action['quantity']
            # Not qty_delta / (X/Y - 1): a ratio like 7/3 has no exact decimal form
            qty_old = remove_exponent(qty_delta * int(parts['Y']) / (int(parts['X']) - int(parts['Y'])))
            action['outcome'] = [{'symbol': action['symbol'], 'quantity': qty_old + qty_delta, 'share': Decimal('1')}]
            action['quantity'] = qty_old
        self._store_corp_action(action)
        return len(withdrawn) + len(received)

    # Bond maturity is stored as a sale of the bond
    def load_bond_maturity(self, withdrawn, _received) -> int:
        self._store_sale(withdrawn[0])
        return 1

    def load_delisting(self, withdrawn, _received) -> int:
        action = withdrawn[0]
        # There might be delisting for issued rights - we don't need to store it as it isn't a real asset
        asset = self._symbol_asset(action['symbol'])
        if asset['type'] == JSF.ASSET_RIGHTS:
            return 0
        action['quantity'] = -action['quantity']
        action['outcome'] = []
        self._store_corp_action(action)
        return 1

    def load_granted_stocks(self, granted_stocks):
        cnt = 0
        # Get each operation type
        VestingPattern = r"^Stock Award (?P<operation>Grant for Cash Deposit|Vesting|Withholding)$"
        for vesting in granted_stocks:
            try:
                vesting['operation'] = re.match(VestingPattern, vesting['description']).groupdict()['operation']
            except AttributeError:
                raise Statement_ImportError(self.tr("Can't parse granted stock description ") + f"'{vesting}'")
        # Subtract withholding from vesting value
        vestings = [x for x in deepcopy(granted_stocks) if x['operation'] == "Vesting"]
        withholdings = [x for x in deepcopy(granted_stocks) if x['operation'] == "Withholding"]
        for withholding in withholdings:
            main_data = lambda x: {i: x[i] for i in x if i not in ['description', 'operation', 'amount']}
            matched_vesting = [x for x in vestings if main_data(x) == main_data(withholding)]
            if not matched_vesting:
                raise Statement_ImportError(self.tr("Stock award withholding matches no vesting ") + f"'{withholding}'")
            if len(matched_vesting) == 1:
                matched_vesting[0]['amount'] += withholding['amount']
            if len(matched_vesting) > 1:
                raise Statement_ImportError(self.tr("Multiple vesting matched withholding ") + f"'{matched_vesting}' / '{withholding}'")
        asset_payments_base = self._next_id(JSF.ASSET_PAYMENTS)
        for i, vesting in enumerate(vestings):
            vesting['id'] = asset_payments_base + i
            vesting['type'] = JSF.PAYMENT_STOCK_VESTING
            vesting['timestamp'] = vesting['vesting_date']
            self.drop_extra_fields(vesting, ["operation", "award_date", "vesting_date"])
            self._data[JSF.ASSET_PAYMENTS].append(vesting)
            cnt += 1
        logging.info(self.tr("Stock grant operations loaded: ") + f"{cnt} ({len(granted_stocks)})")

    def load_cash_transactions(self, cash):
        cnt = 0
        self._refuse_unsupported_cash(cash)
        # Records are picked by type here, as their fields (the type as well) are changed below
        of_type = lambda *types: [x for x in cash if x['type'] in types]
        without_tid = lambda records: [{key: x[key] for key in x if key != 'tid'} for x in records]
        dividends = without_tid(of_type('Dividends', 'Payment In Lieu Of Dividends'))
        bond_interests = of_type('Bond Interest Paid', 'Bond Interest Received')
        taxes = without_tid(of_type('Withholding Tax'))
        transfers = of_type('Deposits/Withdrawals')
        fees = of_type('Other Fees', 'Commission Adjustments', 'Broker Interest Paid', 'Broker Interest Received')
        # A fee that names an asset (an ADR fee) is a fee of that asset, the rest are ordinary spendings
        is_asset_fee = lambda x: x['symbol'] and x['type'] in ('Other Fees', 'Commission Adjustments')
        asset_fees = [x for x in fees if is_asset_fee(x)]
        fees = [x for x in fees if not is_asset_fee(x)]

        dividends = self.aggregate_dividends(dividends)
        asset_payments_base = self._next_id(JSF.ASSET_PAYMENTS)
        for i, dividend in enumerate(dividends):
            dividend['id'] = asset_payments_base + i
            dividend['type'] = JSF.PAYMENT_DIVIDEND
            dividend['number'] = dividend.pop('action_id')  # Mandatory to match taxes
            self.drop_extra_fields(dividend, ["currency", "reported"])
            self._data[JSF.ASSET_PAYMENTS].append(dividend)
            cnt += 1
        asset_payments_base += cnt
        for i, bond_interest in enumerate(bond_interests):
            bond_interest['id'] = asset_payments_base + i
            bond_interest['type'] = JSF.PAYMENT_INTEREST
            self.drop_extra_fields(bond_interest, ["currency", "reported", "tid", "action_id"])
            self._data[JSF.ASSET_PAYMENTS].append(bond_interest)
            cnt += 1

        for tax in self.aggregate_taxes(taxes):
            cnt += self.apply_tax_withheld(tax)

        transfer_base = self._next_id(JSF.TRANSFERS)
        for i, transfer in enumerate(transfers):
            transfer['id'] = transfer_base + i
            transfer['number'] = transfer.pop('tid')
            transfer['symbol'] = [self._single_symbol_of(transfer["currency"])] * 2
            if transfer['amount'] >= 0:  # Deposit
                transfer['account'] = [0, transfer['account'], 0]
                transfer['withdrawal'] = transfer['deposit'] = transfer['amount']
            else:  # Withdrawal
                transfer['account'] = [transfer['account'], 0, 0]
                transfer['withdrawal'] = transfer['deposit'] = -transfer['amount']
            transfer['fee'] = Decimal('0')
            self.drop_extra_fields(transfer, ["type", "amount", "timestamp_day_only", "currency", "reported", "action_id"])
            self._data[JSF.TRANSFERS].append(transfer)
            cnt += 1

        payment_base = self._next_id(JSF.INCOME_SPENDING)
        asset_payments_base = self._next_id(JSF.ASSET_PAYMENTS)
        for i, fee in enumerate(asset_fees):
            fee['id'] = asset_payments_base + i
            fee['type'] = JSF.PAYMENT_FEE
            fee['number'] = fee.pop('action_id') or fee['number']   # a commission adjustment has a trade id only
            self.drop_extra_fields(fee, ["currency", "reported", "tid"])
            self._data[JSF.ASSET_PAYMENTS].append(fee)
            cnt += 1
        for i, fee in enumerate(fees):
            fee['id'] = payment_base + i
            fee['peer'] = 0
            category = PredefinedCategory.Interest if fee['type'] == 'Broker Interest Received' else PredefinedCategory.Fees
            fee['lines'] = [{'amount': fee['amount'], 'category': category, 'description': fee['description']}]
            self.drop_extra_fields(fee, ["type", "amount", "timestamp_day_only", "description", "symbol", "number", "currency", "reported", "tid", "action_id"])
            self._data[JSF.INCOME_SPENDING].append(fee)
            cnt += 1

        logging.info(self.tr("Cash transactions loaded: ") + f"{cnt} ({len(cash)})")

    # Stops the import if the statement has a cash transaction of a type that JAL doesn't import
    def _refuse_unsupported_cash(self, cash):
        unsupported = [x for x in cash if x['type'] not in self.CashTransactionTypes]
        if unsupported:
            found = [f"    {ts2d(x['timestamp'])} '{x['type']}' {remove_exponent(x['amount'])}: {x['description']}"
                     for x in unsupported]
            raise Statement_ImportError("\n".join(
                [self.tr("Import cancelled, cash transactions of unsupported type were found:")] + found))

    # Takes out of 'payments' the first record that is equal to 'target'. The comparison is repeated without the
    # fields of every next element of 'ignored' until something matches. Returns the index of that element, -1 if none
    @staticmethod
    def _take_matching(payments: list, target: dict, ignored: list) -> int:
        for i, fields in enumerate(ignored):
            compared = lambda x: {key: x[key] for key in x if key not in fields}
            matched = [x for x in payments if compared(x) == compared(target)]
            if matched:
                payments.remove(matched[0])
                return i
        return -1

    # Method takes a list of dividend dictionaries and checks for REVERSAL and CANCEL
    # For such description it looks for matching record (for the same symbol) with opposite amount and the same payment
    # and report dates. Description may be different!
    def aggregate_dividends(self, dividends: list) -> list:
        is_reversal = lambda x: self.ReversalSuffix in x or x.startswith(self.CancelPrefix)
        payments = [x for x in deepcopy(dividends) if not is_reversal(x['description'])]
        reversals = [x for x in deepcopy(dividends) if is_reversal(x['description'])]
        # Fields that are left out of comparison and what is said about a match found that way
        matches = [((), logging.info, self.tr("Payment was reversed: ")),
                   (('description',), logging.warning, self.tr("Payment was reversed by approximate description: ")),
                   (('reported',), logging.warning, self.tr("Payment was reversed with different reported date: "))]
        for reversal in reversals:
            description = reversal['description'].replace(self.ReversalSuffix, '').replace(self.CancelPrefix, '')
            target = {**reversal, 'description': description, 'amount': -reversal['amount']}
            matched = self._take_matching(payments, target, [x[0] for x in matches])
            if matched < 0:
                raise Statement_ImportError(self.tr("Can't find match for reversal: ") + f"{reversal}")
            _, log, message = matches[matched]
            log(message + f"{ts2dt(target['timestamp'])}, '{target['description']}': {target['amount']}")
        return payments

    # Method takes a list of taxes and checks if we have the same amount added and deducted the same day,
    # joins the parts of a tax together and stores extra taxes of MLP as fees. Returns the taxes to apply to dividends
    def aggregate_taxes(self, taxes: list) -> list:
        taxes = self._drop_reversed_taxes(taxes)
        taxes = self._join_taxes_in_lieu(taxes)
        return self._store_mlp_extra_taxes(taxes)

    # A returned tax takes away the tax it returns: an exact match first, then with another report date,
    # then with another description as well. A returned tax that matches nothing is kept
    def _drop_reversed_taxes(self, taxes: list) -> list:
        payments = [x for x in deepcopy(taxes) if x['amount'] < 0]
        reversals = [x for x in deepcopy(taxes) if x['amount'] > 0]
        not_matched_reversals = []
        for reversal in reversals:
            target = {**reversal, 'description': reversal['description'].replace(self.CancelPrefix, ''),
                      'amount': -reversal['amount']}
            if self._take_matching(payments, target, [(), ('reported',), ('description', 'reported')]) < 0:
                not_matched_reversals.append(reversal)
        return payments + not_matched_reversals

    # Sometimes IB split tax in several parts for Payment in Lieu of Dividend
    # Below code aggregates such taxes but only negative values (positive might be a correction of previous tax)
    def _join_taxes_in_lieu(self, taxes: list) -> list:
        key_func = lambda x: (x['account'], x['symbol'], x['currency'], x['description'], x['timestamp'], x['reported'])
        taxes_sorted = sorted(taxes, key=key_func)
        tax_in_lieu = [x for x in taxes_sorted if x['amount'] < 0 and 'PAYMENT IN LIEU OF DIVIDEND' in x['description']]
        other_taxes = [x for x in taxes_sorted if x not in tax_in_lieu]
        lieu_aggregated = []
        for _, group in groupby(tax_in_lieu, key=key_func):
            group_list = list(group)
            part = group_list[0]  # Take fist of several actions as a basis
            part['amount'] = sum(tax['amount'] for tax in group_list)  # and update quantity in it
            lieu_aggregated.append(part)
        return sorted(other_taxes + lieu_aggregated, key=key_func)

    # There might be additional record to withhold 10% of extra tax on partnerships (currently faced for MLP) reported
    # in different dates. It is stored as a fee of the asset, the rest of the taxes is returned
    def _store_mlp_extra_taxes(self, taxes: list) -> list:
        key_func = lambda x: (x['account'], x['symbol'], x['currency'], x['description'], x['timestamp'])
        mlp_taxes = [x for x in taxes if self._symbol_asset(x['symbol'])['type'] == JSF.ASSET_MLP]
        non_mlp_taxes = [x for x in taxes if x not in mlp_taxes]
        mlp_processed = []
        for _, group in groupby(mlp_taxes, key=key_func):
            group_list = sorted(list(group), key=lambda x: (x['amount']))
            extra_taxes = [x for x in group_list if self._is_mlp_extra_tax(x)]
            for tax in extra_taxes:
                tax['id'] = self._next_id(JSF.ASSET_PAYMENTS)
                tax['type'] = JSF.PAYMENT_FEE
                tax['description'] += " - Extra 10% tax due to IRS section 1446"
                self.drop_extra_fields(tax, ["source", "currency", "reported", "action_id"])
                self._data[JSF.ASSET_PAYMENTS].append(tax)
            group_list = [x for x in group_list if x not in extra_taxes]
            if len(group_list) > 2:
                raise Statement_ImportError(self.tr("Too many records for MLP tax: ") + f"{group_list}")
            mlp_processed.extend(group_list)
        return sorted(non_mlp_taxes + mlp_processed, key=key_func)

    # True for a tax that is 10% of a dividend paid for the same asset at the same time (to within a cent)
    def _is_mlp_extra_tax(self, tax: dict) -> bool:
        if tax['amount'] >= 0:
            return False
        amounts = [x['amount'] for x in self._data[JSF.ASSET_PAYMENTS] if
                   (x['type'] == JSF.PAYMENT_DIVIDEND or x['type'] == JSF.PAYMENT_STOCK_DIVIDEND)
                   and x['symbol'] == tax['symbol'] and x['account'] == tax['account'] and x['timestamp'] == tax['timestamp']]
        amounts += [x.amount() for x in self._db_dividends(tax) if x.timestamp() == tax['timestamp']]
        return any(abs(Decimal('0.1') * abs(amount) - abs(tax['amount'])) <= Decimal('0.01') for amount in amounts)

    def load_taxes(self, taxes):
        cnt = 0
        for tax in taxes:
            if tax['source'] == 'TRADE':
                trade = self._find_in_list(self._data[JSF.TRADES], "number", tax['number'])
                if trade is None:
                    raise Statement_ImportError(self.tr("Can't find trade for tax: ") + f"{ts2dt(tax['timestamp'])}, '{tax['symbol']}' - {tax['description']}")
                trade['fee'] -= tax['amount']   # a charged tax is negative, the fee of a trade is a positive cost
                cnt += 1
            else:
                if tax['source'] != 'STANDALONE':
                    logging.warning(self.tr("Unexpected tax source: ") + f"{ts2dt(tax['timestamp'])}, '{tax['source']}': {tax['description']}")
                tax['id'] = self._next_id(JSF.ASSET_PAYMENTS)
                tax['type'] = JSF.PAYMENT_FEE
                self.drop_extra_fields(tax, ["source", "number"])
                self._data[JSF.ASSET_PAYMENTS].append(tax)
                cnt += 1
        logging.info(self.tr("Transaction taxes loaded: ") + f"{cnt} ({len(taxes)})")

    def load_sales_taxes(self, taxes):
        cnt = 0
        id_base = self._next_id(JSF.INCOME_SPENDING)
        for i, tax in enumerate(taxes):
            tax['id'] = id_base + i
            tax['peer'] = 0
            rate = format_decimal(Decimal('100') * Decimal(tax['tax_rate']))
            text = f"{tax['tax_type']} {tax['country']} {rate}%: {-tax['taxable_amount']} {tax['currency']} {tax['description']}"
            tax['lines'] = [{'amount': tax['amount'], 'category': PredefinedCategory.Taxes, 'description': text}]
            self.drop_extra_fields(tax, ["amount", "currency", "description", "country", "tax_type", "tax_rate", "taxable_amount",])
            self._data[JSF.INCOME_SPENDING].append(tax)
            cnt += 1
        logging.info(self.tr("Sales taxes loaded: ") + f"{cnt} ({len(taxes)})")

    def load_cfd_charges(self, charges):
        cnt = 0
        for charge in charges:
            if charge['symbol'] != self.NoAsset:   # A charge that names an asset is a fee of that asset
                if not charge['description'].startswith('CFD BORROW FEE FOR'):
                    logging.warning(self.tr("Unknown CFD charge description: ") + charge['description'])
                charge['id'] = self._next_id(JSF.ASSET_PAYMENTS)
                charge['type'] = JSF.PAYMENT_FEE
                self._data[JSF.ASSET_PAYMENTS].append(charge)
                cnt += 1
                continue
            if not (charge['description'].startswith('LONG CFD INTEREST FOR') or
                    charge['description'].startswith('SHORT CFD INTEREST FOR')):
                raise Statement_ImportError(self.tr("Unsupported CFD charge: ") + f"{ts2d(charge['timestamp'])} "
                                            f"{remove_exponent(charge['amount'])}: {charge['description']}")
            charge['id'] = self._next_id(JSF.INCOME_SPENDING)
            charge['peer'] = 0
            charge['lines'] = [{'amount': charge['amount'], 'category': PredefinedCategory.Fees, 'description': charge['description']}]
            self.drop_extra_fields(charge, ["amount", "symbol", "description", "number"])
            self._data[JSF.INCOME_SPENDING].append(charge)
            cnt += 1
        logging.info(self.tr("CFD charges loaded: ") + f"{cnt} ({len(charges)})")

    # Applies a withholding tax to the dividend it was withheld from.
    #
    # A tax is not an operation of its own in JAL - it is a property of the payment it was taken out of, so every
    # such record has to find that payment first. The link is the actionID: IBKR gives the dividend, the tax withheld
    # from it and every later correction of that tax one and the same 'actionID', and keeps it stable across annual
    # statements.
    #
    # A negative amount is tax being taken, a positive one is tax being given back. Both are applied the same way:
    # the tax the payment carries is moved by what this statement says about it, so that several records of one
    # action (a full reversal followed by a smaller re-charge, which is how a tax for ETF holding government paper is
    # corrected next year) arrive at the right figure whatever order they are read in.
    def apply_tax_withheld(self, tax) -> int:
        TaxFullPattern = r"^(?P<description>.*) - (?P<country>\w\w) TAX$"

        parts = re.match(TaxFullPattern, tax['description'], re.IGNORECASE)
        if parts:   # a description without a country leaves the country of the asset as it is
            self.set_asset_country(tax['symbol'], parts.groupdict()['country'].lower())

        dividend = self.find_dividend4tax(tax)      # refuses the whole statement if it finds no single payment
        new_tax = dividend.get('tax', Decimal('0')) - tax['amount']
        if self.mapped_id(JSF.ASSET_PAYMENTS, dividend['id']):
            # Notification is required if we adjust data for dividend that is already in Jal DB
            logging.info(self.tr("Tax adjustment for dividend: ") +
                         f"{remove_exponent(dividend.get('tax', Decimal('0')))} -> {remove_exponent(new_tax)}"
                         f" ({ts2dt(dividend['timestamp'])} {dividend['description']})")
        dividend["tax"] = new_tax
        # append new dividend if it came from DB and haven't been loaded in self._data yet
        if len([1 for x in self._data[JSF.ASSET_PAYMENTS] if x['id'] == dividend['id']]) == 0:
            dividend['type'] = JSF.PAYMENT_DIVIDEND
            self._data[JSF.ASSET_PAYMENTS].append(dividend)
        return 1

    # The dividend a withholding tax belongs to. There is no answer of "none": a tax that cannot be placed stops the
    # import, because the alternative is a statement that looks imported while a payment silently keeps a tax that
    # was corrected months ago - and nothing afterwards would say so.
    #
    # Candidates come from this statement and from the database alike, because a correction reaches JAL months after
    # the payment it corrects and usually in the statement of the following year, by which time the payment is
    # stored. They are looked up by the actionID. Anything else is left for the user to sort out by hand and said so
    # plainly.
    #
    # A payment stored before this id was recorded carries none, and so does a statement old enough to predate it.
    # Either case falls back to the day the payment was made, which is what the statements offered instead. The
    # fallback is deliberately narrow - the same day, the same account, the same asset, and exactly one candidate,
    # never a best guess among several - and it dies out on its own as such payments age out of the corrections
    # window.
    def find_dividend4tax(self, tax) -> dict:
        action_id = tax.get('action_id', '')
        candidates = [x for x in self._data[JSF.ASSET_PAYMENTS]
                      if (x['type'] == JSF.PAYMENT_DIVIDEND or x['type'] == JSF.PAYMENT_STOCK_DIVIDEND)
                      and x['symbol'] == tax['symbol'] and x['account'] == tax['account']]
        # A stored payment that an earlier tax of this same statement already pulled in is not a second candidate -
        # it is the very record now sitting in the statement, and the one there carries the tax applied since.
        known = [x['id'] for x in candidates]
        candidates += [x for x in self._stored_dividends(tax) if x['id'] not in known]
        if action_id:
            matched = [x for x in candidates if x.get('number') == action_id]
            if len(matched) == 1:
                return matched[0]
            if matched:
                self._refuse_unmatched_tax(tax, matched, self.tr("several payments carry this corporate action id"))
        same_day = [x for x in candidates if ts2d(x['timestamp']) == ts2d(tax['timestamp'])]
        if len(same_day) == 1:
            return same_day[0]
        self._refuse_unmatched_tax(tax, same_day if same_day else candidates,
                                   self.tr("no single payment of that day to fall back on") if action_id
                                   else self.tr("the statement gives no corporate action id to match on"))

    # Dividends of the account and asset of the given tax that are already in the database
    def _db_dividends(self, tax) -> list:
        try:
            db_account = self._map_db_account(tax['account'])
            db_asset = self._map_db_asset_by_symbol(tax['symbol'])
        except RuntimeError:
            return []
        if not db_account or not db_asset:
            return []
        return (AssetPayment.get_list(db_account, db_asset, AssetPayment.Dividend) +
                AssetIncome.get_list(db_account, db_asset, AssetIncome.StockDividend))

    # The same dividends in the shape a statement record has.
    def _stored_dividends(self, tax) -> list:
        return [{
            "id": self.statement_payment_id(payment.oid()),
            "account": tax['account'],
            "symbol": tax['symbol'],
            "timestamp": payment.timestamp(),
            "number": payment.number(),
            "amount": payment.amount(),
            "tax": payment.tax(),
            "description": payment.note()
        } for payment in self._db_dividends(tax)]

    # Stops the import and leaves behind everything needed to work out why.
    #
    # The message names what could not be placed and what was considered instead, in terms a user can read; beside it
    # save_debug_info() writes the records of this asset as the statement gives them and as the database holds them,
    # with the account number masked out, so that the file can be sent on to be looked at without sending anything
    # about the rest of the portfolio with it. Failing to write that file must not hide the reason for stopping, so
    # it is attempted separately from the refusal itself.
    def _refuse_unmatched_tax(self, tax, candidates: list, reason: str) -> None:
        symbol = self._symbol(tax['symbol'])
        description = (f"{symbol['symbol']} ({symbol.get('isin', '')})"
                       f" {ts2d(tax['timestamp'])} reported {ts2d(tax['reported'])}"
                       f" amount {remove_exponent(tax['amount'])} action {tax.get('action_id') or '-'}")
        logging.error(self.tr("Withholding tax matches no payment: ") + reason)
        logging.error(f"    {description}")
        logging.error(self.tr("    Payments considered: ") + f"{len(candidates)}")
        for payment in candidates:
            logging.error(f"      {ts2d(payment['timestamp'])} amount {remove_exponent(payment['amount'])}"
                          f" tax {remove_exponent(payment.get('tax', Decimal('0')))} action {payment.get('number') or '-'}")
        try:
            self.save_debug_info(account=tax['account'], symbol=tax['symbol'])
        except Exception as e:
            logging.error(self.tr("Failed to collect debug information: ") + f"{e}")
        raise Statement_ImportError(self.tr("Import cancelled, withholding tax matches no payment: ") + description)

    # Assign ex-date from dividend accruals
    def load_dividend_accruals(self, accruals):
        posted = [x for x in accruals if x['code'] == StatementIBKR.ReversalCode]
        for accrual in posted:
            dividends = [x for x in self._data[JSF.ASSET_PAYMENTS] if x['account']==accrual['account'] and x['symbol']==accrual['symbol'] and ts2d(x['timestamp'])==ts2d(accrual['timestamp']) and x['amount']==-accrual['amount']]
            if len(dividends) == 1:
                dividend = dividends[0]
            else:
                continue
            dividend['ex_date'] = accrual['ex_date']

    # Removes data that was used during XML processing but isn't needed in final output:
    # Drop any assets with type 'right' as JAL won't import them
    def strip_unused_data(self):
        rights_id = [x['id'] for x in self._data[JSF.ASSETS] if x['type'] == JSF.ASSET_RIGHTS]
        for asset_id in rights_id:
            self.remove_asset(asset_id)

    # -----------------------------------------------------------------------------------------------------------------------
    @staticmethod
    def order_statements(statementFiles) -> list:
        READ_COUNT=1024
        pattern = re.compile(r'<FlexStatement.*fromDate=\"([0-9]*)\"\stoDate=\"([0-9]*)\".*>')
        files = []
        for file in statementFiles:
            with open(file) as f:
                m = re.search(pattern, f.read(READ_COUNT))
                if not m:
                    logging.error(QApplication.translate("StatementIBKR", "Can't find a FlexStatement in first {} bytes of {}").format(READ_COUNT, file))
                    return []
                start = int(m.group(1))
                end = int(m.group(2))
                item = [start, end, file]
                idx = 0
                for i in files:
                    if item[1] <= i[0]:
                        break
                    idx += 1
                files.insert(idx, item)
        return [x[2] for x in files]
