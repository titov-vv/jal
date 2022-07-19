BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 0;
--------------------------------------------------------------------------------
ALTER TABLE corp_actions RENAME TO asset_actions;

-- Make new structure for corporate actions
DROP TABLE IF EXISTS action_results;
CREATE TABLE action_results (
    id          INTEGER PRIMARY KEY UNIQUE NOT NULL,
    action_id   INTEGER NOT NULL REFERENCES asset_actions (id) ON DELETE CASCADE ON UPDATE CASCADE,
    asset_id    INTEGER REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    qty         REAL    NOT NULL,
    value_share REAL    NOT NULL
);

-- Populate new table with corporate actions' results
INSERT INTO action_results (action_id, asset_id, qty, value_share)
SELECT id, asset_id, qty, value_share FROM
(SELECT id, asset_id_new AS asset_id, qty_new AS qty, 1 AS value_share FROM asset_actions WHERE type=1 OR type=3 OR type=4
UNION ALL
SELECT id, asset_id_new AS asset_id, qty_new AS qty, (1-basis_ratio) AS value_share FROM asset_actions WHERE type=2
UNION ALL
SELECT id, asset_id, qty, basis_ratio AS value_share FROM asset_actions WHERE type=2)
ORDER BY id;

-- Trim initial corporate actions table
ALTER TABLE asset_actions DROP COLUMN asset_id_new;
ALTER TABLE asset_actions DROP COLUMN qty_new;
ALTER TABLE asset_actions DROP COLUMN basis_ratio;

-- Create triggers
DROP TRIGGER IF EXISTS corp_after_delete;
CREATE TRIGGER asset_action_after_delete
      AFTER DELETE ON asset_actions
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp;
    DELETE FROM open_trades WHERE timestamp >= OLD.timestamp;
END;

DROP TRIGGER IF EXISTS corp_after_insert;
CREATE TRIGGER asset_action_after_insert
      AFTER INSERT ON asset_actions
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= NEW.timestamp;
    DELETE FROM open_trades WHERE timestamp >= NEW.timestamp;
END;

DROP TRIGGER IF EXISTS corp_after_update;
CREATE TRIGGER asset_action_after_update
      AFTER UPDATE OF timestamp, account_id, type, asset_id, qty ON asset_actions
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
    DELETE FROM open_trades WHERE timestamp >= OLD.timestamp  OR timestamp >= NEW.timestamp;
END;

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
UPDATE settings SET value=37 WHERE name='SchemaVersion';
COMMIT;
