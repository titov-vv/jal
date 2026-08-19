BEGIN TRANSACTION;
--------------------------------------------------------------------------------
-- 'trades_opened.remaining_qty' now holds the quantity a lot EFFECTIVELY holds, and 'c_qty' only relates
-- it to the quantity of the operation that opened the lot (reporting). It used to be the other way round -
-- the quantity was the product of the two - and that product is a ratio of two arbitrary amounts, so the
-- lot layer and the ledger books drifted apart and a rounding crumb could abort a whole ledger rebuild.
--
-- No column changes, only their meaning, so the rows that exist cannot be reinterpreted. They cannot be
-- converted here either: the values are decimals kept as TEXT and multiplying them inside SQLite would
-- coerce them to float, which is exactly what this application avoids everywhere. So the calculated data
-- is dropped and rebuilt from the operations, which is the only exact source of it. 'ledger' goes too:
-- left in place it would keep the ledger frontier at the last operation and nothing would be recalculated.
DELETE FROM trades_closed;
DELETE FROM trades_opened;
DELETE FROM ledger_totals;
DELETE FROM ledger;
INSERT OR REPLACE INTO settings(name, value) VALUES ('RebuildDB', 1);
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=64 WHERE name='SchemaVersion';
COMMIT;
