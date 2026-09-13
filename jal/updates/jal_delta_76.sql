BEGIN TRANSACTION;
--------------------------------------------------------------------------------
-- THE DERIVED TABLES GO FIRST
--------------------------------------------------------------------------------
-- Every id below is moved or deleted, so nothing built from them survives this script and the ledger is rebuilt
-- from scratch afterwards. Emptying them here is also what keeps the migration cheap: the invalidation triggers on
-- 'fees' and on the two operation tables fire on every row written below, and each firing is a range delete over
-- 107 000 ledger rows that has nothing left to do once these are empty.
DELETE FROM trades_closed;
DELETE FROM trades_opened;
DELETE FROM ledger_totals;
DELETE FROM ledger;
DELETE FROM ledger_sequence;
--------------------------------------------------------------------------------
-- AN EVENT IS AN OPERATION, THE GAS IS WHAT IT COST
--------------------------------------------------------------------------------
-- All gas is spent by an event, so the operation is the event and the gas is a fee of it. 161 gas payments have it
-- the other way round: the amount is the coin burned, and what actually happened survives only as a translated
-- sentence in the note, which nothing can count or query.
--
-- 51 of them have a sibling operation in the very same transaction - the claim they paid for, or the send - and
-- become a fee row of it. The other 110, plus the one token-account rent, become an operation of their own.
--
-- The three 'asset_payments' triggers are dropped first and re-stated at the end: the delete one removes the root
-- row of every payment it sees go, which would take the roots of the 111 rows being MOVED here with it.
DROP TRIGGER IF EXISTS asset_payments_after_delete;
DROP TRIGGER IF EXISTS asset_payments_after_insert;
DROP TRIGGER IF EXISTS asset_payments_after_update;
--------------------------------------------------------------------------------
-- Table: chain_actions
-- An on-chain event that moved no value: an approval, a reverted transaction, a command to a position, a call that
-- asked for nothing, and the rent locked by a token account. What it cost is a row of 'fees'; this table holds only
-- what happened. See the ChainAction class for why the gas is not the operation.
CREATE TABLE chain_actions (
    oid        INTEGER PRIMARY KEY UNIQUE NOT NULL,   -- Unique operation id
    otype      INTEGER NOT NULL DEFAULT (10),         -- Operation type (10 = chain action)
    timestamp  INTEGER NOT NULL,                      -- Timestamp of the transaction the event happened in
    timestamp_day_only INTEGER NOT NULL DEFAULT (0),  -- 1 when the source stated the DAY and no time within it
    number     TEXT    NOT NULL DEFAULT (''),         -- Hash of that transaction
    type       INTEGER NOT NULL,                      -- What happened (see ChainAction class)
    account_id INTEGER REFERENCES accounts (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,   -- where it happened
    symbol_id  INTEGER REFERENCES asset_symbol (id) ON DELETE CASCADE ON UPDATE CASCADE,        -- what it was ABOUT
                                                     -- (the token approved), NOT the coin spent. NULL when JAL
                                                     -- doesn't know that asset - the address then stays in the note
                                                     -- and no asset record is created for it
    note       TEXT                                   -- Free text comment
);
--------------------------------------------------------------------------------
-- WHO EACH GAS PAYMENT BELONGS TO
--------------------------------------------------------------------------------
-- The link already exists in the data and is simply not drawn: the transaction hash. A gas payment that shares one
-- with another operation is the cost of that operation; one that shares it with nothing stood alone all along.
--
-- An empty hash is not a link. It would match every other hash-less row, which is how a migration keyed on text
-- silently attaches a hand-entered gas payment to an unrelated one.
--
-- A claim that paid out in SEVERAL assets has one gas row and several payments to own it. It goes to the FIRST
-- asset by id, which is the same choice the importer makes ('sorted(ins.items())' in evm.py), so a re-import
-- reproduces it instead of adding a second copy.
CREATE TEMPORARY TABLE gas_owner AS
SELECT g.oid AS gas_oid, g.account_id, g.symbol_id, g.amount,
       COALESCE((SELECT p.oid FROM asset_payments AS p
                   JOIN asset_symbol AS s ON s.id = p.symbol_id
                  WHERE p.number = g.number AND p.oid <> g.oid AND p.type <> 7
                  ORDER BY s.asset_id, p.symbol_id, p.oid LIMIT 1),
                (SELECT t.oid FROM transfers AS t WHERE t.number = g.number ORDER BY t.oid LIMIT 1)) AS owner_oid
  FROM asset_payments AS g WHERE g.type = 7 AND g.number <> '';
--------------------------------------------------------------------------------
-- The 51 that ride the operation they paid for. 'account_id' comes from the gas row and not from its new parent:
-- one claim in the ledger was submitted by a different wallet from the one that received the reward, and one send's
-- gas sits on an account that is neither of its legs - which is exactly what a fee row's own account is for.
INSERT INTO fees (operation_id, idx, account_id, symbol_id, amount, kind)
SELECT o.owner_oid,
       COALESCE((SELECT MAX(f.idx) + 1 FROM fees AS f WHERE f.operation_id = o.owner_oid), 0),
       o.account_id, o.symbol_id, o.amount, 1        -- FeeKind.Gas
  FROM gas_owner AS o WHERE NOT o.owner_oid IS NULL;
--------------------------------------------------------------------------------
-- ... and the 111 that are events of their own. 'symbol_id' is NULL for every one of them: the column now means the
-- SUBJECT of the event and the coin it holds today is the gas, which goes to the cost row below. What was approved
-- was never recorded, so there is nothing to put there.
--
-- The event is read back from the note, which is the only place it was ever written - and the note is TRANSLATED,
-- so both languages the application ships are matched. Anything finer than the importer can tell apart today is
-- deliberately not guessed here: 'type' is not part of an action's identity, so teaching the importer to recognise
-- the rest later re-classifies these rows instead of duplicating them.
INSERT INTO chain_actions (oid, otype, timestamp, timestamp_day_only, number, type, account_id, symbol_id, note)
SELECT g.oid, 10, g.timestamp, g.timestamp_day_only, g.number,
       CASE WHEN g.type = 12 THEN 6                                                       -- TokenAccountRent
            WHEN g.note LIKE 'Gas: token approval%' THEN 1                                -- Authorization
            WHEN g.note LIKE 'Газ: одобрение токена%' THEN 1
            WHEN g.note LIKE 'Gas: failed transaction%' THEN 2                            -- FailedTransaction
            WHEN g.note LIKE 'Газ: неудавшаяся транзакция%' THEN 2
            ELSE 5 END,                                                                   -- ContractCall
       g.account_id, NULL, g.note
  FROM asset_payments AS g
 WHERE g.type = 12
    OR (g.type = 7 AND g.oid NOT IN (SELECT gas_oid FROM gas_owner WHERE NOT owner_oid IS NULL));
--------------------------------------------------------------------------------
-- What each of them cost. Gas is consumed; a rent is locked and comes back if the token account is ever closed, and
-- that is the whole difference between the two - the ledger posts them identically.
INSERT INTO fees (operation_id, idx, account_id, symbol_id, amount, kind)
SELECT g.oid, 0, g.account_id, g.symbol_id, g.amount,
       CASE WHEN g.type = 12 THEN 2 ELSE 1 END       -- FeeKind.Rent / FeeKind.Gas
  FROM asset_payments AS g
 WHERE g.oid IN (SELECT oid FROM chain_actions);
--------------------------------------------------------------------------------
-- The moved ones keep their id and change their type; the 51 stop being operations at all.
UPDATE operations SET otype = 10 WHERE id IN (SELECT oid FROM chain_actions);
DELETE FROM operations WHERE id IN (SELECT gas_oid FROM gas_owner WHERE NOT owner_oid IS NULL);
DELETE FROM asset_payments WHERE type IN (7, 12);
DROP TABLE gas_owner;
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
CREATE TRIGGER chain_actions_after_delete AFTER DELETE ON chain_actions FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp;
    DELETE FROM operations WHERE id = OLD.oid;
END;
-- Ledger and trades cleanup after modification
CREATE TRIGGER chain_actions_after_insert AFTER INSERT ON chain_actions FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= NEW.timestamp;
    UPDATE operations SET timestamp = COALESCE(NEW.timestamp, 0) WHERE id = NEW.oid;
END;
-- Ledger and trades cleanup after modification
CREATE TRIGGER chain_actions_after_update AFTER UPDATE OF timestamp, type, account_id, symbol_id ON chain_actions FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp OR timestamp >= NEW.timestamp;
    UPDATE operations SET timestamp = COALESCE(NEW.timestamp, 0) WHERE id = NEW.oid;
END;
--------------------------------------------------------------------------------
INSERT OR REPLACE INTO settings(name, value) VALUES ('RebuildDB', 1);
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=76 WHERE name='SchemaVersion';
COMMIT;
