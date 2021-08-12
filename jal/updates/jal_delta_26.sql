BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 0;
--------------------------------------------------------------------------------
-- Prepare 'assets' table for update
UPDATE assets SET isin='' WHERE isin IS NULL;
--------------------------------------------------------------------------------
-- Update 'assets' table
--------------------------------------------------------------------------------
CREATE TABLE sqlitestudio_temp_table AS SELECT * FROM assets;

DROP TABLE assets;
CREATE TABLE assets (
    id         INTEGER    PRIMARY KEY
                          UNIQUE
                          NOT NULL,
    name       TEXT (32)  NOT NULL,
    type_id    INTEGER    REFERENCES asset_types (id) ON DELETE RESTRICT
                                                      ON UPDATE CASCADE
                          NOT NULL,
    full_name  TEXT (128) NOT NULL,
    isin       TEXT (12)  DEFAULT ('')
                          NOT NULL,
    country_id INTEGER    REFERENCES countries (id) ON DELETE CASCADE
                                                    ON UPDATE CASCADE
                          NOT NULL
                          DEFAULT (0),
    src_id     INTEGER    REFERENCES data_sources (id) ON DELETE SET NULL
                                                       ON UPDATE CASCADE
                          NOT NULL
                          DEFAULT ( -1),
    expiry     INTEGER    NOT NULL
                          DEFAULT (0)
);

INSERT INTO assets (
                       id,
                       name,
                       type_id,
                       full_name,
                       isin,
                       country_id,
                       src_id
                   )
                   SELECT id,
                          name,
                          type_id,
                          full_name,
                          isin,
                          country_id,
                          src_id
                     FROM sqlitestudio_temp_table;

DROP TABLE sqlitestudio_temp_table;

CREATE UNIQUE INDEX asset_name_isin_idx ON assets (
    name ASC,
    isin ASC,
    expiry ASC
);
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 1;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=26 WHERE name='SchemaVersion';
COMMIT;
