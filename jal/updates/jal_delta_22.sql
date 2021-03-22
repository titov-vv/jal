BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 0;
--------------------------------------------------------------------------------
-- Add triggers for account validation
--------------------------------------------------------------------------------
DROP TABLE IF EXISTS asset_reg_id;
CREATE TABLE asset_reg_id (
    asset_id INTEGER      PRIMARY KEY
                          UNIQUE
                          NOT NULL
                          REFERENCES assets (id) ON DELETE CASCADE
                                                 ON UPDATE CASCADE,
    reg_code VARCHAR (20) NOT NULL
);
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 1;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=22 WHERE name='SchemaVersion';
COMMIT;
