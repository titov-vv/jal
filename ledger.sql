--
-- File generated with SQLiteStudio v3.2.1 on Wed Dec 25 09:34:22 2019
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
    currency_name     TEXT,
    balance           REAL,
    balance_adj       REAL,
    days_unreconciled INTEGER,
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
    active_id  INTEGER     REFERENCES actives (id) ON DELETE RESTRICT
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
                         REFERENCES actives (id) ON DELETE NO ACTION
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
                         REFERENCES actives (id) ON DELETE NO ACTION
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


-- View: frontier
DROP VIEW IF EXISTS frontier;
CREATE VIEW frontier AS
    SELECT MAX(timestamp) AS ledger_frontier
      FROM sequence;


COMMIT TRANSACTION;
PRAGMA foreign_keys = on;
