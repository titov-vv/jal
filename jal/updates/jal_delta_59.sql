BEGIN TRANSACTION;
--------------------------------------------------------------------------------
ALTER TABLE accounts ADD COLUMN credit TEXT DEFAULT ('0') NOT NULL;
--------------------------------------------------------------------------------
INSERT OR REPLACE INTO settings(name, value) VALUES('ShowInactiveAccountBalances', 0);
INSERT OR REPLACE INTO settings(name, value) VALUES('UseAccountCreditLimit', 1);
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=59 WHERE name='SchemaVersion';
COMMIT;