--
-- File generated with SQLiteStudio v3.2.1 on Sun Dec 29 18:19:54 2019
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
    currency_id     INTEGER   REFERENCES actives (id) ON DELETE RESTRICT
                                                      ON UPDATE CASCADE
                              NOT NULL,
    active          INTEGER,
    number          TEXT (32),
    reconciled_on   INTEGER   DEFAULT (0),
    organization_id INTEGER   REFERENCES agents (id) ON DELETE SET NULL
                                                     ON UPDATE CASCADE
);


-- Table: action_details
DROP TABLE IF EXISTS action_details;

CREATE TABLE action_details (
    pid         INTEGER    REFERENCES actions (id) ON DELETE CASCADE
                                                   ON UPDATE CASCADE,
    type        INTEGER    NOT NULL,
    category_id INTEGER    REFERENCES categories (id) ON DELETE RESTRICT
                                                      ON UPDATE CASCADE
                           NOT NULL,
    tag_id      INTEGER    REFERENCES tags (id) ON DELETE SET NULL
                                                ON UPDATE CASCADE,
    sum         REAL       NOT NULL,
    alt_sum     REAL,
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
    peer_id         INTEGER REFERENCES agents (id) ON DELETE RESTRICT
                                                   ON UPDATE CASCADE
                            NOT NULL,
    alt_currency_id INTEGER REFERENCES actives (id) ON DELETE RESTRICT
                                                    ON UPDATE CASCADE
);


-- Table: active_types
DROP TABLE IF EXISTS active_types;

CREATE TABLE active_types (
    id   INTEGER   PRIMARY KEY
                   UNIQUE
                   NOT NULL,
    name TEXT (32) NOT NULL
);


-- Table: actives
DROP TABLE IF EXISTS actives;

CREATE TABLE actives (
    id        INTEGER    PRIMARY KEY
                         UNIQUE
                         NOT NULL,
    name      TEXT (32)  UNIQUE
                         NOT NULL,
    type_id   INTEGER    REFERENCES active_types (id) ON DELETE RESTRICT
                                                      ON UPDATE CASCADE
                         NOT NULL,
    full_name TEXT (128) NOT NULL,
    isin      TEXT (12),
    web_id    TEXT (32),
    src_id    INTEGER    REFERENCES data_sources (id) ON DELETE SET NULL
                                                      ON UPDATE CASCADE
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


-- Table: balances
DROP TABLE IF EXISTS balances;

CREATE TABLE balances (
    level1            INTEGER,
    level2            INTEGER,
    account_name      TEXT    NOT NULL,
    balance           REAL,
    currency_name     TEXT,
    balance_adj       REAL,
    days_unreconciled INTEGER,
    active            INTEGER
);


-- Table: balances_aux
DROP TABLE IF EXISTS balances_aux;

CREATE TABLE balances_aux (
    account_type      INTEGER NOT NULL,
    account           INTEGER NOT NULL,
    currency          INTEGER NOT NULL,
    balance           REAL,
    balance_adj       REAL,
    unreconciled_days INTEGER,
    active            INTEGER
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
    number     TEXT (32),
    account_id INTEGER     REFERENCES accounts (id) ON DELETE CASCADE
                                                    ON UPDATE CASCADE
                           NOT NULL,
    active_id  INTEGER     REFERENCES actives (a_id) ON DELETE RESTRICT
                                                     ON UPDATE CASCADE
                           NOT NULL,
    sum        REAL        NOT NULL,
    sum_tax    REAL,
    note       TEXT (1014),
    note_tax   TEXT (64) 
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
    active_id    INTEGER NOT NULL
                         REFERENCES actives (a_id) ON DELETE NO ACTION
                                                   ON UPDATE NO ACTION,
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
    active_id    INTEGER NOT NULL
                         REFERENCES actives (a_id) ON DELETE NO ACTION
                                                   ON UPDATE NO ACTION,
    account_id   INTEGER NOT NULL
                         REFERENCES accounts (id) ON DELETE NO ACTION
                                                  ON UPDATE NO ACTION,
    sum_amount   REAL,
    sum_value    REAL
);


-- Table: quotes
DROP TABLE IF EXISTS quotes;

CREATE TABLE quotes (
    id        INTEGER PRIMARY KEY
                      UNIQUE
                      NOT NULL,
    timestamp INTEGER NOT NULL,
    active_id INTEGER REFERENCES actives (id) ON DELETE CASCADE
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
    operation_id INTEGER NOT NULL
);


-- Table: t_last_dates
DROP TABLE IF EXISTS t_last_dates;

CREATE TABLE t_last_dates (
    account_id INTEGER NOT NULL,
    timestamp  INTEGER NOT NULL
);


-- Table: t_last_quotes
DROP TABLE IF EXISTS t_last_quotes;

CREATE TABLE t_last_quotes (
    timestamp INTEGER NOT NULL,
    active_id INTEGER NOT NULL,
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


-- Table: trades
DROP TABLE IF EXISTS trades;

CREATE TABLE trades (
    id           INTEGER   PRIMARY KEY
                           UNIQUE
                           NOT NULL,
    timestamp    INTEGER   NOT NULL,
    settlement   INTEGER,
    type         INTEGER   NOT NULL,
    number       TEXT (32),
    account_id   INTEGER   REFERENCES accounts (id) ON DELETE CASCADE
                                                    ON UPDATE CASCADE
                           NOT NULL,
    active_id    INTEGER   REFERENCES actives (id) ON DELETE RESTRICT
                                                   ON UPDATE CASCADE,
    qty          REAL      NOT NULL,
    price        REAL      NOT NULL,
    coupon       REAL,
    fee_broker   REAL,
    fee_exchange REAL,
    sum          REAL      NOT NULL
);


-- Table: transfers
DROP TABLE IF EXISTS transfers;

CREATE TABLE transfers (
    id      INTEGER PRIMARY KEY
                    UNIQUE
                    NOT NULL,
    from_id INTEGER REFERENCES actions (id) ON DELETE RESTRICT
                                            ON UPDATE CASCADE
                    NOT NULL,
    to_id   INTEGER REFERENCES actions (id) ON DELETE RESTRICT
                                            ON UPDATE CASCADE
                    NOT NULL,
    fee_id  INTEGER REFERENCES actions (id) ON DELETE RESTRICT
                                            ON UPDATE CASCADE
);


-- Index: by_sid
DROP INDEX IF EXISTS by_sid;

CREATE INDEX by_sid ON ledger_sums (
    sid
);


-- View: all_operations
DROP VIEW IF EXISTS all_operations;
CREATE VIEW all_operations AS
    SELECT m.type,
           m.id,
           m.timestamp,
           m.account_id,
           a.name AS account,
           m.num_peer,
           m.active_id,
           s.name AS active,
           s.full_name AS active_name,
           m.note,
           m.note2,
           m.amount,
           m.qty_trid,
           m.price,
           m.fee_tax,
           l.sum_amount AS t_amount,
           m.t_qty,
           c.name AS currency,
           CASE WHEN m.timestamp <= a.reconciled_on THEN 1 ELSE 0 END AS reconciled
      FROM (
               SELECT 1 AS type,
                      o.id,
                      timestamp,
                      p.name AS num_peer,
                      account_id,
                      sum(d.type * d.sum) AS amount,
                      o.alt_currency_id AS active_id,
                      coalesce( -t1.id, t2.id, 0) AS qty_trid,
                      sum(d.type * d.alt_sum) AS price,
                      NULL AS fee_tax,
                      NULL AS t_qty,
                      NULL AS note,
                      NULL AS note2
                 FROM actions AS o
                      LEFT JOIN
                      agents AS p ON o.peer_id = p.id
                      LEFT JOIN
                      transfers AS t1 ON t1.from_id = o.id
                      LEFT JOIN
                      transfers AS t2 ON t2.to_id = o.id
                      LEFT JOIN
                      action_details AS d ON o.id = d.pid
                GROUP BY o.id
               UNION ALL
               SELECT 2 AS type,
                      d.id,
                      d.timestamp,
                      d.number AS num_peer,
                      d.account_id,
                      d.sum AS amount,
                      d.active_id,
                      SUM(coalesce(l.amount, 0) ) AS qty_trid,
                      NULL AS price,
                      d.sum_tax AS fee_tax,
                      NULL AS t_qty,
                      d.note AS note,
                      d.note_tax AS note2
                 FROM dividends AS d
                      LEFT JOIN
                      ledger AS l ON d.active_id = l.active_id AND 
                                     d.account_id = l.account_id AND 
                                     l.book_account = 4 AND 
                                     l.timestamp <= d.timestamp
                GROUP BY d.id
               UNION ALL
               SELECT 3 AS type,
                      t.id,
                      t.timestamp,
                      t.number AS num_peer,
                      t.account_id,
                      t.sum AS amount,
                      t.active_id,
                      (t.type * t.qty) AS qty_trid,
                      t.price AS price,
                      t.fee_broker + t.fee_exchange AS fee_tax,
                      l.sum_amount AS t_qty,
                      NULL AS note,
                      NULL AS note2
                 FROM trades AS t
                      LEFT JOIN
                      sequence AS q ON q.type = 3 AND 
                                       t.id = q.operation_id
                      LEFT JOIN
                      ledger_sums AS l ON l.sid = q.id AND 
                                          l.book_account = 4
                ORDER BY timestamp
           )
           AS m
           LEFT JOIN
           accounts AS a ON m.account_id = a.id
           LEFT JOIN
           actives AS s ON m.active_id = s.id
           LEFT JOIN
           actives AS c ON a.currency_id = c.id
           LEFT JOIN
           sequence AS q ON m.type = q.type AND 
                            m.id = q.operation_id
           LEFT JOIN
           ledger_sums AS l ON l.sid = q.id AND 
                               (l.book_account = 3 OR 
                                l.book_account = 5);


-- View: frontier
DROP VIEW IF EXISTS frontier;
CREATE VIEW frontier AS
    SELECT MAX(timestamp) AS ledger_frontier
      FROM sequence;


COMMIT TRANSACTION;
PRAGMA foreign_keys = on;
