import pytest
import sqlparse

from PySide6.QtSql import QSqlTableModel
from PySide6.QtWidgets import QMessageBox, QWidget

from tests.fixtures import project_root, data_path, prepare_db
from jal.db.db import JalDB
from jal.db.asset import JalAsset
from jal.db.common_models import ResidenceListModel
from jal.db.residence import JalResidence
from jal.widgets.delegates import TimezoneDelegate

# Where the residence migration starts and ends inside the delta. It is run from the shipped file rather than
# copied here, so this test breaks if the migration text stops doing what it says.
_MIGRATION_FROM = "-- RESIDENCE REPLACES BASE CURRENCY"
_MIGRATION_TO = "-- A TIMESTAMP THAT STATES A DAY SAYS SO ITSELF"   # the next section of the same delta

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


# The two facts a residence row carries beyond the currency are optional - a move that changes only the reporting
# currency states neither. A row must therefore be committable while it says nothing about the country or the clock.
def test_a_new_row_needs_neither_country_nor_timezone(prepare_db, monkeypatch):
    refusals = []
    monkeypatch.setattr(QMessageBox, 'warning',
                        lambda *args, **kwargs: refusals.append(args[2]) or QMessageBox.Ok)
    model = _model_with_new_row(1662854400, currency=2)

    assert model.submitAll(), model.lastError().databaseText()
    assert refusals == []
    assert JalDB._read("SELECT country_id FROM residence WHERE since_timestamp=1662854400") == 0
    assert JalDB._read("SELECT timezone FROM residence WHERE since_timestamp=1662854400") == ''


# Builds the model the residence dialog is made of and leaves a new, uncommitted row in it
def _model_with_new_row(since: int, currency: int, country: int = None, timezone: str = None) -> ResidenceListModel:
    model = ResidenceListModel()
    model.setEditStrategy(QSqlTableModel.OnManualSubmit)
    model.select()
    model.addElement(model.index(0, 0))
    model.setData(model.index(0, model.fieldIndex("since_timestamp")), since)
    model.setData(model.index(0, model.fieldIndex("currency_id")), currency)
    if country is not None:
        model.setData(model.index(0, model.fieldIndex("country_id")), country)
    if timezone is not None:
        model.setData(model.index(0, model.fieldIndex("timezone")), timezone)
    return model


# Fills the table with a timeline and makes sure the cached one is re-read from it
def _timeline(rows):
    JalDB._exec("DELETE FROM residence")
    for row in rows:
        JalDB._exec("INSERT INTO residence (since_timestamp, currency_id, country_id, timezone) "
                    "VALUES (:since, :currency, :country, :timezone)",
                    [(":since", row[0]), (":currency", row[1]), (":country", row[2]), (":timezone", row[3])])
    JalResidence.invalidate_cache()


# A row states the facts that changed. One that leaves the country or the clock blank doesn't reset them to nothing -
# the last row that did state them still holds, which is what a currency-only change (RUB -> USD, same country) means.
def test_a_blank_fact_is_inherited_from_the_row_that_stated_it(prepare_db):
    _timeline([(946684800, 1, 1, 'Europe/Moscow'), (1662854400, 2, 0, '')])

    assert JalResidence.currency(1700000000) == 2      # ... the currency did change
    assert JalResidence.country(1700000000) == 1       # ... while these two are what the first row said
    assert JalResidence.timezone(1700000000) == 'Europe/Moscow'


# Nothing precedes the first row of the timeline, so nothing can be derived for a moment before it. An empty zone is
# what says so: a caller that meets one keeps doing whatever it did before instead of guessing on the user's behalf.
def test_a_moment_before_the_timeline_states_nothing(prepare_db):
    _timeline([(1662854400, 2, 5, 'Europe/Lisbon')])

    assert JalResidence.timezone(946684800) == ''
    assert JalResidence.country(946684800) == 0
    assert JalResidence.currency(946684800) == 0
    assert JalResidence.timezone(1662854400) == 'Europe/Lisbon'   # the row is in force from its own date on


# The timeline is answered from memory, so an edit made through the dialog has to drop what is cached - otherwise
# the user states where they live and everything keeps reading the timestamps by the zone they left.
def test_an_edit_made_in_the_dialog_reaches_the_timeline(prepare_db, monkeypatch):
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args, **kwargs: QMessageBox.Ok)
    assert JalResidence.timezone(1662854400) == ''   # caches a timeline that states no zone at all
    model = _model_with_new_row(1662854400, currency=2, country=5, timezone='Europe/Lisbon')

    assert model.submitAll(), model.lastError().databaseText()
    assert JalResidence.timezone(1662854400) == 'Europe/Lisbon'
    assert JalResidence.country(1662854400) == 5


# Every widget built here gets a parent: a parentless one is collected by the cyclic collector at a moment
# unrelated to the test that made it, and takes the process down with it.
@pytest.fixture
def parent(prepare_db):
    holder = QWidget()
    yield holder
    holder.deleteLater()


# The zone is picked from a list rather than typed, so that what is stored is always a name ZoneInfo() accepts.
# The empty name has to stay reachable through it - it is how a row says it doesn't state a zone, and a cell left
# as NULL instead would be refused by the table.
def test_a_timezone_is_picked_from_the_ones_the_system_knows(parent):
    model = _model_with_new_row(1662854400, currency=2, timezone='Europe/Moscow')
    index = model.index(0, model.fieldIndex("timezone"))
    delegate = TimezoneDelegate(parent)
    editor = delegate.createEditor(parent, None, index)
    delegate.setEditorData(editor, index)

    assert editor.itemText(0) == ''
    assert editor.currentText() == 'Europe/Moscow'
    editor.setCurrentIndex(editor.findText('Europe/Lisbon'))   # a zone the list is expected to know
    delegate.setModelData(editor, model, index)
    assert model.data(index) == 'Europe/Lisbon'

    editor.setCurrentIndex(0)
    delegate.setModelData(editor, model, index)
    assert model.data(index) == ''
    assert model.submitAll(), model.lastError().databaseText()
