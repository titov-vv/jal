BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 0;
--------------------------------------------------------------------------------
-- Add extra type to split ETFs and Funds
UPDATE asset_types SET name='ETFs' WHERE id=4;
INSERT INTO asset_types (id, name) VALUES (8, 'Funds');
--------------------------------------------------------------------------------
CREATE INDEX details_by_pid ON action_details (pid);
--------------------------------------------------------------------------------
-- Data cleanup
UPDATE action_details SET amount_alt=0 WHERE amount_alt='';
--------------------------------------------------------------------------------
-- Simplify view and handle logic in code
DROP VIEW IF EXISTS all_operations;
DROP VIEW IF EXISTS all_transactions;
DROP VIEW IF EXISTS operation_sequence;
CREATE VIEW operation_sequence AS
SELECT m.op_type, m.id, m.timestamp, m.account_id, subtype
FROM
(
    SELECT op_type, 1 AS seq, id, timestamp, account_id, 0 AS subtype FROM actions
    UNION ALL
    SELECT op_type, 2 AS seq, id, timestamp, account_id, type AS subtype FROM dividends
    UNION ALL
    SELECT op_type, 3 AS seq, id, timestamp, account_id, type AS subtype FROM corp_actions
    UNION ALL
    SELECT op_type, 4 AS seq, id, timestamp, account_id, 0 AS subtype FROM trades
    UNION ALL
    SELECT op_type, 5 AS seq, id, withdrawal_timestamp AS timestamp, withdrawal_account AS account_id, -1 AS subtype FROM transfers
    UNION ALL
    SELECT op_type, 5 AS seq, id, withdrawal_timestamp AS timestamp, fee_account AS account_id, 0 AS subtype FROM transfers WHERE NOT fee IS NULL
    UNION ALL
    SELECT op_type, 5 AS seq, id, deposit_timestamp AS timestamp, deposit_account AS account_id, 1 AS subtype FROM transfers
) AS m
ORDER BY m.timestamp, m.seq, m.subtype, m.id;

--------------------------------------------------------------------------------
DROP TABLE IF EXISTS asset_tickers;
-- Move symbol tickers to separate table
CREATE TABLE asset_tickers (
    id           INTEGER PRIMARY KEY UNIQUE NOT NULL,
    asset_id     INTEGER REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    symbol       TEXT    NOT NULL,
    currency_id  INTEGER NOT NULL REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE,
    description  TEXT    NOT NULL DEFAULT (''),
    quote_source INTEGER REFERENCES data_sources (id) ON DELETE SET NULL ON UPDATE CASCADE DEFAULT (-1),
    active       INTEGER NOT NULL DEFAULT (1)
);

-- Insert money currencies into 'asset_tickers'
INSERT INTO asset_tickers (asset_id, symbol, currency_id, description, quote_source, active)
SELECT a.id AS asset_id, a.name AS symbol, 1 AS currency_id, s.name AS description, a.src_id AS quote_source, 1 AS active
FROM assets AS a
LEFT JOIN data_sources AS s ON a.src_id=s.id
WHERE a.type_id==1
GROUP BY asset_id, currency_id;

-- Put 'old' duplicated tickers for the same ISIN
INSERT INTO asset_tickers (asset_id, symbol, currency_id, description, quote_source, active)
SELECT doubles.mid AS asset_id, old.name AS symbol, ac.currency_id AS currency_id, s.name AS description, old.src_id AS quote_source, 0 AS active
FROM (SELECT MAX(a.id) AS mid, isin, COUNT(a.id) c FROM assets AS a WHERE a.isin!='' GROUP BY a.isin HAVING c > 1) AS doubles
LEFT JOIN assets AS old ON doubles.isin=old.isin AND old.id<doubles.mid
LEFT JOIN data_sources AS s ON old.src_id=s.id
LEFT JOIN (SELECT asset_id, account_id FROM trades UNION ALL SELECT asset_id, account_id FROM dividends) AS t ON t.asset_id=old.id
LEFT JOIN accounts AS ac ON ac.id=t.account_id
GROUP BY asset_id, currency_id
HAVING currency_id IS NOT NULL;

-- Update duplicated symbols
UPDATE dividends SET asset_id=d.mid
FROM
(
SELECT old.id AS id, mid
FROM (SELECT MAX(a.id) AS mid, isin, COUNT(a.id) c FROM assets AS a WHERE a.isin!='' GROUP BY a.isin HAVING c > 1) AS doubles
LEFT JOIN assets AS old ON doubles.isin=old.isin AND old.id<doubles.mid
) AS d
WHERE d.id=asset_id;

UPDATE trades SET asset_id=d.mid
FROM
(
SELECT old.id AS id, mid
FROM (SELECT MAX(a.id) AS mid, isin, COUNT(a.id) c FROM assets AS a WHERE a.isin!='' GROUP BY a.isin HAVING c > 1) AS doubles
LEFT JOIN assets AS old ON doubles.isin=old.isin AND old.id<doubles.mid
) AS d
WHERE d.id=asset_id;

UPDATE quotes SET asset_id=d.mid
FROM
(
SELECT old.id AS id, mid
FROM (SELECT MAX(a.id) AS mid, isin, COUNT(a.id) c FROM assets AS a WHERE a.isin!='' GROUP BY a.isin HAVING c > 1) AS doubles
LEFT JOIN assets AS old ON doubles.isin=old.isin AND old.id<doubles.mid
) AS d
WHERE d.id=asset_id;

UPDATE corp_actions SET asset_id=d.mid
FROM
(
SELECT old.id AS id, mid
FROM (SELECT MAX(a.id) AS mid, isin, COUNT(a.id) c FROM assets AS a WHERE a.isin!='' GROUP BY a.isin HAVING c > 1) AS doubles
LEFT JOIN assets AS old ON doubles.isin=old.isin AND old.id<doubles.mid
) AS d
WHERE d.id=asset_id;

UPDATE corp_actions SET asset_id_new=d.mid
FROM
(
SELECT old.id AS id, mid
FROM (SELECT MAX(a.id) AS mid, isin, COUNT(a.id) c FROM assets AS a WHERE a.isin!='' GROUP BY a.isin HAVING c > 1) AS doubles
LEFT JOIN assets AS old ON doubles.isin=old.isin AND old.id<doubles.mid
) AS d
WHERE d.id=asset_id_new;

-- Delete duplicates for the same ISIN and keep only the last one
DELETE FROM assets WHERE id IN
(
SELECT old.id AS id
FROM (SELECT MAX(a.id) AS mid, isin, COUNT(a.id) c FROM assets AS a WHERE a.isin!='' GROUP BY a.isin HAVING c > 1) AS doubles
LEFT JOIN assets AS old ON doubles.isin=old.isin AND old.id<doubles.mid
);

-- Delete symbols that were duplicated and already added to asset_tickers
DELETE FROM assets WHERE id IN (
SELECT a.id FROM assets AS a
LEFT JOIN trades AS t ON a.id=t.asset_id
LEFT JOIN dividends AS d ON a.id=d.asset_id
LEFT JOIN corp_actions AS c1 ON a.id=c1.asset_id
LEFT JOIN corp_actions AS c2 ON a.id=c2.asset_id_new
WHERE a.type_id!=1 AND t.id IS NULL AND d.id IS NULL AND c1.id IS NULL AND c2.id IS NULL);

-- Insert symbols other than currencies
INSERT INTO asset_tickers (asset_id, symbol, currency_id, description, quote_source, active)
SELECT a.id, a.name, coalesce(ac.currency_id, ac2.currency_id) AS currency, s.name, a.src_id, 1
FROM assets AS a
LEFT JOIN data_sources AS s ON a.src_id=s.id
LEFT JOIN trades AS t ON t.asset_id=a.id
LEFT JOIN accounts AS ac ON ac.id=t.account_id
LEFT JOIN corp_actions AS c ON c.asset_id=a.id OR c.asset_id_new=a.id
LEFT JOIN accounts AS ac2 ON ac2.id=c.account_id
WHERE a.type_id!=1
GROUP BY a.id, currency;

--------------------------------------------------------------------------------
DROP TABLE IF EXISTS asset_data;
CREATE TABLE asset_data (
    id       INTEGER PRIMARY KEY UNIQUE NOT NULL,
    asset_id INTEGER NOT NULL REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE,
    datatype INTEGER NOT NULL,
    value    TEXT    NOT NULL
);

DROP INDEX IF EXISTS asset_data_uniqueness;
CREATE UNIQUE INDEX asset_data_uniqueness ON asset_data ( asset_id, datatype);


-- Insert registration codes
INSERT INTO asset_data (asset_id, datatype, value)
SELECT asset_id, 1 AS datatype, reg_code AS value
FROM asset_reg_id
WHERE reg_code!='';

DROP TABLE asset_reg_id;

-- Insert expiration dates
INSERT INTO asset_data (asset_id, datatype, value)
SELECT id AS asset_id, 2 AS datatype, expiry AS value
FROM assets
WHERE expiry!=0;

--------------------------------------------------------------------------------
-- Update currencies view to take symbol from asset_tickers
DROP VIEW IF EXISTS currencies;

CREATE VIEW currencies AS
SELECT a.id, s.symbol
FROM assets AS a
LEFT JOIN asset_tickers AS s ON s.asset_id = a.id AND  s.active = 1
WHERE a.type_id = 1;

-- Link asset symbol from asset_tickers, no assets
DROP VIEW IF EXISTS deals_ext;
CREATE VIEW deals_ext AS
    SELECT d.account_id,
           ac.name AS account,
           d.asset_id,
           at.symbol AS asset,
           open_timestamp,
           close_timestamp,
           open_price,
           close_price,
           d.qty AS qty,
           coalesce(ot.fee * abs(d.qty / ot.qty), 0) + coalesce(ct.fee * abs(d.qty / ct.qty), 0) AS fee,
           d.qty * (close_price - open_price ) - (coalesce(ot.fee * abs(d.qty / ot.qty), 0) + coalesce(ct.fee * abs(d.qty / ct.qty), 0) ) AS profit,
           coalesce(100 * (d.qty * (close_price - open_price ) - (coalesce(ot.fee * abs(d.qty / ot.qty), 0) + coalesce(ct.fee * abs(d.qty / ct.qty), 0) ) ) / abs(d.qty * open_price ), 0) AS rel_profit,
           coalesce(oca.type, -cca.type) AS corp_action
    FROM deals AS d
          -- Get more information about trade/corp.action that opened the deal
           LEFT JOIN trades AS ot ON ot.id=d.open_op_id AND ot.op_type=d.open_op_type
           LEFT JOIN corp_actions AS oca ON oca.id=d.open_op_id AND oca.op_type=d.open_op_type
          -- Collect value of stock that was accumulated before corporate action
           LEFT JOIN ledger AS ols ON ols.op_type=d.open_op_type AND ols.operation_id=d.open_op_id AND ols.asset_id = d.asset_id AND ols.value_acc != 0
          -- Get more information about trade/corp.action that opened the deal
           LEFT JOIN trades AS ct ON ct.id=d.close_op_id AND ct.op_type=d.close_op_type
           LEFT JOIN corp_actions AS cca ON cca.id=d.close_op_id AND cca.op_type=d.close_op_type
          -- "Decode" account and asset
           LEFT JOIN accounts AS ac ON d.account_id = ac.id
           LEFT JOIN asset_tickers AS at ON d.asset_id = at.asset_id AND ac.currency_id=at.currency_id
     -- drop cases where deal was opened and closed with corporate action
     WHERE NOT (d.open_op_type = 5 AND d.close_op_type = 5)
     ORDER BY close_timestamp, open_timestamp;
--------------------------------------------------------------------------------
-- Modify assets table
DROP INDEX IF EXISTS asset_name_isin_idx;
ALTER TABLE assets DROP COLUMN src_id;
ALTER TABLE assets DROP COLUMN expiry;
ALTER TABLE assets DROP COLUMN name;
ALTER TABLE assets ADD COLUMN base_asset INTEGER REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE;
--------------------------------------------------------------------------------
DROP VIEW IF EXISTS assets_ext;
CREATE VIEW assets_ext AS
    SELECT a.id,
           a.type_id,
           t.symbol,
           a.full_name,
           a.isin,
           t.currency_id,
           a.country_id,
           t.quote_source
    FROM assets a
    LEFT JOIN asset_tickers t ON a.id = t.asset_id
    WHERE t.active = 1
    ORDER BY a.id;

-- Deletion should happen on base table
DROP TRIGGER IF EXISTS on_asset_ext_delete;
CREATE TRIGGER on_asset_ext_delete
    INSTEAD OF DELETE ON assets_ext FOR EACH ROW WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM assets WHERE id = OLD.id;
END;
--------------------------------------------------------------------------------
-- Update quotes table
-- Remove duplicated quotes
DELETE FROM quotes WHERE rowid NOT IN (SELECT MAX(rowid) FROM quotes GROUP BY asset_id, timestamp);
CREATE TABLE _temp_quotes_table AS SELECT * FROM quotes WHERE NOT quote IS NULL;

CREATE TABLE _temp_currency_table AS
SELECT DISTINCT t.asset_id, a.currency_id FROM
(SELECT asset_id, account_id FROM trades) t
LEFT JOIN accounts a ON t.account_id=a.id
ORDER BY asset_id;

DROP TABLE quotes;
CREATE TABLE quotes (
    id          INTEGER PRIMARY KEY UNIQUE NOT NULL,
    timestamp   INTEGER NOT NULL,
    asset_id    INTEGER REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    currency_id INTEGER REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    quote       REAL    NOT NULL DEFAULT (0)
);
CREATE UNIQUE INDEX unique_quotations ON quotes (asset_id, currency_id, timestamp);

INSERT INTO quotes (id, timestamp, asset_id, currency_id, quote)
SELECT q.id, q.timestamp, q.asset_id, coalesce(c.currency_id, 1), q.quote
FROM _temp_quotes_table q
LEFT JOIN _temp_currency_table c ON q.asset_id=c.asset_id;

DROP TABLE _temp_quotes_table;
DROP TABLE _temp_currency_table;

--------------------------------------------------------------------------------
-- Create new data source
INSERT INTO data_sources (id, name) VALUES (5, 'LSE');
INSERT INTO data_sources (id, name) VALUES (6, 'Frankfurt Borse');
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 1;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=32 WHERE name='SchemaVersion';
INSERT OR REPLACE INTO settings(id, name, value) VALUES (7, 'RebuildDB', 1);
COMMIT;
