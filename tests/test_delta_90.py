import sqlparse

from tests.fixtures import project_root, data_path, prepare_db
from jal.db.db import JalDB

_MIGRATION_FROM = "-- PORTFOLIOS:"
_MIGRATION_TO = "-- Set new DB schema version"


def _run_migration(project_root):
    with open(project_root + "/jal/updates/jal_delta_90.sql", encoding='utf-8') as delta:
        text = delta.read()
    for statement in sqlparse.split(text[text.index(_MIGRATION_FROM):text.index(_MIGRATION_TO)]):
        if not sqlparse.format(statement, strip_comments=True).strip():
            continue
        assert JalDB._exec(statement.strip(), commit=True) is not None, f"Migration statement failed: {statement}"


def _table_sql() -> str:
    return JalDB._read("SELECT sql FROM sqlite_master WHERE type='table' AND name='operation_portfolios'")


# A schema-89 database has no table; the delta creates the same one jal_init.sql does
def test_delta_90_upgrade(prepare_db, project_root):
    table = _table_sql()
    JalDB._exec("DROP TABLE operation_portfolios", commit=True)
    assert _table_sql() is None

    _run_migration(project_root)

    assert _table_sql() == table
