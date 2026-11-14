from tests.fixtures import project_root, data_path, prepare_db
from jal.db.db import JalDB

_NAME = "SELECT name FROM accounts WHERE id=:id"


# A reused query is re-bound on every call: each read answers for its own parameters
def test_a_reused_read_is_rebound(prepare_db):
    JalDB._exec("INSERT INTO tags (pid, tag) VALUES (0, 'first'), (0, 'second')", commit=True)
    tags = {tag: tag_id for tag_id, tag in JalDB._read_to_list("SELECT id, tag FROM tags")}
    JalDB.start_statement_reuse()
    try:
        names = [JalDB._read("SELECT tag FROM tags WHERE id=:id", [(":id", tags[x])]) for x in ('first', 'second')]
        assert names == ['first', 'second']
        assert list(JalDB._statements) == [("SELECT tag FROM tags WHERE id=:id", True)]
        assert not JalDB._statements[("SELECT tag FROM tags WHERE id=:id", True)].isActive()
    finally:
        JalDB.stop_statement_reuse()


# Only the outermost stop drops the cache, and nothing is kept outside a scope
def test_the_cache_lives_until_the_outermost_stop(prepare_db):
    JalDB._read(_NAME, [(":id", 1)])
    assert JalDB._statements is None
    JalDB.start_statement_reuse()
    JalDB.start_statement_reuse()
    JalDB._read(_NAME, [(":id", 1)])
    JalDB.stop_statement_reuse()
    assert (_NAME, True) in JalDB._statements
    JalDB.stop_statement_reuse()
    assert JalDB._statements is None


# A plain _exec() is never cached: its query belongs to the caller that iterates it
def test_a_plain_exec_is_not_reused(prepare_db):
    JalDB.start_statement_reuse()
    try:
        outer = JalDB._exec("SELECT id FROM tags ORDER BY id")
        inner = JalDB._exec("SELECT id FROM tags ORDER BY id")
        assert outer is not inner
        assert not JalDB._statements
    finally:
        JalDB.stop_statement_reuse()


# A statement that failed is dropped, the next call prepares it again
def test_a_failed_statement_leaves_the_cache(prepare_db):
    insert = "INSERT INTO tags (pid, tag) VALUES (0, :tag)"
    JalDB.start_statement_reuse()
    try:
        assert JalDB._exec(insert, [(":tag", None)], reuse=True) is None   # tag is NOT NULL
        assert not JalDB._statements
        assert JalDB._exec(insert, [(":tag", 'third')], reuse=True) is not None
        assert JalDB._read("SELECT COUNT(*) FROM tags WHERE tag='third'") == 1
    finally:
        JalDB.stop_statement_reuse()


# The scope is shared by every JalDB subclass, whichever of them opened it
def test_a_scope_opened_by_a_subclass_reaches_all(prepare_db):
    class _Opener(JalDB):
        pass

    _Opener().start_statement_reuse()
    try:
        JalDB._read(_NAME, [(":id", 1)])
        assert (_NAME, True) in JalDB._statements
        assert '_statements' not in vars(_Opener)
    finally:
        _Opener().stop_statement_reuse()
    assert JalDB._statements is None
