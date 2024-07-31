BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = OFF;
--------------------------------------------------------------------------------
DROP INDEX IF EXISTS ledger_by_operation;
CREATE INDEX ledger_by_operation ON ledger (otype, oid, opart, book_account);
DROP INDEX IF EXISTS ledger_by_time;
CREATE INDEX ledger_by_time ON ledger (timestamp, asset_id, account_id);
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=58 WHERE name='SchemaVersion';
COMMIT;