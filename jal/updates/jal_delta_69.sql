BEGIN TRANSACTION;
--------------------------------------------------------------------------------
-- CANONICAL SPELLING OF STORED AMOUNTS
--------------------------------------------------------------------------------
-- The rewrite itself is in the companion jal_delta_69.py
INSERT OR REPLACE INTO settings(name, value) VALUES('RunUpdateScript', 69);
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=69 WHERE name='SchemaVersion';
COMMIT;
