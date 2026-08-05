BEGIN TRANSACTION;
--------------------------------------------------------------------------------
-- Table: chain_balances - the balance an on-chain account REALLY holds of an asset, as the chain itself reports it.
--
-- It is VALUATION DATA, not operations, and it is deliberately kept out of the ledger. Two things make a chain
-- balance drift away from the sum of the movements JAL imported, and neither of them is an economic event a fetcher
-- could have missed:
--   * a REBASING receipt token (an Aave aToken, see AssetData.Rebasing) grows through a protocol index that rises
--     every block, emitting nothing at all;
--   * a STAKING BOX accrues yield inside the container - Solana credits epoch rewards straight into the stake
--     account, Hyperliquid auto-compounds them into the delegation - again with no transaction to import.
-- In both cases the accrued quantity is an UNREALIZED gain, and JAL's convention for unrealized value is valuation
-- data (a quote), not an operation. It is recognized as income only when it is REALIZED, at withdrawal, where the
-- fetchers already split principal from yield.
--
-- Appended to, never updated: one row per (account, asset) per refresh, and the latest row drives the display, so
-- the series is a per-position yield history for free. The unique key mirrors 'quotes', so two refreshes within one
-- second replace rather than duplicate.
--
-- A pure CREATE: nothing existing is read, rewritten or dropped, so this update cannot touch a single financial
-- record. The table starts empty and stays empty until a balance reader fills it, which means a database upgraded
-- by this delta behaves exactly as it did before.
CREATE TABLE chain_balances (
    id         INTEGER PRIMARY KEY UNIQUE NOT NULL,
    timestamp  INTEGER NOT NULL,                     -- when the balance was read from the chain
    account_id INTEGER NOT NULL REFERENCES accounts (id) ON DELETE CASCADE ON UPDATE CASCADE,
    asset_id   INTEGER NOT NULL REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE,
    amount     TEXT    NOT NULL                      -- balance the chain reports, in human units
);
CREATE UNIQUE INDEX chain_balances_uniqueness ON chain_balances (account_id, asset_id, timestamp);
--------------------------------------------------------------------------------
-- AssetData.Rebasing (datatype 5) needs no schema of its own - 'asset_data' is an EAV table and the new attribute is
-- just another datatype in it. It is NOT set on any asset here: asset ids differ from one database to the next, and
-- the flag decides whether a quantity is added to a position, so it is set by hand per asset (Data tab of the asset
-- editor) rather than guessed at by a migration from a ticker prefix.
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=62 WHERE name='SchemaVersion';
COMMIT;
