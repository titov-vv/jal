BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 0;
--------------------------------------------------------------------------------
-- Drop table books
DROP TABLE IF EXISTS ledger;
CREATE TABLE ledger (
    id           INTEGER PRIMARY KEY NOT NULL UNIQUE,
    timestamp    INTEGER NOT NULL,
    op_type      INTEGER NOT NULL,
    operation_id INTEGER NOT NULL,
    book_account INTEGER NOT NULL,
    asset_id     INTEGER REFERENCES assets (id) ON DELETE SET NULL ON UPDATE SET NULL,
    account_id   INTEGER NOT NULL REFERENCES accounts (id) ON DELETE NO ACTION ON UPDATE NO ACTION,
    amount       REAL,
    value        REAL,
    amount_acc   REAL,
    value_acc    REAL,
    peer_id      INTEGER REFERENCES agents (id) ON DELETE NO ACTION ON UPDATE NO ACTION,
    category_id  INTEGER REFERENCES categories (id) ON DELETE NO ACTION ON UPDATE NO ACTION,
    tag_id       INTEGER REFERENCES tags (id) ON DELETE NO ACTION ON UPDATE NO ACTION
);
DROP TABLE IF EXISTS books;

---------------------------------------------------------------------------------
-- Conversion of action_details table from REAL to TEXT storage of decimal values
CREATE TABLE old_details AS SELECT * FROM action_details;
DROP TABLE IF EXISTS action_details;
CREATE TABLE action_details (
    id          INTEGER    PRIMARY KEY NOT NULL UNIQUE,
    pid         INTEGER    REFERENCES actions (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    category_id INTEGER    REFERENCES categories (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    tag_id      INTEGER    REFERENCES tags (id) ON DELETE SET NULL ON UPDATE CASCADE,
    amount      TEXT       NOT NULL,
    amount_alt  TEXT       DEFAULT ('0.0') NOT NULL,
    note        TEXT
);

INSERT INTO action_details (id, pid, category_id, tag_id, amount, amount_alt, note)
  SELECT id, pid, category_id, tag_id, CAST(ROUND(amount, 9) AS TEXT), CAST(ROUND(amount_alt, 9) AS TEXT), note
  FROM old_details;
DROP TABLE old_details;

CREATE INDEX details_by_pid ON action_details (pid);

DROP TRIGGER IF EXISTS action_details_after_delete;
CREATE TRIGGER action_details_after_delete
      AFTER DELETE ON action_details
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= (SELECT timestamp FROM actions WHERE id = OLD.pid);
END;

DROP TRIGGER IF EXISTS action_details_after_insert;
CREATE TRIGGER action_details_after_insert
      AFTER INSERT ON action_details
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= (SELECT timestamp FROM actions WHERE id = NEW.pid);
END;

DROP TRIGGER IF EXISTS action_details_after_update;
CREATE TRIGGER action_details_after_update
      AFTER UPDATE ON action_details
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= (SELECT timestamp FROM actions WHERE id = OLD.pid );
END;
--------------------------------------------------------------------------------
-- Conversion of action_results table from REAL to TEXT storage of decimal values
CREATE TABLE old_results AS SELECT * FROM action_results;
DROP TABLE IF EXISTS action_results;
CREATE TABLE action_results (
    id          INTEGER PRIMARY KEY UNIQUE NOT NULL,
    action_id   INTEGER NOT NULL REFERENCES asset_actions (id) ON DELETE CASCADE ON UPDATE CASCADE,
    asset_id    INTEGER REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    qty         TEXT    NOT NULL,
    value_share TEXT    NOT NULL
);
INSERT INTO action_results (id, action_id, asset_id, qty, value_share)
  SELECT id, action_id, asset_id, CAST(ROUND(qty, 9) AS TEXT), CAST(ROUND(value_share, 9) AS TEXT)
  FROM old_results;
DROP TABLE old_results;

DROP TRIGGER IF EXISTS asset_result_after_delete;
CREATE TRIGGER asset_result_after_delete
      AFTER DELETE ON action_results
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= (SELECT timestamp FROM asset_actions WHERE id = OLD.action_id);
END;

DROP TRIGGER IF EXISTS asset_result_after_insert;
CREATE TRIGGER asset_result_after_insert
      AFTER INSERT ON action_results
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= (SELECT timestamp FROM asset_actions WHERE id = NEW.action_id);
END;

DROP TRIGGER IF EXISTS asset_result_after_update;
CREATE TRIGGER asset_result_after_update
      AFTER UPDATE OF asset_id, qty, value_share ON action_results
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= (SELECT timestamp FROM asset_actions WHERE id = OLD.action_id);
END;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 1;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=38 WHERE name='SchemaVersion';
COMMIT;
--------------------------------------------------------------------------------
-- Reduce file size
VACUUM;
