BEGIN TRANSACTION;
--------------------------------------------------------------------------------
DELETE FROM settings WHERE id>10;
INSERT INTO settings(id, name, value) VALUES (11, 'RecentFolder_Statement', '.');
INSERT INTO settings(id, name, value) VALUES (12, 'RecentFolder_Report', '.');
INSERT INTO settings(id, name, value) VALUES (13, 'CleanDB', 0);
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=45 WHERE name='SchemaVersion';
COMMIT;