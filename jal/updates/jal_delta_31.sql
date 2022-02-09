BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 0;
--------------------------------------------------------------------------------
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
PRAGMA foreign_keys = 1;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=31 WHERE name='SchemaVersion';
INSERT OR REPLACE INTO settings(id, name, value) VALUES (7, 'RebuildDB', 1);
COMMIT;
