BEGIN TRANSACTION;
--------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS asset_id (
    id       NTEGER PRIMARY KEY UNIQUE NOT NULL,
    asset_id INTEGER REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    id_type  INTEGER NOT NULL,
    id_value TEXT NOT NULL
);
-- Migrate existing ISINs to new asset_id table
INSERT INTO asset_id (asset_id, id_type, id_value)
  SELECT id, 2, isin FROM assets WHERE NOT (isin='' OR isin LIKE ' %')
-- Remove ISINs from asset_data table
DELETE FROM asset_data WHERE id IN (SELECT d.id FROM asset_data d JOIN asset_id i ON d.asset_id=i.asset_id AND i.id_type=1 AND d.value=i.id_value)
-- Migrate existing MOEX registration codes from asset_data to new asset_id table
INSERT INTO asset_id (asset_id, id_type, id_value)
  SELECT asset_id, 5, value FROM asset_data d LEFT JOIN assets a ON d.asset_id=a.id
  WHERE datatype=1 AND value LIKE '1-__-%' AND NOT a.id IS NULL;
DELETE FROM asset_data WHERE datatype=1 AND value LIKE '1-__-%'
-- Clean up any remaining registration data from asset_data table (There was a bit of mess)
DELETE FROM asset_data WHERE datatype=1
--------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS asset_location (
    id           INTEGER PRIMARY KEY UNIQUE NOT NULL,
    loc_type     INTEGER NOT NULL,
    name         TEXT NOT NULL UNIQUE,
    country_id   INTEGER DEFAULT (0) NOT NULL REFERENCES countries (id) ON DELETE SET DEFAULT ON UPDATE CASCADE,
    price_source INTEGER DEFAULT (- 1)
);
--------------------------------------------------------------------------------
-- Update assets_ext view and trigger
DROP VIEW assets_ext;
CREATE VIEW assets_ext AS
SELECT a.id, a.type_id, t.symbol, a.full_name, i.id_value AS isin, t.currency_id, a.country_id, t.quote_source
    FROM assets a
    LEFT JOIN asset_tickers t ON a.id = t.asset_id
    LEFT JOIN asset_id i ON a.id = i.asset_id AND i.id_type = 1
    WHERE t.active = 1
    ORDER BY a.id;
DROP TRIGGER on_asset_ext_delete;
CREATE TRIGGER on_asset_ext_delete INSTEAD OF DELETE ON assets_ext FOR EACH ROW
BEGIN
    DELETE FROM assets WHERE id = OLD.id;
END;
--------------------------------------------------------------------------------
-- Remove ISIN column from assets table
ALTER TABLE assets DROP COLUMN isin;
-- Remove unused description from asset symbols
ALTER TABLE asset_tickers DROP COLUMN description;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=60 WHERE name='SchemaVersion';
--INSERT OR REPLACE INTO settings(name, value) VALUES ('RebuildDB', 1);
COMMIT;