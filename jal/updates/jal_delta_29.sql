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
           LEFT JOIN
           sequence AS os ON d.open_sid = os.id
           LEFT JOIN
           trades AS ot ON ot.id = os.operation_id AND
                           os.type = 3
           LEFT JOIN
           corp_actions AS oca ON oca.id = os.operation_id AND
                                  os.type = 5
           LEFT JOIN
           ledger AS ols ON ols.sid = d.open_sid AND
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
--------------------------------------------------------------------------------
DROP TABLE IF EXISTS ledger_sums;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 1;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=29 WHERE name='SchemaVersion';
COMMIT;