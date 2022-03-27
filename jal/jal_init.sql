--
-- File generated with SQLiteStudio v3.2.1 on Tue Jan 28 22:42:15 2020
--
-- Text encoding used: UTF-8
--
PRAGMA foreign_keys = off;
BEGIN TRANSACTION;

-- Table: account_types
DROP TABLE IF EXISTS account_types;

CREATE TABLE account_types (
    id   INTEGER   PRIMARY KEY
                   UNIQUE
                   NOT NULL,
    name TEXT (32) NOT NULL
);


-- Table: accounts
DROP TABLE IF EXISTS accounts;

CREATE TABLE accounts (
    id              INTEGER   PRIMARY KEY UNIQUE NOT NULL,
    type_id         INTEGER   REFERENCES account_types (id) ON DELETE RESTRICT ON UPDATE CASCADE NOT NULL,
    name            TEXT (64) NOT NULL UNIQUE,
    currency_id     INTEGER   REFERENCES assets (id) ON DELETE RESTRICT ON UPDATE CASCADE NOT NULL,
    active          INTEGER   DEFAULT (1) NOT NULL ON CONFLICT REPLACE,
    number          TEXT (32),
    reconciled_on   INTEGER   DEFAULT (0) NOT NULL ON CONFLICT REPLACE,
    organization_id INTEGER   REFERENCES agents (id) ON DELETE SET NULL ON UPDATE CASCADE,
    country_id      INTEGER   REFERENCES countries (id) ON DELETE CASCADE ON UPDATE CASCADE DEFAULT (0) NOT NULL
);


-- Table: action_details
DROP TABLE IF EXISTS action_details;

CREATE TABLE action_details (
    id          INTEGER    PRIMARY KEY
                           NOT NULL
                           UNIQUE,
    pid         INTEGER    REFERENCES actions (id) ON DELETE CASCADE
                                                   ON UPDATE CASCADE
                           NOT NULL,
    category_id INTEGER    REFERENCES categories (id) ON DELETE CASCADE
                                                      ON UPDATE CASCADE
                           NOT NULL,
    tag_id      INTEGER    REFERENCES tags (id) ON DELETE SET NULL
                                                ON UPDATE CASCADE,
    amount      REAL       NOT NULL,
    amount_alt  REAL       DEFAULT (0)
                           NOT NULL,
    note        TEXT (256) 
);


-- Table: actions
DROP TABLE IF EXISTS actions;

CREATE TABLE actions (
    id              INTEGER PRIMARY KEY
                            UNIQUE
                            NOT NULL,
    op_type         INTEGER NOT NULL
                            DEFAULT (1),
    timestamp       INTEGER NOT NULL,
    account_id      INTEGER REFERENCES accounts (id) ON DELETE CASCADE
                                                     ON UPDATE CASCADE
                            NOT NULL,
    peer_id         INTEGER REFERENCES agents (id) ON DELETE CASCADE
                                                   ON UPDATE CASCADE
                            NOT NULL,
    alt_currency_id INTEGER REFERENCES assets (id) ON DELETE RESTRICT
                                                   ON UPDATE CASCADE
);

-- Table: asset_types
DROP TABLE IF EXISTS asset_types;
CREATE TABLE asset_types (
    id   INTEGER   PRIMARY KEY UNIQUE NOT NULL,
    name TEXT (32) NOT NULL
);

-- Table: assets
DROP TABLE IF EXISTS assets;

CREATE TABLE assets (
    id         INTEGER    PRIMARY KEY UNIQUE NOT NULL,
    type_id    INTEGER    REFERENCES asset_types (id) ON DELETE RESTRICT ON UPDATE CASCADE NOT NULL,
    full_name  TEXT (128) NOT NULL,
    isin       TEXT (12)  DEFAULT ('') NOT NULL,
    country_id INTEGER    REFERENCES countries (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL DEFAULT (0),
    base_asset INTEGER    REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE
);

-- Table to keep asset symbols
DROP TABLE IF EXISTS asset_tickers;
CREATE TABLE asset_tickers (
    id           INTEGER PRIMARY KEY UNIQUE NOT NULL,
    asset_id     INTEGER REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    symbol       TEXT    NOT NULL,
    currency_id  INTEGER NOT NULL REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE,
    description  TEXT    NOT NULL DEFAULT (''),
    quote_source INTEGER REFERENCES data_sources (id) ON DELETE SET NULL ON UPDATE CASCADE DEFAULT (-1),
    active       INTEGER NOT NULL DEFAULT (1)
);

-- Table to keep extra asset data
DROP TABLE IF EXISTS asset_data;
CREATE TABLE asset_data (
    id       INTEGER PRIMARY KEY UNIQUE NOT NULL,
    asset_id INTEGER NOT NULL REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE,
    datatype INTEGER NOT NULL,
    value    TEXT    NOT NULL
);

DROP INDEX IF EXISTS asset_data_uniqueness;
CREATE UNIQUE INDEX asset_data_uniqueness ON asset_data ( asset_id, datatype);

-- Table: agents
DROP TABLE IF EXISTS agents;

CREATE TABLE agents (
    id       INTEGER    PRIMARY KEY
                        UNIQUE
                        NOT NULL,
    pid      INTEGER    NOT NULL
                        DEFAULT (0),
    name     TEXT (64)  UNIQUE
                        NOT NULL,
    location TEXT (128) 
);


-- Table: books
DROP TABLE IF EXISTS books;

CREATE TABLE books (
    id   INTEGER   PRIMARY KEY
                   NOT NULL
                   UNIQUE,
    name TEXT (32) NOT NULL
);


-- Table: categories
DROP TABLE IF EXISTS categories;

CREATE TABLE categories (
    id      INTEGER   PRIMARY KEY
                      UNIQUE
                      NOT NULL,
    pid     INTEGER   NOT NULL
                      DEFAULT (0),
    name    TEXT (64) UNIQUE
                      NOT NULL,
    often   INTEGER,
    special INTEGER
);

-- Create new table with list of countries
DROP TABLE IF EXISTS countries;

CREATE TABLE countries (
    id           INTEGER      PRIMARY KEY
                              UNIQUE
                              NOT NULL,
    name         VARCHAR (64) UNIQUE
                              NOT NULL,
    code         CHAR (3)     UNIQUE
                              NOT NULL,
    iso_code     CHAR (4)     UNIQUE
                              NOT NULL,
    tax_treaty   INTEGER      NOT NULL
                              DEFAULT (0)
);


-- Table: data_sources
DROP TABLE IF EXISTS data_sources;

CREATE TABLE data_sources (
    id   INTEGER   PRIMARY KEY
                   UNIQUE
                   NOT NULL,
    name TEXT (32) NOT NULL
);


-- Table: dividends
DROP TABLE IF EXISTS dividends;

CREATE TABLE dividends (
    id         INTEGER     PRIMARY KEY
                           UNIQUE
                           NOT NULL,
    op_type    INTEGER     NOT NULL
                           DEFAULT (2),
    timestamp  INTEGER     NOT NULL,
    ex_date    INTEGER,
    number     TEXT (32)   DEFAULT (''),
    type       INTEGER     NOT NULL,
    account_id INTEGER     REFERENCES accounts (id) ON DELETE CASCADE
                                                    ON UPDATE CASCADE
                           NOT NULL,
    asset_id   INTEGER     REFERENCES assets (id) ON DELETE RESTRICT
                                                  ON UPDATE CASCADE
                           NOT NULL,
    amount     REAL        NOT NULL
                           DEFAULT (0),
    tax        REAL        DEFAULT (0),
    note       TEXT (1024)
);


-- Table: languages
DROP TABLE IF EXISTS languages;

CREATE TABLE languages (
    id       INTEGER  PRIMARY KEY AUTOINCREMENT
                      UNIQUE
                      NOT NULL,
    language CHAR (2) UNIQUE
                      NOT NULL
);

-- Table: ledger
DROP TABLE IF EXISTS ledger;
CREATE TABLE ledger (
    id           INTEGER PRIMARY KEY
                         NOT NULL
                         UNIQUE,
    timestamp    INTEGER NOT NULL,
    op_type      INTEGER NOT NULL,
    operation_id INTEGER NOT NULL,
    book_account INTEGER NOT NULL
                         REFERENCES books (id) ON DELETE NO ACTION
                                               ON UPDATE NO ACTION,
    asset_id     INTEGER REFERENCES assets (id) ON DELETE SET NULL
                                                ON UPDATE SET NULL,
    account_id   INTEGER NOT NULL
                         REFERENCES accounts (id) ON DELETE NO ACTION
                                                  ON UPDATE NO ACTION,
    amount       REAL,
    value        REAL,
    amount_acc   REAL,
    value_acc    REAL,
    peer_id      INTEGER REFERENCES agents (id) ON DELETE NO ACTION
                                                ON UPDATE NO ACTION,
    category_id  INTEGER REFERENCES categories (id) ON DELETE NO ACTION
                                                    ON UPDATE NO ACTION,
    tag_id       INTEGER REFERENCES tags (id) ON DELETE NO ACTION
                                              ON UPDATE NO ACTION
);

-- Table: ledger_totals to keep last accumulated amount value for each transaction
DROP TABLE IF EXISTS ledger_totals;
CREATE TABLE ledger_totals (
    id           INTEGER PRIMARY KEY
                         UNIQUE
                         NOT NULL,
    op_type      INTEGER NOT NULL,
    operation_id INTEGER NOT NULL,
    timestamp    INTEGER NOT NULL,
    book_account INTEGER NOT NULL,
    asset_id     INTEGER NOT NULL,
    account_id   INTEGER NOT NULL,
    amount_acc   REAL    NOT NULL,
    value_acc    REAL    NOT NULL
);

DROP INDEX IF EXISTS ledger_totals_by_timestamp;
CREATE INDEX ledger_totals_by_timestamp ON ledger_totals (timestamp);
DROP INDEX IF EXISTS ledger_totals_by_operation_book;
CREATE INDEX ledger_totals_by_operation_book ON ledger_totals (op_type, operation_id, book_account);

-- Table: map_category
DROP TABLE IF EXISTS map_category;

CREATE TABLE map_category (
    id        INTEGER        PRIMARY KEY
                             UNIQUE
                             NOT NULL,
    value     VARCHAR (1024) NOT NULL,
    mapped_to INTEGER        NOT NULL
                             REFERENCES categories (id) ON DELETE CASCADE
                                                        ON UPDATE CASCADE
);


-- Table: map_peer
DROP TABLE IF EXISTS map_peer;

CREATE TABLE map_peer (
    id        INTEGER        PRIMARY KEY
                             UNIQUE
                             NOT NULL,
    value     VARCHAR (1024) NOT NULL,
    mapped_to INTEGER        REFERENCES agents (id) ON DELETE SET DEFAULT
                                                    ON UPDATE CASCADE
                             NOT NULL
                             DEFAULT (0)
);


-- Table: open_trades
DROP TABLE IF EXISTS open_trades;

CREATE TABLE open_trades (
    id            INTEGER PRIMARY KEY
                          UNIQUE
                          NOT NULL,
    timestamp     INTEGER NOT NULL,
    op_type       INTEGER NOT NULL,
    operation_id  INTEGER NOT NULL,
    account_id    INTEGER REFERENCES accounts (id) ON DELETE CASCADE
                                                   ON UPDATE CASCADE
                          NOT NULL,
    asset_id      INTEGER NOT NULL
                          REFERENCES assets (id) ON DELETE CASCADE
                                                 ON UPDATE CASCADE,
    price         REAL    NOT NULL,
    remaining_qty REAL    NOT NULL
);


-- Table: quotes
DROP TABLE IF EXISTS quotes;
CREATE TABLE quotes (
    id          INTEGER PRIMARY KEY UNIQUE NOT NULL,
    timestamp   INTEGER NOT NULL,
    asset_id    INTEGER REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    currency_id INTEGER REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    quote       REAL    NOT NULL DEFAULT (0)
);
CREATE UNIQUE INDEX unique_quotations ON quotes (asset_id, currency_id, timestamp);


-- Table: settings
DROP TABLE IF EXISTS settings;
CREATE TABLE settings (
    id    INTEGER   PRIMARY KEY NOT NULL UNIQUE,
    name  TEXT (32) NOT NULL UNIQUE,
    value INTEGER
);


-- Table: t_last_assets
DROP TABLE IF EXISTS t_last_assets;

CREATE TABLE t_last_assets (
    id          INTEGER   NOT NULL,
    total_value REAL
);


-- Table: t_last_dates
DROP TABLE IF EXISTS t_last_dates;

CREATE TABLE t_last_dates (
    ref_id INTEGER NOT NULL,
    timestamp  INTEGER NOT NULL
);


-- Table: t_last_quotes
DROP TABLE IF EXISTS t_last_quotes;

CREATE TABLE t_last_quotes (
    timestamp INTEGER NOT NULL,
    asset_id INTEGER NOT NULL,
    quote     REAL
);


-- Table: tags
DROP TABLE IF EXISTS tags;

CREATE TABLE tags (
    id  INTEGER   PRIMARY KEY
                  UNIQUE
                  NOT NULL,
    tag TEXT (64) NOT NULL
);


-- Table: corp_actions
DROP TABLE IF EXISTS corp_actions;

CREATE TABLE corp_actions (
    id           INTEGER     PRIMARY KEY
                             UNIQUE
                             NOT NULL,
    op_type      INTEGER     NOT NULL
                             DEFAULT (5),
    timestamp    INTEGER     NOT NULL,
    number       TEXT (32)   DEFAULT (''),
    account_id   INTEGER     REFERENCES accounts (id) ON DELETE CASCADE
                                                      ON UPDATE CASCADE
                             NOT NULL,
    type         INTEGER     NOT NULL,
    asset_id     INTEGER     REFERENCES assets (id) ON DELETE RESTRICT
                                                    ON UPDATE CASCADE
                             NOT NULL,
    qty          REAL        NOT NULL,
    asset_id_new INTEGER     REFERENCES assets (id) ON DELETE RESTRICT
                                                    ON UPDATE CASCADE
                             NOT NULL,
    qty_new      REAL        NOT NULL,
    basis_ratio  REAL        NOT NULL
                             DEFAULT (1),
    note         TEXT (1024)
);


-- Table: trades
DROP TABLE IF EXISTS trades;

CREATE TABLE trades (
    id         INTEGER     PRIMARY KEY
                           UNIQUE
                           NOT NULL,
    op_type    INTEGER     NOT NULL
                           DEFAULT (3),
    timestamp  INTEGER     NOT NULL,
    settlement INTEGER     DEFAULT (0),
    number     TEXT (32)   DEFAULT (''),
    account_id INTEGER     REFERENCES accounts (id) ON DELETE CASCADE
                                                    ON UPDATE CASCADE
                           NOT NULL,
    asset_id   INTEGER     REFERENCES assets (id) ON DELETE RESTRICT
                                                  ON UPDATE CASCADE
                           NOT NULL,
    qty        REAL        NOT NULL
                           DEFAULT (0),
    price      REAL        NOT NULL
                           DEFAULT (0),
    fee        REAL        DEFAULT (0),
    note       TEXT (1024)
);


-- Table: deals
DROP TABLE IF EXISTS deals;

CREATE TABLE deals (
    id              INTEGER PRIMARY KEY
                            UNIQUE
                            NOT NULL,
    account_id      INTEGER NOT NULL,
    asset_id        INTEGER NOT NULL,
    open_op_type    INTEGER NOT NULL,
    open_op_id      INTEGER NOT NULL,
    open_timestamp  INTEGER NOT NULL,
    open_price      REAL    NOT NULL,
    close_op_type   INTEGER NOT NULL,
    close_op_id     INTEGER NOT NULL,
    close_timestamp INTEGER NOT NULL,
    close_price     REAL    NOT NULL,
    qty             REAL    NOT NULL
);


CREATE TRIGGER on_deal_delete
         AFTER DELETE
            ON deals
    FOR EACH ROW
    WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    UPDATE open_trades
       SET remaining_qty = remaining_qty + OLD.qty
     WHERE op_type=OLD.open_op_type AND operation_id=OLD.open_op_id AND account_id=OLD.account_id AND asset_id = OLD.asset_id;
END;

-- Table: transfers
DROP TABLE IF EXISTS transfers;

CREATE TABLE transfers (
    id                   INTEGER     PRIMARY KEY
                                     UNIQUE
                                     NOT NULL,
    op_type              INTEGER     NOT NULL
                                     DEFAULT (4),
    withdrawal_timestamp INTEGER     NOT NULL,
    withdrawal_account   INTEGER     NOT NULL
                                     REFERENCES accounts (id) ON DELETE CASCADE
                                                              ON UPDATE CASCADE,
    withdrawal           REAL        NOT NULL,
    deposit_timestamp    INTEGER     NOT NULL,
    deposit_account      INTEGER     REFERENCES accounts (id) ON DELETE CASCADE
                                                              ON UPDATE CASCADE
                                     NOT NULL,
    deposit              REAL        NOT NULL,
    fee_account          INTEGER     REFERENCES accounts (id) ON DELETE CASCADE
                                                              ON UPDATE CASCADE,
    fee                  REAL,
    asset                INTEGER     REFERENCES assets (id) ON DELETE CASCADE
                                                            ON UPDATE CASCADE,
    note                 TEXT (1024)
);


-- Index: agents_by_name_idx
DROP INDEX IF EXISTS agents_by_name_idx;
CREATE INDEX agents_by_name_idx ON agents (name);



-- View: operation_sequence
DROP VIEW IF EXISTS operation_sequence;
CREATE VIEW operation_sequence AS
SELECT m.op_type, m.id, m.timestamp, m.account_id, subtype
FROM
(
    SELECT op_type, 1 AS seq, id, timestamp, account_id, 0 AS subtype FROM actions
    UNION ALL
    SELECT op_type, 2 AS seq, id, timestamp, account_id, type AS subtype FROM dividends
    UNION ALL
    SELECT op_type, 3 AS seq, id, timestamp, account_id, type AS subtype FROM corp_actions
    UNION ALL
    SELECT op_type, 4 AS seq, id, timestamp, account_id, 0 AS subtype FROM trades
    UNION ALL
    SELECT op_type, 5 AS seq, id, withdrawal_timestamp AS timestamp, withdrawal_account AS account_id, -1 AS subtype FROM transfers
    UNION ALL
    SELECT op_type, 5 AS seq, id, withdrawal_timestamp AS timestamp, fee_account AS account_id, 0 AS subtype FROM transfers WHERE NOT fee IS NULL
    UNION ALL
    SELECT op_type, 5 AS seq, id, deposit_timestamp AS timestamp, deposit_account AS account_id, 1 AS subtype FROM transfers
) AS m
ORDER BY m.timestamp, m.seq, m.subtype, m.id;


-- View: categories_tree
DROP VIEW IF EXISTS categories_tree;
CREATE VIEW categories_tree AS
WITH RECURSIVE tree (
        id,
        level,
        path
    )
    AS (
        SELECT id,
               0,
               name
          FROM categories
         WHERE pid = 0
        UNION
        SELECT categories.id,
               tree.level + 1 AS level,
               tree.path || CHAR(127) || categories.name AS path
          FROM categories
               JOIN
               tree
         WHERE categories.pid = tree.id
    )
    SELECT id,
           level,
           path
      FROM tree
     ORDER BY path;



-- View: currencies
DROP VIEW IF EXISTS currencies;
CREATE VIEW currencies AS
SELECT a.id, s.symbol
FROM assets AS a
LEFT JOIN asset_tickers AS s ON s.asset_id = a.id AND  s.active = 1
WHERE a.type_id = 1;


-- View: frontier
DROP VIEW IF EXISTS frontier;
CREATE VIEW frontier AS SELECT MAX(ledger.timestamp) AS ledger_frontier FROM ledger;


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
    FROM deals AS d
          -- Get more information about trade/corp.action that opened the deal
           LEFT JOIN trades AS ot ON ot.id=d.open_op_id AND ot.op_type=d.open_op_type
           LEFT JOIN corp_actions AS oca ON oca.id=d.open_op_id AND oca.op_type=d.open_op_type
          -- Collect value of stock that was accumulated before corporate action
           LEFT JOIN ledger AS ols ON ols.op_type=d.open_op_type AND ols.operation_id=d.open_op_id AND ols.asset_id = d.asset_id AND ols.value_acc != 0
          -- Get more information about trade/corp.action that opened the deal
           LEFT JOIN trades AS ct ON ct.id=d.close_op_id AND ct.op_type=d.close_op_type
           LEFT JOIN corp_actions AS cca ON cca.id=d.close_op_id AND cca.op_type=d.close_op_type
          -- "Decode" account and asset
           LEFT JOIN accounts AS ac ON d.account_id = ac.id
           LEFT JOIN asset_tickers AS at ON d.asset_id = at.asset_id AND ac.currency_id=at.currency_id
     -- drop cases where deal was opened and closed with corporate action
     WHERE NOT (d.open_op_type = 5 AND d.close_op_type = 5)
     ORDER BY close_timestamp, open_timestamp;


-- View: assets_ext
DROP VIEW IF EXISTS assets_ext;
CREATE VIEW assets_ext AS
    SELECT a.id,
           a.type_id,
           t.symbol,
           a.full_name,
           a.isin,
           t.currency_id,
           a.country_id,
           t.quote_source
    FROM assets a
    LEFT JOIN asset_tickers t ON a.id = t.asset_id
    WHERE t.active = 1
    ORDER BY a.id;


-- Deletion should happen on base table
DROP TRIGGER IF EXISTS on_asset_ext_delete;
CREATE TRIGGER on_asset_ext_delete
    INSTEAD OF DELETE ON assets_ext FOR EACH ROW
BEGIN
    DELETE FROM assets WHERE id = OLD.id;
END;


-- Trigger: action_details_after_delete
DROP TRIGGER IF EXISTS action_details_after_delete;
CREATE TRIGGER action_details_after_delete
      AFTER DELETE ON action_details
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= (SELECT timestamp FROM actions WHERE id = OLD.pid);
END;


-- Trigger: action_details_after_insert
DROP TRIGGER IF EXISTS action_details_after_insert;
CREATE TRIGGER action_details_after_insert
      AFTER INSERT ON action_details
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= (SELECT timestamp FROM actions WHERE id = NEW.pid);
END;

-- Trigger: action_details_after_update
DROP TRIGGER IF EXISTS action_details_after_update;
CREATE TRIGGER action_details_after_update
      AFTER UPDATE ON action_details
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger
          WHERE timestamp >= (SELECT timestamp FROM actions WHERE id = OLD.pid );
END;

-- Trigger: actions_after_delete
DROP TRIGGER IF EXISTS actions_after_delete;
CREATE TRIGGER actions_after_delete
      AFTER DELETE ON actions
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM action_details WHERE pid = OLD.id;
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp;
END;

-- Trigger: actions_after_insert
DROP TRIGGER IF EXISTS actions_after_insert;
CREATE TRIGGER actions_after_insert
      AFTER INSERT ON actions
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= NEW.timestamp;
END;

-- Trigger: actions_after_update
DROP TRIGGER IF EXISTS actions_after_update;
CREATE TRIGGER actions_after_update
      AFTER UPDATE OF timestamp, account_id, peer_id ON actions
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
END;

-- Trigger: dividends_after_delete
DROP TRIGGER IF EXISTS dividends_after_delete;
CREATE TRIGGER dividends_after_delete
      AFTER DELETE ON dividends
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp;
END;

-- Trigger: dividends_after_insert
DROP TRIGGER IF EXISTS dividends_after_insert;
CREATE TRIGGER dividends_after_insert
      AFTER INSERT ON dividends
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= NEW.timestamp;
END;

-- Trigger: dividends_after_update
DROP TRIGGER IF EXISTS dividends_after_update;
CREATE TRIGGER dividends_after_update
      AFTER UPDATE OF timestamp, account_id, asset_id, amount, tax ON dividends
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
END;

-- Trigger: trades_after_delete
DROP TRIGGER IF EXISTS trades_after_delete;
CREATE TRIGGER trades_after_delete
         AFTER DELETE ON trades
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp;
    DELETE FROM open_trades WHERE timestamp >= OLD.timestamp;
END;

DROP TRIGGER IF EXISTS trades_after_insert;
CREATE TRIGGER trades_after_insert
      AFTER INSERT ON trades
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= NEW.timestamp;
    DELETE FROM open_trades WHERE timestamp >= NEW.timestamp;
END;

DROP TRIGGER IF EXISTS trades_after_update;
CREATE TRIGGER trades_after_update
      AFTER UPDATE OF timestamp, account_id, asset_id, qty, price, fee ON trades
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
    DELETE FROM open_trades WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
END;

DROP TRIGGER IF EXISTS corp_after_delete;
CREATE TRIGGER corp_after_delete
      AFTER DELETE ON corp_actions
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp;
    DELETE FROM open_trades WHERE timestamp >= OLD.timestamp;
END;

DROP TRIGGER IF EXISTS corp_after_insert;
CREATE TRIGGER corp_after_insert
      AFTER INSERT ON corp_actions
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= NEW.timestamp;
    DELETE FROM open_trades WHERE timestamp >= NEW.timestamp;
END;

DROP TRIGGER IF EXISTS corp_after_update;
CREATE TRIGGER corp_after_update
      AFTER UPDATE OF timestamp, account_id, type, asset_id, qty, asset_id_new, qty_new ON corp_actions
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
    DELETE FROM open_trades WHERE timestamp >= OLD.timestamp  OR timestamp >= NEW.timestamp;
END;

-- Trigger: transfers_after_delete
DROP TRIGGER IF EXISTS transfers_after_delete;
CREATE TRIGGER transfers_after_delete
      AFTER DELETE ON transfers
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.withdrawal_timestamp OR timestamp >= OLD.deposit_timestamp;
END;

-- Trigger: transfers_after_insert
DROP TRIGGER IF EXISTS transfers_after_insert;
CREATE TRIGGER transfers_after_insert
      AFTER INSERT ON transfers
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= NEW.withdrawal_timestamp OR timestamp >= NEW.deposit_timestamp;
END;

-- Trigger: transfers_after_update
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

DROP TRIGGER IF EXISTS validate_account_insert;
CREATE TRIGGER validate_account_insert BEFORE INSERT ON accounts
    FOR EACH ROW
    WHEN NEW.type_id = 4 AND NEW.organization_id IS NULL
BEGIN
    SELECT RAISE(ABORT, "JAL_SQL_MSG_0001");
END;

DROP TRIGGER IF EXISTS validate_account_update;
CREATE TRIGGER validate_account_update BEFORE UPDATE ON accounts
    FOR EACH ROW
    WHEN NEW.type_id = 4 AND NEW.organization_id IS NULL
BEGIN
    SELECT RAISE(ABORT, "JAL_SQL_MSG_0001");
END;

-- Trigger to keep predefinded categories from deletion
DROP TRIGGER IF EXISTS keep_predefined_categories;
CREATE TRIGGER keep_predefined_categories BEFORE DELETE ON categories FOR EACH ROW WHEN OLD.special = 1
BEGIN
    SELECT RAISE(ABORT, "JAL_SQL_MSG_0002");
END;


-- Initialize default values for settings
INSERT INTO settings(id, name, value) VALUES (0, 'SchemaVersion', 32);
INSERT INTO settings(id, name, value) VALUES (1, 'TriggersEnabled', 1);
INSERT INTO settings(id, name, value) VALUES (2, 'BaseCurrency', 1);
INSERT INTO settings(id, name, value) VALUES (3, 'Language', 1);
INSERT INTO settings(id, name, value) VALUES (4, 'RuTaxClientSecret', 'IyvrAbKt9h/8p6a7QPh8gpkXYQ4=');
INSERT INTO settings(id, name, value) VALUES (5, 'RuTaxSessionId', '');
INSERT INTO settings(id, name, value) VALUES (6, 'RuTaxRefreshToken', '');
INSERT INTO settings(id, name, value) VALUES (7, 'RebuildDB', 0);
INSERT INTO settings(id, name, value) VALUES (8, 'WindowGeometry', '');
INSERT INTO settings(id, name, value) VALUES (9, 'WindowState', '');

-- Initialize available languages
INSERT INTO languages (id, language) VALUES (1, 'en');
INSERT INTO languages (id, language) VALUES (2, 'ru');

-- Initialize default values for books
INSERT INTO books (id, name) VALUES (1, 'Costs');
INSERT INTO books (id, name) VALUES (2, 'Incomes');
INSERT INTO books (id, name) VALUES (3, 'Money');
INSERT INTO books (id, name) VALUES (4, 'Assets');
INSERT INTO books (id, name) VALUES (5, 'Liabilities');
INSERT INTO books (id, name) VALUES (6, 'Transfers');

-- Initialize asset types values
INSERT INTO asset_types (id, name) VALUES (1, 'Money');
INSERT INTO asset_types (id, name) VALUES (2, 'Shares');
INSERT INTO asset_types (id, name) VALUES (3, 'Bonds');
INSERT INTO asset_types (id, name) VALUES (4, 'ETFs');
INSERT INTO asset_types (id, name) VALUES (5, 'Commodities');
INSERT INTO asset_types (id, name) VALUES (6, 'Derivatives');
INSERT INTO asset_types (id, name) VALUES (7, 'Forex');
INSERT INTO asset_types (id, name) VALUES (8, 'Funds');

-- Initialize some account types
INSERT INTO account_types (id, name) VALUES (1, 'Cash');
INSERT INTO account_types (id, name) VALUES (2, 'Bank accounts');
INSERT INTO account_types (id, name) VALUES (3, 'Cards');
INSERT INTO account_types (id, name) VALUES (4, 'Investment');
INSERT INTO account_types (id, name) VALUES (5, 'Deposits');
INSERT INTO account_types (id, name) VALUES (6, 'Debts');
INSERT INTO account_types (id, name) VALUES (7, 'e-Wallets');

-- Initialize sources of quotation data
INSERT INTO data_sources (id, name) VALUES (-1, 'None');
INSERT INTO data_sources (id, name) VALUES (0, 'Bank of Russia');
INSERT INTO data_sources (id, name) VALUES (1, 'MOEX');
INSERT INTO data_sources (id, name) VALUES (2, 'NYSE/Nasdaq');
INSERT INTO data_sources (id, name) VALUES (3, 'Euronext');
INSERT INTO data_sources (id, name) VALUES (4, 'TMX TSX');
INSERT INTO data_sources (id, name) VALUES (5, 'LSE');
INSERT INTO data_sources (id, name) VALUES (6, 'Frankfurt Borse');

-- Initialize predefinded categories
INSERT INTO categories (id, pid, name, often, special) VALUES (1, 0, 'Income', 0, 1);
INSERT INTO categories (id, pid, name, often, special) VALUES (2, 0, 'Spending', 0, 1);
INSERT INTO categories (id, pid, name, often, special) VALUES (3, 0, 'Profits', 0, 1);
INSERT INTO categories (id, pid, name, often, special) VALUES (4, 1, 'Starting balance', 0, 1);
INSERT INTO categories (id, pid, name, often, special) VALUES (5, 2, 'Fees', 0, 1);
INSERT INTO categories (id, pid, name, often, special) VALUES (6, 2, 'Taxes', 0, 1);
INSERT INTO categories (id, pid, name, often, special) VALUES (7, 3, 'Dividends', 0, 1);
INSERT INTO categories (id, pid, name, often, special) VALUES (8, 3, 'Interest', 0, 1);
INSERT INTO categories (id, pid, name, often, special) VALUES (9, 3, 'Results of investments', 0, 1);

-- Initialize common currencies
INSERT INTO assets (id, type_id, full_name) VALUES (1, 1, 'Российский Рубль');
INSERT INTO asset_tickers (id, asset_id, symbol, currency_id, description, quote_source, active) VALUES (1, 1, 'RUB', 1, 'Российский Рубль', -1, 1);
INSERT INTO assets (id, type_id, full_name) VALUES (2, 1, 'Доллар США');
INSERT INTO asset_tickers (id, asset_id, symbol, currency_id, description, quote_source, active) VALUES (2, 2, 'USD', 1, 'Доллар США (Банк России)', 0, 1);
INSERT INTO assets (id, type_id, full_name) VALUES (3, 1, 'Евро');
INSERT INTO asset_tickers (id, asset_id, symbol, currency_id, description, quote_source, active) VALUES (3, 3, 'EUR', 1, 'Евро (Банк России)', 0, 1);

-- Initialize some pre-defined countries
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (0, 'N/A', 'xx', '000', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (1, 'Russia', 'ru', '643', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (2, 'United States', 'us', '840', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (3, 'Ireland', 'ie', '372', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (4, 'Switzerland', 'ch', '756', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (5, 'France', 'fr', '250', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (6, 'Canada', 'ca', '124', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (7, 'Sweden', 'se', '752', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (8, 'Italy', 'it', '380', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (9, 'Spain', 'es', '724', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (10, 'Australia', 'au', '036', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (11, 'Austria', 'at', '040', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (12, 'Belgium', 'be', '056', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (13, 'United Kingdom', 'gb', '826', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (14, 'Germany', 'de', '276', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (15, 'China', 'cn', '156', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (16, 'Netherlands', 'nl', '528', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (17, 'Greece', 'gr', '300', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (18, 'Bermuda', 'bm', '060', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (19, 'Finland', 'fi', '246', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (20, 'Brazil', 'br', '076', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (21, 'Jersey', 'je', '832', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (22, 'Afghanistan', 'af', '004', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (23, 'Aland Islands', 'ax', '248', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (24, 'Albania', 'al', '008', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (25, 'Algeria', 'dz', '012', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (26, 'American Samoa', 'as', '016', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (27, 'Andorra', 'ad', '020', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (28, 'Angola', 'ao', '024', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (29, 'Anguilla', 'ai', '660', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (30, 'Antarctica', 'aq', '010', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (31, 'Antigua and Barbuda', 'ag', '028', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (32, 'Argentina', 'ar', '032', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (33, 'Armenia', 'am', '051', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (34, 'Aruba', 'aw', '533', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (35, 'Azerbaijan', 'az', '031', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (36, 'Bahamas', 'bs', '044', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (37, 'Bahrain', 'bh', '048', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (38, 'Bangladesh', 'bd', '050', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (39, 'Barbados', 'bb', '052', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (40, 'Belarus', 'by', '112', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (41, 'Belize', 'bz', '084', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (42, 'Benin', 'bj', '204', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (43, 'Bhutan', 'bt', '064', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (44, 'Bolivia', 'bo', '068', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (45, 'Bosnia and Herzegovina', 'ba', '070', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (46, 'Botswana', 'bw', '072', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (47, 'Bouvet Island', 'bv', '074', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (48, 'British Virgin Islands', 'vg', '092', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (49, 'British Indian Ocean Territory', 'io', '086', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (50, 'Brunei Darussalam', 'bn', '096', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (51, 'Bulgaria', 'bg', '100', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (52, 'Burkina Faso', 'bf', '854', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (53, 'Burundi', 'bi', '108', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (54, 'Cambodia', 'kh', '116', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (55, 'Cameroon', 'cm', '120', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (56, 'Cape Verde', 'cv', '132', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (57, 'Cayman Islands', 'ky', '136', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (58, 'Central African Republic', 'cf', '140', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (59, 'Chad', 'td', '148', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (60, 'Chile', 'cl', '152', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (61, 'Hong Kong, SAR China', 'hk', '344', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (62, 'Macao, SAR China', 'mo', '446', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (63, 'Christmas Island', 'cx', '162', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (64, 'Cocos (Keeling) Islands', 'cc', '166', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (65, 'Colombia', 'co', '170', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (66, 'Comoros', 'km', '174', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (67, 'Congo (Brazzaville)', 'cg', '178', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (68, 'Congo, (Kinshasa)', 'cd', '180', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (69, 'Cook Islands', 'ck', '184', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (70, 'Costa Rica', 'cr', '188', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (71, 'Côte d''Ivoire', 'ci', '384', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (72, 'Croatia', 'hr', '191', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (73, 'Cuba', 'cu', '192', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (74, 'Cyprus', 'cy', '196', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (75, 'Czech Republic', 'cz', '203', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (76, 'Denmark', 'dk', '208', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (77, 'Djibouti', 'dj', '262', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (78, 'Dominica', 'dm', '212', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (79, 'Dominican Republic', 'do', '214', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (80, 'Ecuador', 'ec', '218', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (81, 'Egypt', 'eg', '818', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (82, 'El Salvador', 'sv', '222', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (83, 'Equatorial Guinea', 'gq', '226', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (84, 'Eritrea', 'er', '232', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (85, 'Estonia', 'ee', '233', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (86, 'Ethiopia', 'et', '231', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (87, 'Falkland Islands (Malvinas)', 'fk', '238', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (88, 'Faroe Islands', 'fo', '234', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (89, 'Fiji', 'fj', '242', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (90, 'French Guiana', 'gf', '254', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (91, 'French Polynesia', 'pf', '258', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (92, 'French Southern Territories', 'tf', '260', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (93, 'Gabon', 'ga', '266', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (94, 'Gambia', 'gm', '270', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (95, 'Georgia', 'ge', '268', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (96, 'Ghana', 'gh', '288', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (97, 'Gibraltar', 'gi', '292', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (98, 'Greenland', 'gl', '304', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (99, 'Grenada', 'gd', '308', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (100, 'Guadeloupe', 'gp', '312', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (101, 'Guam', 'gu', '316', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (102, 'Guatemala', 'gt', '320', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (103, 'Guernsey', 'gg', '831', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (104, 'Guinea', 'gn', '324', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (105, 'Guinea-Bissau', 'gw', '624', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (106, 'Guyana', 'gy', '328', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (107, 'Haiti', 'ht', '332', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (108, 'Heard and Mcdonald Islands', 'hm', '334', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (109, 'Holy See (Vatican City State)', 'va', '336', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (110, 'Honduras', 'hn', '340', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (111, 'Hungary', 'hu', '348', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (112, 'Iceland', 'is', '352', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (113, 'India', 'in', '356', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (114, 'Indonesia', 'id', '360', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (115, 'Iran, Islamic Republic of', 'ir', '364', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (116, 'Iraq', 'iq', '368', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (117, 'Isle of Man', 'im', '833', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (118, 'Israel', 'il', '376', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (119, 'Jamaica', 'jm', '388', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (120, 'Japan', 'jp', '392', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (121, 'Jordan', 'jo', '400', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (122, 'Kazakhstan', 'kz', '398', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (123, 'Kenya', 'ke', '404', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (124, 'Kiribati', 'ki', '296', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (125, 'Korea (North)', 'kp', '408', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (126, 'Korea (South)', 'kr', '410', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (127, 'Kuwait', 'kw', '414', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (128, 'Kyrgyzstan', 'kg', '417', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (129, 'Lao PDR', 'la', '418', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (130, 'Latvia', 'lv', '428', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (131, 'Lebanon', 'lb', '422', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (132, 'Lesotho', 'ls', '426', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (133, 'Liberia', 'lr', '430', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (134, 'Libya', 'ly', '434', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (135, 'Liechtenstein', 'li', '438', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (136, 'Lithuania', 'lt', '440', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (137, 'Luxembourg', 'lu', '442', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (138, 'Macedonia, Republic of', 'mk', '807', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (139, 'Madagascar', 'mg', '450', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (140, 'Malawi', 'mw', '454', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (141, 'Malaysia', 'my', '458', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (142, 'Maldives', 'mv', '462', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (143, 'Mali', 'ml', '466', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (144, 'Malta', 'mt', '470', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (145, 'Marshall Islands', 'mh', '584', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (146, 'Martinique', 'mq', '474', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (147, 'Mauritania', 'mr', '478', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (148, 'Mauritius', 'mu', '480', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (149, 'Mayotte', 'yt', '175', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (150, 'Mexico', 'mx', '484', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (151, 'Micronesia, Federated States of', 'fm', '583', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (152, 'Moldova', 'md', '498', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (153, 'Monaco', 'mc', '492', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (154, 'Mongolia', 'mn', '496', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (155, 'Montenegro', 'me', '499', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (156, 'Montserrat', 'ms', '500', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (157, 'Morocco', 'ma', '504', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (158, 'Mozambique', 'mz', '508', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (159, 'Myanmar', 'mm', '104', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (160, 'Namibia', 'na', '516', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (161, 'Nauru', 'nr', '520', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (162, 'Nepal', 'np', '524', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (163, 'Netherlands Antilles', 'an', '530', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (164, 'New Caledonia', 'nc', '540', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (165, 'New Zealand', 'nz', '554', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (166, 'Nicaragua', 'ni', '558', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (167, 'Niger', 'ne', '562', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (168, 'Nigeria', 'ng', '566', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (169, 'Niue', 'nu', '570', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (170, 'Norfolk Island', 'nf', '574', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (171, 'Northern Mariana Islands', 'mp', '580', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (172, 'Norway', 'no', '578', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (173, 'Oman', 'om', '512', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (174, 'Pakistan', 'pk', '586', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (175, 'Palau', 'pw', '585', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (176, 'Palestinian Territory', 'ps', '275', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (177, 'Panama', 'pa', '591', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (178, 'Papua New Guinea', 'pg', '598', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (179, 'Paraguay', 'py', '600', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (180, 'Peru', 'pe', '604', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (181, 'Philippines', 'ph', '608', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (182, 'Pitcairn', 'pn', '612', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (183, 'Poland', 'pl', '616', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (184, 'Portugal', 'pt', '620', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (185, 'Puerto Rico', 'pr', '630', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (186, 'Qatar', 'qa', '634', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (187, 'Réunion', 're', '638', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (188, 'Romania', 'ro', '642', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (189, 'Rwanda', 'rw', '646', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (190, 'Saint-Barthélemy', 'bl', '652', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (191, 'Saint Helena', 'sh', '654', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (192, 'Saint Kitts and Nevis', 'kn', '659', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (193, 'Saint Lucia', 'lc', '662', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (194, 'Saint-Martin (French part)', 'mf', '663', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (195, 'Saint Pierre and Miquelon', 'pm', '666', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (196, 'Saint Vincent and Grenadines', 'vc', '670', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (197, 'Samoa', 'ws', '882', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (198, 'San Marino', 'sm', '674', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (199, 'Sao Tome and Principe', 'st', '678', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (200, 'Saudi Arabia', 'sa', '682', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (201, 'Senegal', 'sn', '686', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (202, 'Serbia', 'rs', '688', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (203, 'Seychelles', 'sc', '690', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (204, 'Sierra Leone', 'sl', '694', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (205, 'Singapore', 'sg', '702', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (206, 'Slovakia', 'sk', '703', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (207, 'Slovenia', 'si', '705', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (208, 'Solomon Islands', 'sb', '090', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (209, 'Somalia', 'so', '706', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (210, 'South Africa', 'za', '710', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (211, 'South Georgia and the South Sandwich Islands', 'gs', '239', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (212, 'South Sudan', 'ss', '728', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (213, 'Sri Lanka', 'lk', '144', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (214, 'Sudan', 'sd', '736', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (215, 'Suriname', 'sr', '740', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (216, 'Svalbard and Jan Mayen Islands', 'sj', '744', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (217, 'Swaziland', 'sz', '748', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (218, 'Syrian Arab Republic (Syria)', 'sy', '760', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (219, 'Taiwan, Republic of China', 'tw', '158', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (220, 'Tajikistan', 'tj', '762', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (221, 'Tanzania, United Republic of', 'tz', '834', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (222, 'Thailand', 'th', '764', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (223, 'Timor-Leste', 'tl', '626', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (224, 'Togo', 'tg', '768', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (225, 'Tokelau', 'tk', '772', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (226, 'Tonga', 'to', '776', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (227, 'Trinidad and Tobago', 'tt', '780', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (228, 'Tunisia', 'tn', '788', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (229, 'Turkey', 'tr', '792', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (230, 'Turkmenistan', 'tm', '795', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (231, 'Turks and Caicos Islands', 'tc', '796', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (232, 'Tuvalu', 'tv', '798', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (233, 'Uganda', 'ug', '800', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (234, 'Ukraine', 'ua', '804', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (235, 'United Arab Emirates', 'ae', '784', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (236, 'US Minor Outlying Islands', 'um', '581', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (237, 'Uruguay', 'uy', '858', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (238, 'Uzbekistan', 'uz', '860', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (239, 'Vanuatu', 'vu', '548', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (240, 'Venezuela (Bolivarian Republic)', 've', '862', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (241, 'Viet Nam', 'vn', '704', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (242, 'Virgin Islands, US', 'vi', '850', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (243, 'Wallis and Futuna Islands', 'wf', '876', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (244, 'Western Sahara', 'eh', '732', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (245, 'Yemen', 'ye', '887', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (246, 'Zambia', 'zm', '894', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (247, 'Zimbabwe', 'zw', '716', 0);

-- Initialize rate for base currency
INSERT INTO quotes (id, timestamp, asset_id, currency_id, quote) VALUES (1, 946684800, 1, 1, 1.0);

COMMIT TRANSACTION;
PRAGMA foreign_keys = on;
