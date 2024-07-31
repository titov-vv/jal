BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = OFF;
--------------------------------------------------------------------------------
UPDATE trades SET number='' WHERE number IS NULL;
UPDATE trades SET note='' WHERE note IS NULL;
-- Forbid NULL settlement and fee
CREATE TABLE temp_trades AS SELECT * FROM trades;
DROP TABLE IF EXISTS trades;
CREATE TABLE trades (
    oid        INTEGER     PRIMARY KEY UNIQUE NOT NULL,
    otype      INTEGER     NOT NULL DEFAULT (3),
    timestamp  INTEGER     NOT NULL,
    settlement INTEGER     NOT NULL DEFAULT (0),
    number     TEXT        NOT NULL DEFAULT (''),
    account_id INTEGER     REFERENCES accounts (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    asset_id   INTEGER     REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    qty        TEXT        NOT NULL DEFAULT ('0'),
    price      TEXT        NOT NULL DEFAULT ('0'),
    fee        TEXT        NOT NULL DEFAULT ('0'),
    note       TEXT        NOT NULL DEFAULT ('')
);
INSERT INTO trades (oid, otype, timestamp, settlement, number, account_id, asset_id, qty, price, fee, note)
  SELECT oid, otype, timestamp, settlement, number, account_id, asset_id, qty, price, fee, note FROM temp_trades;
DROP TABLE temp_trades;
CREATE TRIGGER trades_after_delete AFTER DELETE ON trades FOR EACH ROW BEGIN DELETE FROM ledger WHERE timestamp >= OLD.timestamp; DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp; END;
CREATE TRIGGER trades_after_insert AFTER INSERT ON trades FOR EACH ROW BEGIN DELETE FROM ledger WHERE timestamp >= NEW.timestamp; DELETE FROM trades_opened WHERE timestamp >= NEW.timestamp; END;
CREATE TRIGGER trades_after_update AFTER UPDATE OF timestamp, account_id, asset_id, qty, price, fee ON trades FOR EACH ROW BEGIN DELETE FROM ledger WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp; DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp; END;
--------------------------------------------------------------------------------
DROP INDEX IF EXISTS ledger_by_operation;
CREATE INDEX ledger_by_operation ON ledger (otype, oid, opart, book_account);
DROP INDEX IF EXISTS ledger_by_time;
CREATE INDEX ledger_by_time ON ledger (timestamp, asset_id, account_id);
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=58 WHERE name='SchemaVersion';
INSERT OR REPLACE INTO settings(name, value) VALUES ('RebuildDB', 1);
COMMIT;