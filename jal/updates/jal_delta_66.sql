BEGIN TRANSACTION;
--------------------------------------------------------------------------------
-- ICONS MOVE OUT OF THE TABLES THEY DECORATE
--------------------------------------------------------------------------------
CREATE TABLE icons (
    id      INTEGER PRIMARY KEY UNIQUE NOT NULL,
    entity  INTEGER NOT NULL,   -- kind of the owning element (see IconOwner)
    item_id INTEGER NOT NULL,   -- id of the owning row inside that kind's table
    image   BLOB    NOT NULL,   -- PNG image; zero length means "this element deliberately has no icon"
    source  INTEGER NOT NULL    -- who wrote this row - a download or the user (see IconSource)
);
CREATE UNIQUE INDEX icons_uniqueness ON icons (entity, item_id);
--------------------------------------------------------------------------------
-- Migrate existing asset items
INSERT INTO icons (entity, item_id, image, source)
    SELECT 2, id, icon, 1 FROM asset_symbol WHERE icon IS NOT NULL;
ALTER TABLE asset_symbol DROP COLUMN icon;
--------------------------------------------------------------------------------
-- Drop outdated column
ALTER TABLE tags DROP COLUMN icon_file;
--------------------------------------------------------------------------------
-- Triggers, one per table that has icons: (entity, item_id) is a reference no foreign key can express,
-- so a deleted element has to take its icon with it by hand.
CREATE TRIGGER accounts_after_delete_icon AFTER DELETE ON accounts FOR EACH ROW
BEGIN
    DELETE FROM icons WHERE entity=1 AND item_id=OLD.id;
END;
CREATE TRIGGER asset_symbol_after_delete_icon AFTER DELETE ON asset_symbol FOR EACH ROW
BEGIN
    DELETE FROM icons WHERE entity=2 AND item_id=OLD.id;
END;
CREATE TRIGGER tags_after_delete_icon AFTER DELETE ON tags FOR EACH ROW
BEGIN
    DELETE FROM icons WHERE entity=3 AND item_id=OLD.id;
END;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=66 WHERE name='SchemaVersion';
COMMIT;
