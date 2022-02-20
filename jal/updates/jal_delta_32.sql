BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 0;
--------------------------------------------------------------------------------
-- Add extra type to split ETFs and Funds
UPDATE asset_types SET name='ETFs' WHERE id=4;
INSERT INTO asset_types (id, name) VALUES (8, 'Funds');
--------------------------------------------------------------------------------
CREATE INDEX details_by_pid ON action_details (pid);
--------------------------------------------------------------------------------
-- Data cleanup
UPDATE action_details SET amount_alt=0 WHERE amount_alt='';
--------------------------------------------------------------------------------
-- Simplify view and handle logic in code
DROP VIEW IF EXISTS all_operations;
DROP VIEW IF EXISTS all_transactions;
DROP VIEW IF EXISTS operation_sequence;
CREATE VIEW operation_sequence AS
SELECT m.op_type, m.id, m.timestamp, m.account_id, subtype
FROM
(
    SELECT op_type, 1 AS seq, id, timestamp, account_id, 0 AS subtype FROM actions
    UNION ALL
    SELECT op_type, 2 AS seq, id, timestamp, account_id, type AS subtype FROM dividends
    UNION ALL
    SELECT op_type, 3 AS seq, id, timestamp, account_id, type AS subtype FROM corp_actions
    UNION ALL
    SELECT op_type, 4 AS seq, id, timestamp, account_id, 0 AS subtype FROM trades
    UNION ALL
    SELECT op_type, 5 AS seq, id, withdrawal_timestamp AS timestamp, withdrawal_account AS account_id, -1 AS subtype FROM transfers
    UNION ALL
    SELECT op_type, 5 AS seq, id, withdrawal_timestamp AS timestamp, fee_account AS account_id, 0 AS subtype FROM transfers WHERE NOT fee IS NULL
    UNION ALL
    SELECT op_type, 5 AS seq, id, deposit_timestamp AS timestamp, deposit_account AS account_id, 1 AS subtype FROM transfers
) AS m
ORDER BY m.timestamp, m.seq, m.subtype, m.id;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 1;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=32 WHERE name='SchemaVersion';
COMMIT;
