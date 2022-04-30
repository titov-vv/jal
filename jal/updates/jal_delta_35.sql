BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 0;
--------------------------------------------------------------------------------
-- Remove foreign key reference for 'type_id' column in 'accounts' table
CREATE TABLE temp_accounts_table AS SELECT * FROM accounts;
DROP TABLE accounts;
CREATE TABLE accounts (
    id              INTEGER   PRIMARY KEY UNIQUE NOT NULL,
    type_id         INTEGER   NOT NULL,
    name            TEXT (64) NOT NULL UNIQUE,
    currency_id     INTEGER   REFERENCES assets (id) ON DELETE RESTRICT ON UPDATE CASCADE NOT NULL,
    active          INTEGER   DEFAULT (1)  NOT NULL ON CONFLICT REPLACE,
    number          TEXT (32),
    reconciled_on   INTEGER   DEFAULT (0)  NOT NULL ON CONFLICT REPLACE,
    organization_id INTEGER   REFERENCES agents (id) ON DELETE SET NULL ON UPDATE CASCADE,
    country_id      INTEGER   REFERENCES countries (id) ON DELETE CASCADE ON UPDATE CASCADE DEFAULT (0) NOT NULL
);

INSERT INTO accounts (id, type_id, name, currency_id, active, number, reconciled_on, organization_id, country_id)
SELECT id, type_id, name, currency_id, active, number, reconciled_on, organization_id, country_id FROM temp_accounts_table;

DROP TABLE temp_accounts_table;
CREATE TRIGGER validate_account_insert BEFORE INSERT ON accounts
      FOR EACH ROW
      WHEN NEW.type_id = 4 AND NEW.organization_id IS NULL
BEGIN
    SELECT RAISE(ABORT, "JAL_SQL_MSG_0001");
END;

CREATE TRIGGER validate_account_update BEFORE UPDATE ON accounts
      FOR EACH ROW
      WHEN NEW.type_id = 4 AND NEW.organization_id IS NULL
BEGIN
    SELECT RAISE(ABORT, "JAL_SQL_MSG_0001");
END;

-- Remove reference table with account types
DROP TABLE IF EXISTS account_types;

-- Remove foreign key reference for 'type_id' column in 'assets' table
CREATE TABLE temp_assets_table AS SELECT * FROM assets;
DROP TABLE assets;
CREATE TABLE assets (
    id         INTEGER    PRIMARY KEY UNIQUE NOT NULL,
    type_id    INTEGER    NOT NULL,
    full_name  TEXT (128) NOT NULL,
    isin       TEXT (12)  DEFAULT ('') NOT NULL,
    country_id INTEGER    REFERENCES countries (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL DEFAULT (0),
    base_asset INTEGER    REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE
);

INSERT INTO assets (id, type_id, full_name, isin, country_id, base_asset)
SELECT id, type_id, full_name, isin, country_id, base_asset FROM temp_assets_table;

DROP TABLE temp_assets_table;
-- Remove reference table with asset types
DROP TABLE IF EXISTS asset_types;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 1;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=35 WHERE name='SchemaVersion';
COMMIT;
