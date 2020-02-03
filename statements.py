from ibflex import parser
from PySide2.QtSql import QSqlQuery

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
        account_id = self.findAccountID(IBtrade.accountId, IBtrade.currency)
        if account_id:
            print(f"Trade found for account #{account_id}")
        else:
            print(f"Account {IBtrade.accountId} not found")

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


