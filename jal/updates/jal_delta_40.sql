BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 0;
--------------------------------------------------------------------------------
-- Change db structure for base currency
DELETE FROM settings WHERE id=2 AND name='BaseCurrency';

DROP TABLE IF EXISTS base_currency;
CREATE TABLE base_currency (
    id              INTEGER PRIMARY KEY UNIQUE NOT NULL,
    since_timestamp INTEGER NOT NULL UNIQUE,
    currency_id     INTEGER NOT NULL REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE
);
--------------------------------------------------------------------------------
-- Ensure compatibility with previous behavior
INSERT INTO base_currency(id, since_timestamp, currency_id) VALUES (1, 946684800, 1);
-- Update data source name
UPDATE data_sources SET name='Central banks' WHERE id=0;
--------------------------------------------------------------------------------
-- Change db structure for currency handling
CREATE TABLE temp_tickers AS SELECT * FROM asset_tickers;
DROP TABLE asset_tickers;
CREATE TABLE asset_tickers (
    id           INTEGER PRIMARY KEY UNIQUE NOT NULL,
    asset_id     INTEGER REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    symbol       TEXT    NOT NULL,
    currency_id  INTEGER REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE,
    description  TEXT    NOT NULL DEFAULT (''),
    quote_source INTEGER REFERENCES data_sources (id) ON DELETE SET NULL ON UPDATE CASCADE DEFAULT ( -1),
    active       INTEGER NOT NULL DEFAULT (1)
);
INSERT INTO asset_tickers (id, asset_id, symbol, currency_id, description, quote_source, active)
SELECT id, asset_id, symbol, currency_id, description, quote_source, active FROM temp_tickers;
DROP TABLE temp_tickers;
-- Set reference currency to NULL for currency symbols
UPDATE asset_tickers SET currency_id=NULL WHERE asset_id IN (SELECT id FROM assets WHERE type_id=1);
-- Index to prevent duplicates
DROP INDEX IF EXISTS uniq_symbols;
CREATE UNIQUE INDEX uniq_symbols ON asset_tickers (asset_id, symbol COLLATE NOCASE, currency_id);

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
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 1;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=40 WHERE name='SchemaVersion';
COMMIT;
