BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 0;
--------------------------------------------------------------------------------
DROP TABLE IF EXISTS term_deposits;
CREATE TABLE term_deposits (
    id         INTEGER PRIMARY KEY UNIQUE NOT NULL,
    op_type    INTEGER NOT NULL DEFAULT (6),
    account_id INTEGER NOT NULL REFERENCES accounts (id) ON DELETE CASCADE ON UPDATE CASCADE,
    note       TEXT
);
DROP TABLE IF EXISTS deposit_actions;
CREATE TABLE deposit_actions (
    id          INTEGER PRIMARY KEY UNIQUE NOT NULL,
    deposit_id  INTEGER REFERENCES term_deposits (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    timestamp   INTEGER NOT NULL,
    action_type INTEGER NOT NULL,
    amount      TEXT    NOT NULL
);
DROP INDEX IF EXISTS deposit_actions_idx;
CREATE UNIQUE INDEX deposit_actions_idx ON deposit_actions (deposit_id, timestamp, type);
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 1;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=52 WHERE name='SchemaVersion';
COMMIT;
-- Reduce file size
VACUUM;