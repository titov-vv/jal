BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 0;
--------------------------------------------------------------------------------
-- Move accumulated value and amount fields from ledger_sums to ledger table
--------------------------------------------------------------------------------
CREATE TABLE sqlitestudio_temp_table AS SELECT * FROM ledger;

DROP TABLE ledger;

CREATE TABLE ledger (
    id           INTEGER PRIMARY KEY
                         NOT NULL
                         UNIQUE,
    timestamp    INTEGER NOT NULL,
    sid          INTEGER NOT NULL,
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

INSERT INTO ledger (id, timestamp, sid, book_account, asset_id, account_id, amount, value, peer_id, category_id, tag_id)
            SELECT id, timestamp, sid, book_account, asset_id, account_id, amount, value, peer_id, category_id, tag_id
            FROM sqlitestudio_temp_table;

DROP TABLE sqlitestudio_temp_table;
--------------------------------------------------------------------------------
-- Change order of transaction processing in all_transactions view (corp.actions should go before trades)
DROP VIEW IF EXISTS all_transactions;
CREATE VIEW all_transactions AS
    SELECT at.*,
           a.currency_id AS currency
      FROM (
               SELECT 1 AS type,
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
               SELECT 2 AS type,
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
               SELECT 5 AS type,
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
               SELECT 3 AS type,
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
               SELECT 4 AS type,
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
               SELECT 4 AS type,
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
               SELECT 4 AS type,
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
                      l.amount_acc AS t_qty,
                      a.name AS note,
                      a.full_name AS note2
                 FROM corp_actions AS ca
                      LEFT JOIN
                      assets AS a ON ca.asset_id_new = a.id
                      LEFT JOIN
                      sequence AS q ON q.type = 5 AND
                                       ca.id = q.operation_id
                      LEFT JOIN
                      ledger AS l ON l.sid = q.id AND
                                     l.asset_id = ca.asset_id_new AND
                                     l.book_account = 4 AND
                                     l.amount_acc > 0
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
                                  debt.book_account = 5
     ORDER BY m.timestamp;
--------------------------------------------------------------------------------
-- Recreate view deals_ext to use ledger instead of ledger_sums
DROP VIEW deals_ext;
CREATE VIEW deals_ext AS
    SELECT d.account_id,
           ac.name AS account,
           d.asset_id,
           at.name AS asset,
           coalesce(ot.timestamp, oca.timestamp) AS open_timestamp,
           coalesce(ct.timestamp, cca.timestamp) AS close_timestamp,
           coalesce(ot.price, ols.value_acc / ols.amount_acc) AS open_price,
           coalesce(ct.price, ot.price) AS close_price,
           d.qty AS qty,
           coalesce(ot.fee * abs(d.qty / ot.qty), 0) + coalesce(ct.fee * abs(d.qty / ct.qty), 0) AS fee,
           d.qty * (coalesce(ct.price, ot.price) - coalesce(ot.price, ols.value_acc / ols.amount_acc) ) - (coalesce(ot.fee * abs(d.qty / ot.qty), 0) + coalesce(ct.fee * abs(d.qty / ct.qty), 0) ) AS profit,
           coalesce(100 * (d.qty * (coalesce(ct.price, ot.price) - coalesce(ot.price, ols.value_acc / ols.amount_acc) ) - (coalesce(ot.fee * abs(d.qty / ot.qty), 0) + coalesce(ct.fee * abs(d.qty / ct.qty), 0) ) ) / abs(d.qty * coalesce(ot.price, ols.value_acc / ols.amount_acc) ), 0) AS rel_profit,
           coalesce(oca.type, -cca.type) AS corp_action
      FROM deals AS d
          -- Get more information about trade/corp.action that opened the deal
           LEFT JOIN sequence AS os ON d.open_sid = os.id
           LEFT JOIN trades AS ot ON ot.id = os.operation_id AND os.type = 3
           LEFT JOIN corp_actions AS oca ON oca.id = os.operation_id AND os.type = 5
          -- Collect value of stock that was accumulated before corporate action
           LEFT JOIN ledger AS ols ON ols.sid = d.open_sid AND ols.asset_id = d.asset_id AND ols.value_acc != 0
          -- Get more information about trade/corp.action that opened the deal
           LEFT JOIN sequence AS cs ON d.close_sid = cs.id
           LEFT JOIN trades AS ct ON ct.id = cs.operation_id AND cs.type = 3
           LEFT JOIN corp_actions AS cca ON cca.id = cs.operation_id AND cs.type = 5
          -- "Decode" account and asset
           LEFT JOIN accounts AS ac ON d.account_id = ac.id
           LEFT JOIN assets AS at ON d.asset_id = at.id
     -- drop cases where deal was opened and closed with corporate action
     WHERE NOT (os.type = 5 AND cs.type = 5)
     ORDER BY close_timestamp, open_timestamp;
--------------------------------------------------------------------------------
DROP TABLE IF EXISTS ledger_sums;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 1;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=29 WHERE name='SchemaVersion';
COMMIT;
