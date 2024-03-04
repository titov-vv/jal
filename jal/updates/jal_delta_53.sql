BEGIN TRANSACTION;
--------------------------------------------------------------------------------
ALTER TABLE tags ADD COLUMN icon_file TEXT DEFAULT ('');
UPDATE tags SET icon_file='';
-- Free space for 4 predefined tags
UPDATE tags SET pid = (SELECT MAX(id)+1 FROM tags) WHERE pid = 1;
UPDATE tags SET id = (SELECT MAX(id)+1 FROM tags) WHERE id = 1;
UPDATE tags SET pid = (SELECT MAX(id)+1 FROM tags) WHERE pid = 2;
UPDATE tags SET id = (SELECT MAX(id)+1 FROM tags) WHERE id = 2;
UPDATE tags SET pid = (SELECT MAX(id)+1 FROM tags) WHERE pid = 3;
UPDATE tags SET id = (SELECT MAX(id)+1 FROM tags) WHERE id = 3;
UPDATE tags SET pid = (SELECT MAX(id)+1 FROM tags) WHERE pid = 4;
UPDATE tags SET id = (SELECT MAX(id)+1 FROM tags) WHERE id = 4;
UPDATE tags SET pid = (SELECT MAX(id)+1 FROM tags) WHERE pid = 5;
UPDATE tags SET id = (SELECT MAX(id)+1 FROM tags) WHERE id = 5;
-- Create predefined tags for account types
INSERT INTO tags (id, pid, tag) VALUES (1, 0, 'Account type');
INSERT INTO tags (id, pid, tag, icon_file) VALUES (2, 1, 'Cash', 'tag_cash.ico');
INSERT INTO tags (id, pid, tag, icon_file) VALUES (3, 1, 'Bank account', 'tag_bank.ico');
INSERT INTO tags (id, pid, tag, icon_file) VALUES (4, 1, 'Card', 'tag_card.ico');
INSERT INTO tags (id, pid, tag, icon_file) VALUES (5, 1, 'Broker account', 'tag_investing.ico');
--------------------------------------------------------------------------------
-- Free space for new predefined agent
UPDATE agents SET pid = (SELECT MAX(id)+1 FROM agents) WHERE pid = 1;
UPDATE agents SET id = (SELECT MAX(id)+1 FROM agents) WHERE id = 1;
-- Create predefined empty peer agent
INSERT INTO agents (id, pid, name) VALUES (1, 0, 'None');
--------------------------------------------------------------------------------
-- Drop/disable triggers before modifications
DROP TRIGGER IF EXISTS validate_account_insert;
DROP TRIGGER IF EXISTS validate_account_update;
-- Replace old account type_id with new tag value
UPDATE accounts SET type_id=2 WHERE type_id IN (5, 6, 7);
UPDATE accounts SET type_id=5 WHERE type_id = 4;
UPDATE accounts SET type_id=4 WHERE type_id = 3;
UPDATE accounts SET type_id=3 WHERE type_id = 2;
UPDATE accounts SET type_id=2 WHERE type_id = 1;
-- Set predefined peer of it is empty
UPDATE accounts SET organization_id=1 WHERE organization_id IS NULL;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 0;
--------------------------------------------------------------------------------
ALTER TABLE dividends RENAME TO asset_payments;
--------------------------------------------------------------------------------
-- Modify categories table way how to preserve mandatory categories
DROP TRIGGER IF EXISTS keep_predefined_categories;
ALTER TABLE categories DROP COLUMN special;
CREATE TRIGGER keep_predefined_categories BEFORE DELETE ON categories FOR EACH ROW WHEN OLD.id <= 9
BEGIN
    SELECT RAISE(ABORT, "JAL_SQL_MSG_0002");
END;
--------------------------------------------------------------------------------
CREATE TABLE accounts_old AS SELECT * FROM accounts;
DROP TABLE accounts;
CREATE TABLE accounts (
    id              INTEGER   PRIMARY KEY UNIQUE NOT NULL,
    name            TEXT (64) NOT NULL UNIQUE,
    currency_id     INTEGER   REFERENCES assets (id) ON DELETE RESTRICT ON UPDATE CASCADE NOT NULL,
    active          INTEGER   DEFAULT (1) NOT NULL ON CONFLICT REPLACE,
    investing       INTEGER   NOT NULL DEFAULT (0),
    tag_id          INTEGER   REFERENCES tags (id) ON DELETE SET NULL ON UPDATE CASCADE,
    number          TEXT (32),
    reconciled_on   INTEGER   DEFAULT (0) NOT NULL ON CONFLICT REPLACE,
    organization_id INTEGER   REFERENCES agents (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL DEFAULT (1),
    country_id      INTEGER   REFERENCES countries (id) ON DELETE CASCADE ON UPDATE CASCADE DEFAULT (0) NOT NULL,
    precision       INTEGER   NOT NULL DEFAULT (2)
);
INSERT INTO accounts (id, name, currency_id, active, tag_id, number, reconciled_on, organization_id, country_id, precision)
  SELECT id, name, currency_id, active, type_id, number, reconciled_on, organization_id, country_id, precision FROM accounts_old;
DROP TABLE accounts_old;

UPDATE accounts SET investing=1 WHERE tag_id = 5;   -- Set flag for accounts that had investment type assigned

DROP TRIGGER IF EXISTS keep_predefined_agents;
CREATE TRIGGER keep_predefined_agents BEFORE DELETE ON agents FOR EACH ROW WHEN OLD.id <= 1
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
-- Fix of any occasional lost asset that was missed by old code
INSERT INTO asset_tickers (asset_id, symbol, currency_id, description, quote_source, active)
SELECT a.id, '***symbol_'||CAST(a.id AS TEXT), 1, 'autogenerated symbol', -1, 1 FROM assets a LEFT JOIN asset_tickers t ON a.id=t.asset_id WHERE t.symbol IS NULL;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 1;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=53 WHERE name='SchemaVersion';
INSERT OR REPLACE INTO settings(id, name, value) VALUES (7, 'RebuildDB', 1);
COMMIT;
VACUUM;