BEGIN TRANSACTION;
--------------------------------------------------------------------------------
-- LENDING INTEREST IS BOOKED APART FROM THE CONVERSION IT ARRIVED WITH
--------------------------------------------------------------------------------
-- The split of the stored conversions is in the companion jal_delta_80.py
INSERT OR REPLACE INTO settings(name, value) VALUES('RunUpdateScript', 80);
INSERT OR REPLACE INTO settings(name, value) VALUES ('RebuildDB', 1);
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=80 WHERE name='SchemaVersion';
COMMIT;
