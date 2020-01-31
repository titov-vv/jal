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
    id          INTEGER    PRIMARY KEY
                           NOT NULL
                           UNIQUE,
    pid         INTEGER    REFERENCES actions (id) ON DELETE CASCADE
                                                   ON UPDATE CASCADE
                           NOT NULL,
    category_id INTEGER    REFERENCES categories (id) ON DELETE RESTRICT
                                                      ON UPDATE CASCADE
                           NOT NULL,
    tag_id      INTEGER    REFERENCES tags (id) ON DELETE SET NULL
                                                ON UPDATE CASCADE,
    sum         REAL       NOT NULL,
    alt_sum     REAL       DEFAULT (0),
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


-- Table: asset_types
DROP TABLE IF EXISTS asset_types;

CREATE TABLE asset_types (
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
    type_id   INTEGER    REFERENCES asset_types (id) ON DELETE RESTRICT
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


-- Table: holdings
DROP TABLE IF EXISTS holdings;

CREATE TABLE holdings (
    level1     INTEGER,
    level2     INTEGER,
    currency   TEXT,
    account    TEXT,
    asset      TEXT,
    asset_name TEXT,
    qty        REAL,
    open       REAL,
    quote      REAL,
    share      REAL,
    profit_rel REAL,
    profit     REAL,
    value      REAL,
    value_adj  REAL
);


-- Table: holdings_aux
DROP TABLE IF EXISTS holdings_aux;

CREATE TABLE holdings_aux (
    currency  INTEGER,
    account   INTEGER,
    asset     INTEGER,
    qty       REAL,
    value     REAL,
    quote     REAL,
    quote_adj REAL,
    total     REAL,
    total_adj REAL
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
    id          INTEGER   PRIMARY KEY
                          UNIQUE
                          NOT NULL,
    name        TEXT (64) UNIQUE
                          NOT NULL,
    total_value REAL
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


-- Table: transfer_notes
DROP TABLE IF EXISTS transfer_notes;

CREATE TABLE transfer_notes (
    id   INTEGER     PRIMARY KEY
                     UNIQUE
                     NOT NULL,
    tid  INTEGER     NOT NULL
                     UNIQUE,
    note TEXT (1024) NOT NULL
);


-- Table: transfers
DROP TABLE IF EXISTS transfers;

CREATE TABLE transfers (
    id         INTEGER PRIMARY KEY
                       UNIQUE
                       NOT NULL,
    tid        INTEGER NOT NULL,
    timestamp  INTEGER NOT NULL,
    type       INTEGER NOT NULL,
    account_id INTEGER NOT NULL
                       REFERENCES accounts (id) ON DELETE CASCADE
                                                ON UPDATE CASCADE,
    amount     REAL,
    rate       REAL
);


-- Index: agents_by_name_idx
DROP INDEX IF EXISTS agents_by_name_idx;

CREATE INDEX agents_by_name_idx ON agents (
    name
);


-- Index: by_sid
DROP INDEX IF EXISTS by_sid;

CREATE INDEX by_sid ON ledger_sums (
    sid
);


-- View: agents_ext
DROP VIEW IF EXISTS agents_ext;
CREATE VIEW agents_ext AS
    SELECT a1.*,
           count(a2.id) AS children_count,
           count(a3.id) AS actions_count
      FROM agents AS a1
           LEFT JOIN
           agents AS a2 ON a1.id = a2.pid
           LEFT JOIN
           actions AS a3 ON a1.id = a3.peer_id
     GROUP BY a1.id;


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
                      sum(d.sum) AS amount,
                      o.alt_currency_id AS active_id,
                      NULL AS qty_trid,
                      sum(d.alt_sum) AS price,
                      NULL AS fee_tax,
                      NULL AS t_qty,
                      NULL AS note,
                      NULL AS note2
                 FROM actions AS o
                      LEFT JOIN
                      agents AS p ON o.peer_id = p.id
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
                      ( -t.type * t.sum) AS amount,
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
               UNION ALL
               SELECT 4 AS type,
                      r.id,
                      r.timestamp,
                      NULL AS num_peer,
                      r.account_id,
                      r.amount,
                      NULL AS active_id,
                      r.type AS qty_trid,
                      r.rate AS price,
                      NULL AS fee_tax,
                      NULL AS t_qty,
                      n.note,
                      a.name AS note2
                 FROM transfers AS r
                      LEFT JOIN
                      transfer_notes AS n ON r.tid = n.tid
                      LEFT JOIN
                      transfers AS p ON r.tid = p.tid AND 
                                        p.type = -r.type
                      LEFT JOIN
                      accounts AS a ON a.id = p.account_id
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


-- View: categories_ext
DROP VIEW IF EXISTS categories_ext;
CREATE VIEW categories_ext AS
    SELECT c1.*,
           count(c2.id) AS children_count
      FROM categories AS c1
           LEFT JOIN
           categories c2 ON c1.id = c2.pid
     GROUP BY c1.id;


-- View: frontier
DROP VIEW IF EXISTS frontier;
CREATE VIEW frontier AS
    SELECT MAX(sequence.timestamp) AS ledger_frontier
      FROM sequence;


-- View: transfers_combined
DROP VIEW IF EXISTS transfers_combined;
CREATE VIEW transfers_combined AS
    SELECT f.tid AS id,
           f.id AS from_id,
           f.timestamp AS from_timestamp,
           f.account_id AS from_acc_id,
           t.id AS to_id,
           t.timestamp AS to_timestamp,
           t.account_id AS to_acc_id,
           fee.id AS fee_id,
           fee.timestamp AS fee_timestamp,
           fee.account_id AS fee_acc_id,
           f.amount AS from_amount,
           t.amount AS to_amount,
           fee.amount AS fee_amount,
           n.note
      FROM transfers AS f
           INNER JOIN
           transfers AS t ON f.tid = t.tid AND 
                             t.type = 1
           LEFT JOIN
           transfers AS fee ON f.tid = fee.tid AND 
                               fee.type = 0
           LEFT JOIN
           transfer_notes AS n ON f.tid = n.tid
     WHERE f.type = -1;


-- Trigger: action_details_after_delete
DROP TRIGGER IF EXISTS action_details_after_delete;
CREATE TRIGGER action_details_after_delete
         AFTER DELETE
            ON action_details
      FOR EACH ROW
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
          WHEN (
    SELECT value
      FROM settings
     WHERE id = 1
)
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
          WHEN (
    SELECT value
      FROM settings
     WHERE id = 1
)
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
          WHEN (
    SELECT value
      FROM settings
     WHERE id = 1
)
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


-- Trigger: delete_agent
DROP TRIGGER IF EXISTS delete_agent;
CREATE TRIGGER delete_agent
    INSTEAD OF DELETE
            ON agents_ext
      FOR EACH ROW
BEGIN
    DELETE FROM agents
          WHERE id = OLD.id;
END;


-- Trigger: delete_category
DROP TRIGGER IF EXISTS delete_category;
CREATE TRIGGER delete_category
    INSTEAD OF DELETE
            ON categories_ext
      FOR EACH ROW
BEGIN
    DELETE FROM categories
          WHERE id = OLD.id;
END;


-- Trigger: delete_transfers
DROP TRIGGER IF EXISTS delete_transfers;
CREATE TRIGGER delete_transfers
    INSTEAD OF DELETE
            ON transfers_combined
BEGIN
    DELETE FROM transfer_notes
          WHERE tid = OLD.id;
    DELETE FROM transfers
          WHERE tid = OLD.id;
END;


-- Trigger: dividends_after_delete
DROP TRIGGER IF EXISTS dividends_after_delete;
CREATE TRIGGER dividends_after_delete
         AFTER DELETE
            ON dividends
      FOR EACH ROW
          WHEN (
    SELECT value
      FROM settings
     WHERE id = 1
)
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
          WHEN (
    SELECT value
      FROM settings
     WHERE id = 1
)
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
                         active_id,
                         sum,
                         sum_tax
            ON dividends
      FOR EACH ROW
          WHEN (
    SELECT value
      FROM settings
     WHERE id = 1
)
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


-- Trigger: insert_agent
DROP TRIGGER IF EXISTS insert_agent;
CREATE TRIGGER insert_agent
    INSTEAD OF INSERT
            ON agents_ext
      FOR EACH ROW
BEGIN
    INSERT INTO agents (
                           id,
                           pid,
                           name,
                           location
                       )
                       VALUES (
                           NEW.id,
                           NEW.pid,
                           NEW.name,
                           NEW.location
                       );
END;


-- Trigger: insert_category
DROP TRIGGER IF EXISTS insert_category;
CREATE TRIGGER insert_category
    INSTEAD OF INSERT
            ON categories_ext
      FOR EACH ROW
BEGIN
    INSERT INTO categories (
                               id,
                               pid,
                               name,
                               often,
                               special
                           )
                           VALUES (
                               NEW.id,
                               NEW.pid,
                               NEW.name,
                               NEW.often,
                               NEW.special
                           );
END;


-- Trigger: insert_transfers
DROP TRIGGER IF EXISTS insert_transfers;
CREATE TRIGGER insert_transfers
    INSTEAD OF INSERT
            ON transfers_combined
          WHEN NEW.fee_timestamp IS NULL
BEGIN
    INSERT INTO transfers (
                              tid,
                              type,
                              timestamp,
                              account_id,
                              amount,
                              rate
                          )
                          VALUES (
                              (
                                  SELECT MAX(tid) + 1
                                    FROM transfers
                              ),
-                             1,
                              NEW.from_timestamp,
                              NEW.from_acc_id,
                              NEW.from_amount,
                              NEW.to_amount / NEW.from_amount
                          );
    INSERT INTO transfers (
                              tid,
                              type,
                              timestamp,
                              account_id,
                              amount,
                              rate
                          )
                          VALUES (
                              (
                                  SELECT MAX(tid) 
                                    FROM transfers
                              ),
                              1,
                              NEW.to_timestamp,
                              NEW.to_acc_id,
                              NEW.to_amount,
                              NEW.from_amount / NEW.to_amount
                          );
    INSERT INTO transfer_notes (
                                   tid,
                                   note
                               )
                               VALUES (
                                   (
                                       SELECT MAX(tid) 
                                         FROM transfers
                                   ),
                                   NEW.note
                               );
END;


-- Trigger: insert_transfers_with_fee
DROP TRIGGER IF EXISTS insert_transfers_with_fee;
CREATE TRIGGER insert_transfers_with_fee
    INSTEAD OF INSERT
            ON transfers_combined
          WHEN NEW.fee_timestamp IS NOT NULL
BEGIN
    INSERT INTO transfers (
                              tid,
                              type,
                              timestamp,
                              account_id,
                              amount,
                              rate
                          )
                          VALUES (
                              (
                                  SELECT MAX(tid) + 1
                                    FROM transfers
                              ),
-                             1,
                              NEW.from_timestamp,
                              NEW.from_acc_id,
                              NEW.from_amount,
                              NEW.to_amount / NEW.from_amount
                          );
    INSERT INTO transfers (
                              tid,
                              type,
                              timestamp,
                              account_id,
                              amount,
                              rate
                          )
                          VALUES (
                              (
                                  SELECT MAX(tid) 
                                    FROM transfers
                              ),
                              1,
                              NEW.to_timestamp,
                              NEW.to_acc_id,
                              NEW.to_amount,
                              NEW.from_amount / NEW.to_amount
                          );
    INSERT INTO transfers (
                              tid,
                              type,
                              timestamp,
                              account_id,
                              amount,
                              rate
                          )
                          VALUES (
                              (
                                  SELECT MAX(tid) 
                                    FROM transfers
                              ),
                              0,
                              NEW.fee_timestamp,
                              NEW.fee_acc_id,
                              NEW.fee_amount,
                              0
                          );
    INSERT INTO transfer_notes (
                                   tid,
                                   note
                               )
                               VALUES (
                                   (
                                       SELECT MAX(tid) 
                                         FROM transfers
                                   ),
                                   NEW.note
                               );
END;


-- Trigger: trades_after_delete
DROP TRIGGER IF EXISTS trades_after_delete;
CREATE TRIGGER trades_after_delete
         AFTER DELETE
            ON trades
      FOR EACH ROW
          WHEN (
    SELECT value
      FROM settings
     WHERE id = 1
)
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
          WHEN (
    SELECT value
      FROM settings
     WHERE id = 1
)
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
                         type,
                         account_id,
                         active_id,
                         qty,
                         price,
                         coupon,
                         fee_broker,
                         fee_exchange
            ON trades
      FOR EACH ROW
          WHEN (
    SELECT value
      FROM settings
     WHERE id = 1
)
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
          WHEN (
    SELECT value
      FROM settings
     WHERE id = 1
)
BEGIN
    DELETE FROM ledger
          WHERE timestamp >= OLD.timestamp;
    DELETE FROM sequence
          WHERE timestamp >= OLD.timestamp;
    DELETE FROM ledger_sums
          WHERE timestamp >= OLD.timestamp;
END;


-- Trigger: transfers_after_insert
DROP TRIGGER IF EXISTS transfers_after_insert;
CREATE TRIGGER transfers_after_insert
         AFTER INSERT
            ON transfers
      FOR EACH ROW
          WHEN (
    SELECT value
      FROM settings
     WHERE id = 1
)
BEGIN
    DELETE FROM ledger
          WHERE timestamp >= NEW.timestamp;
    DELETE FROM sequence
          WHERE timestamp >= NEW.timestamp;
    DELETE FROM ledger_sums
          WHERE timestamp >= NEW.timestamp;
END;


-- Trigger: transfers_after_update
DROP TRIGGER IF EXISTS transfers_after_update;
CREATE TRIGGER transfers_after_update
         AFTER UPDATE OF timestamp,
                         type,
                         account_id,
                         amount
            ON transfers
      FOR EACH ROW
          WHEN (
    SELECT value
      FROM settings
     WHERE id = 1
)
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


-- Trigger: update_agent
DROP TRIGGER IF EXISTS update_agent;
CREATE TRIGGER update_agent
    INSTEAD OF UPDATE
            ON agents_ext
      FOR EACH ROW
BEGIN
    UPDATE agents
       SET id = NEW.id,
           pid = NEW.pid,
           name = NEW.name,
           location = NEW.location
     WHERE id = OLD.id;
END;


-- Trigger: update_category
DROP TRIGGER IF EXISTS update_category;
CREATE TRIGGER update_category
    INSTEAD OF UPDATE
            ON categories_ext
      FOR EACH ROW
BEGIN
    UPDATE categories
       SET id = NEW.id,
           pid = NEW.pid,
           name = NEW.name,
           often = NEW.often,
           special = NEW.special
     WHERE id = OLD.id;
END;


-- Trigger: update_f_account
DROP TRIGGER IF EXISTS update_f_account;
CREATE TRIGGER update_f_account
    INSTEAD OF UPDATE OF from_acc_id
            ON transfers_combined
BEGIN
    UPDATE transfers
       SET account_id = NEW.from_acc_id
     WHERE tid = OLD.id AND 
           type = -1;
END;


-- Trigger: update_f_amount
DROP TRIGGER IF EXISTS update_f_amount;
CREATE TRIGGER update_f_amount
    INSTEAD OF UPDATE OF from_amount
            ON transfers_combined
BEGIN
    UPDATE transfers
       SET amount = NEW.from_amount
     WHERE tid = OLD.id AND 
           type = -1;
END;


-- Trigger: update_f_timestamp
DROP TRIGGER IF EXISTS update_f_timestamp;
CREATE TRIGGER update_f_timestamp
    INSTEAD OF UPDATE OF from_timestamp
            ON transfers_combined
BEGIN
    UPDATE transfers
       SET timestamp = NEW.from_timestamp
     WHERE tid = OLD.id AND 
           type = -1;
END;


-- Trigger: update_fee_account
DROP TRIGGER IF EXISTS update_fee_account;
CREATE TRIGGER update_fee_account
    INSTEAD OF UPDATE OF fee_acc_id
            ON transfers_combined
BEGIN
    UPDATE transfers
       SET account_id = NEW.fee_acc_id
     WHERE tid = OLD.id AND 
           type = 0;
END;


-- Trigger: update_fee_amount
DROP TRIGGER IF EXISTS update_fee_amount;
CREATE TRIGGER update_fee_amount
    INSTEAD OF UPDATE OF fee_amount
            ON transfers_combined
BEGIN
    UPDATE transfers
       SET amount = NEW.fee_amount
     WHERE tid = OLD.id AND 
           type = 0;
END;


-- Trigger: update_fee_timestamp
DROP TRIGGER IF EXISTS update_fee_timestamp;
CREATE TRIGGER update_fee_timestamp
    INSTEAD OF UPDATE OF fee_timestamp
            ON transfers_combined
BEGIN
    UPDATE transfers
       SET timestamp = NEW.fee_timestamp
     WHERE tid = OLD.id AND 
           type = 0;
END;


-- Trigger: update_note
DROP TRIGGER IF EXISTS update_note;
CREATE TRIGGER update_note
    INSTEAD OF UPDATE OF note
            ON transfers_combined
BEGIN
    UPDATE transfer_notes
       SET note = NEW.note
     WHERE tid = OLD.id;
END;


-- Trigger: update_t_account
DROP TRIGGER IF EXISTS update_t_account;
CREATE TRIGGER update_t_account
    INSTEAD OF UPDATE OF to_acc_id
            ON transfers_combined
BEGIN
    UPDATE transfers
       SET account_id = NEW.to_acc_id
     WHERE tid = OLD.id AND 
           type = 1;
END;


-- Trigger: update_t_amount
DROP TRIGGER IF EXISTS update_t_amount;
CREATE TRIGGER update_t_amount
    INSTEAD OF UPDATE OF to_amount
            ON transfers_combined
BEGIN
    UPDATE transfers
       SET amount = NEW.to_amount
     WHERE tid = OLD.id AND 
           type = 1;
END;


-- Trigger: update_t_timestamp
DROP TRIGGER IF EXISTS update_t_timestamp;
CREATE TRIGGER update_t_timestamp
    INSTEAD OF UPDATE OF to_timestamp
            ON transfers_combined
BEGIN
    UPDATE transfers
       SET timestamp = NEW.to_timestamp
     WHERE tid = OLD.id AND 
           type = 1;
END;


-- Initialize default values for settings
INSERT INTO settings(id, name, value) VALUES (0, 'SchemaVersion', 1);
INSERT INTO settings(id, name, value) VALUES (1, 'TriggersEnabled', 1);

-- Initialize default values for books
INSERT INTO books (id, name) VALUES (1, 'Costs');
INSERT INTO books (id, name) VALUES (2, 'Incomes');
INSERT INTO books (id, name) VALUES (3, 'Money');
INSERT INTO books (id, name) VALUES (4, 'Actives');
INSERT INTO books (id, name) VALUES (5, 'Liabilities');
INSERT INTO books (id, name) VALUES (6, 'Transfers');

-- Initialize active types values
INSERT INTO asset_types (id, name) VALUES (1, 'Money');
INSERT INTO asset_types (id, name) VALUES (2, 'Shares');
INSERT INTO asset_types (id, name) VALUES (3, 'Bonds');
INSERT INTO asset_types (id, name) VALUES (4, 'Funds');
INSERT INTO asset_types (id, name) VALUES (5, 'Commodities');
INSERT INTO asset_types (id, name) VALUES (6, 'Derivatives');

-- Initialize some account types
INSERT INTO account_types (id, name) VALUES (1, 'Cash');
INSERT INTO account_types (id, name) VALUES (2, 'Bank accounts');
INSERT INTO account_types (id, name) VALUES (3, 'Cards');
INSERT INTO account_types (id, name) VALUES (4, 'Investment');
INSERT INTO account_types (id, name) VALUES (5, 'Deposits');
INSERT INTO account_types (id, name) VALUES (6, 'Debts');
INSERT INTO account_types (id, name) VALUES (7, 'e-Wallets');


COMMIT TRANSACTION;
PRAGMA foreign_keys = on;
