PRAGMA foreign_keys = OFF;
BEGIN TRANSACTION;
--------------------------------------------------------------------------------
-- AN OPERATION GETS A PARENT
--------------------------------------------------------------------------------
-- '(otype, oid)' was the address of an operation everywhere in this schema - 'ledger', 'ledger_totals',
-- 'trades_opened', 'trades_closed', 'operation_sequence', every report - and a key in no table at all. Each of the
-- eight operation tables numbered its own rows from 1, so the ids collided across tables and no reference to an
-- operation could be a foreign key: nothing cascaded, and a child of ANY operation (as opposed to a child of one
-- particular type, like 'action_details') could have no integrity whatsoever.
--
-- 'operations' is that missing key: pure identity, allocated once, pointed at. It is a SOURCE table - permanent,
-- never deleted and rebuilt - which is what lets other source data reference it.
CREATE TABLE operations (
    id    INTEGER PRIMARY KEY NOT NULL,  -- The global operation id; each type table's 'oid' becomes this
    otype INTEGER NOT NULL               -- Which table holds the rest of the operation
);
CREATE INDEX operations_by_type ON operations (otype);
--------------------------------------------------------------------------------
-- THE RENUMBERING
--------------------------------------------------------------------------------
-- Every 'oid' in the database is rewritten into one continuous space, 1..N with no gaps. Continuous and not a fixed
-- offset per type: an offset constant is an assumption about how large this database is allowed to grow, and it
-- would have to clear each table's MAX oid rather than its row count anyway, carrying the old gaps forward.
--
-- Gapless ids cannot be computed by arithmetic on the old id, so this needs a map. The obstacle is that
-- 'UPDATE ... SET oid = <new>' is checked row by row, so a new id another row still holds fails mid-statement even
-- when the final state would be unique. The whole NEGATIVE id space is unoccupied: one pass down into it, one pass
-- back up. No companion script, no mapping table left behind.
--
-- The order MUST preserve each type's internal 'oid' order, and 'ORDER BY otype, old_id' does. The ledger is
-- processed in 'timestamp, seq, opart, oid' order, and each 'seq' value maps to exactly one table - so the 'oid'
-- tie-break only ever compares two rows of the SAME table. Preserving the order within a type is therefore enough
-- to guarantee that FIFO lot consumption cannot move. Numbering globally by 'timestamp' would give chronological
-- ids and is WRONG: it reshuffles ids within a type and would silently change which lots a sale consumes.
--
-- A trap in reading what follows: inside a subquery over another table a bare 'oid' binds to THAT table's rowid
-- alias ('oid', 'rowid' and '_rowid_' alias the rowid of any rowid table), not to the outer column. Every column
-- reference below is table-qualified for that reason.
--
-- Why a map and not arithmetic, beyond the missing constant: it fails LOUD. A row the map misses yields NULL, and
-- NULL into an INTEGER PRIMARY KEY is a datatype mismatch on UPDATE (it is auto-assigned only on INSERT), so this
-- script stops instead of writing a silent zero.
CREATE TEMPORARY TABLE opmap AS
SELECT otype, old_id, row_number() OVER (ORDER BY otype, old_id) AS new_id FROM (
             SELECT 1 AS otype, oid AS old_id FROM actions
   UNION ALL SELECT 2, oid FROM asset_payments
   UNION ALL SELECT 3, oid FROM trades
   UNION ALL SELECT 4, oid FROM transfers
   UNION ALL SELECT 5, oid FROM asset_actions
   UNION ALL SELECT 6, oid FROM conversions
   UNION ALL SELECT 7, oid FROM swaps
   UNION ALL SELECT 8, oid FROM bridges);
CREATE UNIQUE INDEX temp.opmap_idx ON opmap (otype, old_id);

-- Pass 1: into the negative half, which no id ever occupies, so no collision is possible.
-- The two child tables are moved BY HAND: 'action_details.pid' and 'asset_action_results.action_id' declare
-- ON UPDATE CASCADE, but this script runs with foreign keys OFF (as every delta that rewrites keys does), so the
-- cascade never fires. Forget them and 39 069 detail rows point at nothing.
UPDATE actions              SET oid       = -(SELECT m.new_id FROM opmap m WHERE m.otype=1 AND m.old_id=actions.oid);
UPDATE action_details       SET pid       = -(SELECT m.new_id FROM opmap m WHERE m.otype=1 AND m.old_id=action_details.pid);
UPDATE asset_payments       SET oid       = -(SELECT m.new_id FROM opmap m WHERE m.otype=2 AND m.old_id=asset_payments.oid);
UPDATE trades               SET oid       = -(SELECT m.new_id FROM opmap m WHERE m.otype=3 AND m.old_id=trades.oid);
UPDATE transfers            SET oid       = -(SELECT m.new_id FROM opmap m WHERE m.otype=4 AND m.old_id=transfers.oid);
UPDATE asset_actions        SET oid       = -(SELECT m.new_id FROM opmap m WHERE m.otype=5 AND m.old_id=asset_actions.oid);
UPDATE asset_action_results SET action_id = -(SELECT m.new_id FROM opmap m WHERE m.otype=5 AND m.old_id=asset_action_results.action_id);
UPDATE conversions          SET oid       = -(SELECT m.new_id FROM opmap m WHERE m.otype=6 AND m.old_id=conversions.oid);
UPDATE swaps                SET oid       = -(SELECT m.new_id FROM opmap m WHERE m.otype=7 AND m.old_id=swaps.oid);
UPDATE bridges              SET oid       = -(SELECT m.new_id FROM opmap m WHERE m.otype=8 AND m.old_id=bridges.oid);
-- One stored oid lives outside the operation tables: 'LiFiAuditedSwap' is the highest swap already audited against
-- the route it came from (jal/net/chain_fetchers/fetchers.py). Left alone it would point into the old numbering;
-- reset to 0 it would re-audit every swap over the network.
UPDATE settings SET value = CAST(-(SELECT m.new_id FROM opmap m WHERE m.otype=7 AND m.old_id=CAST(settings.value AS INTEGER)) AS TEXT)
    WHERE settings.name = 'LiFiAuditedSwap' AND CAST(settings.value AS INTEGER) > 0;

-- Pass 2: back up; the positive half is empty at this point
UPDATE actions              SET oid       = -oid;
UPDATE action_details       SET pid       = -pid;
UPDATE asset_payments       SET oid       = -oid;
UPDATE trades               SET oid       = -oid;
UPDATE transfers            SET oid       = -oid;
UPDATE asset_actions        SET oid       = -oid;
UPDATE asset_action_results SET action_id = -action_id;
UPDATE conversions          SET oid       = -oid;
UPDATE swaps                SET oid       = -oid;
UPDATE bridges              SET oid       = -oid;
UPDATE settings SET value = CAST(-CAST(settings.value AS INTEGER) AS TEXT)
    WHERE settings.name = 'LiFiAuditedSwap' AND CAST(settings.value AS INTEGER) < 0;

-- The map is the same query that populates the root, so the two cannot disagree
INSERT INTO operations (id, otype) SELECT new_id, otype FROM opmap;
DROP TABLE opmap;
--------------------------------------------------------------------------------
-- THE ROOT FOLLOWS ITS TYPE ROW
--------------------------------------------------------------------------------
-- Each trigger below is the one that already existed, with a single statement added.
DROP TRIGGER IF EXISTS actions_after_delete;
CREATE TRIGGER actions_after_delete AFTER DELETE ON actions FOR EACH ROW
BEGIN
    DELETE FROM action_details WHERE pid = OLD.oid;
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp;
    DELETE FROM operations WHERE id = OLD.oid;
END;
DROP TRIGGER IF EXISTS asset_payments_after_delete;
CREATE TRIGGER asset_payments_after_delete AFTER DELETE ON asset_payments FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp;
    DELETE FROM operations WHERE id = OLD.oid;
END;
DROP TRIGGER IF EXISTS trades_after_delete;
CREATE TRIGGER trades_after_delete AFTER DELETE ON trades FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp;
    DELETE FROM operations WHERE id = OLD.oid;
END;
DROP TRIGGER IF EXISTS transfers_after_delete;
CREATE TRIGGER transfers_after_delete AFTER DELETE ON transfers FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.withdrawal_timestamp OR timestamp >= OLD.deposit_timestamp;
    DELETE FROM operations WHERE id = OLD.oid;
END;
DROP TRIGGER IF EXISTS asset_action_after_delete;
CREATE TRIGGER asset_action_after_delete AFTER DELETE ON asset_actions FOR EACH ROW
BEGIN
    DELETE FROM asset_action_results WHERE action_id = OLD.oid;
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp;
    DELETE FROM operations WHERE id = OLD.oid;
END;
DROP TRIGGER IF EXISTS conversions_after_delete;
CREATE TRIGGER conversions_after_delete AFTER DELETE ON conversions FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp;
    DELETE FROM operations WHERE id = OLD.oid;
END;
DROP TRIGGER IF EXISTS swaps_after_delete;
CREATE TRIGGER swaps_after_delete AFTER DELETE ON swaps FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.timestamp;
    DELETE FROM operations WHERE id = OLD.oid;
END;
DROP TRIGGER IF EXISTS bridges_after_delete;
CREATE TRIGGER bridges_after_delete AFTER DELETE ON bridges FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= OLD.out_timestamp OR timestamp >= OLD.in_timestamp;
    DELETE FROM trades_opened WHERE timestamp >= OLD.out_timestamp OR timestamp >= OLD.in_timestamp;
    DELETE FROM operations WHERE id = OLD.oid;
END;
--------------------------------------------------------------------------------
DROP VIEW IF EXISTS operation_sequence;
CREATE VIEW operation_sequence AS SELECT m.otype, m.oid, m.seq, opart, m.timestamp, m.account_id
FROM
(
    SELECT otype, 1 AS seq, oid, 0 AS opart, timestamp, account_id FROM actions
    UNION ALL
    SELECT otype, 2 AS seq, oid, 0 AS opart, timestamp, account_id FROM asset_payments
    UNION ALL
    SELECT otype, 3 AS seq, oid, 0 AS opart, timestamp, account_id FROM asset_actions
    UNION ALL
    SELECT otype, 4 AS seq, oid, 0 AS opart, timestamp, account_id FROM trades
    UNION ALL
    SELECT otype, 5 AS seq, oid, -1 AS opart, withdrawal_timestamp AS timestamp, withdrawal_account AS account_id FROM transfers WHERE NOT withdrawal_account IS NULL
    UNION ALL
    SELECT otype, 5 AS seq, oid, 0 AS opart, withdrawal_timestamp AS timestamp, fee_account AS account_id FROM transfers WHERE NOT fee IS NULL
    UNION ALL
    SELECT otype, 5 AS seq, oid, 1 AS opart, deposit_timestamp AS timestamp, deposit_account AS account_id FROM transfers WHERE NOT deposit_account IS NULL
    UNION ALL
    SELECT otype, 6 AS seq, oid, 0 AS opart, timestamp, account_id FROM conversions
    UNION ALL
    SELECT otype, 6 AS seq, oid, 2 AS opart, timestamp, account_id FROM conversions WHERE NOT fee_qty IS NULL
    UNION ALL
    SELECT otype, 7 AS seq, oid, 0 AS opart, timestamp, account_id FROM swaps WHERE in_account_id IS NULL OR in_account_id=account_id
    UNION ALL
    SELECT otype, 7 AS seq, oid, -1 AS opart, timestamp, account_id FROM swaps WHERE NOT in_account_id IS NULL AND in_account_id<>account_id
    UNION ALL
    SELECT otype, 7 AS seq, oid, 1 AS opart, COALESCE(in_timestamp, timestamp) AS timestamp, in_account_id AS account_id FROM swaps WHERE NOT in_account_id IS NULL AND in_account_id<>account_id
    UNION ALL
    -- Gas is burned on the source chain, so the fee part of a cross-chain swap rides its sending leg
    SELECT otype, 7 AS seq, oid, 2 AS opart, timestamp, account_id FROM swaps WHERE NOT fee_qty IS NULL
    UNION ALL
    SELECT otype, 8 AS seq, oid, -1 AS opart, out_timestamp AS timestamp, out_account_id AS account_id FROM bridges
    UNION ALL
    SELECT otype, 8 AS seq, oid, 0 AS opart, out_timestamp AS timestamp, out_account_id AS account_id FROM bridges WHERE NOT fee_qty IS NULL
    UNION ALL
    SELECT otype, 8 AS seq, oid, 1 AS opart, in_timestamp AS timestamp, in_account_id AS account_id FROM bridges WHERE NOT in_account_id IS NULL
) AS m
ORDER BY m.timestamp, m.seq, m.opart, m.oid;  -- First sort by sequence and part to enforce right operation processing order
--------------------------------------------------------------------------------
-- THE DERIVED TABLES MUST BE WIPED BY HAND
--------------------------------------------------------------------------------
DELETE FROM trades_closed;
DELETE FROM trades_opened;
DELETE FROM ledger_totals;
DELETE FROM ledger;
INSERT OR REPLACE INTO settings(name, value) VALUES ('RebuildDB', 1);
--------------------------------------------------------------------------------
UPDATE settings SET value=71 WHERE name='SchemaVersion';
COMMIT;
PRAGMA foreign_keys = ON;
