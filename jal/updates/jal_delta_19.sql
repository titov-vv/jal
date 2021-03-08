BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 0;
--------------------------------------------------------------------------------
-- Drop 't_pivot' table as reports doesn't use it anymore
--------------------------------------------------------------------------------
DROP TABLE IF EXISTS t_pivot;
DROP TABLE IF EXISTS t_months;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 1;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=19 WHERE name='SchemaVersion';
COMMIT;