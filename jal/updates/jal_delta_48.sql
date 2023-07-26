BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 0;
--------------------------------------------------------------------------------
CREATE TABLE temp_tickers AS SELECT * FROM asset_tickers;
DROP TABLE asset_tickers;
CREATE TABLE asset_tickers (
    id           INTEGER PRIMARY KEY UNIQUE NOT NULL,
    asset_id     INTEGER REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    symbol       TEXT    NOT NULL,
    currency_id  INTEGER REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE,
    description  TEXT    NOT NULL DEFAULT (''),
    quote_source INTEGER DEFAULT ( -1) NOT NULL,
    active       INTEGER NOT NULL DEFAULT (1)
);
INSERT INTO asset_tickers (id, asset_id, symbol, currency_id, description, quote_source, active)
SELECT id, asset_id, symbol, currency_id, description, quote_source, active FROM temp_tickers;
DROP TABLE temp_tickers;
-- Index to prevent duplicates
DROP INDEX IF EXISTS uniq_symbols;
CREATE UNIQUE INDEX uniq_symbols ON asset_tickers (asset_id, symbol COLLATE NOCASE, currency_id);
-- Create triggers to keep currency_id NULL for currencies and NOT NULL for other assets
DROP TRIGGER IF EXISTS validate_ticker_currency_insert;
CREATE TRIGGER validate_ticker_currency_insert
    BEFORE INSERT ON asset_tickers
    FOR EACH ROW
    WHEN IIF(NEW.currency_id IS NULL, 0, 1) = (SELECT IIF(type_id=1, 1, 0) FROM assets WHERE id=NEW.asset_id)
BEGIN
    SELECT RAISE(ABORT, "JAL_SQL_MSG_0003");
END;

DROP TRIGGER IF EXISTS validate_ticker_currency_update;
CREATE TRIGGER validate_ticker_currency_update
    AFTER UPDATE OF currency_id ON asset_tickers
    FOR EACH ROW
    WHEN IIF(NEW.currency_id IS NULL, 0, 1) = (SELECT IIF(type_id=1, 1, 0) FROM assets WHERE id=NEW.asset_id)
BEGIN
    SELECT RAISE(ABORT, "JAL_SQL_MSG_0003");
END;
-- drop table with data sources
DROP TABLE IF EXISTS data_sources;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 1;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=48 WHERE name='SchemaVersion';
COMMIT;
-- Reduce file size
VACUUM;