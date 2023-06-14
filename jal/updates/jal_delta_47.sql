BEGIN TRANSACTION;
--------------------------------------------------------------------------------
INSERT INTO settings(id, name, value) VALUES (14, 'EuLidlClientSecret', 'TGlkbFBsdXNOYXRpdmVDbGllbnQ6c2VjcmV0');
INSERT INTO settings(id, name, value) VALUES (15, 'EuLidlAccessToken', '');
INSERT INTO settings(id, name, value) VALUES (16, 'EuLidlRefreshToken', '');
INSERT INTO settings(id, name, value) VALUES (17, 'PtPingoDoceAccessToken', '');
INSERT INTO settings(id, name, value) VALUES (18, 'PtPingoDoceRefreshToken', '');
INSERT INTO settings(id, name, value) VALUES (19, 'PtPingoDoceUserProfile', '{}');
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=47 WHERE name='SchemaVersion';
COMMIT;