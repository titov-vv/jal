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
-- Set new DB schema version
UPDATE settings SET value=79 WHERE name='SchemaVersion';
COMMIT;
