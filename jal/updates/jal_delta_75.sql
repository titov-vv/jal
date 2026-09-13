BEGIN TRANSACTION;
--------------------------------------------------------------------------------
-- A FEE LEAVES THE OPERATION THAT BEARS IT
--------------------------------------------------------------------------------
-- Every fee is a row of 'fees' now - read, written and posted from there - so the ten columns an operation kept one
-- in hold nothing the application looks at. Their contents were copied into the table by delta 73.
--
-- The five triggers are restated FIRST, so that none of them names a column that is gone. SQLite does not stop this
-- on its own: it drops a column an 'UPDATE OF' list mentions without a word, and leaves the list naming it.
DROP TRIGGER IF EXISTS trades_after_update;
CREATE TRIGGER trades_after_update AFTER UPDATE OF timestamp, account_id, symbol_id, qty, price ON trades FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
    UPDATE operations SET timestamp = COALESCE(NEW.timestamp, 0) WHERE id = NEW.oid;
END;
DROP TRIGGER IF EXISTS swaps_after_update;
CREATE TRIGGER swaps_after_update AFTER UPDATE OF timestamp, account_id, out_symbol_id, out_qty, in_timestamp, in_account_id, in_symbol_id, in_qty ON swaps FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
    UPDATE operations SET timestamp = COALESCE(MIN(NEW.timestamp, COALESCE(NEW.in_timestamp, NEW.timestamp)), 0) WHERE id = NEW.oid;
END;
DROP TRIGGER IF EXISTS bridges_after_update;
CREATE TRIGGER bridges_after_update AFTER UPDATE OF out_timestamp, in_timestamp, out_account_id, in_account_id, out_symbol_id, in_symbol_id, out_qty, in_qty ON bridges FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.out_timestamp OR timestamp >= OLD.in_timestamp OR timestamp >= NEW.out_timestamp OR timestamp >= NEW.in_timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.out_timestamp OR timestamp >= OLD.in_timestamp OR timestamp >= NEW.out_timestamp OR timestamp >= NEW.in_timestamp;
    UPDATE operations SET timestamp = COALESCE(MIN(COALESCE(NEW.out_timestamp, NEW.in_timestamp),
                                                   COALESCE(NEW.in_timestamp, NEW.out_timestamp)), 0)
        WHERE id = NEW.oid;
END;
DROP TRIGGER IF EXISTS transfers_after_update;
CREATE TRIGGER transfers_after_update AFTER UPDATE OF withdrawal_timestamp, deposit_timestamp, withdrawal_account, deposit_account, withdrawal, deposit, symbol_id ON transfers FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.withdrawal_timestamp OR timestamp >= OLD.deposit_timestamp OR
                timestamp >= NEW.withdrawal_timestamp OR timestamp >= NEW.deposit_timestamp;
    UPDATE operations SET timestamp = COALESCE(MIN(COALESCE(NEW.withdrawal_timestamp, NEW.deposit_timestamp),
                                                   COALESCE(NEW.deposit_timestamp, NEW.withdrawal_timestamp)), 0)
        WHERE id = NEW.oid;
END;
DROP TRIGGER IF EXISTS conversions_after_update;
CREATE TRIGGER conversions_after_update AFTER UPDATE OF timestamp, account_id, out_symbol_id, out_qty, in_symbol_id, in_qty ON conversions FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
    UPDATE operations SET timestamp = COALESCE(NEW.timestamp, 0) WHERE id = NEW.oid;
END;
--------------------------------------------------------------------------------
-- ... and the columns themselves
ALTER TABLE trades DROP COLUMN fee;
ALTER TABLE transfers DROP COLUMN fee;
ALTER TABLE transfers DROP COLUMN fee_account;
ALTER TABLE transfers DROP COLUMN fee_symbol_id;
ALTER TABLE conversions DROP COLUMN fee_qty;
ALTER TABLE conversions DROP COLUMN fee_symbol_id;
ALTER TABLE swaps DROP COLUMN fee_qty;
ALTER TABLE swaps DROP COLUMN fee_symbol_id;
ALTER TABLE bridges DROP COLUMN fee_qty;
ALTER TABLE bridges DROP COLUMN fee_symbol_id;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=75 WHERE name='SchemaVersion';
COMMIT;
