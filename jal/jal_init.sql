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
    id              INTEGER   PRIMARY KEY
                              UNIQUE
                              NOT NULL,
    type_id         INTEGER   REFERENCES account_types (id) ON DELETE RESTRICT
                                                            ON UPDATE CASCADE
                              NOT NULL,
    name            TEXT (64) NOT NULL
                              UNIQUE,
    currency_id     INTEGER   REFERENCES assets (id) ON DELETE RESTRICT
                                                      ON UPDATE CASCADE
                              NOT NULL,
    active          INTEGER   DEFAULT (1)
                              NOT NULL ON CONFLICT REPLACE,
    number          TEXT (32),
    reconciled_on   INTEGER   DEFAULT (0)
                              NOT NULL ON CONFLICT REPLACE,
    organization_id INTEGER   REFERENCES agents (id) ON DELETE SET NULL
                                                     ON UPDATE CASCADE,
    country_id      INTEGER   REFERENCES countries (id) ON DELETE CASCADE
                                                        ON UPDATE CASCADE
                              DEFAULT (0)
                              NOT NULL
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
    id   INTEGER   PRIMARY KEY
                   UNIQUE
                   NOT NULL,
    name TEXT (32) NOT NULL
);


-- Table: assets
DROP TABLE IF EXISTS assets;

CREATE TABLE assets (
    id         INTEGER    PRIMARY KEY
                          UNIQUE
                          NOT NULL,
    name       TEXT (32)  NOT NULL,
    type_id    INTEGER    REFERENCES asset_types (id) ON DELETE RESTRICT
                                                      ON UPDATE CASCADE
                          NOT NULL,
    full_name  TEXT (128) NOT NULL,
    isin       TEXT (12)  DEFAULT ('')
                          NOT NULL,
    country_id INTEGER    REFERENCES countries (id) ON DELETE CASCADE
                                                    ON UPDATE CASCADE
                          NOT NULL
                          DEFAULT (0),
    src_id     INTEGER    REFERENCES data_sources (id) ON DELETE SET NULL
                                                       ON UPDATE CASCADE
                          NOT NULL
                          DEFAULT ( -1),
    expiry     INTEGER    NOT NULL
                          DEFAULT (0)
);


CREATE UNIQUE INDEX asset_name_isin_idx ON assets (
    name ASC,
    isin ASC,
    expiry ASC
);

-- Table: asset_reg_id
DROP TABLE IF EXISTS asset_reg_id;

CREATE TABLE asset_reg_id (
    asset_id INTEGER      PRIMARY KEY
                          UNIQUE
                          NOT NULL
                          REFERENCES assets (id) ON DELETE CASCADE
                                                 ON UPDATE CASCADE,
    reg_code VARCHAR (20) NOT NULL
);

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
    note       TEXT (1014)
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
    sid          INTEGER NOT NULL,
    book_account INTEGER NOT NULL
                         REFERENCES books (id) ON DELETE NO ACTION
                                               ON UPDATE NO ACTION,
    asset_id    INTEGER REFERENCES assets (id) ON DELETE SET NULL
                                               ON UPDATE SET NULL,
    account_id   INTEGER NOT NULL
                         REFERENCES accounts (id) ON DELETE NO ACTION
                                                  ON UPDATE NO ACTION,
    amount       REAL,
    value        REAL,
    peer_id      INTEGER REFERENCES agents (id) ON DELETE NO ACTION
                                                ON UPDATE NO ACTION,
    category_id  INTEGER REFERENCES categories (id) ON DELETE NO ACTION
                                                    ON UPDATE NO ACTION,
    tag_id       INTEGER REFERENCES tags (id) ON DELETE NO ACTION
                                              ON UPDATE NO ACTION
);


-- Table: ledger_sums
DROP TABLE IF EXISTS ledger_sums;

CREATE TABLE ledger_sums (
    sid          INTEGER NOT NULL,
    timestamp    INTEGER NOT NULL,
    book_account INTEGER NOT NULL
                         REFERENCES books (id) ON DELETE NO ACTION
                                               ON UPDATE NO ACTION,
    asset_id    INTEGER REFERENCES assets (id) ON DELETE SET NULL
                                               ON UPDATE SET NULL,
    account_id   INTEGER NOT NULL
                         REFERENCES accounts (id) ON DELETE NO ACTION
                                                  ON UPDATE NO ACTION,
    sum_amount   REAL,
    sum_value    REAL
);


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


-- Table: quotes
DROP TABLE IF EXISTS quotes;

CREATE TABLE quotes (
    id        INTEGER PRIMARY KEY
                      UNIQUE
                      NOT NULL,
    timestamp INTEGER NOT NULL,
    asset_id INTEGER REFERENCES assets (id) ON DELETE CASCADE
                                              ON UPDATE CASCADE
                      NOT NULL,
    quote     REAL
);


-- Table: sequence
DROP TABLE IF EXISTS sequence;

CREATE TABLE sequence (
    id           INTEGER PRIMARY KEY
                         NOT NULL
                         UNIQUE,
    timestamp    INTEGER NOT NULL,
    type         INTEGER NOT NULL,
    subtype      INTEGER NOT NULL,
    operation_id INTEGER NOT NULL
);


-- Table: settings
DROP TABLE IF EXISTS settings;

CREATE TABLE settings (
    id    INTEGER   PRIMARY KEY
                    NOT NULL
                    UNIQUE,
    name  TEXT (32) NOT NULL
                    UNIQUE,
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
    id           INTEGER   PRIMARY KEY
                           UNIQUE
                           NOT NULL,
    timestamp    INTEGER   NOT NULL,
    settlement   INTEGER   DEFAULT (0),
    number       TEXT (32) DEFAULT (''),
    account_id   INTEGER   REFERENCES accounts (id) ON DELETE CASCADE
                                                    ON UPDATE CASCADE
                           NOT NULL,
    asset_id     INTEGER   REFERENCES assets (id) ON DELETE RESTRICT
                                                  ON UPDATE CASCADE
                           NOT NULL,
    qty          REAL      NOT NULL
                           DEFAULT (0),
    price        REAL      NOT NULL
                           DEFAULT (0),
    fee          REAL      DEFAULT (0),
    note         TEXT (1024)
);


-- Table: deals
DROP TABLE IF EXISTS deals;

CREATE TABLE deals (
    id             INTEGER PRIMARY KEY
                           UNIQUE
                           NOT NULL,
    account_id     INTEGER NOT NULL,
    asset_id       INTEGER NOT NULL,
    open_sid  INTEGER NOT NULL,
    close_sid INTEGER NOT NULL,
    qty            REAL    NOT NULL
);


-- Table: transfers
DROP TABLE IF EXISTS transfers;

CREATE TABLE transfers (
    id                   INTEGER     PRIMARY KEY
                                     UNIQUE
                                     NOT NULL,
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


-- Index: by_sid
DROP INDEX IF EXISTS by_sid;
CREATE INDEX by_sid ON ledger_sums (sid);


-- View: all_operations
DROP VIEW IF EXISTS all_operations;
CREATE VIEW all_operations AS
    SELECT m.type,
           m.subtype,
           m.id,
           m.timestamp,
           m.account_id,
           a.name AS account,
           m.num_peer,
           m.asset_id,
           s.name AS asset,
           s.full_name AS asset_name,
           m.note,
           m.note2,
           m.amount,
           m.qty_trid,
           m.price,
           m.fee_tax,
           iif(coalesce(money.sum_amount, 0) > 0, money.sum_amount, coalesce(debt.sum_amount, 0) ) AS t_amount,
           m.t_qty,
           c.name AS currency,
           CASE WHEN m.timestamp <= a.reconciled_on THEN 1 ELSE 0 END AS reconciled
      FROM (
               SELECT 1 AS type,
                      iif(SUM(d.amount) < 0, -1, 1) AS subtype,
                      o.id,
                      timestamp,
                      p.name AS num_peer,
                      account_id,
                      sum(d.amount) AS amount,
                      o.alt_currency_id AS asset_id,
                      NULL AS qty_trid,
                      sum(d.amount_alt) AS price,
                      coalesce(sum(d.amount_alt)/sum(d.amount), 0) AS fee_tax,
                      NULL AS t_qty,
                      GROUP_CONCAT(d.note, '|') AS note,
                      GROUP_CONCAT(c.name, '|') AS note2
                 FROM actions AS o
                      LEFT JOIN
                      agents AS p ON o.peer_id = p.id
                      LEFT JOIN
                      action_details AS d ON o.id = d.pid
                      LEFT JOIN
                      categories AS c ON c.id = d.category_id
                GROUP BY o.id
               UNION ALL
               SELECT 2 AS type,
                      d.type AS subtype,
                      d.id,
                      d.timestamp,
                      d.number AS num_peer,
                      d.account_id,
                      d.amount AS amount,
                      d.asset_id,
                      SUM(coalesce(l.amount, 0) ) AS qty_trid,
                      NULL AS price,
                      d.tax AS fee_tax,
                      NULL AS t_qty,
                      d.note AS note,
                      c.name AS note2
                 FROM dividends AS d
                      LEFT JOIN
                      ledger AS l ON d.asset_id = l.asset_id AND
                                     d.account_id = l.account_id AND
                                     l.book_account = 4 AND
                                     l.timestamp <= d.timestamp
                      LEFT JOIN
                      assets AS a ON d.asset_id = a.id
                      LEFT JOIN
                      countries AS c ON a.country_id = c.id
                GROUP BY d.id
               UNION ALL
               SELECT 5 AS type,
                      ca.type AS subtype,
                      ca.id,
                      ca.timestamp,
                      ca.number AS num_peer,
                      ca.account_id,
                      ca.qty AS amount,
                      ca.asset_id,
                      ca.qty_new AS qty_trid,
                      ca.basis_ratio AS price,
                      ca.type AS fee_tax,
                      l.sum_amount AS t_qty,
                      a.name AS note,
                      a.full_name AS note2
                 FROM corp_actions AS ca
                      LEFT JOIN
                      assets AS a ON ca.asset_id_new = a.id
                      LEFT JOIN
                      sequence AS q ON q.type = 5 AND
                                       ca.id = q.operation_id
                      LEFT JOIN
                      ledger_sums AS l ON l.sid = q.id AND
                                          l.asset_id = ca.asset_id_new AND
                                          l.book_account = 4
               UNION ALL
               SELECT 3 AS type,
                      iif(t.qty < 0, -1, 1) AS subtype,
                      t.id,
                      t.timestamp,
                      t.number AS num_peer,
                      t.account_id,
                      -(t.price * t.qty) AS amount,
                      t.asset_id,
                      t.qty AS qty_trid,
                      t.price AS price,
                      t.fee AS fee_tax,
                      l.sum_amount AS t_qty,
                      t.note AS note,
                      NULL AS note2
                 FROM trades AS t
                      LEFT JOIN
                      sequence AS q ON q.type = 3 AND
                                       t.id = q.operation_id
                      LEFT JOIN
                      ledger_sums AS l ON l.sid = q.id AND
                                          l.book_account = 4
               UNION ALL
               SELECT 4 AS type,
                      t.subtype,
                      t.id,
                      t.timestamp,
                      c.name AS num_peer,
                      t.account_id,
                      t.amount,
                      NULL AS asset_id,
                      NULL AS qty_trid,
                      t.rate AS price,
                      NULL AS fee_tax,
                      NULL AS t_qty,
                      t.note,
                      a.name AS note2
                 FROM (
                          SELECT id,
                                 withdrawal_timestamp AS timestamp,
                                 withdrawal_account AS account_id,
                                 deposit_account AS account2_id,
                                 -withdrawal AS amount,
                                 deposit / withdrawal AS rate,
                                 -1 AS subtype,
                                 note
                            FROM transfers
                          UNION ALL
                          SELECT id,
                                 withdrawal_timestamp AS timestamp,
                                 fee_account AS account_id,
                                 NULL AS account2_id,
                                 -fee AS amount,
                                 1 AS rate,
                                 0 AS subtype,
                                 note
                            FROM transfers
                           WHERE NOT fee IS NULL
                          UNION ALL
                          SELECT id,
                                 deposit_timestamp AS timestamp,
                                 deposit_account AS account_id,
                                 withdrawal_account AS account2_id,
                                 deposit AS amount,
                                 withdrawal / deposit AS rate,
                                 1 AS subtype,
                                 note
                            FROM transfers
                           ORDER BY id
                      )
                      AS t
                      LEFT JOIN
                      accounts AS a ON a.id = t.account2_id
                      LEFT JOIN
                      assets AS c ON c.id = a.currency_id
                ORDER BY timestamp
           )
           AS m
           LEFT JOIN
           accounts AS a ON m.account_id = a.id
           LEFT JOIN
           assets AS s ON m.asset_id = s.id
           LEFT JOIN
           assets AS c ON a.currency_id = c.id
           LEFT JOIN
           sequence AS q ON m.type = q.type AND
                            m.subtype = q.subtype AND
                            m.id = q.operation_id
           LEFT JOIN
           ledger_sums AS money ON money.sid = q.id AND
                                   money.account_id = m.account_id AND
                                   money.book_account = 3
           LEFT JOIN
           ledger_sums AS debt ON debt.sid = q.id AND
                                  debt.account_id = m.account_id AND
                                  debt.book_account = 5;


-- View: all_transactions
DROP VIEW IF EXISTS all_transactions;
CREATE VIEW all_transactions AS
    SELECT at.*,
           a.currency_id AS currency
      FROM (
               SELECT 1 AS type,
                      a.id,
                      a.timestamp,
                      CASE WHEN SUM(d.amount) < 0 THEN -COUNT(d.amount) ELSE COUNT(d.amount) END AS subtype,
                      a.account_id AS account,
                      NULL AS asset,
                      SUM(d.amount) AS amount,
                      d.category_id AS category,
                      NULL AS price,
                      NULL AS fee_tax,
                      a.peer_id AS peer,
                      d.tag_id AS tag
                 FROM actions AS a
                      LEFT JOIN
                      action_details AS d ON a.id = d.pid
                GROUP BY a.id
               UNION ALL
               SELECT 2 AS type,
                      d.id,
                      d.timestamp,
                      d.type AS subtype,
                      d.account_id AS account,
                      d.asset_id AS asset,
                      d.amount AS amount,
                      NULL AS category,
                      NULL AS price,
                      d.tax AS fee_tax,
                      a.organization_id AS peer,
                      NULL AS tag
                 FROM dividends AS d
                      LEFT JOIN
                      accounts AS a ON a.id = d.account_id
               UNION ALL
               SELECT 5 AS type,
                      a.id,
                      a.timestamp,
                      a.type AS subtype,
                      a.account_id AS account,
                      a.asset_id AS asset,
                      a.qty AS amount,
                      NULL AS category,
                      a.qty_new AS price,
                      a.basis_ratio AS fee_tax,
                      a.asset_id_new AS peer,
                      NULL AS tag
                 FROM corp_actions AS a
               UNION ALL
               SELECT 3 AS type,
                      t.id,
                      t.timestamp,
                      iif(t.qty < 0, -1, 1) AS subtype,
                      t.account_id AS account,
                      t.asset_id AS asset,
                      t.qty AS amount,
                      NULL AS category,
                      t.price AS price,
                      t.fee AS fee_tax,
                      a.organization_id AS peer,
                      NULL AS tag
                 FROM trades AS t
                      LEFT JOIN
                      accounts AS a ON a.id = t.account_id
               UNION ALL
               SELECT 4 AS type,
                      id,
                      withdrawal_timestamp AS timestamp,
                      -1 AS subtype,
                      withdrawal_account AS account,
                      asset AS asset,
                      withdrawal AS amount,
                      NULL AS category,
                      NULL AS price,
                      NULL AS fee_tax,
                      NULL AS peer,
                      NULL AS tag
                 FROM transfers AS t
               UNION ALL
               SELECT 4 AS type,
                      id,
                      withdrawal_timestamp AS timestamp,
                      0 AS subtype,
                      fee_account AS account,
                      asset AS asset,
                      fee AS amount,
                      NULL AS category,
                      NULL AS price,
                      NULL AS fee_tax,
                      NULL AS peer,
                      NULL AS tag
                 FROM transfers AS t
                 WHERE NOT fee_account IS NULL
               UNION ALL
               SELECT 4 AS type,
                      id,
                      deposit_timestamp AS timestamp,
                      1 AS subtype,
                      deposit_account AS account,
                      asset AS asset,
                      deposit AS amount,
                      NULL AS category,
                      NULL AS price,
                      NULL AS fee_tax,
                      NULL AS peer,
                      NULL AS tag
                 FROM transfers AS t
                ORDER BY timestamp,
                         type,
                         subtype,
                         id
           )
           AS at
           LEFT JOIN
           accounts AS a ON at.account = a.id;


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
    SELECT id,
           name
      FROM assets
     WHERE type_id = 1;


-- View: frontier
DROP VIEW IF EXISTS frontier;
CREATE VIEW frontier AS
    SELECT MAX(sequence.timestamp) AS ledger_frontier
      FROM sequence;


-- View: deals_ext
DROP VIEW IF EXISTS deals_ext;
CREATE VIEW deals_ext AS
    SELECT d.account_id,
           ac.name AS account,
           d.asset_id,
           at.name AS asset,
           coalesce(ot.timestamp, oca.timestamp) AS open_timestamp,
           coalesce(ct.timestamp, cca.timestamp) AS close_timestamp,
           coalesce(ot.price, ols.sum_value / ols.sum_amount) AS open_price,
           coalesce(ct.price, ot.price) AS close_price,
           d.qty AS qty,
           coalesce(ot.fee * abs(d.qty / ot.qty), 0) + coalesce(ct.fee * abs(d.qty / ct.qty), 0) AS fee,
           d.qty * (coalesce(ct.price, ot.price) - coalesce(ot.price, ols.sum_value / ols.sum_amount) ) - (coalesce(ot.fee * abs(d.qty / ot.qty), 0) + coalesce(ct.fee * abs(d.qty / ct.qty), 0) ) AS profit,
           coalesce(100 * (d.qty * (coalesce(ct.price, ot.price) - coalesce(ot.price, ols.sum_value / ols.sum_amount) ) - (coalesce(ot.fee * abs(d.qty / ot.qty), 0) + coalesce(ct.fee * abs(d.qty / ct.qty), 0) ) ) / abs(d.qty * coalesce(ot.price, ols.sum_value / ols.sum_amount) ), 0) AS rel_profit,
           coalesce(oca.type, -cca.type) AS corp_action
      FROM deals AS d
           LEFT JOIN
           sequence AS os ON d.open_sid = os.id
           LEFT JOIN
           trades AS ot ON ot.id = os.operation_id AND
                           os.type = 3
           LEFT JOIN
           corp_actions AS oca ON oca.id = os.operation_id AND
                                  os.type = 5
           LEFT JOIN
           ledger_sums AS ols ON ols.sid = d.open_sid AND
                                 ols.asset_id = d.asset_id
           LEFT JOIN
           sequence AS cs ON d.close_sid = cs.id
           LEFT JOIN
           trades AS ct ON ct.id = cs.operation_id AND
                           cs.type = 3
           LEFT JOIN
           corp_actions AS cca ON cca.id = cs.operation_id AND
                                  cs.type = 5
           LEFT JOIN
           accounts AS ac ON d.account_id = ac.id
           LEFT JOIN
           assets AS at ON d.asset_id = at.id
     WHERE NOT (os.type = 5 AND
                cs.type = 5)
     ORDER BY close_timestamp,
              open_timestamp;


-- Trigger: action_details_after_delete
DROP TRIGGER IF EXISTS action_details_after_delete;
CREATE TRIGGER action_details_after_delete
         AFTER DELETE
            ON action_details
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger
          WHERE timestamp >= (
                                 SELECT timestamp
                                   FROM actions
                                  WHERE id = OLD.pid
                             );
    DELETE FROM sequence
          WHERE timestamp >= (
                                 SELECT timestamp
                                   FROM actions
                                  WHERE id = OLD.pid
                             );
    DELETE FROM ledger_sums
          WHERE timestamp >= (
                                 SELECT timestamp
                                   FROM actions
                                  WHERE id = OLD.pid
                             );
END;


-- Trigger: action_details_after_insert
DROP TRIGGER IF EXISTS action_details_after_insert;
CREATE TRIGGER action_details_after_insert
         AFTER INSERT
            ON action_details
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger
          WHERE timestamp >= (
                                 SELECT timestamp
                                   FROM actions
                                  WHERE id = NEW.pid
                             );
    DELETE FROM sequence
          WHERE timestamp >= (
                                 SELECT timestamp
                                   FROM actions
                                  WHERE id = NEW.pid
                             );
    DELETE FROM ledger_sums
          WHERE timestamp >= (
                                 SELECT timestamp
                                   FROM actions
                                  WHERE id = NEW.pid
                             );
END;

-- Trigger: action_details_after_update
DROP TRIGGER IF EXISTS action_details_after_update;
CREATE TRIGGER action_details_after_update
         AFTER UPDATE
            ON action_details
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger
          WHERE timestamp >= (
                                 SELECT timestamp
                                   FROM actions
                                  WHERE id = OLD.pid
                             );
    DELETE FROM sequence
          WHERE timestamp >= (
                                 SELECT timestamp
                                   FROM actions
                                  WHERE id = OLD.pid
                             );
    DELETE FROM ledger_sums
          WHERE timestamp >= (
                                 SELECT timestamp
                                   FROM actions
                                  WHERE id = OLD.pid
                             );
END;

-- Trigger: actions_after_delete
DROP TRIGGER IF EXISTS actions_after_delete;
CREATE TRIGGER actions_after_delete
         AFTER DELETE
            ON actions
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM action_details
          WHERE pid = OLD.id;
    DELETE FROM ledger
          WHERE timestamp >= OLD.timestamp;
    DELETE FROM sequence
          WHERE timestamp >= OLD.timestamp;
    DELETE FROM ledger_sums
          WHERE timestamp >= OLD.timestamp;
END;

-- Trigger: actions_after_insert
DROP TRIGGER IF EXISTS actions_after_insert;
CREATE TRIGGER actions_after_insert
         AFTER INSERT
            ON actions
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger
          WHERE timestamp >= NEW.timestamp;
    DELETE FROM sequence
          WHERE timestamp >= NEW.timestamp;
    DELETE FROM ledger_sums
          WHERE timestamp >= NEW.timestamp;
END;

-- Trigger: actions_after_update
DROP TRIGGER IF EXISTS actions_after_update;
CREATE TRIGGER actions_after_update
         AFTER UPDATE OF timestamp,
                         account_id,
                         peer_id
            ON actions
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger
          WHERE timestamp >= OLD.timestamp OR
                timestamp >= NEW.timestamp;
    DELETE FROM sequence
          WHERE timestamp >= OLD.timestamp OR
                timestamp >= NEW.timestamp;
    DELETE FROM ledger_sums
          WHERE timestamp >= OLD.timestamp OR
                timestamp >= NEW.timestamp;
END;

-- Trigger: dividends_after_delete
DROP TRIGGER IF EXISTS dividends_after_delete;
CREATE TRIGGER dividends_after_delete
         AFTER DELETE
            ON dividends
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger
          WHERE timestamp >= OLD.timestamp;
    DELETE FROM sequence
          WHERE timestamp >= OLD.timestamp;
    DELETE FROM ledger_sums
          WHERE timestamp >= OLD.timestamp;
END;

-- Trigger: dividends_after_insert
DROP TRIGGER IF EXISTS dividends_after_insert;
CREATE TRIGGER dividends_after_insert
         AFTER INSERT
            ON dividends
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger
          WHERE timestamp >= NEW.timestamp;
    DELETE FROM sequence
          WHERE timestamp >= NEW.timestamp;
    DELETE FROM ledger_sums
          WHERE timestamp >= NEW.timestamp;
END;

-- Trigger: dividends_after_update
DROP TRIGGER IF EXISTS dividends_after_update;
CREATE TRIGGER dividends_after_update
         AFTER UPDATE OF timestamp,
                         account_id,
                         asset_id,
                         amount,
                         tax
            ON dividends
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger
          WHERE timestamp >= OLD.timestamp OR
                timestamp >= NEW.timestamp;
    DELETE FROM sequence
          WHERE timestamp >= OLD.timestamp OR
                timestamp >= NEW.timestamp;
    DELETE FROM ledger_sums
          WHERE timestamp >= OLD.timestamp OR
                timestamp >= NEW.timestamp;
END;

-- Trigger: trades_after_delete
DROP TRIGGER IF EXISTS trades_after_delete;
CREATE TRIGGER trades_after_delete
         AFTER DELETE
            ON trades
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger
          WHERE timestamp >= OLD.timestamp;
    DELETE FROM sequence
          WHERE timestamp >= OLD.timestamp;
    DELETE FROM ledger_sums
          WHERE timestamp >= OLD.timestamp;
END;

-- Trigger: trades_after_insert
DROP TRIGGER IF EXISTS trades_after_insert;
CREATE TRIGGER trades_after_insert
         AFTER INSERT
            ON trades
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger
          WHERE timestamp >= NEW.timestamp;
    DELETE FROM sequence
          WHERE timestamp >= NEW.timestamp;
    DELETE FROM ledger_sums
          WHERE timestamp >= NEW.timestamp;
END;

-- Trigger: trades_after_update
DROP TRIGGER IF EXISTS trades_after_update;
CREATE TRIGGER trades_after_update
         AFTER UPDATE OF timestamp,
                         account_id,
                         asset_id,
                         qty,
                         price,
                         fee
            ON trades
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger
          WHERE timestamp >= OLD.timestamp OR
                timestamp >= NEW.timestamp;
    DELETE FROM sequence
          WHERE timestamp >= OLD.timestamp OR
                timestamp >= NEW.timestamp;
    DELETE FROM ledger_sums
          WHERE timestamp >= OLD.timestamp OR
                timestamp >= NEW.timestamp;
END;

-- Triggers for corp_actions table
DROP TRIGGER IF EXISTS corp_after_delete;
CREATE TRIGGER corp_after_delete
         AFTER DELETE
            ON corp_actions
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger
          WHERE timestamp >= OLD.timestamp;
    DELETE FROM sequence
          WHERE timestamp >= OLD.timestamp;
    DELETE FROM ledger_sums
          WHERE timestamp >= OLD.timestamp;
END;

DROP TRIGGER IF EXISTS corp_after_insert;
CREATE TRIGGER corp_after_insert
         AFTER INSERT
            ON corp_actions
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger
          WHERE timestamp >= NEW.timestamp;
    DELETE FROM sequence
          WHERE timestamp >= NEW.timestamp;
    DELETE FROM ledger_sums
          WHERE timestamp >= NEW.timestamp;
END;

DROP TRIGGER IF EXISTS corp_after_update;
CREATE TRIGGER corp_after_update
         AFTER UPDATE OF timestamp,
                         account_id,
                         type,
                         asset_id,
                         qty,
                         asset_id_new,
                         qty_new
            ON corp_actions
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger
          WHERE timestamp >= OLD.timestamp OR
                timestamp >= NEW.timestamp;
    DELETE FROM sequence
          WHERE timestamp >= OLD.timestamp OR
                timestamp >= NEW.timestamp;
    DELETE FROM ledger_sums
          WHERE timestamp >= OLD.timestamp OR
                timestamp >= NEW.timestamp;
END;

-- Trigger: transfers_after_delete
DROP TRIGGER IF EXISTS transfers_after_delete;
CREATE TRIGGER transfers_after_delete
         AFTER DELETE
            ON transfers
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger
          WHERE timestamp >= OLD.withdrawal_timestamp OR timestamp >= OLD.deposit_timestamp;
    DELETE FROM sequence
          WHERE timestamp >= OLD.withdrawal_timestamp OR timestamp >= OLD.deposit_timestamp;
    DELETE FROM ledger_sums
          WHERE timestamp >= OLD.withdrawal_timestamp OR timestamp >= OLD.deposit_timestamp;
END;

-- Trigger: transfers_after_insert
DROP TRIGGER IF EXISTS transfers_after_insert;
CREATE TRIGGER transfers_after_insert
         AFTER INSERT
            ON transfers
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger
          WHERE timestamp >= NEW.withdrawal_timestamp OR timestamp >= NEW.deposit_timestamp;
    DELETE FROM sequence
          WHERE timestamp >= NEW.withdrawal_timestamp OR timestamp >= NEW.deposit_timestamp;
    DELETE FROM ledger_sums
          WHERE timestamp >= NEW.withdrawal_timestamp OR timestamp >= NEW.deposit_timestamp;
END;

-- Trigger: transfers_after_update
DROP TRIGGER IF EXISTS transfers_after_update;
CREATE TRIGGER transfers_after_update
         AFTER UPDATE OF withdrawal_timestamp,
                         deposit_timestamp,
                         withdrawal_account,
                         deposit_account,
                         fee_account,
                         withdrawal,
                         deposit,
                         fee,
                         asset
            ON transfers
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger
          WHERE timestamp >= OLD.withdrawal_timestamp OR timestamp >= OLD.deposit_timestamp OR
                timestamp >= NEW.withdrawal_timestamp OR timestamp >= NEW.deposit_timestamp;
    DELETE FROM sequence
          WHERE timestamp >= OLD.withdrawal_timestamp OR timestamp >= OLD.deposit_timestamp OR
                timestamp >= NEW.withdrawal_timestamp OR timestamp >= NEW.deposit_timestamp;
    DELETE FROM ledger_sums
          WHERE timestamp >= OLD.withdrawal_timestamp OR timestamp >= OLD.deposit_timestamp OR
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
INSERT INTO settings(id, name, value) VALUES (0, 'SchemaVersion', 27);
INSERT INTO settings(id, name, value) VALUES (1, 'TriggersEnabled', 1);
INSERT INTO settings(id, name, value) VALUES (2, 'BaseCurrency', 1);
INSERT INTO settings(id, name, value) VALUES (3, 'Language', 1);
INSERT INTO settings(id, name, value) VALUES (4, 'RuTaxClientSecret', 'IyvrAbKt9h/8p6a7QPh8gpkXYQ4=');
INSERT INTO settings(id, name, value) VALUES (5, 'RuTaxSessionId', '');
INSERT INTO settings(id, name, value) VALUES (6, 'RuTaxRefreshToken', '');

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
INSERT INTO asset_types (id, name) VALUES (4, 'Funds');
INSERT INTO asset_types (id, name) VALUES (5, 'Commodities');
INSERT INTO asset_types (id, name) VALUES (6, 'Derivatives');
INSERT INTO asset_types (id, name) VALUES (7, 'Forex');

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
INSERT INTO assets (id, name, type_id, full_name, src_id) VALUES (1, 'RUB', 1, 'Российский Рубль', -1);
INSERT INTO assets (id, name, type_id, full_name, src_id) VALUES (2, 'USD', 1, 'Доллар США', 0);
INSERT INTO assets (id, name, type_id, full_name, src_id) VALUES (3, 'EUR', 1, 'Евро', 0);

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
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (30, 'Antarctica ', 'aq', '010', 0);
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
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (57, 'Cayman Islands ', 'ky', '136', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (58, 'Central African Republic', 'cf', '140', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (59, 'Chad', 'td', '148', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (60, 'Chile', 'cl', '152', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (61, 'Hong Kong, SAR China', 'hk', '344', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (62, 'Macao, SAR China', 'mo', '446', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (63, 'Christmas Island', 'cx', '162', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (64, 'Cocos (Keeling) Islands', 'cc', '166', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (65, 'Colombia', 'co', '170', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (66, 'Comoros', 'km', '174', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (67, 'Congo (Brazzaville) ', 'cg', '178', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (68, 'Congo, (Kinshasa)', 'cd', '180', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (69, 'Cook Islands ', 'ck', '184', 0);
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
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (87, 'Falkland Islands (Malvinas) ', 'fk', '238', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (88, 'Faroe Islands', 'fo', '234', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (89, 'Fiji', 'fj', '242', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (90, 'French Guiana', 'gf', '254', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (91, 'French Polynesia', 'pf', '258', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (92, 'French Southern Territories ', 'tf', '260', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (93, 'Gabon', 'ga', '266', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (94, 'Gambia', 'gm', '270', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (95, 'Georgia', 'ge', '268', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (96, 'Ghana', 'gh', '288', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (97, 'Gibraltar ', 'gi', '292', 0);
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
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (117, 'Isle of Man ', 'im', '833', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (118, 'Israel ', 'il', '376', 1);
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
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (169, 'Niue ', 'nu', '570', 0);
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
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (182, 'Pitcairn ', 'pn', '612', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (183, 'Poland', 'pl', '616', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (184, 'Portugal', 'pt', '620', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (185, 'Puerto Rico', 'pr', '630', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (186, 'Qatar', 'qa', '634', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (187, 'Réunion', 're', '638', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (188, 'Romania', 'ro', '642', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (189, 'Rwanda', 'rw', '646', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (190, 'Saint-Barthélemy', 'bl', '652', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (191, 'Saint Helena ', 'sh', '654', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (192, 'Saint Kitts and Nevis', 'kn', '659', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (193, 'Saint Lucia', 'lc', '662', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (194, 'Saint-Martin (French part)', 'mf', '663', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (195, 'Saint Pierre and Miquelon ', 'pm', '666', 0);
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
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (216, 'Svalbard and Jan Mayen Islands ', 'sj', '744', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (217, 'Swaziland', 'sz', '748', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (218, 'Syrian Arab Republic (Syria)', 'sy', '760', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (219, 'Taiwan, Republic of China ', 'tw', '158', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (220, 'Tajikistan', 'tj', '762', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (221, 'Tanzania, United Republic of ', 'tz', '834', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (222, 'Thailand', 'th', '764', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (223, 'Timor-Leste', 'tl', '626', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (224, 'Togo', 'tg', '768', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (225, 'Tokelau ', 'tk', '772', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (226, 'Tonga', 'to', '776', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (227, 'Trinidad and Tobago', 'tt', '780', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (228, 'Tunisia', 'tn', '788', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (229, 'Turkey', 'tr', '792', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (230, 'Turkmenistan', 'tm', '795', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (231, 'Turks and Caicos Islands ', 'tc', '796', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (232, 'Tuvalu', 'tv', '798', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (233, 'Uganda', 'ug', '800', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (234, 'Ukraine', 'ua', '804', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (235, 'United Arab Emirates', 'ae', '784', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (236, 'US Minor Outlying Islands ', 'um', '581', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (237, 'Uruguay', 'uy', '858', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (238, 'Uzbekistan', 'uz', '860', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (239, 'Vanuatu', 'vu', '548', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (240, 'Venezuela (Bolivarian Republic)', 've', '862', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (241, 'Viet Nam', 'vn', '704', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (242, 'Virgin Islands, US', 'vi', '850', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (243, 'Wallis and Futuna Islands ', 'wf', '876', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (244, 'Western Sahara ', 'eh', '732', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (245, 'Yemen', 'ye', '887', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (246, 'Zambia', 'zm', '894', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (247, 'Zimbabwe', 'zw', '716', 0);

-- Initialize rate for base currency
INSERT INTO quotes (id, timestamp, asset_id, quote) VALUES (1, 946684800, 1, 1.0);

COMMIT TRANSACTION;
PRAGMA foreign_keys = on;
