PRAGMA foreign_keys = OFF;
BEGIN TRANSACTION;
--------------------------------------------------------------------------------
-- 'active' BECOMES THE ORDINAL 'status' (see AccountStatus): 20 = active, 10 = background, 0 = closed
--------------------------------------------------------------------------------
-- The table is rebuilt rather than the column renamed, because the DEFAULT has to change with it: a renamed
-- column keeps DEFAULT (1).
CREATE TABLE temp_accounts AS SELECT * FROM accounts;
DROP TABLE IF EXISTS accounts;
CREATE TABLE accounts (
    id              INTEGER   PRIMARY KEY UNIQUE NOT NULL,
    name            TEXT (64) NOT NULL UNIQUE,                                                                       -- human-readable name of the account
    currency_id     INTEGER   REFERENCES assets (id) ON DELETE RESTRICT ON UPDATE CASCADE NOT NULL,                  -- accounting currency for the account
    status          INTEGER   DEFAULT (20) NOT NULL ON CONFLICT REPLACE,                                             -- how much attention the account is due (see AccountStatus): 20 = active, 10 = background, 0 = closed
    investing       INTEGER   DEFAULT (0) NOT NULL,                                                                  -- 1 if account can hold investment assets, 0 otherwise
    reconciled_on   INTEGER   DEFAULT (0) NOT NULL ON CONFLICT REPLACE,                                              -- timestamp of last confirmed operation
    organization_id INTEGER   REFERENCES agents (id) ON DELETE SET DEFAULT ON UPDATE CASCADE NOT NULL DEFAULT (1),   -- Bank/Broker that handles account
    account_type    INTEGER   DEFAULT (2) NOT NULL                                                                   -- account type (see PredefinedAccountType); replaces the former 'tag_id'
);
INSERT INTO accounts (id, name, currency_id, status, investing, reconciled_on, organization_id, account_type)
  SELECT id, name, currency_id, CASE WHEN active = 1 THEN 20 ELSE 0 END,
         investing, reconciled_on, organization_id, account_type
  FROM temp_accounts;
DROP TABLE temp_accounts;
-- The trigger was defined ON the table that was just dropped, so it went with it
DROP TRIGGER IF EXISTS accounts_after_delete_icon;
CREATE TRIGGER accounts_after_delete_icon AFTER DELETE ON accounts FOR EACH ROW
BEGIN
    DELETE FROM icons WHERE entity=1 AND item_id=OLD.id;
END;
--------------------------------------------------------------------------------
INSERT OR REPLACE INTO settings(name, value)
  SELECT 'BalancesMinAccountStatus', CASE WHEN CAST(value AS INTEGER) = 1 THEN 0 ELSE 10 END
  FROM settings WHERE name='ShowInactiveAccountBalances';
INSERT OR REPLACE INTO settings(name, value) SELECT 'BalancesMinAccountStatus', 10
  WHERE NOT EXISTS (SELECT 1 FROM settings WHERE name='BalancesMinAccountStatus');
DELETE FROM settings WHERE name='ShowInactiveAccountBalances';
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=68 WHERE name='SchemaVersion';
COMMIT;
PRAGMA foreign_keys = ON;
