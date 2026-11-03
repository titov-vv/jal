BEGIN TRANSACTION;
--------------------------------------------------------------------------------
-- THE RATE OF A TRANSFER BETWEEN CURRENCIES, KEPT APART FROM THE PRICE FACTOR
--------------------------------------------------------------------------------
ALTER TABLE trades_opened ADD COLUMN c_fx TEXT NOT NULL DEFAULT ('1');
ALTER TABLE trades_closed ADD COLUMN c_fx TEXT NOT NULL DEFAULT ('1');
--------------------------------------------------------------------------------
-- ASSET FEES GROUPED BY KIND: 4 = depositary fee, 5 = position financing
--------------------------------------------------------------------------------
UPDATE asset_payments SET type=4 WHERE type=3 AND note LIKE '%ADR Fee%';
UPDATE asset_payments SET type=5 WHERE type=3 AND note LIKE 'CFD BORROW FEE FOR%';
--------------------------------------------------------------------------------
INSERT OR REPLACE INTO settings(name, value) VALUES ('RebuildDB', 1);
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=85 WHERE name='SchemaVersion';
COMMIT;
