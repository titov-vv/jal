BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 0;
--------------------------------------------------------------------------------
DROP VIEW IF EXISTS operation_sequence;
DELETE FROM settings WHERE id=1;
--------------------------------------------------------------------------------
ALTER TABLE actions RENAME COLUMN id TO oid;
ALTER TABLE actions RENAME COLUMN op_type TO otype;
ALTER TABLE asset_payments RENAME COLUMN id TO oid;
ALTER TABLE asset_payments RENAME COLUMN op_type TO otype;
ALTER TABLE asset_actions RENAME COLUMN id TO oid;
ALTER TABLE asset_actions RENAME COLUMN op_type TO otype;
ALTER TABLE trades RENAME COLUMN id TO oid;
ALTER TABLE trades RENAME COLUMN op_type TO otype;
ALTER TABLE transfers RENAME COLUMN id TO oid;
ALTER TABLE transfers RENAME COLUMN op_type TO otype;
ALTER TABLE term_deposits RENAME COLUMN id TO oid;
ALTER TABLE term_deposits RENAME COLUMN op_type TO otype;
--------------------------------------------------------------------------------
ALTER TABLE ledger RENAME COLUMN op_type TO otype;
ALTER TABLE ledger RENAME COLUMN operation_id TO oid;
ALTER TABLE ledger_totals RENAME COLUMN op_type TO otype;
ALTER TABLE ledger_totals RENAME COLUMN operation_id TO oid;
DROP INDEX IF EXISTS ledger_totals_by_timestamp;
CREATE INDEX ledger_totals_by_timestamp ON ledger_totals (timestamp);
DROP INDEX IF EXISTS ledger_totals_by_operation_book;
CREATE INDEX ledger_totals_by_operation_book ON ledger_totals (otype, oid, book_account);
--------------------------------------------------------------------------------
DROP TABLE IF EXISTS trades_opened;
CREATE TABLE trades_opened (
    id            INTEGER PRIMARY KEY UNIQUE NOT NULL,
    timestamp     INTEGER NOT NULL,
    otype         INTEGER NOT NULL,
    oid           INTEGER NOT NULL,
    account_id    INTEGER REFERENCES accounts (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    asset_id      INTEGER NOT NULL REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE,
    price         TEXT    NOT NULL,
    remaining_qty TEXT    NOT NULL
);
DROP INDEX IF EXISTS open_trades_by_oid;
CREATE INDEX open_trades_by_oid ON trades_opened (timestamp, otype, oid);
--------------------------------------------------------------------------------
DROP TABLE IF EXISTS trades_closed;
CREATE TABLE trades_closed (
    id              INTEGER PRIMARY KEY UNIQUE NOT NULL,
    account_id      INTEGER NOT NULL,
    asset_id        INTEGER NOT NULL,
    open_otype      INTEGER NOT NULL,
    open_oid        INTEGER NOT NULL,
    open_timestamp  INTEGER NOT NULL,
    open_price      TEXT    NOT NULL,
    close_otype     INTEGER NOT NULL,
    close_oid       INTEGER NOT NULL,
    close_timestamp INTEGER NOT NULL,
    close_price     TEXT    NOT NULL,
    qty             TEXT    NOT NULL
);
--------------------------------------------------------------------------------
CREATE VIEW operation_sequence AS
SELECT m.otype, m.oid, m.timestamp, m.account_id, subtype
FROM
(
    SELECT otype, 1 AS seq, oid, timestamp, account_id, 0 AS subtype FROM actions
    UNION ALL
    SELECT otype, 2 AS seq, oid, timestamp, account_id, type AS subtype FROM asset_payments
    UNION ALL
    SELECT otype, 3 AS seq, oid, timestamp, account_id, type AS subtype FROM asset_actions
    UNION ALL
    SELECT otype, 4 AS seq, oid, timestamp, account_id, 0 AS subtype FROM trades
    UNION ALL
    SELECT otype, 5 AS seq, oid, withdrawal_timestamp AS timestamp, withdrawal_account AS account_id, -1 AS subtype FROM transfers
    UNION ALL
    SELECT otype, 5 AS seq, oid, withdrawal_timestamp AS timestamp, fee_account AS account_id, 0 AS subtype FROM transfers WHERE NOT fee IS NULL
    UNION ALL
    SELECT otype, 5 AS seq, oid, deposit_timestamp AS timestamp, deposit_account AS account_id, 1 AS subtype FROM transfers
    UNION ALL
    SELECT td.otype, 6 AS seq, td.oid, da.timestamp, td.account_id, da.id AS subtype FROM deposit_actions AS da LEFT JOIN term_deposits AS td ON da.deposit_id=td.oid WHERE da.action_type<=100
) AS m
ORDER BY m.timestamp, m.seq, m.subtype, m.oid;
--------------------------------------------------------------------------------
-- Triggers update after change of 'settings' table
-- Deletion should happen on base table of the view
DROP TRIGGER IF EXISTS on_asset_ext_delete;
CREATE TRIGGER on_asset_ext_delete INSTEAD OF DELETE ON assets_ext FOR EACH ROW
BEGIN
    DELETE FROM assets WHERE id = OLD.id;
END;
-- Ledger cleanup after modification
DROP TRIGGER IF EXISTS action_details_after_delete;
CREATE TRIGGER action_details_after_delete AFTER DELETE ON action_details FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= (SELECT timestamp FROM actions WHERE oid = OLD.pid);
END;
-- Ledger cleanup after modification
DROP TRIGGER IF EXISTS action_details_after_insert;
CREATE TRIGGER action_details_after_insert AFTER INSERT ON action_details FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= (SELECT timestamp FROM actions WHERE oid = NEW.pid);
END;
-- Ledger cleanup after modification
DROP TRIGGER IF EXISTS action_details_after_update;
CREATE TRIGGER action_details_after_update AFTER UPDATE ON action_details FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= (SELECT timestamp FROM actions WHERE oid = OLD.pid );
END;
-- Ledger cleanup after modification and deletion of detailed records
DROP TRIGGER IF EXISTS actions_after_delete;
CREATE TRIGGER actions_after_delete AFTER DELETE ON actions FOR EACH ROW
BEGIN
    DELETE FROM action_details WHERE pid = OLD.id;
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp;
END;
-- Ledger cleanup after modification
DROP TRIGGER IF EXISTS actions_after_insert;
CREATE TRIGGER actions_after_insert AFTER INSERT ON actions FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= NEW.timestamp;
END;
-- Ledger cleanup after modification
DROP TRIGGER IF EXISTS actions_after_update;
CREATE TRIGGER actions_after_update AFTER UPDATE OF timestamp, account_id, peer_id ON actions FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
END;
-- Ledger and trades cleanup after modification
DROP TRIGGER IF EXISTS asset_payments_after_delete;
CREATE TRIGGER asset_payments_after_delete AFTER DELETE ON asset_payments FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp;
END;
-- Ledger and trades cleanup after modification
DROP TRIGGER IF EXISTS asset_payments_after_insert;
CREATE TRIGGER asset_payments_after_insert AFTER INSERT ON asset_payments FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= NEW.timestamp;
END;
-- Ledger and trades cleanup after modification
DROP TRIGGER IF EXISTS asset_payments_after_update;
CREATE TRIGGER asset_payments_after_update AFTER UPDATE OF timestamp, type, account_id, asset_id, amount, tax ON asset_payments FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
END;
-- Ledger and trades cleanup after modification
DROP TRIGGER IF EXISTS trades_after_delete;
CREATE TRIGGER trades_after_delete AFTER DELETE ON trades FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp;
END;
-- Ledger and trades cleanup after modification
DROP TRIGGER IF EXISTS trades_after_insert;
CREATE TRIGGER trades_after_insert AFTER INSERT ON trades FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= NEW.timestamp;
END;
-- Ledger and trades cleanup after modification
DROP TRIGGER IF EXISTS trades_after_update;
CREATE TRIGGER trades_after_update AFTER UPDATE OF timestamp, account_id, asset_id, qty, price, fee ON trades FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
END;
-- Ledger and trades cleanup after modification
DROP TRIGGER IF EXISTS asset_action_after_delete;
CREATE TRIGGER asset_action_after_delete AFTER DELETE ON asset_actions FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp;
END;
-- Ledger and trades cleanup after modification
DROP TRIGGER IF EXISTS asset_action_after_insert;
CREATE TRIGGER asset_action_after_insert AFTER INSERT ON asset_actions FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= NEW.timestamp;
END;
-- Ledger and trades cleanup after modification
DROP TRIGGER IF EXISTS asset_action_after_update;
CREATE TRIGGER asset_action_after_update AFTER UPDATE OF timestamp, account_id, type, asset_id, qty ON asset_actions FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp  OR timestamp >= NEW.timestamp;
END;
-- Ledger cleanup after modification
DROP TRIGGER IF EXISTS asset_result_after_delete;
CREATE TRIGGER asset_result_after_delete AFTER DELETE ON action_results FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= (SELECT timestamp FROM asset_actions WHERE oid = OLD.action_id);
END;
-- Ledger cleanup after modification
DROP TRIGGER IF EXISTS asset_result_after_insert;
CREATE TRIGGER asset_result_after_insert AFTER INSERT ON action_results FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= (SELECT timestamp FROM asset_actions WHERE oid = NEW.action_id);
END;
-- Ledger cleanup after modification
DROP TRIGGER IF EXISTS asset_result_after_update;
CREATE TRIGGER asset_result_after_update AFTER UPDATE OF asset_id, qty, value_share ON action_results FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= (SELECT timestamp FROM asset_actions WHERE oid = OLD.action_id);
END;
-- Ledger cleanup after modification
DROP TRIGGER IF EXISTS transfers_after_delete;
CREATE TRIGGER transfers_after_delete AFTER DELETE ON transfers FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.withdrawal_timestamp OR timestamp >= OLD.deposit_timestamp;
END;
-- Ledger cleanup after modification
DROP TRIGGER IF EXISTS transfers_after_insert;
CREATE TRIGGER transfers_after_insert AFTER INSERT ON transfers FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= NEW.withdrawal_timestamp OR timestamp >= NEW.deposit_timestamp;
END;
-- Ledger cleanup after modification
DROP TRIGGER IF EXISTS transfers_after_update;
CREATE TRIGGER transfers_after_update AFTER UPDATE OF withdrawal_timestamp, deposit_timestamp, withdrawal_account, deposit_account, fee_account, withdrawal, deposit, fee, asset ON transfers FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.withdrawal_timestamp OR timestamp >= OLD.deposit_timestamp OR
                timestamp >= NEW.withdrawal_timestamp OR timestamp >= NEW.deposit_timestamp;
END;
-- Ledger cleanup after modification
DROP TRIGGER IF EXISTS deposit_action_after_delete;
CREATE TRIGGER deposit_action_after_delete AFTER DELETE ON deposit_actions FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp;
END;
-- Ledger cleanup after modification
DROP TRIGGER IF EXISTS deposit_action_after_insert;
CREATE TRIGGER deposit_action_after_insert AFTER INSERT ON deposit_actions FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= NEW.timestamp;
END;
-- Ledger cleanup after modification
DROP TRIGGER IF EXISTS deposit_action_after_update;
CREATE TRIGGER deposit_action_after_update AFTER UPDATE OF timestamp, account_id, type, asset_id, qty ON deposit_actions FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
END;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 1;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=56 WHERE name='SchemaVersion';
INSERT OR REPLACE INTO settings(id, name, value) VALUES (7, 'RebuildDB', 1);
COMMIT;
VACUUM;