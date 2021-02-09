from jal.constants import Setup
from jal.db.helpers import executeSQL


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
    _ = executeSQL(db, "INSERT INTO t_last_assets (id, total_value) "
                            "SELECT a.id, "
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
                   "SELECT * FROM ( "
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