BEGIN TRANSACTION;
--------------------------------------------------------------------------------
-- THE DERIVED TABLES GO FIRST
--------------------------------------------------------------------------------
-- 538 operations change their table and their id space stays the same, so nothing built from them survives and the
-- ledger is rebuilt from scratch afterwards. Emptying them here is also what keeps the migration cheap: the
-- invalidation triggers fire on every row written below, and each firing is a range delete over the whole ledger
-- that has nothing left to do once these are empty.
DELETE FROM trades_closed;
DELETE FROM trades_opened;
DELETE FROM ledger_totals;
DELETE FROM ledger;
DELETE FROM ledger_sequence;
--------------------------------------------------------------------------------
-- THE ASSET ITSELF ARRIVING IS NOT A PAYMENT
--------------------------------------------------------------------------------
-- 'asset_payments' carried two operations at once: money paid on account of an asset, and the asset arriving. They
-- share a shape and nothing else - the first moves the Money book and the second opens a LOT - and the table was
-- correspondingly sparse, with 'price' set on 59 rows of 1 737 and a 'tax' that is non-zero on nothing but the
-- securities subtypes.
--
-- The three 'asset_payments' triggers are dropped first and re-stated at the end: the delete one removes the root
-- row of every payment it sees go, which would take the roots of the rows being MOVED here with it.
DROP TRIGGER IF EXISTS asset_payments_after_delete;
DROP TRIGGER IF EXISTS asset_payments_after_insert;
DROP TRIGGER IF EXISTS asset_payments_after_update;
--------------------------------------------------------------------------------
-- Table: asset_incomes
-- The asset itself arriving at no cost to the account that receives it - shares granted as a dividend or a vesting,
-- coins earned by staking, dust nobody asked for. 'amount' is a QUANTITY of 'symbol_id' and never a sum of money,
-- which is what separates this from 'asset_payments'; 'tax' is money all the same, where a broker withheld one.
CREATE TABLE asset_incomes (
    oid        INTEGER PRIMARY KEY UNIQUE NOT NULL,   -- Unique operation id
    otype      INTEGER NOT NULL DEFAULT (9),          -- Operation type (9 = asset income)
    timestamp  INTEGER NOT NULL,                      -- Timestamp when the asset arrived
    timestamp_day_only INTEGER NOT NULL DEFAULT (0),  -- 1 when the source stated the DAY and no time within it
    ex_date    INTEGER NOT NULL DEFAULT (0),          -- Timestamp (date) of ex-date for a stock dividend
    number     TEXT    NOT NULL DEFAULT (''),         -- Number of the operation in broker/exchange systems
    type       INTEGER NOT NULL,                      -- Sub-type of operation (see AssetIncome class)
    account_id INTEGER REFERENCES accounts (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,      -- where it arrived
    symbol_id  INTEGER REFERENCES asset_symbol (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,  -- what arrived
    amount     TEXT    NOT NULL DEFAULT ('0'),        -- How much of the asset was received
    tax        TEXT    NOT NULL DEFAULT ('0'),        -- Amount of tax that was witheld, in the account's currency
    price      TEXT    NOT NULL DEFAULT (''),         -- Per-unit value the grant was made at, as the source stated it. Empty means not stated - never a zero, which would be a real and wrong price
    note       TEXT                                   -- Free text comment
);
--------------------------------------------------------------------------------
-- The subtypes are renumbered from 1, because each of the two classes has a selector of its own now and the editor
-- maps it by index. The old numbers are spelled out here and nowhere else: 3 Stock dividend, 4 Stock vesting,
-- 8 Staking reward, 10 Reward, 9 Dust attack, 11 Rebase adjustment, 13 Token account rent returned.
INSERT INTO asset_incomes (oid, otype, timestamp, timestamp_day_only, ex_date, number, type, account_id, symbol_id,
                           amount, tax, price, note)
SELECT p.oid, 9, p.timestamp, p.timestamp_day_only, p.ex_date, p.number,
       CASE p.type WHEN 3 THEN 1 WHEN 4 THEN 2 WHEN 8 THEN 3 WHEN 10 THEN 4
                   WHEN 9 THEN 5 WHEN 11 THEN 6 WHEN 13 THEN 7 END,
       p.account_id, p.symbol_id, p.amount, p.tax, p.price, p.note
  FROM asset_payments AS p WHERE p.type IN (3, 4, 8, 9, 10, 11, 13);
--------------------------------------------------------------------------------
-- The moved ones keep their id and change their type, so every fee row, every ledger reference and every open lot
-- that names one still names the same operation. Their rows then leave the table they came from.
UPDATE operations SET otype = 9 WHERE id IN (SELECT oid FROM asset_incomes);
DELETE FROM asset_payments WHERE type IN (3, 4, 8, 9, 10, 11, 13);
--------------------------------------------------------------------------------
-- THE TRIGGERS, RE-STATED AND ADDED
--------------------------------------------------------------------------------
-- Ledger and trades cleanup after modification
CREATE TRIGGER asset_payments_after_delete AFTER DELETE ON asset_payments FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp;
    DELETE FROM operations WHERE id = OLD.oid;
END;
-- Ledger and trades cleanup after modification
CREATE TRIGGER asset_payments_after_insert AFTER INSERT ON asset_payments FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= NEW.timestamp;
    UPDATE operations SET timestamp = COALESCE(NEW.timestamp, 0) WHERE id = NEW.oid;
END;
-- Ledger and trades cleanup after modification
CREATE TRIGGER asset_payments_after_update AFTER UPDATE OF timestamp, type, account_id, symbol_id, amount, tax, price ON asset_payments FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
    UPDATE operations SET timestamp = COALESCE(NEW.timestamp, 0) WHERE id = NEW.oid;
END;
-- Ledger and trades cleanup after modification
CREATE TRIGGER asset_incomes_after_delete AFTER DELETE ON asset_incomes FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp;
    DELETE FROM operations WHERE id = OLD.oid;
END;
-- Ledger and trades cleanup after modification
CREATE TRIGGER asset_incomes_after_insert AFTER INSERT ON asset_incomes FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= NEW.timestamp;
    UPDATE operations SET timestamp = COALESCE(NEW.timestamp, 0) WHERE id = NEW.oid;
END;
-- Ledger and trades cleanup after modification
CREATE TRIGGER asset_incomes_after_update AFTER UPDATE OF timestamp, type, account_id, symbol_id, amount, tax, price ON asset_incomes FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
    UPDATE operations SET timestamp = COALESCE(NEW.timestamp, 0) WHERE id = NEW.oid;
END;
--------------------------------------------------------------------------------
INSERT OR REPLACE INTO settings(name, value) VALUES ('RebuildDB', 1);
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=77 WHERE name='SchemaVersion';
COMMIT;
