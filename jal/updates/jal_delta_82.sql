BEGIN TRANSACTION;
--------------------------------------------------------------------------------
-- ONE ASSET MAY KEEP SUPERSEDED LISTINGS
--------------------------------------------------------------------------------
-- Only the listings in use have to be unique: a superseded one may repeat the ticker, currency and venue of a live
-- one (a reverse split that keeps its ticker). Weaker than the former index, so the stored rows always satisfy it.
DROP INDEX IF EXISTS uniq_symbols;
CREATE UNIQUE INDEX uniq_symbols ON asset_symbol (asset_id, symbol COLLATE NOCASE, currency_id, location_id) WHERE active=1;
-- A listing has at most one identifier of each type; a repeated one keeps the value stored first
DELETE FROM symbol_ids WHERE id NOT IN (SELECT MIN(id) FROM symbol_ids GROUP BY symbol_id, id_type);
CREATE UNIQUE INDEX uniq_symbol_ids ON symbol_ids (symbol_id, id_type);
--------------------------------------------------------------------------------
-- A CRYPTO LISTING IS KEPT IN ITS VENUE'S QUOTE CURRENCY
--------------------------------------------------------------------------------
-- Done by the companion jal_delta_82.py, which merges the listings that differed by currency only
INSERT OR REPLACE INTO settings(name, value) VALUES('RunUpdateScript', 82);
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=82 WHERE name='SchemaVersion';
COMMIT;
