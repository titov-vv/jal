BEGIN TRANSACTION;
--------------------------------------------------------------------------------
INSERT OR IGNORE INTO data_sources (id, name) VALUES (4, 'TMX TSX');
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=24 WHERE name='SchemaVersion';
COMMIT;
