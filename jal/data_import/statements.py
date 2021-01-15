import logging
import math
import re
from datetime import datetime

import pandas
from lxml import etree
from PySide2.QtCore import QObject, Signal, Slot
from PySide2.QtSql import QSqlTableModel
from PySide2.QtWidgets import QDialog, QFileDialog, QMessageBox
from jal.constants import Setup, TransactionType, PredefinedAsset, PredefinedCategory, CorporateAction
from jal.db.helpers import executeSQL, readSQL, get_country_by_code
from jal.ui_custom.helpers import g_tr
from jal.ui.ui_add_asset_dlg import Ui_AddAssetDialog
from jal.ui.ui_select_account_dlg import Ui_SelectAccountDlg


#-----------------------------------------------------------------------------------------------------------------------
class ReportType:
    IBKR = 'IBKR flex-query (*.xml)'
    Quik = 'Quik HTML-report (*.htm)'


class IBKRCashOp:
    Dividend = 0
    TaxWithhold = 1
    DepositWithdrawal = 2
    Fee = 3
    Interest = 4


#-----------------------------------------------------------------------------------------------------------------------
class IBKR:
    TaxNotePattern = "^(.*) - (..) TAX$"
    DummyExchange = "VALUE"
    SpinOffPattern = "^(.*)\(.* SPINOFF +(\d+) +FOR +(\d+) +\(.*$"
    SplitPattern = "^.* SPLIT +(\d+) +FOR +(\d+) +\(.*$"

    AssetType = {
        'CASH': PredefinedAsset.Money,
        'STK':  PredefinedAsset.Stock,
        # 'BOND': PredefinedAsset.Bond,
        'OPT':  PredefinedAsset.Derivative,
        'FUT':  PredefinedAsset.Derivative
    }

    CorpAction = {
        'TC': CorporateAction.Merger,
        'SO': CorporateAction.SpinOff,
        'IC': CorporateAction.SymbolChange,
        'HI': CorporateAction.StockDividend,
        'FS': CorporateAction.Split
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
                return int(datetime.strptime(time_str, "%Y%m%d;%H%M%S").timestamp())
            elif len(time_str) == 8: # YYYYMMDD
                return int(datetime.strptime(time_str, "%Y%m%d").timestamp())
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
            'Withholding Tax':              IBKRCashOp.TaxWithhold,
            'Deposits/Withdrawals':         IBKRCashOp.DepositWithdrawal,
            'Other Fees':                   IBKRCashOp.Fee,
            'Commission Adjustments':       IBKRCashOp.Fee,
            'Broker Interest Paid':         IBKRCashOp.Interest,
            'Broker Interest Received':     IBKRCashOp.Fee
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
        if data.tag == 'CorporateAction' and IBKR.flString(data, 'listingExchange', None, None) == IBKR.DummyExchange:
            if data.attrib[name].endswith('.OLD'):
                return caller.findAssetID(data.attrib[name][:-len('.OLD')])
        return caller.findAssetID(data.attrib[name])

#-----------------------------------------------------------------------------------------------------------------------
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


#-----------------------------------------------------------------------------------------------------------------------
# Strip white spaces from numbers imported form Quik html-report
def convert_amount(val):
    val = val.replace(' ', '')
    try:
        res = float(val)
    except ValueError:
        res = 0
    return res


def addNewAsset(db, symbol, name, asset_type, isin, data_source=-1):
    _ = executeSQL(db, "INSERT INTO assets(name, type_id, full_name, isin, src_id) "
                       "VALUES(:symbol, :type, :full_name, :isin, :data_src)",
                   [(":symbol", symbol), (":type", asset_type), (":full_name", name),
                    (":isin", isin), (":data_src", data_source)])
    db.commit()
    asset_id = readSQL(db, "SELECT id FROM assets WHERE name=:symbol", [(":symbol", symbol)])
    if asset_id is None:
        logging.error(g_tr('StatementLoader', "Failed to add new asset: ") + f"{symbol}")
    return asset_id


#-----------------------------------------------------------------------------------------------------------------------
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
        x = parent.x() + parent.width()/2 - self.width()/2
        y = parent.y() + parent.height()/2 - self.height()/2
        self.setGeometry(x, y, self.width(), self.height())

    def accept(self):
        self.asset_id = addNewAsset(self.db, self.SymbolEdit.text(), self.NameEdit.text(),
                                    self.type_model.record(self.TypeCombo.currentIndex()).value("id"),
                                    self.isinEdit.text(),
                                    self.data_src_model.record(self.DataSrcCombo.currentIndex()).value("id"))
        super().accept()


#-----------------------------------------------------------------------------------------------------------------------
class SelectAccountDialog(QDialog, Ui_SelectAccountDlg):
    def __init__(self, parent, db, description, current_account):
        QDialog.__init__(self)
        self.setupUi(self)
        self.db = db
        self.account_id = None
        self.current_account = current_account

        self.DescriptionLbl.setText(description)
        self.AccountWidget.init_db(db)

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

#-----------------------------------------------------------------------------------------------------------------------
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

    # Searches for asset_id in database and returns it.
    # If asset is not found - shows dialog for new asset creation.
    # Returns: asset_id or None if new asset creation failed
    def findAssetID(self, symbol):
        asset_id = readSQL(self.db, "SELECT id FROM assets WHERE name=:symbol", [(":symbol", symbol)])
        if asset_id is None:
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
        if bank_id is not None:
            return bank_id
        query = executeSQL(self.db, "INSERT INTO agents (pid, name) VALUES (0, 'Interactive Brokers')")
        bank_id =query.lastInsertId()
        _ = executeSQL(self.db, "UPDATE accounts SET organization_id=:bank_id WHERE id=:account_id",
                       [(":bank_id", bank_id), (":account_id", account_id)])
        return bank_id

    def loadIBFlex(self, filename):
        section_loaders = {
            'SecuritiesInfo':   self.loadIBSecurities,    # Order of load is important - SecuritiesInfo is first
            'Trades':           self.loadIBTrades,
            # Load of options Expirations, Assignments and Executions was disabled because data are present
            # in 'Trades' section as 'BookTrade' operations and functions were dummy before
            # 'OptionEAE':        self.loadIBOptions,
            'CorporateActions': self.loadIBCorporateActions,
            'CashTransactions': self.loadIBCashTransactions,
            'TransactionTaxes': self.loadIBTaxes
        }
        try:
            xml_root = etree.parse(filename)
            for FlexStatements in xml_root.getroot():
                for statement in FlexStatements:
                    attr = statement.attrib
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
            'CashTransactions': {'tag': 'CashTransaction', 'values': [('type', IBKR.flCashOpType, None),
                                                                      ('accountId', IBKR.flAccount, None),
                                                                      ('currency', IBKR.flString, ''),
                                                                      ('symbol', IBKR.flAsset, 0),
                                                                      ('dateTime', IBKR.flTimestamp, None),
                                                                      ('amount', IBKR.flNumber, None),
                                                                      ('description', IBKR.flString, None)]},
            'CorporateActions': {'tag': 'CorporateAction', 'values': [('type', IBKR.flCorpActionType, None),
                                                                      ('accountId', IBKR.flAccount, None),
                                                                      ('symbol', IBKR.flAsset, None),
                                                                      ('listingExchange', IBKR.flString, ''),
                                                                      ('assetCategory', IBKR.flAssetType, None),
                                                                      ('dateTime', IBKR.flTimestamp, None),
                                                                      ('transactionID', IBKR.flString, ''),
                                                                      ('description', IBKR.flString, None),
                                                                      ('quantity', IBKR.flNumber, None),
                                                                      ('code', IBKR.flString, '')]},
            'SecuritiesInfo': {'tag': 'SecurityInfo',
                               'values': [('symbol', IBKR.flString, None),
                                          ('assetCategory', IBKR.flAssetType, None),
                                          ('subCategory', IBKR.flString, ''),
                                          ('description', IBKR.flString, None),
                                          ('isin', IBKR.flString, '')]},
            'Trades': {'tag': 'Trade', 'values': [('assetCategory', IBKR.flAssetType, None),
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
            'TransactionTaxes': {'tag': 'TransactionTax', 'values': [('accountId', IBKR.flAccount, None),
                                                                     ('symbol', IBKR.flString, ''),
                                                                     ('date', IBKR.flTimestamp, None),
                                                                     ('taxAmount', IBKR.flNumber, None),
                                                                     ('description', IBKR.flString, None),
                                                                     ('taxDescription', IBKR.flString, None)]}
        }

        try:
            tag = section_descriptions[section.tag]['tag']
        except KeyError:
            return []           # This section isn't used for import

        data = []
        for sample in section.xpath(tag):
            tag_dictionary = {}
            for attr_name, attr_loader, attr_default in section_descriptions[section.tag]['values']:
                attr_value = attr_loader(sample, attr_name, attr_default, self)
                if attr_value is None:
                    logging.error(g_tr('StatementLoader', "Failed to load attribute: ") + f"{attr_name} / {sample.attrib}")
                    return None
                tag_dictionary[attr_name] = attr_value
            data.append(tag_dictionary)
        return data

    def loadIBSecurities(self, assets):
        cnt = 0
        for asset in assets:
            if readSQL(self.db, "SELECT id FROM assets WHERE name=:symbol", [(":symbol", asset['symbol'])]):
                continue
            asset_type = PredefinedAsset.ETF if asset['subCategory'] == "ETF" else asset['assetCategory']
            addNewAsset(self.db, asset['symbol'], asset['description'], asset_type, asset['isin'])
            cnt += 1
        logging.info(g_tr('StatementLoader', "Securities loaded: ") + f"{cnt} ({len(assets)})")

    def loadIBTrades(self, trades):
        ib_trade_loaders = {
            PredefinedAsset.Stock:      self.loadIBStockTrade,
            PredefinedAsset.Derivative: self.loadIBStockTrade,
            PredefinedAsset.Money:      self.loadIBCurrencyTrade
        }

        cnt = 0
        for trade in trades:
            cnt += ib_trade_loaders[trade['assetCategory']](trade)
        logging.info(g_tr('StatementLoader', "Trades loaded: ") + f"{cnt} ({len(trades)})")

    def loadIBCorporateActions(self, actions):
        cnt = 0
        for action in actions:
            if action['listingExchange'] == IBKR.DummyExchange:  # Skip actions that we loaded as part of main action
                continue
            if action['code'] == 'Ca':
                logging.warning(g_tr('StatementLoader', "*** MANUAL ACTION REQUIRED ***"))
                logging.warning(g_tr('StatementLoader', "Corporate action cancelled: ") + f"{action}")
                continue
            if action['assetCategory'] != PredefinedAsset.Stock:
                logging.warning(g_tr('StatementLoader', "Corporate actions are supported for stocks only"))
                continue

            if action['type'] == CorporateAction.Merger:
                # additional info is in previous dummy record where original symbol and quantity are present
                pair_idu = str(int(action['transactionID']) + 1)
                pair_idl = str(int(action['transactionID']) - 1)
                paired_records = list(filter(
                    lambda pair: (pair['transactionID'] == pair_idl or pair['transactionID'] == pair_idu)
                                 and pair['listingExchange'] == IBKR.DummyExchange
                                 and pair['type'] == action['type']
                                 and pair['description'][:15] == action['description'][:15], actions))
                if len(paired_records) != 1:
                    logging.error(g_tr('StatementLoader', "Can't find paired record for ") + f"{action}")
                    continue
                self.createCorpAction(action['accountId'], CorporateAction.Merger, action['dateTime'], action['transactionID'], paired_records[0]['symbol'],
                                      -paired_records[0]['quantity'], action['symbol'], action['quantity'], action['description'])
                cnt += 2
            elif action['type'] == CorporateAction.SpinOff:
                parts = re.match(IBKR.SpinOffPattern, action['description'], re.IGNORECASE)
                if not parts:
                    logging.error(g_tr('StatementLoader', "Failed to parse Spin-off data for ") + f"{action}")
                    continue
                asset_id_old = self.findAssetID(parts.group(1))
                mult_a = int(parts.group(2))
                mult_b = int(parts.group(3))
                qty_old = mult_b * action['quantity'] / mult_a
                self.createCorpAction(action['accountId'], CorporateAction.SpinOff, action['dateTime'], action['transactionID'], asset_id_old,
                                      qty_old, action['symbol'], action['quantity'], action['description'])
                cnt += 1
            elif action['type'] == CorporateAction.SymbolChange:
                # additional info is in next dummy record where old symbol is changed to *.OLD
                pair_idu = str(int(action['transactionID']) + 1)
                pair_idl = str(int(action['transactionID']) - 1)
                paired_records = list(filter(
                    lambda pair: (pair['transactionID'] == pair_idl or pair['transactionID'] == pair_idu)
                                 and pair['listingExchange'] == IBKR.DummyExchange
                                 and pair['type'] == action['type']
                                 and pair['description'][:15] == action['description'][:15], actions))
                if len(paired_records) != 1:
                    logging.error(g_tr('StatementLoader', "Can't find paired record for: ") + f"{action}")
                    continue
                self.createCorpAction(action['accountId'], CorporateAction.SymbolChange, action['dateTime'], action['transactionID'], paired_records[0]['symbol'],
                                      action['quantity'], action['symbol'], action['quantity'], action['description'])
                cnt += 2
            elif action['type'] == CorporateAction.StockDividend:
                self.createCorpAction(action['accountId'], CorporateAction.StockDividend, action['dateTime'], action['transactionID'], action['symbol'], 0,
                                      action['symbol'], action['quantity'], action['description'])
                cnt += 1
            elif action['type'] == CorporateAction.Split:
                parts = re.match(IBKR.SplitPattern, action['description'], re.IGNORECASE)
                if not parts:
                    logging.error(g_tr('StatementLoader', "Failed to parse corp.action Split data"))
                    return
                mult_a = int(parts.group(1))
                mult_b = int(parts.group(2))
                qty_new = mult_a * action['quantity'] / mult_b
                self.createCorpAction(action['accountId'], CorporateAction.Split, action['dateTime'], action['transactionID'], action['symbol'],
                                      action['quantity'], action['symbol'], qty_new, action['description'])
                cnt += 1
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

    def loadIBCashTransactions(self, cash):
        cnt = 0

        dividends = list(filter(lambda tr: tr['type'] == IBKRCashOp.Dividend, cash))
        for dividend in dividends:
            cnt += self.loadIBDividend(dividend)

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
        if trade['notes'] == 'Ca':
            self.deleteTrade(trade['accountId'], trade['symbol'], trade['dateTime'], trade['settleDateTarget'],
                             trade['tradeID'], qty, trade['tradePrice'], trade['ibCommission'])
        else:
            self.createTrade(trade['accountId'], trade['symbol'], trade['dateTime'], trade['settleDateTarget'],
                             trade['tradeID'], qty, trade['tradePrice'], trade['ibCommission'])
        return 1

    def createTrade(self, account_id, asset_id, timestamp, settlement, number, qty, price, fee, coupon=0.0):
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
                       "INSERT INTO trades (timestamp, settlement, number, account_id, "
                       "asset_id, qty, price, fee, coupon) "
                       "VALUES (:timestamp, :settlement, :number, :account, :asset, :qty, :price, :fee, :coupon)",
                       [(":timestamp", timestamp), (":settlement", settlement), (":number", number),
                        (":account", account_id), (":asset", asset_id), (":qty", float(qty)),
                        (":price", float(price)), (":fee", -float(fee)), (":coupon", float(coupon))])
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
            from_amount = trade['proceeds']  # already negative value
        elif trade['quantity'] < 0:
            from_idx = 0
            to_idx = 1
            from_amount = trade['quantity']  # already negative value
            to_amount = trade['proceeds']  # positive value
        else:
            logging.error(g_tr('StatementLoader', "Zero quantity in cash trade: ") + f"{trade}")
            return 0
        self.createTransfer(trade['dateTime'], trade['accountId'][from_idx], from_amount,
                            trade['accountId'][to_idx], to_amount, trade['accountId'][2], trade['ibCommission'], trade['exchange'])
        return 1

    def createTransfer(self, timestamp, f_acc_id, f_amount, t_acc_id, t_amount, fee_acc_id, fee, note):
        transfer_id = readSQL(self.db,
                              "SELECT id FROM transfers_combined "
                              "WHERE from_timestamp=:timestamp AND from_acc_id=:from_acc_id AND to_acc_id=:to_acc_id",
                              [(":timestamp", timestamp), (":from_acc_id", f_acc_id), (":to_acc_id", t_acc_id)])
        if transfer_id:
            logging.info(g_tr('StatementLoader', "Transfer/Exchange already exists: ") + f"{f_amount}->{t_amount}")
            return
        if abs(fee) > Setup.CALC_TOLERANCE:
            _ = executeSQL(self.db,
                           "INSERT INTO transfers_combined (from_timestamp, from_acc_id, from_amount, "
                           "to_timestamp, to_acc_id, to_amount, fee_timestamp, fee_acc_id, fee_amount, note) "
                           "VALUES (:timestamp, :f_acc_id, :f_amount, :timestamp, :t_acc_id, :t_amount, "
                           ":timestamp, :fee_acc_id, :fee_amount, :note)",
                           [(":timestamp", timestamp), (":f_acc_id", f_acc_id), (":t_acc_id", t_acc_id),
                            (":f_amount", f_amount), (":t_amount", t_amount), (":fee_acc_id", fee_acc_id),
                            (":fee_amount", fee), (":note", note)])
        else:
            _ = executeSQL(self.db,
                           "INSERT INTO transfers_combined (from_timestamp, from_acc_id, from_amount, "
                           "to_timestamp, to_acc_id, to_amount, note) "
                           "VALUES (:timestamp, :f_acc_id, :f_amount, :timestamp, :t_acc_id, :t_amount, :note)",
                           [(":timestamp", timestamp), (":f_acc_id", f_acc_id), (":t_acc_id", t_acc_id),
                            (":f_amount", f_amount), (":t_amount", t_amount), (":note", note)])
        self.db.commit()

    def createCorpAction(self, account_id, type, timestamp, number, asset_id_old, qty_old, asset_id_new, qty_new, note):
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
                       "asset_id, qty, asset_id_new, qty_new, note) "
                       "VALUES (:timestamp, :number, :account, :type, :asset, :qty, :asset_new, :qty_new, :note)",
                       [(":timestamp", timestamp), (":number", number), (":account", account_id), (":type", type),
                        (":asset", asset_id_old), (":qty", float(qty_old)),
                        (":asset_new", asset_id_new), (":qty_new", float(qty_new)), (":note", note)])
        self.db.commit()

    def loadIBDividend(self, dividend):
        self.createDividend(dividend['dateTime'], dividend['accountId'], dividend['symbol'], dividend['amount'], dividend['description'])
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
        if cash['amount'] >= 0:     # Deposit
            text = g_tr('StatementLoader', "Deposit of ") + f"{cash['amount']:.2f} {cash['currency']} " + \
                   f"@{datetime.fromtimestamp(cash['dateTime']).strftime('%d.%m.%Y')}\n" + \
                   g_tr('StatementLoader', "Select account to withdraw from:")
        else:                       # Withdrawal
            text = g_tr('StatementLoader', "Withdrawal of ") + f"{-cash['amount']:.2f} {cash['currency']} " + \
                   f"@{datetime.fromtimestamp(cash['dateTime']).strftime('%d.%m.%Y')}\n" + \
                   g_tr('StatementLoader', "Select account to deposit to:")

        dialog = SelectAccountDialog(self.parent, self.db, text, cash['accountId'])
        if dialog.exec_() != QDialog.Accepted:
            return 0

        if cash['amount'] >= 0:
            self.createTransfer(cash['dateTime'], dialog.account_id, -cash['amount'],
                                cash['accountId'], cash['amount'], 0, 0, cash['description'])
        else:
            self.createTransfer(cash['dateTime'], cash['accountId'], cash['amount'],
                                dialog.account_id, -cash['amount'], 0, 0, cash['description'])
        return 1

    def createDividend(self, timestamp, account_id, asset_id, amount, note):
        id = readSQL(self.db, "SELECT id FROM dividends WHERE timestamp=:timestamp "
                              "AND account_id=:account_id AND asset_id=:asset_id AND note=:note",
                     [(":timestamp", timestamp), (":account_id", account_id), (":asset_id", asset_id), (":note", note)])
        if id:
            logging.info(g_tr('StatementLoader', "Dividend already exists: ") + f"{note}")
            return
        _ = executeSQL(self.db, "INSERT INTO dividends (timestamp, account_id, asset_id, sum, note) "
                                "VALUES (:timestamp, :account_id, :asset_id, :sum, :note)",
                       [(":timestamp", timestamp), (":account_id", account_id), (":asset_id", asset_id),
                        (":sum", amount), (":note", note)])
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
        if country_id == 0:
            query = executeSQL(self.db, "INSERT INTO countries(name, code, tax_treaty) VALUES (:name, :code, 0)",
                               [(":name", "Country_" + country_code), (":code", country_code)])
            country_id = query.lastInsertId()
            logging.warning(g_tr('StatementLoader', "New country added (set Tax Treaty in Data->Countries menu): ")
                            + f"'{country_code}'")
        try:
            dividend_id, old_tax = readSQL(self.db,
                                           "SELECT id, sum_tax FROM dividends "
                                           "WHERE timestamp=:timestamp AND account_id=:account_id "
                                           "AND asset_id=:asset_id AND note LIKE :dividend_description",
                                           [(":timestamp", timestamp), (":account_id", account_id),
                                            (":asset_id", asset_id), (":dividend_description", dividend_note)])
        except:
            logging.warning(g_tr('StatementLoader', "Dividend not found for withholding tax: ") + f"{note}")
            return
        _ = executeSQL(self.db, "UPDATE dividends SET sum_tax=:tax, tax_country_id=:country_id WHERE id=:dividend_id",
                       [(":dividend_id", dividend_id), (":tax", old_tax + amount), (":country_id", country_id)])
        self.db.commit()

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
                break   # End of statement reached
            else:
                logging.warning(g_tr('StatementLoader', "Unknown operation type ") + f"'{row[Quik.Type]}'")
                continue
            asset_id = self.findAssetID(row[Quik.Symbol])
            if asset_id is None:
                logging.warning(g_tr('StatementLoader', "Unknown asset ") + f"'{row[Quik.Symbol]}'")
                continue
            timestamp = int(datetime.strptime(row[Quik.DateTime], "%d.%m.%Y %H:%M:%S").timestamp())
            settlement = int(datetime.strptime(row[Quik.SettleDate], "%d.%m.%Y").timestamp())
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
            coupon = float(row[Quik.Coupon])
            self.createTrade(account_id, asset_id, timestamp, settlement, number, qty, price, -fee, coupon)
        return True