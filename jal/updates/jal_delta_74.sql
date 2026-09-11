BEGIN TRANSACTION;
--------------------------------------------------------------------------------
-- THE PROCESSING ORDER LEAVES THE SCHEMA
--------------------------------------------------------------------------------
-- 'operation_sequence' listed every part of every operation and sorted them into the order the ledger is processed
-- in. Both halves now live in the operation classes: each one states its own parts (LedgerTransaction.sequence_parts)
-- and its own rank among operations of the same second (LedgerTransaction.LedgerRank), and Ledger.refresh_sequence()
-- builds the query from them. Seven of the deltas before this one exist only to rewrite this view; from here a new
-- operation type, or a new part of one, needs no migration at all.
--
-- The table is FILLED HERE and not left to the first rebuild. It is derived data, but from the moment this delta
-- commits it is what the operations list, the balances and the settlement checks read - and a rebuild is something
-- the user may decline (ledger.py: SILENT_REBUILD_THRESHOLD). An upgraded database that started with an empty
-- sequence would show no operation at all until the next one.
--
-- This is the last statement that can use the view, so it uses the view: the fill is the view's own ORDER BY, which
-- keeps the upgrade independent of the code that replaces it. The two are proved identical by test_ledger.py.
DELETE FROM ledger_sequence;
INSERT INTO ledger_sequence (operation_id, opart, timestamp, account_id)
    SELECT oid, opart, timestamp, account_id FROM operation_sequence ORDER BY timestamp, seq, opart, oid;
DROP VIEW IF EXISTS operation_sequence;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=74 WHERE name='SchemaVersion';
COMMIT;
