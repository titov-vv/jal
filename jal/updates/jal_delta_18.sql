BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 0;
--------------------------------------------------------------------------------
-- Drop view that are not used anymore
--------------------------------------------------------------------------------
DROP VIEW agents_ext;
DROP VIEW categories_ext;

--------------------------------------------------------------------------------
PRAGMA foreign_keys = 1;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=18 WHERE name='SchemaVersion';
COMMIT;
