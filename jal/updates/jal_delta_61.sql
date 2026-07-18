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
INSERT INTO settings(name, value) VALUES('DlgGeometry_Token blacklist', '');
INSERT INTO settings(name, value) VALUES('DlgViewState_Token blacklist', '');
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=61 WHERE name='SchemaVersion';
COMMIT;
