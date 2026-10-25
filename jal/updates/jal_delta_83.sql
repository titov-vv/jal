BEGIN TRANSACTION;
--------------------------------------------------------------------------------
-- PREDEFINED CATEGORY 'LOSSES' TAKES ID 11
--------------------------------------------------------------------------------
-- A user category with id 11 moves to the next free id. Foreign keys are off during an upgrade, so the references
-- are moved by hand too (with them on, the id's update has moved them already); the ledger is rebuilt from there
DELETE FROM ledger WHERE timestamp >= (SELECT MIN(timestamp) FROM ledger WHERE category_id=11);
CREATE TEMP TABLE category_move AS SELECT MAX(id) + 1 AS new_id FROM categories;
UPDATE categories SET id=(SELECT new_id FROM category_move) WHERE id=11;
UPDATE categories SET pid=(SELECT new_id FROM category_move) WHERE pid=11;
UPDATE action_details SET category_id=(SELECT new_id FROM category_move) WHERE category_id=11;
DROP TABLE category_move;
-- Names are unique: a user category of the same name (English or Russian) steps aside
UPDATE categories SET name=name || ' (user)' WHERE name IN ('Losses', 'Убытки');
INSERT INTO categories (id, pid, name) VALUES (11, 2, 'Losses');
--------------------------------------------------------------------------------
INSERT OR REPLACE INTO settings(name, value) VALUES ('RebuildDB', 1);
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=83 WHERE name='SchemaVersion';
COMMIT;
