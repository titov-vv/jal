BEGIN TRANSACTION;
--------------------------------------------------------------------------------
-- A RECEIPT IS IMPORTED ONCE
--------------------------------------------------------------------------------
-- The fiscal document id of a shop receipt ('<NIF>:<doc id>' for Portugal, '<fn>:<i>:<fp>' for Russia), empty for
-- anything typed by hand. The receipt import refuses a document whose id is here already.
ALTER TABLE actions ADD COLUMN number TEXT NOT NULL DEFAULT ('');
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=79 WHERE name='SchemaVersion';
COMMIT;
