BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 0;
--------------------------------------------------------------------------------
DROP TABLE IF EXISTS term_deposits;
CREATE TABLE term_deposits (
    id         INTEGER PRIMARY KEY UNIQUE NOT NULL,
    op_type    INTEGER NOT NULL DEFAULT (6),
    timestamp  INTEGER NOT NULL,
    account_id INTEGER NOT NULL REFERENCES accounts (id) ON DELETE CASCADE ON UPDATE CASCADE,
    note       TEXT
);
DROP TABLE IF EXISTS deposit_actions;
CREATE TABLE deposit_actions (
    id         INTEGER PRIMARY KEY UNIQUE NOT NULL,
    deposit_id INTEGER REFERENCES term_deposits (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    timestamp  INTEGER NOT NULL,
    type       INTEGER NOT NULL,
    amount     TEXT    NOT NULL
);
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 1;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=52 WHERE name='SchemaVersion';
COMMIT;
-- Reduce file size
VACUUM;