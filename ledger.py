import datetime
from constants import *
from PySide2.QtSql import QSqlQuery

###################################################################################################
#TODO Check are there positive lines for Incomes
#TODO Check are there negative lines for Costs
#TODO Simplify Buy/Sell queries
###################################################################################################
class Ledger:
    def __init__(self, db):
        self.db = db

    def appendTransaction(self, timestamp, seq_id, book, active_id, account_id, amount, value=None, peer_id=None, category_id=None, tag_id=None):
        query = QSqlQuery(self.db)
        query.prepare("SELECT sid, sum_amount, sum_value FROM ledger_sums "
                       "WHERE book_account = :book AND active_id = :active_id AND account_id = :account_id AND sid <= :seq_id "
                       "ORDER BY sid DESC LIMIT 1")
        query.bindValue(":book", book)
        query.bindValue(":active_id", active_id)
        query.bindValue(":account_id", account_id)
        query.bindValue(":seq_id", seq_id)
        assert query.exec_()
        if query.next():
            old_sid = query.value(0)
            old_amount = query.value(1)
            old_value = query.value(2)
        else:
            old_sid = -1
            old_amount = 0.0
            old_value = 0.0
        new_amount = old_amount + amount
        if value == None:
            new_value = old_value
        else:
            new_value = old_value + value
        if (abs(new_amount-old_amount)+abs(new_value-old_value))<=(2*CALC_TOLERANCE):
            return

        query.prepare(
            "INSERT INTO ledger (timestamp, sid, book_account, active_id, account_id, amount, value, peer_id, category_id, tag_id) "
            "VALUES(:timestamp, :sid, :book, :active_id, :account_id, :amount, :value, :peer_id, :category_id, :tag_id)")
        query.bindValue(":timestamp", timestamp)
        query.bindValue(":sid", seq_id)
        query.bindValue(":book", book)
        query.bindValue(":active_id", active_id)
        query.bindValue(":account_id", account_id)
        query.bindValue(":amount", amount)
        query.bindValue(":value", value)
        query.bindValue(":peer_id", peer_id)
        query.bindValue(":category_id", category_id)
        query.bindValue(":tag_id", tag_id)
        assert query.exec_()
        if seq_id == old_sid:
            query.prepare("UPDATE ledger_sums SET sum_amount = :new_amount, sum_value = :new_value"
                          " WHERE sid = :sid AND book_account = :book AND active_id = :active_id AND account_id = :account_id")
            query.bindValue(":new_amount", new_amount)
            query.bindValue(":new_value", new_value)
            query.bindValue(":sid", seq_id)
            query.bindValue(":book", book)
            query.bindValue(":active_id", active_id)
            query.bindValue(":account_id", account_id)
            assert query.exec_()
        else:
            query.prepare("INSERT INTO ledger_sums(sid, timestamp, book_account, active_id, account_id, sum_amount, sum_value) "
                       "VALUES(:sid, :timestamp, :book, :active_id, :account_id, :new_amount, :new_value)")
            query.bindValue(":sid", seq_id)
            query.bindValue(":timestamp", timestamp)
            query.bindValue(":book", book)
            query.bindValue(":active_id", active_id)
            query.bindValue(":account_id", account_id)
            query.bindValue(":new_amount", new_amount)
            query.bindValue(":new_value", new_value)
            assert query.exec_()
        self.db.commit()

    # TODO check that condition <= is really correct for timestamp in this function
    def getAmount(self, timestamp, book, account_id, active_id = None):
        query = QSqlQuery(self.db)
        if active_id == None:
            query.prepare("SELECT sum_amount FROM ledger_sums WHERE book_account = :book AND account_id = :account_id "
                          "AND timestamp <= :timestamp ORDER BY sid DESC LIMIT 1")
        else:
            query.prepare("SELECT sum_amount FROM ledger_sums WHERE book_account = :book AND account_id = :account_id "
                          "AND active_id = :active_id AND timestamp <= :timestamp ORDER BY sid DESC LIMIT 1")
            query.bindValue(":active_id", active_id)
        query.bindValue(":timestamp", timestamp)
        query.bindValue(":book", book)
        query.bindValue(":account_id", account_id)
        assert query.exec_()
        if query.next():
            return float(query.value(0))
        else:
            return 0.0

    def lastDeal(self, timestamp, active_id, account_id):
        query = QSqlQuery(self.db)
        query.exec_("DROP TABLE IF EXISTS temp.influx")
        query.exec_("DROP TABLE IF EXISTS temp.outflux")
        query.prepare("CREATE TEMPORARY TABLE influx AS "
                       "SELECT buy.timestamp, sum(buy_before.qty) - buy.qty AS qty_before, sum(buy_before.qty) AS qty_after "
                       "FROM trades AS buy "
                       "INNER JOIN trades AS buy_before "
                       "ON buy.timestamp >= buy_before.timestamp and buy.active_id = buy_before.active_id and buy.account_id = buy_before.account_id "
                       "WHERE buy.type = 1 and buy_before.type = 1 and buy.active_id = :active_id and buy.account_id = :account_id and buy.timestamp < :timestamp "
                       "GROUP BY buy.timestamp, buy.qty")
        query.bindValue(":active_id", active_id)
        query.bindValue(":account_id", account_id)
        query.bindValue(":timestampe", timestamp)
        query.exec_()
        query.prepare("CREATE TEMPORARY TABLE outflux AS "
                       "SELECT sell.timestamp, sum(sell_before.qty) - sell.qty AS qty_before, sum(sell_before.qty) AS qty_after "
                       "FROM trades AS sell "
                       "INNER JOIN trades AS sell_before "
                       "ON sell.timestamp >= sell_before.timestamp and sell.active_id = sell_before.active_id and sell.account_id = sell_before.account_id "
                       "WHERE sell.type = -1 and sell_before.type = -1 and sell.active_id = :active_id and sell.account_id = :account_id and sell.timestamp < :timestamp "
                       "GROUP BY sell.timestamp, sell.qty")
        query.bindValue(":active_id", active_id)
        query.bindValue(":account_id", account_id)
        query.bindValue(":timestampe", timestamp)
        query.exec_()
        assert query.exec_("SELECT o.timestamp AS sell_timestamp, i.timestamp AS buy_timestamp, "
                       "CASE WHEN i.qty_after <= o.qty_after THEN 1 ELSE 0 END AS buy_full_match, "
                       "CASE WHEN i.qty_after >= o.qty_after THEN 1 ELSE 0 END AS sell_full_match, "
                       "i.qty_after - o.qty_after AS remainder "
                       "FROM temp.outflux AS o JOIN temp.influx AS i ON o.qty_after > i.qty_before AND o.qty_before < i.qty_after "
                       "ORDER BY o.timestamp DESC, i.timestamp DESC "
                       "LIMIT 1")
        if query.next():
            return (query.value(0), query.value(1), query.value(2), query.value(3), query.value(4))
        else:
            return None

    def takeCredit(self, seq_id, timestamp, account_id, currency_id, action_sum):
        money_available = self.getAmount(timestamp, BOOK_ACCOUNT_MONEY, account_id)
        credit = 0
        if (money_available < action_sum):
            credit = action_sum - money_available
            self.appendTransaction(timestamp, seq_id, BOOK_ACCOUNT_LIABILITIES, currency_id, account_id, -credit)
        return credit

    def returnCredit(self, seq_id, timestamp, account_id, currency_id, action_sum):
        CreditValue = -1.0 * self.getAmount(timestamp, BOOK_ACCOUNT_LIABILITIES, account_id)
        debit = 0
        if (CreditValue > 0):
            if (CreditValue >= action_sum):
                debit = action_sum
            else:
                debit = CreditValue
        if (debit > 0):
            self.appendTransaction(timestamp, seq_id, BOOK_ACCOUNT_LIABILITIES, currency_id, account_id, debit)
        return debit

    def processActionDetails(self, seq_id, op_id):
        query = QSqlQuery(self.db)
        query.prepare("SELECT a.timestamp, a.account_id, a.peer_id, c.currency_id, d.sum as amount, d.category_id, d.tag_id "
                       "FROM actions as a "
                       "LEFT JOIN action_details AS d ON a.id=d.pid "
                       "LEFT JOIN accounts AS c ON a.account_id = c.id "
                       "WHERE pid = :pid")
        query.bindValue(":pid", op_id)
        assert query.exec_()
        while query.next():
            amount = query.value(4)
            if (amount < 0):
                self.appendTransaction(query.value(0), seq_id, BOOK_ACCOUNT_COSTS, query.value(3),
                                       query.value(1), -amount, None, query.value(2), query.value(5), query.value(6))
            else:
                self.appendTransaction(query.value(0), seq_id, BOOK_ACCOUNT_INCOMES, query.value(3),
                                       query.value(1), -amount, None, query.value(2), query.value(5), query.value(6))

    def processAction(self, seq_id, op_id):
        query = QSqlQuery(self.db)
        query.prepare("SELECT a.timestamp, a.account_id, c.currency_id, sum(d.sum) "
                       "FROM actions AS a "
                       "LEFT JOIN action_details AS d ON a.id = d.pid "
                       "LEFT JOIN accounts AS c ON a.account_id = c.id "
                       "WHERE a.id = :id "
                       "GROUP BY a.timestamp, a.account_id, c.currency_id "
                       "ORDER BY a.timestamp, d.sum desc")
        query.bindValue(":id", op_id)
        assert query.exec_()
        query.next()
        timestamp = query.value(0)
        account_id = query.value(1)
        currency_id = query.value(2)
        action_sum = query.value(3)
        if action_sum < 0:
            credit_sum = self.takeCredit(seq_id, timestamp, account_id, currency_id, -action_sum)
            self.appendTransaction(timestamp, seq_id, BOOK_ACCOUNT_MONEY, currency_id, account_id, -(-action_sum - credit_sum))
        else:
            returned_sum = self.returnCredit(seq_id, timestamp, account_id, currency_id, action_sum)
            if (returned_sum < action_sum):
                self.appendTransaction(timestamp, seq_id, BOOK_ACCOUNT_MONEY, currency_id, account_id, (action_sum - returned_sum))
        self.processActionDetails(seq_id, op_id)

    def processDividend(self, seq_id, op_id):
        query = QSqlQuery(self.db)
        query.prepare("SELECT d.timestamp, d.account_id, c.currency_id, c.organization_id, d.sum, d.sum_tax "
                       "FROM dividends AS d "
                       "LEFT JOIN accounts AS c ON d.account_id = c.id "
                       "WHERE d.id = :id")
        query.bindValue(":id", op_id)
        assert query.exec_()
        query.next()
        timestamp = query.value(0)
        account_id = query.value(1)
        currency_id = query.value(2)
        peer_id = query.value(3)
        dividend_sum = query.value(4)
        tax_sum = query.value(5)
        returned_sum = self.returnCredit(seq_id, timestamp, account_id, currency_id, (dividend_sum - tax_sum))
        if (returned_sum < dividend_sum):
            self.appendTransaction(timestamp, seq_id, BOOK_ACCOUNT_MONEY, currency_id, account_id, (dividend_sum - returned_sum))
        self.appendTransaction(timestamp, seq_id, BOOK_ACCOUNT_INCOMES, currency_id, account_id, -dividend_sum, None, peer_id, CATEGORY_DIVIDEND)
        if (tax_sum > 0):
            self.appendTransaction(timestamp, seq_id, BOOK_ACCOUNT_MONEY, currency_id, account_id, -tax_sum)
            self.appendTransaction(timestamp, seq_id, BOOK_ACCOUNT_COSTS, currency_id, account_id, tax_sum, None, peer_id, CATEGORY_TAXES)

    def processBuy(self, seq_id, timestamp, account_id, currency_id, active_id, qty, price, coupon, fee, trade_sum):
        sell_qty = 0
        sell_sum = 0
        query = QSqlQuery(self.db)
        if (self.getAmount(timestamp, BOOK_ACCOUNT_ACTIVES, account_id, active_id) < 0):
            last_deal = self.lastDeal(timestamp, active_id, account_id)
            if (last_deal == None):   # There were no deals -> Select all sells
                reminder = 0
                query.prepare("SELECT t.id, t.qty, t.price FROM trades AS t WHERE t.type = -1 "
                              "AND t.active_id = :active_id AND t.account_id = :account_id AND t.timestamp < :timestamp")
            else:
                if (last_deal[3] == 1):  # SellFullMatch is true -> Select all sells after the closed deal (i.e. last sell timestamp)
                    reminder = 0
                    query.prepare("SELECT t.id, t.qty, t.price FROM trades AS t "
                                   "WHERE t.type = -1 AND t.active_id = :active_id AND t.account_id = :account_id "
                                   "AND t.timestamp < :timestamp AND t.timestamp > :last_deal")
                    query.bindValue(":last_deal", last_deal[0])
                else:
                    reminder = last_deal[4]
                    query.prepare("SELECT t.id, t.qty, t.price FROM trades AS t "
                                   "WHERE t.type = -1 AND t.active_id = :active_id AND t.account_id = :account_id "
                                   "AND t.timestamp < :timestamp AND t.timestamp >= :last_deal")
                    query.bindValue(":last_deal", last_deal[0])
            query.bindValue(":active_id", active_id)
            query.bindValue(":account_id", account_id)
            query.bindValue(":timestamp", timestamp)
            assert query.exec_()
            while query.next():
                if (reminder < 0):
                    next_deal_qty = -reminder
                    reminder = 0
                else:
                    next_deal_qty = query.value(1) # value(1) = quantity
                if (sell_qty + next_deal_qty) >= qty:  # we are buying less or the same amount as was sold previously
                    next_deal_qty = qty - sell_qty
                sell_qty = sell_qty + next_deal_qty
                sell_sum = sell_sum + (next_deal_qty * query.value(2))  # value(2) = price
                if (sell_qty == qty):
                    break
        credit_sum = self.takeCredit(seq_id, timestamp, account_id, currency_id, trade_sum)
        if (trade_sum != credit_sum):
            self.appendTransaction(timestamp, seq_id, BOOK_ACCOUNT_MONEY, currency_id, account_id, -(trade_sum - credit_sum))
        if (sell_qty > 0):  # Result of closed deals
            self.appendTransaction(timestamp, seq_id, BOOK_ACCOUNT_ACTIVES, active_id, account_id, sell_qty, sell_sum)
            if (((price * sell_qty) - sell_sum) != 0):  # Profit if we have it
                self.appendTransaction(timestamp, seq_id, BOOK_ACCOUNT_INCOMES, currency_id, account_id, ((price * sell_qty) - sell_sum), None, None, CATEGORY_PROFIT)
        if (sell_qty < qty):   # Add new long position
            self.appendTransaction(timestamp, seq_id, BOOK_ACCOUNT_ACTIVES, active_id, account_id, (qty - sell_qty), (qty - sell_qty) * price)
        if ((fee + coupon) != 0):  # Comission
            self.appendTransaction(timestamp, seq_id, BOOK_ACCOUNT_COSTS, currency_id, account_id, (fee + coupon), None, None, CATEGORY_FEES)

    def processSell(self, seq_id, timestamp, account_id, currency_id, active_id, qty, price, coupon, fee, trade_sum):
        buy_qty = 0
        buy_sum = 0
        query = QSqlQuery(self.db)
        if (self.getAmount(timestamp, BOOK_ACCOUNT_ACTIVES, account_id, active_id) > 0):
            last_deal = self.lastDeal(timestamp, active_id, account_id)
            if (last_deal == None):   # There were no deals -> Select all purchases
                reminder = 0
                query.prepare("SELECT t.id, t.qty, t.price FROM trades AS t WHERE t.type = 1 "
                              "AND t.active_id = :active_id AND t.account_id = :account_id AND t.timestamp < :timestamp")
            else:
                if (last_deal[2] == 1):  # BuyFullMatch is true -> Select all purchases after the closed deal (i.e. last buy timestamp)
                    reminder = 0
                    query.prepare("SELECT t.id, t.qty, t.price FROM trades AS t "
                                   "WHERE t.type = 1 AND t.active_id = :active_id AND t.account_id = :account_id "
                                   "AND t.timestamp < :timestamp AND t.timestamp > :last_deal")
                    query.bindValue(":last_deal", last_deal[1])
                else:
                    reminder = last_deal[4]
                    query.prepre("SELECT t.id, t.qty, t.price FROM trades AS t "
                                   "WHERE t.type = 1 AND t.active_id = :active_id AND t.account_id = :account_id "
                                   "AND t.timestamp < :timestamp AND t.timestamp >= :last_deal")
                    query.bindValue(":last_deal", last_deal[1])
            query.bindValue(":active_id", active_id)
            query.bindValue(":account_id", account_id)
            query.bindValue(":timestamp", timestamp)
            assert query.exec_()
            while query.next():
                if (reminder > 0):
                    next_deal_qty = reminder
                    reminder = 0
                else:
                    next_deal_qty = query.value(1)  # value(1) = quantity
                if (buy_qty + next_deal_qty) >= qty:  # we are selling less or the same amount as was bought previously
                    next_deal_qty = qty - buy_qty
                buy_qty = buy_qty + next_deal_qty
                buy_sum = buy_sum + (next_deal_qty * query.value(2))  # value(2) = price
                if (buy_qty == qty):
                    break
        returned_sum = self.returnCredit(seq_id, timestamp, account_id, currency_id, trade_sum)
        if (returned_sum < trade_sum):
            self.appendTransaction(timestamp, seq_id, BOOK_ACCOUNT_MONEY, currency_id, account_id, (trade_sum - returned_sum))
        if (buy_qty > 0):  # Result of closed deals
            self.appendTransaction(timestamp, seq_id, BOOK_ACCOUNT_ACTIVES, active_id, account_id, -buy_qty, -buy_sum)
            if ((buy_sum - (price * buy_qty)) != 0):  # Profit if we have it
                self.appendTransaction(timestamp, seq_id, BOOK_ACCOUNT_INCOMES, currency_id, account_id, (buy_sum - (price * buy_qty)), None, None, CATEGORY_PROFIT)
        if (buy_qty < qty):   # Add new short position
            self.appendTransaction(timestamp, seq_id, BOOK_ACCOUNT_ACTIVES, active_id, account_id, (buy_qty - qty), (buy_qty < qty) * price)
        if (coupon > 0):
            self.appendTransaction(timestamp, seq_id, BOOK_ACCOUNT_INCOMES, currency_id, account_id, -coupon, None, None, CATEGORY_PROFIT)
        if ((fee + coupon) != 0):   # Comission
            self.appendTransaction(timestamp, seq_id, BOOK_ACCOUNT_COSTS, currency_id, account_id, (fee + coupon), None, None, CATEGORY_PROFIT)

    def processTrade(self, seq_id, id):
        query = QSqlQuery(self.db)
        query.prepare("SELECT t.type, t.timestamp, t.account_id, c.currency_id, t.active_id, t.qty, t.price, t.coupon, t.fee_broker+t.fee_exchange, t.sum "
                       "FROM trades AS t "
                       "LEFT JOIN accounts AS c ON t.account_id = c.id "
                       "WHERE t.id = :id")
        query.bindValue(":id", id)
        assert query.exec_()
        query.next()
        type = query.value(0)
        if (type == 1):
            self.processBuy(seq_id, query.value(1), query.value(2), query.value(3), query.value(4), query.value(5),
                            query.value(6), query.value(7), query.value(8), query.value(9))
        else:
            self.processSell(seq_id, query.value(1), query.value(2), query.value(3), query.value(4), query.value(5),
                             query.value(6), query.value(7), query.value(8), query.value(9))

    def processTransferOut(self, seq_id, timestamp, account_id, currency_id, amount):
        credit_sum = self.takeCredit(seq_id, timestamp, account_id, currency_id, amount)
        self.appendTransaction(timestamp, seq_id, BOOK_ACCOUNT_MONEY, currency_id, account_id, -(amount - credit_sum))
        self.appendTransaction(timestamp, seq_id, BOOK_ACCOUNT_TRANSFERS, currency_id, account_id, amount)

    def processTransferIn(self, seq_id, timestamp, account_id, currency_id, amount):
        returned_sum = self.returnCredit(seq_id, timestamp, account_id, currency_id, amount)
        if (returned_sum < amount):
            self.appendTransaction(timestamp, seq_id, BOOK_ACCOUNT_MONEY, currency_id, account_id, (amount - returned_sum))
        self.appendTransaction(timestamp, seq_id, BOOK_ACCOUNT_TRANSFERS, currency_id, account_id, -amount)

    def processTransferFee(self, seq_id, timestamp, account_id, currency_id, fee):
        credit_sum = self.takeCredit(seq_id, timestamp, account_id, currency_id, fee)
        self.appendTransaction(timestamp, seq_id, BOOK_ACCOUNT_MONEY, currency_id, account_id, -(fee - credit_sum))
        self.appendTransaction(timestamp, seq_id, BOOK_ACCOUNT_COSTS, currency_id, account_id, fee, None, PEER_FINANCIAL, CATEGORY_FEES, None)

    def processTransfer(self, seq_id, id):
        query = QSqlQuery(self.db)
        query.prepare("SELECT t.type, t.timestamp, t.account_id, a.currency_id, t.amount "
                      "FROM transfers AS t "
                      "LEFT JOIN accounts AS a ON t.account_id = a.id "
                      "WHERE t.id = :id")
        query.bindValue(":id", id)
        assert query.exec_()
        query.next()
        type = query.value(0)
        if (type == TRANSFER_OUT):
            self.processTransferOut(seq_id, query.value(1), query.value(2), query.value(3), -query.value(4))
        elif (type == TRANSFER_IN):
            self.processTransferIn(seq_id, query.value(1), query.value(2), query.value(3), query.value(4))
        elif (type == TRANSFER_FEE):
            self.processTransferFee(seq_id, query.value(1), query.value(2), query.value(3), -query.value(4))

    # Rebuild transaction sequence and recalculate all amounts
    # timestamp:
    # -1 - re-build from last valid operation (from ledger frontier)
    # 0 - re-build from scratch
    # any - re-build all operations after given timestamp
    def MakeUpToDate(self):
        query = QSqlQuery(self.db)
        assert query.exec_("SELECT ledger_frontier FROM frontier")
        query.next()
        frontier = query.value(0)
        if (frontier == ''):
            frontier = 0

        query.prepare("DELETE FROM ledger WHERE timestamp >= :frontier")
        query.bindValue(":frontier", frontier)
        assert query.exec_()
        query.prepare("DELETE FROM sequence WHERE timestamp >= :frontier")
        query.bindValue(":frontier", frontier)
        assert query.exec_()
        query.prepare("DELETE FROM ledger_sums WHERE timestamp >= :frontier")
        query.bindValue(":frontier", frontier)
        assert query.exec_()
        self.db.commit()

        query.prepare("SELECT 1 AS type, a.id, a.timestamp, "
                       "CASE WHEN SUM(d.sum)<0 THEN 5 ELSE 1 END AS seq FROM actions AS a "
                       "LEFT JOIN action_details AS d ON a.id=d.pid WHERE timestamp >= :frontier GROUP BY a.id "
                       "UNION ALL "
                       "SELECT 2 AS type, id, timestamp, 2 AS seq FROM dividends WHERE timestamp >= :frontier "
                       "UNION ALL "
                       "SELECT 4 AS type, id, timestamp, 3 AS seq FROM transfers WHERE timestamp >= :frontier "
                       "UNION ALL "
                       "SELECT 3 AS type, id, timestamp, 4 AS seq FROM trades WHERE timestamp >= :frontier "
                       "ORDER BY timestamp, seq")
        query.bindValue(":frontier", frontier)
        query.setForwardOnly(True)
        assert query.exec_()
        seq_query = QSqlQuery(self.db)
        seq_query.prepare("INSERT INTO sequence(timestamp, type, operation_id) VALUES(:timestamp, :type, :operation_id)")
        while query.next():
            transaction_type = query.value(0)
            transaction_id = query.value(1)
            new_frontier = query.value(2)
            seq_query.bindValue(":timestamp", new_frontier)
            seq_query.bindValue(":type", transaction_type)
            seq_query.bindValue(":operation_id", transaction_id)
            assert seq_query.exec_()
            seq_id = seq_query.lastInsertId()
            if (transaction_type == TRANSACTION_ACTION):
                self.processAction(seq_id, transaction_id)
            if (transaction_type == TRANSACTION_DIVIDEND):
                self.processDividend(seq_id, transaction_id)
            if (transaction_type == TRANSACTION_TRADE):
                self.processTrade(seq_id, transaction_id)
            if (transaction_type == TRANSACTION_TRANSFER):
                self.processTransfer(seq_id, transaction_id)

    # Rebuild transaction sequence and recalculate all amounts
    # timestamp:
    # -1 - re-build from last valid operation (from ledger frontier)
    # 0 - re-build from scratch
    # any - re-build all operations after given timestamp
    def MakeFromTimestamp(self, timestamp):
        query = QSqlQuery(self.db)
        if (timestamp < 0):  # get current frontier
            assert query.exec_("SELECT ledger_frontier FROM frontier")
            query.next()
            frontier = query.value(0)
            if (frontier == ''):
                frontier = 0
        else:
            frontier = timestamp
        print(">> Re-build ledger from: ", datetime.datetime.fromtimestamp(frontier).strftime('%d/%m/%Y %H:%M:%S'))
        start_time = datetime.datetime.now()
        print(">> Started @", start_time)
        query.prepare("DELETE FROM ledger WHERE timestamp >= :frontier")
        query.bindValue(":frontier", frontier)
        assert query.exec_()
        query.prepare("DELETE FROM sequence WHERE timestamp >= :frontier")
        query.bindValue(":frontier", frontier)
        assert query.exec_()
        query.prepare("DELETE FROM ledger_sums WHERE timestamp >= :frontier")
        query.bindValue(":frontier", frontier)
        assert query.exec_()
        self.db.commit()

        assert query.exec_("PRAGMA synchronous = OFF")
        query.prepare("SELECT 1 AS type, a.id, a.timestamp, "
                      "CASE WHEN SUM(d.sum)<0 THEN 5 ELSE 1 END AS seq FROM actions AS a "
                      "LEFT JOIN action_details AS d ON a.id=d.pid WHERE timestamp >= :frontier GROUP BY a.id "
                      "UNION ALL "
                      "SELECT 2 AS type, id, timestamp, 2 AS seq FROM dividends WHERE timestamp >= :frontier "
                      "UNION ALL "
                      "SELECT 4 AS type, id, timestamp, 3 AS seq FROM transfers WHERE timestamp >= :frontier "
                      "UNION ALL "
                      "SELECT 3 AS type, id, timestamp, 4 AS seq FROM trades WHERE timestamp >= :frontier "
                      "ORDER BY timestamp, seq")
        query.bindValue(":frontier", frontier)
        query.setForwardOnly(True)
        assert query.exec_()
        seq_query = QSqlQuery(self.db)
        seq_query.prepare(
            "INSERT INTO sequence(timestamp, type, operation_id) VALUES(:timestamp, :type, :operation_id)")
        i = 0
        while query.next():
            transaction_type = query.value(0)
            transaction_id = query.value(1)
            new_frontier = query.value(2)
            seq_query.bindValue(":timestamp", new_frontier)
            seq_query.bindValue(":type", transaction_type)
            seq_query.bindValue(":operation_id", transaction_id)
            assert seq_query.exec_()
            seq_id = seq_query.lastInsertId()
            if (transaction_type == TRANSACTION_ACTION):
                self.processAction(seq_id, transaction_id)
            if (transaction_type == TRANSACTION_DIVIDEND):
                self.processDividend(seq_id, transaction_id)
            if (transaction_type == TRANSACTION_TRADE):
                self.processTrade(seq_id, transaction_id)
            if (transaction_type == TRANSACTION_TRANSFER):
                self.processTransfer(seq_id, transaction_id)
            i = i + 1
            if (i % 2500) == 0:
                print(">> Processed", i, "records at", datetime.datetime.now())
        assert query.exec_("PRAGMA synchronous = ON")

        end_time = datetime.datetime.now()
        print(">> Ended @", end_time)
        print(">> Processed", i, "records; Time:", end_time - start_time)
        print(">> New frontier:", datetime.datetime.fromtimestamp(new_frontier).strftime('%d/%m/%Y %H:%M:%S'))

    # Populate table balances with data calculated for given parameters:
    # 'timestamp' moment of time for balance
    # 'base_currency' to use for total values
    def BuildBalancesTable(self, timestamp, base_currency, active_only):
        query = QSqlQuery(self.db)
        assert query.exec_("DELETE FROM t_last_quotes")
        assert query.exec_("DELETE FROM t_last_dates")
        assert query.exec_("DELETE FROM balances_aux")
        assert query.exec_("DELETE FROM balances")

        query.prepare("INSERT INTO t_last_quotes(timestamp, active_id, quote) "
                      "SELECT MAX(timestamp) AS timestamp, active_id, quote "
                      "FROM quotes "
                      "WHERE timestamp <= :balances_timestamp "
                      "GROUP BY active_id")
        query.bindValue(":balances_timestamp", timestamp)
        assert query.exec_()

        query.prepare("INSERT INTO t_last_dates(account_id, timestamp) "
                      "SELECT account_id, MAX(timestamp) AS timestamp "
                      "FROM ledger "
                      "WHERE timestamp <= :balances_timestamp "
                      "GROUP BY account_id")
        query.bindValue(":balances_timestamp", timestamp)
        assert query.exec_()

        query.prepare("INSERT INTO balances_aux(account_type, account, currency, balance, balance_adj, unreconciled_days, active) "
                      "SELECT a.type_id AS account_type, l.account_id AS account, a.currency_id AS currency, "
                      "SUM(CASE WHEN l.book_account = 4 THEN l.amount*act_q.quote ELSE l.amount END) AS balance, "
                      "SUM(CASE WHEN l.book_account = 4 THEN l.amount*act_q.quote*cur_q.quote/cur_adj_q.quote ELSE l.amount*cur_q.quote/cur_adj_q.quote END) AS balance_adj, "
                      "(d.timestamp - a.reconciled_on)/86400 AS unreconciled_days, "
                      "a.active AS active "
                      "FROM ledger AS l "
                      "LEFT JOIN accounts AS a ON l.account_id = a.id "
                      "LEFT JOIN t_last_quotes AS act_q ON l.active_id = act_q.active_id "
                      "LEFT JOIN t_last_quotes AS cur_q ON a.currency_id = cur_q.active_id "
                      "LEFT JOIN t_last_quotes AS cur_adj_q ON cur_adj_q.active_id = :base_currency "
                      "LEFT JOIN t_last_dates AS d ON l.account_id = d.account_id "
                      "WHERE (book_account = :money_book OR book_account = :actives_book OR book_account = :liabilities_book) AND l.timestamp <= :balances_timestamp "
                      "GROUP BY l.account_id "
                      "HAVING ABS(balance)>0.0001")
        query.bindValue(":base_currency", base_currency)
        query.bindValue(":money_book", BOOK_ACCOUNT_MONEY)
        query.bindValue(":actives_book", BOOK_ACCOUNT_ACTIVES)
        query.bindValue(":liabilities_book", BOOK_ACCOUNT_LIABILITIES)
        query.bindValue(":balances_timestamp", timestamp)
        assert query.exec_()

        query.prepare("INSERT INTO balances(level1, level2, account_name, currency_name, balance, balance_adj, days_unreconciled, active) "
                    "SELECT  level1, level2, account, currency, balance, balance_adj, unreconciled_days, active "
                    "FROM ( "
                    "SELECT 0 AS level1, 0 AS level2, account_type, a.name AS account, c.name AS currency, balance, balance_adj, unreconciled_days, b.active "
                    "FROM balances_aux AS b LEFT JOIN accounts AS a ON b.account = a.id LEFT JOIN actives AS c ON b.currency = c.id "
                    "WHERE b.active >= :active_only "
                    "UNION "
                    "SELECT 0 AS level1, 1 AS level2, account_type, t.name AS account, c.name AS currency, 0 AS balance, SUM(balance_adj) AS balance_adj, 0 AS unreconciled_days, 1 AS active "
                    "FROM balances_aux AS b LEFT JOIN account_types AS t ON b.account_type = t.id LEFT JOIN actives AS c ON c.id = :base_currency "
                    "WHERE active >= :active_only "
                    "GROUP BY account_type "
                    "UNION "
                    "SELECT 1 AS level1, 0 AS level2, -1 AS account_type, 'Total' AS account, c.name AS currency, 0 AS balance, SUM(balance_adj) AS balance_adj, 0 AS unreconciled_days, 1 AS active "
                    "FROM balances_aux LEFT JOIN actives AS c ON c.id = :base_currency "
                    "WHERE active >= :active_only "
                    ") ORDER BY level1, account_type, level2"
                    )
        query.bindValue(":base_currency", base_currency)
        query.bindValue(":active_only", active_only)
        assert query.exec_()
        self.db.commit()

    def BuildActivesTable(self, timestamp, currency):
        query = QSqlQuery(self.db)
        assert query.exec_("DELETE FROM t_last_quotes")
        assert query.exec_("DELETE FROM t_last_assets")
        assert query.exec_("DELETE FROM holdings_aux")
        assert query.exec_("DELETE FROM holdings")

        assert query.prepare("INSERT INTO t_last_quotes(timestamp, active_id, quote) "
                      "SELECT MAX(timestamp) AS timestamp, active_id, quote "
                      "FROM quotes "
                      "WHERE timestamp <= :balances_timestamp "
                      "GROUP BY active_id")
        query.bindValue(":balances_timestamp", timestamp)
        assert query.exec_()

        assert query.prepare("INSERT INTO t_last_assets (id, name, total_value) "
                      "SELECT a.id, a.name, "
                      "SUM(CASE WHEN a.currency_id = l.active_id THEN l.amount ELSE (l.amount*q.quote) END) AS total_value "
                      "FROM ledger AS l "
                      "LEFT JOIN accounts AS a ON l.account_id = a.id "
                      "LEFT JOIN t_last_quotes AS q ON l.active_id = q.active_id "
                      "WHERE (l.book_account = 3 OR l.book_account = 4 OR l.book_account = 5) "
                      "AND a.type_id = 4 AND l.timestamp <= :actives_timestamp "
                      "GROUP BY a.id "
                      "HAVING ABS(total_value) > :tolerance")
        query.bindValue(":actives_timestamp", timestamp)
        query.bindValue(":tolerance", CALC_TOLERANCE)
        assert query.exec_()

        assert query.prepare("INSERT INTO holdings_aux (currency, account, asset, qty, value, quote, quote_adj, total, total_adj) "
                             "SELECT a.currency_id, l.account_id, l.active_id, sum(l.amount) AS qty, sum(l.value), "
                             "q.quote, q.quote*cur_q.quote/cur_adj_q.quote, t.total_value, t.total_value*cur_q.quote/cur_adj_q.quote "
                             "FROM ledger AS l "
                             "LEFT JOIN accounts AS a ON l.account_id = a.id "
                             "LEFT JOIN t_last_quotes AS q ON l.active_id = q.active_id "
                             "LEFT JOIN t_last_quotes AS cur_q ON a.currency_id = cur_q.active_id "
                             "LEFT JOIN t_last_quotes AS cur_adj_q ON cur_adj_q.active_id = :recalc_currency "
                             "LEFT JOIN t_last_assets AS t ON l.account_id = t.id "
                             "WHERE l.book_account = 4 AND l.timestamp <= :actives_timestamp "
                             "GROUP BY l.account_id, l.active_id "
                             "HAVING ABS(qty) > :tolerance")
        query.bindValue(":recalc_currency", currency)
        query.bindValue(":actives_timestamp", timestamp)
        query.bindValue(":tolerance", CALC_TOLERANCE)
        assert query.exec_()

        query.prepare("INSERT INTO holdings_aux (currency, account, asset, qty, value, quote, quote_adj, total, total_adj) "
                             "SELECT a.currency_id, l.account_id, l.active_id, sum(l.amount) AS qty, sum(l.value), 1, "
                             "cur_q.quote/cur_adj_q.quote, t.total_value, t.total_value*cur_q.quote/cur_adj_q.quote "
                             "FROM ledger AS l "
                             "LEFT JOIN accounts AS a ON l.account_id = a.id "
                             "LEFT JOIN t_last_quotes AS cur_q ON a.currency_id = cur_q.active_id "
                             "LEFT JOIN t_last_quotes AS cur_adj_q ON cur_adj_q.active_id = :recalc_currency "
                             "LEFT JOIN t_last_assets AS t ON l.account_id = t.id "
                             "WHERE (l.book_account = 3 OR l.book_account = 5) AND a.type_id = 4 AND l.timestamp <= :actives_timestamp "
                             "GROUP BY l.account_id, l.active_id "
                             "HAVING ABS(qty) > :tolerance")
        query.bindValue(":recalc_currency", currency)
        query.bindValue(":actives_timestamp", timestamp)
        query.bindValue(":tolerance", CALC_TOLERANCE)
        assert query.exec_()

        query.prepare("INSERT INTO holdings (level1, level2, currency, account, asset, asset_name, "
                      "qty, open, quote, share, profit_rel, profit, value, value_adj) "
                      "SELECT * FROM ( """
                      "SELECT 0 AS level1, 0 AS level2, c.name AS currency, a.name AS account, s.name AS asset, s.full_name AS asset_name, "
                      "h.qty, h.value/h.qty AS open, h.quote, 100*h.quote*h.qty/h.total AS share, "
                      "100*(h.quote*h.qty/h.value-1) AS profit_rel, h.quote*h.qty-h.value AS profit, h.qty*h.quote AS value, h.qty*h.quote_adj AS value_adj "
                      "FROM holdings_aux AS h "
                      "LEFT JOIN actives AS c ON h.currency = c.id "
                      "LEFT JOIN accounts AS a ON h.account = a.id "
                      "LEFT JOIN actives AS s ON h.asset = s.id "
                      "UNION "
                      "SELECT 0 AS level1, 1 AS level2, c.name AS currency, a.name AS account, '' AS asset, '' AS asset_name, "
                      "NULL AS qty, NULL AS open, NULL as quote, 100*h.quote*h.qty/h.total AS share, "
                      "100*(h.quote*h.qty/h.value-1) AS profit_rel, SUM(h.quote*h.qty-h.value) AS profit, SUM(h.qty*h.quote) AS value, SUM(h.qty*h.quote_adj) AS value_adj "
                      "FROM holdings_aux AS h "
                      "LEFT JOIN actives AS c ON h.currency = c.id "
                      "LEFT JOIN accounts AS a ON h.account = a.id "
                      "LEFT JOIN actives AS s ON h.asset = s.id "
                      "GROUP BY currency, account "
                      "UNION "
                      "SELECT 1 AS level1, 1 AS level2, c.name AS currency, '' AS account, '' AS asset, '' AS asset_name, "
                      "NULL AS qty, NULL AS open, NULL as quote, 100*h.quote*h.qty/h.total AS share, "
                      "100*(h.quote*h.qty/h.value-1) AS profit_rel, SUM(h.quote*h.qty-h.value) AS profit, SUM(h.qty*h.quote) AS value, SUM(h.qty*h.quote_adj) AS value_adj "
                      "FROM holdings_aux AS h "
                      "LEFT JOIN actives AS c ON h.currency = c.id "
                      "LEFT JOIN accounts AS a ON h.account = a.id "
                      "LEFT JOIN actives AS s ON h.asset = s.id "
                      "GROUP BY currency "
                      ") ORDER BY currency, level1 DESC, account, level2 DESC")
        print("ERR:", query.lastError().text())
        assert query.exec_()

# Code for verification of old ledger, probably not needed anymore
    # def PrintBalances(self, timestamp, currency_adjustment):
    #     cursor = self.db.cursor()
    #     cursor.executescript("DROP TABLE IF EXISTS temp.last_quotes;"
    #                          "DROP TABLE IF EXISTS temp.last_dates;")
    #     cursor.execute("CREATE TEMPORARY TABLE last_quotes AS "
    #                    "SELECT MAX(timestamp) AS timestamp, active_id, quote "
    #                    "FROM quotes "
    #                    "WHERE timestamp <= ? "
    #                    "GROUP BY active_id", (timestamp, ))
    #     cursor.execute("CREATE TEMPORARY TABLE last_dates AS "
    #                    "SELECT account_id, MAX(timestamp) AS timestamp "
    #                    "FROM ledger "
    #                    "WHERE timestamp <= ? "
    #                    "GROUP BY account_id;", (timestamp, ))
    #     cursor.execute("SELECT a.name AS account_name, c.name AS currency_name, "
    #                    "SUM(CASE WHEN l.book_account = 4 THEN l.amount*act_q.quote ELSE l.amount END) AS sum, "
    #                    "SUM(CASE WHEN l.book_account = 4 THEN l.amount*act_q.quote*cur_q.quote/cur_adj_q.quote ELSE l.amount*cur_q.quote/cur_adj_q.quote END) AS sum_adjusted, "
    #                    "(d.timestamp - a.reconciled_on)/86400 AS unreconciled_days, "
    #                    "a.active "
    #                    "FROM ledger AS l "
    #                    "LEFT JOIN accounts AS a ON l.account_id = a.id "
    #                    "LEFT JOIN actives AS c ON a.currency_id = c.id "
    #                    "LEFT JOIN temp.last_quotes AS act_q ON l.active_id = act_q.active_id "
    #                    "LEFT JOIN temp.last_quotes AS cur_q ON a.currency_id = cur_q.active_id "
    #                    "LEFT JOIN temp.last_quotes AS cur_adj_q ON cur_adj_q.active_id = ? "
    #                    "LEFT JOIN temp.last_dates AS d ON l.account_id = d.account_id "
    #                    "WHERE (book_account = ? OR book_account = ? OR book_account = ?) AND l.timestamp <= ? "
    #                    "GROUP BY a.name "
    #                    "HAVING ABS(sum)>0.0001",
    #                    (currency_adjustment, BOOK_ACCOUNT_MONEY, BOOK_ACCOUNT_ACTIVES, BOOK_ACCOUNT_LIABILITIES, timestamp))
    #     balances = cursor.fetchall()
    #     for row in balances:
    #         print(row)