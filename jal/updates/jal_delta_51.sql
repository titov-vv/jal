BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 0;
--------------------------------------------------------------------------------
CREATE TABLE trades_sequence (
    id              INTEGER PRIMARY KEY UNIQUE NOT NULL,
    account_id      INTEGER NOT NULL,
    asset_id        INTEGER NOT NULL,
    open_op_type    INTEGER NOT NULL,
    open_op_id      INTEGER NOT NULL,
    open_timestamp  INTEGER NOT NULL,
    open_price      TEXT    NOT NULL,
    close_op_type   INTEGER,
    close_op_id     INTEGER,
    close_timestamp INTEGER,
    close_price     TEXT,
    qty             TEXT    NOT NULL
);

INSERT INTO trades_sequence (id, account_id, asset_id, open_op_type, open_op_id, open_timestamp, open_price, close_op_type, close_op_id, close_timestamp, close_price, qty)
SELECT id, account_id, asset_id, open_op_type, open_op_id, open_timestamp, open_price, close_op_type, close_op_id, close_timestamp, close_price, qty FROM trades_closed;

DROP TABLE trades_closed;

DROP TRIGGER IF EXISTS on_closed_trade_delete;
CREATE TRIGGER on_closed_trade_delete
    AFTER DELETE ON trades_sequence
    FOR EACH ROW
    WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    UPDATE trades_opened
    SET remaining_qty = remaining_qty + OLD.qty
    WHERE op_type=OLD.open_op_type AND operation_id=OLD.open_op_id AND account_id=OLD.account_id AND asset_id = OLD.asset_id;
END;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 1;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=51 WHERE name='SchemaVersion';
INSERT OR REPLACE INTO settings(id, name, value) VALUES (7, 'RebuildDB', 1);
COMMIT;
-- Reduce file size
VACUUM;