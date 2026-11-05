import sqlparse

from tests.fixtures import project_root, data_path, prepare_db
from jal.db.db import JalDB

_MIGRATION_FROM = "-- OPEN LOTS:"
_MIGRATION_TO = "-- Set new DB schema version"


def _run_migration(project_root):
    with open(project_root + "/jal/updates/jal_delta_87.sql", encoding='utf-8') as delta:
        text = delta.read()
    for statement in sqlparse.split(text[text.index(_MIGRATION_FROM):text.index(_MIGRATION_TO)]):
        if not sqlparse.format(statement, strip_comments=True).strip():
            continue
        assert JalDB._exec(statement.strip(), commit=True) is not None, f"Migration statement failed: {statement}"


def _index_sql() -> str:
    return JalDB._read("SELECT sql FROM sqlite_master WHERE type='index' AND name='open_trades_by_position'")


# A schema-86 database has no index; the delta creates the same one jal_init.sql does
def test_delta_87_upgrade(prepare_db, project_root):
    index = _index_sql()
    JalDB._exec("DROP INDEX open_trades_by_position", commit=True)
    assert _index_sql() is None

    _run_migration(project_root)

    assert _index_sql() == index


# The position query of JalAccount.open_trades_list() searches by the index instead of scanning the table
def test_open_lots_query_uses_index(prepare_db):
    plan = []
    query = JalDB._exec("EXPLAIN QUERY PLAN SELECT remaining_qty FROM trades_opened "
                        "WHERE account_id=1 AND asset_id=4 AND timestamp<=100")
    while query.next():
        plan.append(query.value(3))
    assert any("USING INDEX open_trades_by_position" in x for x in plan), plan
