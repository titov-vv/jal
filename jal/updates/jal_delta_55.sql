BEGIN TRANSACTION;
--------------------------------------------------------------------------------
INSERT OR REPLACE INTO settings(id, name, value) VALUES (20, 'DlgGeometry_Accounts', '');
INSERT OR REPLACE INTO settings(id, name, value) VALUES (21, 'DlgViewState_Accounts', '');
INSERT OR REPLACE INTO settings(id, name, value) VALUES (22, 'DlgGeometry_Assets', '');
INSERT OR REPLACE INTO settings(id, name, value) VALUES (23, 'DlgViewState_Assets', '');
INSERT OR REPLACE INTO settings(id, name, value) VALUES (24, 'DlgGeometry_Peers', '');
INSERT OR REPLACE INTO settings(id, name, value) VALUES (25, 'DlgViewState_Peers', '');
INSERT OR REPLACE INTO settings(id, name, value) VALUES (26, 'DlgGeometry_Categories', '');
INSERT OR REPLACE INTO settings(id, name, value) VALUES (27, 'DlgViewState_Categories', '');
INSERT OR REPLACE INTO settings(id, name, value) VALUES (28, 'DlgGeometry_Tags', '');
INSERT OR REPLACE INTO settings(id, name, value) VALUES (29, 'DlgViewState_Tags', '');
INSERT OR REPLACE INTO settings(id, name, value) VALUES (30, 'DlgGeometry_Quotes', '');
INSERT OR REPLACE INTO settings(id, name, value) VALUES (31, 'DlgViewState_Quotes', '');
INSERT OR REPLACE INTO settings(id, name, value) VALUES (32, 'DlgGeometry_Base currency', '');
INSERT OR REPLACE INTO settings(id, name, value) VALUES (33, 'DlgViewState_Base currency', '');
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=55 WHERE name='SchemaVersion';
COMMIT;
-- Reduce file size
VACUUM;