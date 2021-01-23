BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 0;

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
-- Set new DB schema version
UPDATE settings SET value=13 WHERE name='SchemaVersion';

COMMIT;

