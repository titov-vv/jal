from constants import *
from PySide2.QtSql import QSqlDatabase, QSqlQuery
from PySide2.QtCore import qDebug

class Ledger:
    def __init__(self, db):
        self.db = db

    # Populate table balances with data calculated for given parameters:
    # 'timestamp' moment of time for balance
    # 'base_currency' to use for total values
    def BuildBalancesTable(self, timestamp, base_currency, active_only):
        query = QSqlQuery(self.db)
        query.exec_("DELETE FROM t_last_quotes")
        query.exec_("DELETE FROM t_last_dates")
        query.exec_("DELETE FROM balances_aux")
        query.exec_("DELETE FROM balances;")

        query.prepare("INSERT INTO t_last_quotes(timestamp, active_id, quote) "
                      "SELECT MAX(timestamp) AS timestamp, active_id, quote "
                      "FROM quotes "
                      "WHERE timestamp <= :balances_timestamp "
                      "GROUP BY active_id")
        query.bindValue(":balances_timestamp", timestamp)
        if not query.exec_():
            print("SQL: Temp table 'last_quotes' creation failed")

        query.prepare("INSERT INTO t_last_dates(account_id, timestamp) "
                      "SELECT account_id, MAX(timestamp) AS timestamp "
                      "FROM ledger "
                      "WHERE timestamp <= :balances_timestamp "
                      "GROUP BY account_id")
        query.bindValue(":balances_timestamp", timestamp)
        if not query.exec_():
            print("SQL: Temp table 'last_dates' creation failed")

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
        if not query.exec_():
            print("SQL: Temp table 'balances_aux' creation failed")

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
        if not query.exec_():
            print("SQL: Table 'balances' creation failed")
        self.db.commit()

    def DeleteOperation(self, type, id, transfer_id):
        query = QSqlQuery(self.db)
        if (type == 1):  # Action
            if (transfer_id != 0):  # have transfer
                query.prepare("DELETE FROM actions AS a "
                              "WHERE a.id = (SELECT from_id FROM transfers AS t WHERE t.id = :transfer_id) "
                              "OR a.id = (SELECT to_id FROM transfers AS t WHERE t.id = :transfer_id)) "
                              "OR a.id = (SELECT fee_id FROM transfers AS t WHERE t.id = :transfer_id))")
                query.bindValue(":transfer_id", id)
                query.exec_()
                query.prepare("DELETE FROM transfers WHERE transfers.id = :transfer_id")
                query.bindValue(":transfer_id", id)
            else: # ordinari action
                query.prepare("DELETE FROM action_details AS a WHERE a.pid = :action_id")
                query.bindValue(":action_id", id)
                query.exec_()
                query.prepare("DELETE FROM actions WHERE actions.id = :action_id")
                query.bindValue(":action_id", id)
        elif (type == 2):  # Dividend
            query.prepare("DELETE FROM dividends WHERE dividends.id = :dividend_id")
            query.bindValue(":dividend_id", id)
        elif (type == 3):  # Trade
            query.prepare("DELETE FROM trades WHERE trades.id = :trade_id")
            query.bindValue(":trade_id", id)
        else:
            print("SQL: Unknown typeof operation for deletion")
        if not query.exec_():
            print(f"SQL: Operation type {type} and id #{id} delete failed")