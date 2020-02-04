from ibflex import parser, AssetClass, BuySell
from PySide2.QtSql import QSqlQuery
from datetime import datetime

class StatementLoader:
    def __init__(self, db):
        self.db = db

    def loadIBFlex(self, filename):
        report = parser.parse(filename)
        for statement in report.FlexStatements:
            self.loadIBStatement(statement)

    def loadIBStatement(self, IBstatement):
        print(f"Load IB Flex-statement for account {IBstatement.accountId} from {IBstatement.fromDate} to {IBstatement.toDate}")
        for trade in IBstatement.Trades:
            self.loadIBTrade(trade)

    def loadIBTrade(self, IBtrade):
        if IBtrade.assetCategory == AssetClass.STOCK:
            self.loadIBStockTrade(IBtrade)
        # elif IBtrade.assetCategory == AssetClass.CASH:
        #     self.laodIBCurrencyTrade(IBtrade)
        else:
            print(f"Load of {IBtrade.assetCategory} is not implemented. Skipping trade #{IBtrade.tradeID}")

    def loadIBStockTrade(self, IBtrade):
        account_id = self.findAccountID(IBtrade.accountId, IBtrade.currency)
        if not account_id:
            print(f"Account {IBtrade.accountId} not found. Skipping trade #{IBtrade.tradeID}")
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
        number = IBtrade.tradeID
        qty = IBtrade.quantity
        price = IBtrade.tradePrice
        fee = IBtrade.ibCommission
        if IBtrade.buySell == BuySell.BUY:
            self.createTrade(account_id, asset_id, 1, timestamp, settlement, number, qty, price, fee)
        elif IBtrade.buySell == BuySell.SELL:
            self.createTrade(account_id, asset_id, -1, timestamp, settlement, number, -qty, price, fee)
        elif IBtrade.buySell == BuySell.CANCELBUY:
            self.deleteTrade(account_id, asset_id, timestamp, settlement, number)
        elif IBtrade.buySell == BuySell.CANCELSELL:
            self.deleteTrade(account_id, asset_id, timestamp, settlement, number)
        else:
            print(f"Trade type f{IBtrade.buySell} is not implemented")

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
        query.bindValue(":qty", float(qty))   # TODO put default 0 values in SQL DB
        query.bindValue(":price", float(price))
        query.bindValue(":fee_broker", float(fee))
        query.bindValue(":sum", float(qty*price-fee))
        assert query.exec_()
        self.db.commit()
        print(f"Trade #{number} added for account {account_id} asset {asset_id} @{timestamp}")

    #TODO Fix delete Trade as it's not operational due to NULL number
    def deleteTrade(self, account_id, asset_id, timestamp, _settlement, number):
        query = QSqlQuery(self.db)
        query.prepare("DELETE FROM trades "
                      "WHERE timestamp=:timestamp AND asset_id = :asset "
                      "AND account_id = :account AND number = :number")
        query.bindValue(":timestamp", timestamp)
        query.bindValue(":asset", asset_id)
        query.bindValue(":account", account_id)
        query.bindValue(":number", number)
        query.exec_()
        self.db.commit()
        print(f"Trade #{number} cancelled for account {account_id} asset {asset_id} @{timestamp}")


