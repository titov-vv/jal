BEGIN TRANSACTION;
--------------------------------------------------------------------------------
-- A LOT CARRIED THROUGH A CORPORATE ACTION KNOWS ITS ACQUISITION DATE
--------------------------------------------------------------------------------
-- Per result: 1 keeps the original purchase date, 0 takes the action's date (TAX_PATH §2.12). Backfilled by the rule:
-- a split, a symbol change and a result on the action's own asset keep it; a spun-off company or a merger result don't
ALTER TABLE asset_action_results ADD COLUMN keep_date INTEGER NOT NULL DEFAULT (0);
UPDATE asset_action_results SET keep_date=1 WHERE EXISTS (
    SELECT 1 FROM asset_actions AS a
    JOIN asset_symbol AS withdrawn ON withdrawn.id=a.symbol_id
    JOIN asset_symbol AS received ON received.id=asset_action_results.symbol_id
    WHERE a.oid=asset_action_results.action_id AND (a.type IN (3, 4) OR received.asset_id=withdrawn.asset_id));
-- The acquisition date a lot carries, rebuilt with the ledger
ALTER TABLE trades_opened ADD COLUMN acquired INTEGER NOT NULL DEFAULT (0);
--------------------------------------------------------------------------------
INSERT OR REPLACE INTO settings(name, value) VALUES ('RebuildDB', 1);
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=81 WHERE name='SchemaVersion';
COMMIT;
