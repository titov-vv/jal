BEGIN TRANSACTION;
--------------------------------------------------------------------------------
DROP VIEW IF EXISTS currencies;  -- Remove views to prevent dependency errors
DROP VIEW IF EXISTS assets_ext;  -- Remove view as it isn't used anymore
--------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS asset_id (
    id        INTEGER PRIMARY KEY UNIQUE NOT NULL,
    symbol_id INTEGER REFERENCES asset_tickers (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    id_type   INTEGER NOT NULL,
    id_value  TEXT NOT NULL
);
-- Migrate existing ISINs to new asset_id table
INSERT INTO asset_id (symbol_id, id_type, id_value)
  SELECT t.id, 2, isin
  FROM assets a
  LEFT JOIN asset_tickers t ON a.id = t.asset_id
  WHERE NOT (isin='' OR isin LIKE ' %');
-- Remove ISINs that were stored as registration code in asset_data table
DELETE FROM asset_data WHERE id IN (SELECT d.id FROM asset_data d JOIN assets a ON d.asset_id=a.id AND d.value=a.isin);
-- Migrate existing MOEX registration codes from asset_data to new asset_id table
INSERT INTO asset_id (symbol_id, id_type, id_value)
  SELECT t.id, 5, value
  FROM asset_data d
  LEFT JOIN asset_tickers t ON d.asset_id = t.asset_id
  WHERE datatype=1 AND value LIKE '1-__-%' AND NOT t.id IS NULL;
DELETE FROM asset_data WHERE datatype=1 AND value LIKE '1-__-%';
-- Migrate what looks like CUSIPs
INSERT INTO asset_id (symbol_id, id_type, id_value)
  SELECT t.id, 4, value
  FROM asset_data d
  LEFT JOIN asset_tickers t ON d.asset_id = t.asset_id
  WHERE datatype=1 AND value REGEXP '^.{5}[A-Z].{3}$' AND NOT t.id IS NULL;
DELETE FROM asset_data WHERE datatype=1 AND value REGEXP '^.{5}[A-Z].{3}$';
-- Clean up any remaining registration data from asset_data table (There was a bit of mess)
DELETE FROM asset_data WHERE datatype=1;
--------------------------------------------------------------------------------
-- Create quote source table
CREATE TABLE IF NOT EXISTS quote_source (
    asset_id    INTEGER REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    currency_id INTEGER REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    datafeed_id INTEGER NOT NULL
);
CREATE UNIQUE INDEX datafeed_pk ON quote_source (asset_id ASC, currency_id ASC);
-- Copy data from symbols table
INSERT INTO quote_source (asset_id, currency_id, datafeed_id)
  SELECT asset_id, currency_id, quote_source
  FROM asset_tickers
  WHERE quote_source>0 AND active=1;
-- Insert data for currencies (it had NULL in currency_id previously)
INSERT INTO quote_source (asset_id, currency_id, datafeed_id)
  SELECT asset_id, asset_id, quote_source
  FROM asset_tickers
  WHERE quote_source=0;
--------------------------------------------------------------------------------
-- Remove ISIN column from assets table
ALTER TABLE assets DROP COLUMN isin;
--------------------------------------------------------------------------------
-- Alter asset symbols table
-- Remove custom error triggers
DROP TRIGGER IF EXISTS validate_ticker_currency_insert;
DROP TRIGGER IF EXISTS  validate_ticker_currency_update;
-- Remove NULL values from currency_id
UPDATE asset_symbol SET currency_id=asset_id WHERE currency_id IS NULL
-- Create new symbols table
CREATE TABLE asset_symbol (
    id          INTEGER PRIMARY KEY UNIQUE NOT NULL,
    asset_id    INTEGER REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    symbol      TEXT NOT NULL,
    currency_id INTEGER REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    location_id INTEGER NOT NULL DEFAULT (0),
    active      INTEGER NOT NULL DEFAULT (1),
    icon        BLOB
);
INSERT INTO asset_symbol (id, asset_id, symbol, currency_id, active) SELECT id, asset_id, symbol, currency_id, active FROM asset_tickers;
DROP TABLE asset_tickers;
CREATE UNIQUE INDEX uniq_symbols ON asset_symbol (asset_id, symbol COLLATE NOCASE, currency_id);
--------------------------------------------------------------------------------
-- Update currencies view
CREATE VIEW currencies AS
SELECT a.id, s.symbol
    FROM assets AS a
    LEFT JOIN asset_symbol AS s ON s.asset_id = a.id AND s.active = 1
    WHERE a.type_id = 1;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=60 WHERE name='SchemaVersion';
--INSERT OR REPLACE INTO settings(name, value) VALUES ('RebuildDB', 1);
COMMIT;