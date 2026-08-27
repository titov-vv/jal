PRAGMA foreign_keys = OFF;
BEGIN TRANSACTION;
--------------------------------------------------------------------------------
-- RESIDENCE REPLACES BASE CURRENCY
-- 'base_currency' kept the history of the reporting currency: one row per change, in force until the
-- next one. That is the shape a residence history has as well, and the two are usually the same event -
-- the user moved country, which changed the jurisdiction, the wall clock and the reporting currency at
-- once. So the table is renamed and given the two facts it was missing rather than a second table being
-- built beside it.
--
-- The two new columns start empty on every row that exists. A migration cannot know where its user
-- lived, and a tax jurisdiction is not a thing to guess quietly - so 'country_id' stays 0 and 'timezone'
-- stays empty until the user states them, and both read as "this row doesn't say, the last one that did
-- still holds".
--
-- The table is re-created instead of ALTERed because ADD COLUMN cannot add a column with a REFERENCES
-- clause, and a database upgraded here must end up with exactly the schema a new one is created with.
DROP TABLE IF EXISTS residence;
CREATE TABLE residence (
    id              INTEGER PRIMARY KEY UNIQUE NOT NULL,
    since_timestamp INTEGER NOT NULL UNIQUE,
    currency_id     INTEGER NOT NULL REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE,
    country_id      INTEGER NOT NULL DEFAULT (0) REFERENCES countries (id) ON DELETE SET DEFAULT ON UPDATE CASCADE,
    timezone        TEXT    NOT NULL DEFAULT ('')
);
INSERT INTO residence (id, since_timestamp, currency_id)
    SELECT id, since_timestamp, currency_id FROM base_currency;
DROP TABLE base_currency;
--------------------------------------------------------------------------------
DELETE FROM settings WHERE name IN ('DlgGeometry_Base currency', 'DlgViewState_Base currency');
INSERT OR REPLACE INTO settings(name, value) VALUES('DlgGeometry_Residence', '');
INSERT OR REPLACE INTO settings(name, value) VALUES('DlgViewState_Residence', '');
--------------------------------------------------------------------------------
DROP TRIGGER IF EXISTS asset_payments_after_delete;
DROP TRIGGER IF EXISTS asset_payments_after_insert;
DROP TRIGGER IF EXISTS asset_payments_after_update;
DROP TRIGGER IF EXISTS asset_action_after_delete;
DROP TRIGGER IF EXISTS asset_action_after_insert;
DROP TRIGGER IF EXISTS asset_action_after_update;
DROP TRIGGER IF EXISTS asset_result_after_delete;
DROP TRIGGER IF EXISTS asset_result_after_insert;
DROP TRIGGER IF EXISTS asset_result_after_update;
DROP VIEW IF EXISTS operation_sequence;
--------------------------------------------------------------------------------
CREATE TABLE asset_payments_new (
    oid        INTEGER PRIMARY KEY UNIQUE NOT NULL,
    otype      INTEGER NOT NULL DEFAULT (2),
    timestamp  INTEGER NOT NULL,
    timestamp_day_only INTEGER NOT NULL DEFAULT (0),
    ex_date    INTEGER NOT NULL DEFAULT (0),
    number     TEXT    NOT NULL DEFAULT (''),
    type       INTEGER NOT NULL,
    account_id INTEGER REFERENCES accounts (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    symbol_id  INTEGER REFERENCES asset_symbol (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    amount     TEXT    NOT NULL DEFAULT ('0'),
    tax        TEXT    NOT NULL DEFAULT ('0'),
    price      TEXT    NOT NULL DEFAULT (''),
    note       TEXT
);
INSERT INTO asset_payments_new (oid, otype, timestamp, ex_date, number, type, account_id, symbol_id, amount, tax, note)
    SELECT oid, otype, timestamp, ex_date, number, type, account_id, symbol_id, amount, tax, note FROM asset_payments;
DROP TABLE asset_payments;
ALTER TABLE asset_payments_new RENAME TO asset_payments;
--------------------------------------------------------------------------------
-- Move the price of a stock divident or vesting into the payment record
UPDATE asset_payments SET price = COALESCE(
    (SELECT q.quote FROM quotes AS q
     JOIN asset_symbol AS s ON s.id = asset_payments.symbol_id
     JOIN accounts AS a ON a.id = asset_payments.account_id
     WHERE q.asset_id = s.asset_id AND q.currency_id = a.currency_id
       AND q.timestamp = asset_payments.timestamp), '')
    WHERE type IN (3, 4);   -- AssetPayment.StockDividend, AssetPayment.StockVesting
-- The quote that was consumed is deleted: an instant stamped in the middle of a day is not a point of a price
-- series, and left there it would go on shadowing the day around it. Only the rows a payment actually took its
-- price from, and the series they sat in is re-downloadable in any case.
DELETE FROM quotes WHERE id IN (
    SELECT q.id FROM quotes AS q
    JOIN asset_symbol AS s ON s.asset_id = q.asset_id
    JOIN asset_payments AS p ON p.symbol_id = s.id AND p.timestamp = q.timestamp AND p.type IN (3, 4)
    JOIN accounts AS a ON a.id = p.account_id AND a.currency_id = q.currency_id
    WHERE p.price <> '');
--------------------------------------------------------------------------------
CREATE TABLE asset_actions_new (
    oid        INTEGER     PRIMARY KEY UNIQUE NOT NULL,
    otype      INTEGER     NOT NULL DEFAULT (5),
    timestamp  INTEGER     NOT NULL,
    timestamp_day_only INTEGER NOT NULL DEFAULT (0),
    number     TEXT        DEFAULT (''),
    account_id INTEGER     REFERENCES accounts (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    type       INTEGER     NOT NULL,
    symbol_id  INTEGER     REFERENCES asset_symbol (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    qty        TEXT        NOT NULL,
    note       TEXT
);
INSERT INTO asset_actions_new (oid, otype, timestamp, number, account_id, type, symbol_id, qty, note)
    SELECT oid, otype, timestamp, number, account_id, type, symbol_id, qty, note FROM asset_actions;
DROP TABLE asset_actions;
ALTER TABLE asset_actions_new RENAME TO asset_actions;
--------------------------------------------------------------------------------
-- Recreate everything that was dropped above
CREATE TRIGGER asset_payments_after_delete AFTER DELETE ON asset_payments FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp;
END;
CREATE TRIGGER asset_payments_after_insert AFTER INSERT ON asset_payments FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= NEW.timestamp;
END;
CREATE TRIGGER asset_payments_after_update AFTER UPDATE OF timestamp, type, account_id, symbol_id, amount, tax, price ON asset_payments FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
END;
CREATE TRIGGER asset_action_after_delete AFTER DELETE ON asset_actions FOR EACH ROW
BEGIN
    DELETE FROM asset_action_results WHERE action_id = OLD.oid;
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp;
END;
CREATE TRIGGER asset_action_after_insert AFTER INSERT ON asset_actions FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= NEW.timestamp;
END;
CREATE TRIGGER asset_action_after_update AFTER UPDATE OF timestamp, account_id, type, symbol_id, qty ON asset_actions FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp  OR timestamp >= NEW.timestamp;
END;
CREATE TRIGGER asset_result_after_delete AFTER DELETE ON asset_action_results FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= (SELECT timestamp FROM asset_actions WHERE oid = OLD.action_id);
END;
CREATE TRIGGER asset_result_after_insert AFTER INSERT ON asset_action_results FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= (SELECT timestamp FROM asset_actions WHERE oid = NEW.action_id);
END;
CREATE TRIGGER asset_result_after_update AFTER UPDATE OF symbol_id, qty, value_share ON asset_action_results FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= (SELECT timestamp FROM asset_actions WHERE oid = OLD.action_id);
END;
CREATE VIEW operation_sequence AS SELECT m.otype, m.oid, opart, m.timestamp, m.account_id
FROM
(
    SELECT otype, 1 AS seq, oid, 0 AS opart, timestamp, account_id FROM actions
    UNION ALL
    SELECT otype, 2 AS seq, oid, 0 AS opart, timestamp, account_id FROM asset_payments
    UNION ALL
    SELECT otype, 3 AS seq, oid, 0 AS opart, timestamp, account_id FROM asset_actions
    UNION ALL
    SELECT otype, 4 AS seq, oid, 0 AS opart, timestamp, account_id FROM trades
    UNION ALL
    SELECT otype, 5 AS seq, oid, -1 AS opart, withdrawal_timestamp AS timestamp, withdrawal_account AS account_id FROM transfers WHERE NOT withdrawal_account IS NULL
    UNION ALL
    SELECT otype, 5 AS seq, oid, 0 AS opart, withdrawal_timestamp AS timestamp, fee_account AS account_id FROM transfers WHERE NOT fee IS NULL
    UNION ALL
    SELECT otype, 5 AS seq, oid, 1 AS opart, deposit_timestamp AS timestamp, deposit_account AS account_id FROM transfers WHERE NOT deposit_account IS NULL
    UNION ALL
    SELECT otype, 6 AS seq, oid, 0 AS opart, timestamp, account_id FROM conversions
    UNION ALL
    SELECT otype, 7 AS seq, oid, 0 AS opart, timestamp, account_id FROM swaps WHERE in_account_id IS NULL OR in_account_id=account_id
    UNION ALL
    SELECT otype, 7 AS seq, oid, -1 AS opart, timestamp, account_id FROM swaps WHERE NOT in_account_id IS NULL AND in_account_id<>account_id
    UNION ALL
    SELECT otype, 7 AS seq, oid, 1 AS opart, COALESCE(in_timestamp, timestamp) AS timestamp, in_account_id AS account_id FROM swaps WHERE NOT in_account_id IS NULL AND in_account_id<>account_id
    UNION ALL
    SELECT otype, 8 AS seq, oid, -1 AS opart, out_timestamp AS timestamp, out_account_id AS account_id FROM bridges
    UNION ALL
    SELECT otype, 8 AS seq, oid, 0 AS opart, out_timestamp AS timestamp, out_account_id AS account_id FROM bridges WHERE NOT fee_qty IS NULL
    UNION ALL
    SELECT otype, 8 AS seq, oid, 1 AS opart, in_timestamp AS timestamp, in_account_id AS account_id FROM bridges WHERE NOT in_account_id IS NULL
) AS m
ORDER BY m.timestamp, m.seq, m.opart, m.oid;  -- First sort by sequence and part to enforce right operation processing order
--------------------------------------------------------------------------------
-- Every corporate action is effective on a date
UPDATE asset_actions SET timestamp_day_only=1;
-- Payments keep the meaning their value carried before this column existed: midnight is the day a source gave
-- without a time, and it is read as such everywhere today. Marked by value rather than by source because the
-- source is exactly what is not recorded.
UPDATE asset_payments SET timestamp_day_only=1 WHERE ((timestamp % 86400) + 86400) % 86400 = 0;
-- The end-of-day stamps IBKR puts on an accounting day, which until now only the importer could recognise.
-- Only payments are marked by them: a dividend, an interest or a fee is not an event with a time of day, and
-- three exact seconds out of the day are not a time any other source writes by accident. The same values on a
-- spending or a trade ARE a plausible evening and are deliberately left alone.
UPDATE asset_payments SET timestamp_day_only=1
    WHERE ((timestamp % 86400) + 86400) % 86400 IN (73200, 73440, 73500);
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=65 WHERE name='SchemaVersion';
COMMIT;
PRAGMA foreign_keys = ON;