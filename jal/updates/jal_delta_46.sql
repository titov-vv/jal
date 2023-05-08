BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 0;
--------------------------------------------------------------------------------
-- Add tree-hierarchy to 'tags' table
CREATE TABLE temp_tags AS SELECT * FROM tags;
DROP TABLE tags;
CREATE TABLE tags (
    id  INTEGER   PRIMARY KEY UNIQUE NOT NULL,
    pid INTEGER   NOT NULL DEFAULT (0),
    tag TEXT (64) NOT NULL UNIQUE
);
INSERT INTO tags (id, tag) SELECT id, tag FROM temp_tags;
DROP TABLE temp_tags;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 1;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=46 WHERE name='SchemaVersion';
COMMIT;
-- Reduce file size
VACUUM;