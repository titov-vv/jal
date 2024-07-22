BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = OFF;
--------------------------------------------------------------------------------
-- Insert root elements for tree-structure supported by foreign key
INSERT INTO agents (id, pid, name) VALUES (0, 0, '');
INSERT INTO categories (id, pid, name, often) VALUES (0, 0, '', 0);
INSERT INTO tags (id, pid, tag) VALUES (0, 0, '');
--------------------------------------------------------------------------------
-- Remove outdated triggers
DROP TRIGGER IF EXISTS keep_predefined_agents;
DROP TRIGGER IF EXISTS keep_predefined_categories;
--------------------------------------------------------------------------------
-- Introduce foreign keys into tables that have data structured as a tree
-- Fix any possible problems with NULL
UPDATE agents SET location='' WHERE location IS NULL;
UPDATE tags SET icon_file='' WHERE icon_file IS NULL;
-- Update Agents table
DROP TABLE IF EXISTS temp_agents;
CREATE TABLE temp_agents AS SELECT * FROM agents;
DROP TABLE agents;
CREATE TABLE agents (
    id       INTEGER    PRIMARY KEY UNIQUE NOT NULL,
    pid      INTEGER    NOT NULL DEFAULT (0) REFERENCES agents (id) ON DELETE CASCADE ON UPDATE CASCADE,
    name     TEXT (64)  UNIQUE NOT NULL,
    location TEXT (128) NOT NULL DEFAULT ('')
);
INSERT INTO agents (id, pid, name, location) SELECT id, pid, name, location FROM temp_agents;
DROP TABLE temp_agents;
-- Update Categories table
DROP TABLE IF EXISTS temp_categories;
CREATE TABLE temp_categories AS SELECT * FROM categories;
DROP TABLE categories;
CREATE TABLE categories (
    id      INTEGER   PRIMARY KEY UNIQUE NOT NULL,
    pid     INTEGER   NOT NULL DEFAULT (0) REFERENCES categories (id) ON DELETE CASCADE ON UPDATE CASCADE,
    name    TEXT (64) UNIQUE NOT NULL
);
INSERT INTO categories (id, pid, name) SELECT id, pid, name FROM temp_categories;
DROP TABLE temp_categories;
-- Update Tags table
DROP TABLE IF EXISTS temp_tags;
CREATE TABLE temp_tags AS SELECT * FROM tags;
DROP TABLE tags;
CREATE TABLE tags (
    id         INTEGER   PRIMARY KEY UNIQUE NOT NULL,
    pid        INTEGER   NOT NULL DEFAULT (0) REFERENCES tags (id) ON DELETE CASCADE ON UPDATE CASCADE,
    tag        TEXT (64) NOT NULL UNIQUE,
    icon_file  TEXT      DEFAULT ('') NOT NULL
);
INSERT INTO tags (id, pid, tag, icon_file) SELECT id, pid, tag, icon_file FROM temp_tags;
DROP TABLE temp_tags;
-- Restore index
CREATE INDEX agents_by_name_idx ON agents (name);
--------------------------------------------------------------------------------
-- Correct foreign keys in accounts table
CREATE TABLE temp_accounts AS SELECT * FROM accounts;
DROP TABLE IF EXISTS accounts;
CREATE TABLE accounts (
    id              INTEGER   PRIMARY KEY UNIQUE NOT NULL,
    name            TEXT (64) NOT NULL UNIQUE,                                                                       -- human-readable name of the account
    currency_id     INTEGER   REFERENCES assets (id) ON DELETE RESTRICT ON UPDATE CASCADE NOT NULL,                  -- accounting currency for the account
    active          INTEGER   DEFAULT (1) NOT NULL ON CONFLICT REPLACE,                                              -- 1 = account is active, 0 = inactive (hidden in UI)
    investing       INTEGER   NOT NULL DEFAULT (0),                                                                  -- 1 if account can hold investment assets, 0 otherwise
    tag_id          INTEGER   REFERENCES tags (id) ON DELETE SET NULL ON UPDATE CASCADE,                             -- optional tag of the account
    number          TEXT (32),                                                                                       -- human-readable number of account (as a reference to bank/broker documents)
    reconciled_on   INTEGER   DEFAULT (0) NOT NULL ON CONFLICT REPLACE,                                              -- timestamp of last confirmed operation
    organization_id INTEGER   REFERENCES agents (id) ON DELETE SET DEFAULT ON UPDATE CASCADE NOT NULL DEFAULT (1),   -- Bank/Broker that handles account
    country_id      INTEGER   REFERENCES countries (id) ON DELETE SET DEFAULT ON UPDATE CASCADE DEFAULT (0) NOT NULL,-- Location of the account
    precision       INTEGER   NOT NULL DEFAULT (2)                                                                   -- number of digits after decimal points that is used by this account
);
INSERT INTO accounts (id, name, currency_id, active, investing, tag_id, number, reconciled_on, organization_id, country_id, precision)
  SELECT id, name, currency_id, active, investing, tag_id, number, reconciled_on, organization_id, country_id, precision FROM temp_accounts;
DROP TABLE temp_accounts;
-- Correct foreign keys in assets table
CREATE TABLE temp_assets AS SELECT * FROM assets;
DROP TABLE IF EXISTS assets;
CREATE TABLE assets (
    id         INTEGER    PRIMARY KEY UNIQUE NOT NULL,
    type_id    INTEGER    NOT NULL,
    full_name  TEXT (128) NOT NULL,
    isin       TEXT (12)  DEFAULT ('') NOT NULL,
    country_id INTEGER    REFERENCES countries (id) ON DELETE SET DEFAULT ON UPDATE CASCADE NOT NULL DEFAULT (0),
    base_asset INTEGER    REFERENCES assets (id) ON DELETE SET NULL ON UPDATE CASCADE
);
INSERT INTO assets (id, type_id, full_name, isin, country_id, base_asset) SELECT id, type_id, full_name, isin, country_id, base_asset FROM temp_assets;
DROP TABLE temp_assets;
-- Correct foreign key in actions table
CREATE TABLE temp_actions AS SELECT * FROM actions;
DROP TABLE IF EXISTS actions;
CREATE TABLE actions (
    oid             INTEGER PRIMARY KEY UNIQUE NOT NULL,
    otype           INTEGER NOT NULL DEFAULT (1),
    timestamp       INTEGER NOT NULL,
    account_id      INTEGER REFERENCES accounts (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    peer_id         INTEGER REFERENCES agents (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,   -- agent that is related with this transaction
    alt_currency_id INTEGER REFERENCES assets (id) ON DELETE SET NULL ON UPDATE CASCADE,           -- if transaction actually happened in another currency
    note            TEXT
);
INSERT INTO actions (oid, otype, timestamp, account_id, peer_id, alt_currency_id, note)
  SELECT oid, otype, timestamp, account_id, peer_id, alt_currency_id, note FROM temp_actions;
DROP TABLE temp_actions;
-- Correct foreign key in asset_payments table
CREATE TABLE temp_asset_payments AS SELECT * FROM asset_payments;
DROP TABLE IF EXISTS asset_payments;
CREATE TABLE asset_payments (
    oid        INTEGER PRIMARY KEY UNIQUE NOT NULL,
    otype      INTEGER NOT NULL DEFAULT (2),
    timestamp  INTEGER NOT NULL,
    ex_date    INTEGER NOT NULL DEFAULT (0),
    number     TEXT    NOT NULL DEFAULT (''),
    type       INTEGER NOT NULL,
    account_id INTEGER REFERENCES accounts (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    asset_id   INTEGER REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    amount     TEXT    NOT NULL DEFAULT ('0'),
    tax        TEXT    NOT NULL DEFAULT ('0'),
    note       TEXT
);
INSERT INTO asset_payments (oid, otype, timestamp, ex_date, number, type, account_id, asset_id, amount, tax, note)
  SELECT oid, otype, timestamp, ex_date, number, type, account_id, asset_id, amount, tax, note FROM temp_asset_payments;
DROP TABLE temp_asset_payments;
-- Correct foreign key in asset_actions table
CREATE TABLE temp_asset_actions AS SELECT * FROM asset_actions;
DROP TABLE IF EXISTS asset_actions;
CREATE TABLE asset_actions (
    oid        INTEGER     PRIMARY KEY UNIQUE NOT NULL,
    otype      INTEGER     NOT NULL DEFAULT (5),
    timestamp  INTEGER     NOT NULL,
    number     TEXT        DEFAULT (''),
    account_id INTEGER     REFERENCES accounts (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    type       INTEGER     NOT NULL,
    asset_id   INTEGER     REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    qty        TEXT        NOT NULL,
    note       TEXT
);
INSERT INTO asset_actions (oid, otype, timestamp, number, account_id, type, asset_id, qty, note)
  SELECT oid, otype, timestamp, number, account_id, type, asset_id, qty, note FROM temp_asset_actions;
DROP TABLE temp_asset_actions;
-- Correct foreign key in trades table
CREATE TABLE temp_trades AS SELECT * FROM trades;
DROP TABLE IF EXISTS trades;
CREATE TABLE trades (
    oid        INTEGER     PRIMARY KEY UNIQUE NOT NULL,
    otype      INTEGER     NOT NULL DEFAULT (3),
    timestamp  INTEGER     NOT NULL,
    settlement INTEGER     DEFAULT (0),
    number     TEXT        DEFAULT (''),
    account_id INTEGER     REFERENCES accounts (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    asset_id   INTEGER     REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    qty        TEXT        NOT NULL DEFAULT ('0'),
    price      TEXT        NOT NULL DEFAULT ('0'),
    fee        TEXT        DEFAULT ('0'),
    note       TEXT
);
INSERT INTO trades (oid, otype, timestamp, settlement, number, account_id, asset_id, qty, price, fee, note)
  SELECT oid, otype, timestamp, settlement, number, account_id, asset_id, qty, price, fee, note FROM temp_trades;
DROP TABLE temp_trades;
-- Restore triggers
CREATE TRIGGER actions_after_delete AFTER DELETE ON actions FOR EACH ROW BEGIN DELETE FROM action_details WHERE pid = OLD.oid; DELETE FROM ledger WHERE timestamp >= OLD.timestamp; END;
CREATE TRIGGER actions_after_insert AFTER INSERT ON actions FOR EACH ROW BEGIN DELETE FROM ledger WHERE timestamp >= NEW.timestamp; END;
CREATE TRIGGER actions_after_update AFTER UPDATE OF timestamp, account_id, peer_id ON actions FOR EACH ROW BEGIN DELETE FROM ledger WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp; END;
CREATE TRIGGER asset_payments_after_delete AFTER DELETE ON asset_payments FOR EACH ROW BEGIN DELETE FROM ledger WHERE timestamp >= OLD.timestamp; DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp; END;
CREATE TRIGGER asset_payments_after_insert AFTER INSERT ON asset_payments FOR EACH ROW BEGIN DELETE FROM ledger WHERE timestamp >= NEW.timestamp; DELETE FROM trades_opened WHERE timestamp >= NEW.timestamp; END;
CREATE TRIGGER asset_payments_after_update AFTER UPDATE OF timestamp, type, account_id, asset_id, amount, tax ON asset_payments FOR EACH ROW BEGIN DELETE FROM ledger WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp; DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp; END;
CREATE TRIGGER asset_action_after_delete AFTER DELETE ON asset_actions FOR EACH ROW BEGIN DELETE FROM action_results WHERE action_id = OLD.oid; DELETE FROM ledger WHERE timestamp >= OLD.timestamp; DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp; END;
CREATE TRIGGER asset_action_after_insert AFTER INSERT ON asset_actions FOR EACH ROW BEGIN DELETE FROM ledger WHERE timestamp >= NEW.timestamp; DELETE FROM trades_opened WHERE timestamp >= NEW.timestamp; END;
CREATE TRIGGER asset_action_after_update AFTER UPDATE OF timestamp, account_id, type, asset_id, qty ON asset_actions FOR EACH ROW BEGIN DELETE FROM ledger WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp; DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp; END;
CREATE TRIGGER trades_after_delete AFTER DELETE ON trades FOR EACH ROW BEGIN DELETE FROM ledger WHERE timestamp >= OLD.timestamp; DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp; END;
CREATE TRIGGER trades_after_insert AFTER INSERT ON trades FOR EACH ROW BEGIN DELETE FROM ledger WHERE timestamp >= NEW.timestamp; DELETE FROM trades_opened WHERE timestamp >= NEW.timestamp; END;
CREATE TRIGGER trades_after_update AFTER UPDATE OF timestamp, account_id, asset_id, qty, price, fee ON trades FOR EACH ROW BEGIN DELETE FROM ledger WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp; DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp; END;
--------------------------------------------------------------------------------
-- re-create ledger table with updated FKs
DROP TABLE IF EXISTS ledger;
CREATE TABLE ledger (
    id           INTEGER PRIMARY KEY NOT NULL UNIQUE,
    timestamp    INTEGER NOT NULL,
    otype        INTEGER NOT NULL,
    oid          INTEGER NOT NULL,
    opart        INTEGER NOT NULL,
    book_account INTEGER NOT NULL,
    asset_id     INTEGER REFERENCES assets (id) ON DELETE SET NULL ON UPDATE SET NULL,
    account_id   INTEGER NOT NULL REFERENCES accounts (id) ON DELETE NO ACTION ON UPDATE NO ACTION,
    amount       TEXT,
    value        TEXT,
    amount_acc   TEXT,
    value_acc    TEXT,
    peer_id      INTEGER REFERENCES agents (id) ON DELETE NO ACTION ON UPDATE NO ACTION,
    category_id  INTEGER REFERENCES categories (id) ON DELETE NO ACTION ON UPDATE NO ACTION,
    tag_id       INTEGER REFERENCES tags (id) ON DELETE NO ACTION ON UPDATE NO ACTION
);
--------------------------------------------------------------------------------
-- re-create trades_closed table with updated FKs
DROP TABLE IF EXISTS trades_closed;
CREATE TABLE trades_closed (
    id              INTEGER PRIMARY KEY UNIQUE NOT NULL,
    account_id      INTEGER REFERENCES accounts (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    asset_id        INTEGER REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    open_otype      INTEGER NOT NULL,   -- Operation type that already initiated the trade
    open_oid        INTEGER NOT NULL,   -- Operation ID that already initiated the trade
    open_timestamp  INTEGER NOT NULL,
    open_price      TEXT    NOT NULL,
    open_qty        TEXT    NOT NULL,   -- Part of open operation that was used in this trade
    close_otype     INTEGER NOT NULL,   -- Operation type that finalized the trade
    close_oid       INTEGER NOT NULL,   -- Operation ID that finalized the trade
    close_timestamp INTEGER NOT NULL,
    close_price     TEXT    NOT NULL,
    close_qty       TEXT    NOT NULL,   -- Part of close operation that was used in this trade
    c_price         TEXT    NOT NULL DEFAULT ('1'),  -- Historical adjustment coefficient of open price
    c_qty           TEXT    NOT NULL DEFAULT ('1')   -- Historical adjustment coefficient of open quantity
);
--------------------------------------------------------------------------------
-- Actions cleanup if all details were deleted
DROP TRIGGER IF EXISTS action_details_parent_clean;
CREATE TRIGGER action_details_parent_clean
AFTER DELETE ON action_details WHEN (SELECT COUNT(id) FROM action_details WHERE pid = OLD.pid) = 0
BEGIN
    DELETE FROM actions WHERE oid = OLD.pid;
END;
-- Add new triggers for ledger update after change in reference data
DROP TRIGGER IF EXISTS agents_after_delete;
CREATE TRIGGER agents_after_delete AFTER DELETE ON agents FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= (SELECT MIN(timestamp) FROM ledger WHERE peer_id=OLD.id);
END;
DROP TRIGGER IF EXISTS categories_after_delete;
CREATE TRIGGER categories_after_delete AFTER DELETE ON categories FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= (SELECT MIN(timestamp) FROM ledger WHERE category_id=OLD.id);
END;
DROP TRIGGER IF EXISTS tags_after_delete;
CREATE TRIGGER tags_after_delete AFTER DELETE ON tags FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= (SELECT MIN(timestamp) FROM ledger WHERE tag_id=OLD.id);
    DELETE FROM asset_data WHERE datatype=4 AND value=OLD.id;
END;

--------------------------------------------------------------------------------
-- Error correction in trigger definition
DROP TRIGGER IF EXISTS deposit_action_after_update;
CREATE TRIGGER deposit_action_after_update AFTER UPDATE OF timestamp, action_type, amount ON deposit_actions FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
END;

--------------------------------------------------------------------------------
-- Modify view
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
) AS m
ORDER BY m.timestamp, m.seq, m.opart, m.oid;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=57 WHERE name='SchemaVersion';
INSERT OR REPLACE INTO settings(name, value) VALUES ('RebuildDB', 1);
COMMIT;
VACUUM;