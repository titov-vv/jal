BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 0;

--------------------------------------------------------------------------------
-- Change 'dividends' table to add 'type' and 'ex_date' fields
-- Type is set to 1 as it should contain only dividends before
--------------------------------------------------------------------------------
CREATE TABLE sqlitestudio_temp_table AS SELECT *
                                          FROM dividends;

DROP TABLE dividends;

CREATE TABLE dividends (
    id         INTEGER     PRIMARY KEY
                           UNIQUE
                           NOT NULL,
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
    sum        REAL        NOT NULL
                           DEFAULT (0),
    sum_tax    REAL        DEFAULT (0),
    note       TEXT (1014)
);

INSERT INTO dividends (
                          id,
                          timestamp,
                          number,
                          type,
                          account_id,
                          asset_id,
                          sum,
                          sum_tax,
                          note
                      )
                      SELECT id,
                             timestamp,
                             number,
                             1,
                             account_id,
                             asset_id,
                             sum,
                             sum_tax,
                             note
                        FROM sqlitestudio_temp_table;

DROP TABLE sqlitestudio_temp_table;

CREATE TRIGGER dividends_after_delete
         AFTER DELETE
            ON dividends
      FOR EACH ROW
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
PRAGMA foreign_keys = 1;

--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=16 WHERE name='SchemaVersion';

COMMIT;