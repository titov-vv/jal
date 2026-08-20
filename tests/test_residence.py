import pytest
import sqlparse

from PySide6.QtSql import QSqlTableModel
from PySide6.QtWidgets import QMessageBox

from tests.fixtures import project_root, data_path, prepare_db
from jal.db.db import JalDB
from jal.db.asset import JalAsset
from jal.db.common_models import BaseCurrencyListModel

# Where the residence migration starts and ends inside the delta. It is run from the shipped file rather than
# copied here, so this test breaks if the migration text stops doing what it says.
_MIGRATION_FROM = "-- RESIDENCE REPLACES BASE CURRENCY"
_MIGRATION_TO = "-- Set new DB schema version"

# The retired table, as it looked in schema version 64.
_OLD_SCHEMA = """
CREATE TABLE base_currency (
    id              INTEGER PRIMARY KEY UNIQUE NOT NULL,
    since_timestamp INTEGER NOT NULL UNIQUE,
    currency_id     INTEGER NOT NULL REFERENCES assets (id) ON DELETE CASCADE ON UPDATE CASCADE
);
"""


def _run(text):
    for statement in sqlparse.split(text):
        if not sqlparse.format(statement, strip_comments=True).strip():
            continue   # a run of comment lines is not a statement
        assert JalDB._exec(statement.strip()) is not None, f"Statement failed: {statement}"


@pytest.fixture
def old_base_currency(prepare_db):
    JalDB._exec("DROP TABLE residence")
    _run(_OLD_SCHEMA)
    for row in [(1, 946684800, 1), (2, 1662854400, 2)]:
        JalDB._exec("INSERT INTO base_currency (id, since_timestamp, currency_id) VALUES (:id, :since, :currency)",
                    [(":id", row[0]), (":since", row[1]), (":currency", row[2])])
    yield


# The history of the reporting currency is what the residence timeline is built on, so the migration has to carry
# every row of it over untouched - the same ids, the same dates, the same currencies.
def test_the_currency_history_survives_the_move_to_residence(project_root, old_base_currency):
    with open(project_root + "/jal/updates/jal_delta_65.sql") as delta:
        text = delta.read()
    _run(text[text.index(_MIGRATION_FROM):text.index(_MIGRATION_TO)])

    rows = []
    query = JalDB._exec("SELECT id, since_timestamp, currency_id, country_id, timezone FROM residence "
                        "ORDER BY since_timestamp")
    while query.next():
        rows.append(JalDB._read_record(query, cast=[int, int, int, int, str]))
    assert rows == [[1, 946684800, 1, 0, ''], [2, 1662854400, 2, 0, '']]   # residence itself is not guessed
    assert JalAsset.get_base_currency(1662854400) == 2
    assert JalDB._read("SELECT COUNT(*) FROM sqlite_master WHERE name='base_currency'") == 0


# The two facts a residence row carries beyond the currency are optional, and the dialog that maintains the table
# doesn't ask for them yet. A row must therefore be committable while it states neither of them.
def test_a_new_row_needs_neither_country_nor_timezone(prepare_db, monkeypatch):
    refusals = []
    monkeypatch.setattr(QMessageBox, 'warning',
                        lambda *args, **kwargs: refusals.append(args[2]) or QMessageBox.Ok)
    model = BaseCurrencyListModel()
    model.setEditStrategy(QSqlTableModel.OnManualSubmit)
    model.select()
    model.addElement(model.index(0, 0))
    model.setData(model.index(0, model.fieldIndex("since_timestamp")), 1662854400)
    model.setData(model.index(0, model.fieldIndex("currency_id")), 2)

    assert model.submitAll(), model.lastError().databaseText()
    assert refusals == []
    assert JalDB._read("SELECT country_id FROM residence WHERE since_timestamp=1662854400") == 0
    assert JalDB._read("SELECT timezone FROM residence WHERE since_timestamp=1662854400") == ''
