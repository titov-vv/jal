BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 0;
--------------------------------------------------------------------------------
-- Drop outdated tables
DROP TABLE IF EXISTS t_last_quotes;
--------------------------------------------------------------------------------
-- Introduce parameterized views
CREATE TABLE view_params (
    id         INTEGER PRIMARY KEY
                       UNIQUE
                       NOT NULL,
    value_i    INTEGER DEFAULT (0),
    value_f    REAL    DEFAULT (0),
    value_t    TEXT    DEFAULT (''),
    view_name  TEXT    NOT NULL,
    param_name TEXT    NOT NULL,
    param_type TEXT    NOT NULL
);
INSERT OR REPLACE INTO view_params(id, value_i, view_name, param_name, param_type) VALUES(1, 0, "last_quotes", "timestamp", "int");
INSERT OR REPLACE INTO view_params(id, value_i, view_name, param_name, param_type) VALUES(2, 0, "last_account_value", "timestamp", "int");
INSERT OR REPLACE INTO view_params(id, value_i, view_name, param_name, param_type) VALUES(3, 0, "last_assets", "timestamp", "int");

-- Below view uses parameter 1/timestamp/int
DROP VIEW IF EXISTS last_quotes;
CREATE VIEW last_quotes AS
SELECT MAX(timestamp) AS timestamp, asset_id, currency_id, quote
FROM quotes
WHERE timestamp <= (SELECT value_i FROM view_params WHERE id=1)
GROUP BY asset_id, currency_id;

-- Below view uses parameter 2/timestamp/int
DROP VIEW IF EXISTS last_account_value;
CREATE VIEW last_account_value AS
SELECT id AS account_id, SUM(t_value) AS total_value
FROM (
   SELECT a.id, SUM(l.amount) AS t_value
   FROM ledger AS l
   LEFT JOIN accounts AS a ON l.account_id = a.id
   WHERE (l.book_account = 3 OR l.book_account = 5) AND  l.timestamp <= (SELECT value_i FROM view_params WHERE id = 2)
   GROUP BY a.id
UNION ALL
   SELECT a.id, SUM(l.amount * q.quote) AS t_value
    FROM ledger AS l
    LEFT JOIN accounts AS a ON l.account_id = a.id
    LEFT JOIN last_quotes AS q ON l.asset_id = q.asset_id AND q.currency_id = a.currency_id
    WHERE l.book_account = 4 AND l.timestamp <= (SELECT value_i FROM view_params WHERE id = 2)
    GROUP BY a.id
)
GROUP BY account_id;

-- Below view uses parameter 3/timestamp/int
DROP VIEW IF EXISTS last_assets;
CREATE VIEW last_assets AS
SELECT currency_id, account_id, asset_id, qty, value, quote
FROM (
   SELECT a.currency_id, l.account_id, l.asset_id, sum(l.amount) AS qty, sum(l.value) AS value, q.quote
   FROM ledger AS l
   LEFT JOIN accounts AS a ON l.account_id = a.id
   LEFT JOIN last_quotes AS q ON l.asset_id = q.asset_id AND q.currency_id = a.currency_id
   WHERE a.type_id = 4 AND l.book_account = 4 AND l.timestamp <= (SELECT value_i FROM view_params WHERE id=3)
   GROUP BY l.account_id, l.asset_id
UNION ALL
   SELECT a.currency_id, l.account_id, l.asset_id, sum(l.amount) AS qty, 0 AS value, 1 AS quote
   FROM ledger AS l
   LEFT JOIN accounts AS a ON l.account_id = a.id
   WHERE (l.book_account=3 OR l.book_account=5) AND a.type_id = 4 AND l.timestamp <= (SELECT value_i FROM view_params WHERE id=3)
   GROUP BY l.account_id, l.asset_id
) ORDER BY account_id, asset_id;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 1;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=36 WHERE name='SchemaVersion';
COMMIT;
