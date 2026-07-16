BEGIN TRANSACTION;
--------------------------------------------------------------------------------
-- New table for a flexible set of per-account attributes.
-- Becomes the home for number/credit/country/precision etc.
CREATE TABLE account_data (
    id         INTEGER PRIMARY KEY UNIQUE NOT NULL,
    account_id INTEGER NOT NULL REFERENCES accounts (id) ON DELETE CASCADE ON UPDATE CASCADE,
    datatype   INTEGER NOT NULL,
    value      TEXT    NOT NULL
);
CREATE UNIQUE INDEX account_data_uniqueness ON account_data (account_id, datatype);
--------------------------------------------------------------------------------
-- Rework 'tag_id' (which was used as an account type) into an 'account_type'
-- enum column (values match PredefinedAccountType). Custom account tags fall back to Cash (2).
ALTER TABLE accounts ADD COLUMN account_type INTEGER NOT NULL DEFAULT (2);
UPDATE accounts SET account_type = CASE WHEN tag_id IN (2, 3, 4, 5) THEN tag_id ELSE 2 END;
--------------------------------------------------------------------------------
-- Move number / credit / country_id / precision into 'account_data'.
INSERT INTO account_data (account_id, datatype, value)
    SELECT id, 1, number                 FROM accounts WHERE number IS NOT NULL;   -- AccountData.Number
INSERT INTO account_data (account_id, datatype, value)
    SELECT id, 2, credit                 FROM accounts WHERE credit <> '0';        -- AccountData.Credit
INSERT INTO account_data (account_id, datatype, value)
    SELECT id, 3, CAST(country_id AS TEXT) FROM accounts WHERE country_id <> 0;    -- AccountData.Country
INSERT INTO account_data (account_id, datatype, value)
    SELECT id, 4, CAST(precision AS TEXT)  FROM accounts WHERE precision <> 2;     -- AccountData.Precision
--------------------------------------------------------------------------------
ALTER TABLE accounts DROP COLUMN tag_id;
ALTER TABLE accounts DROP COLUMN number;
ALTER TABLE accounts DROP COLUMN country_id;
ALTER TABLE accounts DROP COLUMN precision;
ALTER TABLE accounts DROP COLUMN credit;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=61 WHERE name='SchemaVersion';
COMMIT;
