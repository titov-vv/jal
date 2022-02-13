BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 0;
--------------------------------------------------------------------------------
DELETE FROM ledger;  -- to rebuild all as we cleaning deals
------------------------------------------------------------------------------------------------------------------------
-- Move stock dividends from corporate actions to dividends table
INSERT INTO dividends (op_type, timestamp, number, type, account_id, asset_id, amount, tax, note)
SELECT 2, timestamp, number, 3, account_id, asset_id, qty_new-qty, 0, note FROM corp_actions WHERE type=5;
DELETE FROM corp_actions WHERE type=5;
------------------------------------------------------------------------------------------------------------------------
-- Add open/close prices in deals table
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
    open_price      REAL    NOT NULL,
    close_op_type   INTEGER NOT NULL,
    close_op_id     INTEGER NOT NULL,
    close_timestamp INTEGER NOT NULL,
    close_price     REAL    NOT NULL,
    qty             REAL    NOT NULL
);

CREATE TRIGGER on_deal_delete
         AFTER DELETE
            ON deals
    FOR EACH ROW
    WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    UPDATE open_trades
       SET remaining_qty = remaining_qty + OLD.qty
     WHERE op_type=OLD.open_op_type AND operation_id=OLD.open_op_id AND account_id=OLD.account_id AND asset_id = OLD.asset_id;
END;

--------------------------------------------------------------------------------
-- Simplify deals_ext view
DROP VIEW deals_ext;
CREATE VIEW deals_ext AS
    SELECT d.account_id,
           ac.name AS account,
           d.asset_id,
           at.name AS asset,
           open_timestamp,
           close_timestamp,
           open_price,
           close_price,
           d.qty AS qty,
           coalesce(ot.fee * abs(d.qty / ot.qty), 0) + coalesce(ct.fee * abs(d.qty / ct.qty), 0) AS fee,
           d.qty * (close_price - open_price ) - (coalesce(ot.fee * abs(d.qty / ot.qty), 0) + coalesce(ct.fee * abs(d.qty / ct.qty), 0) ) AS profit,
           coalesce(100 * (d.qty * (close_price - open_price ) - (coalesce(ot.fee * abs(d.qty / ot.qty), 0) + coalesce(ct.fee * abs(d.qty / ct.qty), 0) ) ) / abs(d.qty * open_price ), 0) AS rel_profit,
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
-- Updates all operations with more info about stock dividends
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
                      l.amount_acc AS t_qty,
                      d.note AS note,
                      c.name AS note2
                 FROM dividends AS d
                      LEFT JOIN assets AS a ON d.asset_id = a.id
                      LEFT JOIN countries AS c ON a.country_id = c.id
                      LEFT JOIN ledger_totals AS l ON l.op_type=d.op_type AND l.operation_id=d.id AND l.book_account = 4
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
                      LEFT JOIN ledger_totals AS l ON l.op_type = ca.op_type AND l.operation_id=ca.id AND l.asset_id = ca.asset_id_new AND l.book_account = 4
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
                      LEFT JOIN ledger_totals AS l ON l.op_type=t.op_type AND l.operation_id=t.id AND l.book_account = 4
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
           LEFT JOIN ledger_totals AS money ON money.op_type=m.type AND money.operation_id=m.id AND money.account_id = m.account_id AND money.book_account = 3
           LEFT JOIN ledger_totals AS debt ON debt.op_type=m.type AND debt.operation_id=m.id AND debt.account_id = m.account_id AND debt.book_account = 5
    ORDER BY m.timestamp;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 1;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=31 WHERE name='SchemaVersion';
INSERT OR REPLACE INTO settings(id, name, value) VALUES (7, 'RebuildDB', 1);
COMMIT;
