BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 0;
--------------------------------------------------------------------------------
-- Extend accounts table
ALTER TABLE accounts ADD COLUMN precision INTEGER NOT NULL DEFAULT (2);
--------------------------------------------------------------------------------
DROP VIEW IF EXISTS last_account_value;
DROP VIEW IF EXISTS last_assets;
DROP VIEW IF EXISTS last_quotes;
DROP TABLE IF EXISTS view_params;
--------------------------------------------------------------------------------
-- Drop unused table
DROP TABLE IF EXISTS t_last_dates;
DROP TABLE IF EXISTS t_last_assets;
--------------------------------------------------------------------------------
-- Drop table books and modify ledger table to use TEXT instead of REAL for decimal storage
DROP TABLE IF EXISTS ledger;
CREATE TABLE ledger (
    id           INTEGER PRIMARY KEY NOT NULL UNIQUE,
    timestamp    INTEGER NOT NULL,
    op_type      INTEGER NOT NULL,
    operation_id INTEGER NOT NULL,
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
DROP TABLE IF EXISTS books;

---------------------------------------------------------------------------------
-- Modify ledger_totals table to use TEXT instead of REAL for decimal storage
DROP TABLE IF EXISTS ledger_totals;
CREATE TABLE ledger_totals (
    id           INTEGER PRIMARY KEY UNIQUE NOT NULL,
    op_type      INTEGER NOT NULL,
    operation_id INTEGER NOT NULL,
    timestamp    INTEGER NOT NULL,
    book_account INTEGER NOT NULL,
    asset_id     INTEGER NOT NULL,
    account_id   INTEGER NOT NULL,
    amount_acc   TEXT    NOT NULL,
    value_acc    TEXT    NOT NULL
);
DROP INDEX IF EXISTS ledger_totals_by_timestamp;
CREATE INDEX ledger_totals_by_timestamp ON ledger_totals (timestamp);
DROP INDEX IF EXISTS ledger_totals_by_operation_book;
CREATE INDEX ledger_totals_by_operation_book ON ledger_totals (op_type, operation_id, book_account);

---------------------------------------------------------------------------------
-- Rename of open_trades table to trades_opened and conversion from REAL to TEXT storage of decimal values
DROP TABLE IF EXISTS open_trades;
CREATE TABLE trades_opened (
    id            INTEGER PRIMARY KEY UNIQUE NOT NULL,
    timestamp     INTEGER NOT NULL,
    op_type       INTEGER NOT NULL,
    operation_id  INTEGER NOT NULL,
    account_id    INTEGER REFERENCES accounts (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    asset_id      INTEGER NOT NULL REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE,
    price         TEXT    NOT NULL,
    remaining_qty TEXT    NOT NULL
);

---------------------------------------------------------------------------------
-- Rename of deals table to trades_closed and conversion from REAL to TEXT storage of decimal values
DROP TABLE IF EXISTS deals;
CREATE TABLE trades_closed (
    id              INTEGER PRIMARY KEY UNIQUE NOT NULL,
    account_id      INTEGER NOT NULL,
    asset_id        INTEGER NOT NULL,
    open_op_type    INTEGER NOT NULL,
    open_op_id      INTEGER NOT NULL,
    open_timestamp  INTEGER NOT NULL,
    open_price      TEXT    NOT NULL,
    close_op_type   INTEGER NOT NULL,
    close_op_id     INTEGER NOT NULL,
    close_timestamp INTEGER NOT NULL,
    close_price     TEXT    NOT NULL,
    qty             TEXT    NOT NULL
);

DROP TRIGGER IF EXISTS on_deal_delete;
CREATE TRIGGER on_closed_trade_delete
    AFTER DELETE ON trades_closed
    FOR EACH ROW
    WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    UPDATE trades_opened
    SET remaining_qty = remaining_qty + OLD.qty
    WHERE op_type=OLD.open_op_type AND operation_id=OLD.open_op_id AND account_id=OLD.account_id AND asset_id = OLD.asset_id;
END;

-- View: deals_ext
DROP VIEW IF EXISTS deals_ext;
CREATE VIEW deals_ext AS
    SELECT d.account_id,
           ac.name AS account,
           d.asset_id,
           at.symbol AS asset,
           open_timestamp,
           close_timestamp,
           open_price,
           close_price,
           d.qty AS qty,
           coalesce(ot.fee * abs(d.qty / ot.qty), 0) + coalesce(ct.fee * abs(d.qty / ct.qty), 0) AS fee,
           d.qty * (close_price - open_price ) - (coalesce(ot.fee * abs(d.qty / ot.qty), 0) + coalesce(ct.fee * abs(d.qty / ct.qty), 0) ) AS profit,
           coalesce(100 * (d.qty * (close_price - open_price ) - (coalesce(ot.fee * abs(d.qty / ot.qty), 0) + coalesce(ct.fee * abs(d.qty / ct.qty), 0) ) ) / abs(d.qty * open_price ), 0) AS rel_profit,
           coalesce(oca.type, -cca.type) AS corp_action
    FROM trades_closed AS d
          -- Get more information about trade/corp.action that opened the deal
           LEFT JOIN trades AS ot ON ot.id=d.open_op_id AND ot.op_type=d.open_op_type
           LEFT JOIN asset_actions AS oca ON oca.id=d.open_op_id AND oca.op_type=d.open_op_type
          -- Get more information about trade/corp.action that opened the deal
           LEFT JOIN trades AS ct ON ct.id=d.close_op_id AND ct.op_type=d.close_op_type
           LEFT JOIN asset_actions AS cca ON cca.id=d.close_op_id AND cca.op_type=d.close_op_type
          -- "Decode" account and asset
           LEFT JOIN accounts AS ac ON d.account_id = ac.id
           LEFT JOIN asset_tickers AS at ON d.asset_id = at.asset_id AND ac.currency_id=at.currency_id AND at.active=1
     -- drop cases where deal was opened and closed with corporate action
     WHERE NOT (d.open_op_type = 5 AND d.close_op_type = 5)
     ORDER BY close_timestamp, open_timestamp;

---------------------------------------------------------------------------------
-- Conversion of action_details table from REAL to TEXT storage of decimal values
CREATE TABLE old_details AS SELECT * FROM action_details;
DROP TABLE IF EXISTS action_details;
CREATE TABLE action_details (
    id          INTEGER    PRIMARY KEY NOT NULL UNIQUE,
    pid         INTEGER    REFERENCES actions (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    category_id INTEGER    REFERENCES categories (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    tag_id      INTEGER    REFERENCES tags (id) ON DELETE SET NULL ON UPDATE CASCADE,
    amount      TEXT       NOT NULL,
    amount_alt  TEXT       DEFAULT ('0') NOT NULL,
    note        TEXT
);

INSERT INTO action_details (id, pid, category_id, tag_id, amount, amount_alt, note)
  SELECT id, pid, category_id, tag_id, CAST(ROUND(amount, 9) AS TEXT), CAST(ROUND(amount_alt, 9) AS TEXT), note
  FROM old_details;
DROP TABLE old_details;

CREATE INDEX details_by_pid ON action_details (pid);

DROP TRIGGER IF EXISTS action_details_after_delete;
CREATE TRIGGER action_details_after_delete
      AFTER DELETE ON action_details
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= (SELECT timestamp FROM actions WHERE id = OLD.pid);
END;

DROP TRIGGER IF EXISTS action_details_after_insert;
CREATE TRIGGER action_details_after_insert
      AFTER INSERT ON action_details
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= (SELECT timestamp FROM actions WHERE id = NEW.pid);
END;

DROP TRIGGER IF EXISTS action_details_after_update;
CREATE TRIGGER action_details_after_update
      AFTER UPDATE ON action_details
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= (SELECT timestamp FROM actions WHERE id = OLD.pid );
END;
---------------------------------------------------------------------------------
-- Conversion of action_results table from REAL to TEXT storage of decimal values
CREATE TABLE old_results AS SELECT * FROM action_results;
DROP TABLE IF EXISTS action_results;
CREATE TABLE action_results (
    id          INTEGER PRIMARY KEY UNIQUE NOT NULL,
    action_id   INTEGER NOT NULL REFERENCES asset_actions (id) ON DELETE CASCADE ON UPDATE CASCADE,
    asset_id    INTEGER REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    qty         TEXT    NOT NULL,
    value_share TEXT    NOT NULL
);
INSERT INTO action_results (id, action_id, asset_id, qty, value_share)
  SELECT id, action_id, asset_id, CAST(ROUND(qty, 9) AS TEXT), CAST(ROUND(value_share, 9) AS TEXT)
  FROM old_results;
DROP TABLE old_results;

DROP TRIGGER IF EXISTS asset_result_after_delete;
CREATE TRIGGER asset_result_after_delete
      AFTER DELETE ON action_results
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= (SELECT timestamp FROM asset_actions WHERE id = OLD.action_id);
END;

DROP TRIGGER IF EXISTS asset_result_after_insert;
CREATE TRIGGER asset_result_after_insert
      AFTER INSERT ON action_results
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= (SELECT timestamp FROM asset_actions WHERE id = NEW.action_id);
END;

DROP TRIGGER IF EXISTS asset_result_after_update;
CREATE TRIGGER asset_result_after_update
      AFTER UPDATE OF asset_id, qty, value_share ON action_results
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= (SELECT timestamp FROM asset_actions WHERE id = OLD.action_id);
END;
---------------------------------------------------------------------------------
-- Conversion of action_actions table from REAL to TEXT storage of decimal values
CREATE TABLE old_actions AS SELECT * FROM asset_actions;
DROP TABLE IF EXISTS asset_actions;
CREATE TABLE asset_actions (
    id         INTEGER     PRIMARY KEY UNIQUE NOT NULL,
    op_type    INTEGER     NOT NULL DEFAULT (5),
    timestamp  INTEGER     NOT NULL,
    number     TEXT        DEFAULT (''),
    account_id INTEGER     REFERENCES accounts (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    type       INTEGER     NOT NULL,
    asset_id   INTEGER     REFERENCES assets (id) ON DELETE RESTRICT ON UPDATE CASCADE NOT NULL,
    qty        TEXT        NOT NULL,
    note       TEXT
);
INSERT INTO asset_actions (id, op_type, timestamp, number, account_id, type, asset_id, qty, note)
  SELECT id, op_type, timestamp, number, account_id, type, asset_id, CAST(ROUND(qty, 9) AS TEXT), note
  FROM old_actions;
DROP TABLE old_actions;

DROP TRIGGER IF EXISTS asset_action_after_delete;
CREATE TRIGGER asset_action_after_delete
      AFTER DELETE ON asset_actions
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp;
END;

DROP TRIGGER IF EXISTS asset_action_after_insert;
CREATE TRIGGER asset_action_after_insert
      AFTER INSERT ON asset_actions
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= NEW.timestamp;
END;

DROP TRIGGER IF EXISTS asset_action_after_update;
CREATE TRIGGER asset_action_after_update
      AFTER UPDATE OF timestamp, account_id, type, asset_id, qty ON asset_actions
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp  OR timestamp >= NEW.timestamp;
END;
---------------------------------------------------------------------------------
-- Conversion of dividends table from REAL to TEXT storage of decimal values
CREATE TABLE old_dividends AS SELECT * FROM dividends;
DROP TABLE IF EXISTS dividends;
CREATE TABLE dividends (
    id         INTEGER     PRIMARY KEY UNIQUE NOT NULL,
    op_type    INTEGER     NOT NULL DEFAULT (2),
    timestamp  INTEGER     NOT NULL,
    ex_date    INTEGER,
    number     TEXT        DEFAULT (''),
    type       INTEGER     NOT NULL,
    account_id INTEGER     REFERENCES accounts (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    asset_id   INTEGER     REFERENCES assets (id) ON DELETE RESTRICT ON UPDATE CASCADE NOT NULL,
    amount     TEXT        NOT NULL DEFAULT ('0'),
    tax        TEXT        DEFAULT ('0'),
    note       TEXT
);
INSERT INTO dividends (id, op_type, timestamp, ex_date, number, type, account_id, asset_id, amount, tax, note)
  SELECT id, op_type, timestamp, ex_date, number, type, account_id, asset_id, CAST(ROUND(amount, 9) AS TEXT), CAST(ROUND(tax, 9) AS TEXT), note
  FROM old_dividends;
DROP TABLE old_dividends;

DROP TRIGGER IF EXISTS dividends_after_delete;
CREATE TRIGGER dividends_after_delete
      AFTER DELETE ON dividends
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp;
END;

DROP TRIGGER IF EXISTS dividends_after_insert;
CREATE TRIGGER dividends_after_insert
      AFTER INSERT ON dividends
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= NEW.timestamp;
END;

DROP TRIGGER IF EXISTS dividends_after_update;
CREATE TRIGGER dividends_after_update
      AFTER UPDATE OF timestamp, account_id, asset_id, amount, tax ON dividends
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
END;
---------------------------------------------------------------------------------
-- Conversion of quotes table from REAL to TEXT storage of decimal values
CREATE TABLE old_quotes AS SELECT * FROM quotes;
DROP TABLE IF EXISTS quotes;
CREATE TABLE quotes (
    id          INTEGER PRIMARY KEY UNIQUE NOT NULL,
    timestamp   INTEGER NOT NULL,
    asset_id    INTEGER REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    currency_id INTEGER REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    quote       TEXT    NOT NULL DEFAULT ('0')
);
INSERT INTO quotes (id, timestamp, asset_id, currency_id, quote)
  SELECT id, timestamp, asset_id, currency_id, CAST(ROUND(quote, 9) AS TEXT)
   FROM old_quotes;
DROP TABLE old_quotes;
CREATE UNIQUE INDEX unique_quotations ON quotes (asset_id, currency_id, timestamp);
---------------------------------------------------------------------------------
-- Conversion of trades table from REAL to TEXT storage of decimal values
CREATE TABLE old_trades AS SELECT * FROM trades;
DROP TABLE IF EXISTS trades;
CREATE TABLE trades (
    id         INTEGER     PRIMARY KEY UNIQUE NOT NULL,
    op_type    INTEGER     NOT NULL DEFAULT (3),
    timestamp  INTEGER     NOT NULL,
    settlement INTEGER     DEFAULT (0),
    number     TEXT        DEFAULT (''),
    account_id INTEGER     REFERENCES accounts (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    asset_id   INTEGER     REFERENCES assets (id) ON DELETE RESTRICT ON UPDATE CASCADE NOT NULL,
    qty        TEXT        NOT NULL DEFAULT ('0'),
    price      TEXT        NOT NULL DEFAULT ('0'),
    fee        TEXT        DEFAULT ('0'),
    note       TEXT
);
INSERT INTO trades (id, op_type, timestamp, settlement, number, account_id, asset_id, qty, price, fee, note)
  SELECT id, op_type, timestamp, settlement, number, account_id, asset_id, CAST(ROUND(qty, 9) AS TEXT), CAST(ROUND(price, 9) AS TEXT), CAST(ROUND(fee, 9) AS TEXT), note
  FROM old_trades;
DROP TABLE old_trades;

DROP TRIGGER IF EXISTS trades_after_delete;
CREATE TRIGGER trades_after_delete
         AFTER DELETE ON trades
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp;
END;

DROP TRIGGER IF EXISTS trades_after_insert;
CREATE TRIGGER trades_after_insert
      AFTER INSERT ON trades
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= NEW.timestamp;
END;

DROP TRIGGER IF EXISTS trades_after_update;
CREATE TRIGGER trades_after_update
      AFTER UPDATE OF timestamp, account_id, asset_id, qty, price, fee ON trades
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
END;
---------------------------------------------------------------------------------
-- Conversion of transfers table from REAL to TEXT storage of decimal values
CREATE TABLE old_transfers AS SELECT * FROM transfers;
DROP TABLE IF EXISTS transfers;
CREATE TABLE transfers (
    id                   INTEGER     PRIMARY KEY UNIQUE NOT NULL,
    op_type              INTEGER     NOT NULL DEFAULT (4),
    withdrawal_timestamp INTEGER     NOT NULL,
    withdrawal_account   INTEGER     NOT NULL REFERENCES accounts (id) ON DELETE CASCADE ON UPDATE CASCADE,
    withdrawal           TEXT        NOT NULL,
    deposit_timestamp    INTEGER     NOT NULL,
    deposit_account      INTEGER     NOT NULL REFERENCES accounts (id) ON DELETE CASCADE ON UPDATE CASCADE,
    deposit              TEXT        NOT NULL,
    fee_account          INTEGER     REFERENCES accounts (id) ON DELETE CASCADE ON UPDATE CASCADE,
    fee                  TEXT,
    asset                INTEGER     REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE,
    note                 TEXT
);
INSERT INTO transfers (id, op_type, withdrawal_timestamp, withdrawal_account, withdrawal,
                       deposit_timestamp, deposit_account, deposit, fee_account, fee, asset, note)
  SELECT id, op_type, withdrawal_timestamp, withdrawal_account, CAST(ROUND(withdrawal, 9) AS TEXT),
         deposit_timestamp, deposit_account, CAST(ROUND(deposit, 9) AS TEXT), fee_account, CAST(ROUND(fee, 9) AS TEXT), asset, note
  FROM old_transfers;
DROP TABLE old_transfers;

DROP TRIGGER IF EXISTS transfers_after_delete;
CREATE TRIGGER transfers_after_delete
      AFTER DELETE ON transfers
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.withdrawal_timestamp OR timestamp >= OLD.deposit_timestamp;
END;

DROP TRIGGER IF EXISTS transfers_after_insert;
CREATE TRIGGER transfers_after_insert
      AFTER INSERT ON transfers
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= NEW.withdrawal_timestamp OR timestamp >= NEW.deposit_timestamp;
END;

DROP TRIGGER IF EXISTS transfers_after_update;
CREATE TRIGGER transfers_after_update
      AFTER UPDATE OF withdrawal_timestamp, deposit_timestamp, withdrawal_account, deposit_account, fee_account,
                      withdrawal, deposit, fee, asset ON transfers
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.withdrawal_timestamp OR timestamp >= OLD.deposit_timestamp OR
                timestamp >= NEW.withdrawal_timestamp OR timestamp >= NEW.deposit_timestamp;
END;
--------------------------------------------------------------------------------
-- Enforce unique names in shop mapping 
CREATE TABLE temp_map_peer AS SELECT * FROM map_peer;
DROP TABLE map_peer;
CREATE TABLE map_peer (
    id        INTEGER PRIMARY KEY UNIQUE NOT NULL,
    value     TEXT    NOT NULL UNIQUE,
    mapped_to INTEGER REFERENCES agents (id) ON DELETE SET DEFAULT ON UPDATE CASCADE NOT NULL DEFAULT (0) 
);
INSERT INTO map_peer (value, mapped_to) SELECT value, mapped_to FROM temp_map_peer GROUP BY value;
DROP TABLE temp_map_peer;
-- Enforce unique names in category mapping
CREATE TABLE temp_map_category AS SELECT * FROM map_category;
DROP TABLE map_category;
CREATE TABLE map_category (
    id        INTEGER        PRIMARY KEY UNIQUE NOT NULL,
    value     TEXT           NOT NULL UNIQUE,
    mapped_to INTEGER        NOT NULL REFERENCES categories (id) ON DELETE CASCADE ON UPDATE CASCADE
);
INSERT INTO map_category (value, mapped_to) SELECT value, mapped_to FROM temp_map_category GROUP BY value;
DROP TABLE temp_map_category;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 1;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=38 WHERE name='SchemaVersion';
INSERT OR REPLACE INTO settings(id, name, value) VALUES (7, 'RebuildDB', 1);
INSERT OR REPLACE INTO settings(id, name, value) VALUES (10, 'MessageOnce',
'{"en": "Database version was updated.\nNow you may set calculation precesion per account (default value is 2)\nPlease set higher value via menu Data->Accounts if you have finer values than 0.01.", "ru": "Версия базы данных обновлена.\nТеперь вы можете устанавливать значение точности для счёта (значение по умолчанию 2)\nПожалуйста установить большую точность через меню Данные->Счета, если у вас есть значения меньше 0.01."}');
COMMIT;
--------------------------------------------------------------------------------
-- Reduce file size
VACUUM;
