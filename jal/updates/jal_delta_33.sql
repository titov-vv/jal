BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 0;
--------------------------------------------------------------------------------
-- Link asset symbol from asset_tickers, no assets
DROP VIEW IF EXISTS deals_ext;
CREATE VIEW deals_ext AS
    SELECT d.account_id,
           ac.name AS account,
           d.asset_id,
           at.symbol AS asset,
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
           LEFT JOIN asset_tickers AS at ON d.asset_id = at.asset_id AND ac.currency_id=at.currency_id AND at.active=1
     -- drop cases where deal was opened and closed with corporate action
     WHERE NOT (d.open_op_type = 5 AND d.close_op_type = 5)
     ORDER BY close_timestamp, open_timestamp;
--------------------------------------------------------------------------------
-- Add again coutries that are probably escaped from sequential updates
INSERT OR IGNORE INTO countries (id, name, code, iso_code, tax_treaty) VALUES (8, 'Italy', 'it', '380', 1);
INSERT OR IGNORE INTO countries (id, name, code, iso_code, tax_treaty) VALUES (9, 'Spain', 'es', '724', 1);
INSERT OR IGNORE INTO countries (id, name, code, iso_code, tax_treaty) VALUES (10, 'Australia', 'au', '036', 1);
INSERT OR IGNORE INTO countries (id, name, code, iso_code, tax_treaty) VALUES (11, 'Austria', 'at', '040', 1);
INSERT OR IGNORE INTO countries (id, name, code, iso_code, tax_treaty) VALUES (12, 'Belgium', 'be', '056', 1);
INSERT OR IGNORE INTO countries (id, name, code, iso_code, tax_treaty) VALUES (13, 'United Kingdom', 'gb', '826', 1);
INSERT OR IGNORE INTO countries (id, name, code, iso_code, tax_treaty) VALUES (14, 'Germany', 'de', '276', 1);
INSERT OR IGNORE INTO countries (id, name, code, iso_code, tax_treaty) VALUES (15, 'China', 'cn', '156', 1);
INSERT OR IGNORE INTO countries (id, name, code, iso_code, tax_treaty) VALUES (16, 'Netherlands', 'nl', '528', 1);
INSERT OR IGNORE INTO countries (id, name, code, iso_code, tax_treaty) VALUES (17, 'Greece', 'gr', '300', 1);
INSERT OR IGNORE INTO countries (id, name, code, iso_code, tax_treaty) VALUES (18, 'Bermuda', 'bm', '060', 0);
INSERT OR IGNORE INTO countries (id, name, code, iso_code, tax_treaty) VALUES (19, 'Finland', 'fi', '246', 1);
INSERT OR IGNORE INTO countries (id, name, code, iso_code, tax_treaty) VALUES (20, 'Brazil', 'br', '076', 0);
INSERT OR IGNORE INTO countries (id, name, code, iso_code, tax_treaty) VALUES (21, 'Jersey', 'je', '832', 0);
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 1;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=33 WHERE name='SchemaVersion';
COMMIT;
