BEGIN TRANSACTION;

-- Create new table with list of countries
CREATE TABLE countries (
    id           INTEGER      PRIMARY KEY
                              UNIQUE
                              NOT NULL,
    name         VARCHAR (64) UNIQUE
                              NOT NULL,
    code         CHAR (3)     UNIQUE
                              NOT NULL,
    tax_ageement INTEGER      NOT NULL
                              DEFAULT (0)
);

-- Make some pre-defined countries
INSERT INTO countries (id, name, code, tax_ageement) VALUES (1, 'N/A', 'xx', 0);
INSERT INTO countries (id, name, code, tax_ageement) VALUES (1, 'Russia', 'ru', 0);
INSERT INTO countries (id, name, code, tax_ageement) VALUES (2, 'United States', 'us', 1);
INSERT INTO countries (id, name, code, tax_ageement) VALUES (3, 'Ireland', 'ie', 1);
INSERT INTO countries (id, name, code, tax_ageement) VALUES (4, 'Switzerland', 'ch', 1);
INSERT INTO countries (id, name, code, tax_ageement) VALUES (5, 'France', 'fr', 1);
INSERT INTO countries (id, name, code, tax_ageement) VALUES (6, 'Canada', 'ca', 1);
INSERT INTO countries (id, name, code, tax_ageement) VALUES (7, 'Sweden', 'se', 1);

-- Modify dividends table to inclue new 'tax_country_id' column
CREATE TABLE sqlitestudio_temp_table AS SELECT *
                                          FROM dividends;

DROP TABLE dividends;

CREATE TABLE dividends (
    id             INTEGER     PRIMARY KEY
                               UNIQUE
                               NOT NULL,
    timestamp      INTEGER     NOT NULL,
    number         TEXT (32)   DEFAULT (''),
    account_id     INTEGER     REFERENCES accounts (id) ON DELETE CASCADE
                                                        ON UPDATE CASCADE
                               NOT NULL,
    asset_id       INTEGER     REFERENCES assets (id) ON DELETE RESTRICT
                                                      ON UPDATE CASCADE
                               NOT NULL,
    sum            REAL        NOT NULL
                               DEFAULT (0),
    sum_tax        REAL        DEFAULT (0),
    note           TEXT (1014),
    note_tax       TEXT (64),
    tax_country_id INTEGER     REFERENCES countries (id) ON DELETE CASCADE
                                                         ON UPDATE CASCADE
                               DEFAULT (0)
);

INSERT INTO dividends (
                          id,
                          timestamp,
                          number,
                          account_id,
                          asset_id,
                          sum,
                          sum_tax,
                          note,
                          note_tax
                      )
                      SELECT id,
                             timestamp,
                             number,
                             account_id,
                             asset_id,
                             sum,
                             sum_tax,
                             note,
                             note_tax
                        FROM sqlitestudio_temp_table;

DROP TABLE sqlitestudio_temp_table;

CREATE TRIGGER dividends_after_delete
         AFTER DELETE
            ON dividends
      FOR EACH ROW
          WHEN (
    SELECT value
      FROM settings
     WHERE id = 1
)
BEGIN
    DELETE FROM ledger
          WHERE timestamp >= OLD.timestamp;
    DELETE FROM sequence
          WHERE timestamp >= OLD.timestamp;
    DELETE FROM ledger_sums
          WHERE timestamp >= OLD.timestamp;
END;

CREATE TRIGGER dividends_after_insert
         AFTER INSERT
            ON dividends
      FOR EACH ROW
          WHEN (
    SELECT value
      FROM settings
     WHERE id = 1
)
BEGIN
    DELETE FROM ledger
          WHERE timestamp >= NEW.timestamp;
    DELETE FROM sequence
          WHERE timestamp >= NEW.timestamp;
    DELETE FROM ledger_sums
          WHERE timestamp >= NEW.timestamp;
END;

CREATE TRIGGER dividends_after_update
         AFTER UPDATE OF timestamp,
                         account_id,
                         asset_id,
                         sum,
                         sum_tax
            ON dividends
      FOR EACH ROW
          WHEN (
    SELECT value
      FROM settings
     WHERE id = 1
)
BEGIN
    DELETE FROM ledger
          WHERE timestamp >= OLD.timestamp OR
                timestamp >= NEW.timestamp;
    DELETE FROM sequence
          WHERE timestamp >= OLD.timestamp OR
                timestamp >= NEW.timestamp;
    DELETE FROM ledger_sums
          WHERE timestamp >= OLD.timestamp OR
                timestamp >= NEW.timestamp;
END;

-- Assign country based on 'note_tax' field
-- Update russian:
UPDATE dividends SET tax_country_id=1 WHERE note_tax='НДФЛ';
-- Update all other based on 'XX tax' value of 'note_tax' field
UPDATE dividends
SET tax_country_id = (SELECT countries.id FROM countries WHERE countries.code = substr(dividends.note_tax, 1, 2) COLLATE NOCASE)
WHERE EXISTS (SELECT countries.* FROM countries WHERE countries.code = substr(dividends.note_tax, 1, 2) COLLATE NOCASE);
-- Set default if anything remains NULL
UPDATE dividends SET tax_country_id=0 WHERE tax_country_id IS NULL;

-- Set new DB schema version
UPDATE settings SET value=11 WHERE name='SchemaVersion';

COMMIT;

