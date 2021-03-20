import logging
import re
from datetime import datetime, timezone
from itertools import groupby
from lxml import etree

from jal.constants import TransactionType, PredefinedAsset, PredefinedCategory, CorporateAction, DividendSubtype
from jal.widgets.helpers import g_tr, ManipulateDate
from jal.db.update import JalDB
from jal.db.helpers import executeSQL, readSQL, get_country_by_code, update_asset_country


# -----------------------------------------------------------------------------------------------------------------------
class IBKRCashOp:
    Dividend = 0
    TaxWithhold = 1
    DepositWithdrawal = 2
    Fee = 3
    Interest = 4
    BondInterest = 5


# -----------------------------------------------------------------------------------------------------------------------
#TODO Check dividend parsing for "RDS B" stock (see example here https://github.com/KonishchevDmitry/investments/issues/28 )
class IBKR:
    BondPricipal = 1000
    CancelledFlag = 'Ca'
    TaxNotePattern = "^(.*) - (..) TAX$"
    MergerPattern = "^(?P<symbol_old>\w+)\((?P<isin_old>\w+)\) +MERGED\(\w+\) +WITH +(?P<isin_new>\w+) +(?P<X>\d+) +FOR +(?P<Y>\d+) +\((?P<symbol>\w+), (?P<name>.*), (?P<id>\w+)\)$"
    SpinOffPattern = "^(?P<symbol_old>\w+)\((?P<isin_old>\w+)\) +SPINOFF +(?P<X>\d+) +FOR +(?P<Y>\d+) +\((?P<symbol>\w+), (?P<name>.*), (?P<id>\w+)\)$"
    SymbolChangePattern = "^(?P<symbol_old>\w+)\((?P<isin_old>\w+)\) +CUSIP\/ISIN CHANGE TO +\((?P<isin_new>\w+)\) +\((?P<symbol>\w+), (?P<name>.*), (?P<id>\w+)\)$"
    SplitPattern = "^(?P<symbol_old>\w+)\((?P<isin_old>\w+)\) +SPLIT +(?P<X>\d+) +FOR +(?P<Y>\d+) +\((?P<symbol>\w+), (?P<name>.*), (?P<id>\w+)\)$"

    AssetType = {
        'CASH': PredefinedAsset.Money,
        'STK': PredefinedAsset.Stock,
        'BOND': PredefinedAsset.Bond,
        'OPT': PredefinedAsset.Derivative,
        'FUT': PredefinedAsset.Derivative
    }

    CorpAction = {
        'TC': CorporateAction.Merger,
        'SO': CorporateAction.SpinOff,
        'IC': CorporateAction.SymbolChange,
        'HI': CorporateAction.StockDividend,
        'FS': CorporateAction.Split,
        'RS': CorporateAction.Split
    }

    def __init__(self, parent, filename):
        self._parent = parent
        self._filename = filename
        self.last_selected_account = None

    @staticmethod
    def flString(data, name, default_value, _caller):
        if name not in data.attrib:
            return default_value
        return data.attrib[name]

    @staticmethod
    def flNumber(data, name, default_value, _caller):
        if name not in data.attrib:
            return default_value
        try:
            value = float(data.attrib[name])
        except ValueError:
            return None
        return value

    @staticmethod
    def flTimestamp(data, name, default_value, _caller):
        if name not in data.attrib:
            return default_value
        time_str = data.attrib[name]
        try:
            if len(time_str) == 15:  # YYYYMMDD;HHMMSS
                return int(datetime.strptime(time_str, "%Y%m%d;%H%M%S").replace(tzinfo=timezone.utc).timestamp())
            elif len(time_str) == 8:  # YYYYMMDD
                return int(datetime.strptime(time_str, "%Y%m%d").replace(tzinfo=timezone.utc).timestamp())
            else:
                return default_value
        except ValueError:
            logging.error(g_tr('IBKR', "Unsupported date/time format: ") + f"{data.attrib[name]}")
            return None

    @staticmethod
    def flAssetType(data, name, default_value, _caller):
        if name not in data.attrib:
            return default_value
        try:
            return IBKR.AssetType[data.attrib[name]]
        except KeyError:
            if default_value is not None:
                return default_value
            else:
                logging.error(g_tr('IBKR', "Asset type isn't supported: ") + f"{data.attrib[name]}")
                return None

    @staticmethod
    def flCorpActionType(data, name, default_value, _caller):
        if name not in data.attrib:
            return default_value
        try:
            return IBKR.CorpAction[data.attrib[name]]
        except KeyError:
            if default_value is not None:
                return default_value
            else:
                logging.error(g_tr('IBKR', "Corporate action isn't supported: ") + f"{data.attrib[name]}")
                return None

    @staticmethod
    def flCashOpType(data, name, default_value, _caller):
        operations = {
            'Dividends':                    IBKRCashOp.Dividend,
            'Payment In Lieu Of Dividends': IBKRCashOp.Dividend,
            'Bond Interest Paid':           IBKRCashOp.BondInterest,
            'Bond Interest Received':       IBKRCashOp.BondInterest,
            'Withholding Tax':              IBKRCashOp.TaxWithhold,
            'Deposits/Withdrawals':         IBKRCashOp.DepositWithdrawal,
            'Other Fees':                   IBKRCashOp.Fee,
            'Commission Adjustments':       IBKRCashOp.Fee,
            'Broker Interest Paid':         IBKRCashOp.Fee,
            'Broker Interest Received':     IBKRCashOp.Interest
        }

        if name not in data.attrib:
            return default_value
        try:
            return operations[data.attrib[name]]
        except KeyError:
            if default_value is not None:
                return default_value
            else:
                logging.error(g_tr('IBKR', "Cash transaction isn't supported: ") + f"{data.attrib[name]}")
                return None

    @staticmethod
    def flAccount(data, name, default_value, caller):
        if name not in data.attrib:
            return default_value
        if data.tag == 'Trade' and IBKR.flAssetType(data, 'assetCategory', None, None) == PredefinedAsset.Money:
            if 'symbol' not in data.attrib:
                logging.error(g_tr('IBKR', "Can't get currencies for accounts: ") + f"{data}")
                return None
            if 'ibCommissionCurrency' not in data.attrib:
                logging.error(g_tr('IBKR', "Can't get account currency for fee account: ") + f"{data}")
                return None
            currencies = data.attrib['symbol'].split('.')
            currencies.append(data.attrib['ibCommissionCurrency'])
            accountIds = []
            for currency in currencies:
                account = caller.findAccountID(data.attrib[name], currency)
                if account is None:
                    return None
                accountIds.append(account)
            return accountIds
        if 'currency' not in data.attrib:
            if default_value is None:
                logging.error(g_tr('IBKR', "Can't get account currency for account: ") + f"{data}")
            return default_value
        return caller.findAccountID(data.attrib[name], data.attrib['currency'])

    @staticmethod
    def flAsset(data, name, default_value, caller):
        if name not in data.attrib:
            return default_value
        if data.attrib[name] == '':
            return default_value
        if data.tag == 'Trade' and IBKR.flAssetType(data, 'assetCategory', None, None) == PredefinedAsset.Money:
            currency_asset = default_value
            for currency in data.attrib['symbol'].split('.'):
                currency_asset = caller.findAssetID(currency)
            return currency_asset

        isin = data.attrib['isin'] if 'isin' in data.attrib else ''
        if data.tag == 'CorporateAction' and data.attrib[name].endswith('.OLD'):
            return caller.findAssetID(data.attrib[name][:-len('.OLD')], isin=isin)
        return caller.findAssetID(data.attrib[name], isin=isin)

    def load(self):
        section_loaders = {
            'SecuritiesInfo': self.loadIBSecurities,  # Order of load is important - SecuritiesInfo is first
            'Trades': self.loadIBTrades,
            'OptionEAE': self.loadIBOptions,
            'CorporateActions': self.loadIBCorporateActions,
            'CashTransactions': self.loadIBCashTransactions,
            'TransactionTaxes': self.loadIBTaxes
        }
        try:
            xml_root = etree.parse(self._filename)
            for FlexStatements in xml_root.getroot():
                for statement in FlexStatements:
                    attr = statement.attrib
                    report_start = int(
                        datetime.strptime(attr['fromDate'], "%Y%m%d").replace(tzinfo=timezone.utc).timestamp())
                    if not self._parent.checkStatementPeriod(attr['accountId'], report_start):
                        return False
                    logging.info(g_tr('StatementLoader', "Load IB Flex-statement for account ") +
                                 f"{attr['accountId']}: {attr['fromDate']} - {attr['toDate']}")
                    for section in section_loaders:
                        section_elements = statement.xpath(section)  # Actually should be list of 0 or 1 element
                        if section_elements:
                            section_data = self.getIBdata(section_elements[0])
                            if section_data is None:
                                return False
                            section_loaders[section](section_data)
        except Exception as e:
            logging.error(g_tr('StatementLoader', "Failed to parse Interactive Brokers flex-report") + f": {e}")
            return False
        logging.info(g_tr('StatementLoader', "IB Flex-statement loaded successfully"))
        return True

    def getIBdata(self, section):
        section_descriptions = {
            'SecuritiesInfo': {'tag': 'SecurityInfo',
                               'level': '',
                               'values': [('symbol', IBKR.flString, None),
                                          ('assetCategory', IBKR.flAssetType, None),
                                          ('subCategory', IBKR.flString, ''),
                                          ('description', IBKR.flString, None),
                                          ('isin', IBKR.flString, '')]},
            'Trades': {'tag': 'Trade',
                       'level': 'EXECUTION',
                       'values': [('assetCategory', IBKR.flAssetType, None),
                                  ('symbol', IBKR.flAsset, None),
                                  ('accountId', IBKR.flAccount, None),
                                  ('dateTime', IBKR.flTimestamp, None),
                                  ('settleDateTarget', IBKR.flTimestamp, 0),
                                  ('tradePrice', IBKR.flNumber, None),
                                  ('quantity', IBKR.flNumber, None),
                                  ('proceeds', IBKR.flNumber, None),
                                  ('multiplier', IBKR.flNumber, None),
                                  ('ibCommission', IBKR.flNumber, None),
                                  ('tradeID', IBKR.flString, ''),
                                  ('exchange', IBKR.flString, ''),
                                  ('notes', IBKR.flString, '')]},
            'OptionEAE': {'tag': 'OptionEAE',
                          'level': '',
                          'values': [('transactionType', IBKR.flString, None),
                                     ('symbol', IBKR.flAsset, None),
                                     ('accountId', IBKR.flAccount, None),
                                     ('date', IBKR.flTimestamp, None),
                                     ('tradePrice', IBKR.flNumber, None),
                                     ('quantity', IBKR.flNumber, None),
                                     ('multiplier', IBKR.flNumber, None),
                                     ('commisionsAndTax', IBKR.flNumber, None),
                                     ('tradeID', IBKR.flString, ''),
                                     ('notes', IBKR.flString, '')]},
            'CorporateActions': {'tag': 'CorporateAction',
                                 'level': 'DETAIL',
                                 'values': [('type', IBKR.flCorpActionType, None),
                                            ('accountId', IBKR.flAccount, None),
                                            ('symbol', IBKR.flAsset, None),
                                            ('isin', IBKR.flString, ''),
                                            ('listingExchange', IBKR.flString, ''),
                                            ('assetCategory', IBKR.flAssetType, None),
                                            ('dateTime', IBKR.flTimestamp, None),
                                            ('transactionID', IBKR.flString, ''),
                                            ('description', IBKR.flString, None),
                                            ('quantity', IBKR.flNumber, None),
                                            ('code', IBKR.flString, '')]},
            'CashTransactions': {'tag': 'CashTransaction',
                                 'level': 'DETAIL',
                                 'values': [('type', IBKR.flCashOpType, None),
                                            ('accountId', IBKR.flAccount, None),
                                            ('currency', IBKR.flString, ''),
                                            ('symbol', IBKR.flAsset, 0),
                                            ('dateTime', IBKR.flTimestamp, None),
                                            ('amount', IBKR.flNumber, None),
                                            ('tradeID', IBKR.flString, ''),
                                            ('description', IBKR.flString, None)]},
            'TransactionTaxes': {'tag': 'TransactionTax',
                                 'level': '',
                                 'values': [('accountId', IBKR.flAccount, None),
                                            ('symbol', IBKR.flString, ''),
                                            ('date', IBKR.flTimestamp, None),
                                            ('taxAmount', IBKR.flNumber, None),
                                            ('description', IBKR.flString, None),
                                            ('taxDescription', IBKR.flString, None)]}
        }

        try:
            tag = section_descriptions[section.tag]['tag']
        except KeyError:
            return []  # This section isn't used for import

        data = []
        for sample in section.xpath(tag):
            tag_dictionary = {}
            if section_descriptions[section.tag]['level']:  # Skip extra lines (SUMMARY, etc)
                if IBKR.flString(sample, 'levelOfDetail', '', self) != section_descriptions[section.tag]['level']:
                    continue
            for attr_name, attr_loader, attr_default in section_descriptions[section.tag]['values']:
                attr_value = attr_loader(sample, attr_name, attr_default, self._parent)
                if attr_value is None:
                    logging.error(
                        g_tr('StatementLoader', "Failed to load attribute: ") + f"{attr_name} / {sample.attrib}")
                    return None
                tag_dictionary[attr_name] = attr_value
            data.append(tag_dictionary)
        return data

    def loadIBSecurities(self, assets):
        cnt = 0
        for asset in assets:
            # IB may use '.OLD' suffix if asset is being replaced
            symbol = asset['symbol'][:-len('.OLD')] if asset['symbol'].endswith('.OLD') else asset['symbol']
            asset_id = self._parent.findAssetID(symbol, asset['isin'], dialog_new=False)
            if asset_id is not None:
                continue
            asset_type = PredefinedAsset.ETF if asset['subCategory'] == "ETF" else asset['assetCategory']
            JalDB().add_asset(symbol, asset['description'], asset_type, asset['isin'])
            cnt += 1
        logging.info(g_tr('StatementLoader', "Securities loaded: ") + f"{cnt} ({len(assets)})")

    def loadIBTrades(self, trades):
        ib_trade_loaders = {
            PredefinedAsset.Stock: self.loadIBStockTrade,
            PredefinedAsset.Bond: self.loadIBBondTrade,
            PredefinedAsset.Derivative: self.loadIBStockTrade,
            PredefinedAsset.Money: self.loadIBCurrencyTrade
        }

        cnt = 0
        for trade in trades:
            try:
                cnt += ib_trade_loaders[trade['assetCategory']](trade)
            except KeyError:
                logging.error(g_tr('StatementLoader', "Asset type isn't supported for trade: ") + f"{trade})")
        logging.info(g_tr('StatementLoader', "Trades loaded: ") + f"{cnt} ({len(trades)})")

    def loadIBCorporateActions(self, actions):
        cnt = 0
        if any(action['code'] == IBKR.CancelledFlag for action in actions):
            actions = [action for action in actions if action['code'] != IBKR.CancelledFlag]
            logging.warning(g_tr('StatementLoader',
                                 "Statement contains cancelled corporate actions. They were skipped."))
        if any(action['assetCategory'] != PredefinedAsset.Stock for action in actions):
            actions = [action for action in actions if action['assetCategory'] == PredefinedAsset.Stock]
            logging.warning(g_tr('StatementLoader',
                                 "Corporate actions are supported for stocks only. "
                                 "Actions for other asset types were skipped"))

        # If stocks were bought/sold on a corporate action day IBKR may put several records for one corporate
        # action. So first step is to aggregate quantity.
        key_func = lambda x: (x['accountId'], x['symbol'], x['type'], x['description'], x['isin'], x['dateTime'])
        actions_sorted = sorted(actions, key=key_func)
        actions_aggregated = []
        for k, group in groupby(actions_sorted, key=key_func):
            group_list = list(group)
            part = group_list[0]  # Take fist of several actions as a basis
            part['quantity'] = sum(action['quantity'] for action in group_list)  # and update quantity in it
            part['jal_processed'] = False   # This flag will be used to mark already processed records
            actions_aggregated.append(part)
            cnt += len(group_list) - 1
        # Now split in 2 parts: A for new stocks deposit, B for old stocks withdrawal
        parts_a = [action for action in actions_aggregated if action['quantity'] >= 0]
        parts_b = [action for action in actions_aggregated if action['quantity'] < 0]

        # Process sequentially '+' and '-', 'jal_processed' will set True when '+' has pair record in '-'
        for action in parts_a+parts_b:
            if action['jal_processed']:
                continue
            if action['type'] == CorporateAction.Merger:
                parts = re.match(IBKR.MergerPattern, action['description'], re.IGNORECASE)
                if parts is None:
                    logging.error(g_tr('StatementLoader', "Can't parse Merger description ") + f"'{action}'")
                    continue
                merger_a = parts.groupdict()
                if len(merger_a) != 8:
                    logging.error(g_tr('StatementLoader', "Merger description miss some data ") + f"'{action}'")
                    continue
                description_b = action['description'][:parts.span(6)[0]] + merger_a['symbol_old'] + ", "
                asset_b = self._parent.findAssetID(merger_a['symbol_old'], merger_a['isin_old'])

                paired_record = list(filter(
                    lambda pair: pair['symbol'] == asset_b
                                 and pair['description'].startswith(description_b)
                                 and pair['type'] == action['type']
                                 and pair['dateTime'] == action['dateTime'], parts_b))
                if len(paired_record) != 1:
                    logging.error(g_tr('StatementLoader', "Can't find paired record for ") + f"{action}")
                    continue
                JalDB().add_corporate_action(action['accountId'], CorporateAction.Merger, action['dateTime'],
                                             action['transactionID'], paired_record[0]['symbol'],
                                             -paired_record[0]['quantity'], action['symbol'], action['quantity'], 1,
                                             action['description'])
                paired_record[0]['jal_processed'] = True
                cnt += 2
            elif action['type'] == CorporateAction.SpinOff:
                parts = re.match(IBKR.SpinOffPattern, action['description'], re.IGNORECASE)
                if parts is None:
                    logging.error(g_tr('StatementLoader', "Can't parse Spin-off description ") + f"'{action}'")
                    continue
                spinoff = parts.groupdict()
                if len(spinoff) != 7:
                    logging.error(g_tr('StatementLoader', "Spin-off description miss some data ") + f"'{action}'")
                    continue
                asset_id_old = self._parent.findAssetID(spinoff['symbol_old'], spinoff['isin_old'])
                qty_old = int(spinoff['Y']) * action['quantity'] / int(spinoff['X'])
                JalDB().add_corporate_action(action['accountId'], CorporateAction.SpinOff, action['dateTime'],
                                             action['transactionID'], asset_id_old,
                                             qty_old, action['symbol'], action['quantity'], 0, action['description'])
                cnt += 1
            elif action['type'] == CorporateAction.SymbolChange:
                parts = re.match(IBKR.SymbolChangePattern, action['description'], re.IGNORECASE)
                if parts is None:
                    logging.error(g_tr('StatementLoader', "Can't parse Symbol Change description ") + f"'{action}'")
                    continue
                isin_change = parts.groupdict()
                if len(isin_change) != 6:
                    logging.error(g_tr('StatementLoader', "Spin-off description miss some data ") + f"'{action}'")
                    continue
                description_b = action['description'][:parts.span(4)[0]] + isin_change['symbol_old'] + ".OLD, "
                asset_b = self._parent.findAssetID(isin_change['symbol_old'], isin_change['isin_old'])

                paired_record = list(filter(
                    lambda pair: pair['symbol'] == asset_b
                                 and pair['description'].startswith(description_b)
                                 and pair['type'] == action['type']
                                 and pair['dateTime'] == action['dateTime'], parts_b))
                if len(paired_record) != 1:
                    logging.error(g_tr('StatementLoader', "Can't find paired record for: ") + f"{action}")
                    continue
                JalDB().add_corporate_action(action['accountId'], CorporateAction.SymbolChange, action['dateTime'],
                                             action['transactionID'], paired_record[0]['symbol'],
                                             -paired_record[0]['quantity'], action['symbol'], action['quantity'], 1,
                                             action['description'])
                paired_record[0]['jal_processed'] = True
                cnt += 2
            elif action['type'] == CorporateAction.StockDividend:
                JalDB().add_corporate_action(action['accountId'], CorporateAction.StockDividend, action['dateTime'],
                                             action['transactionID'], action['symbol'], -1,
                                             action['symbol'], action['quantity'], 0, action['description'])
                cnt += 1
            elif action['type'] == CorporateAction.Split:
                parts = re.match(IBKR.SplitPattern, action['description'], re.IGNORECASE)
                if parts is None:
                    logging.error(g_tr('StatementLoader', "Can't parse Split description ") + f"'{action}'")
                    continue
                split = parts.groupdict()
                if len(split) != 7:
                    logging.error(g_tr('StatementLoader', "Split description miss some data ") + f"'{action}'")
                    continue

                if parts['isin_old'] == parts['id']:  # Simple split without ISIN change
                    qty_delta = action['quantity']
                    if qty_delta >= 0:  # Forward split (X>Y)
                        qty_old = qty_delta / (int(split['X']) - int(split['Y']))
                        qty_new = int(split['X']) * qty_delta / (int(split['X']) - int(split['Y']))
                    else:               # Reverse split (X<Y)
                        qty_new = qty_delta / (int(split['X']) - int(split['Y']))
                        qty_old = int(split['Y']) * qty_delta / (int(split['X']) - int(split['Y']))
                    JalDB().add_corporate_action(action['accountId'], CorporateAction.Split, action['dateTime'],
                                                 action['transactionID'], action['symbol'],
                                                 qty_old, action['symbol'], qty_new, 1, action['description'])
                    cnt += 1
                else:  # Split together with ISIN change and there should be 2nd record available
                    description_b = action['description'][:parts.span(5)[0]] + split['symbol_old'] + ".OLD, "
                    asset_b = self._parent.findAssetID(split['symbol_old'], split['isin_old'])

                    paired_record = list(filter(
                        lambda pair: pair['symbol'] == asset_b
                                     and pair['description'].startswith(description_b)
                                     and pair['type'] == action['type']
                                     and pair['dateTime'] == action['dateTime'], parts_b))
                    if len(paired_record) != 1:
                        logging.error(g_tr('StatementLoader', "Can't find paired record for: ") + f"{action}")
                        continue
                    JalDB().add_corporate_action(action['accountId'], CorporateAction.Split, action['dateTime'],
                                                 action['transactionID'], paired_record[0]['symbol'],
                                                 -paired_record[0]['quantity'], action['symbol'], action['quantity'], 1,
                                                 action['description'])
                    paired_record[0]['jal_processed'] = True
                    cnt += 2
            else:
                logging.error(g_tr('StatementLoader', "Corporate action type is not supported: ")
                              + f"{action['type']}")
                continue
        logging.info(g_tr('StatementLoader', "Corporate actions loaded: ") + f"{cnt} ({len(actions)})")

    def loadIBTaxes(self, taxes):
        cnt = 0
        for tax in taxes:
            note = f"{tax['symbol']} ({tax['description']}) - {tax['taxDescription']}"
            id = readSQL("SELECT id FROM all_operations WHERE type = :type "
                         "AND timestamp=:timestamp AND account_id=:account_id AND amount=:amount",
                         [(":timestamp", tax['date']), (":type", TransactionType.Action),
                          (":account_id", tax['accountId']), (":amount", tax['taxAmount'])])
            if id:
                logging.warning(g_tr('StatementLoader', "Tax transaction already exists ") + f"{tax}")
                continue
            JalDB().add_cash_transaction(tax['accountId'], self._parent.getAccountBank(tax['accountId']), tax['date'],
                                         tax['taxAmount'], PredefinedCategory.Taxes, note)
            cnt += 1
        logging.info(g_tr('StatementLoader', "Taxes loaded: ") + f"{cnt} ({len(taxes)})")

    def loadIBOptions(self, options):
        transaction_desctiption = {
            "Assignment": g_tr('StatementLoader', "Option assignment"),
            "Exercise": g_tr('StatementLoader', "Option exercise"),
            "Expiration": g_tr('StatementLoader', "Option expiration"),
            "Buy": g_tr('StatementLoader', "Option assignment/exercise"),
            "Sell": g_tr('StatementLoader', "Option assignment/exercise"),
        }
        cnt = 0
        for option in options:
            try:
                description = transaction_desctiption[option['transactionType']]
                if description:
                    _ = executeSQL("UPDATE trades SET note=:description WHERE "
                                   "account_id=:account_id AND asset_id=:asset_id AND number=:trade_id",
                                   [(":description", description), (":account_id", option['accountId']),
                                    (":asset_id", option['symbol']), (":trade_id", option['tradeID'])], commit=True)
                    cnt += 1
            except KeyError:
                logging.error(
                    g_tr('StatementLoader', "Option E&A&E action isn't implemented: ") + f"{option['transactionType']}")
        logging.info(g_tr('StatementLoader', "Options E&A&E loaded: ") + f"{cnt} ({len(options)})")

    def loadIBCashTransactions(self, cash):
        cnt = 0

        dividends = list(filter(lambda tr: tr['type'] == IBKRCashOp.Dividend, cash))
        for dividend in dividends:
            cnt += self.loadIBDividend(dividend)

        bond_interests = list(filter(lambda tr: tr['type'] == IBKRCashOp.BondInterest, cash))
        for bond_interest in bond_interests:
            cnt += self.loadIBBondInterest(bond_interest)

        taxes = list(filter(lambda tr: tr['type'] == IBKRCashOp.TaxWithhold, cash))
        for tax in taxes:
            cnt += self.loadIBWithholdingTax(tax)

        transfers = list(filter(lambda tr: tr['type'] == IBKRCashOp.DepositWithdrawal, cash))
        for transfer in transfers:
            cnt += self.loadIBDepositWithdraw(transfer)

        fees = list(filter(lambda tr: tr['type'] == IBKRCashOp.Fee, cash))
        for fee in fees:
            cnt += self.loadIBFee(fee)

        interests = list(filter(lambda tr: tr['type'] == IBKRCashOp.Interest, cash))
        for interest in interests:
            cnt += self.loadIBInterest(interest)

        logging.info(g_tr('StatementLoader', "Cash transactions loaded: ") + f"{cnt} ({len(cash)})")

    def loadIBStockTrade(self, trade):
        qty = trade['quantity'] * trade['multiplier']
        if trade['settleDateTarget'] == 0:
            trade['settleDateTarget'] = trade['dateTime']
        if trade['notes'] == IBKR.CancelledFlag:
            JalDB().del_trade(trade['accountId'], trade['symbol'], trade['dateTime'], trade['settleDateTarget'],
                              trade['tradeID'], qty, trade['tradePrice'], trade['ibCommission'])
        else:
            JalDB().add_trade(trade['accountId'], trade['symbol'], trade['dateTime'], trade['settleDateTarget'],
                              trade['tradeID'], qty, trade['tradePrice'], trade['ibCommission'])
        return 1

    def loadIBBondTrade(self, trade):
        qty = trade['quantity'] / IBKR.BondPricipal
        price = trade['tradePrice'] * IBKR.BondPricipal / 100.0   # Bonds are priced in percents of principal
        if trade['settleDateTarget'] == 0:
            trade['settleDateTarget'] = trade['dateTime']
        if trade['notes'] == IBKR.CancelledFlag:
            JalDB().del_trade(trade['accountId'], trade['symbol'], trade['dateTime'], trade['settleDateTarget'],
                              trade['tradeID'], qty, price, trade['ibCommission'])
        else:
            JalDB().add_trade(trade['accountId'], trade['symbol'], trade['dateTime'], trade['settleDateTarget'],
                              trade['tradeID'], qty, price, trade['ibCommission'])
        return 1

    def loadIBCurrencyTrade(self, trade):
        if trade['quantity'] > 0:
            from_idx = 1
            to_idx = 0
            to_amount = trade['quantity']  # positive value
            from_amount = -trade['proceeds']  # we use positive value in DB while it is negative in report
        elif trade['quantity'] < 0:
            from_idx = 0
            to_idx = 1
            from_amount = -trade['quantity']  # we use positive value in DB while it is negative in report
            to_amount = trade['proceeds']  # positive value
        else:
            logging.error(g_tr('StatementLoader', "Zero quantity in cash trade: ") + f"{trade}")
            return 0
        fee_idx = 2
        fee_amount = -trade['ibCommission']  # Fee is negative in IB report but we store positive value in database
        JalDB().add_transfer(trade['dateTime'], trade['accountId'][from_idx], from_amount,
                             trade['accountId'][to_idx], to_amount, trade['accountId'][fee_idx],
                             fee_amount, trade['exchange'])
        return 1

    def loadIBDividend(self, dividend):
        JalDB().add_dividend(DividendSubtype.Dividend, dividend['dateTime'], dividend['accountId'], dividend['symbol'],
                             dividend['amount'], dividend['description'])
        return 1

    def loadIBBondInterest(self, interest):
        JalDB().add_dividend(DividendSubtype.BondInterest, interest['dateTime'], interest['accountId'],
                             interest['symbol'],
                             interest['amount'], interest['description'], interest['tradeID'])
        return 1

    def loadIBWithholdingTax(self, tax):
        self.addWithholdingTax(tax['dateTime'], tax['accountId'], tax['symbol'], -tax['amount'], tax['description'])
        return 1

    def loadIBFee(self, fee):
        JalDB().add_cash_transaction(fee['accountId'], self._parent.getAccountBank(fee['accountId']), fee['dateTime'],
                                     fee['amount'], PredefinedCategory.Fees, fee['description'])
        return 1

    def loadIBInterest(self, interest):
        JalDB().add_cash_transaction(interest['accountId'], self._parent.getAccountBank(interest['accountId']),
                                     interest['dateTime'], interest['amount'], PredefinedCategory.Interest,
                                     interest['description'])
        return 1

    # noinspection PyMethodMayBeStatic
    def loadIBDepositWithdraw(self, cash):
        if cash['amount'] >= 0:  # Deposit
            text = g_tr('StatementLoader', "Deposit of ") + f"{cash['amount']:.2f} {cash['currency']} " + \
                   f"@{datetime.utcfromtimestamp(cash['dateTime']).strftime('%d.%m.%Y')}\n" + \
                   g_tr('StatementLoader', "Select account to withdraw from:")
        else:  # Withdrawal
            text = g_tr('StatementLoader', "Withdrawal of ") + f"{-cash['amount']:.2f} {cash['currency']} " + \
                   f"@{datetime.utcfromtimestamp(cash['dateTime']).strftime('%d.%m.%Y')}\n" + \
                   g_tr('StatementLoader', "Select account to deposit to:")
        pair_account = self._parent.selectAccount(text, cash['accountId'], self.last_selected_account)
        if pair_account == 0:
            return 0
        self.last_selected_account = pair_account
        if cash['amount'] >= 0:
            JalDB().add_transfer(cash['dateTime'], pair_account, cash['amount'],
                                 cash['accountId'], cash['amount'], 0, 0, cash['description'])
        else:
            JalDB().add_transfer(cash['dateTime'], cash['accountId'], -cash['amount'],
                                 pair_account, -cash['amount'], 0, 0, cash['description'])
        return 1

    def addWithholdingTax(self, timestamp, account_id, asset_id, amount, note):
        parts = re.match(IBKR.TaxNotePattern, note)
        if not parts:
            logging.warning(g_tr('StatementLoader', "*** MANUAL ENTRY REQUIRED ***"))
            logging.warning(g_tr('StatementLoader', "Unhandled tax pattern found: ") + f"{note}")
            return
        dividend_note = parts.group(1) + '%'
        country_code = parts.group(2).lower()
        country_id = get_country_by_code(country_code)
        update_asset_country(asset_id, country_id)
        dividend_id = self.findDividend4Tax(timestamp, account_id, asset_id, dividend_note)
        if dividend_id is None:
            logging.warning(g_tr('StatementLoader', "Dividend not found for withholding tax: ") + f"{note}")
            return
        old_tax = readSQL("SELECT tax FROM dividends WHERE id=:id", [(":id", dividend_id)])
        _ = executeSQL("UPDATE dividends SET tax=:tax WHERE id=:dividend_id",
                       [(":dividend_id", dividend_id), (":tax", old_tax + amount)], commit=True)

    def findDividend4Tax(self, timestamp, account_id, asset_id, note):
        # Check strong match
        id = readSQL("SELECT id FROM dividends WHERE type=:div AND timestamp=:timestamp "
                     "AND account_id=:account_id AND asset_id=:asset_id AND note LIKE :dividend_description",
                     [(":div", DividendSubtype.Dividend), (":timestamp", timestamp), (":account_id", account_id),
                      (":asset_id", asset_id), (":dividend_description", note)])
        if id is not None:
            return id
        # Check weak match
        range_start = ManipulateDate.startOfPreviousYear(day=datetime.utcfromtimestamp(timestamp))
        count = readSQL("SELECT COUNT(id) FROM dividends WHERE type=:div AND timestamp>=:start_range "
                        "AND account_id=:account_id AND asset_id=:asset_id AND note LIKE :dividend_description",
                        [(":div", DividendSubtype.Dividend), (":start_range", range_start), (":account_id", account_id),
                         (":asset_id", asset_id), (":dividend_description", note)])
        if count > 1:
            logging.warning(g_tr('StatementLoader', "Multiple dividends match withholding tax"))
            return None
        id = readSQL("SELECT id FROM dividends WHERE type=:div AND timestamp>=:start_range "
                     "AND account_id=:account_id AND asset_id=:asset_id AND note LIKE :dividend_description",
                     [(":div", DividendSubtype.Dividend), (":start_range", range_start), (":account_id", account_id),
                      (":asset_id", asset_id), (":dividend_description", note)])
        return id
