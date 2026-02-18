BEGIN TRANSACTION;
--------------------------------------------------------------------------------
DROP VIEW IF EXISTS currencies;  -- Remove views to prevent dependency errors
DROP VIEW IF EXISTS assets_ext;  -- Remove view as it isn't used anymore
--------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS asset_id (
    id        INTEGER PRIMARY KEY UNIQUE NOT NULL,
    symbol_id INTEGER REFERENCES asset_tickers (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    id_type   INTEGER NOT NULL,
    id_value  TEXT NOT NULL
);
-- Migrate existing ISINs to new asset_id table
INSERT INTO asset_id (symbol_id, id_type, id_value)
  SELECT t.id, 2, isin
  FROM assets a
  LEFT JOIN asset_tickers t ON a.id = t.asset_id
  WHERE NOT (isin='' OR isin LIKE ' %');
-- Remove ISINs that were stored as registration code in asset_data table
DELETE FROM asset_data WHERE id IN (SELECT d.id FROM asset_data d JOIN assets a ON d.asset_id=a.id AND d.value=a.isin);
-- Migrate existing MOEX registration codes from asset_data to new asset_id table
INSERT INTO asset_id (symbol_id, id_type, id_value)
  SELECT t.id, 5, value
  FROM asset_data d
  LEFT JOIN asset_tickers t ON d.asset_id = t.asset_id
  WHERE datatype=1 AND value LIKE '1-__-%' AND NOT t.id IS NULL;
DELETE FROM asset_data WHERE datatype=1 AND value LIKE '1-__-%';
-- Migrate what looks like CUSIPs
INSERT INTO asset_id (symbol_id, id_type, id_value)
  SELECT t.id, 4, value
  FROM asset_data d
  LEFT JOIN asset_tickers t ON d.asset_id = t.asset_id
  WHERE datatype=1 AND value REGEXP '^.{5}[A-Z].{3}$' AND NOT t.id IS NULL;
DELETE FROM asset_data WHERE datatype=1 AND value REGEXP '^.{5}[A-Z].{3}$';
-- Clean up any remaining registration data from asset_data table (There was a bit of mess)
DELETE FROM asset_data WHERE datatype=1;
--------------------------------------------------------------------------------
-- Create quote source table
CREATE TABLE IF NOT EXISTS quote_source (
    asset_id    INTEGER REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    currency_id INTEGER REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    datafeed_id INTEGER NOT NULL
);
CREATE UNIQUE INDEX datafeed_pk ON quote_source (asset_id ASC, currency_id ASC);
-- Copy data from symbols table
INSERT INTO quote_source (asset_id, currency_id, datafeed_id)
  SELECT asset_id, currency_id, quote_source
  FROM asset_tickers
  WHERE quote_source>0 AND active=1;
-- Insert data for currencies (it had NULL in currency_id previously)
INSERT INTO quote_source (asset_id, currency_id, datafeed_id)
  SELECT asset_id, asset_id, quote_source
  FROM asset_tickers
  WHERE quote_source=0;
--------------------------------------------------------------------------------
-- Remove ISIN column from assets table
ALTER TABLE assets DROP COLUMN isin;
--------------------------------------------------------------------------------
-- Alter asset symbols table
-- Remove custom error triggers
DROP TRIGGER IF EXISTS validate_ticker_currency_insert;
DROP TRIGGER IF EXISTS  validate_ticker_currency_update;
-- Remove NULL values from currency_id
UPDATE asset_tickers SET currency_id=asset_id WHERE currency_id IS NULL;
-- Fix absent symbols for non-default currency
INSERT INTO asset_tickers (asset_id, symbol, currency_id)
  SELECT DISTINCT p.asset_id, s2.symbol, a.currency_id
  FROM asset_payments p
  LEFT JOIN accounts a ON p.account_id=a.id
  LEFT JOIN asset_tickers s1 ON p.asset_id=s1.asset_id AND a.currency_id=s1.currency_id AND s1.active=1
  LEFT JOIN asset_tickers s2 ON p.asset_id=s2.asset_id AND s2.currency_id=1 AND s2.active=1
  WHERE s1.symbol IS NULL;
-- Create new symbols table
CREATE TABLE asset_symbol (
    id          INTEGER PRIMARY KEY UNIQUE NOT NULL,
    asset_id    INTEGER REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    symbol      TEXT NOT NULL,
    currency_id INTEGER REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    location_id INTEGER NOT NULL DEFAULT (0),
    active      INTEGER NOT NULL DEFAULT (1),
    icon        BLOB
);
INSERT INTO asset_symbol (id, asset_id, symbol, currency_id, active) SELECT id, asset_id, symbol, currency_id, active FROM asset_tickers;
PRAGMA foreign_keys = OFF;  -- Prevent deletion of linked asset_ids
DROP TABLE asset_tickers;
-- Re-create asset_id table to recover foreign keys (otherwise it will be linked to an old non-existing table asset_tickers
CREATE TABLE IF NOT EXISTS asset_id_new (
    id        INTEGER PRIMARY KEY UNIQUE NOT NULL,
    symbol_id INTEGER REFERENCES asset_symbol (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    id_type   INTEGER NOT NULL,
    id_value  TEXT NOT NULL
);
INSERT INTO asset_id_new (id, symbol_id, id_type, id_value)
  SELECT id, symbol_id, id_type, id_value FROM asset_id;
DROP TABLE asset_id;
ALTER TABLE asset_id_new RENAME TO asset_id;
PRAGMA foreign_keys = ON;  -- Prevent deletion of linked asset_ids
CREATE UNIQUE INDEX uniq_symbols ON asset_symbol (asset_id, symbol COLLATE NOCASE, currency_id);
--------------------------------------------------------------------------------
-- Update currencies view
CREATE VIEW currencies AS
SELECT a.id, s.symbol
    FROM assets AS a
    LEFT JOIN asset_symbol AS s ON s.asset_id = a.id AND s.active = 1
    WHERE a.type_id = 1;
--------------------------------------------------------------------------------
-- Link asset payments to asset symbol
CREATE TABLE old_asset_payments AS SELECT * FROM asset_payments;
DROP TABLE asset_payments;
CREATE TABLE asset_payments (
    oid        INTEGER PRIMARY KEY UNIQUE NOT NULL,
    otype      INTEGER NOT NULL DEFAULT (2),
    timestamp  INTEGER NOT NULL,
    ex_date    INTEGER NOT NULL DEFAULT (0),
    number     TEXT    NOT NULL DEFAULT (''),
    type       INTEGER NOT NULL,
    account_id INTEGER REFERENCES accounts (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    symbol_id  INTEGER REFERENCES asset_symbol (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    amount     TEXT    NOT NULL DEFAULT ('0'),
    tax        TEXT    NOT NULL DEFAULT ('0'),
    note       TEXT
);
INSERT INTO asset_payments (oid, otype, timestamp, ex_date, number, type, account_id, symbol_id, amount, tax, note)
  SELECT p.oid, p.otype, p.timestamp, p.ex_date, p.number, p.type, p.account_id, s.id AS symbol_id, p.amount, p.tax, p.note
  FROM old_asset_payments p
  LEFT JOIN accounts a ON p.account_id=a.id
  LEFT JOIN asset_symbol s ON p.asset_id=s.asset_id AND a.currency_id=s.currency_id AND s.active=1;
DROP TABLE old_asset_payments;
-- re-create triggers
CREATE TRIGGER asset_payments_after_delete AFTER DELETE ON asset_payments FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp;
END;
CREATE TRIGGER asset_payments_after_insert AFTER INSERT ON asset_payments FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= NEW.timestamp;
END;
CREATE TRIGGER asset_payments_after_update AFTER UPDATE OF timestamp, type, account_id, symbol_id, amount, tax ON asset_payments FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
END;
--------------------------------------------------------------------------------
-- Link trades to asset symbol
CREATE TABLE old_trades AS SELECT * FROM trades;
DROP TABLE trades;
CREATE TABLE trades (
    oid        INTEGER  PRIMARY KEY UNIQUE NOT NULL,  -- Unique operation id
    otype      INTEGER  NOT NULL DEFAULT (3),         -- Operation type (3 = trade)
    timestamp  INTEGER  NOT NULL,                     -- Timestamp when trade happened
    settlement INTEGER  NOT NULL DEFAULT (0),         -- Timestamp of settlement if known (otherwise 0)
    number     TEXT     NOT NULL DEFAULT (''),        -- Number of trade in broker/exchange systems
    account_id INTEGER  REFERENCES accounts (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,      -- where trade is accounted
    symbol_id  INTEGER  REFERENCES asset_symbol (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,  -- which asset was bought/sold
    qty        TEXT     NOT NULL DEFAULT ('0'),       -- Quantity of asset (>0 - Buy, <0 - Sell)
    price      TEXT     NOT NULL DEFAULT ('0'),       -- Price of the trade
    fee        TEXT     NOT NULL DEFAULT ('0'),       -- Total fee (broker, exchange, other) of the trade
    note       TEXT     NOT NULL DEFAULT ('')         -- Free text comment
);
INSERT INTO trades (oid, otype, timestamp, settlement, number, account_id, symbol_id, qty, price, fee, note)
  SELECT t.oid, t.otype, t.timestamp, t.settlement, t.number, t.account_id, s.id AS symbol_id, t.qty, t.price, t.fee, t.note
  FROM old_trades t
  LEFT JOIN accounts a ON t.account_id=a.id
  LEFT JOIN asset_symbol s ON t.asset_id=s.asset_id AND a.currency_id=s.currency_id AND s.active=1;
DROP TABLE old_trades;
-- re-create triggers
CREATE TRIGGER trades_after_delete AFTER DELETE ON trades FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp;
END;
CREATE TRIGGER trades_after_insert AFTER INSERT ON trades FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= NEW.timestamp;
END;
CREATE TRIGGER trades_after_update AFTER UPDATE OF timestamp, account_id, symbol_id, qty, price, fee ON trades FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
END;
--------------------------------------------------------------------------------
-- Link transfers to asset symbol
CREATE TABLE old_transfers AS SELECT * FROM transfers;
DROP TABLE transfers;
CREATE TABLE transfers (
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
    note                 TEXT                                         -- Free text comment
);
INSERT INTO transfers (oid, otype, withdrawal_timestamp, withdrawal_account, withdrawal, deposit_timestamp, deposit_account, deposit, fee_account, fee, number, symbol_id, note)
  SELECT t.oid, t.otype, t.withdrawal_timestamp, t.withdrawal_account, t.withdrawal, t.deposit_timestamp, t.deposit_account, t.deposit, t.fee_account, t.fee, t.number, s.id AS symbol_id, t.note
  FROM old_transfers t
  LEFT JOIN accounts a ON t.withdrawal_account=a.id
  LEFT JOIN asset_symbol s ON t.asset=s.asset_id AND a.currency_id=s.currency_id AND s.active=1;
DROP TABLE old_transfers;
-- re-create triggers
CREATE TRIGGER transfers_after_delete AFTER DELETE ON transfers FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.withdrawal_timestamp OR timestamp >= OLD.deposit_timestamp;
END;
CREATE TRIGGER transfers_after_insert AFTER INSERT ON transfers FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= NEW.withdrawal_timestamp OR timestamp >= NEW.deposit_timestamp;
END;
CREATE TRIGGER transfers_after_update AFTER UPDATE OF withdrawal_timestamp, deposit_timestamp, withdrawal_account, deposit_account, fee_account, withdrawal, deposit, fee, symbol_id ON transfers FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.withdrawal_timestamp OR timestamp >= OLD.deposit_timestamp OR
                timestamp >= NEW.withdrawal_timestamp OR timestamp >= NEW.deposit_timestamp;
END;
--------------------------------------------------------------------------------
-- Link corporate action results to asset symbol
CREATE TABLE old_action_results AS SELECT * FROM action_results;
DROP TABLE action_results;
CREATE TABLE asset_action_results (
    id          INTEGER PRIMARY KEY UNIQUE NOT NULL,             -- PK
    action_id   INTEGER NOT NULL REFERENCES asset_actions (oid) ON DELETE CASCADE ON UPDATE CASCADE,  -- Reference to corporate action operation
    symbol_id   INTEGER REFERENCES asset_symbol (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,    -- which asset appears after the action
    qty         TEXT    NOT NULL,                                -- Quantity of the asset the appears after the action
    value_share TEXT    NOT NULL                                 -- Which share of total 100% this asset takes in the action results
);
INSERT INTO asset_action_results (id, action_id, symbol_id, qty, value_share)
  SELECT r.id, r.action_id, s.id AS symbol_id, r.qty, r.value_share FROM old_action_results r
  LEFT JOIN asset_actions aa ON r.action_id=aa.oid
  LEFT JOIN accounts a ON aa.account_id=a.id
  LEFT JOIN asset_symbol s ON r.asset_id=s.asset_id AND a.currency_id=s.currency_id AND s.active=1;
DROP TABLE old_action_results;
-- re-create triggers
CREATE TRIGGER asset_result_after_delete AFTER DELETE ON asset_action_results FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= (SELECT timestamp FROM asset_actions WHERE oid = OLD.action_id);
END;
CREATE TRIGGER asset_result_after_insert AFTER INSERT ON asset_action_results FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= (SELECT timestamp FROM asset_actions WHERE oid = NEW.action_id);
END;
CREATE TRIGGER asset_result_after_update AFTER UPDATE OF symbol_id, qty, value_share ON asset_action_results FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= (SELECT timestamp FROM asset_actions WHERE oid = OLD.action_id);
END;
--------------------------------------------------------------------------------
-- Link corporate actions to asset symbol
PRAGMA foreign_keys = OFF;  -- Prevent child table 'asset_action_results' cleanup
CREATE TABLE old_asset_actions AS SELECT * FROM asset_actions;
DROP TABLE asset_actions;
CREATE TABLE asset_actions (
    oid        INTEGER     PRIMARY KEY UNIQUE NOT NULL,          -- Unique operation id
    otype      INTEGER     NOT NULL DEFAULT (5),                 -- Operation type (5 = corporate action)
    timestamp  INTEGER     NOT NULL,                             -- Timestamp when action happened
    number     TEXT        DEFAULT (''),                         -- Number of operation in broker/exchange systems
    account_id INTEGER     REFERENCES accounts (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,      -- where the operation is accounted
    type       INTEGER     NOT NULL,                             -- Type of corporate action (see CorporateAction class)
    symbol_id  INTEGER     REFERENCES asset_symbol (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,  -- which asset experienced the change
    qty        TEXT        NOT NULL,                             -- Quantity of the asset affected by the action
    note       TEXT                                              -- Free text comment
);
INSERT INTO asset_actions (oid, otype, timestamp, number, account_id, type, symbol_id, qty, note)
  SELECT o.oid, o.otype, o.timestamp, o.number, o.account_id, o.type, s.id AS symbol_id, o.qty, o.note FROM old_asset_actions o
  LEFT JOIN accounts a ON o.account_id=a.id
  LEFT JOIN asset_symbol s ON o.asset_id=s.asset_id AND a.currency_id=s.currency_id AND s.active=1;
DROP TABLE old_asset_actions;
PRAGMA foreign_keys = ON;
-- re-create triggers
CREATE TRIGGER asset_action_after_delete AFTER DELETE ON asset_actions FOR EACH ROW
BEGIN
    DELETE FROM asset_action_results WHERE action_id = OLD.oid;
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp;
END;
CREATE TRIGGER asset_action_after_insert AFTER INSERT ON asset_actions FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= NEW.timestamp;
END;
CREATE TRIGGER asset_action_after_update AFTER UPDATE OF timestamp, account_id, type, symbol_id, qty ON asset_actions FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp  OR timestamp >= NEW.timestamp;
END;
-------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=60 WHERE name='SchemaVersion';
--INSERT OR REPLACE INTO settings(name, value) VALUES ('RebuildDB', 1);
COMMIT;