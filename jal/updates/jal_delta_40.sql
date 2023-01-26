BEGIN TRANSACTION;
--------------------------------------------------------------------------------
DELETE FROM settings WHERE id=2 AND name='BaseCurrency';

DROP TABLE IF EXISTS base_currency;
CREATE TABLE base_currency (
    id              INTEGER PRIMARY KEY UNIQUE NOT NULL,
    since_timestamp INTEGER NOT NULL UNIQUE,
    currency_id     INTEGER NOT NULL REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE
);
--------------------------------------------------------------------------------
-- Update data source name
UPDATE data_sources SET name='Central banks' WHERE id=0;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=40 WHERE name='SchemaVersion';
COMMIT;
