BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 0;
--------------------------------------------------------------------------------
-- Add operation code to 'actions' table
CREATE TABLE sqlitestudio_temp_table AS SELECT * FROM actions;
DROP TABLE actions;
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
INSERT INTO actions (
                        id,
                        timestamp,
                        account_id,
                        peer_id,
                        alt_currency_id
                    )
                    SELECT id,
                           timestamp,
                           account_id,
                           peer_id,
                           alt_currency_id
                      FROM sqlitestudio_temp_table;
DROP TABLE sqlitestudio_temp_table;
--------------------------------------------------------------------------------
-- Add operation code to 'dividends' table
CREATE TABLE sqlitestudio_temp_table AS SELECT * FROM dividends;
DROP TABLE dividends;
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

INSERT INTO dividends (
                          id,
                          timestamp,
                          ex_date,
                          number,
                          type,
                          account_id,
                          asset_id,
                          amount,
                          tax,
                          note
                      )
                      SELECT id,
                             timestamp,
                             ex_date,
                             number,
                             type,
                             account_id,
                             asset_id,
                             amount,
                             tax,
                             note
                        FROM sqlitestudio_temp_table;
DROP TABLE sqlitestudio_temp_table;
--------------------------------------------------------------------------------
-- Add operation code to 'trades' table
CREATE TABLE sqlitestudio_temp_table AS SELECT * FROM trades;
DROP TABLE trades;
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

INSERT INTO trades (
                       id,
                       timestamp,
                       settlement,
                       number,
                       account_id,
                       asset_id,
                       qty,
                       price,
                       fee,
                       note
                   )
                   SELECT id,
                          timestamp,
                          settlement,
                          number,
                          account_id,
                          asset_id,
                          qty,
                          price,
                          fee,
                          note
                     FROM sqlitestudio_temp_table;
DROP TABLE sqlitestudio_temp_table;
--------------------------------------------------------------------------------
-- Add operation code to 'transfers' table
CREATE TABLE sqlitestudio_temp_table AS SELECT * FROM transfers;
DROP TABLE transfers;
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

INSERT INTO transfers (
                          id,
                          withdrawal_timestamp,
                          withdrawal_account,
                          withdrawal,
                          deposit_timestamp,
                          deposit_account,
                          deposit,
                          fee_account,
                          fee,
                          asset,
                          note
                      )
                      SELECT id,
                             withdrawal_timestamp,
                             withdrawal_account,
                             withdrawal,
                             deposit_timestamp,
                             deposit_account,
                             deposit,
                             fee_account,
                             fee,
                             asset,
                             note
                        FROM sqlitestudio_temp_table;

DROP TABLE sqlitestudio_temp_table;
--------------------------------------------------------------------------------
-- Add operation code to 'corp_actions' table
CREATE TABLE sqlitestudio_temp_table AS SELECT * FROM corp_actions;
DROP TABLE corp_actions;
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

INSERT INTO corp_actions (
                             id,
                             timestamp,
                             number,
                             account_id,
                             type,
                             asset_id,
                             qty,
                             asset_id_new,
                             qty_new,
                             basis_ratio,
                             note
                         )
                         SELECT id,
                                timestamp,
                                number,
                                account_id,
                                type,
                                asset_id,
                                qty,
                                asset_id_new,
                                qty_new,
                                basis_ratio,
                                note
                           FROM sqlitestudio_temp_table;
DROP TABLE sqlitestudio_temp_table;
--------------------------------------------------------------------------------
-- New table to support FIFO
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

--------------------------------------------------------------------------------
-- Move accumulated value and amount fields from ledger_sums to ledger table
--------------------------------------------------------------------------------
DROP TABLE IF EXISTS ledger;
DROP TABLE IF EXISTS sequence;
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

--------------------------------------------------------------------------------
-- New deals structure
DROP TABLE deals;
CREATE TABLE deals (
    id              INTEGER PRIMARY KEY
                            UNIQUE
                            NOT NULL,
    account_id      INTEGER NOT NULL,
    asset_id        INTEGER NOT NULL,
    open_op_type    INTEGER NOT NULL,
    open_op_id      INTEGER NOT NULL,
    open_timestamp  INTEGER NOT NULL,
    close_op_type   INTEGER NOT NULL,
    close_op_id     INTEGER NOT NULL,
    close_timestamp INTEGER NOT NULL,
    qty             REAL    NOT NULL
);

CREATE TRIGGER on_deal_delete
    AFTER DELETE ON deals
    FOR EACH ROW
    WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    UPDATE open_trades SET remaining_qty = remaining_qty + OLD.qty
    WHERE op_type=OLD.open_op_type AND operation_id=OLD.open_op_id AND account_id=OLD.account_id AND asset_id = OLD.asset_id;
END;
--------------------------------------------------------------------------------
-- Recreate 'frontier' view based on ledger table
DROP VIEW IF EXISTS frontier;
CREATE VIEW frontier AS SELECT MAX(ledger.timestamp) AS ledger_frontier FROM ledger;
--------------------------------------------------------------------------------
-- Change order of transaction processing in all_transactions view (corp.actions should go before trades)
DROP VIEW IF EXISTS all_transactions;
CREATE VIEW all_transactions AS
    SELECT at.*,
           a.currency_id AS currency
      FROM (
               SELECT a.op_type AS type,
                      1 AS seq,
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
               SELECT d.op_type AS type,
                      2 AS seq,
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
               SELECT a.op_type AS type,
                      3 AS seq,
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
               SELECT t.op_type AS type,
                      4 AS seq,
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
               SELECT op_type AS type,
                      5 AS seq,
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
               SELECT op_type AS type,
                      5 AS seq,
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
               SELECT op_type AS type,
                      5 AS seq,
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
           )
           AS at
           LEFT JOIN
           accounts AS a ON at.account = a.id
     ORDER BY at.timestamp,
              at.seq,
              at.subtype,
              at.id;
--------------------------------------------------------------------------------
DROP VIEW IF EXISTS all_operations;
CREATE VIEW all_operations AS
-- We will need accumulated sums from ledger, but only the last record if several available
WITH _ledger_last AS (SELECT * FROM ledger WHERE id IN (SELECT MAX(id) FROM ledger GROUP BY op_type, operation_id, book_account))
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
           iif(coalesce(money.amount_acc, 0) > 0, money.amount_acc, coalesce(debt.amount_acc, 0) ) AS t_amount,
           m.t_qty,
           c.name AS currency,
           CASE WHEN m.timestamp <= a.reconciled_on THEN 1 ELSE 0 END AS reconciled
      FROM (
               SELECT o.op_type AS type,
                      iif(SUM(d.amount) < 0, -1, 1) AS subtype,
                      o.id,
                      timestamp,
                      p.name AS num_peer,
                      account_id,
                      sum(d.amount) AS amount,
                      o.alt_currency_id AS asset_id,
                      NULL AS qty_trid,
                      sum(d.amount_alt) AS price,
                      coalesce(sum(d.amount_alt) / sum(d.amount), 0) AS fee_tax,
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
               SELECT d.op_type AS type,
                      d.type AS subtype,
                      d.id,
                      d.timestamp,
                      d.number AS num_peer,
                      d.account_id,
                      d.amount AS amount,
                      d.asset_id,
                      NULL AS qty_trid,
                      NULL AS price,
                      d.tax AS fee_tax,
                      NULL AS t_qty,
                      d.note AS note,
                      c.name AS note2
                 FROM dividends AS d
                      LEFT JOIN assets AS a ON d.asset_id = a.id
                      LEFT JOIN countries AS c ON a.country_id = c.id
                GROUP BY d.id
               UNION ALL
               SELECT ca.op_type AS type,
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
                      l.amount_acc AS t_qty,
                      a.name AS note,
                      a.full_name AS note2
                 FROM corp_actions AS ca
                      LEFT JOIN assets AS a ON ca.asset_id_new = a.id
                      LEFT JOIN _ledger_last AS l ON l.op_type = ca.op_type AND l.operation_id=ca.id AND l.asset_id = ca.asset_id_new AND l.book_account = 4
               UNION ALL
               SELECT t.op_type AS type,
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
                      l.amount_acc AS t_qty,
                      t.note AS note,
                      NULL AS note2
                 FROM trades AS t
                      LEFT JOIN _ledger_last AS l ON l.op_type=t.op_type AND l.operation_id=t.id AND l.book_account = 4
               UNION ALL
               SELECT t.op_type AS type,
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
                          SELECT op_type, id,
                                 withdrawal_timestamp AS timestamp,
                                 withdrawal_account AS account_id,
                                 deposit_account AS account2_id,
                                 -withdrawal AS amount,
                                 deposit / withdrawal AS rate,
                                 -1 AS subtype,
                                 note
                            FROM transfers
                          UNION ALL
                          SELECT op_type, id,
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
                          SELECT op_type, id,
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
           )
           AS m
           LEFT JOIN accounts AS a ON m.account_id = a.id
           LEFT JOIN assets AS s ON m.asset_id = s.id
           LEFT JOIN assets AS c ON a.currency_id = c.id
           LEFT JOIN _ledger_last AS money ON money.op_type=m.type AND money.operation_id=m.id AND money.account_id = m.account_id AND money.book_account = 3
           LEFT JOIN _ledger_last AS debt ON debt.op_type=m.type AND debt.operation_id=m.id AND debt.account_id = m.account_id AND debt.book_account = 5
     ORDER BY m.timestamp;
--------------------------------------------------------------------------------
-- Recreate view deals_ext to use ledger instead of ledger_sums
DROP VIEW deals_ext;
CREATE VIEW deals_ext AS
    SELECT d.account_id,
           ac.name AS account,
           d.asset_id,
           at.name AS asset,
           open_timestamp,
           close_timestamp,
           coalesce(ot.price, ols.value_acc / ols.amount_acc) AS open_price,
           coalesce(ct.price, ot.price) AS close_price,
           d.qty AS qty,
           coalesce(ot.fee * abs(d.qty / ot.qty), 0) + coalesce(ct.fee * abs(d.qty / ct.qty), 0) AS fee,
           d.qty * (coalesce(ct.price, ot.price) - coalesce(ot.price, ols.value_acc / ols.amount_acc) ) - (coalesce(ot.fee * abs(d.qty / ot.qty), 0) + coalesce(ct.fee * abs(d.qty / ct.qty), 0) ) AS profit,
           coalesce(100 * (d.qty * (coalesce(ct.price, ot.price) - coalesce(ot.price, ols.value_acc / ols.amount_acc) ) - (coalesce(ot.fee * abs(d.qty / ot.qty), 0) + coalesce(ct.fee * abs(d.qty / ct.qty), 0) ) ) / abs(d.qty * coalesce(ot.price, ols.value_acc / ols.amount_acc) ), 0) AS rel_profit,
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
           LEFT JOIN assets AS at ON d.asset_id = at.id
     -- drop cases where deal was opened and closed with corporate action
     WHERE NOT (d.open_op_type = 5 AND d.close_op_type = 5)
     ORDER BY close_timestamp, open_timestamp;
--------------------------------------------------------------------------------
-- Update triggers linked to 'ledger_sums' table
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

--------------------------------------------------------------------------------
DROP INDEX IF EXISTS by_sid;
DROP INDEX IF EXISTS by_book_account_asset_ts;
DROP TABLE IF EXISTS ledger_sums;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 1;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=29 WHERE name='SchemaVersion';
INSERT OR REPLACE INTO settings(id, name, value) VALUES (7, 'RebuildDB', 1);
INSERT OR REPLACE INTO settings(id, name, value) VALUES (8, 'WindowGeometry', '');
INSERT OR REPLACE INTO settings(id, name, value) VALUES (9, 'WindowState', '');
COMMIT;
