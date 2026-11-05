BEGIN TRANSACTION;
--------------------------------------------------------------------------------
-- OPEN LOTS: INDEX FOR THE POSITION QUERY OF open_trades_list()
--------------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS open_trades_by_position ON trades_opened (account_id, asset_id, timestamp);
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=87 WHERE name='SchemaVersion';
COMMIT;
