BEGIN TRANSACTION;
--------------------------------------------------------------------------------
-- RESIDENCE REPLACES BASE CURRENCY
-- 'base_currency' kept the history of the reporting currency: one row per change, in force until the
-- next one. That is the shape a residence history has as well, and the two are usually the same event -
-- the user moved country, which changed the jurisdiction, the wall clock and the reporting currency at
-- once. So the table is renamed and given the two facts it was missing rather than a second table being
-- built beside it.
--
-- The two new columns start empty on every row that exists. A migration cannot know where its user
-- lived, and a tax jurisdiction is not a thing to guess quietly - so 'country_id' stays 0 and 'timezone'
-- stays empty until the user states them, and both read as "this row doesn't say, the last one that did
-- still holds".
--
-- The table is re-created instead of ALTERed because ADD COLUMN cannot add a column with a REFERENCES
-- clause, and a database upgraded here must end up with exactly the schema a new one is created with.
DROP TABLE IF EXISTS residence;
CREATE TABLE residence (
    id              INTEGER PRIMARY KEY UNIQUE NOT NULL,
    since_timestamp INTEGER NOT NULL UNIQUE,
    currency_id     INTEGER NOT NULL REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE,
    country_id      INTEGER NOT NULL DEFAULT (0) REFERENCES countries (id) ON DELETE SET DEFAULT ON UPDATE CASCADE,
    timezone        TEXT    NOT NULL DEFAULT ('')
);
INSERT INTO residence (id, since_timestamp, currency_id)
    SELECT id, since_timestamp, currency_id FROM base_currency;
DROP TABLE base_currency;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=65 WHERE name='SchemaVersion';
COMMIT;
