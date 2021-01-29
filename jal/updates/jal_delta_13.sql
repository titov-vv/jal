BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 0;

--------------------------------------------------------------------------------
-- Drop unique constraints from t_last_assets table
--------------------------------------------------------------------------------
DROP TABLE t_last_assets;

CREATE TABLE t_last_assets (
    id          INTEGER   NOT NULL,
    name        TEXT (64) NOT NULL,
    total_value REAL
);
--------------------------------------------------------------------------------
-- Add field 'basis_ratio to corp_actions table
--------------------------------------------------------------------------------
CREATE TABLE sqlitestudio_temp_table AS SELECT * FROM corp_actions;

DROP TABLE corp_actions;

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
                                note
                           FROM sqlitestudio_temp_table;

DROP TABLE sqlitestudio_temp_table;

CREATE TRIGGER corp_after_delete
         AFTER DELETE
            ON corp_actions
      FOR EACH ROW
BEGIN
    DELETE FROM ledger
          WHERE timestamp >= OLD.timestamp;
    DELETE FROM sequence
          WHERE timestamp >= OLD.timestamp;
    DELETE FROM ledger_sums
          WHERE timestamp >= OLD.timestamp;
END;

CREATE TRIGGER corp_after_insert
         AFTER INSERT
            ON corp_actions
      FOR EACH ROW
BEGIN
    DELETE FROM ledger
          WHERE timestamp >= NEW.timestamp;
    DELETE FROM sequence
          WHERE timestamp >= NEW.timestamp;
    DELETE FROM ledger_sums
          WHERE timestamp >= NEW.timestamp;
END;

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

PRAGMA foreign_keys = 1;

--------------------------------------------------------------------------------
-- Include 'basis_ratio' in all_operations view
--------------------------------------------------------------------------------
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
               SELECT 5 AS type,
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
                      a.full_name AS note2,
                      ca.id AS operation_id
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
                      NULL AS note,
                      NULL AS note2,
                      t.id AS operation_id
                 FROM trades AS t
                      LEFT JOIN
                      sequence AS q ON q.type = 3 AND
                                       t.id = q.operation_id
                      LEFT JOIN
                      ledger_sums AS l ON l.sid = q.id AND
                                          l.book_account = 4
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
-- Include 'basis_ratio' in all_transactions view
--------------------------------------------------------------------------------
DROP VIEW all_transactions;

CREATE VIEW all_transactions AS
    SELECT at.*,
           a.currency_id AS currency
      FROM (
               SELECT 1 AS type,
                      a.id,
                      a.timestamp,
                      CASE WHEN SUM(d.sum) < 0 THEN COUNT(d.sum) ELSE -COUNT(d.sum) END AS subtype,
                      a.account_id AS account,
                      NULL AS asset,
                      SUM(d.sum) AS amount,
                      d.category_id AS category,
                      NULL AS price,
                      NULL AS fee_tax,
                      NULL AS coupon,
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
                      0 AS subtype,
                      d.account_id AS account,
                      d.asset_id AS asset,
                      d.sum AS amount,
                      7 AS category,
                      NULL AS price,
                      d.sum_tax AS fee_tax,
                      NULL AS coupon,
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
                      NULL AS coupon,
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
                      t.coupon AS coupon,
                      a.organization_id AS peer,
                      NULL AS tag
                 FROM trades AS t
                      LEFT JOIN
                      accounts AS a ON a.id = t.account_id
               UNION ALL
               SELECT 4 AS type,
                      id,
                      timestamp,
                      type AS subtype,
                      account_id AS account,
                      NULL AS asset,
                      amount,
                      NULL AS category,
                      NULL AS price,
                      NULL AS fee_tax,
                      NULL AS coupon,
                      NULL AS peer,
                      NULL AS tag
                 FROM transfers
                ORDER BY timestamp
           )
           AS at
           LEFT JOIN
           accounts AS a ON at.account = a.id;
--------------------------------------------------------------------------------
-- Modify 'deals_ext' view for correct profit calculation
--------------------------------------------------------------------------------
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

-- Set new DB schema version
UPDATE settings SET value=13 WHERE name='SchemaVersion';

COMMIT;

