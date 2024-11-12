BEGIN TRANSACTION;
--------------------------------------------------------------------------------
INSERT OR REPLACE INTO settings(name, value) VALUES('ShowInactiveAccountBalances', 0);
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=59 WHERE name='SchemaVersion';
COMMIT;