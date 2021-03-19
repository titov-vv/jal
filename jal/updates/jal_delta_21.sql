BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 0;
--------------------------------------------------------------------------------
-- Add triggers for account validation
--------------------------------------------------------------------------------
DROP TRIGGER IF EXISTS validate_account_insert;
CREATE TRIGGER validate_account_insert
        BEFORE INSERT
            ON accounts
      FOR EACH ROW
          WHEN NEW.type_id = 4 AND
               NEW.organization_id IS NULL
BEGIN
    SELECT RAISE(ABORT, "JAL_SQL_MSG_0001");
END;

DROP TRIGGER IF EXISTS validate_account_update;
CREATE TRIGGER validate_account_update
        BEFORE UPDATE
            ON accounts
      FOR EACH ROW
          WHEN NEW.type_id = 4 AND
               NEW.organization_id IS NULL
BEGIN
    SELECT RAISE(ABORT, "JAL_SQL_MSG_0001");
END;

DROP TRIGGER IF EXISTS keep_predefined_categories;
CREATE TRIGGER keep_predefined_categories
        BEFORE DELETE
            ON categories
      FOR EACH ROW
          WHEN OLD.special = 1
BEGIN
    SELECT RAISE(ABORT, "JAL_SQL_MSG_0002");
END;

--------------------------------------------------------------------------------
PRAGMA foreign_keys = 1;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=21 WHERE name='SchemaVersion';
COMMIT;