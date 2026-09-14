BEGIN TRANSACTION;
--------------------------------------------------------------------------------
-- A PAYMENT IS MONEY, AND NOTHING ELSE
--------------------------------------------------------------------------------
-- Everything whose amount was a quantity of an asset has left for 'asset_incomes', so what remains is money paid on
-- account of an asset. Two things follow: the per-unit price a grant was made at has nothing left to describe here,
-- and the subtypes are renumbered from 1 like the other two classes of the family.
--------------------------------------------------------------------------------
-- A bond amortization has no operation to become. It books money in AND reduces the position's basis, which nothing
-- else does; no importer can emit one (the JSF string exists in no producer) and hand entry was the only way to make
-- one at all, so the live ledger holds none and the routine was never reached by any test. Rather than guess what a
-- stored one should turn into, an upgrade that meets one STOPS: this statement writes nothing when there are none
-- and violates NOT NULL when there is one, which rolls the whole delta back and leaves the database at version 77.
INSERT INTO settings(name, value) SELECT NULL, 'bond amortization' FROM asset_payments WHERE type = 5;
--------------------------------------------------------------------------------
-- 'Asset fee/tax' takes the first free number, so the editor's selector can be indexed by the subtype like the
-- other two. No row on the live ledger carries it; the statement is here because another database may.
UPDATE asset_payments SET type = 3 WHERE type = 6;
--------------------------------------------------------------------------------
-- The trigger is re-stated BEFORE the column goes, because SQLite drops a column an 'UPDATE OF' list names without
-- a word and leaves the list naming it - the opposite of what it does for a view, which it refuses to break.
DROP TRIGGER IF EXISTS asset_payments_after_update;
CREATE TRIGGER asset_payments_after_update AFTER UPDATE OF timestamp, type, account_id, symbol_id, amount, tax ON asset_payments FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
    UPDATE operations SET timestamp = COALESCE(NEW.timestamp, 0) WHERE id = NEW.oid;
END;
--------------------------------------------------------------------------------
ALTER TABLE asset_payments DROP COLUMN price;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=78 WHERE name='SchemaVersion';
COMMIT;
