BEGIN TRANSACTION;
--------------------------------------------------------------------------------
DELETE FROM quotes WHERE quote='NaN';
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=54 WHERE name='SchemaVersion';
COMMIT;
-- Reduce file size
VACUUM;