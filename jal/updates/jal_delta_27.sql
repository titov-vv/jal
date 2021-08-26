BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 0;
--------------------------------------------------------------------------------
-- Update 'countries' table
--------------------------------------------------------------------------------
CREATE TABLE sqlitestudio_temp_table AS SELECT * FROM countries;

DROP TABLE countries;

CREATE TABLE countries (
    id         INTEGER      PRIMARY KEY
                            UNIQUE
                            NOT NULL,
    name       VARCHAR (64) UNIQUE
                            NOT NULL,
    code       CHAR (3)     UNIQUE
                            NOT NULL,
    iso_code   CHAR (4)     UNIQUE
                            NOT NULL,
    tax_treaty INTEGER      NOT NULL
                            DEFAULT (0)
);

INSERT INTO countries (
                          id,
                          name,
                          code,
                          iso_code,
                          tax_treaty
                      )
                      SELECT id,
                             name,
                             code,
                             code,   -- Need to put code as value should be unique
                             tax_treaty
                        FROM sqlitestudio_temp_table;

DROP TABLE sqlitestudio_temp_table;
--------------------------------------------------------------------------------
-- Update existing records
WITH c_codes(cc, iso_code) AS (VALUES ('xx', '000'), ('ru', '643'), ('us', '840'), ('ie', '372'), ('ch', '756'), ('fr', '250'), ('ca', '124'), ('se', '752'),
                                      ('it', '380'), ('es', '724'), ('au', '036'), ('at', '040'), ('be', '056'), ('gb', '826'), ('de', '276'),
                                      ('cn', '156'), ('fi', '246'), ('nl', '528'), ('gr', '300'), ('bm', '060'), ('br', '076'), ('je', '832'))
UPDATE countries SET iso_code = (SELECT iso_code FROM c_codes WHERE code = c_codes.cc)
WHERE code IN (SELECT cc FROM c_codes);
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 1;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=27 WHERE name='SchemaVersion';
COMMIT;
