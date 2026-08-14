BEGIN TRANSACTION;
--------------------------------------------------------------------------------
-- Two indexes for 'ledger'. Why they are needed:
-- 'ledger_by_time' leads on 'timestamp', so a query that pins an account and asks for a
-- point-in-time balance ("WHERE account_id=? AND asset_id=? AND timestamp<=?") could only be served as a scan of
-- the whole timestamp range - EXPLAIN QUERY PLAN reported "SEARCH ledger USING INDEX ledger_by_time (timestamp<?)".
-- The balance sheet asks that question once per account at every start-up, so the cost grew with the ledger.
-- 'peer_id' had no index at all, so counting the operations of one peer scanned the entire table.
--
-- Column order of 'ledger_by_account_asset' follows how the callers filter: the equality columns first
-- (account_id, asset_id, book_account - see JalAccount.get_asset_amount() and assets_list()), the inequality
-- column 'timestamp' last, which is the only order that lets SQLite seek instead of scan.
DROP INDEX IF EXISTS ledger_by_account_asset;
CREATE INDEX ledger_by_account_asset ON ledger (account_id, asset_id, book_account, timestamp);
DROP INDEX IF EXISTS ledger_by_peer;
CREATE INDEX ledger_by_peer ON ledger (peer_id);
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=63 WHERE name='SchemaVersion';
COMMIT;
