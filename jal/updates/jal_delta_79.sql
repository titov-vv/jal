BEGIN TRANSACTION;
--------------------------------------------------------------------------------
-- A RECEIPT IS IMPORTED ONCE
--------------------------------------------------------------------------------
-- The fiscal document id of a shop receipt ('<NIF>:<doc id>' for Portugal, '<fn>:<i>:<fp>' for Russia), empty for
-- anything typed by hand. The receipt import refuses a document whose id is here already.
ALTER TABLE actions ADD COLUMN number TEXT NOT NULL DEFAULT ('');
--------------------------------------------------------------------------------
-- RECEIPT CATEGORY RECOGNITION IS REMOVED
--------------------------------------------------------------------------------
-- Product names remembered as training data for the recognizer
DROP TABLE IF EXISTS map_category;
-- The receipt lines lost their hidden 'confidence' column; a stored layout of the old columns would hide 'Tag'
DELETE FROM settings WHERE name='ColumnsState_ImportReceiptDialog_LinesTableView';
--------------------------------------------------------------------------------
-- LIDL PLUS AND PINGO DOCE RECEIPT APIS ARE REMOVED
--------------------------------------------------------------------------------
DELETE FROM settings WHERE name IN ('EuLidlClientSecret', 'EuLidlAccessToken', 'EuLidlRefreshToken',
                                    'PtPingoDoceAccessToken', 'PtPingoDoceRefreshToken', 'PtPingoDoceUserProfile');
--------------------------------------------------------------------------------
-- PREDEFINED CATEGORY 'DISCOUNTS' TAKES ID 10
--------------------------------------------------------------------------------
-- A user category with id 10 moves to the next free id. Foreign keys are off during an upgrade, so the references
-- are moved by hand too (with them on, the id's update has moved them already); the ledger is rebuilt from there
DELETE FROM ledger WHERE timestamp >= (SELECT MIN(timestamp) FROM ledger WHERE category_id=10);
CREATE TEMP TABLE category_move AS SELECT MAX(id) + 1 AS new_id FROM categories;
UPDATE categories SET id=(SELECT new_id FROM category_move) WHERE id=10;
UPDATE categories SET pid=(SELECT new_id FROM category_move) WHERE pid=10;
UPDATE action_details SET category_id=(SELECT new_id FROM category_move) WHERE category_id=10;
DROP TABLE category_move;
-- Names are unique: a user category of the same name (English or Russian) steps aside
UPDATE categories SET name=name || ' (user)' WHERE name IN ('Discounts', 'Скидки');
INSERT INTO categories (id, pid, name) VALUES (10, 2, 'Discounts');
--------------------------------------------------------------------------------
INSERT OR REPLACE INTO settings(name, value) VALUES ('RebuildDB', 1);
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=79 WHERE name='SchemaVersion';
COMMIT;
