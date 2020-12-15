import logging
import math
import re
from datetime import datetime

import pandas
from lxml import etree
from PySide2.QtCore import QObject, Signal
from PySide2.QtSql import QSqlTableModel
from PySide2.QtWidgets import QDialog, QFileDialog
from constants import Setup, TransactionType, PredefinedAsset, PredefinedCategory, CorporateAction
from db.helpers import executeSQL, readSQL, get_country_by_code
from ui_custom.helpers import g_tr
from ui.ui_add_asset_dlg import Ui_AddAssetDialog


#-----------------------------------------------------------------------------------------------------------------------
class ReportType:
    IBKR = 'IBKR flex-query (*.xml)'
    Quik = 'Quik HTML-report (*.htm)'


#-----------------------------------------------------------------------------------------------------------------------
class IBKR:
    TaxNotePattern = "^(.*) - (..) TAX$"
    AssetType = {
        'STK': PredefinedAsset.Stock,
        'BOND': PredefinedAsset.Bond,
        'OPT': PredefinedAsset.Derivative,
        'FUT': PredefinedAsset.Derivative
    }
    DummyExchange = "VALUE"
    SpinOffPattern = "^(.*)\(.* SPINOFF +(\d+) +FOR +(\d+) +\(.*$"
    IssueChangePattern = "^(.*)\.OLD$"
    SplitPattern = "^.* SPLIT +(\d+) +FOR +(\d+) +\(.*$"


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
        logging.error(g_tr('', "Failed to add new asset: "), + f"{symbol}")
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
            'OptionEAE':        self.loadIBOptions,
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
                            section_loaders[section](self.getIBdata(section_elements[0]))
        except Exception as e:
            logging.error(g_tr('StatementLoader', "Failed to parse Interactive Brokers flex-report") + f": {e}")
            return False
        logging.info(g_tr('StatementLoader', "IB Flex-statement loaded successfully"))
        return True

    def getIBdata(self, section):
        section_tags = {
            'CashTransactions': 'CashTransaction',
            'CorporateActions': 'CorporateAction',
            'OptionEAE':        'OptionEAE',
            'SecuritiesInfo':   'SecurityInfo',
            'Trades':           'Trade',
            'TransactionTaxes': 'TransactionTax'
        }

        data = []
        try:
            tag = section_tags[section.tag]
        except KeyError:
            return data
        for sample in section.xpath(tag):
            tag_dictionary = {}
            for attr_name, attr_value in sample.items():
                tag_dictionary[attr_name] = attr_value
            data.append(tag_dictionary)
        return data

    def loadIBSecurities(self, assets):
        cnt = 0
        for asset in assets:
            if readSQL(self.db, "SELECT id FROM assets WHERE name=:symbol", [(":symbol", asset['symbol'])]):
                continue
            try:
                asset_type = PredefinedAsset.ETF if asset['subCategory'] == "ETF" else IBKR.AssetType[asset['assetCategory']]
            except:
                logging.error(g_tr('StatementLoader', "Asset type isn't supported: ") + f"{asset['assetCategory']}")
                continue
            addNewAsset(self.db, asset['symbol'], asset['description'], asset_type, asset['isin'])
            cnt += 1
        logging.info(g_tr('StatementLoader', "Securities loaded: ") + f"{cnt} ({len(assets)})")

    def loadIBTrades(self, trades):
        ib_trade_loaders = {
            'STK': self.loadIBStockTrade,
            'OPT': self.loadIBStockTrade,
            'CASH': self.loadIBCurrencyTrade
        }

        cnt = 0
        for trade in trades:
            try:
                cnt += ib_trade_loaders[trade['assetCategory']](trade)
            except KeyError:
                logging.error(g_tr('StatementLoader', "Trade isn't implemented for type: ") + f"{trade['assetCategory']}")
        logging.info(g_tr('StatementLoader', "Trades loaded: ") + f"{cnt} ({len(trades)})")

    def loadIBOptions(self, options):
        ib_option_loaders = {
            "Assignment": self.loadIBOptionEAE,
            "Exercise":   self.loadIBOptionEAE,
            "Expiration": self.loadIBOptionEAE,
            "Buy":        self.loadIBStockTrade,
            "Sell":       self.loadIBStockTrade,
        }
        cnt = 0
        for option in options:
            try:
                cnt += ib_option_loaders[option['transactionType']](option)
            except KeyError:
                logging.error(
                    g_tr('StatementLoader', "Option E&A&E action isn't implemented: ") + f"{option['transactionType']}")
        logging.info(g_tr('StatementLoader', "Options E&A&E loaded: ") + f"{cnt} ({len(options)})")

    def loadIBCorporateActions(self, actions):
        cnt = 0
        for action in actions:
            try:
                if action['listingExchange'] == IBKR.DummyExchange:  # Skip actions that we loaded as part of main action
                    continue
                if action['code'] == 'Ca':
                    logging.warning(g_tr('StatementLoader', "*** MANUAL ACTION REQUIRED ***"))
                    logging.warning(g_tr('StatementLoader', "Corporate action cancelled: ") + f"{action}")
                    continue
                if action['assetCategory'] != 'STK':
                    logging.warning(g_tr('StatementLoader', "Corporate action not supported for asset class: ")
                                    + f"{action['assetCategory']}")
                    continue
                account_id = self.findAccountID(action['accountId'], action['currency'])
                type = action['type']
                asset_id_new = self.findAssetID(action['symbol'])
                timestamp = int(datetime.strptime(action['dateTime'], "%Y%m%d;%H%M%S").timestamp())
                number = action['transactionID']
                note = action['description']
                qty = float(action['quantity'])
            except KeyError as e:
                logging.error(g_tr('StatementLoader', "Failed to get field: ") + f"{e} / {action}")
                continue

            if type == 'TC':   # Reorg.MERGER
                # additional info is in previous dummy record where original symbol and quantity are present
                pair_id = str(int(number) - 1)
                paired_records = list(filter(
                    lambda pair: pair['transactionID'] == pair_id and pair['listingExchange'] == IBKR.DummyExchange,
                    actions))
                if len(paired_records) != 1:
                    logging.error(g_tr('StatementLoader', "Can't find paired record for ") + f"{action}")
                    continue
                asset_id_old = self.findAssetID(paired_records[0]['symbol'])
                qty_old = -float(paired_records[0]['quantity'])
                self.createCorpAction(account_id, CorporateAction.Merger, timestamp, number, asset_id_old,
                                      qty_old, asset_id_new, qty, note)
                cnt += 2
            elif type == 'SO':   # Reorg.SPINOFF
                parts = re.match(IBKR.SpinOffPattern, note, re.IGNORECASE)
                if not parts:
                    logging.error(g_tr('StatementLoader', "Failed to parse Spin-off data for ") + f"{action}")
                    continue
                asset_id_old = self.findAssetID(parts.group(1))
                mult_a = int(parts.group(2))
                mult_b = int(parts.group(3))
                qty_old = mult_b * qty / mult_a
                self.createCorpAction(account_id, CorporateAction.SpinOff, timestamp, number, asset_id_old,
                                      qty_old, asset_id_new, qty, note)
                cnt += 1
            elif type == 'IC':    # Reorg.ISSUECHANGE
                # additional info is in next dummy record where old symbol is changed to *.OLD
                pair_id = str(int(number) + 1)
                paired_records = list(filter(
                    lambda pair: pair['transactionID'] == pair_id and pair['listingExchange'] == IBKR.DummyExchange,
                    actions))
                if len(paired_records) != 1:
                    logging.error(g_tr('StatementLoader', "Can't find paired record for: ") + f"{action}")
                    continue
                parts = re.match(IBKR.IssueChangePattern, paired_records[0]['symbol'])
                if not parts:
                    logging.error(g_tr('StatementLoader', "Failed to parse old symbol for: ") + f"{action}")
                    return
                asset_id_old = self.findAssetID(parts.group(1))
                self.createCorpAction(account_id, CorporateAction.SymbolChange, timestamp, number, asset_id_old,
                                      qty, asset_id_new, qty, note)
                cnt += 2
            elif type == 'HI':    # Reorg.CHOICEDIVISSUE
                self.createCorpAction(account_id, CorporateAction.StockDividend, timestamp, number, asset_id_new, 0,
                                      asset_id_new, qty, note)
            elif type == 'FS':    # Reorg.FORWARDSPLIT
                parts = re.match(IBKR.SplitPattern, note, re.IGNORECASE)
                if not parts:
                    logging.error(g_tr('StatementLoader', "Failed to parse corp.action Split data"))
                    return
                mult_a = int(parts.group(1))
                mult_b = int(parts.group(2))
                qty_new = mult_a * qty / mult_b
                self.createCorpAction(account_id, CorporateAction.Split, timestamp, number, asset_id_new,
                                      qty, asset_id_new, qty_new, note)
                cnt += 1
            else:
                logging.error(g_tr('StatementLoader', "Corporate action type is not supported: ")
                              + f"{type}")
                continue
        logging.info(g_tr('StatementLoader', "Corporate actions loaded: ") + f"{cnt} ({len(actions)})")

    def loadIBTaxes(self, taxes):
        cnt = 0
        for tax in taxes:
            try:
                account_id = self.findAccountID(tax['accountId'], tax['currency'])
                bank_id = self.getAccountBank(account_id)
                timestamp = int(datetime.strptime(tax['date'], "%Y%m%d").timestamp())
                amount = float(tax['taxAmount'])    # value is negative already
                note = f"{tax['symbol']} ({tax['description']}) - {tax['taxDescription']} (#{tax['tradeId']})"
            except KeyError as e:
                logging.error(g_tr('StatementLoader', "Failed to get field: ") + f"{e} / {tax}")
                continue
            id = readSQL(self.db, "SELECT id FROM all_operations WHERE type = :type "
                                  "AND timestamp=:timestamp AND account_id=:account_id AND amount=:amount",
                         [(":timestamp", timestamp), (":type", TransactionType.Action),
                          (":account_id", account_id), (":amount", amount)])
            if id:
                logging.warning(g_tr('StatementLoader', "Tax transaction already exists #") + f"{tax['tradeId']}")
                continue
            query = executeSQL(self.db, "INSERT INTO actions (timestamp, account_id, peer_id) "
                                        "VALUES (:timestamp, :account_id, :bank_id)",
                               [(":timestamp", timestamp), (":account_id", account_id), (":bank_id", bank_id)])
            pid = query.lastInsertId()
            _ = executeSQL(self.db, "INSERT INTO action_details (pid, category_id, sum, note) "
                                    "VALUES (:pid, :category_id, :sum, :note)",
                           [(":pid", pid), (":category_id", PredefinedCategory.Taxes),
                            (":sum", amount), (":note", note)])
            self.db.commit()
            cnt += 1
        logging.info(g_tr('StatementLoader', "Taxes loaded: ") + f"{cnt} ({len(taxes)})")

    def loadIBCashTransactions(self, cash):
        cnt = 0

        dividends = list(filter(lambda tr: tr['type'] == 'Dividends', cash))
        for dividend in dividends:
            cnt += self.loadIBDividend(dividend)

        taxes = list(filter(lambda tr: tr['type'] == 'Withholding Tax', cash))
        for tax in taxes:
            cnt += self.loadIBWithholdingTax(tax)

        transfers = list(filter(lambda tr: tr['type'] == 'Deposits/Withdrawals', cash))
        for transfer in transfers:
            cnt += self.loadIBDepositWithdraw(transfer)

        fees = list(filter(lambda tr: tr['type'] == 'Other Fees' or tr['type'] == 'Broker Interest Paid', cash))
        for fee in fees:
            cnt += self.loadIBFee(fee)

        interests = list(filter(lambda tr: tr['type'] == 'Broker Interest Received', cash))
        for interest in interests:
            cnt += self.loadIBInterest(interest)
        logging.info(g_tr('StatementLoader', "Cash transactions loaded: ") + f"{cnt} ({len(cash)})")

    def loadIBStockTrade(self, trade):
        trade_action = {
            'BUY': self.createTrade,
            'Buy': self.createTrade,
            'SELL': self.createTrade,
            'Sell': self.createTrade,
            'BUY (Ca.)': self.deleteTrade,
            'SELL (Ca.)': self.deleteTrade
        }
        try:
            if 'buySell' in trade:
                type = trade['buySell']
            else:
                type = trade['transactionType']
            account_id = self.findAccountID(trade['accountId'], trade['currency'])
            asset_id = self.findAssetID(trade['symbol'])
            if 'dateTime' in trade:
                timestamp = int(datetime.strptime(trade['dateTime'], "%Y%m%d;%H%M%S").timestamp())
            else:
                timestamp = int(datetime.strptime(trade['date'], "%Y%m%d").timestamp())
            settlement = timestamp
            if 'settleDateTarget' in trade:
                if trade['settleDateTarget']:
                    settlement = int(datetime.strptime(trade['settleDateTarget'], "%Y%m%d").timestamp())
            number = trade['tradeID']
            qty = float(trade['quantity']) * float(trade['multiplier'])
            price = float(trade['tradePrice'])
            if 'ibCommission' in trade:
                fee = float(trade['ibCommission'])
            else:
                fee = float(trade['commisionsAndTax'])
        except KeyError as e:
            logging.error(g_tr('StatementLoader', "Failed to get field: ") + f"{e} / {trade}")
            return 0
        except ValueError as e:
            logging.error(g_tr('StatementLoader', "Import failure: ") + f"{e} / {trade}")
            return 0
        try:
            trade_action[type](account_id, asset_id, timestamp, settlement, number, qty, price, fee)
            return 1
        except KeyError:
            logging.error(g_tr('StatementLoader', "Trade action isn't implemented: ") + f"{trade['buySell']}")
            return 0

    def loadIBOptionEAE(self, option):
        try:
            account_id = self.findAccountID(option['accountId'], option['currency'])
            asset_id = self.findAssetID(option['symbol'])
            timestamp = int(datetime.strptime(option['date'], "%Y%m%d").timestamp())
            number = option['tradeID']
            qty = float(option['quantity']) * float(option['multiplier'])
            price = float(option['tradePrice'])
            fee = float(option['commisionsAndTax'])
        except KeyError as e:
            logging.error(g_tr('StatementLoader', "Failed to get field: ") + f"{e} / {option}")
            return 0
        except ValueError as e:
            logging.error(g_tr('StatementLoader', "Import failure: ") + f"{e} / {option}")
            return 0
        self.createTrade(account_id, asset_id, timestamp, timestamp, number, qty, price, fee)
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
        try:
            if trade['buySell'] == 'BUY':
                from_idx = 1
                to_idx = 0
                to_amount = float(trade['quantity'])  # positive value
                from_amount = float(trade['proceeds'])  # already negative value
            elif trade['buySell'] == 'SELL':
                from_idx = 0
                to_idx = 1
                from_amount = float(trade['quantity'])  # already negative value
                to_amount = float(trade['proceeds'])  # positive value
            else:
                logging.error(g_tr('StatementLoader', "Transaction type isn't implemented: ") + f"{trade['buySell']}")
                return 0
            currency = trade['symbol'].split('.')
            to_account = self.findAccountID(trade['accountId'], currency[to_idx])
            from_account = self.findAccountID(trade['accountId'], currency[from_idx])
            fee_account = self.findAccountID(trade['accountId'], trade['ibCommissionCurrency'])
            if to_account is None or from_account is None or fee_account is None:
                return 0
            timestamp = int(datetime.strptime(trade['dateTime'], "%Y%m%d;%H%M%S").timestamp())
            fee = float(trade['ibCommission'])  # already negative value
            note = trade['exchange']
        except KeyError as e:
            logging.error(g_tr('StatementLoader', "Failed to get field: ") + f"{e} / {trade}")
            return 0
        self.createTransfer(timestamp, from_account, from_amount, to_account, to_amount, fee_account, fee, note)
        return 1

    def createTransfer(self, timestamp, f_acc_id, f_amount, t_acc_id, t_amount, fee_acc_id, fee, note):
        transfer_id = readSQL(self.db,
                              "SELECT id FROM transfers_combined "
                              "WHERE from_timestamp=:timestamp AND from_acc_id=:from_acc_id AND to_acc_id=:to_acc_id",
                              [(":timestamp", timestamp), (":from_acc_id", f_acc_id), (":to_acc_id", t_acc_id)])
        if transfer_id:
            logging.info(g_tr('StatementLoader', "Currency exchange already exists: ") + f"{f_amount}->{t_amount}")
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
        try:
            account_id = self.findAccountID(dividend['accountId'], dividend['currency'])
            asset_id = self.findAssetID(dividend['symbol'])
            timestamp = int(datetime.strptime(dividend['dateTime'], "%Y%m%d;%H%M%S").timestamp())
            amount = float(dividend['amount'])
            note = dividend['description']
        except KeyError as e:
            logging.error(g_tr('StatementLoader', "Failed to get field: ") + f"{e} / {dividend}")
            return 0
        self.createDividend(timestamp, account_id, asset_id, amount, note)
        return 1

    def loadIBWithholdingTax(self, tax):
        try:
            account_id = self.findAccountID(tax['accountId'], tax['currency'])
            asset_id = self.findAssetID(tax['symbol'])
            timestamp = int(datetime.strptime(tax['dateTime'], "%Y%m%d;%H%M%S").timestamp())
            amount = -float(tax['amount'])
            note = tax['description']
        except KeyError as e:
            logging.error(g_tr('StatementLoader', "Failed to get field: ") + f"{e} / {tax}")
            return 0
        self.addWithholdingTax(timestamp, account_id, asset_id, amount, note)
        return 1

    def loadIBFee(self, fee):
        try:
            account_id = self.findAccountID(fee['accountId'], fee['currency'])
            bank_id = self.getAccountBank(account_id)
            timestamp = int(datetime.strptime(fee['dateTime'], "%Y%m%d;%H%M%S").timestamp())
            amount = float(fee['amount'])  # value may be both positive and negative
            note = fee['description']
        except KeyError as e:
            logging.error(g_tr('StatementLoader', "Failed to get field: ") + f"{e} / {fee}")
            return 0
        query = executeSQL(self.db,"INSERT INTO actions (timestamp, account_id, peer_id) "
                                   "VALUES (:timestamp, :account_id, :bank_id)",
                           [(":timestamp", timestamp), (":account_id", account_id), (":bank_id", bank_id)])
        pid = query.lastInsertId()
        _ = executeSQL(self.db, "INSERT INTO action_details (pid, category_id, sum, note) "
                                "VALUES (:pid, :category_id, :sum, :note)",
                       [(":pid", pid), (":category_id", PredefinedCategory.Fees), (":sum", amount), (":note", note)])
        self.db.commit()
        return 1

    def loadIBInterest(self, interest):
        try:
            account_id = self.findAccountID(interest['accountId'], interest['currency'])
            bank_id = self.getAccountBank(account_id)
            timestamp = int(datetime.strptime(interest['dateTime'], "%Y%m%d;%H%M%S").timestamp())
            amount = float(interest['amount'])  # value may be both positive and negative
            note = interest['description']
        except KeyError as e:
            logging.error(g_tr('StatementLoader', "Failed to get field: ") + f"{e} / {interest}")
            return 0
        query = executeSQL(self.db,"INSERT INTO actions (timestamp, account_id, peer_id) "
                                   "VALUES (:timestamp, :account_id, :bank_id)",
                           [(":timestamp", timestamp), (":account_id", account_id), (":bank_id", bank_id)])
        pid = query.lastInsertId()
        _ = executeSQL(self.db, "INSERT INTO action_details (pid, category_id, sum, note) "
                                "VALUES (:pid, :category_id, :sum, :note)",
                       [(":pid", pid), (":category_id", PredefinedCategory.Interest), (":sum", amount), (":note", note)])
        self.db.commit()
        return 1

    # noinspection PyMethodMayBeStatic
    def loadIBDepositWithdraw(self, cash):
        logging.warning(g_tr('StatementLoader', "*** MANUAL ENTRY REQUIRED ***"))
        logging.warning(g_tr('StatementLoader', "Deposit / Withdrawal: ") + f"{cash}")
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
            logging.warning(g_tr('StatementLoader', "New dummy country added with code ") + country_code)
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