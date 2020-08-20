import logging
import math
import re
from datetime import datetime

import pandas
from PySide2.QtCore import QObject, Signal
from PySide2.QtSql import QSqlQuery, QSqlTableModel
from PySide2.QtWidgets import QDialog, QFileDialog
from ibflex import parser, AssetClass, BuySell, CashAction, Reorg, Code
from constants import Setup, TransactionType, PredefinedAsset, PredefinedCategory
from DB.helpers import executeSQL, readSQL
from UI.add_asset_dlg import Ui_AddAssetDialog


#-----------------------------------------------------------------------------------------------------------------------
class ReportType:
    IBKR = 'IBKR flex-query (*.xml)'
    Quik = 'Quik HTML-report (*.htm)'


#-----------------------------------------------------------------------------------------------------------------------
class IBKR:
    TaxNotePattern = "^(.*) - (..) TAX$"
    

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

    def loadReport(self):
        report_file, active_filter = \
            QFileDialog.getOpenFileName(None, "Select statement file to import", ".",
                                        f"{ReportType.IBKR};;{ReportType.Quik}")
        if report_file:
            if active_filter == ReportType.IBKR:
                self.loadIBFlex(report_file)
            if active_filter == ReportType.Quik:
                if self.loadQuikHtml(report_file):
                    self.load_completed.emit()
                else:
                    self.load_failed.emit()

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
        report = parser.parse(filename)
        for statement in report.FlexStatements:
            self.loadIBStatement(statement)

    def loadIBStatement(self, IBstatement):
        logging.info(f"Load IB Flex-statement for account {IBstatement.accountId} "
                     f"from {IBstatement.fromDate} to {IBstatement.toDate}")

        for asset in IBstatement.SecuritiesInfo:
            self.storeIBAsset(asset)
        for trade in IBstatement.Trades:
            self.loadIBTrade(trade)
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
        query = QSqlQuery(self.db)
        query.prepare("SELECT id FROM assets WHERE name=:symbol")
        query.bindValue(":symbol", IBasset.symbol)
        assert query.exec_()
        if query.next():
            return  # Asset already present in DB

        if IBasset.assetCategory == AssetClass.STOCK:
            asset_type = PredefinedAsset.Stock
            if IBasset.subCategory == "ETF":
                asset_type = PredefinedAsset.ETF
        elif IBasset.assetCategory == AssetClass.BOND:
            asset_type = PredefinedAsset.Bond
        else:
            logging.error(f"Unknown asset type {IBasset}")
            return
        addNewAsset(IBasset.symbol, IBasset.description, asset_type, IBasset.isin)
        # query.prepare("INSERT INTO assets(name, type_id, full_name, isin) VALUES(:symbol, :type, :full_name, :isin)")
        # query.bindValue(":symbol", IBasset.symbol)
        # query.bindValue(":type", asset_type)
        # query.bindValue(":full_name", IBasset.description)
        # query.bindValue(":isin", IBasset.isin)
        # assert query.exec_()
        # logging.info(f"Asset added: {IBasset.symbol}")

    def loadIBTrade(self, IBtrade):
        if IBtrade.assetCategory == AssetClass.STOCK:
            self.loadIBStockTrade(IBtrade)
        elif IBtrade.assetCategory == AssetClass.CASH:
            self.loadIBCurrencyTrade(IBtrade)
        else:
            logging.error(f"Load of {IBtrade.assetCategory} is not implemented. Skipping trade #{IBtrade.tradeID}")

    def loadIBStockTrade(self, IBtrade):
        account_id = self.findAccountID(IBtrade.accountId, IBtrade.currency)
        if account_id is None:
            logging.error(
                f"Account {IBtrade.accountId} ({IBtrade.currency}) not found. Skipping trade #{IBtrade.tradeID}")
            return
        asset_id = self.findAssetID(IBtrade.symbol)
        timestamp = int(IBtrade.dateTime.timestamp())
        if IBtrade.settleDateTarget:
            settlement = int(datetime.combine(IBtrade.settleDateTarget, datetime.min.time()).timestamp())
        else:
            settlement = timestamp
        if IBtrade.tradeID:
            number = IBtrade.tradeID
        else:
            number = ""
        qty = IBtrade.quantity
        price = IBtrade.tradePrice
        fee = IBtrade.ibCommission
        if IBtrade.buySell == BuySell.BUY or IBtrade.buySell == BuySell.SELL:
            self.createTrade(account_id, asset_id, timestamp, settlement, number, qty, price, fee)
        elif IBtrade.buySell == BuySell.CANCELBUY or IBtrade.buySell == BuySell.CANCELSELL:
            self.deleteTrade(account_id, asset_id, timestamp, number, qty, price)
        else:
            logging.error(f"Trade type f{IBtrade.buySell} is not implemented")

    def createTrade(self, account_id, asset_id, timestamp, settlement, number, qty, price, fee, coupon=0.0):
        trade_id = readSQL(self.db,
                           "SELECT id FROM trades "
                           "WHERE timestamp=:timestamp AND asset_id = :asset "
                           "AND account_id = :account AND number = :number AND qty = :qty AND price = :price",
                           [(":timestamp", timestamp), (":asset", asset_id), (":account", account_id),
                            (":number", number), (":qty", qty), (":price", price)])
        if trade_id:
            logging.warning(f"Trade #{number} already exists in ledger. Skipped")
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

    def deleteTrade(self, account_id, asset_id, timestamp, number, qty, price):
        query = QSqlQuery(self.db)
        query.prepare("DELETE FROM trades "
                      "WHERE timestamp=:timestamp AND asset_id=:asset "
                      "AND account_id=:account AND number=:number AND qty=:qty AND price=:price")
        query.bindValue(":timestamp", timestamp)
        query.bindValue(":asset", asset_id)
        query.bindValue(":account", account_id)
        query.bindValue(":number", number)
        query.bindValue(":qty", -qty)
        query.bindValue(":price", price)
        assert query.exec_()
        self.db.commit()
        logging.info(
            f"Trade #{number} cancelled for account {account_id} asset {asset_id} @{timestamp}, Qty {qty}x{price}")

    def loadIBCurrencyTrade(self, IBtrade):
        if IBtrade.buySell == BuySell.BUY:
            from_idx = 1
            to_idx = 0
            to_amount = float(IBtrade.quantity)  # positive value
            from_amount = float(IBtrade.proceeds)  # already negative value
        elif IBtrade.buySell == BuySell.SELL:
            from_idx = 0
            to_idx = 1
            from_amount = float(IBtrade.quantity)  # already negative value
            to_amount = float(IBtrade.proceeds)  # positive value
        else:
            logging.error(f"Currency transaction of type {IBtrade.buySell} is not implemented")
            return
        currency = IBtrade.symbol.split('.')
        to_account_id = self.findAccountID(IBtrade.accountId, currency[to_idx])
        if to_account_id is None:
            logging.error(f"Account {IBtrade.accountId} ({currency[to_idx]}) not found. "
                          f"Skipping currency exchange transaction #{IBtrade.tradeID}")
            return
        from_account_id = self.findAccountID(IBtrade.accountId, currency[from_idx])
        if from_account_id is None:
            logging.error(f"Account {IBtrade.accountId} ({currency[from_idx]}) not found. "
                          f"Skipping currency exchange transaction #{IBtrade.tradeID}")
            return
        fee_account_id = self.findAccountID(IBtrade.accountId, IBtrade.ibCommissionCurrency)
        if fee_account_id is None:
            logging.error(f"Account {IBtrade.accountId} ({IBtrade.ibCommissionCurrency}) not found. "
                          f"Skipping currency exchange transaction #{IBtrade.tradeID}")
            return
        timestamp = int(IBtrade.dateTime.timestamp())
        fee = float(IBtrade.ibCommission)  # already negative value
        note = IBtrade.exchange
        self.createTransfer(timestamp, from_account_id, from_amount, to_account_id, to_amount, fee_account_id, fee,
                            note)

    def createTransfer(self, timestamp, f_acc_id, f_amount, t_acc_id, t_amount, fee_acc_id, fee, note):
        query = QSqlQuery(self.db)
        query.prepare("SELECT id FROM transfers_combined "
                      "WHERE from_timestamp=:timestamp AND from_acc_id=:from_acc_id AND to_acc_id=:to_acc_id")
        query.bindValue(":timestamp", timestamp)
        query.bindValue(":from_acc_id", f_acc_id)
        query.bindValue(":to_acc_id", t_acc_id)
        assert query.exec_()
        if query.next():
            logging.warning(f"Currency exchange {f_amount}->{t_amount} already exists")
            return
        if abs(fee) > Setup.CALC_TOLERANCE:
            query.prepare("INSERT INTO transfers_combined (from_timestamp, from_acc_id, from_amount, "
                          "to_timestamp, to_acc_id, to_amount, fee_timestamp, fee_acc_id, fee_amount, note) "
                          "VALUES (:timestamp, :f_acc_id, :f_amount, :timestamp, :t_acc_id, :t_amount, "
                          ":timestamp, :fee_acc_id, :fee_amount, :note)")
            query.bindValue(":fee_acc_id", fee_acc_id)
            query.bindValue(":fee_amount", fee)
        else:
            query.prepare("INSERT INTO transfers_combined (from_timestamp, from_acc_id, from_amount, "
                          "to_timestamp, to_acc_id, to_amount, note) "
                          "VALUES (:timestamp, :f_acc_id, :f_amount, :timestamp, :t_acc_id, :t_amount, :note)")
        query.bindValue(":timestamp", timestamp)
        query.bindValue(":f_acc_id", f_acc_id)
        query.bindValue(":t_acc_id", t_acc_id)
        query.bindValue(":f_amount", f_amount)
        query.bindValue(":t_amount", t_amount)
        query.bindValue(":note", note)
        assert query.exec_()
        self.db.commit()
        logging.info(f"Currency exchange {f_amount}->{t_amount} added @{timestamp}")

    def loadIBTransactionTax(self, IBtax):
        account_id = self.findAccountID(IBtax.accountId, IBtax.currency)
        if account_id is None:
            logging.error(
                f"Account {IBtax.accountId} ({IBtax.currency}) not found. Skipping transaction tax #{IBtax.tradeID}")
            return
        timestamp = int(datetime.combine(IBtax.date, datetime.min.time()).timestamp())
        amount = float(IBtax.taxAmount)  # value is negative already
        note = f"{IBtax.symbol} ({IBtax.description}) - {IBtax.taxDescription} (#{IBtax.tradeId})"

        query = QSqlQuery(self.db)
        query.prepare("SELECT id FROM all_operations "
                      "WHERE type = :type AND timestamp=:timestamp AND account_id=:account_id AND amount=:amount")
        query.bindValue(":timestamp", timestamp)
        query.bindValue(":type", TransactionType.Action)
        query.bindValue(":account_id", account_id)
        query.bindValue(":amount", amount)
        assert query.exec_()
        if query.next():
            logging.warning(f"Tax transaction #{IBtax.tradeId} already exists")
            return
        query.prepare("INSERT INTO actions (timestamp, account_id, peer_id) "
                      "VALUES (:timestamp, :account_id, (SELECT organization_id FROM accounts WHERE id=:account_id))")
        query.bindValue(":timestamp", timestamp)
        query.bindValue(":account_id", account_id)
        assert query.exec_()
        pid = query.lastInsertId()
        query.prepare("INSERT INTO action_details (pid, category_id, sum, note) "
                      "VALUES (:pid, :category_id, :sum, :note)")
        query.bindValue(":pid", pid)
        query.bindValue(":category_id", PredefinedCategory.Taxes)
        query.bindValue(":sum", amount)
        query.bindValue(":note", note)
        assert query.exec_()
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

    def loadIBDividend(self, IBdividend):
        if IBdividend.assetCategory != AssetClass.STOCK:
            logging.error(f"Dividend for {IBdividend.assetCategory} not implemented")
            return
        account_id = self.findAccountID(IBdividend.accountId, IBdividend.currency)
        if account_id is None:
            logging.error(f"Account {IBdividend.accountId} ({IBdividend.currency}) not found. "
                          f"Skipping dividend #{IBdividend.transactionID}")
            return
        asset_id = self.findAssetID(IBdividend.symbol)
        timestamp = int(IBdividend.dateTime.timestamp())
        amount = float(IBdividend.amount)
        note = IBdividend.description
        self.createDividend(timestamp, account_id, asset_id, amount, note)

    def loadIBWithholdingTax(self, IBtax):
        if IBtax.assetCategory != AssetClass.STOCK:
            logging.error(f"Withholding tax for {IBtax.assetCategory} not implemented")
            return
        account_id = self.findAccountID(IBtax.accountId, IBtax.currency)
        if account_id is None:
            logging.error(f"Account {IBtax.accountId} ({IBtax.currency}) not found. "
                          f"Skipping withholding tax #{IBtax.transactionID}")
            return
        asset_id = self.findAssetID(IBtax.symbol)
        timestamp = int(IBtax.dateTime.timestamp())
        amount = float(IBtax.amount)
        note = IBtax.description
        self.addWithholdingTax(timestamp, account_id, asset_id, amount, note)

    def loadIBFee(self, IBfee):
        account_id = self.findAccountID(IBfee.accountId, IBfee.currency)
        if account_id is None:
            logging.error(f"Account {IBfee.accountId} ({IBfee.currency}) not found. "
                          f"Skipping transaction tax #{IBfee.transactionID}")
            return
        timestamp = int(IBfee.dateTime.timestamp())
        amount = float(IBfee.amount)  # value may be both positive and negative
        note = IBfee.description
        query = QSqlQuery(self.db)
        query.prepare("INSERT INTO actions (timestamp, account_id, peer_id) "
                      "VALUES (:timestamp, :account_id, (SELECT organization_id FROM accounts WHERE id=:account_id))")
        query.bindValue(":timestamp", timestamp)
        query.bindValue(":account_id", account_id)
        assert query.exec_()
        pid = query.lastInsertId()
        query.prepare("INSERT INTO action_details (pid, category_id, sum, note) "
                      "VALUES (:pid, :category_id, :sum, :note)")
        query.bindValue(":pid", pid)
        query.bindValue(":category_id", PredefinedCategory.Fees)
        query.bindValue(":sum", amount)
        query.bindValue(":note", note)
        assert query.exec_()
        self.db.commit()
        logging.info(f"Fees added: {note}, {amount}")

    # noinspection PyMethodMayBeStatic
    def loadIBDepositWithdraw(self, IBcash):
        logging.warning("*** MANUAL ENTRY REQUIRED ***")
        logging.warning(f"{IBcash.dateTime} {IBcash.description}: {IBcash.accountId} {IBcash.amount} {IBcash.currency}")

    def createDividend(self, timestamp, account_id, asset_id, amount, note):
        query = QSqlQuery(self.db)
        query.prepare("SELECT id FROM dividends "
                      "WHERE timestamp=:timestamp AND account_id=:account_id AND asset_id=:asset_id AND note=:note")
        query.bindValue(":timestamp", timestamp)
        query.bindValue(":account_id", account_id)
        query.bindValue(":asset_id", asset_id)
        query.bindValue(":note", note)
        assert query.exec_()
        if query.next():
            logging.warning(f"Dividend already exists: {note}")
            return
        query.prepare("INSERT INTO dividends (timestamp, account_id, asset_id, sum, note) "
                      "VALUES (:timestamp, :account_id, :asset_id, :sum, :note)")
        query.bindValue(":timestamp", timestamp)
        query.bindValue(":account_id", account_id)
        query.bindValue(":asset_id", asset_id)
        query.bindValue(":sum", amount)
        query.bindValue(":note", note)
        assert query.exec_()
        self.db.commit()
        logging.info(f"Dividend added: {note}")

    def addWithholdingTax(self, timestamp, account_id, asset_id, amount, note):
        parts = re.match(IBKR.TaxNotePattern, note)
        if not parts:
            logging.warning("*** MANUAL ENTRY REQUIRED ***")
            logging.warning(f"Strange tax found: {note}")
            return
        dividend_note = parts.group(1) + '%'
        country_code = parts.group(2)
        query = QSqlQuery(self.db)
        query.prepare("SELECT id, sum_tax FROM dividends "
                      "WHERE timestamp=:timestamp AND account_id=:account_id AND asset_id=:asset_id "
                      "AND note LIKE :dividend_description")
        query.bindValue(":timestamp", timestamp)
        query.bindValue(":account_id", account_id)
        query.bindValue(":asset_id", asset_id)
        query.bindValue(":dividend_description", dividend_note)
        assert query.exec_()
        if not query.next():
            logging.warning(f"Dividend not found for withholding tax: {note}")
            return
        dividend_id = query.value(0)
        old_tax = query.value(1)
        query.prepare("UPDATE dividends SET sum_tax=:tax, note_tax=:note WHERE id=:dividend_id")
        query.bindValue(":dividend_id", dividend_id)
        query.bindValue(":tax", old_tax + amount)
        query.bindValue(":note", country_code + " tax")
        assert query.exec_()
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