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
-- TERM DEPOSITS BECOME ACCOUNTS ("a box is an account", CRYPTO_PATH decisions #49-#51).
--
-- The 'TermDeposit' operation is retired: a deposit is a container that holds a balance over time, has an owner and
-- takes money in and out in any order - i.e. an account with extra steps. Every term deposit becomes an 'accounts'
-- row of the new hidden type 7 (PredefinedAccountType.Deposit), and its actions become ordinary operations:
--   Opening / TopUp                -> a Transfer from the funding account into the box
--   PartialWithdrawal / Closing    -> a Transfer from the box back to the funding account
--   InterestAccrued                -> an IncomeSpending on the box (category Interest, peer = the bank), merged with
--                                     a same-timestamp TaxWithheld as a second, negative line (category Taxes)
--   TaxWithheld without an interest twin -> a single-line spending of its own
--   Renewal                        -> none can exist: the operation asserts in the ledger, so no database that was
--                                     ever built can hold one. Not migrated.
-- 'BookAccount.Savings' is retired with the operation - the money now sits in the ordinary Money book of the box.
--
-- Amount arithmetic below is done on integers scaled by 10^6: SQLite has no decimal type and summing money as REAL
-- would drift. Money amounts carry at most 6 decimals and stay far below 2^53/10^6, so the scaling is exact.

DROP TABLE IF EXISTS _deposit_migration;
CREATE TABLE _deposit_migration AS
WITH base AS (
    SELECT td.oid AS deposit_id, td.account_id AS funding_id, a.currency_id AS currency_id,
           a.organization_id AS peer_id,
           COALESCE(NULLIF(TRIM(td.note), ''), 'Term deposit') AS base_name
    FROM term_deposits AS td LEFT JOIN accounts AS a ON a.id = td.account_id
)
SELECT b.deposit_id, b.funding_id, b.currency_id, b.peer_id,
       -- Box ids are assigned here rather than by the INSERT below, because every action of the deposit has to
       -- reference the account it belongs to and SQLite offers no way to read back a set of generated ids.
       (SELECT COALESCE(MAX(id), 0) FROM accounts) + ROW_NUMBER() OVER (ORDER BY b.deposit_id) AS box_id,
       -- The deposit's note becomes the account name, which must be unique: a note shared by two deposits (or by an
       -- account that already exists) gets the deposit id appended to keep both distinguishable.
       CASE WHEN (SELECT COUNT(*) FROM base AS b2 WHERE b2.base_name = b.base_name) > 1
                 OR b.base_name IN (SELECT name FROM accounts)
            THEN b.base_name || ' #' || b.deposit_id
            ELSE b.base_name END AS name,
       (SELECT MAX(da.timestamp) FROM deposit_actions AS da
        WHERE da.deposit_id = b.deposit_id AND da.action_type = 100) AS closing_ts   -- DepositActions.Closing
FROM base AS b;

-- Balance the closing action moves back to the funding account. The old ledger did NOT use the amount stored on the
-- Closing action (which is unreliable - in the author's data 10 of 306 disagree with the deposit's actual balance);
-- it moved whatever had accumulated in the Savings book, so that is what is reproduced here.
DROP TABLE IF EXISTS _deposit_closing;
CREATE TABLE _deposit_closing AS
SELECT m.deposit_id, m.closing_ts,
       (SELECT COALESCE(SUM(CASE WHEN da.action_type IN (1, 2, 50)    -- Opening, TopUp, InterestAccrued
                                 THEN CAST(ROUND(CAST(da.amount AS REAL) * 1000000) AS INTEGER)
                                 WHEN da.action_type IN (51, 99)      -- TaxWithheld, PartialWithdrawal
                                 THEN -CAST(ROUND(CAST(da.amount AS REAL) * 1000000) AS INTEGER)
                                 ELSE 0 END), 0)
        FROM deposit_actions AS da
        WHERE da.deposit_id = m.deposit_id AND da.timestamp <= m.closing_ts) AS scaled
FROM _deposit_migration AS m WHERE m.closing_ts IS NOT NULL;

-- One account per deposit. A box whose closing already happened is deactivated, so only deposits that are still
-- running can ever show up in a default view; it is not investing (it holds money only) and inherits currency and
-- bank from the account it was funded from. The closing date is compared with today rather than merely being
-- present, because the old format demanded exactly one closing action even for a running deposit - so such a
-- deposit was recorded with a closing far in the future, and it has to stay open just as it was before.
INSERT INTO accounts (id, name, currency_id, active, investing, reconciled_on, organization_id, account_type)
    SELECT m.box_id, m.name, m.currency_id,
           CASE WHEN m.closing_ts IS NULL OR m.closing_ts > CAST(strftime('%s', 'now') AS INTEGER)
                THEN 1 ELSE 0 END, 0, 0, m.peer_id, 7
    FROM _deposit_migration AS m;

-- The date the deposit ended is the only term attribute the old format kept (implicitly, as the closing action);
-- the interest rate was never recorded, so migrated boxes simply have none.
INSERT INTO account_data (account_id, datatype, value)
    SELECT m.box_id, 8, CAST(m.closing_ts AS TEXT)      -- AccountData.DepositEnd
    FROM _deposit_migration AS m WHERE m.closing_ts IS NOT NULL;

-- Money put into the box: Opening and TopUp
INSERT INTO transfers (otype, withdrawal_timestamp, withdrawal_account, withdrawal,
                       deposit_timestamp, deposit_account, deposit, number, note)
    SELECT 4, da.timestamp, m.funding_id, da.amount, da.timestamp, m.box_id, da.amount, '', NULL
    FROM deposit_actions AS da JOIN _deposit_migration AS m ON m.deposit_id = da.deposit_id
    WHERE da.action_type IN (1, 2);

-- Money taken out of the box: PartialWithdrawal by its own amount, Closing by the accumulated balance
INSERT INTO transfers (otype, withdrawal_timestamp, withdrawal_account, withdrawal,
                       deposit_timestamp, deposit_account, deposit, number, note)
    SELECT 4, da.timestamp, m.box_id, da.amount, da.timestamp, m.funding_id, da.amount, '', NULL
    FROM deposit_actions AS da JOIN _deposit_migration AS m ON m.deposit_id = da.deposit_id
    WHERE da.action_type = 99;
-- The closing balance is what leaves the box (RTRIM strips the padding printf() adds; the decimal point stops it,
-- so '100.000000' becomes '100' and not '1'). A deposit that somehow ends up overdrawn - more taken out of it than
-- ever went in, which no sane data has but the old format never forbade - is closed by putting the shortfall back
-- IN, so that the transfer amount is always positive whichever way the money has to go.
INSERT INTO transfers (otype, withdrawal_timestamp, withdrawal_account, withdrawal,
                       deposit_timestamp, deposit_account, deposit, number, note)
    SELECT 4, c.closing_ts, m.box_id, RTRIM(RTRIM(printf('%.6f', c.scaled / 1000000.0), '0'), '.'),
              c.closing_ts, m.funding_id, RTRIM(RTRIM(printf('%.6f', c.scaled / 1000000.0), '0'), '.'), '', NULL
    FROM _deposit_closing AS c JOIN _deposit_migration AS m ON m.deposit_id = c.deposit_id
    WHERE c.scaled > 0;
INSERT INTO transfers (otype, withdrawal_timestamp, withdrawal_account, withdrawal,
                       deposit_timestamp, deposit_account, deposit, number, note)
    SELECT 4, c.closing_ts, m.funding_id, RTRIM(RTRIM(printf('%.6f', -c.scaled / 1000000.0), '0'), '.'),
              c.closing_ts, m.box_id, RTRIM(RTRIM(printf('%.6f', -c.scaled / 1000000.0), '0'), '.'), '', NULL
    FROM _deposit_closing AS c JOIN _deposit_migration AS m ON m.deposit_id = c.deposit_id
    WHERE c.scaled < 0;

-- Interest (and the tax withheld from it) becomes an income/spending operation on the box. One operation per
-- (deposit, timestamp) that saw either of them: 'deposit_actions' is unique on (deposit, timestamp, action_type),
-- so an interest payment and its tax can only ever pair up one to one.
DROP TABLE IF EXISTS _deposit_income;
CREATE TABLE _deposit_income AS
SELECT m.box_id, m.peer_id, da.timestamp,
       (SELECT COALESCE(MAX(oid), 0) FROM actions) + ROW_NUMBER() OVER (ORDER BY m.box_id, da.timestamp) AS action_id,
       (SELECT i.amount FROM deposit_actions AS i
        WHERE i.deposit_id = da.deposit_id AND i.timestamp = da.timestamp AND i.action_type = 50) AS interest,
       (SELECT t.amount FROM deposit_actions AS t
        WHERE t.deposit_id = da.deposit_id AND t.timestamp = da.timestamp AND t.action_type = 51) AS tax
FROM (SELECT DISTINCT deposit_id, timestamp FROM deposit_actions WHERE action_type IN (50, 51)) AS da
JOIN _deposit_migration AS m ON m.deposit_id = da.deposit_id;

INSERT INTO actions (oid, otype, timestamp, account_id, peer_id, alt_currency_id)
    SELECT action_id, 1, timestamp, box_id, peer_id, NULL FROM _deposit_income;
-- Interest is a positive line (category Interest) and the tax a negative one (category Taxes) of the same
-- operation: IncomeSpending books every detail line by its own sign, so one two-line operation is correct.
INSERT INTO action_details (pid, category_id, tag_id, amount, amount_alt, note)
    SELECT action_id, 8, NULL, interest, '0', NULL FROM _deposit_income WHERE interest IS NOT NULL;
-- The tax was stored as a positive amount to be subtracted, so it is negated here. The sign is flipped on the
-- string rather than through arithmetic (SQLite has no decimal type), and an already-negative value - which would be
-- a data anomaly - is handled rather than turned into '--5'.
INSERT INTO action_details (pid, category_id, tag_id, amount, amount_alt, note)
    SELECT action_id, 6, NULL,
           CASE WHEN SUBSTR(TRIM(tax), 1, 1) = '-' THEN SUBSTR(TRIM(tax), 2) ELSE '-' || TRIM(tax) END,
           '0', NULL
    FROM _deposit_income WHERE tax IS NOT NULL;

DROP TABLE _deposit_income;
DROP TABLE _deposit_closing;
DROP TABLE _deposit_migration;

-- The operation and everything that served it are gone
DROP TRIGGER IF EXISTS deposit_action_after_delete;
DROP TRIGGER IF EXISTS deposit_action_after_insert;
DROP TRIGGER IF EXISTS deposit_action_after_update;
DROP TABLE IF EXISTS deposit_actions;
DROP TABLE IF EXISTS term_deposits;

--------------------------------------------------------------------------------
-- New operation: conversions - a same-account exchange of one asset into another that PRESERVES COST BASIS and
-- recognizes no income (CRYPTO_PATH decisions #52-#54). It covers wrapping (ETH -> WETH), supplying to and
-- withdrawing from a lending protocol (USDG -> aEthUSDG) and liquid staking - all cases where the wallet keeps the
-- same economic position, only in the shape of a receipt token. Unlike a Swap nothing is disposed of at market
-- value: the quantity may change (a rebasing receipt token folds accrued yield into it) while the basis does not,
-- so the yield rides along as an unrealized gain and realizes only when the underlying is finally sold.
-- It takes the operation type freed by retiring TermDeposit above.
CREATE TABLE conversions (
    oid           INTEGER     PRIMARY KEY UNIQUE NOT NULL,     -- Unique operation id
    otype         INTEGER     NOT NULL DEFAULT (6),            -- Operation type (6 = conversion)
    timestamp     INTEGER     NOT NULL,
    account_id    INTEGER     NOT NULL REFERENCES accounts (id) ON DELETE CASCADE ON UPDATE CASCADE,
    tx_hash       TEXT        NOT NULL DEFAULT (''),           -- Hash of the blockchain transaction
    out_symbol_id INTEGER     NOT NULL REFERENCES asset_symbol (id) ON DELETE CASCADE ON UPDATE CASCADE,  -- Converted asset
    out_qty       TEXT        NOT NULL,
    in_symbol_id  INTEGER     NOT NULL REFERENCES asset_symbol (id) ON DELETE CASCADE ON UPDATE CASCADE,  -- Asset received instead
    in_qty        TEXT        NOT NULL,
    fee_symbol_id INTEGER     REFERENCES asset_symbol (id) ON DELETE CASCADE ON UPDATE CASCADE,           -- Fee (gas) asset, if any
    fee_qty       TEXT,
    note          TEXT
);
-- Ledger and trades cleanup after modification (mirrors the swaps_* triggers)
DROP TRIGGER IF EXISTS conversions_after_delete;
CREATE TRIGGER conversions_after_delete AFTER DELETE ON conversions FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp;
END;
DROP TRIGGER IF EXISTS conversions_after_insert;
CREATE TRIGGER conversions_after_insert AFTER INSERT ON conversions FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= NEW.timestamp;
END;
DROP TRIGGER IF EXISTS conversions_after_update;
CREATE TRIGGER conversions_after_update AFTER UPDATE OF timestamp, account_id, out_symbol_id, out_qty, in_symbol_id, in_qty, fee_symbol_id, fee_qty ON conversions FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
END;
--------------------------------------------------------------------------------
-- 'operation_sequence' loses the term-deposit branch and gains the conversion one. Operation type 6 changes meaning
-- here, which is exactly why the ledger cache has to be dropped: a leftover otype=6 row would be read as a
-- Conversion. RebuildDB (set above) makes the application offer to re-build it on the next start.
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
    SELECT otype, 6 AS seq, oid, 0 AS opart, timestamp, account_id FROM conversions
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

-- Every cached ledger row is discarded, not only the deposit ones: operation type 6 changes meaning with this
-- update, so a row that survived would be read as a Conversion. The cache is rebuilt from the operations themselves.
DELETE FROM ledger;
DELETE FROM ledger_totals;
DELETE FROM trades_closed;
DELETE FROM trades_opened;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=61 WHERE name='SchemaVersion';
COMMIT;
