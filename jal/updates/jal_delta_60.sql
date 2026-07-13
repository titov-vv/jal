BEGIN TRANSACTION;
--------------------------------------------------------------------------------
DROP VIEW IF EXISTS currencies;  -- Remove views to prevent dependency errors
DROP VIEW IF EXISTS assets_ext;  -- Remove view as it isn't used anymore
--------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS symbol_ids (
    id        INTEGER PRIMARY KEY UNIQUE NOT NULL,
    symbol_id INTEGER REFERENCES asset_tickers (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    id_type   INTEGER NOT NULL,
    id_value  TEXT NOT NULL
);
-- Migrate existing ISINs to new symbol_ids table
INSERT INTO symbol_ids (symbol_id, id_type, id_value)
  SELECT t.id, 2, isin
  FROM assets a
  LEFT JOIN asset_tickers t ON a.id = t.asset_id
  WHERE NOT (isin='' OR isin LIKE ' %') AND NOT t.id IS NULL;
-- Remove ISINs that were stored as registration code in asset_data table
DELETE FROM asset_data WHERE id IN (SELECT d.id FROM asset_data d JOIN assets a ON d.asset_id=a.id AND d.value=a.isin);
-- Migrate existing MOEX registration codes from asset_data to new symbol_ids table
INSERT INTO symbol_ids (symbol_id, id_type, id_value)
  SELECT t.id, 5, value
  FROM asset_data d
  LEFT JOIN asset_tickers t ON d.asset_id = t.asset_id
  WHERE datatype=1 AND value LIKE '1-__-%' AND NOT t.id IS NULL;
DELETE FROM asset_data WHERE datatype=1 AND value LIKE '1-__-%';
-- Migrate what looks like CUSIPs
INSERT INTO symbol_ids (symbol_id, id_type, id_value)
  SELECT t.id, 4, value
  FROM asset_data d
  LEFT JOIN asset_tickers t ON d.asset_id = t.asset_id
  WHERE datatype=1 AND value REGEXP '^.{5}[A-Z].{3}$' AND NOT t.id IS NULL;
DELETE FROM asset_data WHERE datatype=1 AND value REGEXP '^.{5}[A-Z].{3}$';
-- Clean up any remaining registration data from asset_data table (There was a bit of mess)
DELETE FROM asset_data WHERE datatype=1;
--------------------------------------------------------------------------------
-- Re-number AssetData.Tag from 4 to 1 (freed up by the registration code cleanup above)
UPDATE asset_data SET datatype=1 WHERE datatype=4;
DROP TRIGGER IF EXISTS tags_after_delete;
CREATE TRIGGER tags_after_delete AFTER DELETE ON tags FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= (SELECT MIN(timestamp) FROM ledger WHERE tag_id=OLD.id);
    DELETE FROM asset_data WHERE datatype=1 AND value=OLD.id;
END;
--------------------------------------------------------------------------------
-- Remove ISIN column from assets table
ALTER TABLE assets DROP COLUMN isin;
-- Remove base_asset column from assets table - never used by any logic, only added UI complexity
ALTER TABLE assets DROP COLUMN base_asset;
--------------------------------------------------------------------------------
-- Alter asset symbols table
-- Remove custom error triggers
DROP TRIGGER IF EXISTS validate_ticker_currency_insert;
DROP TRIGGER IF EXISTS  validate_ticker_currency_update;
-- Remove NULL values from currency_id
UPDATE asset_tickers SET currency_id=asset_id WHERE currency_id IS NULL;
-- Fabricate symbols that are absent for (asset, operation account currency) pairs,
-- so that every operation backfill below finds an active symbol to link to
CREATE TABLE symbol_gaps AS
  SELECT q.asset_id, q.currency_id FROM (
    SELECT t.asset_id AS asset_id, a.currency_id AS currency_id
      FROM trades t LEFT JOIN accounts a ON t.account_id=a.id
    UNION
    SELECT p.asset_id, a.currency_id
      FROM asset_payments p LEFT JOIN accounts a ON p.account_id=a.id
    UNION
    SELECT t.asset, a.currency_id
      FROM transfers t LEFT JOIN accounts a ON t.withdrawal_account=a.id
      WHERE NOT t.asset IS NULL
    UNION
    SELECT o.asset_id, a.currency_id
      FROM asset_actions o LEFT JOIN accounts a ON o.account_id=a.id
    UNION
    SELECT r.asset_id, a.currency_id
      FROM action_results r
      LEFT JOIN asset_actions aa ON r.action_id=aa.oid
      LEFT JOIN accounts a ON aa.account_id=a.id
  ) q
  WHERE NOT q.currency_id IS NULL
    AND NOT EXISTS (SELECT 1 FROM asset_tickers s
                    WHERE s.asset_id=q.asset_id AND s.currency_id=q.currency_id AND s.active=1);
-- Symbol text is taken from any active ticker of the asset, then any ticker, then asset name
INSERT OR IGNORE INTO asset_tickers (asset_id, symbol, currency_id)
  SELECT g.asset_id,
         COALESCE((SELECT s.symbol FROM asset_tickers s WHERE s.asset_id=g.asset_id AND s.active=1 ORDER BY s.id LIMIT 1),
                  (SELECT s.symbol FROM asset_tickers s WHERE s.asset_id=g.asset_id ORDER BY s.id LIMIT 1),
                  (SELECT a.full_name FROM assets a WHERE a.id=g.asset_id)),
         g.currency_id
  FROM symbol_gaps g;
-- Re-activate inactive symbols that were skipped by INSERT OR IGNORE due to uniq_symbols index
UPDATE asset_tickers SET active=1 WHERE id IN (
  SELECT MIN(s.id) FROM asset_tickers s
  JOIN symbol_gaps g ON s.asset_id=g.asset_id AND s.currency_id=g.currency_id
  WHERE NOT EXISTS (SELECT 1 FROM asset_tickers x
                    WHERE x.asset_id=g.asset_id AND x.currency_id=g.currency_id AND x.active=1)
  GROUP BY s.asset_id, s.currency_id
);
DROP TABLE symbol_gaps;
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
-- Translate old MarketDataFeed quote_source numbering into new AssetLocation location_id numbering
INSERT INTO asset_symbol (id, asset_id, symbol, currency_id, active, location_id)
  SELECT id, asset_id, symbol, currency_id, active,
    CASE quote_source
      WHEN 0 THEN 101   -- FX (Central banks) -> BANK_ACCOUNT
      WHEN 1 THEN 208   -- RU (MOEX) -> MOEX_EXCHANGE
      WHEN 2 THEN 201   -- US (NYSE/Nasdaq) -> NYSE_EXCHANGE (can't disambiguate Nasdaq from here)
      WHEN 3 THEN 209   -- EU (Euronext) -> EURONEXT_EXCHANGE
      WHEN 4 THEN 207   -- CA (TMX) -> TMX_EXCHANGE
      WHEN 5 THEN 203   -- GB (LSE) -> LSE_EXCHANGE
      WHEN 6 THEN 204   -- FRA (Frankfurt Borse) -> FRA_EXCHANGE
      WHEN 7 THEN 999   -- SMA_VICTORIA -> SMA_VICTORIA
      WHEN 8 THEN 301   -- COIN (Coinbase) -> ETH_BLOCKCHAIN (stub, crypto isn't really implemented)
      WHEN 9 THEN 205   -- MILAN (Borsa Italiana) -> MILAN_EXCHANGE
      WHEN 10 THEN 206  -- WSE -> WSE_EXCHANGE
      ELSE 0            -- unset/unknown -> UNDEFINED
    END
  FROM asset_tickers;
PRAGMA foreign_keys = OFF;  -- Prevent deletion of linked asset_ids
DROP TABLE asset_tickers;
-- Re-create symbol_ids table to recover foreign keys (otherwise it will be linked to an old non-existing table asset_tickers
CREATE TABLE IF NOT EXISTS symbol_ids_new (
    id        INTEGER PRIMARY KEY UNIQUE NOT NULL,
    symbol_id INTEGER REFERENCES asset_symbol (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    id_type   INTEGER NOT NULL,
    id_value  TEXT NOT NULL
);
INSERT INTO symbol_ids_new (id, symbol_id, id_type, id_value)
  SELECT id, symbol_id, id_type, id_value FROM symbol_ids;
DROP TABLE symbol_ids;
ALTER TABLE symbol_ids_new RENAME TO symbol_ids;
PRAGMA foreign_keys = ON;  -- Prevent deletion of linked asset_ids
CREATE UNIQUE INDEX uniq_symbols ON asset_symbol (asset_id, symbol COLLATE NOCASE, currency_id);
-- Seed ISO4217 numeric codes for currency symbols (fresh installs get them from jal_init.sql).
-- Currencies with unrecognized symbols are skipped and may be filled in manually.
INSERT INTO symbol_ids (symbol_id, id_type, id_value)
  SELECT q.id, 6, q.code FROM (
    SELECT s.id,
      CASE s.symbol
        WHEN 'RUB' THEN '643' WHEN 'USD' THEN '840' WHEN 'EUR' THEN '978'
        WHEN 'CNY' THEN '156' WHEN 'GBP' THEN '826' WHEN 'GEL' THEN '981'
        WHEN 'HUF' THEN '348' WHEN 'ILS' THEN '376' WHEN 'KZT' THEN '398'
        WHEN 'PLN' THEN '985' WHEN 'TRY' THEN '949'
      END AS code
    FROM asset_symbol s
    JOIN assets a ON s.asset_id=a.id AND a.type_id=1
    WHERE s.active=1
      AND NOT EXISTS (SELECT 1 FROM symbol_ids i WHERE i.symbol_id=s.id AND i.id_type=6)
  ) q
  WHERE NOT q.code IS NULL;
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
  SELECT p.oid, p.otype, p.timestamp, p.ex_date, p.number, p.type, p.account_id,
         (SELECT MIN(s.id) FROM asset_symbol s WHERE p.asset_id=s.asset_id AND a.currency_id=s.currency_id AND s.active=1) AS symbol_id,
         p.amount, p.tax, p.note
  FROM old_asset_payments p
  LEFT JOIN accounts a ON p.account_id=a.id;
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
  SELECT t.oid, t.otype, t.timestamp, t.settlement, t.number, t.account_id,
         (SELECT MIN(s.id) FROM asset_symbol s WHERE t.asset_id=s.asset_id AND a.currency_id=s.currency_id AND s.active=1) AS symbol_id,
         t.qty, t.price, t.fee, t.note
  FROM old_trades t
  LEFT JOIN accounts a ON t.account_id=a.id;
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
  SELECT t.oid, t.otype, t.withdrawal_timestamp, t.withdrawal_account, t.withdrawal, t.deposit_timestamp, t.deposit_account, t.deposit, t.fee_account, t.fee, t.number,
         (SELECT MIN(s.id) FROM asset_symbol s WHERE t.asset=s.asset_id AND a.currency_id=s.currency_id AND s.active=1) AS symbol_id,
         t.note
  FROM old_transfers t
  LEFT JOIN accounts a ON t.withdrawal_account=a.id;
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
  SELECT r.id, r.action_id,
         (SELECT MIN(s.id) FROM asset_symbol s WHERE r.asset_id=s.asset_id AND a.currency_id=s.currency_id AND s.active=1) AS symbol_id,
         r.qty, r.value_share
  FROM old_action_results r
  LEFT JOIN asset_actions aa ON r.action_id=aa.oid
  LEFT JOIN accounts a ON aa.account_id=a.id;
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
  SELECT o.oid, o.otype, o.timestamp, o.number, o.account_id, o.type,
         (SELECT MIN(s.id) FROM asset_symbol s WHERE o.asset_id=s.asset_id AND a.currency_id=s.currency_id AND s.active=1) AS symbol_id,
         o.qty, o.note
  FROM old_asset_actions o
  LEFT JOIN accounts a ON o.account_id=a.id;
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
INSERT OR REPLACE INTO settings(name, value) VALUES ('RebuildDB', 1);
COMMIT;