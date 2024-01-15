BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 0;
--------------------------------------------------------------------------------
DROP TRIGGER IF EXISTS on_closed_trade_delete;

DROP INDEX IF EXISTS open_trades_by_operation_idx;
CREATE INDEX open_trades_by_operation_idx ON trades_opened (timestamp, op_type, operation_id);
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 1;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=51 WHERE name='SchemaVersion';
INSERT OR REPLACE INTO settings(id, name, value) VALUES (7, 'RebuildDB', 1);
COMMIT;
-- Reduce file size
VACUUM;