BEGIN TRANSACTION;
--------------------------------------------------------------------------------
DROP VIEW IF EXISTS categories_tree;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=39 WHERE name='SchemaVersion';
COMMIT;
