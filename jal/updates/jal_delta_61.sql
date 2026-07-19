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
-- Set new DB schema version
UPDATE settings SET value=61 WHERE name='SchemaVersion';
COMMIT;
