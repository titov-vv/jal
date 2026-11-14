BEGIN TRANSACTION;
--------------------------------------------------------------------------------
-- RECEIPT ITEMS: WHAT THE USER MADE OF THE ITEMS A SHOP PRINTS ON ITS RECEIPTS
--------------------------------------------------------------------------------
CREATE TABLE receipt_items (
    id          INTEGER PRIMARY KEY UNIQUE NOT NULL,
    peer_id     INTEGER REFERENCES agents (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,      -- the shop
    printed     TEXT    NOT NULL,                                                                 -- item text as the receipt prints it
    name        TEXT    NOT NULL DEFAULT (''),                                                    -- name given by the user, empty if the printed one was kept
    category_id INTEGER REFERENCES categories (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    tag_id      INTEGER REFERENCES tags (id) ON DELETE SET NULL ON UPDATE CASCADE,
    UNIQUE (peer_id, printed)
);
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=88 WHERE name='SchemaVersion';
COMMIT;
VACUUM;
