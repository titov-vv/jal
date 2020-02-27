from constants import *
import re
import pandas
import math
from ibflex import parser, AssetClass, BuySell, CashAction, Reorg, Code
from PySide2.QtSql import QSqlQuery
from datetime import datetime

TAX_NOTE_PATTERN = "^(.*) - (..) TAX$"
CLIENT_PATTERN = "^Код клиента: (.*)$"

QUIK_TIMESTAMP = 'Дата и время заключения сделки'
QUIK_DEAL_NUMBER = 'Номер сделки'
QUIK_SYMBOL = 'Код инструмента'
QUIK_SECNAME = 'Краткое наименование инструмента'
QUIK_DEAL_TYPE = 'Направление'
QUIK_QTY = 'Кол-во'
QUIK_PRICE = 'Цена'
QUIK_AMOUNT = 'Объём'
QUIK_COUPON = 'НКД'
QUIK_SETTLEMENT = 'Дата расчётов'
QUIK_BUY = 'Купля'
QUIK_SELL = 'Продажа'

class StatementLoader:
    def __init__(self, db):
        self.db = db

    def findAccountID(self, accountNumber, accountCurrency = ''):
        query = QSqlQuery(self.db)
        if accountCurrency:
            query.prepare("SELECT a.id FROM accounts AS a "
                          "LEFT JOIN assets AS c ON c.id=a.currency_id "
                          "WHERE a.number=:account_number AND c.name=:currency_name")
            query.bindValue(":currency_name", accountCurrency)
        else:
            query.prepare("SELECT a.id FROM accounts AS a "
                          "LEFT JOIN assets AS c ON c.id=a.currency_id "
                          "WHERE a.number=:account_number")
        query.bindValue(":account_number", accountNumber)
        assert query.exec_()
        if query.next():
            return query.value(0)
        else:
            return 0

    def findAssetID(self, symbol):
        query = QSqlQuery(self.db)
        query.prepare("SELECT id FROM assets WHERE name=:symbol")
        query.bindValue(":symbol", symbol)
        assert query.exec_()
        if query.next():
            return query.value(0)
        else:
            assert False   # We shouldn't be here as all assets from report should be added in advance

    def loadIBFlex(self, filename):
        report = parser.parse(filename)
        for statement in report.FlexStatements:
            self.loadIBStatement(statement)

    def loadIBStatement(self, IBstatement):
        print(f"Load IB Flex-statement for account {IBstatement.accountId} from {IBstatement.fromDate} to {IBstatement.toDate}")

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
            asset_type = 2
            if IBasset.subCategory == "ETF":
                asset_type = 4
        if IBasset.assetCategory == AssetClass.BOND:
            asset_type = 3
        query.prepare("INSERT INTO assets(name, type_id, full_name, isin) VALUES(:symbol, :type, :full_name, :isin)")
        query.bindValue(":symbol", IBasset.symbol)
        query.bindValue(":type", asset_type)
        query.bindValue(":full_name", IBasset.description)
        query.bindValue(":isin", IBasset.isin)
        assert query.exec_()
        print(f"Asset added: {IBasset.symbol}")

    def loadIBTrade(self, IBtrade):
        if IBtrade.assetCategory == AssetClass.STOCK:
            self.loadIBStockTrade(IBtrade)
        elif IBtrade.assetCategory == AssetClass.CASH:
            self.loadIBCurrencyTrade(IBtrade)
        else:
            print(f"Load of {IBtrade.assetCategory} is not implemented. Skipping trade #{IBtrade.tradeID}")

    def loadIBStockTrade(self, IBtrade):
        account_id = self.findAccountID(IBtrade.accountId, IBtrade.currency)
        if not account_id:
            print(f"Account {IBtrade.accountId} ({IBtrade.currency}) not found. Skipping trade #{IBtrade.tradeID}")
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
            print(f"Trade type f{IBtrade.buySell} is not implemented")

    def createTrade(self, account_id, asset_id, timestamp, settlement, number, qty, price, fee, coupon=0):
        query = QSqlQuery(self.db)
        query.prepare("SELECT id FROM trades "
                      "WHERE timestamp=:timestamp AND asset_id = :asset "
                      "AND account_id = :account AND number = :number AND qty = :qty AND price = :price")
        query.bindValue(":timestamp", timestamp)
        query.bindValue(":asset", asset_id)
        query.bindValue(":account", account_id)
        query.bindValue(":number", number)
        query.bindValue(":qty", qty)
        query.bindValue(":price", price)
        assert query.exec_()
        if query.next():
            print(f"Trade #{number} already exists")
            return
        query.prepare("INSERT INTO trades (timestamp, settlement, corp_action_id, number, account_id, "
                      "asset_id, qty, price, fee, coupon) "
                      "VALUES (:timestamp, :settlement, 0, :number, :account, "
                      ":asset, :qty, :price, :fee, :coupon)")
        query.bindValue(":timestamp", timestamp)
        query.bindValue(":settlement", settlement)
        query.bindValue(":number", number)
        query.bindValue(":account", account_id)
        query.bindValue(":asset", asset_id)
        query.bindValue(":qty", float(qty))
        query.bindValue(":price", float(price))
        query.bindValue(":fee", -float(fee))
        query.bindValue(":coupon", float(coupon))
        assert query.exec_()
        self.db.commit()
        print(f"Trade #{number} added for account {account_id} asset {asset_id} @{timestamp}: {qty}x{price}")

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
        print(f"Trade #{number} cancelled for account {account_id} asset {asset_id} @{timestamp}, Qty {qty}x{price}")

    def loadIBCurrencyTrade(self, IBtrade):
        if IBtrade.buySell == BuySell.BUY:
            from_idx = 1
            to_idx = 0
            to_amount = float(IBtrade.quantity)    # positive value
            from_amount = float(IBtrade.proceeds)  # already negative value
        elif IBtrade.buySell == BuySell.SELL:
            from_idx = 0
            to_idx = 1
            from_amount = float(IBtrade.quantity)  # already negative value
            to_amount = float(IBtrade.proceeds)    # positive value
        else:
            print(f"Currency transaction of type {IBtrade.buySell} is not implemented")
            return
        currency = IBtrade.symbol.split('.')
        to_account_id = self.findAccountID(IBtrade.accountId, currency[to_idx])
        if not to_account_id:
            print(f"Account {IBtrade.accountId} ({currency[to_idx]}) not found. Skipping currency exchange transaction #{IBtrade.tradeID}")
            return
        from_account_id = self.findAccountID(IBtrade.accountId, currency[from_idx])
        if not from_account_id:
            print(f"Account {IBtrade.accountId} ({currency[from_idx]}) not found. Skipping currency exchange transaction #{IBtrade.tradeID}")
            return
        fee_account_id = self.findAccountID(IBtrade.accountId, IBtrade.ibCommissionCurrency)
        if not fee_account_id:
            print(f"Account {IBtrade.accountId} ({IBtrade.ibCommissionCurrency}) not found. Skipping currency exchange transaction #{IBtrade.tradeID}")
            return
        timestamp = int(IBtrade.dateTime.timestamp())
        fee = float(IBtrade.ibCommission)   # already negative value
        note = IBtrade.exchange
        self.createTransfer(timestamp, from_account_id, from_amount, to_account_id, to_amount, fee_account_id, fee, note)

    def createTransfer(self, timestamp, f_acc_id, f_amount, t_acc_id, t_amount, fee_acc_id, fee, note):
        query = QSqlQuery(self.db)
        query.prepare("SELECT id FROM transfers_combined "
                      "WHERE from_timestamp=:timestamp AND from_acc_id=:from_acc_id AND to_acc_id=:to_acc_id")
        query.bindValue(":timestamp", timestamp)
        query.bindValue(":from_acc_id", f_acc_id)
        query.bindValue(":to_acc_id", t_acc_id)
        assert query.exec_()
        if query.next():
            print(f"Currency exchange {f_amount}->{t_amount} already exists")
            return
        if abs(fee) > CALC_TOLERANCE:
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
        print(f"Currency exchange {f_amount}->{t_amount} added @{timestamp}")

    def loadIBTransactionTax(self, IBtax):
        account_id = self.findAccountID(IBtax.accountId, IBtax.currency)
        if not account_id:
            print(f"Account {IBtax.accountId} ({IBtax.currency}) not found. Skipping transaction tax #{IBtax.tradeID}")
            return
        timestamp = int(datetime.combine(IBtax.date, datetime.min.time()).timestamp())
        amount = float(IBtax.taxAmount) # value is negative already
        note = f"{IBtax.symbol} ({IBtax.description}) - {IBtax.taxDescription} (#{IBtax.tradeId})"

        query = QSqlQuery(self.db)
        query.prepare("SELECT id FROM all_operations "
                      "WHERE type = :type AND timestamp=:timestamp AND account_id=:account_id AND amount=:amount")
        query.bindValue(":timestamp", timestamp)
        query.bindValue(":type", TRANSACTION_ACTION)
        query.bindValue(":account_id", account_id)
        query.bindValue(":amount", amount)
        assert query.exec_()
        if query.next():
            print(f"Tax transaction #{IBtax.tradeId} already exists")
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
        query.bindValue(":category_id", CATEGORY_TAXES)
        query.bindValue(":sum", amount)
        query.bindValue(":note", note)
        assert query.exec_()
        self.db.commit()
        print(f"Transaction tax added: {note}, {amount}")

    def loadIBCorpAction(self, IBCorpAction):
        if IBCorpAction.code == Code.CANCEL:
            print("*** MANUAL ACTION REQUIRED ***")
            print(f"Corporate action cancelled {IBCorpAction.type} for account {IBCorpAction.accountId} ({IBCorpAction.currency}): {IBCorpAction.actionDescription}")
            print(f"@{IBCorpAction.dateTime} for {IBCorpAction.symbol}: Qty {IBCorpAction.quantity}, Value {IBCorpAction.value}, Type {IBCorpAction.type}, Code {IBCorpAction.code}")
            return
        if IBCorpAction.assetCategory == AssetClass.STOCK and (IBCorpAction.type == Reorg.MERGER or IBCorpAction.type == Reorg.SPINOFF):
            account_id = self.findAccountID(IBCorpAction.accountId, IBCorpAction.currency)
            if not account_id:
                print(
                    f"Account {IBCorpAction.accountId} ({IBCorpAction.currency}) not found. Skipping trade #{IBCorpAction.transactionID}")
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
        print("*** MANUAL ACTION REQUIRED ***")
        print(f"Corporate action {IBCorpAction.type} for account {IBCorpAction.accountId} ({IBCorpAction.currency}): {IBCorpAction.actionDescription}")
        print(f"@{IBCorpAction.dateTime} for {IBCorpAction.symbol}: Qty {IBCorpAction.quantity}, Value {IBCorpAction.value}, Type {IBCorpAction.type}, Code {IBCorpAction.code}")

    def loadIBDividend(self, IBdividend):
        if IBdividend.assetCategory != AssetClass.STOCK:
            print(f"Dividend for {IBdividend.assetCategory} not implemented")
            return
        account_id = self.findAccountID(IBdividend.accountId, IBdividend.currency)
        if not account_id:
            print(f"Account {IBdividend.accountId} ({IBdividend.currency}) not found. Skipping dividend #{IBdividend.transactionID}")
            return
        asset_id = self.findAssetID(IBdividend.symbol)
        timestamp = int(IBdividend.dateTime.timestamp())
        amount = float(IBdividend.amount)
        note = IBdividend.description
        self.createDividend(timestamp, account_id, asset_id, amount, note)

    def loadIBWithholdingTax(self, IBtax):
        if IBtax.assetCategory != AssetClass.STOCK:
            print(f"Withholding tax for {IBtax.assetCategory} not implemented")
            return
        account_id = self.findAccountID(IBtax.accountId, IBtax.currency)
        if not account_id:
            print(
                f"Account {IBtax.accountId} ({IBtax.currency}) not found. Skipping withholding tax #{IBtax.transactionID}")
            return
        asset_id = self.findAssetID(IBtax.symbol)
        timestamp = int(IBtax.dateTime.timestamp())
        amount = float(IBtax.amount)
        note = IBtax.description
        self.addWithholdingTax(timestamp, account_id, asset_id, amount, note)

    def loadIBFee(self, IBfee):
        account_id = self.findAccountID(IBfee.accountId, IBfee.currency)
        if not account_id:
            print(f"Account {IBfee.accountId} ({IBfee.currency}) not found. Skipping transaction tax #{IBfee.transactionID}")
            return
        timestamp = int(IBfee.dateTime.timestamp())
        amount = float(IBfee.amount)  # value may be both positive and negative
        note = IBfee.description
        query=QSqlQuery(self.db)
        query.prepare("INSERT INTO actions (timestamp, account_id, peer_id) "
                      "VALUES (:timestamp, :account_id, (SELECT organization_id FROM accounts WHERE id=:account_id))")
        query.bindValue(":timestamp", timestamp)
        query.bindValue(":account_id", account_id)
        assert query.exec_()
        pid = query.lastInsertId()
        query.prepare("INSERT INTO action_details (pid, category_id, sum, note) "
                      "VALUES (:pid, :category_id, :sum, :note)")
        query.bindValue(":pid", pid)
        query.bindValue(":category_id", CATEGORY_FEES)
        query.bindValue(":sum", amount)
        query.bindValue(":note", note)
        assert query.exec_()
        self.db.commit()
        print(f"Fees added: {note}, {amount}")

    def loadIBDepositWithdraw(self, IBcash):
        print("*** MANUAL ENTRY REQUIRED ***")
        print(f"{IBcash.dateTime} {IBcash.description}: {IBcash.accountId} {IBcash.amount} {IBcash.currency}")

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
            print(f"Dividend already exists: {note}")
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
        print(f"Dividend added: {note}")

    def addWithholdingTax(self, timestamp, account_id, asset_id, amount, note):
        parts = re.match(TAX_NOTE_PATTERN, note)
        if not parts:
            print("*** MANUAL ENTRY REQUIRED ***")
            print(f"Strange tax found: {note}")
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
            print(f"Dividend not found for withholding tax: {note}")
            return
        dividend_id = query.value(0)
        old_tax = query.value(1)
        query.prepare("UPDATE dividends SET sum_tax=:tax, note_tax=:note WHERE id=:dividend_id")
        query.bindValue(":dividend_id", dividend_id)
        query.bindValue(":tax", old_tax+amount)
        query.bindValue(":note", country_code + " tax")
        assert query.exec_()
        self.db.commit()
        print(f"Withholding tax added: {note}")

    def loadQuikHtml(self, filename):
        data = pandas.read_html(filename, encoding='cp1251')
        report_info = data[0]
        deals_info = data[1]
        parts = re.match(CLIENT_PATTERN, report_info[0][2])
        if parts:
            account_number = parts.group(1)
            account_id = self.findAccountID(account_number)
            if not account_id:
                print(f"Account {account_number} not found. Import cancelled.")
                return
        for index, row in deals_info.iterrows():
            if row[QUIK_DEAL_TYPE] == QUIK_BUY:
                qty = int(row[QUIK_QTY])
            elif row[QUIK_DEAL_TYPE] == QUIK_SELL:
                qty = -int(row[QUIK_QTY])
            else:
                break
            asset_id = self.findAssetID(row[QUIK_SYMBOL])
            timestamp = int(datetime.strptime(row[QUIK_TIMESTAMP], "%d.%m.%Y %H:%M:%S").timestamp())
            settlement = int(datetime.strptime(row[QUIK_SETTLEMENT], "%d.%m.%Y").timestamp())
            number = row[QUIK_DEAL_NUMBER]
            price = float(row[QUIK_PRICE])
            amount = float(row[QUIK_AMOUNT])
            lot_size = math.pow(10, round(math.log10(amount / (price*abs(qty)))))
            qty = qty * lot_size
            fee = 0  # there is monthly fee in Uralsib
            coupon = float(row[QUIK_COUPON])
            self.createTrade(account_id, asset_id, timestamp, settlement, number, qty, price, fee, coupon)