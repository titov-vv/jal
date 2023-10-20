PRAGMA foreign_keys = off;
BEGIN TRANSACTION;

-- Table: accounts
DROP TABLE IF EXISTS accounts;

CREATE TABLE accounts (
    id              INTEGER   PRIMARY KEY UNIQUE NOT NULL,
    type_id         INTEGER   NOT NULL,
    name            TEXT (64) NOT NULL UNIQUE,
    currency_id     INTEGER   REFERENCES assets (id) ON DELETE RESTRICT ON UPDATE CASCADE NOT NULL,
    active          INTEGER   DEFAULT (1) NOT NULL ON CONFLICT REPLACE,
    number          TEXT (32),
    reconciled_on   INTEGER   DEFAULT (0) NOT NULL ON CONFLICT REPLACE,
    organization_id INTEGER   REFERENCES agents (id) ON DELETE SET NULL ON UPDATE CASCADE,
    country_id      INTEGER   REFERENCES countries (id) ON DELETE CASCADE ON UPDATE CASCADE DEFAULT (0) NOT NULL,
    precision       INTEGER   NOT NULL DEFAULT (2)
);


-- Table: action_details
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


-- Table: actions
DROP TABLE IF EXISTS actions;
CREATE TABLE actions (
    id              INTEGER PRIMARY KEY UNIQUE NOT NULL,
    op_type         INTEGER NOT NULL DEFAULT (1),
    timestamp       INTEGER NOT NULL,
    account_id      INTEGER REFERENCES accounts (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    peer_id         INTEGER REFERENCES agents (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    alt_currency_id INTEGER REFERENCES assets (id) ON DELETE RESTRICT ON UPDATE CASCADE,
    note            TEXT
);

-- Table: assets
DROP TABLE IF EXISTS assets;
CREATE TABLE assets (
    id         INTEGER    PRIMARY KEY UNIQUE NOT NULL,
    type_id    INTEGER    NOT NULL,
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
    currency_id  INTEGER REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE,
    description  TEXT    NOT NULL DEFAULT (''),
    quote_source INTEGER DEFAULT ( -1) NOT NULL,
    active       INTEGER NOT NULL DEFAULT (1)
);
-- Index to prevent duplicates
DROP INDEX IF EXISTS uniq_symbols;
CREATE UNIQUE INDEX uniq_symbols ON asset_tickers (asset_id, symbol COLLATE NOCASE, currency_id);
-- Create triggers to keep currency_id NULL for currencies and NOT NULL for other assets
DROP TRIGGER IF EXISTS validate_ticker_currency_insert;
CREATE TRIGGER validate_ticker_currency_insert
    BEFORE INSERT ON asset_tickers
    FOR EACH ROW
    WHEN IIF(NEW.currency_id IS NULL, 0, 1) = (SELECT IIF(type_id=1, 1, 0) FROM assets WHERE id=NEW.asset_id)
BEGIN
    SELECT RAISE(ABORT, "JAL_SQL_MSG_0003");
END;

DROP TRIGGER IF EXISTS validate_ticker_currency_update;
CREATE TRIGGER validate_ticker_currency_update
    AFTER UPDATE OF currency_id ON asset_tickers
    FOR EACH ROW
    WHEN IIF(NEW.currency_id IS NULL, 0, 1) = (SELECT IIF(type_id=1, 1, 0) FROM assets WHERE id=NEW.asset_id)
BEGIN
    SELECT RAISE(ABORT, "JAL_SQL_MSG_0003");
END;

-- Table to keep extra asset data
DROP TABLE IF EXISTS asset_data;
CREATE TABLE asset_data (
    id       INTEGER PRIMARY KEY UNIQUE NOT NULL,
    asset_id INTEGER NOT NULL REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE,
    datatype INTEGER NOT NULL,
    value    TEXT    NOT NULL
);

-- Table to keep history of base currency changes
DROP TABLE IF EXISTS base_currency;
CREATE TABLE base_currency (
    id              INTEGER PRIMARY KEY UNIQUE NOT NULL,
    since_timestamp INTEGER NOT NULL UNIQUE,
    currency_id     INTEGER NOT NULL REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE
);

DROP INDEX IF EXISTS asset_data_uniqueness;
CREATE UNIQUE INDEX asset_data_uniqueness ON asset_data ( asset_id, datatype);

-- Table: agents
DROP TABLE IF EXISTS agents;
CREATE TABLE agents (
    id       INTEGER    PRIMARY KEY UNIQUE NOT NULL,
    pid      INTEGER    NOT NULL DEFAULT (0),
    name     TEXT (64)  UNIQUE NOT NULL,
    location TEXT (128) 
);

-- Table: categories
DROP TABLE IF EXISTS categories;
CREATE TABLE categories (
    id      INTEGER   PRIMARY KEY UNIQUE NOT NULL,
    pid     INTEGER   NOT NULL DEFAULT (0),
    name    TEXT (64) UNIQUE NOT NULL,
    often   INTEGER,
    special INTEGER
);

-- Create new table with list of countries
DROP TABLE IF EXISTS countries;
CREATE TABLE countries (
    id           INTEGER      PRIMARY KEY UNIQUE NOT NULL,
    code         CHAR (3)     UNIQUE NOT NULL,
    iso_code     CHAR (4)     UNIQUE NOT NULL
);

CREATE TABLE country_names (
    id          INTEGER PRIMARY KEY UNIQUE NOT NULL,
    country_id  INTEGER REFERENCES countries (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    language_id INTEGER REFERENCES languages (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    name        TEXT    NOT NULL
);
CREATE UNIQUE INDEX country_name_by_language ON country_names (country_id, language_id);

-- Table: dividends
DROP TABLE IF EXISTS dividends;
CREATE TABLE dividends (
    id         INTEGER PRIMARY KEY UNIQUE NOT NULL,
    op_type    INTEGER NOT NULL DEFAULT (2),
    timestamp  INTEGER NOT NULL,
    ex_date    INTEGER NOT NULL DEFAULT (0),
    number     TEXT    NOT NULL DEFAULT (''),
    type       INTEGER NOT NULL,
    account_id INTEGER REFERENCES accounts (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    asset_id   INTEGER REFERENCES assets (id) ON DELETE RESTRICT ON UPDATE CASCADE NOT NULL,
    amount     TEXT    NOT NULL DEFAULT ('0'),
    tax        TEXT    NOT NULL DEFAULT ('0'),
    note       TEXT
);


-- Table: languages
DROP TABLE IF EXISTS languages;
CREATE TABLE languages (
    id       INTEGER  PRIMARY KEY AUTOINCREMENT UNIQUE NOT NULL,
    language CHAR (2) UNIQUE NOT NULL
);

-- Table: ledger
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

-- Table: ledger_totals to keep last accumulated amount value for each transaction
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

-- Table: map_category
DROP TABLE IF EXISTS map_category;
CREATE TABLE map_category (
    id        INTEGER        PRIMARY KEY UNIQUE NOT NULL,
    value     VARCHAR (1024) NOT NULL,
    mapped_to INTEGER        NOT NULL REFERENCES categories (id) ON DELETE CASCADE ON UPDATE CASCADE
);


-- Table: map_peer
DROP TABLE IF EXISTS map_peer;
CREATE TABLE map_peer (
    id        INTEGER        PRIMARY KEY UNIQUE NOT NULL,
    value     VARCHAR (1024) NOT NULL,
    mapped_to INTEGER        REFERENCES agents (id) ON DELETE SET DEFAULT ON UPDATE CASCADE NOT NULL DEFAULT (0)
);


-- Table: open_trades
DROP TABLE IF EXISTS trades_opened;
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


-- Table: quotes
DROP TABLE IF EXISTS quotes;
CREATE TABLE quotes (
    id          INTEGER PRIMARY KEY UNIQUE NOT NULL,
    timestamp   INTEGER NOT NULL,
    asset_id    INTEGER REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    currency_id INTEGER REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    quote       TEXT    NOT NULL DEFAULT ('0')
);
CREATE UNIQUE INDEX unique_quotations ON quotes (asset_id, currency_id, timestamp);

-- Table: settings
DROP TABLE IF EXISTS settings;
CREATE TABLE settings (
    id    INTEGER   PRIMARY KEY NOT NULL UNIQUE,
    name  TEXT (32) NOT NULL UNIQUE,
    value INTEGER
);

-- Table: tags
DROP TABLE IF EXISTS tags;
CREATE TABLE tags (
    id  INTEGER   PRIMARY KEY UNIQUE NOT NULL,
    pid INTEGER   NOT NULL DEFAULT (0),
    tag TEXT (64) NOT NULL UNIQUE
);

-- Table to store about corporate actions that transform one asset into another
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

-- Table to store information about assets that appear after corporate action
DROP TABLE IF EXISTS action_results;
CREATE TABLE action_results (
    id          INTEGER PRIMARY KEY UNIQUE NOT NULL,
    action_id   INTEGER NOT NULL REFERENCES asset_actions (id) ON DELETE CASCADE ON UPDATE CASCADE,
    asset_id    INTEGER REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    qty         TEXT    NOT NULL,
    value_share TEXT    NOT NULL
);

-- Table: trades
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

-- Table for closed deals storage
DROP TABLE IF EXISTS trades_closed;
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

DROP TRIGGER IF EXISTS on_closed_trade_delete;
CREATE TRIGGER on_closed_trade_delete
    AFTER DELETE ON trades_closed
    FOR EACH ROW
    WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    UPDATE trades_opened
    SET remaining_qty = remaining_qty + OLD.qty
    WHERE op_type=OLD.open_op_type AND operation_id=OLD.open_op_id AND account_id=OLD.account_id AND asset_id = OLD.asset_id;
END;

-- Table: transfers
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
    number               TEXT        NOT NULL DEFAULT (''),
    asset                INTEGER     REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE,
    note                 TEXT
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
    SELECT op_type, 3 AS seq, id, timestamp, account_id, type AS subtype FROM asset_actions
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


-- View: assets_ext
DROP VIEW IF EXISTS assets_ext;
CREATE VIEW assets_ext AS
    SELECT a.id, a.type_id, t.symbol, a.full_name, a.isin, t.currency_id, a.country_id, t.quote_source
    FROM assets a
    LEFT JOIN asset_tickers t ON a.id = t.asset_id
    WHERE t.active = 1
    ORDER BY a.id;


DROP VIEW IF EXISTS countries_ext;
CREATE VIEW countries_ext AS
    SELECT c.id, c.code, c.iso_code, n.name
    FROM countries AS c
    LEFT JOIN country_names AS n ON n.country_id = c.id AND n.language_id = (SELECT value FROM settings WHERE id = 3);


--------------------------------------------------------------------------------
-- TRIGGERS

-- Deletion should happen on base table
DROP TRIGGER IF EXISTS on_asset_ext_delete;
CREATE TRIGGER on_asset_ext_delete
    INSTEAD OF DELETE ON assets_ext FOR EACH ROW WHEN (SELECT value FROM settings WHERE id = 1)
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
    DELETE FROM ledger WHERE timestamp >= (SELECT timestamp FROM actions WHERE id = OLD.pid );
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
INSERT INTO settings(id, name, value) VALUES (0, 'SchemaVersion', 50);
INSERT INTO settings(id, name, value) VALUES (1, 'TriggersEnabled', 1);
-- INSERT INTO settings(id, name, value) VALUES (2, 'BaseCurrency', 1); -- Deprecated and ID shouldn't be re-used
INSERT INTO settings(id, name, value) VALUES (3, 'Language', 1);
INSERT INTO settings(id, name, value) VALUES (4, 'RuTaxClientSecret', 'IyvrAbKt9h/8p6a7QPh8gpkXYQ4=');
INSERT INTO settings(id, name, value) VALUES (5, 'RuTaxSessionId', '');
INSERT INTO settings(id, name, value) VALUES (6, 'RuTaxRefreshToken', '');
INSERT INTO settings(id, name, value) VALUES (7, 'RebuildDB', 0);
INSERT INTO settings(id, name, value) VALUES (8, 'WindowGeometry', '');
INSERT INTO settings(id, name, value) VALUES (9, 'WindowState', '');
INSERT INTO settings(id, name, value) VALUES (10, 'MessageOnce', '');
INSERT INTO settings(id, name, value) VALUES (11, 'RecentFolder_Statement', '.');
INSERT INTO settings(id, name, value) VALUES (12, 'RecentFolder_Report', '.');
INSERT INTO settings(id, name, value) VALUES (13, 'CleanDB', 0);
INSERT INTO settings(id, name, value) VALUES (14, 'EuLidlClientSecret', 'TGlkbFBsdXNOYXRpdmVDbGllbnQ6c2VjcmV0');
INSERT INTO settings(id, name, value) VALUES (15, 'EuLidlAccessToken', '');
INSERT INTO settings(id, name, value) VALUES (16, 'EuLidlRefreshToken', '');
INSERT INTO settings(id, name, value) VALUES (17, 'PtPingoDoceAccessToken', '');
INSERT INTO settings(id, name, value) VALUES (18, 'PtPingoDoceRefreshToken', '');
INSERT INTO settings(id, name, value) VALUES (19, 'PtPingoDoceUserProfile', '{}');

-- Initialize available languages
INSERT INTO languages (id, language) VALUES (1, 'en');
INSERT INTO languages (id, language) VALUES (2, 'ru');

-- Initialize predefined categories
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
INSERT INTO asset_tickers (id, asset_id, symbol, description, quote_source, active) VALUES (1, 1, 'RUB', 'Российский Рубль', -1, 1);
INSERT INTO assets (id, type_id, full_name) VALUES (2, 1, 'Доллар США');
INSERT INTO asset_tickers (id, asset_id, symbol, description, quote_source, active) VALUES (2, 2, 'USD', 'Доллар США', 0, 1);
INSERT INTO assets (id, type_id, full_name) VALUES (3, 1, 'Евро');
INSERT INTO asset_tickers (id, asset_id, symbol, description, quote_source, active) VALUES (3, 3, 'EUR', 'Евро', 0, 1);

-- Initialize countries
INSERT INTO countries (id, code, iso_code) VALUES (0, 'xx', '000');
INSERT INTO countries (id, code, iso_code) VALUES (1, 'ru', '643');
INSERT INTO countries (id, code, iso_code) VALUES (2, 'us', '840');
INSERT INTO countries (id, code, iso_code) VALUES (3, 'ie', '372');
INSERT INTO countries (id, code, iso_code) VALUES (4, 'ch', '756');
INSERT INTO countries (id, code, iso_code) VALUES (5, 'fr', '250');
INSERT INTO countries (id, code, iso_code) VALUES (6, 'ca', '124');
INSERT INTO countries (id, code, iso_code) VALUES (7, 'se', '752');
INSERT INTO countries (id, code, iso_code) VALUES (8, 'it', '380');
INSERT INTO countries (id, code, iso_code) VALUES (9, 'es', '724');
INSERT INTO countries (id, code, iso_code) VALUES (10, 'au', '036');
INSERT INTO countries (id, code, iso_code) VALUES (11, 'at', '040');
INSERT INTO countries (id, code, iso_code) VALUES (12, 'be', '056');
INSERT INTO countries (id, code, iso_code) VALUES (13, 'gb', '826');
INSERT INTO countries (id, code, iso_code) VALUES (14, 'de', '276');
INSERT INTO countries (id, code, iso_code) VALUES (15, 'cn', '156');
INSERT INTO countries (id, code, iso_code) VALUES (16, 'nl', '528');
INSERT INTO countries (id, code, iso_code) VALUES (17, 'gr', '300');
INSERT INTO countries (id, code, iso_code) VALUES (18, 'bm', '060');
INSERT INTO countries (id, code, iso_code) VALUES (19, 'fi', '246');
INSERT INTO countries (id, code, iso_code) VALUES (20, 'br', '076');
INSERT INTO countries (id, code, iso_code) VALUES (21, 'je', '832');
INSERT INTO countries (id, code, iso_code) VALUES (22, 'af', '004');
INSERT INTO countries (id, code, iso_code) VALUES (23, 'ax', '248');
INSERT INTO countries (id, code, iso_code) VALUES (24, 'al', '008');
INSERT INTO countries (id, code, iso_code) VALUES (25, 'dz', '012');
INSERT INTO countries (id, code, iso_code) VALUES (26, 'as', '016');
INSERT INTO countries (id, code, iso_code) VALUES (27, 'ad', '020');
INSERT INTO countries (id, code, iso_code) VALUES (28, 'ao', '024');
INSERT INTO countries (id, code, iso_code) VALUES (29, 'ai', '660');
INSERT INTO countries (id, code, iso_code) VALUES (30, 'aq', '010');
INSERT INTO countries (id, code, iso_code) VALUES (31, 'ag', '028');
INSERT INTO countries (id, code, iso_code) VALUES (32, 'ar', '032');
INSERT INTO countries (id, code, iso_code) VALUES (33, 'am', '051');
INSERT INTO countries (id, code, iso_code) VALUES (34, 'aw', '533');
INSERT INTO countries (id, code, iso_code) VALUES (35, 'az', '031');
INSERT INTO countries (id, code, iso_code) VALUES (36, 'bs', '044');
INSERT INTO countries (id, code, iso_code) VALUES (37, 'bh', '048');
INSERT INTO countries (id, code, iso_code) VALUES (38, 'bd', '050');
INSERT INTO countries (id, code, iso_code) VALUES (39, 'bb', '052');
INSERT INTO countries (id, code, iso_code) VALUES (40, 'by', '112');
INSERT INTO countries (id, code, iso_code) VALUES (41, 'bz', '084');
INSERT INTO countries (id, code, iso_code) VALUES (42, 'bj', '204');
INSERT INTO countries (id, code, iso_code) VALUES (43, 'bt', '064');
INSERT INTO countries (id, code, iso_code) VALUES (44, 'bo', '068');
INSERT INTO countries (id, code, iso_code) VALUES (45, 'ba', '070');
INSERT INTO countries (id, code, iso_code) VALUES (46, 'bw', '072');
INSERT INTO countries (id, code, iso_code) VALUES (47, 'bv', '074');
INSERT INTO countries (id, code, iso_code) VALUES (48, 'vg', '092');
INSERT INTO countries (id, code, iso_code) VALUES (49, 'io', '086');
INSERT INTO countries (id, code, iso_code) VALUES (50, 'bn', '096');
INSERT INTO countries (id, code, iso_code) VALUES (51, 'bg', '100');
INSERT INTO countries (id, code, iso_code) VALUES (52, 'bf', '854');
INSERT INTO countries (id, code, iso_code) VALUES (53, 'bi', '108');
INSERT INTO countries (id, code, iso_code) VALUES (54, 'kh', '116');
INSERT INTO countries (id, code, iso_code) VALUES (55, 'cm', '120');
INSERT INTO countries (id, code, iso_code) VALUES (56, 'cv', '132');
INSERT INTO countries (id, code, iso_code) VALUES (57, 'ky', '136');
INSERT INTO countries (id, code, iso_code) VALUES (58, 'cf', '140');
INSERT INTO countries (id, code, iso_code) VALUES (59, 'td', '148');
INSERT INTO countries (id, code, iso_code) VALUES (60, 'cl', '152');
INSERT INTO countries (id, code, iso_code) VALUES (61, 'hk', '344');
INSERT INTO countries (id, code, iso_code) VALUES (62, 'mo', '446');
INSERT INTO countries (id, code, iso_code) VALUES (63, 'cx', '162');
INSERT INTO countries (id, code, iso_code) VALUES (64, 'cc', '166');
INSERT INTO countries (id, code, iso_code) VALUES (65, 'co', '170');
INSERT INTO countries (id, code, iso_code) VALUES (66, 'km', '174');
INSERT INTO countries (id, code, iso_code) VALUES (67, 'cg', '178');
INSERT INTO countries (id, code, iso_code) VALUES (68, 'cd', '180');
INSERT INTO countries (id, code, iso_code) VALUES (69, 'ck', '184');
INSERT INTO countries (id, code, iso_code) VALUES (70, 'cr', '188');
INSERT INTO countries (id, code, iso_code) VALUES (71, 'ci', '384');
INSERT INTO countries (id, code, iso_code) VALUES (72, 'hr', '191');
INSERT INTO countries (id, code, iso_code) VALUES (73, 'cu', '192');
INSERT INTO countries (id, code, iso_code) VALUES (74, 'cy', '196');
INSERT INTO countries (id, code, iso_code) VALUES (75, 'cz', '203');
INSERT INTO countries (id, code, iso_code) VALUES (76, 'dk', '208');
INSERT INTO countries (id, code, iso_code) VALUES (77, 'dj', '262');
INSERT INTO countries (id, code, iso_code) VALUES (78, 'dm', '212');
INSERT INTO countries (id, code, iso_code) VALUES (79, 'do', '214');
INSERT INTO countries (id, code, iso_code) VALUES (80, 'ec', '218');
INSERT INTO countries (id, code, iso_code) VALUES (81, 'eg', '818');
INSERT INTO countries (id, code, iso_code) VALUES (82, 'sv', '222');
INSERT INTO countries (id, code, iso_code) VALUES (83, 'gq', '226');
INSERT INTO countries (id, code, iso_code) VALUES (84, 'er', '232');
INSERT INTO countries (id, code, iso_code) VALUES (85, 'ee', '233');
INSERT INTO countries (id, code, iso_code) VALUES (86, 'et', '231');
INSERT INTO countries (id, code, iso_code) VALUES (87, 'fk', '238');
INSERT INTO countries (id, code, iso_code) VALUES (88, 'fo', '234');
INSERT INTO countries (id, code, iso_code) VALUES (89, 'fj', '242');
INSERT INTO countries (id, code, iso_code) VALUES (90, 'gf', '254');
INSERT INTO countries (id, code, iso_code) VALUES (91, 'pf', '258');
INSERT INTO countries (id, code, iso_code) VALUES (92, 'tf', '260');
INSERT INTO countries (id, code, iso_code) VALUES (93, 'ga', '266');
INSERT INTO countries (id, code, iso_code) VALUES (94, 'gm', '270');
INSERT INTO countries (id, code, iso_code) VALUES (95, 'ge', '268');
INSERT INTO countries (id, code, iso_code) VALUES (96, 'gh', '288');
INSERT INTO countries (id, code, iso_code) VALUES (97, 'gi', '292');
INSERT INTO countries (id, code, iso_code) VALUES (98, 'gl', '304');
INSERT INTO countries (id, code, iso_code) VALUES (99, 'gd', '308');
INSERT INTO countries (id, code, iso_code) VALUES (100, 'gp', '312');
INSERT INTO countries (id, code, iso_code) VALUES (101, 'gu', '316');
INSERT INTO countries (id, code, iso_code) VALUES (102, 'gt', '320');
INSERT INTO countries (id, code, iso_code) VALUES (103, 'gg', '831');
INSERT INTO countries (id, code, iso_code) VALUES (104, 'gn', '324');
INSERT INTO countries (id, code, iso_code) VALUES (105, 'gw', '624');
INSERT INTO countries (id, code, iso_code) VALUES (106, 'gy', '328');
INSERT INTO countries (id, code, iso_code) VALUES (107, 'ht', '332');
INSERT INTO countries (id, code, iso_code) VALUES (108, 'hm', '334');
INSERT INTO countries (id, code, iso_code) VALUES (109, 'va', '336');
INSERT INTO countries (id, code, iso_code) VALUES (110, 'hn', '340');
INSERT INTO countries (id, code, iso_code) VALUES (111, 'hu', '348');
INSERT INTO countries (id, code, iso_code) VALUES (112, 'is', '352');
INSERT INTO countries (id, code, iso_code) VALUES (113, 'in', '356');
INSERT INTO countries (id, code, iso_code) VALUES (114, 'id', '360');
INSERT INTO countries (id, code, iso_code) VALUES (115, 'ir', '364');
INSERT INTO countries (id, code, iso_code) VALUES (116, 'iq', '368');
INSERT INTO countries (id, code, iso_code) VALUES (117, 'im', '833');
INSERT INTO countries (id, code, iso_code) VALUES (118, 'il', '376');
INSERT INTO countries (id, code, iso_code) VALUES (119, 'jm', '388');
INSERT INTO countries (id, code, iso_code) VALUES (120, 'jp', '392');
INSERT INTO countries (id, code, iso_code) VALUES (121, 'jo', '400');
INSERT INTO countries (id, code, iso_code) VALUES (122, 'kz', '398');
INSERT INTO countries (id, code, iso_code) VALUES (123, 'ke', '404');
INSERT INTO countries (id, code, iso_code) VALUES (124, 'ki', '296');
INSERT INTO countries (id, code, iso_code) VALUES (125, 'kp', '408');
INSERT INTO countries (id, code, iso_code) VALUES (126, 'kr', '410');
INSERT INTO countries (id, code, iso_code) VALUES (127, 'kw', '414');
INSERT INTO countries (id, code, iso_code) VALUES (128, 'kg', '417');
INSERT INTO countries (id, code, iso_code) VALUES (129, 'la', '418');
INSERT INTO countries (id, code, iso_code) VALUES (130, 'lv', '428');
INSERT INTO countries (id, code, iso_code) VALUES (131, 'lb', '422');
INSERT INTO countries (id, code, iso_code) VALUES (132, 'ls', '426');
INSERT INTO countries (id, code, iso_code) VALUES (133, 'lr', '430');
INSERT INTO countries (id, code, iso_code) VALUES (134, 'ly', '434');
INSERT INTO countries (id, code, iso_code) VALUES (135, 'li', '438');
INSERT INTO countries (id, code, iso_code) VALUES (136, 'lt', '440');
INSERT INTO countries (id, code, iso_code) VALUES (137, 'lu', '442');
INSERT INTO countries (id, code, iso_code) VALUES (138, 'mk', '807');
INSERT INTO countries (id, code, iso_code) VALUES (139, 'mg', '450');
INSERT INTO countries (id, code, iso_code) VALUES (140, 'mw', '454');
INSERT INTO countries (id, code, iso_code) VALUES (141, 'my', '458');
INSERT INTO countries (id, code, iso_code) VALUES (142, 'mv', '462');
INSERT INTO countries (id, code, iso_code) VALUES (143, 'ml', '466');
INSERT INTO countries (id, code, iso_code) VALUES (144, 'mt', '470');
INSERT INTO countries (id, code, iso_code) VALUES (145, 'mh', '584');
INSERT INTO countries (id, code, iso_code) VALUES (146, 'mq', '474');
INSERT INTO countries (id, code, iso_code) VALUES (147, 'mr', '478');
INSERT INTO countries (id, code, iso_code) VALUES (148, 'mu', '480');
INSERT INTO countries (id, code, iso_code) VALUES (149, 'yt', '175');
INSERT INTO countries (id, code, iso_code) VALUES (150, 'mx', '484');
INSERT INTO countries (id, code, iso_code) VALUES (151, 'fm', '583');
INSERT INTO countries (id, code, iso_code) VALUES (152, 'md', '498');
INSERT INTO countries (id, code, iso_code) VALUES (153, 'mc', '492');
INSERT INTO countries (id, code, iso_code) VALUES (154, 'mn', '496');
INSERT INTO countries (id, code, iso_code) VALUES (155, 'me', '499');
INSERT INTO countries (id, code, iso_code) VALUES (156, 'ms', '500');
INSERT INTO countries (id, code, iso_code) VALUES (157, 'ma', '504');
INSERT INTO countries (id, code, iso_code) VALUES (158, 'mz', '508');
INSERT INTO countries (id, code, iso_code) VALUES (159, 'mm', '104');
INSERT INTO countries (id, code, iso_code) VALUES (160, 'na', '516');
INSERT INTO countries (id, code, iso_code) VALUES (161, 'nr', '520');
INSERT INTO countries (id, code, iso_code) VALUES (162, 'np', '524');
INSERT INTO countries (id, code, iso_code) VALUES (163, 'an', '530');
INSERT INTO countries (id, code, iso_code) VALUES (164, 'nc', '540');
INSERT INTO countries (id, code, iso_code) VALUES (165, 'nz', '554');
INSERT INTO countries (id, code, iso_code) VALUES (166, 'ni', '558');
INSERT INTO countries (id, code, iso_code) VALUES (167, 'ne', '562');
INSERT INTO countries (id, code, iso_code) VALUES (168, 'ng', '566');
INSERT INTO countries (id, code, iso_code) VALUES (169, 'nu', '570');
INSERT INTO countries (id, code, iso_code) VALUES (170, 'nf', '574');
INSERT INTO countries (id, code, iso_code) VALUES (171, 'mp', '580');
INSERT INTO countries (id, code, iso_code) VALUES (172, 'no', '578');
INSERT INTO countries (id, code, iso_code) VALUES (173, 'om', '512');
INSERT INTO countries (id, code, iso_code) VALUES (174, 'pk', '586');
INSERT INTO countries (id, code, iso_code) VALUES (175, 'pw', '585');
INSERT INTO countries (id, code, iso_code) VALUES (176, 'ps', '275');
INSERT INTO countries (id, code, iso_code) VALUES (177, 'pa', '591');
INSERT INTO countries (id, code, iso_code) VALUES (178, 'pg', '598');
INSERT INTO countries (id, code, iso_code) VALUES (179, 'py', '600');
INSERT INTO countries (id, code, iso_code) VALUES (180, 'pe', '604');
INSERT INTO countries (id, code, iso_code) VALUES (181, 'ph', '608');
INSERT INTO countries (id, code, iso_code) VALUES (182, 'pn', '612');
INSERT INTO countries (id, code, iso_code) VALUES (183, 'pl', '616');
INSERT INTO countries (id, code, iso_code) VALUES (184, 'pt', '620');
INSERT INTO countries (id, code, iso_code) VALUES (185, 'pr', '630');
INSERT INTO countries (id, code, iso_code) VALUES (186, 'qa', '634');
INSERT INTO countries (id, code, iso_code) VALUES (187, 're', '638');
INSERT INTO countries (id, code, iso_code) VALUES (188, 'ro', '642');
INSERT INTO countries (id, code, iso_code) VALUES (189, 'rw', '646');
INSERT INTO countries (id, code, iso_code) VALUES (190, 'bl', '652');
INSERT INTO countries (id, code, iso_code) VALUES (191, 'sh', '654');
INSERT INTO countries (id, code, iso_code) VALUES (192, 'kn', '659');
INSERT INTO countries (id, code, iso_code) VALUES (193, 'lc', '662');
INSERT INTO countries (id, code, iso_code) VALUES (194, 'mf', '663');
INSERT INTO countries (id, code, iso_code) VALUES (195, 'pm', '666');
INSERT INTO countries (id, code, iso_code) VALUES (196, 'vc', '670');
INSERT INTO countries (id, code, iso_code) VALUES (197, 'ws', '882');
INSERT INTO countries (id, code, iso_code) VALUES (198, 'sm', '674');
INSERT INTO countries (id, code, iso_code) VALUES (199, 'st', '678');
INSERT INTO countries (id, code, iso_code) VALUES (200, 'sa', '682');
INSERT INTO countries (id, code, iso_code) VALUES (201, 'sn', '686');
INSERT INTO countries (id, code, iso_code) VALUES (202, 'rs', '688');
INSERT INTO countries (id, code, iso_code) VALUES (203, 'sc', '690');
INSERT INTO countries (id, code, iso_code) VALUES (204, 'sl', '694');
INSERT INTO countries (id, code, iso_code) VALUES (205, 'sg', '702');
INSERT INTO countries (id, code, iso_code) VALUES (206, 'sk', '703');
INSERT INTO countries (id, code, iso_code) VALUES (207, 'si', '705');
INSERT INTO countries (id, code, iso_code) VALUES (208, 'sb', '090');
INSERT INTO countries (id, code, iso_code) VALUES (209, 'so', '706');
INSERT INTO countries (id, code, iso_code) VALUES (210, 'za', '710');
INSERT INTO countries (id, code, iso_code) VALUES (211, 'gs', '239');
INSERT INTO countries (id, code, iso_code) VALUES (212, 'ss', '728');
INSERT INTO countries (id, code, iso_code) VALUES (213, 'lk', '144');
INSERT INTO countries (id, code, iso_code) VALUES (214, 'sd', '736');
INSERT INTO countries (id, code, iso_code) VALUES (215, 'sr', '740');
INSERT INTO countries (id, code, iso_code) VALUES (216, 'sj', '744');
INSERT INTO countries (id, code, iso_code) VALUES (217, 'sz', '748');
INSERT INTO countries (id, code, iso_code) VALUES (218, 'sy', '760');
INSERT INTO countries (id, code, iso_code) VALUES (219, 'tw', '158');
INSERT INTO countries (id, code, iso_code) VALUES (220, 'tj', '762');
INSERT INTO countries (id, code, iso_code) VALUES (221, 'tz', '834');
INSERT INTO countries (id, code, iso_code) VALUES (222, 'th', '764');
INSERT INTO countries (id, code, iso_code) VALUES (223, 'tl', '626');
INSERT INTO countries (id, code, iso_code) VALUES (224, 'tg', '768');
INSERT INTO countries (id, code, iso_code) VALUES (225, 'tk', '772');
INSERT INTO countries (id, code, iso_code) VALUES (226, 'to', '776');
INSERT INTO countries (id, code, iso_code) VALUES (227, 'tt', '780');
INSERT INTO countries (id, code, iso_code) VALUES (228, 'tn', '788');
INSERT INTO countries (id, code, iso_code) VALUES (229, 'tr', '792');
INSERT INTO countries (id, code, iso_code) VALUES (230, 'tm', '795');
INSERT INTO countries (id, code, iso_code) VALUES (231, 'tc', '796');
INSERT INTO countries (id, code, iso_code) VALUES (232, 'tv', '798');
INSERT INTO countries (id, code, iso_code) VALUES (233, 'ug', '800');
INSERT INTO countries (id, code, iso_code) VALUES (234, 'ua', '804');
INSERT INTO countries (id, code, iso_code) VALUES (235, 'ae', '784');
INSERT INTO countries (id, code, iso_code) VALUES (236, 'um', '581');
INSERT INTO countries (id, code, iso_code) VALUES (237, 'uy', '858');
INSERT INTO countries (id, code, iso_code) VALUES (238, 'uz', '860');
INSERT INTO countries (id, code, iso_code) VALUES (239, 'vu', '548');
INSERT INTO countries (id, code, iso_code) VALUES (240, 've', '862');
INSERT INTO countries (id, code, iso_code) VALUES (241, 'vn', '704');
INSERT INTO countries (id, code, iso_code) VALUES (242, 'vi', '850');
INSERT INTO countries (id, code, iso_code) VALUES (243, 'wf', '876');
INSERT INTO countries (id, code, iso_code) VALUES (244, 'eh', '732');
INSERT INTO countries (id, code, iso_code) VALUES (245, 'ye', '887');
INSERT INTO countries (id, code, iso_code) VALUES (246, 'zm', '894');
INSERT INTO countries (id, code, iso_code) VALUES (247, 'zw', '716');
-- ENGLISH --
INSERT INTO country_names (country_id, language_id, name) VALUES (0, 1, 'N/A');
INSERT INTO country_names (country_id, language_id, name) VALUES (1, 1, 'Russia');
INSERT INTO country_names (country_id, language_id, name) VALUES (2, 1, 'United States');
INSERT INTO country_names (country_id, language_id, name) VALUES (3, 1, 'Ireland');
INSERT INTO country_names (country_id, language_id, name) VALUES (4, 1, 'Switzerland');
INSERT INTO country_names (country_id, language_id, name) VALUES (5, 1, 'France');
INSERT INTO country_names (country_id, language_id, name) VALUES (6, 1, 'Canada');
INSERT INTO country_names (country_id, language_id, name) VALUES (7, 1, 'Sweden');
INSERT INTO country_names (country_id, language_id, name) VALUES (8, 1, 'Italy');
INSERT INTO country_names (country_id, language_id, name) VALUES (9, 1, 'Spain');
INSERT INTO country_names (country_id, language_id, name) VALUES (10, 1, 'Australia');
INSERT INTO country_names (country_id, language_id, name) VALUES (11, 1, 'Austria');
INSERT INTO country_names (country_id, language_id, name) VALUES (12, 1, 'Belgium');
INSERT INTO country_names (country_id, language_id, name) VALUES (13, 1, 'United Kingdom');
INSERT INTO country_names (country_id, language_id, name) VALUES (14, 1, 'Germany');
INSERT INTO country_names (country_id, language_id, name) VALUES (15, 1, 'China');
INSERT INTO country_names (country_id, language_id, name) VALUES (16, 1, 'Netherlands');
INSERT INTO country_names (country_id, language_id, name) VALUES (17, 1, 'Greece');
INSERT INTO country_names (country_id, language_id, name) VALUES (18, 1, 'Bermuda');
INSERT INTO country_names (country_id, language_id, name) VALUES (19, 1, 'Finland');
INSERT INTO country_names (country_id, language_id, name) VALUES (20, 1, 'Brazil');
INSERT INTO country_names (country_id, language_id, name) VALUES (21, 1, 'Jersey');
INSERT INTO country_names (country_id, language_id, name) VALUES (22, 1, 'Afghanistan');
INSERT INTO country_names (country_id, language_id, name) VALUES (23, 1, 'Aland Islands');
INSERT INTO country_names (country_id, language_id, name) VALUES (24, 1, 'Albania');
INSERT INTO country_names (country_id, language_id, name) VALUES (25, 1, 'Algeria');
INSERT INTO country_names (country_id, language_id, name) VALUES (26, 1, 'American Samoa');
INSERT INTO country_names (country_id, language_id, name) VALUES (27, 1, 'Andorra');
INSERT INTO country_names (country_id, language_id, name) VALUES (28, 1, 'Angola');
INSERT INTO country_names (country_id, language_id, name) VALUES (29, 1, 'Anguilla');
INSERT INTO country_names (country_id, language_id, name) VALUES (30, 1, 'Antarctica');
INSERT INTO country_names (country_id, language_id, name) VALUES (31, 1, 'Antigua and Barbuda');
INSERT INTO country_names (country_id, language_id, name) VALUES (32, 1, 'Argentina');
INSERT INTO country_names (country_id, language_id, name) VALUES (33, 1, 'Armenia');
INSERT INTO country_names (country_id, language_id, name) VALUES (34, 1, 'Aruba');
INSERT INTO country_names (country_id, language_id, name) VALUES (35, 1, 'Azerbaijan');
INSERT INTO country_names (country_id, language_id, name) VALUES (36, 1, 'Bahamas');
INSERT INTO country_names (country_id, language_id, name) VALUES (37, 1, 'Bahrain');
INSERT INTO country_names (country_id, language_id, name) VALUES (38, 1, 'Bangladesh');
INSERT INTO country_names (country_id, language_id, name) VALUES (39, 1, 'Barbados');
INSERT INTO country_names (country_id, language_id, name) VALUES (40, 1, 'Belarus');
INSERT INTO country_names (country_id, language_id, name) VALUES (41, 1, 'Belize');
INSERT INTO country_names (country_id, language_id, name) VALUES (42, 1, 'Benin');
INSERT INTO country_names (country_id, language_id, name) VALUES (43, 1, 'Bhutan');
INSERT INTO country_names (country_id, language_id, name) VALUES (44, 1, 'Bolivia');
INSERT INTO country_names (country_id, language_id, name) VALUES (45, 1, 'Bosnia and Herzegovina');
INSERT INTO country_names (country_id, language_id, name) VALUES (46, 1, 'Botswana');
INSERT INTO country_names (country_id, language_id, name) VALUES (47, 1, 'Bouvet Island');
INSERT INTO country_names (country_id, language_id, name) VALUES (48, 1, 'British Virgin Islands');
INSERT INTO country_names (country_id, language_id, name) VALUES (49, 1, 'British Indian Ocean Territory');
INSERT INTO country_names (country_id, language_id, name) VALUES (50, 1, 'Brunei Darussalam');
INSERT INTO country_names (country_id, language_id, name) VALUES (51, 1, 'Bulgaria');
INSERT INTO country_names (country_id, language_id, name) VALUES (52, 1, 'Burkina Faso');
INSERT INTO country_names (country_id, language_id, name) VALUES (53, 1, 'Burundi');
INSERT INTO country_names (country_id, language_id, name) VALUES (54, 1, 'Cambodia');
INSERT INTO country_names (country_id, language_id, name) VALUES (55, 1, 'Cameroon');
INSERT INTO country_names (country_id, language_id, name) VALUES (56, 1, 'Cape Verde');
INSERT INTO country_names (country_id, language_id, name) VALUES (57, 1, 'Cayman Islands');
INSERT INTO country_names (country_id, language_id, name) VALUES (58, 1, 'Central African Republic');
INSERT INTO country_names (country_id, language_id, name) VALUES (59, 1, 'Chad');
INSERT INTO country_names (country_id, language_id, name) VALUES (60, 1, 'Chile');
INSERT INTO country_names (country_id, language_id, name) VALUES (61, 1, 'Hong Kong, SAR China');
INSERT INTO country_names (country_id, language_id, name) VALUES (62, 1, 'Macao, SAR China');
INSERT INTO country_names (country_id, language_id, name) VALUES (63, 1, 'Christmas Island');
INSERT INTO country_names (country_id, language_id, name) VALUES (64, 1, 'Cocos (Keeling) Islands');
INSERT INTO country_names (country_id, language_id, name) VALUES (65, 1, 'Colombia');
INSERT INTO country_names (country_id, language_id, name) VALUES (66, 1, 'Comoros');
INSERT INTO country_names (country_id, language_id, name) VALUES (67, 1, 'Congo (Brazzaville)');
INSERT INTO country_names (country_id, language_id, name) VALUES (68, 1, 'Congo, (Kinshasa)');
INSERT INTO country_names (country_id, language_id, name) VALUES (69, 1, 'Cook Islands');
INSERT INTO country_names (country_id, language_id, name) VALUES (70, 1, 'Costa Rica');
INSERT INTO country_names (country_id, language_id, name) VALUES (71, 1, 'Côte d’Ivoire');
INSERT INTO country_names (country_id, language_id, name) VALUES (72, 1, 'Croatia');
INSERT INTO country_names (country_id, language_id, name) VALUES (73, 1, 'Cuba');
INSERT INTO country_names (country_id, language_id, name) VALUES (74, 1, 'Cyprus');
INSERT INTO country_names (country_id, language_id, name) VALUES (75, 1, 'Czech Republic');
INSERT INTO country_names (country_id, language_id, name) VALUES (76, 1, 'Denmark');
INSERT INTO country_names (country_id, language_id, name) VALUES (77, 1, 'Djibouti');
INSERT INTO country_names (country_id, language_id, name) VALUES (78, 1, 'Dominica');
INSERT INTO country_names (country_id, language_id, name) VALUES (79, 1, 'Dominican Republic');
INSERT INTO country_names (country_id, language_id, name) VALUES (80, 1, 'Ecuador');
INSERT INTO country_names (country_id, language_id, name) VALUES (81, 1, 'Egypt');
INSERT INTO country_names (country_id, language_id, name) VALUES (82, 1, 'El Salvador');
INSERT INTO country_names (country_id, language_id, name) VALUES (83, 1, 'Equatorial Guinea');
INSERT INTO country_names (country_id, language_id, name) VALUES (84, 1, 'Eritrea');
INSERT INTO country_names (country_id, language_id, name) VALUES (85, 1, 'Estonia');
INSERT INTO country_names (country_id, language_id, name) VALUES (86, 1, 'Ethiopia');
INSERT INTO country_names (country_id, language_id, name) VALUES (87, 1, 'Falkland Islands (Malvinas)');
INSERT INTO country_names (country_id, language_id, name) VALUES (88, 1, 'Faroe Islands');
INSERT INTO country_names (country_id, language_id, name) VALUES (89, 1, 'Fiji');
INSERT INTO country_names (country_id, language_id, name) VALUES (90, 1, 'French Guiana');
INSERT INTO country_names (country_id, language_id, name) VALUES (91, 1, 'French Polynesia');
INSERT INTO country_names (country_id, language_id, name) VALUES (92, 1, 'French Southern Territories');
INSERT INTO country_names (country_id, language_id, name) VALUES (93, 1, 'Gabon');
INSERT INTO country_names (country_id, language_id, name) VALUES (94, 1, 'Gambia');
INSERT INTO country_names (country_id, language_id, name) VALUES (95, 1, 'Georgia');
INSERT INTO country_names (country_id, language_id, name) VALUES (96, 1, 'Ghana');
INSERT INTO country_names (country_id, language_id, name) VALUES (97, 1, 'Gibraltar');
INSERT INTO country_names (country_id, language_id, name) VALUES (98, 1, 'Greenland');
INSERT INTO country_names (country_id, language_id, name) VALUES (99, 1, 'Grenada');
INSERT INTO country_names (country_id, language_id, name) VALUES (100, 1, 'Guadeloupe');
INSERT INTO country_names (country_id, language_id, name) VALUES (101, 1, 'Guam');
INSERT INTO country_names (country_id, language_id, name) VALUES (102, 1, 'Guatemala');
INSERT INTO country_names (country_id, language_id, name) VALUES (103, 1, 'Guernsey');
INSERT INTO country_names (country_id, language_id, name) VALUES (104, 1, 'Guinea');
INSERT INTO country_names (country_id, language_id, name) VALUES (105, 1, 'Guinea-Bissau');
INSERT INTO country_names (country_id, language_id, name) VALUES (106, 1, 'Guyana');
INSERT INTO country_names (country_id, language_id, name) VALUES (107, 1, 'Haiti');
INSERT INTO country_names (country_id, language_id, name) VALUES (108, 1, 'Heard and Mcdonald Islands');
INSERT INTO country_names (country_id, language_id, name) VALUES (109, 1, 'Holy See (Vatican City State)');
INSERT INTO country_names (country_id, language_id, name) VALUES (110, 1, 'Honduras');
INSERT INTO country_names (country_id, language_id, name) VALUES (111, 1, 'Hungary');
INSERT INTO country_names (country_id, language_id, name) VALUES (112, 1, 'Iceland');
INSERT INTO country_names (country_id, language_id, name) VALUES (113, 1, 'India');
INSERT INTO country_names (country_id, language_id, name) VALUES (114, 1, 'Indonesia');
INSERT INTO country_names (country_id, language_id, name) VALUES (115, 1, 'Iran, Islamic Republic of');
INSERT INTO country_names (country_id, language_id, name) VALUES (116, 1, 'Iraq');
INSERT INTO country_names (country_id, language_id, name) VALUES (117, 1, 'Isle of Man');
INSERT INTO country_names (country_id, language_id, name) VALUES (118, 1, 'Israel');
INSERT INTO country_names (country_id, language_id, name) VALUES (119, 1, 'Jamaica');
INSERT INTO country_names (country_id, language_id, name) VALUES (120, 1, 'Japan');
INSERT INTO country_names (country_id, language_id, name) VALUES (121, 1, 'Jordan');
INSERT INTO country_names (country_id, language_id, name) VALUES (122, 1, 'Kazakhstan');
INSERT INTO country_names (country_id, language_id, name) VALUES (123, 1, 'Kenya');
INSERT INTO country_names (country_id, language_id, name) VALUES (124, 1, 'Kiribati');
INSERT INTO country_names (country_id, language_id, name) VALUES (125, 1, 'Korea (North)');
INSERT INTO country_names (country_id, language_id, name) VALUES (126, 1, 'Korea (South)');
INSERT INTO country_names (country_id, language_id, name) VALUES (127, 1, 'Kuwait');
INSERT INTO country_names (country_id, language_id, name) VALUES (128, 1, 'Kyrgyzstan');
INSERT INTO country_names (country_id, language_id, name) VALUES (129, 1, 'Lao PDR');
INSERT INTO country_names (country_id, language_id, name) VALUES (130, 1, 'Latvia');
INSERT INTO country_names (country_id, language_id, name) VALUES (131, 1, 'Lebanon');
INSERT INTO country_names (country_id, language_id, name) VALUES (132, 1, 'Lesotho');
INSERT INTO country_names (country_id, language_id, name) VALUES (133, 1, 'Liberia');
INSERT INTO country_names (country_id, language_id, name) VALUES (134, 1, 'Libya');
INSERT INTO country_names (country_id, language_id, name) VALUES (135, 1, 'Liechtenstein');
INSERT INTO country_names (country_id, language_id, name) VALUES (136, 1, 'Lithuania');
INSERT INTO country_names (country_id, language_id, name) VALUES (137, 1, 'Luxembourg');
INSERT INTO country_names (country_id, language_id, name) VALUES (138, 1, 'Macedonia, Republic of');
INSERT INTO country_names (country_id, language_id, name) VALUES (139, 1, 'Madagascar');
INSERT INTO country_names (country_id, language_id, name) VALUES (140, 1, 'Malawi');
INSERT INTO country_names (country_id, language_id, name) VALUES (141, 1, 'Malaysia');
INSERT INTO country_names (country_id, language_id, name) VALUES (142, 1, 'Maldives');
INSERT INTO country_names (country_id, language_id, name) VALUES (143, 1, 'Mali');
INSERT INTO country_names (country_id, language_id, name) VALUES (144, 1, 'Malta');
INSERT INTO country_names (country_id, language_id, name) VALUES (145, 1, 'Marshall Islands');
INSERT INTO country_names (country_id, language_id, name) VALUES (146, 1, 'Martinique');
INSERT INTO country_names (country_id, language_id, name) VALUES (147, 1, 'Mauritania');
INSERT INTO country_names (country_id, language_id, name) VALUES (148, 1, 'Mauritius');
INSERT INTO country_names (country_id, language_id, name) VALUES (149, 1, 'Mayotte');
INSERT INTO country_names (country_id, language_id, name) VALUES (150, 1, 'Mexico');
INSERT INTO country_names (country_id, language_id, name) VALUES (151, 1, 'Micronesia, Federated States of');
INSERT INTO country_names (country_id, language_id, name) VALUES (152, 1, 'Moldova');
INSERT INTO country_names (country_id, language_id, name) VALUES (153, 1, 'Monaco');
INSERT INTO country_names (country_id, language_id, name) VALUES (154, 1, 'Mongolia');
INSERT INTO country_names (country_id, language_id, name) VALUES (155, 1, 'Montenegro');
INSERT INTO country_names (country_id, language_id, name) VALUES (156, 1, 'Montserrat');
INSERT INTO country_names (country_id, language_id, name) VALUES (157, 1, 'Morocco');
INSERT INTO country_names (country_id, language_id, name) VALUES (158, 1, 'Mozambique');
INSERT INTO country_names (country_id, language_id, name) VALUES (159, 1, 'Myanmar');
INSERT INTO country_names (country_id, language_id, name) VALUES (160, 1, 'Namibia');
INSERT INTO country_names (country_id, language_id, name) VALUES (161, 1, 'Nauru');
INSERT INTO country_names (country_id, language_id, name) VALUES (162, 1, 'Nepal');
INSERT INTO country_names (country_id, language_id, name) VALUES (163, 1, 'Netherlands Antilles');
INSERT INTO country_names (country_id, language_id, name) VALUES (164, 1, 'New Caledonia');
INSERT INTO country_names (country_id, language_id, name) VALUES (165, 1, 'New Zealand');
INSERT INTO country_names (country_id, language_id, name) VALUES (166, 1, 'Nicaragua');
INSERT INTO country_names (country_id, language_id, name) VALUES (167, 1, 'Niger');
INSERT INTO country_names (country_id, language_id, name) VALUES (168, 1, 'Nigeria');
INSERT INTO country_names (country_id, language_id, name) VALUES (169, 1, 'Niue');
INSERT INTO country_names (country_id, language_id, name) VALUES (170, 1, 'Norfolk Island');
INSERT INTO country_names (country_id, language_id, name) VALUES (171, 1, 'Northern Mariana Islands');
INSERT INTO country_names (country_id, language_id, name) VALUES (172, 1, 'Norway');
INSERT INTO country_names (country_id, language_id, name) VALUES (173, 1, 'Oman');
INSERT INTO country_names (country_id, language_id, name) VALUES (174, 1, 'Pakistan');
INSERT INTO country_names (country_id, language_id, name) VALUES (175, 1, 'Palau');
INSERT INTO country_names (country_id, language_id, name) VALUES (176, 1, 'Palestinian Territory');
INSERT INTO country_names (country_id, language_id, name) VALUES (177, 1, 'Panama');
INSERT INTO country_names (country_id, language_id, name) VALUES (178, 1, 'Papua New Guinea');
INSERT INTO country_names (country_id, language_id, name) VALUES (179, 1, 'Paraguay');
INSERT INTO country_names (country_id, language_id, name) VALUES (180, 1, 'Peru');
INSERT INTO country_names (country_id, language_id, name) VALUES (181, 1, 'Philippines');
INSERT INTO country_names (country_id, language_id, name) VALUES (182, 1, 'Pitcairn');
INSERT INTO country_names (country_id, language_id, name) VALUES (183, 1, 'Poland');
INSERT INTO country_names (country_id, language_id, name) VALUES (184, 1, 'Portugal');
INSERT INTO country_names (country_id, language_id, name) VALUES (185, 1, 'Puerto Rico');
INSERT INTO country_names (country_id, language_id, name) VALUES (186, 1, 'Qatar');
INSERT INTO country_names (country_id, language_id, name) VALUES (187, 1, 'Réunion');
INSERT INTO country_names (country_id, language_id, name) VALUES (188, 1, 'Romania');
INSERT INTO country_names (country_id, language_id, name) VALUES (189, 1, 'Rwanda');
INSERT INTO country_names (country_id, language_id, name) VALUES (190, 1, 'Saint-Barthélemy');
INSERT INTO country_names (country_id, language_id, name) VALUES (191, 1, 'Saint Helena');
INSERT INTO country_names (country_id, language_id, name) VALUES (192, 1, 'Saint Kitts and Nevis');
INSERT INTO country_names (country_id, language_id, name) VALUES (193, 1, 'Saint Lucia');
INSERT INTO country_names (country_id, language_id, name) VALUES (194, 1, 'Saint-Martin (French part)');
INSERT INTO country_names (country_id, language_id, name) VALUES (195, 1, 'Saint Pierre and Miquelon');
INSERT INTO country_names (country_id, language_id, name) VALUES (196, 1, 'Saint Vincent and Grenadines');
INSERT INTO country_names (country_id, language_id, name) VALUES (197, 1, 'Samoa');
INSERT INTO country_names (country_id, language_id, name) VALUES (198, 1, 'San Marino');
INSERT INTO country_names (country_id, language_id, name) VALUES (199, 1, 'Sao Tome and Principe');
INSERT INTO country_names (country_id, language_id, name) VALUES (200, 1, 'Saudi Arabia');
INSERT INTO country_names (country_id, language_id, name) VALUES (201, 1, 'Senegal');
INSERT INTO country_names (country_id, language_id, name) VALUES (202, 1, 'Serbia');
INSERT INTO country_names (country_id, language_id, name) VALUES (203, 1, 'Seychelles');
INSERT INTO country_names (country_id, language_id, name) VALUES (204, 1, 'Sierra Leone');
INSERT INTO country_names (country_id, language_id, name) VALUES (205, 1, 'Singapore');
INSERT INTO country_names (country_id, language_id, name) VALUES (206, 1, 'Slovakia');
INSERT INTO country_names (country_id, language_id, name) VALUES (207, 1, 'Slovenia');
INSERT INTO country_names (country_id, language_id, name) VALUES (208, 1, 'Solomon Islands');
INSERT INTO country_names (country_id, language_id, name) VALUES (209, 1, 'Somalia');
INSERT INTO country_names (country_id, language_id, name) VALUES (210, 1, 'South Africa');
INSERT INTO country_names (country_id, language_id, name) VALUES (211, 1, 'South Georgia and the South Sandwich Islands');
INSERT INTO country_names (country_id, language_id, name) VALUES (212, 1, 'South Sudan');
INSERT INTO country_names (country_id, language_id, name) VALUES (213, 1, 'Sri Lanka');
INSERT INTO country_names (country_id, language_id, name) VALUES (214, 1, 'Sudan');
INSERT INTO country_names (country_id, language_id, name) VALUES (215, 1, 'Suriname');
INSERT INTO country_names (country_id, language_id, name) VALUES (216, 1, 'Svalbard and Jan Mayen Islands');
INSERT INTO country_names (country_id, language_id, name) VALUES (217, 1, 'Swaziland');
INSERT INTO country_names (country_id, language_id, name) VALUES (218, 1, 'Syrian Arab Republic (Syria)');
INSERT INTO country_names (country_id, language_id, name) VALUES (219, 1, 'Taiwan, Republic of China');
INSERT INTO country_names (country_id, language_id, name) VALUES (220, 1, 'Tajikistan');
INSERT INTO country_names (country_id, language_id, name) VALUES (221, 1, 'Tanzania, United Republic of');
INSERT INTO country_names (country_id, language_id, name) VALUES (222, 1, 'Thailand');
INSERT INTO country_names (country_id, language_id, name) VALUES (223, 1, 'Timor-Leste');
INSERT INTO country_names (country_id, language_id, name) VALUES (224, 1, 'Togo');
INSERT INTO country_names (country_id, language_id, name) VALUES (225, 1, 'Tokelau');
INSERT INTO country_names (country_id, language_id, name) VALUES (226, 1, 'Tonga');
INSERT INTO country_names (country_id, language_id, name) VALUES (227, 1, 'Trinidad and Tobago');
INSERT INTO country_names (country_id, language_id, name) VALUES (228, 1, 'Tunisia');
INSERT INTO country_names (country_id, language_id, name) VALUES (229, 1, 'Turkey');
INSERT INTO country_names (country_id, language_id, name) VALUES (230, 1, 'Turkmenistan');
INSERT INTO country_names (country_id, language_id, name) VALUES (231, 1, 'Turks and Caicos Islands');
INSERT INTO country_names (country_id, language_id, name) VALUES (232, 1, 'Tuvalu');
INSERT INTO country_names (country_id, language_id, name) VALUES (233, 1, 'Uganda');
INSERT INTO country_names (country_id, language_id, name) VALUES (234, 1, 'Ukraine');
INSERT INTO country_names (country_id, language_id, name) VALUES (235, 1, 'United Arab Emirates');
INSERT INTO country_names (country_id, language_id, name) VALUES (236, 1, 'US Minor Outlying Islands');
INSERT INTO country_names (country_id, language_id, name) VALUES (237, 1, 'Uruguay');
INSERT INTO country_names (country_id, language_id, name) VALUES (238, 1, 'Uzbekistan');
INSERT INTO country_names (country_id, language_id, name) VALUES (239, 1, 'Vanuatu');
INSERT INTO country_names (country_id, language_id, name) VALUES (240, 1, 'Venezuela (Bolivarian Republic)');
INSERT INTO country_names (country_id, language_id, name) VALUES (241, 1, 'Viet Nam');
INSERT INTO country_names (country_id, language_id, name) VALUES (242, 1, 'Virgin Islands, US');
INSERT INTO country_names (country_id, language_id, name) VALUES (243, 1, 'Wallis and Futuna Islands');
INSERT INTO country_names (country_id, language_id, name) VALUES (244, 1, 'Western Sahara');
INSERT INTO country_names (country_id, language_id, name) VALUES (245, 1, 'Yemen');
INSERT INTO country_names (country_id, language_id, name) VALUES (246, 1, 'Zambia');
INSERT INTO country_names (country_id, language_id, name) VALUES (247, 1, 'Zimbabwe');
-- RUSSIAN --
INSERT INTO country_names (country_id, language_id, name) VALUES (0, 2, 'н/д');
INSERT INTO country_names (country_id, language_id, name) VALUES (1, 2, 'Россия');
INSERT INTO country_names (country_id, language_id, name) VALUES (2, 2, 'США');
INSERT INTO country_names (country_id, language_id, name) VALUES (3, 2, 'Ирландия');
INSERT INTO country_names (country_id, language_id, name) VALUES (4, 2, 'Швейцария');
INSERT INTO country_names (country_id, language_id, name) VALUES (5, 2, 'Франция');
INSERT INTO country_names (country_id, language_id, name) VALUES (6, 2, 'Канада');
INSERT INTO country_names (country_id, language_id, name) VALUES (7, 2, 'Швеция');
INSERT INTO country_names (country_id, language_id, name) VALUES (8, 2, 'Италия');
INSERT INTO country_names (country_id, language_id, name) VALUES (9, 2, 'Испания');
INSERT INTO country_names (country_id, language_id, name) VALUES (10, 2, 'Австралия');
INSERT INTO country_names (country_id, language_id, name) VALUES (11, 2, 'Австрия');
INSERT INTO country_names (country_id, language_id, name) VALUES (12, 2, 'Бельгия');
INSERT INTO country_names (country_id, language_id, name) VALUES (13, 2, 'Великобритания');
INSERT INTO country_names (country_id, language_id, name) VALUES (14, 2, 'Германия');
INSERT INTO country_names (country_id, language_id, name) VALUES (15, 2, 'Китай');
INSERT INTO country_names (country_id, language_id, name) VALUES (16, 2, 'Нидерланды');
INSERT INTO country_names (country_id, language_id, name) VALUES (17, 2, 'Греция');
INSERT INTO country_names (country_id, language_id, name) VALUES (18, 2, 'Бермудские Острова');
INSERT INTO country_names (country_id, language_id, name) VALUES (19, 2, 'Финляндия');
INSERT INTO country_names (country_id, language_id, name) VALUES (20, 2, 'Бразилия');
INSERT INTO country_names (country_id, language_id, name) VALUES (21, 2, 'Джерси');
INSERT INTO country_names (country_id, language_id, name) VALUES (22, 2, 'Афганистан');
INSERT INTO country_names (country_id, language_id, name) VALUES (23, 2, 'Аландские острова');
INSERT INTO country_names (country_id, language_id, name) VALUES (24, 2, 'Албания');
INSERT INTO country_names (country_id, language_id, name) VALUES (25, 2, 'Алжир');
INSERT INTO country_names (country_id, language_id, name) VALUES (26, 2, 'Американское Самоа');
INSERT INTO country_names (country_id, language_id, name) VALUES (27, 2, 'Андорра');
INSERT INTO country_names (country_id, language_id, name) VALUES (28, 2, 'Ангола');
INSERT INTO country_names (country_id, language_id, name) VALUES (29, 2, 'Ангилья');
INSERT INTO country_names (country_id, language_id, name) VALUES (30, 2, 'Антарктика');
INSERT INTO country_names (country_id, language_id, name) VALUES (31, 2, 'Антигуа и Барбуда');
INSERT INTO country_names (country_id, language_id, name) VALUES (32, 2, 'Аргентина');
INSERT INTO country_names (country_id, language_id, name) VALUES (33, 2, 'Армения');
INSERT INTO country_names (country_id, language_id, name) VALUES (34, 2, 'Аруба');
INSERT INTO country_names (country_id, language_id, name) VALUES (35, 2, 'Азербайджан');
INSERT INTO country_names (country_id, language_id, name) VALUES (36, 2, 'Багамские Острова');
INSERT INTO country_names (country_id, language_id, name) VALUES (37, 2, 'Бахрейн');
INSERT INTO country_names (country_id, language_id, name) VALUES (38, 2, 'Бангладеш');
INSERT INTO country_names (country_id, language_id, name) VALUES (39, 2, 'Барбадос');
INSERT INTO country_names (country_id, language_id, name) VALUES (40, 2, 'Беларусь');
INSERT INTO country_names (country_id, language_id, name) VALUES (41, 2, 'Белиз');
INSERT INTO country_names (country_id, language_id, name) VALUES (42, 2, 'Бенин');
INSERT INTO country_names (country_id, language_id, name) VALUES (43, 2, 'Бутан');
INSERT INTO country_names (country_id, language_id, name) VALUES (44, 2, 'Боливия');
INSERT INTO country_names (country_id, language_id, name) VALUES (45, 2, 'Босния и Герцоговина');
INSERT INTO country_names (country_id, language_id, name) VALUES (46, 2, 'Ботсвана');
INSERT INTO country_names (country_id, language_id, name) VALUES (47, 2, 'Остров Буве');
INSERT INTO country_names (country_id, language_id, name) VALUES (48, 2, 'Виргинские Острова (Великобритания)');
INSERT INTO country_names (country_id, language_id, name) VALUES (49, 2, 'Британская Территория в Индийском Океане');
INSERT INTO country_names (country_id, language_id, name) VALUES (50, 2, 'Бруней');
INSERT INTO country_names (country_id, language_id, name) VALUES (51, 2, 'Болгария');
INSERT INTO country_names (country_id, language_id, name) VALUES (52, 2, 'Буркина-Фасо');
INSERT INTO country_names (country_id, language_id, name) VALUES (53, 2, 'Бурунди');
INSERT INTO country_names (country_id, language_id, name) VALUES (54, 2, 'Камбоджа');
INSERT INTO country_names (country_id, language_id, name) VALUES (55, 2, 'Камерун');
INSERT INTO country_names (country_id, language_id, name) VALUES (56, 2, 'Кабо-Верде');
INSERT INTO country_names (country_id, language_id, name) VALUES (57, 2, 'Острова Кайман');
INSERT INTO country_names (country_id, language_id, name) VALUES (58, 2, 'Центральноафриканская Республика');
INSERT INTO country_names (country_id, language_id, name) VALUES (59, 2, 'Чад');
INSERT INTO country_names (country_id, language_id, name) VALUES (60, 2, 'Чили');
INSERT INTO country_names (country_id, language_id, name) VALUES (61, 2, 'Гонконг');
INSERT INTO country_names (country_id, language_id, name) VALUES (62, 2, 'Макао');
INSERT INTO country_names (country_id, language_id, name) VALUES (63, 2, 'Остров Рождества');
INSERT INTO country_names (country_id, language_id, name) VALUES (64, 2, 'Кокосовые острова');
INSERT INTO country_names (country_id, language_id, name) VALUES (65, 2, 'Колумбия');
INSERT INTO country_names (country_id, language_id, name) VALUES (66, 2, 'Коморы');
INSERT INTO country_names (country_id, language_id, name) VALUES (67, 2, 'Республика Конго');
INSERT INTO country_names (country_id, language_id, name) VALUES (68, 2, 'Демократическая Республика Конго');
INSERT INTO country_names (country_id, language_id, name) VALUES (69, 2, 'Острова Кука');
INSERT INTO country_names (country_id, language_id, name) VALUES (70, 2, 'Коста-Рика');
INSERT INTO country_names (country_id, language_id, name) VALUES (71, 2, 'Кот-д’Ивуар');
INSERT INTO country_names (country_id, language_id, name) VALUES (72, 2, 'Хорватия');
INSERT INTO country_names (country_id, language_id, name) VALUES (73, 2, 'Куба');
INSERT INTO country_names (country_id, language_id, name) VALUES (74, 2, 'Кипр');
INSERT INTO country_names (country_id, language_id, name) VALUES (75, 2, 'Чехия');
INSERT INTO country_names (country_id, language_id, name) VALUES (76, 2, 'Дания');
INSERT INTO country_names (country_id, language_id, name) VALUES (77, 2, 'Джибути');
INSERT INTO country_names (country_id, language_id, name) VALUES (78, 2, 'Доминика');
INSERT INTO country_names (country_id, language_id, name) VALUES (79, 2, 'Доминиканская Республика');
INSERT INTO country_names (country_id, language_id, name) VALUES (80, 2, 'Эквадор');
INSERT INTO country_names (country_id, language_id, name) VALUES (81, 2, 'Египет');
INSERT INTO country_names (country_id, language_id, name) VALUES (82, 2, 'Сальвадор');
INSERT INTO country_names (country_id, language_id, name) VALUES (83, 2, 'Экваториальная Гвинея');
INSERT INTO country_names (country_id, language_id, name) VALUES (84, 2, 'Эритрея');
INSERT INTO country_names (country_id, language_id, name) VALUES (85, 2, 'Эстония');
INSERT INTO country_names (country_id, language_id, name) VALUES (86, 2, 'Эфиопия');
INSERT INTO country_names (country_id, language_id, name) VALUES (87, 2, 'Фолклендские острова');
INSERT INTO country_names (country_id, language_id, name) VALUES (88, 2, 'Фарерские острова');
INSERT INTO country_names (country_id, language_id, name) VALUES (89, 2, 'Фиджи');
INSERT INTO country_names (country_id, language_id, name) VALUES (90, 2, 'Французская Гвиана');
INSERT INTO country_names (country_id, language_id, name) VALUES (91, 2, 'Французская Полинезия');
INSERT INTO country_names (country_id, language_id, name) VALUES (92, 2, 'Французские южные территории');
INSERT INTO country_names (country_id, language_id, name) VALUES (93, 2, 'Габон');
INSERT INTO country_names (country_id, language_id, name) VALUES (94, 2, 'Гамбия');
INSERT INTO country_names (country_id, language_id, name) VALUES (95, 2, 'Грузия');
INSERT INTO country_names (country_id, language_id, name) VALUES (96, 2, 'Гана');
INSERT INTO country_names (country_id, language_id, name) VALUES (97, 2, 'Гибралтар ');
INSERT INTO country_names (country_id, language_id, name) VALUES (98, 2, 'Гренландия');
INSERT INTO country_names (country_id, language_id, name) VALUES (99, 2, 'Гренада');
INSERT INTO country_names (country_id, language_id, name) VALUES (100, 2, 'Гваделупа');
INSERT INTO country_names (country_id, language_id, name) VALUES (101, 2, 'Гуам');
INSERT INTO country_names (country_id, language_id, name) VALUES (102, 2, 'Гватемала');
INSERT INTO country_names (country_id, language_id, name) VALUES (103, 2, 'Гернси');
INSERT INTO country_names (country_id, language_id, name) VALUES (104, 2, 'Гвинея');
INSERT INTO country_names (country_id, language_id, name) VALUES (105, 2, 'Гвинея-Бисау');
INSERT INTO country_names (country_id, language_id, name) VALUES (106, 2, 'Гайана');
INSERT INTO country_names (country_id, language_id, name) VALUES (107, 2, 'Республика Гаити');
INSERT INTO country_names (country_id, language_id, name) VALUES (108, 2, 'Остров Херд и острова Макдональд');
INSERT INTO country_names (country_id, language_id, name) VALUES (109, 2, 'Ватикан');
INSERT INTO country_names (country_id, language_id, name) VALUES (110, 2, 'Гондурас');
INSERT INTO country_names (country_id, language_id, name) VALUES (111, 2, 'Венгрия');
INSERT INTO country_names (country_id, language_id, name) VALUES (112, 2, 'Исландия');
INSERT INTO country_names (country_id, language_id, name) VALUES (113, 2, 'Индия');
INSERT INTO country_names (country_id, language_id, name) VALUES (114, 2, 'Индонезия');
INSERT INTO country_names (country_id, language_id, name) VALUES (115, 2, 'Иран');
INSERT INTO country_names (country_id, language_id, name) VALUES (116, 2, 'Ирак');
INSERT INTO country_names (country_id, language_id, name) VALUES (117, 2, 'Остров Мэн');
INSERT INTO country_names (country_id, language_id, name) VALUES (118, 2, 'Израиль');
INSERT INTO country_names (country_id, language_id, name) VALUES (119, 2, 'Ямайка');
INSERT INTO country_names (country_id, language_id, name) VALUES (120, 2, 'Япония');
INSERT INTO country_names (country_id, language_id, name) VALUES (121, 2, 'Иордания');
INSERT INTO country_names (country_id, language_id, name) VALUES (122, 2, 'Казахстан');
INSERT INTO country_names (country_id, language_id, name) VALUES (123, 2, 'Кения');
INSERT INTO country_names (country_id, language_id, name) VALUES (124, 2, 'Кирибати');
INSERT INTO country_names (country_id, language_id, name) VALUES (125, 2, 'КНДР');
INSERT INTO country_names (country_id, language_id, name) VALUES (126, 2, 'Южная Корея');
INSERT INTO country_names (country_id, language_id, name) VALUES (127, 2, 'Кувейт');
INSERT INTO country_names (country_id, language_id, name) VALUES (128, 2, 'Киргизия');
INSERT INTO country_names (country_id, language_id, name) VALUES (129, 2, 'Лаос');
INSERT INTO country_names (country_id, language_id, name) VALUES (130, 2, 'Латвия');
INSERT INTO country_names (country_id, language_id, name) VALUES (131, 2, 'Ливан');
INSERT INTO country_names (country_id, language_id, name) VALUES (132, 2, 'Лесото');
INSERT INTO country_names (country_id, language_id, name) VALUES (133, 2, 'Либерия');
INSERT INTO country_names (country_id, language_id, name) VALUES (134, 2, 'Ливия');
INSERT INTO country_names (country_id, language_id, name) VALUES (135, 2, 'Лихтенштейн');
INSERT INTO country_names (country_id, language_id, name) VALUES (136, 2, 'Литва');
INSERT INTO country_names (country_id, language_id, name) VALUES (137, 2, 'Люксембург');
INSERT INTO country_names (country_id, language_id, name) VALUES (138, 2, 'Македония');
INSERT INTO country_names (country_id, language_id, name) VALUES (139, 2, 'Мадагаскар');
INSERT INTO country_names (country_id, language_id, name) VALUES (140, 2, 'Малави');
INSERT INTO country_names (country_id, language_id, name) VALUES (141, 2, 'Малайзия');
INSERT INTO country_names (country_id, language_id, name) VALUES (142, 2, 'Мальдивы');
INSERT INTO country_names (country_id, language_id, name) VALUES (143, 2, 'Мали');
INSERT INTO country_names (country_id, language_id, name) VALUES (144, 2, 'Мальта');
INSERT INTO country_names (country_id, language_id, name) VALUES (145, 2, 'Маршалловы Острова');
INSERT INTO country_names (country_id, language_id, name) VALUES (146, 2, 'Мартиника');
INSERT INTO country_names (country_id, language_id, name) VALUES (147, 2, 'Мавритания');
INSERT INTO country_names (country_id, language_id, name) VALUES (148, 2, 'Маврикий');
INSERT INTO country_names (country_id, language_id, name) VALUES (149, 2, 'Майотта');
INSERT INTO country_names (country_id, language_id, name) VALUES (150, 2, 'Мексика');
INSERT INTO country_names (country_id, language_id, name) VALUES (151, 2, 'Микронезия');
INSERT INTO country_names (country_id, language_id, name) VALUES (152, 2, 'Молдавия');
INSERT INTO country_names (country_id, language_id, name) VALUES (153, 2, 'Монако');
INSERT INTO country_names (country_id, language_id, name) VALUES (154, 2, 'Монголия');
INSERT INTO country_names (country_id, language_id, name) VALUES (155, 2, 'Черногория');
INSERT INTO country_names (country_id, language_id, name) VALUES (156, 2, 'Монтсеррат');
INSERT INTO country_names (country_id, language_id, name) VALUES (157, 2, 'Марокко');
INSERT INTO country_names (country_id, language_id, name) VALUES (158, 2, 'Мозамбик');
INSERT INTO country_names (country_id, language_id, name) VALUES (159, 2, 'Мьянма');
INSERT INTO country_names (country_id, language_id, name) VALUES (160, 2, 'Намибия');
INSERT INTO country_names (country_id, language_id, name) VALUES (161, 2, 'Науру');
INSERT INTO country_names (country_id, language_id, name) VALUES (162, 2, 'Непал');
INSERT INTO country_names (country_id, language_id, name) VALUES (163, 2, 'Нидерландские Антильские острова');
INSERT INTO country_names (country_id, language_id, name) VALUES (164, 2, 'Новая Каледония');
INSERT INTO country_names (country_id, language_id, name) VALUES (165, 2, 'Новая Зеландия');
INSERT INTO country_names (country_id, language_id, name) VALUES (166, 2, 'Никарагуа');
INSERT INTO country_names (country_id, language_id, name) VALUES (167, 2, 'Нигер');
INSERT INTO country_names (country_id, language_id, name) VALUES (168, 2, 'Нигерия');
INSERT INTO country_names (country_id, language_id, name) VALUES (169, 2, 'Ниуэ');
INSERT INTO country_names (country_id, language_id, name) VALUES (170, 2, 'Остров Норфолк');
INSERT INTO country_names (country_id, language_id, name) VALUES (171, 2, 'Северные Марианские Острова');
INSERT INTO country_names (country_id, language_id, name) VALUES (172, 2, 'Норвегия');
INSERT INTO country_names (country_id, language_id, name) VALUES (173, 2, 'Оман');
INSERT INTO country_names (country_id, language_id, name) VALUES (174, 2, 'Пакистан');
INSERT INTO country_names (country_id, language_id, name) VALUES (175, 2, 'Палау');
INSERT INTO country_names (country_id, language_id, name) VALUES (176, 2, 'Сектор Газа');
INSERT INTO country_names (country_id, language_id, name) VALUES (177, 2, 'Панама');
INSERT INTO country_names (country_id, language_id, name) VALUES (178, 2, 'Папуа - Новая Гвинея');
INSERT INTO country_names (country_id, language_id, name) VALUES (179, 2, 'Парагвай');
INSERT INTO country_names (country_id, language_id, name) VALUES (180, 2, 'Перу');
INSERT INTO country_names (country_id, language_id, name) VALUES (181, 2, 'Филиппины');
INSERT INTO country_names (country_id, language_id, name) VALUES (182, 2, 'Острова Питкэрн');
INSERT INTO country_names (country_id, language_id, name) VALUES (183, 2, 'Польша');
INSERT INTO country_names (country_id, language_id, name) VALUES (184, 2, 'Португалия');
INSERT INTO country_names (country_id, language_id, name) VALUES (185, 2, 'Пуэрто-Рико ');
INSERT INTO country_names (country_id, language_id, name) VALUES (186, 2, 'Катар');
INSERT INTO country_names (country_id, language_id, name) VALUES (187, 2, 'Реюньон');
INSERT INTO country_names (country_id, language_id, name) VALUES (188, 2, 'Румыния');
INSERT INTO country_names (country_id, language_id, name) VALUES (189, 2, 'Руанда');
INSERT INTO country_names (country_id, language_id, name) VALUES (190, 2, 'Сен-Бартелеми (Карибы)');
INSERT INTO country_names (country_id, language_id, name) VALUES (191, 2, 'Остров Святой Елены');
INSERT INTO country_names (country_id, language_id, name) VALUES (192, 2, 'Сент-Китс и Невис');
INSERT INTO country_names (country_id, language_id, name) VALUES (193, 2, 'Сент-Люсия');
INSERT INTO country_names (country_id, language_id, name) VALUES (194, 2, 'Сен-Мартен (владение Франции)');
INSERT INTO country_names (country_id, language_id, name) VALUES (195, 2, 'Сен-Пьер и Микелон');
INSERT INTO country_names (country_id, language_id, name) VALUES (196, 2, 'Сент-Винсент и Гренадины');
INSERT INTO country_names (country_id, language_id, name) VALUES (197, 2, 'Самоа');
INSERT INTO country_names (country_id, language_id, name) VALUES (198, 2, 'Сан-Марино');
INSERT INTO country_names (country_id, language_id, name) VALUES (199, 2, 'Сан-Томе и Принсипи');
INSERT INTO country_names (country_id, language_id, name) VALUES (200, 2, 'Саудовская Аравия');
INSERT INTO country_names (country_id, language_id, name) VALUES (201, 2, 'Сенегал');
INSERT INTO country_names (country_id, language_id, name) VALUES (202, 2, 'Сербия');
INSERT INTO country_names (country_id, language_id, name) VALUES (203, 2, 'Сейшельские Острова');
INSERT INTO country_names (country_id, language_id, name) VALUES (204, 2, 'Сьерра-Леоне ');
INSERT INTO country_names (country_id, language_id, name) VALUES (205, 2, 'Сингапур');
INSERT INTO country_names (country_id, language_id, name) VALUES (206, 2, 'Словакия');
INSERT INTO country_names (country_id, language_id, name) VALUES (207, 2, 'Словения');
INSERT INTO country_names (country_id, language_id, name) VALUES (208, 2, 'Соломоновы Острова');
INSERT INTO country_names (country_id, language_id, name) VALUES (209, 2, 'Сомали');
INSERT INTO country_names (country_id, language_id, name) VALUES (210, 2, 'Южно-Африканская Республика');
INSERT INTO country_names (country_id, language_id, name) VALUES (211, 2, 'Южная Георгия и Южные Сандвичевы Острова');
INSERT INTO country_names (country_id, language_id, name) VALUES (212, 2, 'Южный Судан');
INSERT INTO country_names (country_id, language_id, name) VALUES (213, 2, 'Шри-Ланка');
INSERT INTO country_names (country_id, language_id, name) VALUES (214, 2, 'Судан');
INSERT INTO country_names (country_id, language_id, name) VALUES (215, 2, 'Суринам');
INSERT INTO country_names (country_id, language_id, name) VALUES (216, 2, 'Заморские территории Норвегии');
INSERT INTO country_names (country_id, language_id, name) VALUES (217, 2, 'Эсватини');
INSERT INTO country_names (country_id, language_id, name) VALUES (218, 2, 'Сирия');
INSERT INTO country_names (country_id, language_id, name) VALUES (219, 2, 'Тайвань');
INSERT INTO country_names (country_id, language_id, name) VALUES (220, 2, 'Таджикистан');
INSERT INTO country_names (country_id, language_id, name) VALUES (221, 2, 'Танзания');
INSERT INTO country_names (country_id, language_id, name) VALUES (222, 2, 'Тайланд');
INSERT INTO country_names (country_id, language_id, name) VALUES (223, 2, 'Восточный Тимор');
INSERT INTO country_names (country_id, language_id, name) VALUES (224, 2, 'Того');
INSERT INTO country_names (country_id, language_id, name) VALUES (225, 2, 'Токелау');
INSERT INTO country_names (country_id, language_id, name) VALUES (226, 2, 'Тонга');
INSERT INTO country_names (country_id, language_id, name) VALUES (227, 2, 'Тринидад и Тобаго');
INSERT INTO country_names (country_id, language_id, name) VALUES (228, 2, 'Тунис');
INSERT INTO country_names (country_id, language_id, name) VALUES (229, 2, 'Турция');
INSERT INTO country_names (country_id, language_id, name) VALUES (230, 2, 'Туркменистан');
INSERT INTO country_names (country_id, language_id, name) VALUES (231, 2, 'Теркс и Кайкос');
INSERT INTO country_names (country_id, language_id, name) VALUES (232, 2, 'Тувалу');
INSERT INTO country_names (country_id, language_id, name) VALUES (233, 2, 'Уганда');
INSERT INTO country_names (country_id, language_id, name) VALUES (234, 2, 'Украина');
INSERT INTO country_names (country_id, language_id, name) VALUES (235, 2, 'Объединённые Арабские Эмираты');
INSERT INTO country_names (country_id, language_id, name) VALUES (236, 2, 'Внешние малые острова США');
INSERT INTO country_names (country_id, language_id, name) VALUES (237, 2, 'Уругвай');
INSERT INTO country_names (country_id, language_id, name) VALUES (238, 2, 'Узбекистан');
INSERT INTO country_names (country_id, language_id, name) VALUES (239, 2, 'Вануату');
INSERT INTO country_names (country_id, language_id, name) VALUES (240, 2, 'Венесуэла');
INSERT INTO country_names (country_id, language_id, name) VALUES (241, 2, 'Вьетнам');
INSERT INTO country_names (country_id, language_id, name) VALUES (242, 2, 'Американские Виргинские Острова');
INSERT INTO country_names (country_id, language_id, name) VALUES (243, 2, 'Уоллис и Футуна');
INSERT INTO country_names (country_id, language_id, name) VALUES (244, 2, 'Западная Сахара');
INSERT INTO country_names (country_id, language_id, name) VALUES (245, 2, 'Йемен');
INSERT INTO country_names (country_id, language_id, name) VALUES (246, 2, 'Замбия');
INSERT INTO country_names (country_id, language_id, name) VALUES (247, 2, 'Зимбабве');
--------------------------------------------------------------------------------

-- Initialize base currency
INSERT INTO base_currency(id, since_timestamp, currency_id) VALUES (1, 946684800, 1);

COMMIT TRANSACTION;
PRAGMA foreign_keys = on;
