import logging
import math
import re
from datetime import datetime

import pandas
from PySide2.QtCore import QObject, Signal
from PySide2.QtSql import QSqlTableModel
from PySide2.QtWidgets import QDialog, QFileDialog
from ibflex import parser, AssetClass, BuySell, CashAction, Reorg, Code
from constants import Setup, TransactionType, PredefinedAsset, PredefinedCategory
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
        AssetClass.STOCK: PredefinedAsset.Stock,
        AssetClass.BOND: PredefinedAsset.Bond
    }
    DummyExchange = "VALUE"


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
    if asset_id is not None:
        logging.info(g_tr('', "New asset with id ") + f"{asset_id}" + g_tr('', " was added: ") + f"{symbol} - '{name}'")
    else:
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
        self.ib_trade_loaders = {
            AssetClass.STOCK: self.loadIBStockTrade,
            AssetClass.CASH: self.loadIBCurrencyTrade
        }

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

    def loadIBFlex(self, filename):
        try:
            report = parser.parse(filename)
        except Exception as e:
            logging.error(g_tr('StatementLoader', "Failed to parse Interactive Brokers flex-report") + f": {e}")
            return False
        for statement in report.FlexStatements:
            self.loadIBStatement(statement)
        return True

    def loadIBStatement(self, IBstatement):
        logging.info(g_tr('StatementLoader', "Load IB Flex-statement for account ") + f"{IBstatement.accountId} " +
                     g_tr('StatementLoader', "from ") + f"{IBstatement.fromDate}" +
                     g_tr('StatementLoader', " to ") + f"{IBstatement.toDate}")

        for asset in IBstatement.SecuritiesInfo:
            if self.storeIBAsset(asset) is None:
                return False

        for trade in IBstatement.Trades:
            try:
                self.ib_trade_loaders[trade.assetCategory](trade)
            except:
                logging.error(g_tr('StatementLoader', "Load of ") + f"{trade.assetCategory}" +
                              g_tr('StatementLoader', " is not implemented. Skipping trade #") + f"{trade.tradeID}")

        for tax in IBstatement.TransactionTaxes:
            self.loadIBTransactionTax(tax)
            
        for corp_action in IBstatement.CorporateActions:
            self.loadIBCorpAction(corp_action)
            
        # 1st loop to load all dividends separately - to allow tax match in 2nd loop
        for cash_transaction in IBstatement.CashTransactions:
            if cash_transaction.type == CashAction.DIVIDEND:
                self.loadIBDividend(cash_transaction)
        for cash_transaction in IBstatement.CashTransactions:
            if cash_transaction.type == CashAction.WHTAX:
                self.loadIBWithholdingTax(cash_transaction)
            elif cash_transaction.type == CashAction.FEES:
                self.loadIBFee(cash_transaction)
            elif cash_transaction.type == CashAction.DEPOSITWITHDRAW:
                self.loadIBDepositWithdraw(cash_transaction)

    def storeIBAsset(self, IBasset):
        asset_id = readSQL(self.db, "SELECT id FROM assets WHERE name=:symbol", [(":symbol", IBasset.symbol)])
        if asset_id is not None:
            return asset_id
        try:
            asset_type = IBKR.AssetType[IBasset.assetCategory]
        except:
            logging.error(g_tr('StatementLoader', "Asset type ") + f"{IBasset.assetCategory}" +
                          g_tr('StatementLoader', " is not supported"))
            return None
        if IBasset.subCategory == "ETF":
            asset_type = PredefinedAsset.ETF
        return addNewAsset(self.db, IBasset.symbol, IBasset.description, asset_type, IBasset.isin)

    def loadIBStockTrade(self, trade):
        trade_action = {
            BuySell.BUY: self.createTrade,
            BuySell.SELL: self.createTrade,
            BuySell.CANCELBUY: self.deleteTrade,
            BuySell.CANCELSELL: self.deleteTrade
        }
        account_id = self.findAccountID(trade.accountId, trade.currency)
        if account_id is None:
            logging.error(g_tr('StatementLoader', "Account ") + f"{trade.accountId} ({trade.currency})" +
                          g_tr('StatementLoader', " not found. Skipping trade #") + f"{trade.tradeID}")
            return
        asset_id = self.findAssetID(trade.symbol)
        timestamp = int(trade.dateTime.timestamp())
        settlement = 0
        if trade.settleDateTarget:
            settlement = int(datetime.combine(trade.settleDateTarget, datetime.min.time()).timestamp())
        number = trade.tradeID if trade.tradeID else ""
        qty = trade.quantity
        price = trade.tradePrice
        fee = trade.ibCommission
        try:
            trade_action[trade.buySell](account_id, asset_id, timestamp, settlement, number, qty, price, fee)
        except:
            logging.error(g_tr('StatementLoader', "Trade type ") + f"{trade.buySell}" +
                          g_tr('StatementLoader', " is not implemented. Skipped trade #") + f"{number}")

    def createTrade(self, account_id, asset_id, timestamp, settlement, number, qty, price, fee, coupon=0.0):
        trade_id = readSQL(self.db,
                           "SELECT id FROM trades "
                           "WHERE timestamp=:timestamp AND asset_id = :asset "
                           "AND account_id = :account AND number = :number AND qty = :qty AND price = :price",
                           [(":timestamp", timestamp), (":asset", asset_id), (":account", account_id),
                            (":number", number), (":qty", qty), (":price", price)])
        if trade_id:
            logging.info(g_tr('StatementLoader', "Trade #") + f"{number}" +
                         g_tr('StatementLoader', " already exists in ledger. Skipped"))
            return

        _ = executeSQL(self.db,
                       "INSERT INTO trades (timestamp, settlement, corp_action_id, number, account_id, "
                       "asset_id, qty, price, fee, coupon) "
                       "VALUES (:timestamp, :settlement, 0, :number, :account, "
                       ":asset, :qty, :price, :fee, :coupon)",
                       [(":timestamp", timestamp), (":settlement", settlement), (":number", number),
                        (":account", account_id), (":asset", asset_id), (":qty", float(qty)),
                        (":price", float(price)), (":fee", -float(fee)), (":coupon", float(coupon))])
        self.db.commit()
        logging.info(f"Trade #{number} added for account {account_id} asset {asset_id} @{timestamp}: {qty}x{price}")

    def deleteTrade(self, account_id, asset_id, timestamp, _settlement, number, qty, price, _fee):
        _ = executeSQL(self.db, "DELETE FROM trades "
                                "WHERE timestamp=:timestamp AND asset_id=:asset "
                                "AND account_id=:account AND number=:number AND qty=:qty AND price=:price",
                       [(":timestamp", timestamp), (":asset", asset_id), (":account", account_id),
                        (":number", number), (":qty", -qty), (":price", price)])
        self.db.commit()
        logging.info(f"Trade #{number} cancelled for account {account_id} asset {asset_id} @{timestamp}: {qty}x{price}")

    def loadIBCurrencyTrade(self, trade):
        if trade.buySell == BuySell.BUY:
            from_idx = 1
            to_idx = 0
            to_amount = float(trade.quantity)  # positive value
            from_amount = float(trade.proceeds)  # already negative value
        elif trade.buySell == BuySell.SELL:
            from_idx = 0
            to_idx = 1
            from_amount = float(trade.quantity)  # already negative value
            to_amount = float(trade.proceeds)  # positive value
        else:
            logging.error(g_tr('StatementLoader', "Currency transaction of type ") + f"{trade.buySell}" +
                          g_tr('StatementLoader', " is not implemented"))
            return
        currency = trade.symbol.split('.')
        to_account = self.findAccountID(trade.accountId, currency[to_idx])
        from_account = self.findAccountID(trade.accountId, currency[from_idx])
        fee_account = self.findAccountID(trade.accountId, trade.ibCommissionCurrency)
        if to_account is None or from_account is None or fee_account is None:
            logging.error(g_tr('StatementLoader', "Account ") + f"{trade.accountId} ({currency[to_idx]})" +
                          g_tr('StatementLoader', "not found. Currency transaction #") + f"{trade.tradeID}" +
                          g_tr('StatementLoader', " skipped"))
            return
        timestamp = int(trade.dateTime.timestamp())
        fee = float(trade.ibCommission)  # already negative value
        note = trade.exchange
        self.createTransfer(timestamp, from_account, from_amount, to_account, to_amount, fee_account, fee, note)

    def createTransfer(self, timestamp, f_acc_id, f_amount, t_acc_id, t_amount, fee_acc_id, fee, note):
        transfer_id = readSQL(self.db,
                              "SELECT id FROM transfers_combined "
                              "WHERE from_timestamp=:timestamp AND from_acc_id=:from_acc_id AND to_acc_id=:to_acc_id",
                              [(":timestamp", timestamp), (":from_acc_id", f_acc_id), (":to_acc_id", t_acc_id)])
        if transfer_id:
            logging.info(f"Currency exchange {f_amount}->{t_amount} already exists in ledger. Skipped")
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
        logging.info(g_tr('StatementLoader', "Currency exchange ") + f"{f_amount}->{t_amount}" +
                     g_tr('StatementLoader', " added"))

    def loadIBTransactionTax(self, IBtax):
        account_id = self.findAccountID(IBtax.accountId, IBtax.currency)
        if account_id is None:
            logging.error(g_tr('StatementLoader', "Account ") + f"{IBtax.accountId} ({IBtax.currency})" +
                          g_tr('StatementLoader', " not found. Tax #") + f"{IBtax.tradeID}" +
                          g_tr('StatementLoader', " skipped"))
            return
        timestamp = int(datetime.combine(IBtax.date, datetime.min.time()).timestamp())
        amount = float(IBtax.taxAmount)  # value is negative already
        note = f"{IBtax.symbol} ({IBtax.description}) - {IBtax.taxDescription} (#{IBtax.tradeId})"

        id = readSQL(self.db, "SELECT id FROM all_operations WHERE type = :type "
                              "AND timestamp=:timestamp AND account_id=:account_id AND amount=:amount",
                     [(":timestamp", timestamp), (":type", TransactionType.Action),
                      (":account_id", account_id), (":amount", amount)])
        if id:
            logging.warning(g_tr('StatementLoader', "Tax transaction #") + f"{IBtax.tradeId}" +
                            g_tr('StatementLoader', " already exists"))
            return
        query = executeSQL(self.db,
                           "INSERT INTO actions (timestamp, account_id, peer_id) VALUES "
                           "(:timestamp, :account_id, (SELECT organization_id FROM accounts WHERE id=:account_id))",
                           [(":timestamp", timestamp), (":account_id", account_id)])
        pid = query.lastInsertId()
        _ = executeSQL(self.db, "INSERT INTO action_details (pid, category_id, sum, note) "
                                "VALUES (:pid, :category_id, :sum, :note)",
                       [(":pid", pid), (":category_id", PredefinedCategory.Taxes), (":sum", amount), (":note", note)])
        self.db.commit()
        logging.info(g_tr('StatementLoader', "Transaction tax added: ") + f"{note}, {amount}")

    def loadIBCorpAction(self, IBCorpAction):
        if IBCorpAction.listingExchange == IBKR.DummyExchange:   # Skip artificial corporate actions
            return
        if IBCorpAction.code == Code.CANCEL:
            logging.warning(g_tr('StatementLoader', "*** MANUAL ACTION REQUIRED ***"))
            logging.warning(f"Corporate action cancelled {IBCorpAction.type} for account "
                            f"{IBCorpAction.accountId} ({IBCorpAction.currency}): {IBCorpAction.actionDescription}")
            logging.warning(f"@{IBCorpAction.dateTime} for {IBCorpAction.symbol}: Qty {IBCorpAction.quantity}, "
                            f"Value {IBCorpAction.value}, Type {IBCorpAction.type}, Code {IBCorpAction.code}")
            return
        if IBCorpAction.assetCategory == AssetClass.STOCK and (
                IBCorpAction.type == Reorg.MERGER or IBCorpAction.type == Reorg.SPINOFF):
            account_id = self.findAccountID(IBCorpAction.accountId, IBCorpAction.currency)
            if account_id is None:
                logging.error(g_tr('StatementLoader', "Account ") + f"{IBCorpAction.accountId} ({IBCorpAction.currency})" +
                              g_tr('StatementLoader', " not found. Skipping trade #") + f"{IBCorpAction.transactionID}")
                return
            asset_id = self.findAssetID(IBCorpAction.symbol)
            timestamp = int(IBCorpAction.dateTime.timestamp())
            settlement = timestamp
            if IBCorpAction.transactionID:
                number = IBCorpAction.transactionID
            else:
                number = ""
            qty = IBCorpAction.quantity
            self.createTrade(account_id, asset_id, timestamp, settlement, number, qty, 0, 0)
            return
        logging.warning(g_tr('StatementLoader', "*** MANUAL ACTION REQUIRED ***"))
        logging.warning(f"Corporate action {IBCorpAction.type} for account "
                        f"{IBCorpAction.accountId} ({IBCorpAction.currency}): {IBCorpAction.actionDescription}")
        logging.warning(f"@{IBCorpAction.dateTime} for {IBCorpAction.symbol}: Qty {IBCorpAction.quantity}, "
                        f"Value {IBCorpAction.value}, Type {IBCorpAction.type}, Code {IBCorpAction.code}")

    def loadIBDividend(self, dividend):
        if dividend.assetCategory != AssetClass.STOCK:
            logging.error(g_tr('StatementLoader', "Dividend for ") + f"{dividend.assetCategory}" +
                          g_tr('StatementLoader', " not implemented"))
            return
        account_id = self.findAccountID(dividend.accountId, dividend.currency)
        if account_id is None:
            logging.error(g_tr('StatementLoader', "Account ") + f"{dividend.accountId} ({dividend.currency})" +
                          g_tr('StatementLoader', " not found. Skipping dividend #") + f"{dividend.transactionID}")
            return
        asset_id = self.findAssetID(dividend.symbol)
        timestamp = int(dividend.dateTime.timestamp())
        amount = float(dividend.amount)
        note = dividend.description
        self.createDividend(timestamp, account_id, asset_id, amount, note)

    def loadIBWithholdingTax(self, tax):
        if tax.assetCategory != AssetClass.STOCK:
            logging.error(g_tr('StatementLoader', "Withholding tax for ") + f"{tax.assetCategory}" +
                          g_tr('StatementLoader', " not implemented"))
            return
        account_id = self.findAccountID(tax.accountId, tax.currency)
        if account_id is None:
            logging.error(g_tr('StatementLoader', "Account ") + f"{tax.accountId} ({tax.currency})" +
                          g_tr('StatementLoader', " not found. Skipping tax #") + f"{tax.transactionID}")
            return
        asset_id = self.findAssetID(tax.symbol)
        timestamp = int(tax.dateTime.timestamp())
        amount = float(tax.amount)
        note = tax.description
        self.addWithholdingTax(timestamp, account_id, asset_id, amount, note)

    def loadIBFee(self, fee):
        account_id = self.findAccountID(fee.accountId, fee.currency)
        if account_id is None:
            logging.error(g_tr('StatementLoader', "Account ") + f"{fee.accountId} ({fee.currency})" +
                          g_tr('StatementLoader', " not found. Skipping fee #") + f"{fee.transactionID}")
            return
        timestamp = int(fee.dateTime.timestamp())
        amount = float(fee.amount)  # value may be both positive and negative
        note = fee.description
        query = executeSQL(self.db,"INSERT INTO actions (timestamp, account_id, peer_id) VALUES "
                               "(:timestamp, :account_id, (SELECT organization_id FROM accounts WHERE id=:account_id))",
                       [(":timestamp", timestamp), (":account_id", account_id)])
        pid = query.lastInsertId()
        _ = executeSQL(self.db, "INSERT INTO action_details (pid, category_id, sum, note) "
                                "VALUES (:pid, :category_id, :sum, :note)",
                       [(":pid", pid), (":category_id", PredefinedCategory.Fees), (":sum", amount), (":note", note)])
        self.db.commit()
        logging.info(g_tr('StatementLoader', "Fee added: ") + f"{note}, {amount}")

    # noinspection PyMethodMayBeStatic
    def loadIBDepositWithdraw(self, cash):
        logging.warning(g_tr('StatementLoader', "*** MANUAL ENTRY REQUIRED ***"))
        logging.warning(f"{cash.dateTime} {cash.description}: {cash.accountId} {cash.amount} {cash.currency}")

    def createDividend(self, timestamp, account_id, asset_id, amount, note):
        id = readSQL(self.db, "SELECT id FROM dividends WHERE timestamp=:timestamp "
                              "AND account_id=:account_id AND asset_id=:asset_id AND note=:note",
                     [(":timestamp", timestamp), (":account_id", account_id), (":asset_id", asset_id), (":note", note)])
        if id:
            logging.warning(g_tr('StatementLoader', "Dividend already exists: ") + f"{note}")
            return
        _ = executeSQL(self.db, "INSERT INTO dividends (timestamp, account_id, asset_id, sum, note) "
                                "VALUES (:timestamp, :account_id, :asset_id, :sum, :note)",
                       [(":timestamp", timestamp), (":account_id", account_id), (":asset_id", asset_id),
                        (":sum", amount), (":note", note)])
        self.db.commit()
        logging.info(g_tr('StatementLoader', "Dividend added: ") + f"{note}")

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
        logging.info(g_tr('StatementLoader', "Withholding tax added: ") + f"{note}")

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