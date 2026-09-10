BEGIN TRANSACTION;
--------------------------------------------------------------------------------
-- THE PROCESSING ORDER BECOMES STORED DATA
--------------------------------------------------------------------------------
CREATE TABLE ledger_sequence (
    seq_no       INTEGER PRIMARY KEY,        -- The processing order itself, assigned at refresh (it is the rowid,
                                             -- so reading in order costs no sort)
    operation_id INTEGER NOT NULL REFERENCES operations (id) ON DELETE CASCADE,
    opart        INTEGER NOT NULL,           -- Which part of the operation this row is
    timestamp    INTEGER NOT NULL,           -- THIS part's moment, which is not always the operation's own
    account_id   INTEGER REFERENCES accounts (id),
    UNIQUE (operation_id, opart)
);
CREATE INDEX ledger_sequence_acct ON ledger_sequence (account_id, seq_no);
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=72 WHERE name='SchemaVersion';
COMMIT;
