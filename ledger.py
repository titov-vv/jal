import datetime
import logging

from constants import *
from PySide2.QtCore import Qt, QDate, QDateTime
from PySide2.QtWidgets import QDialog, QMessageBox
from PySide2.QtSql import QSqlQuery
from DB.helpers import get_base_currency
from UI.ui_rebuild_window import Ui_ReBuildDialog


class RebuildDialog(QDialog, Ui_ReBuildDialog):
    def __init__(self, parent, frontier):
        QDialog.__init__(self)
        self.setupUi(self)

        self.LastRadioButton.toggle()
        self.frontier = frontier
        frontier_text = datetime.datetime.fromtimestamp(frontier).strftime('%d/%m/%Y')
        self.FrontierDateLabel.setText(frontier_text)
        self.CustomDateEdit.setDate(QDate.currentDate())

        # center dialog with respect to parent window
        x = parent.x() + parent.width()/2 - self.width()/2
        y = parent.y() + parent.height()/2 - self.height()/2
        self.setGeometry(x, y, self.width(), self.height())

    def getTimestamp(self):
        if self.LastRadioButton.isChecked():
            return self.frontier
        elif self.DateRadionButton.isChecked():
            return self.CustomDateEdit.dateTime().toSecsSinceEpoch()
        else:  # self.AllRadioButton.isChecked()
            return 0


# ===================================================================================================================
# TODO Check are there positive lines for Incomes
# TODO Check are there negative lines for Costs
# ===================================================================================================================
class Ledger:
    def __init__(self, db):
        self.db = db
        self.balances_view = None
        self.holdings_view = None
        self.balance_active_only = 1
        self.balance_currency = get_base_currency(self.db)
        self.balance_date = QDateTime.currentSecsSinceEpoch()
        self.holdings_date = QDateTime.currentSecsSinceEpoch()
        self.holdings_currency = self.balance_currency

    def setViews(self, balances, holdings):
        self.balances_view = balances
        self.holdings_view = holdings

    def setActiveBalancesOnly(self, active_only):
        if self.balance_active_only != active_only:
            self.balance_active_only = active_only
            self.UpdateBalances()

    def setBalancesDate(self, balance_date):
        if self.balance_date != balance_date:
            self.balance_date = balance_date
            self.UpdateBalances()

    def setBalancesCurrency(self, currency_id, currency_name):
        if self.balance_currency != currency_id:
            self.balance_currency = currency_id
            balances_model = self.balances_view.model()
            balances_model.setHeaderData(balances_model.fieldIndex("balance_adj"), Qt.Horizontal,
                                         "Balance, " + currency_name)
            self.UpdateBalances()

    def UpdateBalances(self):
        self.BuildBalancesTable()
        self.balances_view.model().select()

    def setHoldingsDate(self, holdings_date):
        if self.holdings_date != holdings_date:
            self.holdings_date = holdings_date
            self.UpdateHoldings()

    def setHoldingsCurrency(self, currency_id, currency_name):
        if self.holdings_currency != currency_id:
            self.holdings_currency = currency_id
            holidings_model = self.holdings_view.model()
            holidings_model.setHeaderData(holidings_model.fieldIndex("value_adj"), Qt.Horizontal,
                                          "Value, " + currency_name)
            self.UpdateHoldings()

    def UpdateHoldings(self):
        self.BuildHoldingsTable()
        holidings_model = self.holdings_view.model()
        holidings_model.select()
        for row in range(holidings_model.rowCount()):
            if holidings_model.data(holidings_model.index(row, 1)):
                self.holdings_view.setSpan(row, 3, 1, 3)
        self.holdings_view.show()

    # Returns timestamp of last operations that were calculated into ledger
    def getCurrentFrontier(self):
        query = QSqlQuery(self.db)
        assert query.exec_("SELECT ledger_frontier FROM frontier")
        query.next()
        current_frontier = query.value(0)
        if current_frontier == '':
            current_frontier = 0
        return current_frontier

    def appendTransaction(self, timestamp, seq_id, book, asset_id, account_id, amount, value=None, peer_id=None,
                          category_id=None, tag_id=None):
        query = QSqlQuery(self.db)
        query.prepare("SELECT sid, sum_amount, sum_value FROM ledger_sums "
                      "WHERE book_account = :book AND asset_id = :asset_id "
                      "AND account_id = :account_id AND sid <= :seq_id "
                      "ORDER BY sid DESC LIMIT 1")
        query.bindValue(":book", book)
        query.bindValue(":asset_id", asset_id)
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
        if value is None:
            new_value = old_value
        else:
            new_value = old_value + value
        if (abs(new_amount - old_amount) + abs(new_value - old_value)) <= (2 * Setup.CALC_TOLERANCE):
            return

        query.prepare(
            "INSERT INTO ledger (timestamp, sid, book_account, asset_id, account_id, "
            "amount, value, peer_id, category_id, tag_id) "
            "VALUES(:timestamp, :sid, :book, :asset_id, :account_id, :amount, :value, :peer_id, :category_id, :tag_id)")
        query.bindValue(":timestamp", timestamp)
        query.bindValue(":sid", seq_id)
        query.bindValue(":book", book)
        query.bindValue(":asset_id", asset_id)
        query.bindValue(":account_id", account_id)
        query.bindValue(":amount", amount)
        query.bindValue(":value", value)
        query.bindValue(":peer_id", peer_id)
        query.bindValue(":category_id", category_id)
        query.bindValue(":tag_id", tag_id)
        assert query.exec_()
        if seq_id == old_sid:
            query.prepare("UPDATE ledger_sums SET sum_amount = :new_amount, sum_value = :new_value"
                          " WHERE sid = :sid AND book_account = :book"
                          " AND asset_id = :asset_id AND account_id = :account_id")
            query.bindValue(":new_amount", new_amount)
            query.bindValue(":new_value", new_value)
            query.bindValue(":sid", seq_id)
            query.bindValue(":book", book)
            query.bindValue(":asset_id", asset_id)
            query.bindValue(":account_id", account_id)
            assert query.exec_()
        else:
            query.prepare(
                "INSERT INTO ledger_sums(sid, timestamp, book_account, asset_id, account_id, sum_amount, sum_value) "
                "VALUES(:sid, :timestamp, :book, :asset_id, :account_id, :new_amount, :new_value)")
            query.bindValue(":sid", seq_id)
            query.bindValue(":timestamp", timestamp)
            query.bindValue(":book", book)
            query.bindValue(":asset_id", asset_id)
            query.bindValue(":account_id", account_id)
            query.bindValue(":new_amount", new_amount)
            query.bindValue(":new_value", new_value)
            assert query.exec_()
        self.db.commit()

    # TODO check that condition <= is really correct for timestamp in this function
    def getAmount(self, timestamp, book, account_id, asset_id=None):
        query = QSqlQuery(self.db)
        if asset_id is None:
            query.prepare("SELECT sum_amount FROM ledger_sums WHERE book_account = :book AND account_id = :account_id "
                          "AND timestamp <= :timestamp ORDER BY sid DESC LIMIT 1")
        else:
            query.prepare("SELECT sum_amount FROM ledger_sums WHERE book_account = :book AND account_id = :account_id "
                          "AND asset_id = :asset_id AND timestamp <= :timestamp ORDER BY sid DESC LIMIT 1")
            query.bindValue(":asset_id", asset_id)
        query.bindValue(":timestamp", timestamp)
        query.bindValue(":book", book)
        query.bindValue(":account_id", account_id)
        assert query.exec_()
        if query.next():
            return float(query.value(0))
        else:
            return 0.0

    def takeCredit(self, seq_id, timestamp, account_id, currency_id, action_sum):
        money_available = self.getAmount(timestamp, BookAccount.Money, account_id)
        credit = 0
        if money_available < action_sum:
            credit = action_sum - money_available
            self.appendTransaction(timestamp, seq_id, BookAccount.Liabilities, currency_id, account_id, -credit)
        return credit

    def returnCredit(self, seq_id, timestamp, account_id, currency_id, action_sum):
        CreditValue = -1.0 * self.getAmount(timestamp, BookAccount.Liabilities, account_id)
        debit = 0
        if CreditValue > 0:
            if CreditValue >= action_sum:
                debit = action_sum
            else:
                debit = CreditValue
        if debit > 0:
            self.appendTransaction(timestamp, seq_id, BookAccount.Liabilities, currency_id, account_id, debit)
        return debit

    def processActionDetails(self, seq_id, op_id):
        query = QSqlQuery(self.db)
        query.prepare(
            "SELECT a.timestamp, a.account_id, a.peer_id, c.currency_id, d.sum as amount, d.category_id, d.tag_id "
            "FROM actions as a "
            "LEFT JOIN action_details AS d ON a.id=d.pid "
            "LEFT JOIN accounts AS c ON a.account_id = c.id "
            "WHERE pid = :pid")
        query.bindValue(":pid", op_id)
        assert query.exec_()
        while query.next():
            amount = query.value(4)
            if amount < 0:
                self.appendTransaction(query.value(0), seq_id, BookAccount.Costs, query.value(3),
                                       query.value(1), -amount, None, query.value(2), query.value(5), query.value(6))
            else:
                self.appendTransaction(query.value(0), seq_id, BookAccount.Incomes, query.value(3),
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
            self.appendTransaction(timestamp, seq_id, BookAccount.Money, currency_id, account_id,
                                   -(-action_sum - credit_sum))
        else:
            returned_sum = self.returnCredit(seq_id, timestamp, account_id, currency_id, action_sum)
            if returned_sum < action_sum:
                self.appendTransaction(timestamp, seq_id, BookAccount.Money, currency_id, account_id,
                                       (action_sum - returned_sum))
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
        if returned_sum < dividend_sum:
            self.appendTransaction(timestamp, seq_id, BookAccount.Money, currency_id, account_id,
                                   (dividend_sum - returned_sum))
        self.appendTransaction(timestamp, seq_id, BookAccount.Incomes, currency_id, account_id, -dividend_sum, None,
                               peer_id, CATEGORY_DIVIDEND)
        if tax_sum:
            self.appendTransaction(timestamp, seq_id, BookAccount.Money, currency_id, account_id, tax_sum)
            self.appendTransaction(timestamp, seq_id, BookAccount.Costs, currency_id, account_id, -tax_sum, None,
                                   peer_id, CATEGORY_TAXES)

    def processBuy(self, seq_id, timestamp, account_id, currency_id, asset_id, qty, price, coupon, fee):
        trade_sum = round(price * qty, 2) + fee + coupon
        sell_qty = 0
        sell_sum = 0
        deal_query = QSqlQuery(self.db)
        deal_query.prepare("INSERT INTO deals(account_id, asset_id, open_sid, close_sid, qty) "
                           "VALUES(:account_id, :asset_id, :open_sid, :close_sid, :qty)")
        deal_query.bindValue(":account_id", account_id)
        deal_query.bindValue(":asset_id", asset_id)
        deal_query.bindValue(":close_sid", seq_id)
        query = QSqlQuery(self.db)
        if self.getAmount(timestamp, BookAccount.Assets, account_id, asset_id) < 0:
            query.prepare("SELECT d.open_sid AS open, abs(o.qty) - SUM(d.qty) AS remainder FROM deals AS d "
                          "LEFT JOIN sequence AS os ON os.type=3 AND os.id=d.open_sid "
                          "JOIN trades AS o ON o.id = os.operation_id "
                          "WHERE d.account_id=:account_id AND d.asset_id=:asset_id "
                          "GROUP BY d.open_sid "
                          "ORDER BY d.close_sid DESC, d.open_sid DESC LIMIT 1")
            query.bindValue(":asset_id", asset_id)
            query.bindValue(":account_id", account_id)
            query.bindValue(":timestamp", timestamp)
            assert query.exec_()
            if query.next():
                reminder = query.value(1)  # value(1) = non-matched reminder of last Sell trade
                last_sid = query.value(0)  # value(0) = sid of Sell trade from the last deal
                if reminder:  # we have some not fully matched Sell trade - start from it
                    query.prepare("SELECT s.id, -t.qty, t.price FROM trades AS t "
                                  "LEFT JOIN sequence AS s ON s.type = 3 AND s.operation_id=t.id "
                                  "WHERE t.qty < 0 AND t.asset_id = :asset_id AND t.account_id = :account_id "
                                  "AND s.id < :sid AND s.id >= :last_sid")
                else:  # start from next Sell trade
                    query.prepare("SELECT s.id, -t.qty, t.price FROM trades AS t "
                                  "LEFT JOIN sequence AS s ON s.type = 3 AND s.operation_id=t.id "
                                  "WHERE t.qty < 0 AND t.asset_id = :asset_id AND t.account_id = :account_id "
                                  "AND s.id < :sid AND s.id >= :last_sid")
                query.bindValue(":last_sid", last_sid)
            else:  # There were no deals -> Select all sells
                reminder = 0
                query.prepare("SELECT s.id, -t.qty, t.price FROM trades AS t "
                              "LEFT JOIN sequence AS s ON s.type = 3 AND s.operation_id=t.id "
                              "WHERE t.qty < 0 AND t.asset_id=:asset_id AND t.account_id=:account_id AND s.id<:sid")
            query.bindValue(":asset_id", asset_id)
            query.bindValue(":sid", seq_id)
            assert query.exec_()
            while query.next():
                if reminder:
                    next_deal_qty = reminder
                    reminder = 0
                else:
                    next_deal_qty = query.value(1)  # value(1) = quantity
                if (sell_qty + next_deal_qty) >= qty:  # we are buying less or the same amount as was sold previously
                    next_deal_qty = qty - sell_qty
                deal_query.bindValue(":open_sid", query.value(0))
                deal_query.bindValue(":qty", next_deal_qty)
                assert deal_query.exec_()
                sell_qty = sell_qty + next_deal_qty
                sell_sum = sell_sum + (next_deal_qty * query.value(2))  # value(2) = price
                if sell_qty == qty:
                    break
        credit_sum = self.takeCredit(seq_id, timestamp, account_id, currency_id, trade_sum)
        if trade_sum != credit_sum:
            self.appendTransaction(timestamp, seq_id, BookAccount.Money, currency_id, account_id,
                                   -(trade_sum - credit_sum))
        if sell_qty > 0:  # Result of closed deals
            self.appendTransaction(timestamp, seq_id, BookAccount.Assets, asset_id, account_id, sell_qty, sell_sum)
            if ((price * sell_qty) - sell_sum) != 0:  # Profit if we have it
                self.appendTransaction(timestamp, seq_id, BookAccount.Incomes, currency_id, account_id,
                                       ((price * sell_qty) - sell_sum), None, None, CATEGORY_PROFIT)
        if sell_qty < qty:  # Add new long position
            self.appendTransaction(timestamp, seq_id, BookAccount.Assets, asset_id, account_id, (qty - sell_qty),
                                   (qty - sell_qty) * price)
        if coupon:
            self.appendTransaction(timestamp, seq_id, BookAccount.Costs, currency_id, account_id, coupon, None, None,
                                   CATEGORY_DIVIDEND)
        if fee:
            self.appendTransaction(timestamp, seq_id, BookAccount.Costs, currency_id, account_id, fee, None, None,
                                   CATEGORY_FEES)

    def processSell(self, seq_id, timestamp, account_id, currency_id, asset_id, qty, price, coupon, fee):
        trade_sum = round(price * qty, 2) - fee + coupon
        buy_qty = 0
        buy_sum = 0
        deal_query = QSqlQuery(self.db)
        deal_query.prepare("INSERT INTO deals(account_id, asset_id, open_sid, close_sid, qty) "
                           "VALUES(:account_id, :asset_id, :open_sid, :close_sid, :qty)")
        deal_query.bindValue(":account_id", account_id)
        deal_query.bindValue(":asset_id", asset_id)
        deal_query.bindValue(":close_sid", seq_id)
        query = QSqlQuery(self.db)
        if self.getAmount(timestamp, BookAccount.Assets, account_id, asset_id) > 0:
            query.prepare("SELECT d.open_sid AS open, abs(o.qty) - SUM(d.qty) AS remainder FROM deals AS d "
                          "LEFT JOIN sequence AS os ON os.type=3 AND os.id=d.open_sid "
                          "JOIN trades AS o ON o.id = os.operation_id "
                          "WHERE d.account_id=:account_id AND d.asset_id=:asset_id "
                          "GROUP BY d.open_sid "
                          "ORDER BY d.close_sid DESC, d.open_sid DESC LIMIT 1")
            query.bindValue(":asset_id", asset_id)
            query.bindValue(":account_id", account_id)
            query.bindValue(":timestamp", timestamp)
            assert query.exec_()
            if query.next():
                reminder = query.value(1)  # value(1) = non-matched reminder of last Sell trade
                last_sid = query.value(0)  # value(0) = sid of Buy trade from last deal
                if reminder:  # we have some not fully matched Buy trade - start from it
                    query.prepare("SELECT s.id, t.qty, t.price FROM trades AS t "
                                  "LEFT JOIN sequence AS s ON s.type = 3 AND s.operation_id=t.id "
                                  "WHERE t.qty > 0 AND t.asset_id = :asset_id AND t.account_id = :account_id "
                                  "AND s.id < :sid AND s.id >= :last_sid")
                else:  # start from next Buy trade
                    query.prepare("SELECT s.id, t.qty, t.price FROM trades AS t "
                                  "LEFT JOIN sequence AS s ON s.type = 3 AND s.operation_id=t.id "
                                  "WHERE t.qty > 0 AND t.asset_id = :asset_id AND t.account_id = :account_id "
                                  "AND s.id < :sid AND s.id >= :last_sid")
                query.bindValue(":last_sid", last_sid)
            else:  # There were no deals -> Select all purchases
                reminder = 0
                query.prepare("SELECT s.id, t.qty, t.price FROM trades AS t "
                              "LEFT JOIN sequence AS s ON s.type = 3 AND s.operation_id=t.id "
                              "WHERE t.qty > 0 AND t.asset_id=:asset_id AND t.account_id=:account_id AND s.id<:sid")
            query.bindValue(":asset_id", asset_id)
            query.bindValue(":account_id", account_id)
            query.bindValue(":sid", seq_id)
            assert query.exec_()
            while query.next():
                if reminder > 0:
                    next_deal_qty = reminder
                    reminder = 0
                else:
                    next_deal_qty = query.value(1)  # value(1) = quantity
                if (buy_qty + next_deal_qty) >= qty:  # we are selling less or the same amount as was bought previously
                    next_deal_qty = qty - buy_qty
                deal_query.bindValue(":open_sid", query.value(0))
                deal_query.bindValue(":qty", next_deal_qty)
                assert deal_query.exec_()
                buy_qty = buy_qty + next_deal_qty
                buy_sum = buy_sum + (next_deal_qty * query.value(2))  # value(2) = price
                if buy_qty == qty:
                    break
        returned_sum = self.returnCredit(seq_id, timestamp, account_id, currency_id, trade_sum)
        if returned_sum < trade_sum:
            self.appendTransaction(timestamp, seq_id, BookAccount.Money, currency_id, account_id,
                                   (trade_sum - returned_sum))
        if buy_qty > 0:  # Result of closed deals
            self.appendTransaction(timestamp, seq_id, BookAccount.Assets, asset_id, account_id, -buy_qty, -buy_sum)
            if (buy_sum - (price * buy_qty)) != 0:  # Profit if we have it
                self.appendTransaction(timestamp, seq_id, BookAccount.Incomes, currency_id, account_id,
                                       (buy_sum - (price * buy_qty)), None, None, CATEGORY_PROFIT)
        if buy_qty < qty:  # Add new short position
            self.appendTransaction(timestamp, seq_id, BookAccount.Assets, asset_id, account_id, (buy_qty - qty),
                                   (buy_qty - qty) * price)
        if coupon:
            self.appendTransaction(timestamp, seq_id, BookAccount.Incomes, currency_id, account_id, -coupon, None,
                                   None, CATEGORY_DIVIDEND)
        if fee:
            self.appendTransaction(timestamp, seq_id, BookAccount.Costs, currency_id, account_id, fee, None, None,
                                   CATEGORY_FEES)

    def processCorpAction(self):
        pass

    def processTrade(self, seq_id, trade_id):
        query = QSqlQuery(self.db)
        query.prepare(
            "SELECT a.type, t.timestamp, t.account_id, c.currency_id, t.asset_id, t.qty, t.price, t.coupon, t.fee "
            "FROM trades AS t "
            "LEFT JOIN accounts AS c ON t.account_id = c.id "
            "LEFT JOIN corp_actions AS a ON t.corp_action_id = a.id "
            "WHERE t.id = :id")
        query.bindValue(":id", trade_id)
        assert query.exec_()
        query.next()
        if query.value(0):  # if we have a corp.action instead of normal trade
            # TODO change processing of Corp.action transactions to keep money flow
            qty = query.value(5)
            if qty > 0:
                self.processBuy(seq_id, query.value(1), query.value(2), query.value(3), query.value(4), query.value(5),
                                query.value(6), query.value(7), query.value(8))
            else:
                self.processSell(seq_id, query.value(1), query.value(2), query.value(3), query.value(4),
                                 -query.value(5),
                                 query.value(6), query.value(7), query.value(8))
        else:
            qty = query.value(5)
            if qty > 0:
                self.processBuy(seq_id, query.value(1), query.value(2), query.value(3), query.value(4), query.value(5),
                                query.value(6), query.value(7), query.value(8))
            else:
                self.processSell(seq_id, query.value(1), query.value(2), query.value(3), query.value(4),
                                 -query.value(5),
                                 query.value(6), query.value(7), query.value(8))

    def processTransferOut(self, seq_id, timestamp, account_id, currency_id, amount):
        credit_sum = self.takeCredit(seq_id, timestamp, account_id, currency_id, amount)
        self.appendTransaction(timestamp, seq_id, BookAccount.Money, currency_id, account_id, -(amount - credit_sum))
        self.appendTransaction(timestamp, seq_id, BookAccount.Transfers, currency_id, account_id, amount)

    def processTransferIn(self, seq_id, timestamp, account_id, currency_id, amount):
        returned_sum = self.returnCredit(seq_id, timestamp, account_id, currency_id, amount)
        if returned_sum < amount:
            self.appendTransaction(timestamp, seq_id, BookAccount.Money, currency_id, account_id,
                                   (amount - returned_sum))
        self.appendTransaction(timestamp, seq_id, BookAccount.Transfers, currency_id, account_id, -amount)

    def processTransferFee(self, seq_id, timestamp, account_id, currency_id, fee):
        credit_sum = self.takeCredit(seq_id, timestamp, account_id, currency_id, fee)
        self.appendTransaction(timestamp, seq_id, BookAccount.Money, currency_id, account_id, -(fee - credit_sum))
        self.appendTransaction(timestamp, seq_id, BookAccount.Costs, currency_id, account_id, fee, None,
                               PEER_FINANCIAL, CATEGORY_FEES, None)

    def processTransfer(self, seq_id, transfer_id):
        query = QSqlQuery(self.db)
        query.prepare("SELECT t.type, t.timestamp, t.account_id, a.currency_id, t.amount "
                      "FROM transfers AS t "
                      "LEFT JOIN accounts AS a ON t.account_id = a.id "
                      "WHERE t.id = :id")
        query.bindValue(":id", transfer_id)
        assert query.exec_()
        query.next()
        transfer_type = query.value(0)
        if transfer_type == TRANSFER_OUT:
            self.processTransferOut(seq_id, query.value(1), query.value(2), query.value(3), -query.value(4))
        elif transfer_type == TRANSFER_IN:
            self.processTransferIn(seq_id, query.value(1), query.value(2), query.value(3), query.value(4))
        elif transfer_type == TRANSFER_FEE:
            self.processTransferFee(seq_id, query.value(1), query.value(2), query.value(3), -query.value(4))

    # TODO check if this method may be combined with the next one
    # Rebuild transaction sequence and recalculate all amounts
    # from last valid operation (from ledger frontier) until present moment
    # Methods asks for confirmation if we have more than 15 days unreconciled
    def MakeUpToDate(self):
        frontier = self.getCurrentFrontier()
        if (QDateTime.currentDateTime().toSecsSinceEpoch() - frontier) > 1296000:
            if QMessageBox().warning(None, "Confirmation",
                                     "More than 2 weeks require rebuild. Do you want to do it right now?",
                                     QMessageBox.Yes, QMessageBox.No) == QMessageBox.No:
                return

        query = QSqlQuery(self.db)
        query.prepare("DELETE FROM deals WHERE close_sid > "
                      "(SELECT coalesce(MIN(id), 0) FROM sequence WHERE timestamp >= :frontier)")
        query.bindValue(":frontier", frontier)
        assert query.exec_()
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
        seq_query.prepare(
            "INSERT INTO sequence(timestamp, type, operation_id) VALUES(:timestamp, :type, :operation_id)")
        while query.next():
            transaction_type = query.value(0)
            transaction_id = query.value(1)
            new_frontier = query.value(2)
            seq_query.bindValue(":timestamp", new_frontier)
            seq_query.bindValue(":type", transaction_type)
            seq_query.bindValue(":operation_id", transaction_id)
            assert seq_query.exec_()
            seq_id = seq_query.lastInsertId()
            if transaction_type == TransactionType.Action:
                self.processAction(seq_id, transaction_id)
            if transaction_type == TransactionType.Dividend:
                self.processDividend(seq_id, transaction_id)
            if transaction_type == TransactionType.Trade:
                self.processTrade(seq_id, transaction_id)
            if transaction_type == TransactionType.Transfer:
                self.processTransfer(seq_id, transaction_id)

    # Rebuild transaction sequence and recalculate all amounts
    # timestamp:
    # -1 - re-build from last valid operation (from ledger frontier)
    # 0 - re-build from scratch
    # any - re-build all operations after given timestamp
    def MakeFromTimestamp(self, timestamp):
        query = QSqlQuery(self.db)
        if timestamp < 0:  # get current frontier
            assert query.exec_("SELECT ledger_frontier FROM frontier")
            query.next()
            frontier = query.value(0)
            if frontier == '':
                frontier = 0
        else:
            frontier = timestamp
        new_frontier = frontier  # this variable will be updated later together with ledger updates
        logging.info(f"Re-build ledger from: {datetime.datetime.fromtimestamp(frontier).strftime('%d/%m/%Y %H:%M:%S')}")
        start_time = datetime.datetime.now()
        query.prepare("DELETE FROM deals WHERE close_sid >= "
                      "(SELECT coalesce(MIN(id), 0) FROM sequence WHERE timestamp >= :frontier)")
        query.bindValue(":frontier", frontier)
        assert query.exec_()
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
            if transaction_type == TransactionType.Action:
                self.processAction(seq_id, transaction_id)
            if transaction_type == TransactionType.Dividend:
                self.processDividend(seq_id, transaction_id)
            if transaction_type == TransactionType.Trade:
                self.processTrade(seq_id, transaction_id)
            if transaction_type == TransactionType.Transfer:
                self.processTransfer(seq_id, transaction_id)
            i = i + 1
            if (i % 1000) == 0:
                logging.info(f"Processed {i} records, current frontier: "
                             f"{datetime.datetime.fromtimestamp(new_frontier).strftime('%d/%m/%Y %H:%M:%S')}")
        assert query.exec_("PRAGMA synchronous = ON")

        end_time = datetime.datetime.now()
        logging.info(f"Ledger is complete. Processed {i} records; elapsed time: {end_time - start_time}, "
                     f"new frontier: {datetime.datetime.fromtimestamp(new_frontier).strftime('%d/%m/%Y %H:%M:%S')}")

    # Populate table balances with data calculated for given parameters:
    # 'timestamp' moment of time for balance
    # 'base_currency' to use for total values
    def BuildBalancesTable(self):
        query = QSqlQuery(self.db)
        assert query.exec_("DELETE FROM t_last_quotes")
        assert query.exec_("DELETE FROM t_last_dates")
        assert query.exec_("DELETE FROM balances_aux")
        assert query.exec_("DELETE FROM balances")

        query.prepare("INSERT INTO t_last_quotes(timestamp, asset_id, quote) "
                      "SELECT MAX(timestamp) AS timestamp, asset_id, quote "
                      "FROM quotes "
                      "WHERE timestamp <= :balances_timestamp "
                      "GROUP BY asset_id")
        query.bindValue(":balances_timestamp", self.balance_date)
        assert query.exec_()

        query.prepare("INSERT INTO t_last_dates(ref_id, timestamp) "
                      "SELECT account_id AS ref_id, MAX(timestamp) AS timestamp "
                      "FROM ledger "
                      "WHERE timestamp <= :balances_timestamp "
                      "GROUP BY ref_id")
        query.bindValue(":balances_timestamp", self.balance_date)
        assert query.exec_()

        query.prepare(
            "INSERT INTO balances_aux(account_type, account, currency, balance, "
            "balance_adj, unreconciled_days, active) "
            "SELECT a.type_id AS account_type, l.account_id AS account, a.currency_id AS currency, "
            "SUM(CASE WHEN l.book_account = 4 THEN l.amount*act_q.quote ELSE l.amount END) AS balance, "
            "SUM(CASE WHEN l.book_account = 4 THEN l.amount*act_q.quote*cur_q.quote/cur_adj_q.quote "
            "ELSE l.amount*cur_q.quote/cur_adj_q.quote END) AS balance_adj, "
            "(d.timestamp - coalesce(a.reconciled_on, 0))/86400 AS unreconciled_days, "
            "a.active AS active "
            "FROM ledger AS l "
            "LEFT JOIN accounts AS a ON l.account_id = a.id "
            "LEFT JOIN t_last_quotes AS act_q ON l.asset_id = act_q.asset_id "
            "LEFT JOIN t_last_quotes AS cur_q ON a.currency_id = cur_q.asset_id "
            "LEFT JOIN t_last_quotes AS cur_adj_q ON cur_adj_q.asset_id = :base_currency "
            "LEFT JOIN t_last_dates AS d ON l.account_id = d.ref_id "
            "WHERE (book_account = :money_book OR book_account = :assets_book OR book_account = :liabilities_book) "
            "AND l.timestamp <= :balances_timestamp "
            "GROUP BY l.account_id "
            "HAVING ABS(balance)>0.0001")
        query.bindValue(":base_currency", self.balance_currency)
        query.bindValue(":money_book", BookAccount.Money)
        query.bindValue(":assets_book", BookAccount.Assets)
        query.bindValue(":liabilities_book", BookAccount.Liabilities)
        query.bindValue(":balances_timestamp", self.balance_date)
        assert query.exec_()

        query.prepare(
            "INSERT INTO balances(level1, level2, account_name, currency_name, "
            "balance, balance_adj, days_unreconciled, active) "
            "SELECT  level1, level2, account, currency, balance, balance_adj, unreconciled_days, active "
            "FROM ( "
            "SELECT 0 AS level1, 0 AS level2, account_type, a.name AS account, c.name AS currency, "
            "balance, balance_adj, unreconciled_days, b.active "
            "FROM balances_aux AS b LEFT JOIN accounts AS a ON b.account = a.id "
            "LEFT JOIN assets AS c ON b.currency = c.id "
            "WHERE b.active >= :active_only "
            "UNION "
            "SELECT 0 AS level1, 1 AS level2, account_type, t.name AS account, c.name AS currency, 0 AS balance, "
            "SUM(balance_adj) AS balance_adj, 0 AS unreconciled_days, 1 AS active "
            "FROM balances_aux AS b LEFT JOIN account_types AS t ON b.account_type = t.id "
            "LEFT JOIN assets AS c ON c.id = :base_currency "
            "WHERE active >= :active_only "
            "GROUP BY account_type "
            "UNION "
            "SELECT 1 AS level1, 0 AS level2, -1 AS account_type, 'Total' AS account, c.name AS currency, "
            "0 AS balance, SUM(balance_adj) AS balance_adj, 0 AS unreconciled_days, 1 AS active "
            "FROM balances_aux LEFT JOIN assets AS c ON c.id = :base_currency "
            "WHERE active >= :active_only "
            ") ORDER BY level1, account_type, level2"
        )
        query.bindValue(":base_currency", self.balance_currency)
        query.bindValue(":active_only", self.balance_active_only)
        assert query.exec_()
        self.db.commit()

    def BuildHoldingsTable(self):
        query = QSqlQuery(self.db)
        assert query.exec_("DELETE FROM t_last_quotes")
        assert query.exec_("DELETE FROM t_last_assets")
        assert query.exec_("DELETE FROM holdings_aux")
        assert query.exec_("DELETE FROM holdings")

        assert query.prepare("INSERT INTO t_last_quotes(timestamp, asset_id, quote) "
                             "SELECT MAX(timestamp) AS timestamp, asset_id, quote "
                             "FROM quotes "
                             "WHERE timestamp <= :balances_timestamp "
                             "GROUP BY asset_id")
        query.bindValue(":balances_timestamp", self.holdings_date)
        assert query.exec_()

        # TODO Is account name really required in this temporary table?
        assert query.prepare("INSERT INTO t_last_assets (id, name, total_value) "
                             "SELECT a.id, a.name, "
                             "SUM(CASE WHEN a.currency_id = l.asset_id THEN l.amount "
                             "ELSE (l.amount*q.quote) END) AS total_value "
                             "FROM ledger AS l "
                             "LEFT JOIN accounts AS a ON l.account_id = a.id "
                             "LEFT JOIN t_last_quotes AS q ON l.asset_id = q.asset_id "
                             "WHERE (l.book_account = 3 OR l.book_account = 4 OR l.book_account = 5) "
                             "AND a.type_id = 4 AND l.timestamp <= :holdings_timestamp "
                             "GROUP BY a.id "
                             "HAVING ABS(total_value) > :tolerance")
        query.bindValue(":holdings_timestamp", self.holdings_date)
        query.bindValue(":tolerance", Setup.DISP_TOLERANCE)
        assert query.exec_()

        assert query.prepare(
            "INSERT INTO holdings_aux (currency, account, asset, qty, value, quote, quote_adj, total, total_adj) "
            "SELECT a.currency_id, l.account_id, l.asset_id, sum(l.amount) AS qty, sum(l.value), "
            "q.quote, q.quote*cur_q.quote/cur_adj_q.quote, t.total_value, t.total_value*cur_q.quote/cur_adj_q.quote "
            "FROM ledger AS l "
            "LEFT JOIN accounts AS a ON l.account_id = a.id "
            "LEFT JOIN t_last_quotes AS q ON l.asset_id = q.asset_id "
            "LEFT JOIN t_last_quotes AS cur_q ON a.currency_id = cur_q.asset_id "
            "LEFT JOIN t_last_quotes AS cur_adj_q ON cur_adj_q.asset_id = :recalc_currency "
            "LEFT JOIN t_last_assets AS t ON l.account_id = t.id "
            "WHERE l.book_account = 4 AND l.timestamp <= :holdings_timestamp "
            "GROUP BY l.account_id, l.asset_id "
            "HAVING ABS(qty) > :tolerance")
        query.bindValue(":recalc_currency", self.holdings_currency)
        query.bindValue(":holdings_timestamp", self.holdings_date)
        query.bindValue(":tolerance", Setup.DISP_TOLERANCE)
        assert query.exec_()

        query.prepare(
            "INSERT INTO holdings_aux (currency, account, asset, qty, value, quote, quote_adj, total, total_adj) "
            "SELECT a.currency_id, l.account_id, l.asset_id, sum(l.amount) AS qty, sum(l.value), 1, "
            "cur_q.quote/cur_adj_q.quote, t.total_value, t.total_value*cur_q.quote/cur_adj_q.quote "
            "FROM ledger AS l "
            "LEFT JOIN accounts AS a ON l.account_id = a.id "
            "LEFT JOIN t_last_quotes AS cur_q ON a.currency_id = cur_q.asset_id "
            "LEFT JOIN t_last_quotes AS cur_adj_q ON cur_adj_q.asset_id = :recalc_currency "
            "LEFT JOIN t_last_assets AS t ON l.account_id = t.id "
            "WHERE (l.book_account = 3 OR l.book_account = 5) AND a.type_id = 4 AND l.timestamp <= :holdings_timestamp "
            "GROUP BY l.account_id, l.asset_id "
            "HAVING ABS(qty) > :tolerance")
        query.bindValue(":recalc_currency", self.holdings_currency)
        query.bindValue(":holdings_timestamp", self.holdings_date)
        query.bindValue(":tolerance", Setup.DISP_TOLERANCE)
        assert query.exec_()

        query.prepare("INSERT INTO holdings (level1, level2, currency, account, asset, asset_name, "
                      "qty, open, quote, share, profit_rel, profit, value, value_adj) "
                      "SELECT * FROM ( """
                      "SELECT 0 AS level1, 0 AS level2, c.name AS currency, a.name AS account, "
                      "s.name AS asset, s.full_name AS asset_name, "
                      "h.qty, h.value/h.qty AS open, h.quote, 100*h.quote*h.qty/h.total AS share, "
                      "100*(h.quote*h.qty/h.value-1) AS profit_rel, h.quote*h.qty-h.value AS profit, "
                      "h.qty*h.quote AS value, h.qty*h.quote_adj AS value_adj "
                      "FROM holdings_aux AS h "
                      "LEFT JOIN assets AS c ON h.currency = c.id "
                      "LEFT JOIN accounts AS a ON h.account = a.id "
                      "LEFT JOIN assets AS s ON h.asset = s.id "
                      "UNION "
                      "SELECT 0 AS level1, 1 AS level2, c.name AS currency, "
                      "a.name AS account, '' AS asset, '' AS asset_name, "
                      "NULL AS qty, NULL AS open, NULL as quote, NULL AS share, "
                      "100*SUM(h.quote*h.qty-h.value)/(SUM(h.qty*h.quote)-SUM(h.quote*h.qty-h.value)) AS profit_rel, "
                      "SUM(h.quote*h.qty-h.value) AS profit, SUM(h.qty*h.quote) AS value, "
                      "SUM(h.qty*h.quote_adj) AS value_adj "
                      "FROM holdings_aux AS h "
                      "LEFT JOIN assets AS c ON h.currency = c.id "
                      "LEFT JOIN accounts AS a ON h.account = a.id "
                      "GROUP BY currency, account "
                      "UNION "
                      "SELECT 1 AS level1, 1 AS level2, c.name AS currency, c.name AS account, '' AS asset, "
                      "c.full_name AS asset_name, NULL AS qty, NULL AS open, NULL as quote, NULL AS share, "
                      "100*SUM(h.quote*h.qty-h.value)/(SUM(h.qty*h.quote)-SUM(h.quote*h.qty-h.value)) AS profit_rel, "
                      "SUM(h.quote*h.qty-h.value) AS profit, SUM(h.qty*h.quote) AS value, "
                      "SUM(h.qty*h.quote_adj) AS value_adj "
                      "FROM holdings_aux AS h "
                      "LEFT JOIN assets AS c ON h.currency = c.id "
                      "GROUP BY currency "
                      ") ORDER BY currency, level1 DESC, account, level2 DESC")
        assert query.exec_()

    def showRebuildDialog(self, parent):
        rebuild_dialog = RebuildDialog(parent, self.getCurrentFrontier())
        if rebuild_dialog.exec_():
            rebuild_date = rebuild_dialog.getTimestamp()
            self.MakeFromTimestamp(rebuild_date)