BEGIN TRANSACTION;
--------------------------------------------------------------------------------
-- GAS OF A SWAP AND OF A CONVERSION BECOMES A PART OF ITS OWN
--------------------------------------------------------------------------------
-- The fee was processed inside the operation's main part and drawn as a third line of its row. It becomes a
-- sequence part of its own (opart 2), the way a transfer and a bridge fee already are, so it gets a row of its own.
DROP VIEW IF EXISTS operation_sequence;
CREATE VIEW operation_sequence AS SELECT m.otype, m.oid, opart, m.timestamp, m.account_id
FROM
(
    SELECT otype, 1 AS seq, oid, 0 AS opart, timestamp, account_id FROM actions
    UNION ALL
    SELECT otype, 2 AS seq, oid, 0 AS opart, timestamp, account_id FROM asset_payments
    UNION ALL
    SELECT otype, 3 AS seq, oid, 0 AS opart, timestamp, account_id FROM asset_actions
    UNION ALL
    SELECT otype, 4 AS seq, oid, 0 AS opart, timestamp, account_id FROM trades
    UNION ALL
    SELECT otype, 5 AS seq, oid, -1 AS opart, withdrawal_timestamp AS timestamp, withdrawal_account AS account_id FROM transfers WHERE NOT withdrawal_account IS NULL
    UNION ALL
    SELECT otype, 5 AS seq, oid, 0 AS opart, withdrawal_timestamp AS timestamp, fee_account AS account_id FROM transfers WHERE NOT fee IS NULL
    UNION ALL
    SELECT otype, 5 AS seq, oid, 1 AS opart, deposit_timestamp AS timestamp, deposit_account AS account_id FROM transfers WHERE NOT deposit_account IS NULL
    UNION ALL
    SELECT otype, 6 AS seq, oid, 0 AS opart, timestamp, account_id FROM conversions
    UNION ALL
    SELECT otype, 6 AS seq, oid, 2 AS opart, timestamp, account_id FROM conversions WHERE NOT fee_qty IS NULL
    UNION ALL
    SELECT otype, 7 AS seq, oid, 0 AS opart, timestamp, account_id FROM swaps WHERE in_account_id IS NULL OR in_account_id=account_id
    UNION ALL
    SELECT otype, 7 AS seq, oid, -1 AS opart, timestamp, account_id FROM swaps WHERE NOT in_account_id IS NULL AND in_account_id<>account_id
    UNION ALL
    SELECT otype, 7 AS seq, oid, 1 AS opart, COALESCE(in_timestamp, timestamp) AS timestamp, in_account_id AS account_id FROM swaps WHERE NOT in_account_id IS NULL AND in_account_id<>account_id
    UNION ALL
    -- Gas is burned on the source chain, so the fee part of a cross-chain swap rides its sending leg
    SELECT otype, 7 AS seq, oid, 2 AS opart, timestamp, account_id FROM swaps WHERE NOT fee_qty IS NULL
    UNION ALL
    SELECT otype, 8 AS seq, oid, -1 AS opart, out_timestamp AS timestamp, out_account_id AS account_id FROM bridges
    UNION ALL
    SELECT otype, 8 AS seq, oid, 0 AS opart, out_timestamp AS timestamp, out_account_id AS account_id FROM bridges WHERE NOT fee_qty IS NULL
    UNION ALL
    SELECT otype, 8 AS seq, oid, 1 AS opart, in_timestamp AS timestamp, in_account_id AS account_id FROM bridges WHERE NOT in_account_id IS NULL
) AS m
ORDER BY m.timestamp, m.seq, m.opart, m.oid;  -- First sort by sequence and part to enforce right operation processing order
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=70 WHERE name='SchemaVersion';
COMMIT;
