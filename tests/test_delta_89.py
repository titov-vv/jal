import sqlparse

from tests.fixtures import project_root, data_path, prepare_db
from jal.db.db import JalDB

_MIGRATION_FROM = "-- Ledger rows of asset operations"
_MIGRATION_TO = "-- Set new DB schema version"


def _run_migration(project_root):
    with open(project_root + "/jal/updates/jal_delta_89.sql", encoding='utf-8') as delta:
        text = delta.read()
    for statement in sqlparse.split(text[text.index(_MIGRATION_FROM):text.index(_MIGRATION_TO)]):
        if not sqlparse.format(statement, strip_comments=True).strip():
            continue
        assert JalDB._exec(statement.strip(), commit=True) is not None, f"Migration statement failed: {statement}"


def _trigger_sql() -> str:
    return JalDB._read("SELECT sql FROM sqlite_master WHERE type='trigger' AND name='tags_after_delete'")


# Asset tags go and the tag trigger becomes the one jal_init.sql creates
def test_delta_89_upgrade(prepare_db, project_root):
    trigger = _trigger_sql()
    tag_id = JalDB._read("SELECT id FROM tags WHERE tag='Cash'")
    asset_id = JalDB._read("SELECT MIN(id) FROM assets")
    JalDB._exec("INSERT INTO asset_data (asset_id, datatype, value) VALUES (:asset, 1, :tag)",
                [(":asset", asset_id), (":tag", str(tag_id))], commit=True)
    assert JalDB._read("SELECT COUNT(*) FROM asset_data WHERE datatype=1") == 1

    _run_migration(project_root)

    assert _trigger_sql() == trigger
    assert JalDB._read("SELECT COUNT(*) FROM asset_data WHERE datatype=1") == 0
    assert JalDB._read("SELECT value FROM settings WHERE name='RebuildDB'") == '1'
