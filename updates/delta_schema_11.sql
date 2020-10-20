BEGIN TRANSACTION;
--------------------------------------------------------------------------------
-- Create new table with list of countries
CREATE TABLE countries (
    id           INTEGER      PRIMARY KEY
                              UNIQUE
                              NOT NULL,
    name         VARCHAR (64) UNIQUE
                              NOT NULL,
    code         CHAR (3)     UNIQUE
                              NOT NULL,
    tax_treaty INTEGER        NOT NULL
                              DEFAULT (0)
);

-- Make some pre-defined countries
INSERT INTO countries (id, name, code, tax_treaty) VALUES (0, 'N/A', 'xx', 0);
INSERT INTO countries (id, name, code, tax_treaty) VALUES (1, 'Russia', 'ru', 0);
INSERT INTO countries (id, name, code, tax_treaty) VALUES (2, 'United States', 'us', 1);
INSERT INTO countries (id, name, code, tax_treaty) VALUES (3, 'Ireland', 'ie', 1);
INSERT INTO countries (id, name, code, tax_treaty) VALUES (4, 'Switzerland', 'ch', 1);
INSERT INTO countries (id, name, code, tax_treaty) VALUES (5, 'France', 'fr', 1);
INSERT INTO countries (id, name, code, tax_treaty) VALUES (6, 'Canada', 'ca', 1);
INSERT INTO countries (id, name, code, tax_treaty) VALUES (7, 'Sweden', 'se', 1);


--------------------------------------------------------------------------------
-- Modify dividends table to include new 'tax_country_id' column
CREATE TABLE sqlitestudio_temp_table AS SELECT * FROM dividends;

DROP TABLE dividends;

CREATE TABLE dividends (
    id             INTEGER     PRIMARY KEY
                               UNIQUE
                               NOT NULL,
    timestamp      INTEGER     NOT NULL,
    number         TEXT (32)   DEFAULT (''),
    account_id     INTEGER     REFERENCES accounts (id) ON DELETE CASCADE
                                                        ON UPDATE CASCADE
                               NOT NULL,
    asset_id       INTEGER     REFERENCES assets (id) ON DELETE RESTRICT
                                                      ON UPDATE CASCADE
                               NOT NULL,
    sum            REAL        NOT NULL
                               DEFAULT (0),
    sum_tax        REAL        DEFAULT (0),
    note           TEXT (1014),
    note_tax       TEXT (64),
    tax_country_id INTEGER     REFERENCES countries (id) ON DELETE CASCADE
                                                         ON UPDATE CASCADE
                               DEFAULT (0)
);

INSERT INTO dividends (
                          id,
                          timestamp,
                          number,
                          account_id,
                          asset_id,
                          sum,
                          sum_tax,
                          note,
                          note_tax
                      )
                      SELECT id,
                             timestamp,
                             number,
                             account_id,
                             asset_id,
                             sum,
                             sum_tax,
                             note,
                             note_tax
                        FROM sqlitestudio_temp_table;

DROP TABLE sqlitestudio_temp_table;

--------------------------------------------------------------------------------
-- Assign country based on 'note_tax' field data
-- Update russian:
UPDATE dividends SET tax_country_id=1 WHERE note_tax='НДФЛ';
-- Update all other based on 'XX tax' value of 'note_tax' field
UPDATE dividends
SET tax_country_id = (SELECT countries.id FROM countries WHERE countries.code = substr(dividends.note_tax, 1, 2) COLLATE NOCASE)
WHERE EXISTS (SELECT countries.* FROM countries WHERE countries.code = substr(dividends.note_tax, 1, 2) COLLATE NOCASE);
-- Set default if anything remains NULL
UPDATE dividends SET tax_country_id=0 WHERE tax_country_id IS NULL;

--------------------------------------------------------------------------------
-- Modify dividends table to delete old 'note_tax' column
CREATE TABLE sqlitestudio_temp_table AS SELECT * FROM dividends;

DROP TABLE dividends;

CREATE TABLE dividends (
    id             INTEGER     PRIMARY KEY
                               UNIQUE
                               NOT NULL,
    timestamp      INTEGER     NOT NULL,
    number         TEXT (32)   DEFAULT (''),
    account_id     INTEGER     REFERENCES accounts (id) ON DELETE CASCADE
                                                        ON UPDATE CASCADE
                               NOT NULL,
    asset_id       INTEGER     REFERENCES assets (id) ON DELETE RESTRICT
                                                      ON UPDATE CASCADE
                               NOT NULL,
    sum            REAL        NOT NULL
                               DEFAULT (0),
    sum_tax        REAL        DEFAULT (0),
    note           TEXT (1014),
    tax_country_id INTEGER     REFERENCES countries (id) ON DELETE CASCADE
                                                         ON UPDATE CASCADE
                               DEFAULT (0)
);

INSERT INTO dividends (
                          id,
                          timestamp,
                          number,
                          account_id,
                          asset_id,
                          sum,
                          sum_tax,
                          note,
                          tax_country_id
                      )
                      SELECT id,
                             timestamp,
                             number,
                             account_id,
                             asset_id,
                             sum,
                             sum_tax,
                             note,
                             tax_country_id
                        FROM sqlitestudio_temp_table;

DROP TABLE sqlitestudio_temp_table;

--------------------------------------------------------------------------------
-- Create all triggers
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

CREATE TRIGGER dividends_after_update
         AFTER UPDATE OF timestamp,
                         account_id,
                         asset_id,
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

--------------------------------------------------------------------------------
-- UPDATE VIEWS
DROP VIEW all_operations;

CREATE VIEW all_operations AS
    SELECT m.type,
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
           coalesce(money.sum_amount, 0) + coalesce(debt.sum_amount, 0) AS t_amount,
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
                      o.alt_currency_id AS asset_id,
                      NULL AS qty_trid,
                      sum(d.alt_sum) AS price,
                      NULL AS fee_tax,
                      NULL AS t_qty,
                      NULL AS note,
                      NULL AS note2,
                      o.id AS operation_id
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
                      d.asset_id,
                      SUM(coalesce(l.amount, 0) ) AS qty_trid,
                      NULL AS price,
                      d.sum_tax AS fee_tax,
                      NULL AS t_qty,
                      d.note AS note,
                      c.name AS note2,
                      d.id AS operation_id
                 FROM dividends AS d
                      LEFT JOIN
                      ledger AS l ON d.asset_id = l.asset_id AND
                                     d.account_id = l.account_id AND
                                     l.book_account = 4 AND
                                     l.timestamp <= d.timestamp
                      LEFT JOIN
                      countries AS c ON d.tax_country_id = c.id
                GROUP BY d.id
               UNION ALL
               SELECT 3 AS type,
                      t.id,
                      t.timestamp,
                      t.number AS num_peer,
                      t.account_id,
-                     (t.price * t.qty) AS amount,
                      t.asset_id,
                      t.qty AS qty_trid,
                      t.price AS price,
                      t.fee AS fee_tax,
                      l.sum_amount AS t_qty,
                      ca.note AS note,
                      NULL AS note2,
                      t.id AS operation_id
                 FROM trades AS t
                      LEFT JOIN
                      sequence AS q ON q.type = 3 AND
                                       t.id = q.operation_id
                      LEFT JOIN
                      ledger_sums AS l ON l.sid = q.id AND
                                          l.book_account = 4
                      LEFT JOIN
                      corp_actions AS ca ON t.corp_action_id = ca.id
               UNION ALL
               SELECT 4 AS type,
                      r.tid,
                      r.timestamp,
                      c.name AS num_peer,
                      r.account_id,
                      r.amount,
                      NULL AS asset_id,
                      r.type AS qty_trid,
                      r.rate AS price,
                      NULL AS fee_tax,
                      NULL AS t_qty,
                      n.note,
                      a.name AS note2,
                      r.id AS operation_id
                 FROM transfers AS r
                      LEFT JOIN
                      transfer_notes AS n ON r.tid = n.tid
                      LEFT JOIN
                      transfers AS tr ON r.tid = tr.tid AND
                                         r.type = -tr.type
                      LEFT JOIN
                      accounts AS a ON a.id = tr.account_id
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
                            m.operation_id = q.operation_id
           LEFT JOIN
           ledger_sums AS money ON money.sid = q.id AND
                                   money.book_account = 3
           LEFT JOIN
           ledger_sums AS debt ON debt.sid = q.id AND
                                  debt.book_account = 5;

--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=11 WHERE name='SchemaVersion';

COMMIT;

