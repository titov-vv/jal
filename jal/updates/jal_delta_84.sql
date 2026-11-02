BEGIN TRANSACTION;
--------------------------------------------------------------------------------
-- SWAP TREATMENT: AUTO / SALE / CONVERSION
--------------------------------------------------------------------------------
ALTER TABLE swaps ADD COLUMN treatment INTEGER NOT NULL DEFAULT (0);
DROP TRIGGER IF EXISTS swaps_after_update;
CREATE TRIGGER swaps_after_update AFTER UPDATE OF timestamp, account_id, out_symbol_id, out_qty, in_timestamp, in_account_id, in_symbol_id, in_qty, treatment ON swaps FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
    UPDATE operations SET timestamp = COALESCE(MIN(NEW.timestamp, COALESCE(NEW.in_timestamp, NEW.timestamp)), 0) WHERE id = NEW.oid;
END;
--------------------------------------------------------------------------------
-- A PEG EDIT RE-RESOLVES EVERY AUTO SWAP OF THAT ASSET
--------------------------------------------------------------------------------
DROP TRIGGER IF EXISTS asset_data_peg_after_insert;
CREATE TRIGGER asset_data_peg_after_insert AFTER INSERT ON asset_data FOR EACH ROW WHEN NEW.datatype = 8
BEGIN
    DELETE FROM ledger WHERE timestamp >= (SELECT MIN(w.timestamp) FROM swaps AS w JOIN asset_symbol AS s ON s.id IN (w.out_symbol_id, w.in_symbol_id) WHERE s.asset_id = NEW.asset_id);
    DELETE FROM trades_opened WHERE timestamp >= (SELECT MIN(w.timestamp) FROM swaps AS w JOIN asset_symbol AS s ON s.id IN (w.out_symbol_id, w.in_symbol_id) WHERE s.asset_id = NEW.asset_id);
END;
DROP TRIGGER IF EXISTS asset_data_peg_after_update;
CREATE TRIGGER asset_data_peg_after_update AFTER UPDATE ON asset_data FOR EACH ROW WHEN OLD.datatype = 8 OR NEW.datatype = 8
BEGIN
    DELETE FROM ledger WHERE timestamp >= (SELECT MIN(w.timestamp) FROM swaps AS w JOIN asset_symbol AS s ON s.id IN (w.out_symbol_id, w.in_symbol_id) WHERE s.asset_id IN (OLD.asset_id, NEW.asset_id));
    DELETE FROM trades_opened WHERE timestamp >= (SELECT MIN(w.timestamp) FROM swaps AS w JOIN asset_symbol AS s ON s.id IN (w.out_symbol_id, w.in_symbol_id) WHERE s.asset_id IN (OLD.asset_id, NEW.asset_id));
END;
DROP TRIGGER IF EXISTS asset_data_peg_after_delete;
CREATE TRIGGER asset_data_peg_after_delete AFTER DELETE ON asset_data FOR EACH ROW WHEN OLD.datatype = 8
BEGIN
    DELETE FROM ledger WHERE timestamp >= (SELECT MIN(w.timestamp) FROM swaps AS w JOIN asset_symbol AS s ON s.id IN (w.out_symbol_id, w.in_symbol_id) WHERE s.asset_id = OLD.asset_id);
    DELETE FROM trades_opened WHERE timestamp >= (SELECT MIN(w.timestamp) FROM swaps AS w JOIN asset_symbol AS s ON s.id IN (w.out_symbol_id, w.in_symbol_id) WHERE s.asset_id = OLD.asset_id);
END;
--------------------------------------------------------------------------------
INSERT OR REPLACE INTO settings(name, value) VALUES ('RebuildDB', 1);
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=84 WHERE name='SchemaVersion';
COMMIT;
