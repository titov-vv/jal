from constants import *
from ibflex import parser, AssetClass, BuySell
from PySide2.QtSql import QSqlQuery
from datetime import datetime

class StatementLoader:
    def __init__(self, db):
        self.db = db

    def findAccountID(self, accountNumber, accountCurrency):
        query = QSqlQuery(self.db)
        query.prepare("SELECT a.id FROM accounts AS a "
                      "LEFT JOIN assets AS c ON c.id=a.currency_id "
                      "WHERE a.number=:account_number AND c.name=:currency_name")
        query.bindValue(":account_number", accountNumber)
        query.bindValue(":currency_name", accountCurrency)
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
            return 0

    def loadIBFlex(self, filename):
        report = parser.parse(filename)
        for statement in report.FlexStatements:
            self.loadIBStatement(statement)

    def loadIBStatement(self, IBstatement):
        print(f"Load IB Flex-statement for account {IBstatement.accountId} from {IBstatement.fromDate} to {IBstatement.toDate}")
        for trade in IBstatement.Trades:
            self.loadIBTrade(trade)
        for tax in IBstatement.TransactionTaxes:
            self.loadIBTransactionTax(tax)

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
        if not asset_id:
            print(f"Asset {IBtrade.symbol} not found. Skipping trade #{IBtrade.tradeID}")
            return
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
        if IBtrade.buySell == BuySell.BUY:
            self.createTrade(account_id, asset_id, 1, timestamp, settlement, number, qty, price, fee)
        elif IBtrade.buySell == BuySell.SELL:
            self.createTrade(account_id, asset_id, -1, timestamp, settlement, number, -qty, price, fee)
        elif IBtrade.buySell == BuySell.CANCELBUY:
            self.deleteTrade(account_id, asset_id, 1, timestamp, number)
        elif IBtrade.buySell == BuySell.CANCELSELL:
            self.deleteTrade(account_id, asset_id, -1, timestamp, number)
        else:
            print(f"Trade type f{IBtrade.buySell} is not implemented")

    def createTrade(self, account_id, asset_id, type, timestamp, settlement, number, qty, price, fee):
        query = QSqlQuery(self.db)
        query.prepare("SELECT id FROM trades "
                      "WHERE timestamp=:timestamp AND asset_id = :asset "
                      "AND account_id = :account AND number = :number")
        query.bindValue(":timestamp", timestamp)
        query.bindValue(":asset", asset_id)
        query.bindValue(":account", account_id)
        query.bindValue(":number", number)
        assert query.exec_()
        if query.next():
            print(f"Trade #{number} already exists")
            return
        query.prepare("INSERT INTO trades (timestamp, settlement, type, number, account_id, "
                      "asset_id, qty, price, fee_broker, sum) "
                      "VALUES (:timestamp, :settlement, :type, :number, :account, "
                      ":asset, :qty, :price, :fee, :sum)")
        query.bindValue(":timestamp", timestamp)
        query.bindValue(":settlement", settlement)
        query.bindValue(":type", type)
        query.bindValue(":number", number)
        query.bindValue(":account", account_id)
        query.bindValue(":asset", asset_id)
        query.bindValue(":qty", float(qty))
        query.bindValue(":price", float(price))
        query.bindValue(":fee_broker", float(fee))
        query.bindValue(":sum", float(qty*price-fee))
        assert query.exec_()
        self.db.commit()
        print(f"Trade #{number} added for account {account_id} asset {asset_id} @{timestamp}: {qty}x{price}")

    #TODO add transaction details for matching trade
    def deleteTrade(self, account_id, asset_id, type, timestamp, number):
        query = QSqlQuery(self.db)
        query.prepare("DELETE FROM trades "
                      "WHERE timestamp=:timestamp AND type=:type AND asset_id=:asset "
                      "AND account_id=:account AND number=:number")
        query.bindValue(":timestamp", timestamp)
        query.bindValue(":type", type)
        query.bindValue(":asset", asset_id)
        query.bindValue(":account", account_id)
        query.bindValue(":number", number)
        query.exec_()
        self.db.commit()
        print(f"Trade #{number} cancelled for account {account_id} asset {asset_id} @{timestamp}")

    def loadIBCurrencyTrade(self, IBtrade):
        if IBtrade.buySell == BuySell.BUY:
            from_idx = 1
            to_idx = 0
        elif IBtrade.buySell == BuySell.SELL:
            from_idx = 0
            to_idx = 1
        else:
            print(f"Currency transaction of type {IBtrade.buySell} is not implemented")
            return
        currency = IBtrade.symbol.split('.')
        to_currency_id = self.findAssetID(currency[to_idx])
        from_currency_id = self.findAssetID(currency[from_idx])
        if not to_currency_id or not from_currency_id:
            print(f"Assets for {IBtrade.symbol} not found. Skipping currency exchange transaction #{IBtrade.tradeID}")
            return
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
        to_amount = float(IBtrade.quantity)    # positive value
        from_amount = float(IBtrade.proceeds)  # already negative value
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
        query.prepare("INSERT INTO transfers_combined (from_timestamp, from_acc_id, from_amount, "
                      "to_timestamp, to_acc_id, to_amount, fee_timestamp, fee_acc_id, fee_amount, note) "
                      "VALUES (:timestamp, :f_acc_id, :f_amount, :timestamp, :t_acc_id, :t_amount, "
                      ":timestamp, :fee_acc_id, :fee_amount, :note)")
        query.bindValue(":timestamp", timestamp)
        query.bindValue(":f_acc_id", f_acc_id)
        query.bindValue(":t_acc_id", t_acc_id)
        query.bindValue(":fee_acc_id", fee_acc_id)
        query.bindValue(":f_amount", f_amount)
        query.bindValue(":t_amount", t_amount)
        query.bindValue(":fee_amount", fee)
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