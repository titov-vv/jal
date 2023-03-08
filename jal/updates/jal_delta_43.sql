BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 0;
--------------------------------------------------------------------------------
-- Fix old data
UPDATE dividends SET ex_date=0 WHERE ex_date IS NULL;
UPDATE dividends SET number='' WHERE number IS NULL;
UPDATE dividends SET tax='0' WHERE tax IS NULL;
--------------------------------------------------------------------------------
-- Correct table structure
CREATE TABLE dividends_old AS SELECT * FROM dividends;
DROP TABLE dividends;
CREATE TABLE dividends (
    id         INTEGER PRIMARY KEY UNIQUE NOT NULL,
    op_type    INTEGER NOT NULL DEFAULT (2),
    timestamp  INTEGER NOT NULL,
    ex_date    INTEGER NOT NULL DEFAULT (0),
    number     TEXT    DEFAULT ('') NOT NULL,
    type       INTEGER NOT NULL,
    account_id INTEGER REFERENCES accounts (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    asset_id   INTEGER REFERENCES assets (id) ON DELETE RESTRICT ON UPDATE CASCADE NOT NULL,
    amount     TEXT    NOT NULL DEFAULT ('0'),
    tax        TEXT    NOT NULL DEFAULT ('0'),
    note       TEXT
);
INSERT INTO dividends (id, op_type, timestamp, ex_date, number, type, account_id, asset_id, amount, tax, note)
SELECT id, op_type, timestamp, ex_date, number, type, account_id, asset_id, amount, tax, note FROM dividends_old;
DROP TABLE dividends_old;

DROP TRIGGER IF EXISTS dividends_after_delete;
CREATE TRIGGER dividends_after_delete
      AFTER DELETE ON dividends
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp;
END;

DROP TRIGGER IF EXISTS dividends_after_insert;
CREATE TRIGGER dividends_after_insert
      AFTER INSERT ON dividends
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= NEW.timestamp;
END;

DROP TRIGGER IF EXISTS dividends_after_update;
CREATE TRIGGER dividends_after_update
      AFTER UPDATE OF timestamp, account_id, asset_id, amount, tax ON dividends
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
END;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 1;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=43 WHERE name='SchemaVersion';
COMMIT;