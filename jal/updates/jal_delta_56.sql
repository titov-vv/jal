BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 0;
--------------------------------------------------------------------------------
ALTER TABLE actions RENAME COLUMN op_type TO otype;
ALTER TABLE asset_payments RENAME COLUMN op_type TO otype;
ALTER TABLE asset_actions RENAME COLUMN op_type TO otype;
ALTER TABLE trades RENAME COLUMN op_type TO otype;
ALTER TABLE transfers RENAME COLUMN op_type TO otype;
ALTER TABLE term_deposits RENAME COLUMN op_type TO otype;
--------------------------------------------------------------------------------
ALTER TABLE ledger RENAME COLUMN op_type TO otype;
ALTER TABLE ledger RENAME COLUMN operation_id TO otype;
ALTER TABLE ledger_totals RENAME COLUMN op_type TO otype;
ALTER TABLE ledger_totals RENAME COLUMN operation_id TO otype;
DROP INDEX IF EXISTS ledger_totals_by_timestamp;
CREATE INDEX ledger_totals_by_timestamp ON ledger_totals (timestamp);
DROP INDEX IF EXISTS ledger_totals_by_operation_book;
CREATE INDEX ledger_totals_by_operation_book ON ledger_totals (otype, oid, book_account);
--------------------------------------------------------------------------------
DROP TABLE IF EXISTS trades_opened;
CREATE TABLE trades_opened (
    id            INTEGER PRIMARY KEY UNIQUE NOT NULL,
    timestamp     INTEGER NOT NULL,
    otype         INTEGER NOT NULL,
    oid           INTEGER NOT NULL,
    account_id    INTEGER REFERENCES accounts (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    asset_id      INTEGER NOT NULL REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE,
    price         TEXT    NOT NULL,
    remaining_qty TEXT    NOT NULL
);
DROP INDEX IF EXISTS open_trades_by_oid;
CREATE INDEX open_trades_by_oid ON trades_opened (timestamp, otype, oid);
--------------------------------------------------------------------------------
DROP TABLE IF EXISTS trades_closed;
CREATE TABLE trades_closed (
    id              INTEGER PRIMARY KEY UNIQUE NOT NULL,
    account_id      INTEGER NOT NULL,
    asset_id        INTEGER NOT NULL,
    open_otype      INTEGER NOT NULL,
    open_oid        INTEGER NOT NULL,
    open_timestamp  INTEGER NOT NULL,
    open_price      TEXT    NOT NULL,
    close_otype     INTEGER NOT NULL,
    close_oid       INTEGER NOT NULL,
    close_timestamp INTEGER NOT NULL,
    close_price     TEXT    NOT NULL,
    qty             TEXT    NOT NULL
);
--------------------------------------------------------------------------------
DROP VIEW IF EXISTS operation_sequence;
CREATE VIEW operation_sequence AS
SELECT m.otype, m.oid, m.timestamp, m.account_id, subtype
FROM
(
    SELECT otype, 1 AS seq, id AS oid, timestamp, account_id, 0 AS subtype FROM actions
    UNION ALL
    SELECT otype, 2 AS seq, id AS oid, timestamp, account_id, type AS subtype FROM asset_payments
    UNION ALL
    SELECT otype, 3 AS seq, id AS oid, timestamp, account_id, type AS subtype FROM asset_actions
    UNION ALL
    SELECT otype, 4 AS seq, id AS oid, timestamp, account_id, 0 AS subtype FROM trades
    UNION ALL
    SELECT otype, 5 AS seq, id AS oid, withdrawal_timestamp AS timestamp, withdrawal_account AS account_id, -1 AS subtype FROM transfers
    UNION ALL
    SELECT otype, 5 AS seq, id AS oid, withdrawal_timestamp AS timestamp, fee_account AS account_id, 0 AS subtype FROM transfers WHERE NOT fee IS NULL
    UNION ALL
    SELECT otype, 5 AS seq, id AS oid, deposit_timestamp AS timestamp, deposit_account AS account_id, 1 AS subtype FROM transfers
    UNION ALL
    SELECT td.otype, 6 AS seq, td.id AS oid, da.timestamp, td.account_id, da.id AS subtype FROM deposit_actions AS da LEFT JOIN term_deposits AS td ON da.deposit_id=td.id WHERE da.action_type<=100
) AS m
ORDER BY m.timestamp, m.seq, m.subtype, m.oid;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 1;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=56 WHERE name='SchemaVersion';
INSERT OR REPLACE INTO settings(id, name, value) VALUES (7, 'RebuildDB', 1);
COMMIT;
VACUUM;