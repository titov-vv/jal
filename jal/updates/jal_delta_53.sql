BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 0;
--------------------------------------------------------------------------------
ALTER TABLE dividends RENAME TO asset_payments;
--------------------------------------------------------------------------------
CREATE TABLE accounts_old AS SELECT * FROM accounts;
DROP TABLE accounts;
CREATE TABLE accounts (
    id              INTEGER   PRIMARY KEY UNIQUE NOT NULL,
    type_id         INTEGER,
    name            TEXT (64) NOT NULL UNIQUE,
    currency_id     INTEGER   REFERENCES assets (id) ON DELETE RESTRICT ON UPDATE CASCADE NOT NULL,
    active          INTEGER   DEFAULT (1) NOT NULL ON CONFLICT REPLACE,
    investing       INTEGER   NOT NULL DEFAULT (0),
    number          TEXT (32),
    reconciled_on   INTEGER   DEFAULT (0) NOT NULL ON CONFLICT REPLACE,
    organization_id INTEGER   REFERENCES agents (id) ON DELETE SET NULL ON UPDATE CASCADE,
    country_id      INTEGER   REFERENCES countries (id) ON DELETE CASCADE ON UPDATE CASCADE DEFAULT (0) NOT NULL,
    precision       INTEGER   NOT NULL DEFAULT (2)
);
INSERT INTO accounts (id, type_id, name, currency_id, active, number, reconciled_on, organization_id, country_id, precision)
  SELECT id, type_id, name, currency_id, active, number, reconciled_on, organization_id, country_id, precision FROM accounts_old;
DROP TABLE accounts_old;

UPDATE accounts SET investing=1 WHERE type_id=4;   -- Set flat for accounts that had investment type assigned

DROP TRIGGER IF EXISTS validate_account_insert;
CREATE TRIGGER validate_account_insert BEFORE INSERT ON accounts
    FOR EACH ROW
    WHEN NEW.investing = 1 AND NEW.organization_id IS NULL
BEGIN
    SELECT RAISE(ABORT, "JAL_SQL_MSG_0001");
END;

DROP TRIGGER IF EXISTS validate_account_update;
CREATE TRIGGER validate_account_update BEFORE UPDATE ON accounts
    FOR EACH ROW
    WHEN NEW.investing = 1 AND NEW.organization_id IS NULL
BEGIN
    SELECT RAISE(ABORT, "JAL_SQL_MSG_0001");
END;
--------------------------------------------------------------------------------
DROP VIEW IF EXISTS operation_sequence;
CREATE VIEW operation_sequence AS
SELECT m.op_type, m.id, m.timestamp, m.account_id, subtype
FROM
(
    SELECT op_type, 1 AS seq, id, timestamp, account_id, 0 AS subtype FROM actions
    UNION ALL
    SELECT op_type, 2 AS seq, id, timestamp, account_id, type AS subtype FROM asset_payments
    UNION ALL
    SELECT op_type, 3 AS seq, id, timestamp, account_id, type AS subtype FROM asset_actions
    UNION ALL
    SELECT op_type, 4 AS seq, id, timestamp, account_id, 0 AS subtype FROM trades
    UNION ALL
    SELECT op_type, 5 AS seq, id, withdrawal_timestamp AS timestamp, withdrawal_account AS account_id, -1 AS subtype FROM transfers
    UNION ALL
    SELECT op_type, 5 AS seq, id, withdrawal_timestamp AS timestamp, fee_account AS account_id, 0 AS subtype FROM transfers WHERE NOT fee IS NULL
    UNION ALL
    SELECT op_type, 5 AS seq, id, deposit_timestamp AS timestamp, deposit_account AS account_id, 1 AS subtype FROM transfers
    UNION ALL
    SELECT td.op_type, 6 AS seq, td.id, da.timestamp, td.account_id, da.id AS subtype FROM deposit_actions AS da LEFT JOIN term_deposits AS td ON da.deposit_id=td.id WHERE da.action_type<=100
) AS m
ORDER BY m.timestamp, m.seq, m.subtype, m.id;

DROP TRIGGER IF EXISTS dividends_after_delete;
CREATE TRIGGER asset_payments_after_delete
      AFTER DELETE ON asset_payments
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp;
END;

DROP TRIGGER IF EXISTS dividends_after_insert;
CREATE TRIGGER asset_payments_after_insert
      AFTER INSERT ON asset_payments
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= NEW.timestamp;
END;

DROP TRIGGER IF EXISTS dividends_after_update;
CREATE TRIGGER asset_payments_after_update
      AFTER UPDATE OF timestamp, type, account_id, asset_id, amount, tax ON asset_payments
      FOR EACH ROW
      WHEN (SELECT value FROM settings WHERE id = 1)
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
END;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 1;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=53 WHERE name='SchemaVersion';
INSERT OR REPLACE INTO settings(id, name, value) VALUES (7, 'RebuildDB', 1);
COMMIT;