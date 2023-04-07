BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 0;
--------------------------------------------------------------------------------
-- Add new 'number' field into transfers table
CREATE TABLE transfers_old AS SELECT * FROM transfers;
DROP TABLE IF EXISTS transfers;
CREATE TABLE transfers (
    id                   INTEGER     PRIMARY KEY UNIQUE NOT NULL,
    op_type              INTEGER     NOT NULL DEFAULT (4),
    withdrawal_timestamp INTEGER     NOT NULL,
    withdrawal_account   INTEGER     NOT NULL REFERENCES accounts (id) ON DELETE CASCADE ON UPDATE CASCADE,
    withdrawal           TEXT        NOT NULL,
    deposit_timestamp    INTEGER     NOT NULL,
    deposit_account      INTEGER     NOT NULL REFERENCES accounts (id) ON DELETE CASCADE ON UPDATE CASCADE,
    deposit              TEXT        NOT NULL,
    fee_account          INTEGER     REFERENCES accounts (id) ON DELETE CASCADE ON UPDATE CASCADE,
    fee                  TEXT,
    number               TEXT        NOT NULL DEFAULT (''),
    asset                INTEGER     REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE,
    note                 TEXT
);
INSERT INTO transfers (id, op_type, withdrawal_timestamp, withdrawal_account, withdrawal, deposit_timestamp, deposit_account, deposit, fee_account, fee, asset, note)
SELECT id, op_type, withdrawal_timestamp, withdrawal_account, withdrawal, deposit_timestamp, deposit_account, deposit, fee_account, fee, asset, note FROM transfers_old;
DROP TABLE transfers_old;

DROP TRIGGER IF EXISTS transfers_after_delete;
CREATE TRIGGER transfers_after_delete
      AFTER DELETE ON transfers
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.withdrawal_timestamp OR timestamp >= OLD.deposit_timestamp;
END;

DROP TRIGGER IF EXISTS transfers_after_insert;
CREATE TRIGGER transfers_after_insert
      AFTER INSERT ON transfers
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= NEW.withdrawal_timestamp OR timestamp >= NEW.deposit_timestamp;
END;

DROP TRIGGER IF EXISTS transfers_after_update;
CREATE TRIGGER transfers_after_update
      AFTER UPDATE OF withdrawal_timestamp, deposit_timestamp, withdrawal_account, deposit_account, fee_account,
                      withdrawal, deposit, fee, asset ON transfers
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.withdrawal_timestamp OR timestamp >= OLD.deposit_timestamp OR
                timestamp >= NEW.withdrawal_timestamp OR timestamp >= NEW.deposit_timestamp;
END;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 1;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=44 WHERE name='SchemaVersion';
COMMIT;
