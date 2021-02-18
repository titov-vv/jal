BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 0;

--------------------------------------------------------------------------------
-- Change constraints on 'assets' table
--------------------------------------------------------------------------------
CREATE TABLE sqlitestudio_temp_table AS SELECT *
                                          FROM assets;

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
    isin       TEXT (12),
    country_id INTEGER    REFERENCES countries (id) ON DELETE CASCADE
                                                    ON UPDATE CASCADE
                          NOT NULL
                          DEFAULT (0),
    src_id     INTEGER    REFERENCES data_sources (id) ON DELETE SET NULL
                                                       ON UPDATE CASCADE
                          NOT NULL
                          DEFAULT ( -1)
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
    isin ASC
);

--------------------------------------------------------------------------------
PRAGMA foreign_keys = 1;

--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=15 WHERE name='SchemaVersion';

COMMIT;