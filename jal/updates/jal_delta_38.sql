BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 0;
--------------------------------------------------------------------------------
-- Conversion of Action details table from REAL to TEXT storage of decimal values
CREATE TABLE old_details AS SELECT * FROM action_details;
DROP TABLE action_details;
CREATE TABLE action_details (
    id          INTEGER    PRIMARY KEY NOT NULL UNIQUE,
    pid         INTEGER    REFERENCES actions (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    category_id INTEGER    REFERENCES categories (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    tag_id      INTEGER    REFERENCES tags (id) ON DELETE SET NULL ON UPDATE CASCADE,
    amount      TEXT       NOT NULL,
    amount_alt  TEXT       DEFAULT ('0.0') NOT NULL,
    note        TEXT (256)
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
PRAGMA foreign_keys = 1;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=38 WHERE name='SchemaVersion';
COMMIT;
--------------------------------------------------------------------------------
-- Reduce file size
VACUUM;
