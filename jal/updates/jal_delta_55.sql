BEGIN TRANSACTION;
--------------------------------------------------------------------------------

--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=55 WHERE name='SchemaVersion';
COMMIT;
-- Reduce file size
VACUUM;