BEGIN TRANSACTION;
--------------------------------------------------------------------------------
-- New table for a flexible set of per-account attributes.
-- Becomes the home for number/credit/country/precision etc.
CREATE TABLE account_data (
    id         INTEGER PRIMARY KEY UNIQUE NOT NULL,
    account_id INTEGER NOT NULL REFERENCES accounts (id) ON DELETE CASCADE ON UPDATE CASCADE,
    datatype   INTEGER NOT NULL,
    value      TEXT    NOT NULL
);
CREATE UNIQUE INDEX account_data_uniqueness ON account_data (account_id, datatype);
--------------------------------------------------------------------------------
-- Rework 'tag_id' (which was used as an account type) into an 'account_type'
-- enum column (values match PredefinedAccountType). Custom account tags fall back to Cash (2).
ALTER TABLE accounts ADD COLUMN account_type INTEGER NOT NULL DEFAULT (2);
UPDATE accounts SET account_type = CASE WHEN tag_id IN (2, 3, 4, 5) THEN tag_id ELSE 2 END;
--------------------------------------------------------------------------------
-- Move number / credit / country_id / precision into 'account_data'.
INSERT INTO account_data (account_id, datatype, value)
    SELECT id, 1, number                 FROM accounts WHERE number IS NOT NULL;   -- AccountData.Number
INSERT INTO account_data (account_id, datatype, value)
    SELECT id, 2, credit                 FROM accounts WHERE credit <> '0';        -- AccountData.Credit
INSERT INTO account_data (account_id, datatype, value)
    SELECT id, 3, CAST(country_id AS TEXT) FROM accounts WHERE country_id <> 0;    -- AccountData.Country
INSERT INTO account_data (account_id, datatype, value)
    SELECT id, 4, CAST(precision AS TEXT)  FROM accounts WHERE precision <> 2;     -- AccountData.Precision
--------------------------------------------------------------------------------
ALTER TABLE accounts DROP COLUMN tag_id;
ALTER TABLE accounts DROP COLUMN number;
ALTER TABLE accounts DROP COLUMN country_id;
ALTER TABLE accounts DROP COLUMN precision;
ALTER TABLE accounts DROP COLUMN credit;
--------------------------------------------------------------------------------
-- Unknown/spam token policy: locally blacklisted tokens are never imported and never
-- become assets/symbols, so scam names/tickers stay out of the asset tables entirely.
CREATE TABLE token_blacklist (
    id          INTEGER PRIMARY KEY UNIQUE NOT NULL,
    location_id INTEGER NOT NULL,                    -- blockchain, see AssetLocation.*_BLOCKCHAIN
    address     TEXT    NOT NULL,                    -- contract/mint address, normalized
    name_hint   TEXT    NOT NULL DEFAULT (''),       -- ticker/name seen on-chain, informational only
    added_ts    INTEGER NOT NULL DEFAULT (0),
    auto        INTEGER NOT NULL DEFAULT (1)         -- 1 = auto-quarantined, 0 = added by user
);
CREATE UNIQUE INDEX token_blacklist_uniqueness ON token_blacklist (location_id, address);
--------------------------------------------------------------------------------
-- Local cache of downloaded allow-/block- token lists (see TokenList / TokenListKind)
CREATE TABLE token_list_cache (
    id          INTEGER PRIMARY KEY UNIQUE NOT NULL,
    list_id     INTEGER NOT NULL,                    -- source list, see TokenList
    kind        INTEGER NOT NULL,                    -- TokenListKind: 1 = allow, 2 = block
    location_id INTEGER NOT NULL,
    address     TEXT    NOT NULL,                    -- normalized
    symbol      TEXT    NOT NULL DEFAULT (''),
    name        TEXT    NOT NULL DEFAULT ('')
);
CREATE UNIQUE INDEX token_list_cache_uniqueness ON token_list_cache (list_id, location_id, address);
-- Membership is always asked as "is this address on ANY allow/block list for this chain"
CREATE INDEX token_list_cache_lookup ON token_list_cache (kind, location_id, address);
-- Timestamp of the last successful fetch per (list, chain) - drives the refresh interval
CREATE TABLE token_list_updates (
    id          INTEGER PRIMARY KEY UNIQUE NOT NULL,
    list_id     INTEGER NOT NULL,
    location_id INTEGER NOT NULL,
    updated_ts  INTEGER NOT NULL DEFAULT (0)
);
CREATE UNIQUE INDEX token_list_updates_uniqueness ON token_list_updates (list_id, location_id);
--------------------------------------------------------------------------------
-- A transfer fee may be paid in an asset rather than in the money of the fee account: on-chain gas is
-- burned in the native coin of the blockchain (TRX on Tron, ETH on Ethereum), which may or may not be
-- the asset being transferred. NULL keeps the historical meaning - the fee is in the fee account currency.
--
-- The table is rebuilt rather than extended with ALTER TABLE ADD COLUMN, which can only append: 'fee_symbol_id'
-- belongs next to 'symbol_id' and 'note' stays last, so that a migrated database is identical to one created
-- from jal_init.sql. Order of operations matters here:
--  - the triggers are dropped first, so that the rename below neither rewrites nor validates them;
--  - 'operation_sequence' is dropped too, because ALTER TABLE ... RENAME validates every view in the schema and
--    would fail on a view still pointing at the table being replaced;
--  - nothing REFERENCES transfers, and foreign keys are off while deltas run, so dropping it cascades nowhere.
DROP TRIGGER IF EXISTS transfers_after_delete;
DROP TRIGGER IF EXISTS transfers_after_insert;
DROP TRIGGER IF EXISTS transfers_after_update;
DROP VIEW IF EXISTS operation_sequence;

CREATE TABLE transfers_new (
    oid                  INTEGER     PRIMARY KEY UNIQUE NOT NULL,     -- Unique operation id
    otype                INTEGER     NOT NULL DEFAULT (4),            -- Operation type (4 = transfer)
    withdrawal_timestamp INTEGER     NOT NULL,                        -- When initiated
    withdrawal_account   INTEGER     NOT NULL REFERENCES accounts (id) ON DELETE CASCADE ON UPDATE CASCADE,  -- From where transfer is
    withdrawal           TEXT        NOT NULL,                        -- Amount sent
    deposit_timestamp    INTEGER     NOT NULL,                        -- When received
    deposit_account      INTEGER     NOT NULL REFERENCES accounts (id) ON DELETE CASCADE ON UPDATE CASCADE,  -- To where transfer is
    deposit              TEXT        NOT NULL,                        -- Amount received
    fee_account          INTEGER     REFERENCES accounts (id) ON DELETE CASCADE ON UPDATE CASCADE,           -- If and where fee was withdrawn
    fee                  TEXT,                                        -- Fee amount
    number               TEXT        NOT NULL DEFAULT (''),           -- Number of operation in bank/broker systems
    symbol_id            INTEGER     REFERENCES asset_symbol (id) ON DELETE CASCADE ON UPDATE CASCADE,       -- If it is an asset transfer
    fee_symbol_id        INTEGER     REFERENCES asset_symbol (id) ON DELETE CASCADE ON UPDATE CASCADE,       -- Asset the fee is paid in (crypto only); NULL = fee account currency
    note                 TEXT                                         -- Free text comment
);
INSERT INTO transfers_new (oid, otype, withdrawal_timestamp, withdrawal_account, withdrawal,
                           deposit_timestamp, deposit_account, deposit, fee_account, fee, number,
                           symbol_id, fee_symbol_id, note)
    SELECT oid, otype, withdrawal_timestamp, withdrawal_account, withdrawal,
           deposit_timestamp, deposit_account, deposit, fee_account, fee, number,
           symbol_id, NULL, note FROM transfers;   -- No transfer paid its fee in an asset before this version
DROP TABLE transfers;
ALTER TABLE transfers_new RENAME TO transfers;

-- Recreate everything that was dropped above. The update trigger lists the columns it watches explicitly, so
-- 'fee_symbol_id' has to be named there or changing the fee asset would leave a stale ledger behind.
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
    SELECT otype, 5 AS seq, oid, -1 AS opart, withdrawal_timestamp AS timestamp, withdrawal_account AS account_id FROM transfers
    UNION ALL
    SELECT otype, 5 AS seq, oid, 0 AS opart, withdrawal_timestamp AS timestamp, fee_account AS account_id FROM transfers WHERE NOT fee IS NULL
    UNION ALL
    SELECT otype, 5 AS seq, oid, 1 AS opart, deposit_timestamp AS timestamp, deposit_account AS account_id FROM transfers
    UNION ALL
    SELECT td.otype, 6 AS seq, td.oid, da.id AS opart, da.timestamp, td.account_id FROM deposit_actions AS da LEFT JOIN term_deposits AS td ON da.deposit_id=td.oid
) AS m
ORDER BY m.timestamp, m.seq, m.opart, m.oid;  -- First sort by sequence and part to enforce right operation processing order

CREATE TRIGGER transfers_after_delete AFTER DELETE ON transfers FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.withdrawal_timestamp OR timestamp >= OLD.deposit_timestamp;
END;
CREATE TRIGGER transfers_after_insert AFTER INSERT ON transfers FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= NEW.withdrawal_timestamp OR timestamp >= NEW.deposit_timestamp;
END;
CREATE TRIGGER transfers_after_update AFTER UPDATE OF withdrawal_timestamp, deposit_timestamp, withdrawal_account, deposit_account, fee_account, withdrawal, deposit, fee, fee_symbol_id, symbol_id ON transfers FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.withdrawal_timestamp OR timestamp >= OLD.deposit_timestamp OR
                timestamp >= NEW.withdrawal_timestamp OR timestamp >= NEW.deposit_timestamp;
END;
--------------------------------------------------------------------------------
INSERT INTO settings(name, value) VALUES('DlgGeometry_Token blacklist', '');
INSERT INTO settings(name, value) VALUES('DlgViewState_Token blacklist', '');
--------------------------------------------------------------------------------
-- New operation: swaps (an on-chain exchange of one asset for another; realizes profit/loss on the disposed asset
-- and opens the acquired asset as a new lot at market value - NOT a cost-basis-preserving SymbolChange/Merger).
-- 'in_account_id'/'in_timestamp'/'in_tx_hash' describe a CROSS-CHAIN swap, where the acquired asset arrives on
-- another account (chain) and in another transaction; they stay NULL for an ordinary same-chain swap.
CREATE TABLE swaps (
    oid           INTEGER     PRIMARY KEY UNIQUE NOT NULL,     -- Unique operation id
    otype         INTEGER     NOT NULL DEFAULT (7),            -- Operation type (7 = swap)
    timestamp     INTEGER     NOT NULL,                        -- When the disposed asset left (the swap itself, same-chain)
    account_id    INTEGER     NOT NULL REFERENCES accounts (id) ON DELETE CASCADE ON UPDATE CASCADE,  -- Source account
    tx_hash       TEXT        NOT NULL DEFAULT (''),           -- Hash of the blockchain transaction
    out_symbol_id INTEGER     NOT NULL REFERENCES asset_symbol (id) ON DELETE CASCADE ON UPDATE CASCADE,  -- Disposed asset
    out_qty       TEXT        NOT NULL,
    in_timestamp  INTEGER,                                     -- When the acquired asset arrived (NULL = same as 'timestamp')
    in_account_id INTEGER     REFERENCES accounts (id) ON DELETE CASCADE ON UPDATE CASCADE,   -- Destination account (NULL = same as 'account_id')
    in_symbol_id  INTEGER     NOT NULL REFERENCES asset_symbol (id) ON DELETE CASCADE ON UPDATE CASCADE,  -- Acquired asset
    in_qty        TEXT        NOT NULL,
    in_tx_hash    TEXT        NOT NULL DEFAULT (''),           -- Hash of the receiving transaction (destination chain)
    fee_symbol_id INTEGER     REFERENCES asset_symbol (id) ON DELETE CASCADE ON UPDATE CASCADE,           -- Fee (gas) asset, if any
    fee_qty       TEXT,
    note          TEXT                                         -- Free text comment
);

-- Ledger and trades cleanup after modification (mirrors the trades_* triggers)
DROP TRIGGER IF EXISTS swaps_after_delete;
CREATE TRIGGER swaps_after_delete AFTER DELETE ON swaps FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp;
END;
DROP TRIGGER IF EXISTS swaps_after_insert;
CREATE TRIGGER swaps_after_insert AFTER INSERT ON swaps FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= NEW.timestamp;
END;
DROP TRIGGER IF EXISTS swaps_after_update;
CREATE TRIGGER swaps_after_update AFTER UPDATE OF timestamp, account_id, out_symbol_id, out_qty, in_timestamp, in_account_id, in_symbol_id, in_qty, fee_symbol_id, fee_qty ON swaps FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
END;

-- Table: bridges - a cross-chain move of ONE asset between two accounts, imported as two independent on-chain legs
-- (a send and a receive) that arrive in separate runs. Only the sending leg is recognizable as part of a bridge, so
-- it is always present while the receiving one is nullable: a row with in_* NULL is a "pending half-bridge" waiting
-- for its arrival to be adopted from a plain transfer (see jal_init.sql and jal/db/bridge_matcher.py).
DROP TABLE IF EXISTS bridges;
CREATE TABLE bridges (
    oid            INTEGER    PRIMARY KEY UNIQUE NOT NULL,
    otype          INTEGER    NOT NULL DEFAULT (8),
    out_timestamp  INTEGER    NOT NULL,
    out_account_id INTEGER    NOT NULL REFERENCES accounts (id) ON DELETE CASCADE ON UPDATE CASCADE,
    out_symbol_id  INTEGER    NOT NULL REFERENCES asset_symbol (id) ON DELETE CASCADE ON UPDATE CASCADE,
    out_qty        TEXT       NOT NULL,
    out_tx_hash    TEXT       NOT NULL DEFAULT (''),
    in_timestamp   INTEGER,
    in_account_id  INTEGER    REFERENCES accounts (id) ON DELETE CASCADE ON UPDATE CASCADE,
    in_symbol_id   INTEGER    REFERENCES asset_symbol (id) ON DELETE CASCADE ON UPDATE CASCADE,
    in_qty         TEXT,
    in_tx_hash     TEXT       NOT NULL DEFAULT (''),
    fee_symbol_id  INTEGER    REFERENCES asset_symbol (id) ON DELETE CASCADE ON UPDATE CASCADE,
    fee_qty        TEXT,
    note           TEXT
);
DROP TRIGGER IF EXISTS bridges_after_delete;
CREATE TRIGGER bridges_after_delete AFTER DELETE ON bridges FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.out_timestamp OR timestamp >= OLD.in_timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.out_timestamp OR timestamp >= OLD.in_timestamp;
END;
DROP TRIGGER IF EXISTS bridges_after_insert;
CREATE TRIGGER bridges_after_insert AFTER INSERT ON bridges FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= NEW.out_timestamp OR timestamp >= NEW.in_timestamp;
    DELETE FROM trades_opened WHERE timestamp >= NEW.out_timestamp OR timestamp >= NEW.in_timestamp;
END;
DROP TRIGGER IF EXISTS bridges_after_update;
CREATE TRIGGER bridges_after_update AFTER UPDATE OF out_timestamp, in_timestamp, out_account_id, in_account_id, out_symbol_id, in_symbol_id, out_qty, in_qty, fee_symbol_id, fee_qty ON bridges FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.out_timestamp OR timestamp >= OLD.in_timestamp OR timestamp >= NEW.out_timestamp OR timestamp >= NEW.in_timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.out_timestamp OR timestamp >= OLD.in_timestamp OR timestamp >= NEW.out_timestamp OR timestamp >= NEW.in_timestamp;
END;

-- The display/processing sequence view has to learn about the new operations: a same-chain swap stays a single part,
-- a cross-chain one splits into a send (-1) and a receive (+1) part processed on their own accounts and dates;
-- bridge legs are guarded as either of them may still be missing.
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
    SELECT otype, 5 AS seq, oid, -1 AS opart, withdrawal_timestamp AS timestamp, withdrawal_account AS account_id FROM transfers
    UNION ALL
    SELECT otype, 5 AS seq, oid, 0 AS opart, withdrawal_timestamp AS timestamp, fee_account AS account_id FROM transfers WHERE NOT fee IS NULL
    UNION ALL
    SELECT otype, 5 AS seq, oid, 1 AS opart, deposit_timestamp AS timestamp, deposit_account AS account_id FROM transfers
    UNION ALL
    SELECT td.otype, 6 AS seq, td.oid, da.id AS opart, da.timestamp, td.account_id FROM deposit_actions AS da LEFT JOIN term_deposits AS td ON da.deposit_id=td.oid
    UNION ALL
    SELECT otype, 7 AS seq, oid, 0 AS opart, timestamp, account_id FROM swaps WHERE in_account_id IS NULL OR in_account_id=account_id
    UNION ALL
    SELECT otype, 7 AS seq, oid, -1 AS opart, timestamp, account_id FROM swaps WHERE NOT in_account_id IS NULL AND in_account_id<>account_id
    UNION ALL
    SELECT otype, 7 AS seq, oid, 1 AS opart, COALESCE(in_timestamp, timestamp) AS timestamp, in_account_id AS account_id FROM swaps WHERE NOT in_account_id IS NULL AND in_account_id<>account_id
    UNION ALL
    SELECT otype, 8 AS seq, oid, -1 AS opart, out_timestamp AS timestamp, out_account_id AS account_id FROM bridges
    UNION ALL
    SELECT otype, 8 AS seq, oid, 0 AS opart, out_timestamp AS timestamp, out_account_id AS account_id FROM bridges WHERE NOT fee_qty IS NULL
    UNION ALL
    SELECT otype, 8 AS seq, oid, 1 AS opart, in_timestamp AS timestamp, in_account_id AS account_id FROM bridges WHERE NOT in_account_id IS NULL
) AS m
ORDER BY m.timestamp, m.seq, m.opart, m.oid;  -- First sort by sequence and part to enforce right operation processing order
--------------------------------------------------------------------------------
-- Add the listing location to the symbol-uniqueness key. A token that lives on several blockchains (e.g. USDT on
-- Ethereum and on Tron) is one asset with a per-chain listing keyed by its own contract address; the old key
-- (asset_id, symbol, currency_id) refused a second chain's listing because ticker and currency are the same.
DROP INDEX IF EXISTS uniq_symbols;
CREATE UNIQUE INDEX uniq_symbols ON asset_symbol (asset_id, symbol COLLATE NOCASE, currency_id, location_id);
--------------------------------------------------------------------------------
-- Give every open trade a stable per-slice identity so open_trades_list() can tell one lot's successive states
-- apart from two independent slices of the same operation. Without it, carrying the same original lot twice into
-- one (account, asset) bucket (e.g. two partial transfers of one buy) makes the second row shadow the first under
-- the shared (otype, oid) key and silently drops a slice's quantity from the FIFO list, understating realized P&L.
-- The column is filled by the trigger below on rebuild; existing rows stay NULL and are discarded by the rebuild.
ALTER TABLE trades_opened ADD COLUMN slice_id INTEGER;
DROP TRIGGER IF EXISTS trades_opened_set_slice;
CREATE TRIGGER trades_opened_set_slice AFTER INSERT ON trades_opened
    WHEN NEW.slice_id IS NULL
BEGIN
    UPDATE trades_opened SET slice_id = NEW.id WHERE id = NEW.id;
END;
-- The whole ledger cache (including trades_opened) must be rebuilt so slice ids are assigned to every open trade.
INSERT OR REPLACE INTO settings(name, value) VALUES ('RebuildDB', 1);
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=61 WHERE name='SchemaVersion';
COMMIT;
