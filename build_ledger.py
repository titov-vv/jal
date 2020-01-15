import sqlite3, datetime
from constants import *
###################################################################################################
#TODO Check are there positive lines for Incomes
#TODO Check are there negative lines for Costs
#TODO Simplify Buy/Sell queries
###################################################################################################

class Ledger_Bookkeeper:
    def __init__(self, db_path):
        self.db = sqlite3.connect(db_path)

    def __del__(self):
        self.db.close()

    def GetLedgerAmountAndValue(self, timestamp, book_account, active_id, account_id):
        cursor = self.db.cursor()
        cursor.execute("SELECT sum_amount, sum_value FROM ledger_sums "
                       "WHERE book_account = ? AND active_id = ? AND account_id = ? AND timestamp <= ? "
                       "ORDER BY sid DESC LIMIT 1",
                       (book_account, active_id, account_id, timestamp))
        result = cursor.fetchone()
        if result == None:
            return (0.0, 0.0)
        else:
            return (float(result[0]), float(result[1]))

    def AppendTransaction(self, timestamp, seq_id, book_account, active_id, account_id, amount, value=None, peer_id=None, category_id=None, tag_id=None):
        cursor = self.db.cursor()
        cursor.execute("SELECT sid, sum_amount, sum_value FROM ledger_sums "
                       "WHERE book_account = ? AND active_id = ? AND account_id = ? AND sid <= ? "
                       "ORDER BY sid DESC LIMIT 1",
                       (book_account, active_id, account_id, seq_id))
        sums = cursor.fetchone()
        if sums == None:
            old_sid = -1
            old_amount = 0.0
            old_value = 0.0
        else:
            old_sid = sums[0]
            old_amount = sums[1]
            old_value = sums[2]
        new_amount = old_amount + amount
        if value == None:
            new_value = old_value
        else:
            new_value = old_value + value
        if (abs(new_amount-old_amount)+abs(new_value-old_value))<=(2*CALC_TOLERANCE):
            return
        cursor.execute(
            "INSERT INTO ledger (timestamp, sid, book_account, active_id, account_id, amount, value, peer_id, category_id, tag_id) "
            "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (timestamp, seq_id, book_account, active_id, account_id, amount, value, peer_id, category_id, tag_id))
        if seq_id == old_sid:
            cursor.execute("UPDATE ledger_sums SET sum_amount = ?, sum_value = ? WHERE sid = ? AND book_account = ? AND active_id = ? AND account_id = ?",
                           (new_amount, new_value, seq_id, book_account, active_id, account_id))
        else:
            cursor.execute("INSERT INTO ledger_sums(sid, timestamp, book_account, active_id, account_id, sum_amount, sum_value) "
                       "VALUES(?, ?, ?, ?, ?, ?, ?)",
                       (seq_id, timestamp, book_account, active_id, account_id, new_amount, new_value))
        self.db.commit()

#TODO Check possibility to combine MoneyAmount and SharesAmount methods
    def MoneyAmount(self, timestamp, book_account, account_id):
        cursor = self.db.cursor()
        cursor.execute("SELECT sum_amount FROM ledger_sums WHERE book_account = ? AND account_id = ? AND sid <= ? ORDER BY sid DESC LIMIT 1",   #TODO check that condition <= is really correct for timestamp
                       (book_account, account_id, timestamp))
        result = cursor.fetchone()
        if result == None:
            return 0.0
        else:
            return float(result[0])

    def SharesAmount(self, timestamp, active_id, account_id):
        cursor = self.db.cursor()
        cursor.execute("SELECT sum_amount FROM ledger_sums WHERE book_account = ? AND account_id = ? AND active_id = ? AND sid <= ? ORDER BY sid DESC LIMIT 1",   # TODO check that condition <= is really correct for timestamp
                       (BOOK_ACCOUNT_ACTIVES, account_id, active_id, timestamp))
        result = cursor.fetchone()
        if result == None:
            return 0.0
        else:
            return float(result[0])

    def LastDeal(self, timestamp, active_id, account_id):
        cursor = self.db.cursor()
        cursor.executescript("DROP TABLE IF EXISTS temp.influx;"
                             "DROP TABLE IF EXISTS temp.outflux;")
        cursor.execute("CREATE TEMPORARY TABLE influx AS "
                       "SELECT buy.timestamp, sum(buy_before.qty) - buy.qty AS qty_before, sum(buy_before.qty) AS qty_after "
                       "FROM trades AS buy "
                       "INNER JOIN trades AS buy_before "
                       "ON buy.timestamp >= buy_before.timestamp and buy.active_id = buy_before.active_id and buy.account_id = buy_before.account_id "
                       "WHERE buy.type = 1 and buy_before.type = 1 and buy.active_id = ? and buy.account_id = ? and buy.timestamp < ? "
                       "GROUP BY buy.timestamp, buy.qty",
                       (active_id, account_id, timestamp))
        cursor.execute("CREATE TEMPORARY TABLE outflux AS "
                       "SELECT sell.timestamp, sum(sell_before.qty) - sell.qty AS qty_before, sum(sell_before.qty) AS qty_after "
                       "FROM trades AS sell "
                       "INNER JOIN trades AS sell_before "
                       "ON sell.timestamp >= sell_before.timestamp and sell.active_id = sell_before.active_id and sell.account_id = sell_before.account_id "
                       "WHERE sell.type = -1 and sell_before.type = -1 and sell.active_id = ? and sell.account_id = ? and sell.timestamp < ? "
                       "GROUP BY sell.timestamp, sell.qty",
                       (active_id, account_id, timestamp))
        cursor.execute("SELECT o.timestamp AS sell_timestamp, i.timestamp AS buy_timestamp, "
                       "CASE WHEN i.timestamp IS NULL THEN 0 ELSE "
                       "(CASE WHEN i.qty_after < o.qty_after THEN i.qty_after ELSE o.qty_after END) - (CASE WHEN i.qty_before > o.qty_before THEN i.qty_before ELSE o.qty_before END) "
                       "END AS withdraw_qty, "
                       "CASE WHEN i.qty_after <= o.qty_after THEN 1 ELSE 0 END AS buy_full_match, "
                       "CASE WHEN i.qty_after >= o.qty_after THEN 1 ELSE 0 END AS sell_full_match, "
                       "i.qty_after - o.qty_after AS remainder "
                       "FROM temp.outflux AS o JOIN temp.influx AS i ON o.qty_after > i.qty_before AND o.qty_before < i.qty_after "
                       "ORDER BY o.timestamp DESC, i.timestamp DESC "
                       "LIMIT 1")
        result = cursor.fetchone()
        return result

    def Bookkeep_TakeCredit(self, seq_id, timestamp, account_id, currency_id, action_sum):
        money_available = self.MoneyAmount(timestamp, BOOK_ACCOUNT_MONEY, account_id)
        credit = 0
        if (money_available < action_sum):
            credit = action_sum - money_available
            self.AppendTransaction(timestamp, seq_id, BOOK_ACCOUNT_LIABILITIES, currency_id, account_id, -credit)
        return credit

    def Bookkeep_ReturnCredit(self, seq_id, timestamp, account_id, currency_id, action_sum):
        CreditValue = -1.0 * self.MoneyAmount(timestamp, BOOK_ACCOUNT_LIABILITIES, account_id)

        debit = 0
        if (CreditValue > 0):
            if (CreditValue >= action_sum):
                debit = action_sum
            else:
                debit = CreditValue
        if (debit > 0):
            self.AppendTransaction(timestamp, seq_id, BOOK_ACCOUNT_LIABILITIES, currency_id, account_id, debit)
        return debit

    def Bookkeep_ActionDetails(self, seq_id, op_id):
        cursor = self.db.cursor()
        cursor.execute("SELECT a.timestamp, a.account_id, a.peer_id, c.currency_id, (d.type*d.sum) as amount, d.category_id, d.tag_id "
                       "FROM actions as a "
                       "LEFT JOIN action_details AS d ON a.id=d.pid "
                       "LEFT JOIN accounts AS c ON a.account_id = c.id "
                       "WHERE pid = ?", (op_id, ))
        details_rows = cursor.fetchall()
        for details_row in details_rows:
            timestamp = details_row[0]
            account_id = details_row[1]
            peer_id = details_row[2]
            currency_id = details_row[3]
            amount = details_row[4]
            category_id = details_row[5]
            tag_id = details_row[6]

            if ((category_id == CATEGORY_TRANSFER_IN) or (category_id == CATEGORY_TRANSFER_OUT)):
                self.AppendTransaction(timestamp, seq_id, BOOK_ACCOUNT_TRANSFERS, currency_id, account_id, -amount)
            else: # Normal debit/credit operation
                if (amount < 0):
                    self.AppendTransaction(timestamp, seq_id, BOOK_ACCOUNT_COSTS, currency_id,
                                           account_id, -amount, None, peer_id, category_id, tag_id)
                else:
                    self.AppendTransaction(timestamp, seq_id, BOOK_ACCOUNT_INCOMES, currency_id,
                                           account_id, -amount, None, peer_id, category_id, tag_id)

    def Bookkeep_Action(self, seq_id, op_id):
        cursor = self.db.cursor()
        cursor.execute("SELECT a.timestamp, a.account_id, c.currency_id, sum(d.type*d.sum) "
                       "FROM actions AS a "
                       "LEFT JOIN action_details AS d ON a.id = d.pid "
                       "LEFT JOIN accounts AS c ON a.account_id = c.id "
                       "WHERE a.id = ? "
                       "GROUP BY a.timestamp, a.account_id, c.currency_id "
                       "ORDER BY a.timestamp, d.type desc", (op_id, ))
        action_row = cursor.fetchone()
        timestamp = action_row[0]
        account_id = action_row[1]
        currency_id = action_row[2]
        action_sum = action_row[3]

        if (action_sum < 0):
            credit_sum = self.Bookkeep_TakeCredit(seq_id, timestamp, account_id, currency_id, -action_sum)
            #TODO check for 0 values
            self.AppendTransaction(timestamp, seq_id, BOOK_ACCOUNT_MONEY, currency_id, account_id, -(-action_sum - credit_sum))
        else:
            returned_sum = self.Bookkeep_ReturnCredit(seq_id, timestamp, account_id, currency_id, action_sum)
            #TODO probably here not so strict check
            if (returned_sum < action_sum):
                self.AppendTransaction(timestamp, seq_id, BOOK_ACCOUNT_MONEY, currency_id, account_id, (action_sum - returned_sum))
        self.Bookkeep_ActionDetails(seq_id, op_id)

    def Bookkeep_Dividend(self, seq_id, op_id):
        cursor = self.db.cursor()
        cursor.execute("SELECT d.timestamp, d.account_id, c.currency_id, c.organization_id, d.sum, d.sum_tax "
                       "FROM dividends AS d "
                       "LEFT JOIN accounts AS c ON d.account_id = c.id "
                       "WHERE d.id = ?", (op_id,))
        dividend_row = cursor.fetchone()
        timestamp = dividend_row[0]
        account_id = dividend_row[1]
        currency_id = dividend_row[2]
        peer_id = dividend_row[3]
        dividend_sum = dividend_row[4]
        tax_sum = dividend_row[5]
        returned_sum = self.Bookkeep_ReturnCredit(seq_id, timestamp, account_id, currency_id, (dividend_sum - tax_sum))
        #TODO not so strict compare
        if (returned_sum < dividend_sum):
            self.AppendTransaction(timestamp, seq_id, BOOK_ACCOUNT_MONEY, currency_id, account_id, (dividend_sum - returned_sum))
        self.AppendTransaction(timestamp, seq_id, BOOK_ACCOUNT_INCOMES, currency_id, account_id, -dividend_sum, None, peer_id, CATEGORY_DIVIDEND)
        if (tax_sum > 0):
            self.AppendTransaction(timestamp, seq_id, BOOK_ACCOUNT_MONEY, currency_id, account_id, -tax_sum)
            self.AppendTransaction(timestamp, seq_id, BOOK_ACCOUNT_COSTS, currency_id, account_id, tax_sum, None, peer_id, CATEGORY_TAXES)

    def Buy(self, seq_id, timestamp, account_id, currency_id, active_id, qty, price, coupon, fee_broker, fee_exchange, trade_sum):
        sell_qty = 0
        sell_sum = 0
        cursor = self.db.cursor()
        if (self.SharesAmount(timestamp, active_id, account_id) < 0):
            last_deal = self.LastDeal(timestamp, active_id, account_id)
            if (last_deal == None):   # There were no deals -> Select all sells
                reminder = 0
                cursor.execute("SELECT t.id, t.qty, t.price FROM trades AS t WHERE t.type = -1 AND t.active_id = ? AND t.account_id = ? AND t.timestamp < ?",
                               (active_id, account_id, timestamp))
            else:
                if (last_deal[4] == 1):  # SellFullMatch is true -> Select all sells after the closed deal (i.e. last sell timestamp)
                    reminder = 0
                    cursor.execute("SELECT t.id, t.qty, t.price FROM trades AS t "
                                   "WHERE t.type = -1 AND t.active_id = ? AND t.account_id = ? "
                                   "AND t.timestamp < ? AND t.timestamp > ?",
                                   (active_id, account_id, timestamp, last_deal[0]))
                else:
                    reminder = last_deal[5]
                    cursor.execute("SELECT t.id, t.qty, t.price FROM trades AS t "
                                   "WHERE t.type = -1 AND t.active_id = ? AND t.account_id = ? "
                                   "AND t.timestamp < ? AND t.timestamp >= ?",
                                   (active_id, account_id, timestamp, last_deal[0]))
            sells = cursor.fetchall()
            for sell in sells:
                if (reminder < 0):
                    next_deal_qty = -reminder
                    reminder  = 0
                else:
                    next_deal_qty = sell[1] # quantity

                if (sell_qty + next_deal_qty) >= qty:  # we are buying less or the same amount as was sold previously
                    next_deal_qty = qty - sell_qty
                sell_qty = sell_qty + next_deal_qty
                sell_sum = sell_sum + (next_deal_qty * sell[2])  # sell[2] = price
                if (sell_qty == qty):
                    break
        credit_sum = self.Bookkeep_TakeCredit(seq_id, timestamp, account_id, currency_id, trade_sum)
        #TODO not so strict compare
        if (trade_sum != credit_sum):
            self.AppendTransaction(timestamp, seq_id, BOOK_ACCOUNT_MONEY, currency_id, account_id, -(trade_sum - credit_sum))
        if (sell_qty > 0):  # Result of closed deals
            self.AppendTransaction(timestamp, seq_id, BOOK_ACCOUNT_ACTIVES, active_id, account_id, sell_qty, sell_sum)
            if (((price * sell_qty) - sell_sum) != 0):  # Profit if we have it
                self.AppendTransaction(timestamp, seq_id, BOOK_ACCOUNT_INCOMES, currency_id, account_id, ((price * sell_qty) - sell_sum), None, None, CATEGORY_PROFIT)
        if (sell_qty < qty):   # Add new long position
            self.AppendTransaction(timestamp, seq_id, BOOK_ACCOUNT_ACTIVES, active_id, account_id, (qty - sell_qty), (qty - sell_qty) * price)
        if ((fee_broker + fee_exchange + coupon) != 0):  # Comission
            self.AppendTransaction(timestamp, seq_id, BOOK_ACCOUNT_COSTS, currency_id, account_id, (fee_broker + fee_exchange + coupon), None, None, CATEGORY_FEES)

    def Sell(self, seq_id, timestamp, account_id, currency_id, active_id, qty, price, coupon, fee_broker, fee_exchange, trade_sum):
        buy_qty = 0
        buy_sum = 0
        cursor = self.db.cursor()
        if (self.SharesAmount(timestamp, active_id, account_id) > 0):
            last_deal = self.LastDeal(timestamp, active_id, account_id)
            if (last_deal == None):   # There were no deals -> Select all purchases
                reminder = 0
                cursor.execute("SELECT t.id, t.qty, t.price FROM trades AS t WHERE t.type = 1 AND t.active_id = ? AND t.account_id = ? AND t.timestamp < ?",
                               (active_id, account_id, timestamp))
            else:
                if (last_deal[3] == 1):  # BuyFullMatch is true -> Select all purchases after the closed deal (i.e. last buy timestamp)
                    reminder = 0
                    cursor.execute("SELECT t.id, t.qty, t.price FROM trades AS t "
                                   "WHERE t.type = 1 AND t.active_id = ? AND t.account_id = ? "
                                   "AND t.timestamp < ? AND t.timestamp > ?",
                                   (active_id, account_id, timestamp, last_deal[1]))
                else:
                    reminder = last_deal[5]
                    cursor.execute("SELECT t.id, t.qty, t.price FROM trades AS t "
                                   "WHERE t.type = 1 AND t.active_id = ? AND t.account_id = ? "
                                   "AND t.timestamp < ? AND t.timestamp >= ?",
                                   (active_id, account_id, timestamp, last_deal[1]))
            purchases = cursor.fetchall()
            for purchase in purchases:
                if (reminder > 0):
                    next_deal_qty = reminder
                    reminder = 0
                else:
                    next_deal_qty = purchase[1]  # quantity

                if (buy_qty + next_deal_qty) >= qty:  # we are selling less or the same amount as was bought previously
                    next_deal_qty = qty - buy_qty
                buy_qty = buy_qty + next_deal_qty
                buy_sum = buy_sum + (next_deal_qty * purchase[2])  # sell[2] = price
                if (buy_qty == qty):
                    break
        returned_sum = self.Bookkeep_ReturnCredit(seq_id, timestamp, account_id, currency_id, trade_sum)
        if (returned_sum < trade_sum):
            self.AppendTransaction(timestamp, seq_id, BOOK_ACCOUNT_MONEY, currency_id, account_id, (trade_sum - returned_sum))
        if (buy_qty > 0):  # Result of closed deals
            self.AppendTransaction(timestamp, seq_id, BOOK_ACCOUNT_ACTIVES, active_id, account_id, -buy_qty, -buy_sum)
            if ((buy_sum - (price * buy_qty)) != 0):  # Profit if we have it
                self.AppendTransaction(timestamp, seq_id, BOOK_ACCOUNT_INCOMES, currency_id, account_id, (buy_sum - (price * buy_qty)), None, None, CATEGORY_PROFIT)
        if (buy_qty < qty):   # Add new short position
            self.AppendTransaction(timestamp, seq_id, BOOK_ACCOUNT_ACTIVES, active_id, account_id, (buy_qty - qty), (buy_qty < qty) * price)
        if (coupon > 0):
            self.AppendTransaction(timestamp, seq_id, BOOK_ACCOUNT_INCOMES, currency_id, account_id, -coupon, None, None, CATEGORY_PROFIT)
        if ((fee_broker + fee_exchange + coupon) != 0):   # Comission
            self.AppendTransaction(timestamp, seq_id, BOOK_ACCOUNT_COSTS, currency_id, account_id, (fee_broker + fee_exchange + coupon), None, None, CATEGORY_PROFIT)

    def Bookkeep_Trade(self, seq_id, id):
        cursor = self.db.cursor()
        cursor.execute("SELECT t.type, t.timestamp, t.account_id, c.currency_id, t.active_id, t.qty, t.price, t.coupon, t.fee_broker, t.fee_exchange, t.sum "
                       "FROM trades AS t "
                       "LEFT JOIN accounts AS c ON t.account_id = c.id "
                       "WHERE t.id = ?", (id,))
        trade_row = cursor.fetchone()
        type = trade_row[0]
        timestamp = trade_row[1]
        account_id = trade_row[2]
        currency_id = trade_row[3]
        active_id = trade_row[4]
        qty = trade_row[5]
        price = trade_row[6]
        coupon = trade_row[7]
        fee_broker = trade_row[8]
        fee_exchange = trade_row[9]
        trade_sum = trade_row[10]
        if (type == 1):
            self.Buy(seq_id, timestamp, account_id, currency_id, active_id, qty, price, coupon, fee_broker, fee_exchange, trade_sum)
        else:
            self.Sell(seq_id, timestamp, account_id, currency_id, active_id, qty, price, coupon, fee_broker, fee_exchange, trade_sum)

    def TransferOut(self, seq_id, timestamp, account_id, currency_id, amount):
        credit_sum = self.Bookkeep_TakeCredit(seq_id, timestamp, account_id, currency_id, amount)
        #TODO check for 0 values
        self.AppendTransaction(timestamp, seq_id, BOOK_ACCOUNT_MONEY, currency_id, account_id, -(amount - credit_sum))
        self.AppendTransaction(timestamp, seq_id, BOOK_ACCOUNT_TRANSFERS, currency_id, account_id, amount)

    def TransferIn(self, seq_id, timestamp, account_id, currency_id, amount):
        returned_sum = self.Bookkeep_ReturnCredit(seq_id, timestamp, account_id, currency_id, amount)
        # TODO probably here not so strict check
        if (returned_sum < amount):
            self.AppendTransaction(timestamp, seq_id, BOOK_ACCOUNT_MONEY, currency_id, account_id, (amount - returned_sum))
        self.AppendTransaction(timestamp, seq_id, BOOK_ACCOUNT_TRANSFERS, currency_id, account_id, -amount)

    def Fee(self, seq_id, timestamp, account_id, currency_id, fee):
        credit_sum = self.Bookkeep_TakeCredit(seq_id, timestamp, account_id, currency_id, fee)
        # TODO check for 0 values
        self.AppendTransaction(timestamp, seq_id, BOOK_ACCOUNT_MONEY, currency_id, account_id, -(fee - credit_sum))
        self.AppendTransaction(timestamp, seq_id, BOOK_ACCOUNT_COSTS, currency_id, account_id, fee, None, PEER_FINANCIAL, CATEGORY_FEES, None)

    def Bookkeep_Transfer(self, seq_id, id):
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT t.type, t.timestamp, t.account_id, a.currency_id, t.amount "
            "FROM transfers AS t "
            "LEFT JOIN accounts AS a ON t.account_id = a.id "
            "WHERE t.id = ?", (id,))
        transfer_row = cursor.fetchone()
        type = transfer_row[0]
        timestamp = transfer_row[1]
        account_id = transfer_row[2]
        currency_id = transfer_row[3]
        amount = transfer_row[4]
        if (type == TRANSFER_OUT):
            self.TransferOut(seq_id, timestamp, account_id, currency_id, -amount)
        elif (type == TRANSFER_IN):
            self.TransferIn(seq_id, timestamp, account_id, currency_id, amount)
        elif (type == TRANSFER_FEE):
            self.Fee(seq_id, timestamp, account_id, currency_id, -amount)

    # Rebuild transaction sequence and recalculate all amounts
    # timestamp:
    # -1 - re-build from last valid operation (from ledger frontier)
    # 0 - re-build from scratch
    # any - re-build all operations after given timestamp
    def RebuildLedger(self, timestamp):
        cursor = self.db.cursor()
        if (timestamp < 0): # get current frontier
            cursor.execute("SELECT ledger_frontier FROM frontier")
            result = cursor.fetchone()
            frontier = result[0]
        else:
            frontier = timestamp
        print("Re-build ledger from: ", datetime.datetime.fromtimestamp(frontier).strftime('%d/%m/%Y %H:%M:%S'))
        start_time = datetime.datetime.now()
        print("Started @", start_time)

        cursor.execute("DELETE FROM ledger WHERE timestamp >= ?", (frontier, ))
        cursor.execute("DELETE FROM sequence WHERE timestamp >= ?", (frontier, ))
        cursor.execute("DELETE FROM ledger_sums WHERE timestamp >= ?", (frontier, ))
        self.db.commit()

        cursor.execute("SELECT 1 AS type, a.id, a.timestamp, "
                       "CASE WHEN SUM(d.type*d.sum)<0 THEN 5 ELSE 1 END AS seq FROM actions AS a "
                       "LEFT JOIN action_details AS d ON a.id=d.pid WHERE timestamp >= ? GROUP BY a.id "
                       "UNION ALL "
                       "SELECT 2 AS type, id, timestamp, 2 AS seq FROM dividends WHERE timestamp >= ? "
                       "UNION ALL "
                       "SELECT 4 AS type, id, timestamp, 3 AS seq FROM transfers WHERE timestamp >= ? "
                       "UNION ALL "
                       "SELECT 3 AS type, id, timestamp, 4 AS seq FROM trades WHERE timestamp >= ? "
                       "ORDER BY timestamp, seq", (frontier, frontier, frontier, frontier))
        transaction_rows = cursor.fetchall()

        # Unsafe operations to speed-up execution
        cursor.execute("PRAGMA synchronous = OFF")
        i = 0
        new_frontier = 0
        for row in transaction_rows:
            transaction_type = row[0]
            transaction_id = row[1]
            new_frontier = row[2]
            cursor.execute("INSERT INTO sequence(timestamp, type, operation_id) VALUES(?, ?, ?)",
                           (new_frontier, transaction_type, transaction_id))
            seq_id = cursor.lastrowid
            if (transaction_type == TRANSACTION_ACTION):
                self.Bookkeep_Action(seq_id, transaction_id)
            if (transaction_type == TRANSACTION_DIVIDEND):
                self.Bookkeep_Dividend(seq_id, transaction_id)
            if (transaction_type == TRANSACTION_TRADE):
                self.Bookkeep_Trade(seq_id, transaction_id)
            if (transaction_type == TRANSACTION_TRANSFER):
                self.Bookkeep_Transfer(seq_id, transaction_id)
            i = i + 1
            if (i % 2500) == 0:
                print("Processed", i, "records at", datetime.datetime.now())
        cursor.execute("PRAGMA synchronous = ON")

        end_time = datetime.datetime.now()
        print("Ended @", end_time)
        print("Processed", i, "records; Time:", end_time-start_time)
        print("New frontier:", datetime.datetime.fromtimestamp(new_frontier).strftime('%d/%m/%Y %H:%M:%S'))

    def PrintBalances(self, timestamp, currency_adjustment):
        cursor = self.db.cursor()
        cursor.executescript("DROP TABLE IF EXISTS temp.last_quotes;"
                             "DROP TABLE IF EXISTS temp.last_dates;")
        cursor.execute("CREATE TEMPORARY TABLE last_quotes AS "
                       "SELECT MAX(timestamp) AS timestamp, active_id, quote "
                       "FROM quotes "
                       "WHERE timestamp <= ? "
                       "GROUP BY active_id", (timestamp, ))
        cursor.execute("CREATE TEMPORARY TABLE last_dates AS "
                       "SELECT account_id, MAX(timestamp) AS timestamp "
                       "FROM ledger "
                       "WHERE timestamp <= ? "
                       "GROUP BY account_id;", (timestamp, ))
        cursor.execute("SELECT a.name AS account_name, c.name AS currency_name, "
                       "SUM(CASE WHEN l.book_account = 4 THEN l.amount*act_q.quote ELSE l.amount END) AS sum, "
                       "SUM(CASE WHEN l.book_account = 4 THEN l.amount*act_q.quote*cur_q.quote/cur_adj_q.quote ELSE l.amount*cur_q.quote/cur_adj_q.quote END) AS sum_adjusted, "
                       "(d.timestamp - a.reconciled_on)/86400 AS unreconciled_days, "
                       "a.active "
                       "FROM ledger AS l "
                       "LEFT JOIN accounts AS a ON l.account_id = a.id "
                       "LEFT JOIN actives AS c ON a.currency_id = c.id "
                       "LEFT JOIN temp.last_quotes AS act_q ON l.active_id = act_q.active_id "
                       "LEFT JOIN temp.last_quotes AS cur_q ON a.currency_id = cur_q.active_id "
                       "LEFT JOIN temp.last_quotes AS cur_adj_q ON cur_adj_q.active_id = ? "
                       "LEFT JOIN temp.last_dates AS d ON l.account_id = d.account_id "
                       "WHERE (book_account = ? OR book_account = ? OR book_account = ?) AND l.timestamp <= ? "
                       "GROUP BY a.name "
                       "HAVING ABS(sum)>0.0001",
                       (currency_adjustment, BOOK_ACCOUNT_MONEY, BOOK_ACCOUNT_ACTIVES, BOOK_ACCOUNT_LIABILITIES, timestamp))
        balances = cursor.fetchall()
        for row in balances:
            print(row)
#------------------------------------------------------------------------------


