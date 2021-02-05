BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 0;

--------------------------------------------------------------------------------
-- Drop unique constraints from t_last_assets table
--------------------------------------------------------------------------------
DROP TABLE t_last_assets;

CREATE TABLE t_last_assets (
    id          INTEGER NOT NULL,
    total_value REAL
);


--------------------------------------------------------------------------------
-- Change 'category_id' FK settings
--------------------------------------------------------------------------------
CREATE TABLE sqlitestudio_temp_table AS SELECT *
                                          FROM action_details;

DROP TABLE action_details;

CREATE TABLE action_details (
    id          INTEGER    PRIMARY KEY
                           NOT NULL
                           UNIQUE,
    pid         INTEGER    REFERENCES actions (id) ON DELETE CASCADE
                                                   ON UPDATE CASCADE
                           NOT NULL,
    category_id INTEGER    REFERENCES categories (id) ON DELETE CASCADE
                                                      ON UPDATE CASCADE
                           NOT NULL,
    tag_id      INTEGER    REFERENCES tags (id) ON DELETE SET NULL
                                                ON UPDATE CASCADE,
    sum         REAL       NOT NULL,
    alt_sum     REAL       DEFAULT (0),
    note        TEXT (256)
);

INSERT INTO action_details (
                               id,
                               pid,
                               category_id,
                               tag_id,
                               sum,
                               alt_sum,
                               note
                           )
                           SELECT id,
                                  pid,
                                  category_id,
                                  tag_id,
                                  sum,
                                  alt_sum,
                                  note
                             FROM sqlitestudio_temp_table;

DROP TABLE sqlitestudio_temp_table;

CREATE TRIGGER action_details_after_delete
         AFTER DELETE
            ON action_details
      FOR EACH ROW
BEGIN
    DELETE FROM ledger
          WHERE timestamp >= (
                                 SELECT timestamp
                                   FROM actions
                                  WHERE id = OLD.pid
                             );
    DELETE FROM sequence
          WHERE timestamp >= (
                                 SELECT timestamp
                                   FROM actions
                                  WHERE id = OLD.pid
                             );
    DELETE FROM ledger_sums
          WHERE timestamp >= (
                                 SELECT timestamp
                                   FROM actions
                                  WHERE id = OLD.pid
                             );
END;

CREATE TRIGGER action_details_after_insert
         AFTER INSERT
            ON action_details
      FOR EACH ROW
BEGIN
    DELETE FROM ledger
          WHERE timestamp >= (
                                 SELECT timestamp
                                   FROM actions
                                  WHERE id = NEW.pid
                             );
    DELETE FROM sequence
          WHERE timestamp >= (
                                 SELECT timestamp
                                   FROM actions
                                  WHERE id = NEW.pid
                             );
    DELETE FROM ledger_sums
          WHERE timestamp >= (
                                 SELECT timestamp
                                   FROM actions
                                  WHERE id = NEW.pid
                             );
END;

CREATE TRIGGER action_details_after_update
         AFTER UPDATE
            ON action_details
      FOR EACH ROW
BEGIN
    DELETE FROM ledger
          WHERE timestamp >= (
                                 SELECT timestamp
                                   FROM actions
                                  WHERE id = OLD.pid
                             );
    DELETE FROM sequence
          WHERE timestamp >= (
                                 SELECT timestamp
                                   FROM actions
                                  WHERE id = OLD.pid
                             );
    DELETE FROM ledger_sums
          WHERE timestamp >= (
                                 SELECT timestamp
                                   FROM actions
                                  WHERE id = OLD.pid
                             );
END;

--------------------------------------------------------------------------------
-- Change 'mapped_to' FK settings
--------------------------------------------------------------------------------

CREATE TABLE sqlitestudio_temp_table AS SELECT *
                                          FROM map_category;

DROP TABLE map_category;

CREATE TABLE map_category (
    id        INTEGER        PRIMARY KEY
                             UNIQUE
                             NOT NULL,
    value     VARCHAR (1024) NOT NULL,
    mapped_to INTEGER        NOT NULL
                             REFERENCES categories (id) ON DELETE CASCADE
                                                        ON UPDATE CASCADE
);

INSERT INTO map_category (
                             id,
                             value,
                             mapped_to
                         )
                         SELECT id,
                                value,
                                mapped_to
                           FROM sqlitestudio_temp_table;

DROP TABLE sqlitestudio_temp_table;

--------------------------------------------------------------------------------
-- Add 'note' field to 'trades' table
--------------------------------------------------------------------------------
CREATE TABLE sqlitestudio_temp_table AS SELECT *
                                          FROM trades;

DROP TABLE trades;

CREATE TABLE trades (
    id         INTEGER     PRIMARY KEY
                           UNIQUE
                           NOT NULL,
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
    coupon     REAL        DEFAULT (0),
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
                       coupon,
                       fee
                   )
                   SELECT id,
                          timestamp,
                          settlement,
                          number,
                          account_id,
                          asset_id,
                          qty,
                          price,
                          coupon,
                          fee
                     FROM sqlitestudio_temp_table;

DROP TABLE sqlitestudio_temp_table;

CREATE TRIGGER trades_after_delete
         AFTER DELETE
            ON trades
      FOR EACH ROW
BEGIN
    DELETE FROM ledger
          WHERE timestamp >= OLD.timestamp;
    DELETE FROM sequence
          WHERE timestamp >= OLD.timestamp;
    DELETE FROM ledger_sums
          WHERE timestamp >= OLD.timestamp;
END;

CREATE TRIGGER trades_after_insert
         AFTER INSERT
            ON trades
      FOR EACH ROW
BEGIN
    DELETE FROM ledger
          WHERE timestamp >= NEW.timestamp;
    DELETE FROM sequence
          WHERE timestamp >= NEW.timestamp;
    DELETE FROM ledger_sums
          WHERE timestamp >= NEW.timestamp;
END;

CREATE TRIGGER trades_after_update
         AFTER UPDATE OF timestamp,
                         account_id,
                         asset_id,
                         qty,
                         price,
                         coupon,
                         fee
            ON trades
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
UPDATE settings SET value=14 WHERE name='SchemaVersion';

COMMIT;
