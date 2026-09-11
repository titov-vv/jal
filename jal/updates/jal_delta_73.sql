BEGIN TRANSACTION;
--------------------------------------------------------------------------------
-- AN OPERATION REMEMBERS WHEN IT HAPPENS
--------------------------------------------------------------------------------
-- The moment a child of an operation invalidates the ledger from. Copied out of the type tables so that a child
-- has one parent to ask - see the column comment in jal_init.sql for why it is not the operation's display date.
ALTER TABLE operations ADD COLUMN timestamp INTEGER NOT NULL DEFAULT (0);
-- The one-time fill. This is the only place the eight tables are listed: from here the sixteen triggers below keep
-- the value current, and a child of an operation never needs to know any of them.
UPDATE operations SET timestamp = COALESCE(
    (SELECT timestamp FROM actions        WHERE oid = operations.id),
    (SELECT timestamp FROM asset_payments WHERE oid = operations.id),
    (SELECT timestamp FROM asset_actions  WHERE oid = operations.id),
    (SELECT timestamp FROM trades         WHERE oid = operations.id),
    (SELECT timestamp FROM conversions    WHERE oid = operations.id),
    (SELECT MIN(COALESCE(withdrawal_timestamp, deposit_timestamp),
                COALESCE(deposit_timestamp, withdrawal_timestamp)) FROM transfers WHERE oid = operations.id),
    (SELECT MIN(timestamp, COALESCE(in_timestamp, timestamp)) FROM swaps WHERE oid = operations.id),
    (SELECT MIN(COALESCE(out_timestamp, in_timestamp),
                COALESCE(in_timestamp, out_timestamp)) FROM bridges WHERE oid = operations.id), 0);
--------------------------------------------------------------------------------
-- THE MOMENT FOLLOWS ITS TYPE ROW
--------------------------------------------------------------------------------
-- Each trigger below is the one that already existed, with a single statement added.
DROP TRIGGER IF EXISTS actions_after_insert;
CREATE TRIGGER actions_after_insert AFTER INSERT ON actions FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= NEW.timestamp;
    UPDATE operations SET timestamp = COALESCE(NEW.timestamp, 0) WHERE id = NEW.oid;
END;
DROP TRIGGER IF EXISTS actions_after_update;
CREATE TRIGGER actions_after_update AFTER UPDATE OF timestamp, account_id, peer_id ON actions FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
    UPDATE operations SET timestamp = COALESCE(NEW.timestamp, 0) WHERE id = NEW.oid;
END;
DROP TRIGGER IF EXISTS asset_payments_after_insert;
CREATE TRIGGER asset_payments_after_insert AFTER INSERT ON asset_payments FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= NEW.timestamp;
    UPDATE operations SET timestamp = COALESCE(NEW.timestamp, 0) WHERE id = NEW.oid;
END;
DROP TRIGGER IF EXISTS asset_payments_after_update;
CREATE TRIGGER asset_payments_after_update AFTER UPDATE OF timestamp, type, account_id, symbol_id, amount, tax, price ON asset_payments FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
    UPDATE operations SET timestamp = COALESCE(NEW.timestamp, 0) WHERE id = NEW.oid;
END;
DROP TRIGGER IF EXISTS asset_action_after_insert;
CREATE TRIGGER asset_action_after_insert AFTER INSERT ON asset_actions FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= NEW.timestamp;
    UPDATE operations SET timestamp = COALESCE(NEW.timestamp, 0) WHERE id = NEW.oid;
END;
DROP TRIGGER IF EXISTS asset_action_after_update;
CREATE TRIGGER asset_action_after_update AFTER UPDATE OF timestamp, account_id, type, symbol_id, qty ON asset_actions FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp  OR timestamp >= NEW.timestamp;
    UPDATE operations SET timestamp = COALESCE(NEW.timestamp, 0) WHERE id = NEW.oid;
END;
DROP TRIGGER IF EXISTS trades_after_insert;
CREATE TRIGGER trades_after_insert AFTER INSERT ON trades FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= NEW.timestamp;
    UPDATE operations SET timestamp = COALESCE(NEW.timestamp, 0) WHERE id = NEW.oid;
END;
DROP TRIGGER IF EXISTS trades_after_update;
CREATE TRIGGER trades_after_update AFTER UPDATE OF timestamp, account_id, symbol_id, qty, price, fee ON trades FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
    UPDATE operations SET timestamp = COALESCE(NEW.timestamp, 0) WHERE id = NEW.oid;
END;
DROP TRIGGER IF EXISTS transfers_after_insert;
CREATE TRIGGER transfers_after_insert AFTER INSERT ON transfers FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= NEW.withdrawal_timestamp OR timestamp >= NEW.deposit_timestamp;
    UPDATE operations SET timestamp = COALESCE(MIN(COALESCE(NEW.withdrawal_timestamp, NEW.deposit_timestamp),
                                                   COALESCE(NEW.deposit_timestamp, NEW.withdrawal_timestamp)), 0)
        WHERE id = NEW.oid;
END;
DROP TRIGGER IF EXISTS transfers_after_update;
CREATE TRIGGER transfers_after_update AFTER UPDATE OF withdrawal_timestamp, deposit_timestamp, withdrawal_account, deposit_account, fee_account, withdrawal, deposit, fee, fee_symbol_id, symbol_id ON transfers FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.withdrawal_timestamp OR timestamp >= OLD.deposit_timestamp OR
                timestamp >= NEW.withdrawal_timestamp OR timestamp >= NEW.deposit_timestamp;
    UPDATE operations SET timestamp = COALESCE(MIN(COALESCE(NEW.withdrawal_timestamp, NEW.deposit_timestamp),
                                                   COALESCE(NEW.deposit_timestamp, NEW.withdrawal_timestamp)), 0)
        WHERE id = NEW.oid;
END;
DROP TRIGGER IF EXISTS conversions_after_insert;
CREATE TRIGGER conversions_after_insert AFTER INSERT ON conversions FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= NEW.timestamp;
    UPDATE operations SET timestamp = COALESCE(NEW.timestamp, 0) WHERE id = NEW.oid;
END;
DROP TRIGGER IF EXISTS conversions_after_update;
CREATE TRIGGER conversions_after_update AFTER UPDATE OF timestamp, account_id, out_symbol_id, out_qty, in_symbol_id, in_qty, fee_symbol_id, fee_qty ON conversions FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
    UPDATE operations SET timestamp = COALESCE(NEW.timestamp, 0) WHERE id = NEW.oid;
END;
DROP TRIGGER IF EXISTS swaps_after_insert;
CREATE TRIGGER swaps_after_insert AFTER INSERT ON swaps FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= NEW.timestamp;
    UPDATE operations SET timestamp = COALESCE(MIN(NEW.timestamp, COALESCE(NEW.in_timestamp, NEW.timestamp)), 0) WHERE id = NEW.oid;
END;
DROP TRIGGER IF EXISTS swaps_after_update;
CREATE TRIGGER swaps_after_update AFTER UPDATE OF timestamp, account_id, out_symbol_id, out_qty, in_timestamp, in_account_id, in_symbol_id, in_qty, fee_symbol_id, fee_qty ON swaps FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
    UPDATE operations SET timestamp = COALESCE(MIN(NEW.timestamp, COALESCE(NEW.in_timestamp, NEW.timestamp)), 0) WHERE id = NEW.oid;
END;
DROP TRIGGER IF EXISTS bridges_after_insert;
CREATE TRIGGER bridges_after_insert AFTER INSERT ON bridges FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= NEW.out_timestamp OR timestamp >= NEW.in_timestamp;
    DELETE FROM trades_opened WHERE timestamp >= NEW.out_timestamp OR timestamp >= NEW.in_timestamp;
    UPDATE operations SET timestamp = COALESCE(MIN(COALESCE(NEW.out_timestamp, NEW.in_timestamp),
                                                   COALESCE(NEW.in_timestamp, NEW.out_timestamp)), 0)
        WHERE id = NEW.oid;
END;
DROP TRIGGER IF EXISTS bridges_after_update;
CREATE TRIGGER bridges_after_update AFTER UPDATE OF out_timestamp, in_timestamp, out_account_id, in_account_id, out_symbol_id, in_symbol_id, out_qty, in_qty, fee_symbol_id, fee_qty ON bridges FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.out_timestamp OR timestamp >= OLD.in_timestamp OR timestamp >= NEW.out_timestamp OR timestamp >= NEW.in_timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.out_timestamp OR timestamp >= OLD.in_timestamp OR timestamp >= NEW.out_timestamp OR timestamp >= NEW.in_timestamp;
    UPDATE operations SET timestamp = COALESCE(MIN(COALESCE(NEW.out_timestamp, NEW.in_timestamp),
                                                   COALESCE(NEW.in_timestamp, NEW.out_timestamp)), 0)
        WHERE id = NEW.oid;
END;
--------------------------------------------------------------------------------
-- A FEE GETS A TABLE OF ITS OWN
--------------------------------------------------------------------------------
-- Table: fees - what an operation was charged for happening, one row per charge.
-- A fee is a PROPERTY of the operation that bears it and carries no description of its own: every fee has a parent,
-- and saying what happened is the parent's job. What it does carry is who bore it, in what it was paid and what sort
-- of charge it was - none of which the single fee column of an operation table could express.
-- SOURCE data, keyed on the operations root: the cascade there reaches these rows by every path an operation can
-- leave by, not only its own deletion - an account, an asset listing or an agent takes its operations with it.
CREATE TABLE fees (
    id           INTEGER PRIMARY KEY,
    operation_id INTEGER NOT NULL REFERENCES operations (id) ON DELETE CASCADE,     -- The operation bearing the fee
    idx          INTEGER NOT NULL DEFAULT (0),   -- Stability and not the order the user sees: it keeps two fees of
                                                 -- one operation in the same relative order across a rebuild, and
                                                 -- gives each of them a sequence part of its own. Assigned by
                                                 -- whoever writes the row and never edited afterwards.
    account_id   INTEGER NOT NULL REFERENCES accounts (id) ON DELETE CASCADE ON UPDATE CASCADE,   -- Who bore it: not
                                                 -- always a leg of the operation, as a transfer charged on a third
                                                 -- account shows
    symbol_id    INTEGER REFERENCES asset_symbol (id) ON DELETE CASCADE ON UPDATE CASCADE,  -- NULL = account currency
    amount       TEXT    NOT NULL,               -- A quantity when 'symbol_id' names an asset, a sum of money when
                                                 -- it doesn't - the same split the fee columns live with today
    kind         INTEGER NOT NULL DEFAULT (0)    -- What sort of charge it is: FeeKind in jal/db/operations.py
);
CREATE INDEX fees_by_operation ON fees (operation_id);
--------------------------------------------------------------------------------
-- THE FEES THAT ARE ALREADY STORED
--------------------------------------------------------------------------------
-- One row per fee an operation table already holds.
-- 'kind' is FeeKind in jal/db/operations.py - Commission for a charge in money, Gas for one denominated in an asset.
INSERT INTO fees (operation_id, idx, account_id, symbol_id, amount, kind)
    SELECT oid, 0, account_id, NULL, fee, 0 FROM trades WHERE CAST(fee AS REAL) <> 0;
INSERT INTO fees (operation_id, idx, account_id, symbol_id, amount, kind)
    SELECT oid, 0, COALESCE(fee_account, withdrawal_account, deposit_account), fee_symbol_id, fee,
           CASE WHEN fee_symbol_id IS NULL THEN 0 ELSE 1 END
      FROM transfers WHERE CAST(fee AS REAL) <> 0;
INSERT INTO fees (operation_id, idx, account_id, symbol_id, amount, kind)
    SELECT oid, 0, account_id, fee_symbol_id, fee_qty, 1 FROM conversions WHERE CAST(fee_qty AS REAL) <> 0;
INSERT INTO fees (operation_id, idx, account_id, symbol_id, amount, kind)
    SELECT oid, 0, account_id, fee_symbol_id, fee_qty, 1 FROM swaps WHERE CAST(fee_qty AS REAL) <> 0;
-- Gas is burned on the source chain, so a bridge's fee is borne by the sending account
INSERT INTO fees (operation_id, idx, account_id, symbol_id, amount, kind)
    SELECT oid, 0, out_account_id, fee_symbol_id, fee_qty, 1 FROM bridges WHERE CAST(fee_qty AS REAL) <> 0;
--------------------------------------------------------------------------------
-- A FEE EDIT MUST INVALIDATE THE LEDGER
--------------------------------------------------------------------------------
-- A fee edits the ledger as much as the operation it belongs to does, so the three triggers below invalidate it the
-- way the parent's own triggers do. Without them a fee could be added, changed or removed and the ledger would keep
-- the balance it had - the worst failure this schema has, because nothing about it looks wrong.
-- The parent is ONE lookup on the root, which is what the root is for: a child of an operation names 'operations'
-- and nothing else, and the eight type tables stay the business of the eight triggers that keep the moment current.
DROP TRIGGER IF EXISTS fees_after_insert;
CREATE TRIGGER fees_after_insert AFTER INSERT ON fees FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= (SELECT timestamp FROM operations WHERE id = NEW.operation_id);
    DELETE FROM trades_opened WHERE timestamp >= (SELECT timestamp FROM operations WHERE id = NEW.operation_id);
END;
DROP TRIGGER IF EXISTS fees_after_update;
CREATE TRIGGER fees_after_update AFTER UPDATE ON fees FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= (SELECT timestamp FROM operations WHERE id = OLD.operation_id);
    DELETE FROM trades_opened WHERE timestamp >= (SELECT timestamp FROM operations WHERE id = OLD.operation_id);
END;
DROP TRIGGER IF EXISTS fees_after_delete;
CREATE TRIGGER fees_after_delete AFTER DELETE ON fees FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= (SELECT timestamp FROM operations WHERE id = OLD.operation_id);
    DELETE FROM trades_opened WHERE timestamp >= (SELECT timestamp FROM operations WHERE id = OLD.operation_id);
END;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=73 WHERE name='SchemaVersion';
COMMIT;
