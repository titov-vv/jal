import logging
import math
import re
from datetime import datetime, timezone
from itertools import groupby

import pandas
from lxml import etree
from PySide2.QtCore import QObject, Signal, Slot
from PySide2.QtSql import QSqlTableModel
from PySide2.QtWidgets import QDialog, QFileDialog, QMessageBox
from jal.constants import Setup, TransactionType, PredefinedAsset, PredefinedCategory, CorporateAction, DividendSubtype
from jal.db.helpers import executeSQL, readSQL, get_country_by_code, account_last_date, update_asset_country
from jal.ui_custom.helpers import g_tr, ManipulateDate
from jal.ui.ui_add_asset_dlg import Ui_AddAssetDialog
from jal.ui.ui_select_account_dlg import Ui_SelectAccountDlg


# -----------------------------------------------------------------------------------------------------------------------
class ReportType:
    IBKR = 'IBKR flex-query (*.xml)'
    Quik = 'Quik HTML-report (*.htm)'


class IBKRCashOp:
    Dividend = 0
    TaxWithhold = 1
    DepositWithdrawal = 2
    Fee = 3
    Interest = 4
    BondInterest = 5


# -----------------------------------------------------------------------------------------------------------------------
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
            logging.error(g_tr('StatementLoader', "Unsupported date/time format: ") + f"{data.attrib[name]}")
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
                logging.error(g_tr('StatementLoader', "Asset type isn't supported: ") + f"{data.attrib[name]}")
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
                logging.error(g_tr('StatementLoader', "Corporate action isn't supported: ") + f"{data.attrib[name]}")
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
                logging.error(g_tr('StatementLoader', "Cash transaction isn't supported: ") + f"{data.attrib[name]}")
                return None

    @staticmethod
    def flAccount(data, name, default_value, caller):
        if name not in data.attrib:
            return default_value
        if data.tag == 'Trade' and IBKR.flAssetType(data, 'assetCategory', None, None) == PredefinedAsset.Money:
            if 'symbol' not in data.attrib:
                logging.error(g_tr('StatementLoader', "Can't get currencies for accounts: ") + f"{data}")
                return None
            if 'ibCommissionCurrency' not in data.attrib:
                logging.error(g_tr('StatementLoader', "Can't get account currency for fee account: ") + f"{data}")
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
                logging.error(g_tr('StatementLoader', "Can't get account currency for account: ") + f"{data}")
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


# -----------------------------------------------------------------------------------------------------------------------
class Quik:
    ClientPattern = "^Код клиента: (.*)$"
    DateTime = 'Дата и время заключения сделки'
    TradeNumber = 'Номер сделки'
    Symbol = 'Код инструмента'
    Name = 'Краткое наименование инструмента'
    Type = 'Направление'
    Qty = 'Кол-во'
    Price = 'Цена'
    Amount = 'Объём'
    Coupon = 'НКД'
    SettleDate = 'Дата расчётов'
    Buy = 'Купля'
    Sell = 'Продажа'
    Fee = 'Комиссия Брокера'
    FeeEx = 'Суммарная комиссия ТС'    # This line is used in KIT Broker reports
    FeeEx1 = 'Комиссия за ИТС'         # Below 3 lines are used in Uralsib Borker reports
    FeeEx2 = 'Комиссия за организацию торговли'
    FeeEx3 = 'Клиринговая комиссия'
    Total = 'ИТОГО'


# -----------------------------------------------------------------------------------------------------------------------
# Strip white spaces from numbers imported form Quik html-report
def convert_amount(val):
    val = val.replace(' ', '')
    try:
        res = float(val)
    except ValueError:
        res = 0
    return res


def addNewAsset(db, symbol, name, asset_type, isin, data_source=-1):
    if symbol.endswith('.OLD'):
        symbol = symbol[:-len('.OLD')]
    _ = executeSQL(db, "INSERT INTO assets(name, type_id, full_name, isin, src_id) "
                       "VALUES(:symbol, :type, :full_name, :isin, :data_src)",
                   [(":symbol", symbol), (":type", asset_type), (":full_name", name),
                    (":isin", isin), (":data_src", data_source)])
    db.commit()
    asset_id = readSQL(db, "SELECT id FROM assets WHERE name=:symbol", [(":symbol", symbol)])
    if asset_id is None:
        logging.error(g_tr('StatementLoader', "Failed to add new asset: ") + f"{symbol}")
    return asset_id


# -----------------------------------------------------------------------------------------------------------------------
class AddAssetDialog(QDialog, Ui_AddAssetDialog):
    def __init__(self, parent, db, symbol):
        QDialog.__init__(self)
        self.setupUi(self)
        self.db = db
        self.asset_id = None

        self.SymbolEdit.setText(symbol)

        self.type_model = QSqlTableModel(db=db)
        self.type_model.setTable('asset_types')
        self.type_model.select()
        self.TypeCombo.setModel(self.type_model)
        self.TypeCombo.setModelColumn(1)

        self.data_src_model = QSqlTableModel(db=db)
        self.data_src_model.setTable('data_sources')
        self.data_src_model.select()
        self.DataSrcCombo.setModel(self.data_src_model)
        self.DataSrcCombo.setModelColumn(1)

        # center dialog with respect to parent window
        x = parent.x() + parent.width() / 2 - self.width() / 2
        y = parent.y() + parent.height() / 2 - self.height() / 2
        self.setGeometry(x, y, self.width(), self.height())

    def accept(self):
        self.asset_id = addNewAsset(self.db, self.SymbolEdit.text(), self.NameEdit.text(),
                                    self.type_model.record(self.TypeCombo.currentIndex()).value("id"),
                                    self.isinEdit.text(),
                                    self.data_src_model.record(self.DataSrcCombo.currentIndex()).value("id"))
        super().accept()


# -----------------------------------------------------------------------------------------------------------------------
class SelectAccountDialog(QDialog, Ui_SelectAccountDlg):
    def __init__(self, parent, db, description, current_account, recent_account=None):
        QDialog.__init__(self)
        self.setupUi(self)
        self.db = db
        self.account_id = recent_account
        self.current_account = current_account

        self.DescriptionLbl.setText(description)
        self.AccountWidget.init_db(db)
        if self.account_id:
            self.AccountWidget.selected_id = self.account_id

        # center dialog with respect to parent window
        x = parent.x() + parent.width() / 2 - self.width() / 2
        y = parent.y() + parent.height() / 2 - self.height() / 2
        self.setGeometry(x, y, self.width(), self.height())

    @Slot()
    def closeEvent(self, event):
        self.account_id = self.AccountWidget.selected_id
        if self.AccountWidget.selected_id == 0:
            QMessageBox().warning(None, g_tr('ReferenceDataDialog', "No selection"),
                                  g_tr('ReferenceDataDialog', "Invalid account selected"),
                                  QMessageBox.Ok)
            event.ignore()
            return

        if self.AccountWidget.selected_id == self.current_account:
            QMessageBox().warning(None, g_tr('ReferenceDataDialog', "No selection"),
                                  g_tr('ReferenceDataDialog', "Please select different account"),
                                  QMessageBox.Ok)
            event.ignore()
            return

        self.setResult(QDialog.Accepted)
        event.accept()


# -----------------------------------------------------------------------------------------------------------------------
class StatementLoader(QObject):
    load_completed = Signal()
    load_failed = Signal()

    def __init__(self, parent, db):
        super().__init__()
        self.parent = parent
        self.db = db
        self.loaders = {
            ReportType.IBKR: self.loadIBFlex,
            ReportType.Quik: self.loadQuikHtml
        }
        self.currentIBstatement = None
        self.last_selected_account = None

    # Displays file choose dialog and loads corresponding report if user have chosen a file
    def loadReport(self):
        report_file, active_filter = \
            QFileDialog.getOpenFileName(None, g_tr('StatementLoader', "Select statement file to import"),
                                        ".", f"{ReportType.IBKR};;{ReportType.Quik}")
        if report_file:
            result = self.loaders[active_filter](report_file)
            if result:
                self.load_completed.emit()
            else:
                self.load_failed.emit()

    # Searches for account_id by account number and optional currency
    # Returns: account_id or None if no account was found
    def findAccountID(self, accountNumber, accountCurrency=''):
        if accountCurrency:
            account_id = readSQL(self.db, "SELECT a.id FROM accounts AS a "
                                          "LEFT JOIN assets AS c ON c.id=a.currency_id "
                                          "WHERE a.number=:account_number AND c.name=:currency_name",
                                 [(":account_number", accountNumber), (":currency_name", accountCurrency)])
        else:
            account_id = readSQL(self.db, "SELECT a.id FROM accounts AS a "
                                          "LEFT JOIN assets AS c ON c.id=a.currency_id "
                                          "WHERE a.number=:account_number", [(":account_number", accountNumber)])
        if account_id is None:
            logging.error(g_tr('StatementLoader', "Account not found: ") + f"{accountNumber} ({accountCurrency})")
        return account_id

    # Searches for asset_id in database and returns its ID
    # 1. if ISIN is give tries to find by ISIN.
    # 2. If found by ISIN - checks symbol and updates it if function is called with another symbol
    # 3. If not found by ISIN or ISIN is not given - tries to find by symbol only
    # 4. If asset is not found - shows dialog for new asset creation.
    # Returns: asset_id or None if new asset creation failed
    def findAssetID(self, symbol, isin='', dialog_new=True):
        if isin:
            asset_id = readSQL(self.db, "SELECT id FROM assets WHERE isin=:isin", [(":isin", isin)])
            if asset_id is not None:
                db_symbol = readSQL(self.db, "SELECT name FROM assets WHERE id=:asset_id", [(":asset_id", asset_id)])
                if db_symbol != symbol:
                    _ = executeSQL(self.db, "UPDATE assets SET name=:symbol WHERE id=:asset_id",
                                   [(":symbol", symbol), (":asset_id", asset_id)])
                    # Show warning if symbol was changed not due known bankruptcy or new issue pattern
                    if (db_symbol != symbol + 'D') and (db_symbol + 'D' != symbol) \
                            and (db_symbol != symbol + 'Q') and (db_symbol + 'Q' != symbol):
                        logging.warning(
                            g_tr('StatementLoader', "Symbol updated for ISIN ") + f"{isin}: {db_symbol} -> {symbol}")
                return asset_id
        asset_id = readSQL(self.db, "SELECT id FROM assets WHERE name=:symbol", [(":symbol", symbol)])
        if asset_id is not None:
            # Check why symbol was not found by ISIN
            db_isin = readSQL(self.db, "SELECT isin FROM assets WHERE id=:asset_id", [(":asset_id", asset_id)])
            if db_isin == '':  # Update ISIN if it was absent in DB
                _ = executeSQL(self.db, "UPDATE assets SET isin=:isin WHERE id=:asset_id",
                               [(":isin", isin), (":asset_id", asset_id)])
                logging.info(g_tr('StatementLoader', "ISIN updated for ") + f"{symbol}: {isin}")
            else:
                logging.warning(g_tr('StatementLoader', "ISIN mismatch for ") + f"{symbol}: {isin} != {db_isin}")
        elif dialog_new:
            dialog = AddAssetDialog(self.parent, self.db, symbol)
            dialog.exec_()
            asset_id = dialog.asset_id
        return asset_id

    # returns bank id assigned for the account or asks for assignment if field is empty
    def getAccountBank(self, account_id):
        bank_id = readSQL(self.db, "SELECT organization_id FROM accounts WHERE id=:account_id",
                          [(":account_id", account_id)])
        if bank_id != '':
            return bank_id
        bank_id = readSQL(self.db, "SELECT id FROM agents WHERE name='Interactive Brokers'")
        if bank_id is not None:  # FIXME Better to check that every investment accunt has bank assigned at creation
            return bank_id
        query = executeSQL(self.db, "INSERT INTO agents (pid, name) VALUES (0, 'Interactive Brokers')")
        bank_id = query.lastInsertId()
        _ = executeSQL(self.db, "UPDATE accounts SET organization_id=:bank_id WHERE id=:account_id",
                       [(":bank_id", bank_id), (":account_id", account_id)])
        return bank_id

    def loadIBFlex(self, filename):
        section_loaders = {
            'SecuritiesInfo': self.loadIBSecurities,  # Order of load is important - SecuritiesInfo is first
            'Trades': self.loadIBTrades,
            'OptionEAE': self.loadIBOptions,
            'CorporateActions': self.loadIBCorporateActions,
            'CashTransactions': self.loadIBCashTransactions,
            'TransactionTaxes': self.loadIBTaxes
        }
        try:
            xml_root = etree.parse(filename)
            for FlexStatements in xml_root.getroot():
                for statement in FlexStatements:
                    attr = statement.attrib
                    report_start = int(
                        datetime.strptime(attr['fromDate'], "%Y%m%d").replace(tzinfo=timezone.utc).timestamp())
                    if report_start < account_last_date(self.db, attr['accountId']):
                        if QMessageBox().warning(None,
                                                 g_tr('StatementLoader', "Confirmation"),
                                                 g_tr('StatementLoader',
                                                      "Statement period starts before last recorded operation for the account. Continue import?"),
                                                 QMessageBox.Yes, QMessageBox.No) == QMessageBox.No:
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
                attr_value = attr_loader(sample, attr_name, attr_default, self)
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
            asset_id = self.findAssetID(asset['symbol'], asset['isin'], dialog_new=False)
            if asset_id is not None:
                continue
            asset_type = PredefinedAsset.ETF if asset['subCategory'] == "ETF" else asset['assetCategory']
            addNewAsset(self.db, asset['symbol'], asset['description'], asset_type, asset['isin'])
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
            _ = self.getAccountBank(trade['accountId'])  # Checks that bank is present (in order to process fees)
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
                asset_b = self.findAssetID(merger_a['symbol_old'], merger_a['isin_old'])

                paired_record = list(filter(
                    lambda pair: pair['symbol'] == asset_b
                                 and pair['description'].startswith(description_b)
                                 and pair['type'] == action['type']
                                 and pair['dateTime'] == action['dateTime'], parts_b))
                if len(paired_record) != 1:
                    logging.error(g_tr('StatementLoader', "Can't find paired record for ") + f"{action}")
                    continue
                self.createCorpAction(action['accountId'], CorporateAction.Merger, action['dateTime'],
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
                asset_id_old = self.findAssetID(spinoff['symbol_old'], spinoff['isin_old'])
                qty_old = int(spinoff['Y']) * action['quantity'] / int(spinoff['X'])
                self.createCorpAction(action['accountId'], CorporateAction.SpinOff, action['dateTime'],
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
                asset_b = self.findAssetID(isin_change['symbol_old'], isin_change['isin_old'])

                paired_record = list(filter(
                    lambda pair: pair['symbol'] == asset_b
                                 and pair['description'].startswith(description_b)
                                 and pair['type'] == action['type']
                                 and pair['dateTime'] == action['dateTime'], parts_b))
                if len(paired_record) != 1:
                    logging.error(g_tr('StatementLoader', "Can't find paired record for: ") + f"{action}")
                    continue
                self.createCorpAction(action['accountId'], CorporateAction.SymbolChange, action['dateTime'],
                                      action['transactionID'], paired_record[0]['symbol'],
                                      -paired_record[0]['quantity'], action['symbol'], action['quantity'], 1,
                                      action['description'])
                paired_record[0]['jal_processed'] = True
                cnt += 2
            elif action['type'] == CorporateAction.StockDividend:
                self.createCorpAction(action['accountId'], CorporateAction.StockDividend, action['dateTime'],
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
                    self.createCorpAction(action['accountId'], CorporateAction.Split, action['dateTime'],
                                          action['transactionID'], action['symbol'],
                                          qty_old, action['symbol'], qty_new, 1, action['description'])
                    cnt += 1
                else:  # Split together with ISIN change and there should be 2nd record available
                    description_b = action['description'][:parts.span(5)[0]] + split['symbol_old'] + ".OLD, "
                    asset_b = self.findAssetID(split['symbol_old'], split['isin_old'])

                    paired_record = list(filter(
                        lambda pair: pair['symbol'] == asset_b
                                     and pair['description'].startswith(description_b)
                                     and pair['type'] == action['type']
                                     and pair['dateTime'] == action['dateTime'], parts_b))
                    if len(paired_record) != 1:
                        logging.error(g_tr('StatementLoader', "Can't find paired record for: ") + f"{action}")
                        continue
                    self.createCorpAction(action['accountId'], CorporateAction.Split, action['dateTime'],
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
            bank_id = self.getAccountBank(tax['accountId'])
            note = f"{tax['symbol']} ({tax['description']}) - {tax['taxDescription']}"
            id = readSQL(self.db, "SELECT id FROM all_operations WHERE type = :type "
                                  "AND timestamp=:timestamp AND account_id=:account_id AND amount=:amount",
                         [(":timestamp", tax['date']), (":type", TransactionType.Action),
                          (":account_id", tax['accountId']), (":amount", tax['taxAmount'])])
            if id:
                logging.warning(g_tr('StatementLoader', "Tax transaction already exists ") + f"{tax}")
                continue
            query = executeSQL(self.db, "INSERT INTO actions (timestamp, account_id, peer_id) "
                                        "VALUES (:timestamp, :account_id, :bank_id)",
                               [(":timestamp", tax['date']), (":account_id", tax['accountId']), (":bank_id", bank_id)])
            pid = query.lastInsertId()
            _ = executeSQL(self.db, "INSERT INTO action_details (pid, category_id, sum, note) "
                                    "VALUES (:pid, :category_id, :sum, :note)",
                           [(":pid", pid), (":category_id", PredefinedCategory.Taxes),
                            (":sum", tax['taxAmount']), (":note", note)])
            self.db.commit()
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
                    _ = executeSQL(self.db,
                                   "UPDATE trades SET note=:description WHERE "
                                   "account_id=:account_id AND asset_id=:asset_id AND number=:trade_id",
                                   [(":description", description), (":account_id", option['accountId']),
                                    (":asset_id", option['symbol']), (":trade_id", option['tradeID'])])
                    self.db.commit()
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
            self.deleteTrade(trade['accountId'], trade['symbol'], trade['dateTime'], trade['settleDateTarget'],
                             trade['tradeID'], qty, trade['tradePrice'], trade['ibCommission'])
        else:
            self.createTrade(trade['accountId'], trade['symbol'], trade['dateTime'], trade['settleDateTarget'],
                             trade['tradeID'], qty, trade['tradePrice'], trade['ibCommission'])
        return 1

    def loadIBBondTrade(self, trade):
        qty = trade['quantity'] / IBKR.BondPricipal
        price = trade['tradePrice'] * IBKR.BondPricipal / 100.0   # Bonds are priced in percents of principal
        if trade['settleDateTarget'] == 0:
            trade['settleDateTarget'] = trade['dateTime']
        if trade['notes'] == IBKR.CancelledFlag:
            self.deleteTrade(trade['accountId'], trade['symbol'], trade['dateTime'], trade['settleDateTarget'],
                             trade['tradeID'], qty, price, trade['ibCommission'])
        else:
            self.createTrade(trade['accountId'], trade['symbol'], trade['dateTime'], trade['settleDateTarget'],
                             trade['tradeID'], qty, price, trade['ibCommission'])
        return 1

    def createTrade(self, account_id, asset_id, timestamp, settlement, number, qty, price, fee):
        trade_id = readSQL(self.db,
                           "SELECT id FROM trades "
                           "WHERE timestamp=:timestamp AND asset_id = :asset "
                           "AND account_id = :account AND number = :number AND qty = :qty AND price = :price",
                           [(":timestamp", timestamp), (":asset", asset_id), (":account", account_id),
                            (":number", number), (":qty", qty), (":price", price)])
        if trade_id:
            logging.info(g_tr('StatementLoader', "Trade already exists: #") + f"{number}")
            return

        _ = executeSQL(self.db,
                       "INSERT INTO trades (timestamp, settlement, number, account_id, asset_id, qty, price, fee) "
                       "VALUES (:timestamp, :settlement, :number, :account, :asset, :qty, :price, :fee)",
                       [(":timestamp", timestamp), (":settlement", settlement), (":number", number),
                        (":account", account_id), (":asset", asset_id), (":qty", float(qty)),
                        (":price", float(price)), (":fee", -float(fee))])
        self.db.commit()

    def deleteTrade(self, account_id, asset_id, timestamp, _settlement, number, qty, price, _fee):
        _ = executeSQL(self.db, "DELETE FROM trades "
                                "WHERE timestamp=:timestamp AND asset_id=:asset "
                                "AND account_id=:account AND number=:number AND qty=:qty AND price=:price",
                       [(":timestamp", timestamp), (":asset", asset_id), (":account", account_id),
                        (":number", number), (":qty", -qty), (":price", price)])
        self.db.commit()

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
        self.createTransfer(trade['dateTime'], trade['accountId'][from_idx], from_amount,
                            trade['accountId'][to_idx], to_amount, trade['accountId'][fee_idx],
                            fee_amount, trade['exchange'])
        return 1

    def createTransfer(self, timestamp, f_acc_id, f_amount, t_acc_id, t_amount, fee_acc_id, fee, note):
        transfer_id = readSQL(self.db,
                              "SELECT id FROM transfers WHERE withdrawal_timestamp=:timestamp "
                              "AND withdrawal_account=:from_acc_id AND deposit_account=:to_acc_id",
                              [(":timestamp", timestamp), (":from_acc_id", f_acc_id), (":to_acc_id", t_acc_id)])
        if transfer_id:
            logging.info(g_tr('StatementLoader', "Transfer/Exchange already exists: ") + f"{f_amount}->{t_amount}")
            return
        if abs(fee) > Setup.CALC_TOLERANCE:
            _ = executeSQL(self.db,
                           "INSERT INTO transfers (withdrawal_timestamp, withdrawal_account, withdrawal, "
                           "deposit_timestamp, deposit_account, deposit, fee_account, fee, note) "
                           "VALUES (:timestamp, :f_acc_id, :f_amount, :timestamp, :t_acc_id, :t_amount, "
                           ":fee_acc_id, :fee_amount, :note)",
                           [(":timestamp", timestamp), (":f_acc_id", f_acc_id), (":t_acc_id", t_acc_id),
                            (":f_amount", f_amount), (":t_amount", t_amount), (":fee_acc_id", fee_acc_id),
                            (":fee_amount", fee), (":note", note)])
        else:
            _ = executeSQL(self.db,
                           "INSERT INTO transfers (withdrawal_timestamp, withdrawal_account, withdrawal, "
                           "deposit_timestamp, deposit_account, deposit, note) "
                           "VALUES (:timestamp, :f_acc_id, :f_amount, :timestamp, :t_acc_id, :t_amount, :note)",
                           [(":timestamp", timestamp), (":f_acc_id", f_acc_id), (":t_acc_id", t_acc_id),
                            (":f_amount", f_amount), (":t_amount", t_amount), (":note", note)])
        self.db.commit()

    def createCorpAction(self, account_id, type, timestamp, number, asset_id_old, qty_old, asset_id_new, qty_new,
                         basis_ratio, note):
        action_id = readSQL(self.db,
                            "SELECT id FROM corp_actions "
                            "WHERE timestamp=:timestamp AND type = :type AND account_id = :account AND number = :number "
                            "AND asset_id = :asset AND asset_id_new = :asset_new",
                            [(":timestamp", timestamp), (":type", type), (":account", account_id), (":number", number),
                             (":asset", asset_id_old), (":asset_new", asset_id_new)])
        if action_id:
            logging.info(g_tr('StatementLoader', "Corporate action already exists: #") + f"{number}")
            return

        _ = executeSQL(self.db,
                       "INSERT INTO corp_actions (timestamp, number, account_id, type, "
                       "asset_id, qty, asset_id_new, qty_new, basis_ratio, note) "
                       "VALUES (:timestamp, :number, :account, :type, "
                       ":asset, :qty, :asset_new, :qty_new, :basis_ratio, :note)",
                       [(":timestamp", timestamp), (":number", number), (":account", account_id), (":type", type),
                        (":asset", asset_id_old), (":qty", float(qty_old)), (":asset_new", asset_id_new),
                        (":qty_new", float(qty_new)), (":basis_ratio", basis_ratio), (":note", note)])
        self.db.commit()

    def loadIBDividend(self, dividend):
        self.createDividend(DividendSubtype.Dividend, dividend['dateTime'], dividend['accountId'], dividend['symbol'],
                            dividend['amount'], dividend['description'])
        return 1

    def loadIBBondInterest(self, interest):
        self.createDividend(DividendSubtype.BondInterest, interest['dateTime'], interest['accountId'], interest['symbol'],
                            interest['amount'], interest['description'], interest['tradeID'])
        return 1

    def loadIBWithholdingTax(self, tax):
        self.addWithholdingTax(tax['dateTime'], tax['accountId'], tax['symbol'], -tax['amount'], tax['description'])
        return 1

    def loadIBFee(self, fee):
        bank_id = self.getAccountBank(fee['accountId'])
        query = executeSQL(self.db, "INSERT INTO actions (timestamp, account_id, peer_id) "
                                    "VALUES (:timestamp, :account_id, :bank_id)",
                           [(":timestamp", fee['dateTime']), (":account_id", fee['accountId']), (":bank_id", bank_id)])
        pid = query.lastInsertId()
        _ = executeSQL(self.db, "INSERT INTO action_details (pid, category_id, sum, note) "
                                "VALUES (:pid, :category_id, :sum, :note)",
                       [(":pid", pid), (":category_id", PredefinedCategory.Fees), (":sum", fee['amount']),
                        (":note", fee['description'])])
        self.db.commit()
        return 1

    def loadIBInterest(self, interest):
        bank_id = self.getAccountBank(interest['accountId'])
        query = executeSQL(self.db, "INSERT INTO actions (timestamp, account_id, peer_id) "
                                    "VALUES (:timestamp, :account_id, :bank_id)",
                           [(":timestamp", interest['dateTime']), (":account_id", interest['accountId']),
                            (":bank_id", bank_id)])
        pid = query.lastInsertId()
        _ = executeSQL(self.db, "INSERT INTO action_details (pid, category_id, sum, note) "
                                "VALUES (:pid, :category_id, :sum, :note)",
                       [(":pid", pid), (":category_id", PredefinedCategory.Interest), (":sum", interest['amount']),
                        (":note", interest['description'])])
        self.db.commit()
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

        dialog = SelectAccountDialog(self.parent, self.db, text, cash['accountId'],
                                     recent_account=self.last_selected_account)
        if dialog.exec_() != QDialog.Accepted:
            return 0
        self.last_selected_account = dialog.account_id
        if cash['amount'] >= 0:
            self.createTransfer(cash['dateTime'], dialog.account_id, cash['amount'],
                                cash['accountId'], cash['amount'], 0, 0, cash['description'])
        else:
            self.createTransfer(cash['dateTime'], cash['accountId'], -cash['amount'],
                                dialog.account_id, -cash['amount'], 0, 0, cash['description'])
        return 1

    def createDividend(self, subtype, timestamp, account_id, asset_id, amount, note, trade_number=''):
        id = readSQL(self.db, "SELECT id FROM dividends WHERE timestamp=:timestamp "
                              "AND account_id=:account_id AND asset_id=:asset_id AND note=:note",
                     [(":timestamp", timestamp), (":account_id", account_id), (":asset_id", asset_id), (":note", note)])
        if id:
            logging.info(g_tr('StatementLoader', "Dividend already exists: ") + f"{note}")
            return
        _ = executeSQL(self.db, "INSERT INTO dividends (timestamp, number, type, account_id, asset_id, amount, note) "
                                "VALUES (:timestamp, :number, :subtype, :account_id, :asset_id, :amount, :note)",
                       [(":timestamp", timestamp), (":number", trade_number), (":subtype", subtype),
                        (":account_id", account_id), (":asset_id", asset_id), (":amount", amount), (":note", note)])
        self.db.commit()

    def addWithholdingTax(self, timestamp, account_id, asset_id, amount, note):
        parts = re.match(IBKR.TaxNotePattern, note)
        if not parts:
            logging.warning(g_tr('StatementLoader', "*** MANUAL ENTRY REQUIRED ***"))
            logging.warning(g_tr('StatementLoader', "Unhandled tax pattern found: ") + f"{note}")
            return
        dividend_note = parts.group(1) + '%'
        country_code = parts.group(2).lower()
        country_id = get_country_by_code(self.db, country_code)
        update_asset_country(self.db, asset_id, country_id)
        dividend_id = self.findDividend4Tax(timestamp, account_id, asset_id, dividend_note)
        if dividend_id is None:
            logging.warning(g_tr('StatementLoader', "Dividend not found for withholding tax: ") + f"{note}")
            return
        old_tax = readSQL(self.db, "SELECT tax FROM dividends WHERE id=:id", [(":id", dividend_id)])
        _ = executeSQL(self.db, "UPDATE dividends SET tax=:tax WHERE id=:dividend_id",
                       [(":dividend_id", dividend_id), (":tax", old_tax + amount)])
        self.db.commit()

    def findDividend4Tax(self, timestamp, account_id, asset_id, note):
        # Check strong match
        id = readSQL(self.db, "SELECT id FROM dividends WHERE type=:div AND timestamp=:timestamp "
                              "AND account_id=:account_id AND asset_id=:asset_id AND note LIKE :dividend_description",
                     [(":div", DividendSubtype.Dividend), (":timestamp", timestamp), (":account_id", account_id),
                      (":asset_id", asset_id), (":dividend_description", note)])
        if id is not None:
            return id
        # Check weak match
        range_start = ManipulateDate.startOfPreviousYear(day=datetime.utcfromtimestamp(timestamp))
        count = readSQL(self.db, "SELECT COUNT(id) FROM dividends WHERE type=:div AND timestamp>=:start_range "
                              "AND account_id=:account_id AND asset_id=:asset_id AND note LIKE :dividend_description",
                     [(":div", DividendSubtype.Dividend), (":start_range", range_start), (":account_id", account_id),
                      (":asset_id", asset_id), (":dividend_description", note)])
        if count > 1:
            logging.warning(g_tr('StatementLoader', "Multiple dividends match withholding tax"))
            return None
        id = readSQL(self.db, "SELECT id FROM dividends WHERE type=:div AND timestamp>=:start_range "
                              "AND account_id=:account_id AND asset_id=:asset_id AND note LIKE :dividend_description",
                     [(":div", DividendSubtype.Dividend), (":start_range", range_start), (":account_id", account_id),
                      (":asset_id", asset_id), (":dividend_description", note)])
        return id

    def loadQuikHtml(self, filename):
        try:
            data = pandas.read_html(filename, encoding='cp1251',
                                    converters={Quik.Qty: convert_amount, Quik.Amount: convert_amount,
                                                Quik.Price: convert_amount, Quik.Coupon: convert_amount})
        except:
            logging.error(g_tr('StatementLoader', "Can't read statement file"))
            return False

        report_info = data[0]
        deals_info = data[1]
        parts = re.match(Quik.ClientPattern, report_info[0][2])
        if parts:
            account_id = self.findAccountID(parts.group(1))
        else:
            logging.error(g_tr('StatementLoader', "Can't get account number from the statement."))
            return False
        if account_id is None:
            logging.error(g_tr('StatementLoader', "Account with number ") + f"{parts.group(1)}" +
                          g_tr('StatementLoader', " not found. Import cancelled."))
            return False

        for index, row in deals_info.iterrows():
            if row[Quik.Type] == Quik.Buy:
                qty = int(row[Quik.Qty])
            elif row[Quik.Type] == Quik.Sell:
                qty = -int(row[Quik.Qty])
            elif row[Quik.Type][:len(Quik.Total)] == Quik.Total:
                break  # End of statement reached
            else:
                logging.warning(g_tr('StatementLoader', "Unknown operation type ") + f"'{row[Quik.Type]}'")
                continue
            asset_id = self.findAssetID(row[Quik.Symbol])
            if asset_id is None:
                logging.warning(g_tr('StatementLoader', "Unknown asset ") + f"'{row[Quik.Symbol]}'")
                continue
            timestamp = int(
                datetime.strptime(row[Quik.DateTime], "%d.%m.%Y %H:%M:%S").replace(tzinfo=timezone.utc).timestamp())
            settlement = int(
                datetime.strptime(row[Quik.SettleDate], "%d.%m.%Y").replace(tzinfo=timezone.utc).timestamp())
            number = row[Quik.TradeNumber]
            price = row[Quik.Price]
            amount = row[Quik.Amount]
            lot_size = math.pow(10, round(math.log10(amount / (price * abs(qty)))))
            qty = qty * lot_size
            fee = float(row[Quik.Fee])
            if Quik.FeeEx in row:  # Broker dependent fee import
                fee = fee + float(row[Quik.FeeEx])
            else:
                fee = fee + float(row[Quik.FeeEx1]) + float(row[Quik.FeeEx2]) + float(row[Quik.FeeEx3])
            # FIXME paid/received bond interest should be recorded as separate transaction in table 'dividends'
            bond_interest = float(row[Quik.Coupon])
            self.createTrade(account_id, asset_id, timestamp, settlement, number, qty, price, -fee)
        return True
