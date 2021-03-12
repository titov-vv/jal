BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 0;
--------------------------------------------------------------------------------
CREATE TABLE sqlitestudio_temp_table AS SELECT * FROM actions;
DROP TABLE actions;

CREATE TABLE actions (
    id              INTEGER PRIMARY KEY
                            UNIQUE
                            NOT NULL,
    timestamp       INTEGER NOT NULL,
    account_id      INTEGER REFERENCES accounts (id) ON DELETE CASCADE
                                                     ON UPDATE CASCADE
                            NOT NULL,
    peer_id         INTEGER REFERENCES agents (id) ON DELETE CASCADE
                                                   ON UPDATE CASCADE
                            NOT NULL,
    alt_currency_id INTEGER REFERENCES assets (id) ON DELETE RESTRICT
                                                   ON UPDATE CASCADE
);

INSERT INTO actions (
                        id,
                        timestamp,
                        account_id,
                        peer_id,
                        alt_currency_id
                    )
                    SELECT id,
                           timestamp,
                           account_id,
                           peer_id,
                           alt_currency_id
                      FROM sqlitestudio_temp_table;

DROP TABLE sqlitestudio_temp_table;

CREATE TRIGGER actions_after_delete
         AFTER DELETE
            ON actions
      FOR EACH ROW
BEGIN
    DELETE FROM action_details
          WHERE pid = OLD.id;
    DELETE FROM ledger
          WHERE timestamp >= OLD.timestamp;
    DELETE FROM sequence
          WHERE timestamp >= OLD.timestamp;
    DELETE FROM ledger_sums
          WHERE timestamp >= OLD.timestamp;
END;

CREATE TRIGGER actions_after_insert
         AFTER INSERT
            ON actions
      FOR EACH ROW
BEGIN
    DELETE FROM ledger
          WHERE timestamp >= NEW.timestamp;
    DELETE FROM sequence
          WHERE timestamp >= NEW.timestamp;
    DELETE FROM ledger_sums
          WHERE timestamp >= NEW.timestamp;
END;

CREATE TRIGGER actions_after_update
         AFTER UPDATE OF timestamp,
                         account_id,
                         peer_id
            ON actions
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
UPDATE settings SET value=20 WHERE name='SchemaVersion';
COMMIT;