BEGIN TRANSACTION;
--------------------------------------------------------------------------------
-- PORTFOLIOS: THE PORTFOLIO (A TAG) OF THE LOTS AN OPERATION OPENS
--------------------------------------------------------------------------------
CREATE TABLE operation_portfolios (
    operation_id INTEGER PRIMARY KEY NOT NULL REFERENCES operations (id) ON DELETE CASCADE,
    tag_id       INTEGER NOT NULL REFERENCES tags (id) ON DELETE CASCADE ON UPDATE CASCADE
);
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=90 WHERE name='SchemaVersion';
COMMIT;
VACUUM;
