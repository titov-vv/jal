BEGIN TRANSACTION;
--------------------------------------------------------------------------------
-- ASSET TAGS REMOVED (asset_data datatype 1)
--------------------------------------------------------------------------------
-- Ledger rows of asset operations carried the asset's tag; the ledger is rebuilt from the first of them
DELETE FROM ledger WHERE timestamp >= (SELECT MIN(timestamp) FROM ledger WHERE tag_id IS NOT NULL AND otype<>1);
DELETE FROM asset_data WHERE datatype=1;
DROP TRIGGER IF EXISTS tags_after_delete;
CREATE TRIGGER tags_after_delete AFTER DELETE ON tags FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= (SELECT MIN(timestamp) FROM ledger WHERE tag_id=OLD.id);
    DELETE FROM account_data WHERE datatype=12 AND value=OLD.id;
END;
--------------------------------------------------------------------------------
INSERT OR REPLACE INTO settings(name, value) VALUES ('RebuildDB', 1);
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=89 WHERE name='SchemaVersion';
COMMIT;
VACUUM;
