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
      WHEN (SELECT value FROM settings WHERE id = 1)
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
      WHEN (SELECT value FROM settings WHERE id = 1)
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
      WHEN (SELECT value FROM settings WHERE id = 1)
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
-- Update all triggers
--------------------------------------------------------------------------------
DROP TRIGGER action_details_after_delete;
CREATE TRIGGER action_details_after_delete
         AFTER DELETE
            ON action_details
      FOR EACH ROW
          WHEN (
    SELECT value
      FROM settings
     WHERE id = 1
)
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

DROP TRIGGER action_details_after_insert;
CREATE TRIGGER action_details_after_insert
         AFTER INSERT
            ON action_details
      FOR EACH ROW
          WHEN (
    SELECT value
      FROM settings
     WHERE id = 1
)
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

DROP TRIGGER action_details_after_update;
CREATE TRIGGER action_details_after_update
         AFTER UPDATE
            ON action_details
      FOR EACH ROW
          WHEN (
    SELECT value
      FROM settings
     WHERE id = 1
)
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

DROP TRIGGER dividends_after_delete;
CREATE TRIGGER dividends_after_delete
         AFTER DELETE
            ON dividends
      FOR EACH ROW
          WHEN (
    SELECT value
      FROM settings
     WHERE id = 1
)
BEGIN
    DELETE FROM ledger
          WHERE timestamp >= OLD.timestamp;
    DELETE FROM sequence
          WHERE timestamp >= OLD.timestamp;
    DELETE FROM ledger_sums
          WHERE timestamp >= OLD.timestamp;
END;

DROP TRIGGER dividends_after_insert;
CREATE TRIGGER dividends_after_insert
         AFTER INSERT
            ON dividends
      FOR EACH ROW
          WHEN (
    SELECT value
      FROM settings
     WHERE id = 1
)
BEGIN
    DELETE FROM ledger
          WHERE timestamp >= NEW.timestamp;
    DELETE FROM sequence
          WHERE timestamp >= NEW.timestamp;
    DELETE FROM ledger_sums
          WHERE timestamp >= NEW.timestamp;
END;

DROP TRIGGER dividends_after_update;
CREATE TRIGGER dividends_after_update
         AFTER UPDATE OF timestamp,
                         account_id,
                         asset_id,
                         amount,
                         tax
            ON dividends
      FOR EACH ROW
          WHEN (
    SELECT value
      FROM settings
     WHERE id = 1
)
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

DROP TRIGGER trades_after_delete;
CREATE TRIGGER trades_after_delete
         AFTER DELETE
            ON trades
      FOR EACH ROW
          WHEN (
    SELECT value
      FROM settings
     WHERE id = 1
)
BEGIN
    DELETE FROM ledger
          WHERE timestamp >= OLD.timestamp;
    DELETE FROM sequence
          WHERE timestamp >= OLD.timestamp;
    DELETE FROM ledger_sums
          WHERE timestamp >= OLD.timestamp;
END;

DROP TRIGGER trades_after_insert;
CREATE TRIGGER trades_after_insert
         AFTER INSERT
            ON trades
      FOR EACH ROW
          WHEN (
    SELECT value
      FROM settings
     WHERE id = 1
)
BEGIN
    DELETE FROM ledger
          WHERE timestamp >= NEW.timestamp;
    DELETE FROM sequence
          WHERE timestamp >= NEW.timestamp;
    DELETE FROM ledger_sums
          WHERE timestamp >= NEW.timestamp;
END;

DROP TRIGGER trades_after_update;
CREATE TRIGGER trades_after_update
         AFTER UPDATE OF timestamp,
                         account_id,
                         asset_id,
                         qty,
                         price,
                         fee
            ON trades
      FOR EACH ROW
          WHEN (
    SELECT value
      FROM settings
     WHERE id = 1
)
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

DROP TRIGGER corp_after_delete;
CREATE TRIGGER corp_after_delete
         AFTER DELETE
            ON corp_actions
      FOR EACH ROW
          WHEN (
    SELECT value
      FROM settings
     WHERE id = 1
)
BEGIN
    DELETE FROM ledger
          WHERE timestamp >= OLD.timestamp;
    DELETE FROM sequence
          WHERE timestamp >= OLD.timestamp;
    DELETE FROM ledger_sums
          WHERE timestamp >= OLD.timestamp;
END;

DROP TRIGGER corp_after_insert;
CREATE TRIGGER corp_after_insert
         AFTER INSERT
            ON corp_actions
      FOR EACH ROW
          WHEN (
    SELECT value
      FROM settings
     WHERE id = 1
)
BEGIN
    DELETE FROM ledger
          WHERE timestamp >= NEW.timestamp;
    DELETE FROM sequence
          WHERE timestamp >= NEW.timestamp;
    DELETE FROM ledger_sums
          WHERE timestamp >= NEW.timestamp;
END;

DROP TRIGGER corp_after_update;
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
          WHEN (
    SELECT value
      FROM settings
     WHERE id = 1
)
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

DROP TRIGGER transfers_after_delete;
CREATE TRIGGER transfers_after_delete
         AFTER DELETE
            ON transfers
      FOR EACH ROW
          WHEN (
    SELECT value
      FROM settings
     WHERE id = 1
)
BEGIN
    DELETE FROM ledger
          WHERE timestamp >= OLD.withdrawal_timestamp OR
                timestamp >= OLD.deposit_timestamp;
    DELETE FROM sequence
          WHERE timestamp >= OLD.withdrawal_timestamp OR
                timestamp >= OLD.deposit_timestamp;
    DELETE FROM ledger_sums
          WHERE timestamp >= OLD.withdrawal_timestamp OR
                timestamp >= OLD.deposit_timestamp;
END;

DROP TRIGGER transfers_after_insert;
CREATE TRIGGER transfers_after_insert
         AFTER INSERT
            ON transfers
      FOR EACH ROW
          WHEN (
    SELECT value
      FROM settings
     WHERE id = 1
)
BEGIN
    DELETE FROM ledger
          WHERE timestamp >= NEW.withdrawal_timestamp OR
                timestamp >= NEW.deposit_timestamp;
    DELETE FROM sequence
          WHERE timestamp >= NEW.withdrawal_timestamp OR
                timestamp >= NEW.deposit_timestamp;
    DELETE FROM ledger_sums
          WHERE timestamp >= NEW.withdrawal_timestamp OR
                timestamp >= NEW.deposit_timestamp;
END;

DROP TRIGGER transfers_after_update;
CREATE TRIGGER transfers_after_update
         AFTER UPDATE OF withdrawal_timestamp,
                         deposit_timestamp,
                         withdrawal_account,
                         deposit_account,
                         fee_account,
                         withdrawal,
                         deposit,
                         fee,
                         asset
            ON transfers
      FOR EACH ROW
          WHEN (
    SELECT value
      FROM settings
     WHERE id = 1
)
BEGIN
    DELETE FROM ledger
          WHERE timestamp >= OLD.withdrawal_timestamp OR
                timestamp >= OLD.deposit_timestamp OR
                timestamp >= NEW.withdrawal_timestamp OR
                timestamp >= NEW.deposit_timestamp;
    DELETE FROM sequence
          WHERE timestamp >= OLD.withdrawal_timestamp OR
                timestamp >= OLD.deposit_timestamp OR
                timestamp >= NEW.withdrawal_timestamp OR
                timestamp >= NEW.deposit_timestamp;
    DELETE FROM ledger_sums
          WHERE timestamp >= OLD.withdrawal_timestamp OR
                timestamp >= OLD.deposit_timestamp OR
                timestamp >= NEW.withdrawal_timestamp OR
                timestamp >= NEW.deposit_timestamp;
END;


--------------------------------------------------------------------------------
PRAGMA foreign_keys = 1;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=20 WHERE name='SchemaVersion';
COMMIT;