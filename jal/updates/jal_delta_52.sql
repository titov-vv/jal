BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 0;
--------------------------------------------------------------------------------
DROP TABLE IF EXISTS term_deposits;
CREATE TABLE term_deposits (
    id         INTEGER PRIMARY KEY UNIQUE NOT NULL,
    op_type    INTEGER NOT NULL DEFAULT (6),
    account_id INTEGER NOT NULL REFERENCES accounts (id) ON DELETE CASCADE ON UPDATE CASCADE,
    note       TEXT
);
DROP TABLE IF EXISTS deposit_actions;
CREATE TABLE deposit_actions (
    id          INTEGER PRIMARY KEY UNIQUE NOT NULL,
    deposit_id  INTEGER REFERENCES term_deposits (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    timestamp   INTEGER NOT NULL,
    action_type INTEGER NOT NULL,
    amount      TEXT    NOT NULL
);
DROP INDEX IF EXISTS deposit_actions_idx;
CREATE UNIQUE INDEX deposit_actions_idx ON deposit_actions (deposit_id, timestamp, action_type);


DROP TRIGGER IF EXISTS deposit_action_after_delete;
CREATE TRIGGER deposit_action_after_delete
      AFTER DELETE ON deposit_actions
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp;
END;

DROP TRIGGER IF EXISTS deposit_action_after_insert;
CREATE TRIGGER deposit_action_after_insert
      AFTER INSERT ON deposit_actions
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= NEW.timestamp;
END;

DROP TRIGGER IF EXISTS deposit_action_after_update;
CREATE TRIGGER deposit_action_after_update
      AFTER UPDATE OF timestamp, account_id, type, asset_id, qty ON deposit_actions
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
END;


DROP VIEW IF EXISTS operation_sequence;
CREATE VIEW operation_sequence AS
SELECT m.op_type, m.id, m.timestamp, m.account_id, subtype
FROM
(
    SELECT op_type, 1 AS seq, id, timestamp, account_id, 0 AS subtype FROM actions
    UNION ALL
    SELECT op_type, 2 AS seq, id, timestamp, account_id, type AS subtype FROM dividends
    UNION ALL
    SELECT op_type, 3 AS seq, id, timestamp, account_id, type AS subtype FROM asset_actions
    UNION ALL
    SELECT op_type, 4 AS seq, id, timestamp, account_id, 0 AS subtype FROM trades
    UNION ALL
    SELECT op_type, 5 AS seq, id, withdrawal_timestamp AS timestamp, withdrawal_account AS account_id, -1 AS subtype FROM transfers
    UNION ALL
    SELECT op_type, 5 AS seq, id, withdrawal_timestamp AS timestamp, fee_account AS account_id, 0 AS subtype FROM transfers WHERE NOT fee IS NULL
    UNION ALL
    SELECT op_type, 5 AS seq, id, deposit_timestamp AS timestamp, deposit_account AS account_id, 1 AS subtype FROM transfers
    UNION ALL
    SELECT td.op_type, 6 AS seq, td.id, da.timestamp, td.account_id, da.id AS subtype FROM deposit_actions AS da LEFT JOIN term_deposits AS td ON da.deposit_id=td.id WHERE da.action_type<=100
) AS m
ORDER BY m.timestamp, m.seq, m.subtype, m.id;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 1;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=52 WHERE name='SchemaVersion';
COMMIT;
-- Reduce file size
VACUUM;