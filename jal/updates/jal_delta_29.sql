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
-                     1 AS subtype,
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
