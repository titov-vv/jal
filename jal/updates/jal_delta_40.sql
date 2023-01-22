BEGIN TRANSACTION;
--------------------------------------------------------------------------------
DELETE FROM settings WHERE id=2 AND name='BaseCurrency';

DROP TABLE IF EXISTS base_currency;
CREATE TABLE base_currency (
    since_timestamp INTEGER PRIMARY KEY NOT NULL UNIQUE,
    currency_id     INTEGER NOT NULL REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE
);
--------------------------------------------------------------------------------
-- Ensure compatibility with previous behavior
INSERT INTO base_currency(since_timestamp, currency_id) VALUES (946684800, 1);
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=40 WHERE name='SchemaVersion';
COMMIT;
