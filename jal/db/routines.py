from jal.constants import Setup, BookAccount
from jal.db.helpers import executeSQL


# Populate table balances with data calculated for given parameters:
# 'timestamp' moment of time for balance
# 'base_currency' to use for total values
def calculateBalances(db, timestamp, currency, active_accounts_only):
    _ = executeSQL(db, "DELETE FROM t_last_quotes")
    _ = executeSQL(db, "DELETE FROM t_last_dates")
    _ = executeSQL(db, "DELETE FROM balances_aux")
    _ = executeSQL(db, "DELETE FROM balances")
    _ = executeSQL(db, "INSERT INTO t_last_quotes(timestamp, asset_id, quote) "
                            "SELECT MAX(timestamp) AS timestamp, asset_id, quote "
                            "FROM quotes "
                            "WHERE timestamp <= :balances_timestamp "
                            "GROUP BY asset_id", [(":balances_timestamp", timestamp)])
    _ = executeSQL(db, "INSERT INTO t_last_dates(ref_id, timestamp) "
                            "SELECT account_id AS ref_id, MAX(timestamp) AS timestamp "
                            "FROM ledger "
                            "WHERE timestamp <= :balances_timestamp "
                            "GROUP BY ref_id", [(":balances_timestamp", timestamp)])
    _ = executeSQL(db,
                   "INSERT INTO balances_aux(account_type, account, currency, balance, "
                   "balance_adj, unreconciled_days, active) "
                   "SELECT a.type_id AS account_type, l.account_id AS account, a.currency_id AS currency, "
                   "SUM(CASE WHEN l.book_account=4 THEN l.amount*act_q.quote ELSE l.amount END) AS balance, "
                   "SUM(CASE WHEN l.book_account=4 THEN l.amount*coalesce(act_q.quote*cur_q.quote/cur_adj_q.quote, 0) "
                   "ELSE l.amount*coalesce(cur_q.quote/cur_adj_q.quote, 0) END) AS balance_adj, "
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
                   "HAVING ABS(balance)>0.0001",
                   [(":base_currency", currency), (":money_book", BookAccount.Money),
                    (":assets_book", BookAccount.Assets), (":liabilities_book", BookAccount.Liabilities),
                    (":balances_timestamp", timestamp)])
    _ = executeSQL(db,
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
                   "SELECT 0 AS level1, 1 AS level2, account_type, t.name AS account, c.name AS currency, "
                   "0 AS balance, SUM(balance_adj) AS balance_adj, 0 AS unreconciled_days, 1 AS active "
                   "FROM balances_aux AS b LEFT JOIN account_types AS t ON b.account_type = t.id "
                   "LEFT JOIN assets AS c ON c.id = :base_currency "
                   "WHERE active >= :active_only "
                   "GROUP BY account_type "
                   "UNION "
                   "SELECT 1 AS level1, 0 AS level2, -1 AS account_type, 'Total' AS account, c.name AS currency, "
                   "0 AS balance, SUM(balance_adj) AS balance_adj, 0 AS unreconciled_days, 1 AS active "
                   "FROM balances_aux LEFT JOIN assets AS c ON c.id = :base_currency "
                   "WHERE active >= :active_only "
                   ") ORDER BY level1, account_type, level2",
                   [(":base_currency", currency), (":active_only", active_accounts_only)])
    db.commit()

def calculateHoldings(db, timestamp, currency):
    _ = executeSQL(db, "DELETE FROM t_last_quotes")
    _ = executeSQL(db, "DELETE FROM t_last_assets")
    _ = executeSQL(db, "DELETE FROM holdings_aux")
    _ = executeSQL(db, "DELETE FROM holdings")
    _ = executeSQL(db, "INSERT INTO t_last_quotes(timestamp, asset_id, quote) "
                            "SELECT MAX(timestamp) AS timestamp, asset_id, quote "
                            "FROM quotes "
                            "WHERE timestamp <= :balances_timestamp "
                            "GROUP BY asset_id", [(":balances_timestamp", timestamp)])
    # TODO Is account name really required in this temporary table?
    _ = executeSQL(db, "INSERT INTO t_last_assets (id, name, total_value) "
                            "SELECT a.id, a.name, "
                            "SUM(CASE WHEN a.currency_id = l.asset_id THEN l.amount "
                            "ELSE (l.amount*q.quote) END) AS total_value "
                            "FROM ledger AS l "
                            "LEFT JOIN accounts AS a ON l.account_id = a.id "
                            "LEFT JOIN t_last_quotes AS q ON l.asset_id = q.asset_id "
                            "WHERE (l.book_account = 3 OR l.book_account = 4 OR l.book_account = 5) "
                            "AND a.type_id = 4 AND l.timestamp <= :holdings_timestamp "
                            "GROUP BY a.id "
                            "HAVING ABS(total_value) > :tolerance",
                   [(":holdings_timestamp", timestamp), (":tolerance", Setup.DISP_TOLERANCE)])
    _ = executeSQL(db,
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
                   "HAVING ABS(qty) > :tolerance",
                   [(":recalc_currency", currency), (":holdings_timestamp", timestamp),
                    (":tolerance", Setup.DISP_TOLERANCE)])
    _ = executeSQL(db,
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
                   "HAVING ABS(qty) > :tolerance",
                   [(":recalc_currency", currency), (":holdings_timestamp", timestamp),
                    (":tolerance", Setup.DISP_TOLERANCE)])
    _ = executeSQL(db,
                   "INSERT INTO holdings (level1, level2, currency, account, asset, asset_name, "
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