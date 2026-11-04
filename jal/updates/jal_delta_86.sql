BEGIN TRANSACTION;
--------------------------------------------------------------------------------
-- TAX OVERRIDES: THE USER'S PER-JURISDICTION DECISION ON ONE OPERATION
--------------------------------------------------------------------------------
CREATE TABLE tax_overrides (
    id           INTEGER PRIMARY KEY UNIQUE NOT NULL,
    operation_id INTEGER NOT NULL REFERENCES operations (id) ON DELETE CASCADE,
    jurisdiction TEXT    NOT NULL,
    kind         INTEGER NOT NULL,
    value        TEXT    NOT NULL DEFAULT (''),
    note         TEXT    NOT NULL
);
CREATE UNIQUE INDEX tax_overrides_uniqueness ON tax_overrides (operation_id, jurisdiction, kind);
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=86 WHERE name='SchemaVersion';
COMMIT;
