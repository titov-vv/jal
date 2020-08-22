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
from DB.helpers import executeSQL, readSQL
from UI.ui_add_asset_dlg import Ui_AddAssetDialog


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
    FeeEx1 = 'Комиссия за ИТС'
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
        logging.info(f"New asset with id {asset_id} was added: {symbol} - '{name}'")
    else:
        logging.error(f"Failed to add new asset: {symbol}")
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
            QFileDialog.getOpenFileName(None, "Select statement file to import", ".",
                                        f"{ReportType.IBKR};;{ReportType.Quik}")
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
        except:
            logging.error("Failed to parse Interactive Brokers flex-report")
            return False
        for statement in report.FlexStatements:
            self.loadIBStatement(statement)
        return True

    def loadIBStatement(self, IBstatement):
        logging.info(f"Load IB Flex-statement for account {IBstatement.accountId} "
                     f"from {IBstatement.fromDate} to {IBstatement.toDate}")

        for asset in IBstatement.SecuritiesInfo:
            if self.storeIBAsset(asset) is None:
                return False

        for trade in IBstatement.Trades:
            try:
                self.ib_trade_loaders[trade.assetCategory](trade)
            except:
                logging.error(f"Load of {trade.assetCategory} is not implemented. Skipping trade #{trade.tradeID}")

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
            logging.error(f"Asset type {IBasset.assetCategory} is not supported")
            return None
        if IBasset.subCategory == "ETF":
            asset_type = PredefinedAsset.ETF
        return addNewAsset(IBasset.symbol, IBasset.description, asset_type, IBasset.isin)

    def loadIBStockTrade(self, trade):
        trade_action = {
            BuySell.BUY: self.createTrade,
            BuySell.SELL: self.createTrade,
            BuySell.CANCELBUY: self.deleteTrade,
            BuySell.CANCELSELL: self.deleteTrade
        }
        account_id = self.findAccountID(trade.accountId, trade.currency)
        if account_id is None:
            logging.error(f"Account {trade.accountId} ({trade.currency}) not found. Skipping trade #{trade.tradeID}")
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
            logging.error(f"Trade type f{trade.buySell} is not implemented. Skipped trade #{number}")

    def createTrade(self, account_id, asset_id, timestamp, settlement, number, qty, price, fee, coupon=0.0):
        trade_id = readSQL(self.db,
                           "SELECT id FROM trades "
                           "WHERE timestamp=:timestamp AND asset_id = :asset "
                           "AND account_id = :account AND number = :number AND qty = :qty AND price = :price",
                           [(":timestamp", timestamp), (":asset", asset_id), (":account", account_id),
                            (":number", number), (":qty", qty), (":price", price)])
        if trade_id:
            logging.info(f"Trade #{number} already exists in ledger. Skipped")
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
            logging.error(f"Currency transaction of type {trade.buySell} is not implemented")
            return
        currency = trade.symbol.split('.')
        to_account = self.findAccountID(trade.accountId, currency[to_idx])
        from_account = self.findAccountID(trade.accountId, currency[from_idx])
        fee_account = self.findAccountID(trade.accountId, trade.ibCommissionCurrency)
        if to_account is None or from_account is None or fee_account is None:
            logging.error(f"Account {trade.accountId} ({currency[to_idx]}) not found. "
                          f"Currency transaction #{trade.tradeID} skipped")
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
        logging.info(f"Currency exchange {f_amount}->{t_amount} added")

    def loadIBTransactionTax(self, IBtax):
        account_id = self.findAccountID(IBtax.accountId, IBtax.currency)
        if account_id is None:
            logging.error(f"Account {IBtax.accountId} ({IBtax.currency}) not found. Tax #{IBtax.tradeID} skipped")
            return
        timestamp = int(datetime.combine(IBtax.date, datetime.min.time()).timestamp())
        amount = float(IBtax.taxAmount)  # value is negative already
        note = f"{IBtax.symbol} ({IBtax.description}) - {IBtax.taxDescription} (#{IBtax.tradeId})"

        id = readSQL(self.db, "SELECT id FROM all_operations WHERE type = :type "
                              "AND timestamp=:timestamp AND account_id=:account_id AND amount=:amount",
                     [(":timestamp", timestamp), (":type", TransactionType.Action),
                      (":account_id", account_id), (":amount", amount)])
        if id:
            logging.warning(f"Tax transaction #{IBtax.tradeId} already exists")
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
        logging.info(f"Transaction tax added: {note}, {amount}")

    def loadIBCorpAction(self, IBCorpAction):
        if IBCorpAction.code == Code.CANCEL:
            logging.warning("*** MANUAL ACTION REQUIRED ***")
            logging.warning(f"Corporate action cancelled {IBCorpAction.type} for account "
                            f"{IBCorpAction.accountId} ({IBCorpAction.currency}): {IBCorpAction.actionDescription}")
            logging.warning(f"@{IBCorpAction.dateTime} for {IBCorpAction.symbol}: Qty {IBCorpAction.quantity}, "
                            f"Value {IBCorpAction.value}, Type {IBCorpAction.type}, Code {IBCorpAction.code}")
            return
        if IBCorpAction.assetCategory == AssetClass.STOCK and (
                IBCorpAction.type == Reorg.MERGER or IBCorpAction.type == Reorg.SPINOFF):
            account_id = self.findAccountID(IBCorpAction.accountId, IBCorpAction.currency)
            if account_id is None:
                logging.error(f"Account {IBCorpAction.accountId} ({IBCorpAction.currency}) not found. "
                              f"Skipping trade #{IBCorpAction.transactionID}")
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
        logging.warning("*** MANUAL ACTION REQUIRED ***")
        logging.warning(f"Corporate action {IBCorpAction.type} for account "
                        f"{IBCorpAction.accountId} ({IBCorpAction.currency}): {IBCorpAction.actionDescription}")
        logging.warning(f"@{IBCorpAction.dateTime} for {IBCorpAction.symbol}: Qty {IBCorpAction.quantity}, "
                        f"Value {IBCorpAction.value}, Type {IBCorpAction.type}, Code {IBCorpAction.code}")

    def loadIBDividend(self, dividend):
        if dividend.assetCategory != AssetClass.STOCK:
            logging.error(f"Dividend for {dividend.assetCategory} not implemented")
            return
        account_id = self.findAccountID(dividend.accountId, dividend.currency)
        if account_id is None:
            logging.error(f"Account {dividend.accountId} ({dividend.currency}) not found. "
                          f"Skipping dividend #{dividend.transactionID}")
            return
        asset_id = self.findAssetID(dividend.symbol)
        timestamp = int(dividend.dateTime.timestamp())
        amount = float(dividend.amount)
        note = dividend.description
        self.createDividend(timestamp, account_id, asset_id, amount, note)

    def loadIBWithholdingTax(self, tax):
        if tax.assetCategory != AssetClass.STOCK:
            logging.error(f"Withholding tax for {tax.assetCategory} not implemented")
            return
        account_id = self.findAccountID(tax.accountId, tax.currency)
        if account_id is None:
            logging.error(f"Account {tax.accountId} ({tax.currency}) not found. Tax #{tax.transactionID} skipped")
            return
        asset_id = self.findAssetID(tax.symbol)
        timestamp = int(tax.dateTime.timestamp())
        amount = float(tax.amount)
        note = tax.description
        self.addWithholdingTax(timestamp, account_id, asset_id, amount, note)

    def loadIBFee(self, fee):
        account_id = self.findAccountID(fee.accountId, fee.currency)
        if account_id is None:
            logging.error(f"Account {fee.accountId} ({fee.currency}) not found. Fax #{fee.transactionID} skipped")
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
        logging.info(f"Fees added: {note}, {amount}")

    # noinspection PyMethodMayBeStatic
    def loadIBDepositWithdraw(self, cash):
        logging.warning("*** MANUAL ENTRY REQUIRED ***")
        logging.warning(f"{cash.dateTime} {cash.description}: {cash.accountId} {cash.amount} {cash.currency}")

    def createDividend(self, timestamp, account_id, asset_id, amount, note):
        id = readSQL(self.db, "SELECT id FROM dividends WHERE timestamp=:timestamp "
                              "AND account_id=:account_id AND asset_id=:asset_id AND note=:note",
                     [(":timestamp", timestamp), (":account_id", account_id), (":asset_id", asset_id), (":note", note)])
        if id:
            logging.warning(f"Dividend already exists: {note}")
            return
        _ = executeSQL(self.db, "INSERT INTO dividends (timestamp, account_id, asset_id, sum, note) "
                                "VALUES (:timestamp, :account_id, :asset_id, :sum, :note)",
                       [(":timestamp", timestamp), (":account_id", account_id), (":asset_id", asset_id),
                        (":sum", amount), (":note", note)])
        self.db.commit()
        logging.info(f"Dividend added: {note}")

    def addWithholdingTax(self, timestamp, account_id, asset_id, amount, note):
        parts = re.match(IBKR.TaxNotePattern, note)
        if not parts:
            logging.warning("*** MANUAL ENTRY REQUIRED ***")
            logging.warning(f"Unhandled tax pattern found: {note}")
            return
        dividend_note = parts.group(1) + '%'
        country_code = parts.group(2)
        try:
            dividend_id, old_tax = readSQL(self.db,
                                           "SELECT id, sum_tax FROM dividends "
                                           "WHERE timestamp=:timestamp AND account_id=:account_id "
                                           "AND asset_id=:asset_id AND note LIKE :dividend_description",
                                           [(":timestamp", timestamp), (":account_id", account_id),
                                            (":asset_id", asset_id), (":dividend_description", dividend_note)])
        except:
            logging.warning(f"Dividend not found for withholding tax: {note}")
            return
        _ = executeSQL(self.db, "UPDATE dividends SET sum_tax=:tax, note_tax=:note WHERE id=:dividend_id",
                       [(":dividend_id", dividend_id), (":tax", old_tax + amount), (":note", country_code + " tax")])
        self.db.commit()
        logging.info(f"Withholding tax added: {note}")

    def loadQuikHtml(self, filename):
        try:
            data = pandas.read_html(filename, encoding='cp1251',
                                    converters={Quik.Qty: convert_amount, Quik.Amount: convert_amount,
                                                Quik.Price: convert_amount, Quik.Coupon: convert_amount})
        except:
            logging.error("Can't read statement file")
            return False

        report_info = data[0]
        deals_info = data[1]
        parts = re.match(Quik.ClientPattern, report_info[0][2])
        if parts:
            account_id = self.findAccountID(parts.group(1))
        else:
            logging.error("Can't get account number from the statement.")
            return False
        if account_id is None:
            logging.error(f"Account with number {parts.group(1)} not found. Import cancelled.")
            return False

        for index, row in deals_info.iterrows():
            if row[Quik.Type] == Quik.Buy:
                qty = int(row[Quik.Qty])
            elif row[Quik.Type] == Quik.Sell:
                qty = -int(row[Quik.Qty])
            elif row[Quik.Type] == Quik.Total:
                break   # End of statement reached
            else:
                logging.warning(f"Unknown operation type {row[Quik.Type]}. Skipped.")
                continue
            asset_id = self.findAssetID(row[Quik.Symbol])
            if asset_id is None:
                logging.warning(f"Unknown asset {row[Quik.Symbol]}. Skipped.")
                continue
            timestamp = int(datetime.strptime(row[Quik.DateTime], "%d.%m.%Y %H:%M:%S").timestamp())
            settlement = int(datetime.strptime(row[Quik.SettleDate], "%d.%m.%Y").timestamp())
            number = row[Quik.TradeNumber]
            price = row[Quik.Price]
            amount = row[Quik.Amount]
            lot_size = math.pow(10, round(math.log10(amount / (price * abs(qty)))))
            qty = qty * lot_size
            fee = float(row[Quik.Fee]) + float(row[Quik.FeeEx1]) + float(row[Quik.FeeEx2]) + float(row[Quik.FeeEx3])
            coupon = float(row[Quik.Coupon])
            self.createTrade(account_id, asset_id, timestamp, settlement, number, qty, price, -fee, coupon)
        return True