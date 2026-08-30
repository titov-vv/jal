BEGIN TRANSACTION;
--------------------------------------------------------------------------------
-- AN ACCOUNT MAY CARRY A TAG (AccountData.Tag = 12)
--------------------------------------------------------------------------------
-- The tag is stored in 'account_data' and no foreign key can express that, so the
-- rows are dropped here beside the 'asset_data' ones that hold an asset's tag.
DROP TRIGGER IF EXISTS tags_after_delete;
CREATE TRIGGER tags_after_delete AFTER DELETE ON tags FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= (SELECT MIN(timestamp) FROM ledger WHERE tag_id=OLD.id);
    DELETE FROM asset_data WHERE datatype=1 AND value=OLD.id;
    DELETE FROM account_data WHERE datatype=12 AND value=OLD.id;
END;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=67 WHERE name='SchemaVersion';
COMMIT;
