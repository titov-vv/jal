BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 0;
--------------------------------------------------------------------------------
DROP TRIGGER IF EXISTS on_closed_trade_delete;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 1;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=51 WHERE name='SchemaVersion';
INSERT OR REPLACE INTO settings(id, name, value) VALUES (7, 'RebuildDB', 1);
COMMIT;
-- Reduce file size
VACUUM;