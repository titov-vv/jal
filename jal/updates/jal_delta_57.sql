BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = OFF;
--------------------------------------------------------------------------------
-- Insert root elements for tree-structure supported by foreign key
INSERT INTO agents (id, pid, name) VALUES (0, 0, '<ROOT>');
INSERT INTO categories (id, pid, name, often) VALUES (0, 0, '<ROOT>', 0);
INSERT INTO tags (id, pid, tag) VALUES (0, 0, '<ROOT>');
--------------------------------------------------------------------------------
-- Introduce foreign keys into tables that have data structured as a tree
-- Fix any possible problems with NULL
UPDATE agents SET location='' WHERE location IS NULL;
UPDATE tags SET icon_file='' WHERE icon_file IS NULL;
-- Update Agents table
DROP TABLE IF EXISTS temp_agents;
CREATE TABLE temp_agents AS SELECT * FROM agents;
DROP TABLE agents;
CREATE TABLE agents (
    id       INTEGER    PRIMARY KEY UNIQUE NOT NULL,
    pid      INTEGER    NOT NULL DEFAULT (0) REFERENCES agents (id) ON DELETE CASCADE ON UPDATE CASCADE,
    name     TEXT (64)  UNIQUE NOT NULL,
    location TEXT (128) NOT NULL DEFAULT ('')
);
INSERT INTO agents (id, pid, name, location) SELECT id, pid, name, location FROM temp_agents;
DROP TABLE temp_agents;
-- Update Categories table
DROP TABLE IF EXISTS temp_categories;
CREATE TABLE temp_categories AS SELECT * FROM categories;
DROP TABLE categories;
CREATE TABLE categories (
    id      INTEGER   PRIMARY KEY UNIQUE NOT NULL,
    pid     INTEGER   NOT NULL DEFAULT (0) REFERENCES categories (id) ON DELETE CASCADE ON UPDATE CASCADE,
    name    TEXT (64) UNIQUE NOT NULL
);
INSERT INTO categories (id, pid, name) SELECT id, pid, name FROM temp_categories;
DROP TABLE temp_categories;
-- Update Tags table
DROP TABLE IF EXISTS temp_tags;
CREATE TABLE temp_tags AS SELECT * FROM tags;
DROP TABLE tags;
CREATE TABLE tags (
    id         INTEGER   PRIMARY KEY UNIQUE NOT NULL,
    pid        INTEGER   NOT NULL DEFAULT (0) REFERENCES tags (id) ON DELETE CASCADE ON UPDATE CASCADE,
    tag        TEXT (64) NOT NULL UNIQUE,
    icon_file  TEXT      DEFAULT ('') NOT NULL
);
INSERT INTO tags (id, pid, tag, icon_file) SELECT id, pid, tag, icon_file FROM temp_tags;
DROP TABLE temp_tags;
-- Restore index
CREATE INDEX agents_by_name_idx ON agents (name);
-- Restore triggers
CREATE TRIGGER keep_predefined_agents BEFORE DELETE ON agents FOR EACH ROW WHEN OLD.id <= 1 BEGIN SELECT RAISE (ABORT, 'JAL_SQL_MSG_0001'); END;
CREATE TRIGGER keep_predefined_categories BEFORE DELETE ON categories FOR EACH ROW WHEN OLD.id <= 9 BEGIN SELECT RAISE (ABORT, 'JAL_SQL_MSG_0002'); END;
--------------------------------------------------------------------------------
DROP TABLE IF EXISTS ledger;
CREATE TABLE ledger (
    id           INTEGER PRIMARY KEY NOT NULL UNIQUE,
    timestamp    INTEGER NOT NULL,
    otype        INTEGER NOT NULL,
    oid          INTEGER NOT NULL,
    opart        INTEGER NOT NULL,
    book_account INTEGER NOT NULL,
    asset_id     INTEGER REFERENCES assets (id) ON DELETE SET NULL ON UPDATE SET NULL,
    account_id   INTEGER NOT NULL REFERENCES accounts (id) ON DELETE NO ACTION ON UPDATE NO ACTION,
    amount       TEXT,
    value        TEXT,
    amount_acc   TEXT,
    value_acc    TEXT,
    peer_id      INTEGER REFERENCES agents (id) ON DELETE NO ACTION ON UPDATE NO ACTION,
    category_id  INTEGER REFERENCES categories (id) ON DELETE NO ACTION ON UPDATE NO ACTION,
    tag_id       INTEGER REFERENCES tags (id) ON DELETE NO ACTION ON UPDATE NO ACTION
);
--------------------------------------------------------------------------------
-- Actions cleanup if all details were deleted
DROP TRIGGER IF EXISTS action_details_parent_clean;
CREATE TRIGGER action_details_parent_clean
AFTER DELETE ON action_details WHEN (SELECT COUNT(id) FROM action_details WHERE pid = OLD.pid) = 0
BEGIN
    DELETE FROM actions WHERE oid = OLD.pid;
END;
-- Add new triggers for ledger update after change in reference data
DROP TRIGGER IF EXISTS categories_after_delete;
CREATE TRIGGER categories_after_delete AFTER DELETE ON tags FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= (SELECT MIN(timestamp) FROM ledger WHERE category_id=OLD.id);
END;
DROP TRIGGER IF EXISTS tags_after_delete;
CREATE TRIGGER tags_after_delete AFTER DELETE ON tags FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= (SELECT MIN(timestamp) FROM ledger WHERE tag_id=OLD.id);
    DELETE FROM asset_data WHERE datatype=4 AND value=OLD.id;
END;

--------------------------------------------------------------------------------
-- Error correction in trigger definition
DROP TRIGGER IF EXISTS deposit_action_after_update;
CREATE TRIGGER deposit_action_after_update AFTER UPDATE OF timestamp, action_type, amount ON deposit_actions FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
END;

--------------------------------------------------------------------------------
-- Modify view
DROP VIEW IF EXISTS operation_sequence;
CREATE VIEW operation_sequence AS SELECT m.otype, m.oid, opart, m.timestamp, m.account_id
FROM
(
    SELECT otype, 1 AS seq, oid, 0 AS opart, timestamp, account_id FROM actions
    UNION ALL
    SELECT otype, 2 AS seq, oid, 0 AS opart, timestamp, account_id FROM asset_payments
    UNION ALL
    SELECT otype, 3 AS seq, oid, 0 AS opart, timestamp, account_id FROM asset_actions
    UNION ALL
    SELECT otype, 4 AS seq, oid, 0 AS opart, timestamp, account_id FROM trades
    UNION ALL
    SELECT otype, 5 AS seq, oid, -1 AS opart, withdrawal_timestamp AS timestamp, withdrawal_account AS account_id FROM transfers
    UNION ALL
    SELECT otype, 5 AS seq, oid, 0 AS opart, withdrawal_timestamp AS timestamp, fee_account AS account_id FROM transfers WHERE NOT fee IS NULL
    UNION ALL
    SELECT otype, 5 AS seq, oid, 1 AS opart, deposit_timestamp AS timestamp, deposit_account AS account_id FROM transfers
    UNION ALL
    SELECT td.otype, 6 AS seq, td.oid, da.id AS opart, da.timestamp, td.account_id FROM deposit_actions AS da LEFT JOIN term_deposits AS td ON da.deposit_id=td.oid
) AS m
ORDER BY m.timestamp, m.seq, m.opart, m.oid;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=57 WHERE name='SchemaVersion';
INSERT OR REPLACE INTO settings(name, value) VALUES ('RebuildDB', 1);
COMMIT;
VACUUM;