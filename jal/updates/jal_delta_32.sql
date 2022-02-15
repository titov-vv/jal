BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 0;
--------------------------------------------------------------------------------
CREATE INDEX details_by_pid ON action_details (pid);
--------------------------------------------------------------------------------
-- Simplify view and handle logic in code
DROP VIEW IF EXISTS all_operations;
DROP VIEW IF EXISTS operation_sequence;
CREATE VIEW operation_sequence AS
SELECT m.op_type, m.id, m.timestamp, m.account_id, subtype
FROM
(
    SELECT op_type, id, timestamp, account_id, NULL AS subtype FROM actions
    UNION ALL
    SELECT op_type, id, timestamp, account_id, type AS subtype FROM dividends
    UNION ALL
    SELECT op_type, id, timestamp, account_id, type AS subtype FROM corp_actions
    UNION ALL
    SELECT op_type, id, timestamp, account_id, NULL AS subtype FROM trades
    UNION ALL
    SELECT op_type, id, timestamp, account_id, subtype FROM
    (
        SELECT op_type, id, withdrawal_timestamp AS timestamp, withdrawal_account AS account_id, -1 AS subtype FROM transfers
        UNION ALL
        SELECT op_type, id, withdrawal_timestamp AS timestamp, fee_account AS account_id, 0 AS subtype FROM transfers WHERE NOT fee IS NULL
        UNION ALL
        SELECT op_type, id, deposit_timestamp AS timestamp, deposit_account AS account_id, 1 AS subtype FROM transfers
        ORDER BY id
    )
) AS m
ORDER BY m.timestamp;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 1;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=32 WHERE name='SchemaVersion';
COMMIT;
