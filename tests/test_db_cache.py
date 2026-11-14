from tests.fixtures import project_root, data_path, prepare_db, prepare_db_taxes
from jal.db.db import JalDB, JalDBError
from jal.db.cache import DbCache, UniversalCache
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.residence import JalResidence
from jal.widgets.helpers import DateFormat, RowPadding


# A cached row survives a write made behind its class's back until the caches are invalidated
def test_invalidation_reaches_class_caches(prepare_db_taxes):
    name = JalAccount(1).name()
    asset_name = JalAsset(2).name()
    JalDB._exec("UPDATE accounts SET name='Renamed' WHERE id=1")
    JalDB._exec("UPDATE assets SET full_name='RENAMED' WHERE id=2", commit=True)
    assert JalAccount(1).name() == name
    assert JalAsset(2).name() == asset_name
    JalAccount(1).invalidate_cache()    # called on any class or object, it empties all of them
    assert JalAccount(1).name() == 'Renamed'
    assert JalAsset(2).name() == 'RENAMED'


# Making objects doesn't grow the registry: a cache is registered once, when it is created
def test_registry_holds_caches_not_objects(prepare_db_taxes):
    before = len(DbCache._all)
    _ = [JalAccount(1) for _ in range(1000)]
    assert len(DbCache._all) == before
    assert JalAccount.db_cache in DbCache._all and JalResidence.db_cache in DbCache._all


# What is kept outside a DbCache is emptied by the same call
def test_invalidation_reaches_registered_functions(prepare_db):
    DateFormat.current()
    RowPadding.factor()
    JalAsset._missing_quotes.add('a miss')
    assert DateFormat._current is not None and RowPadding._current is not None
    JalDB.invalidate_cache()
    assert DateFormat._current is None and RowPadding._current is None
    assert not JalAsset._missing_quotes


# A plain UniversalCache belongs to its owner and stays out of the registry
def test_owner_cache_is_not_registered(prepare_db):
    cache = UniversalCache()
    assert cache.get_data(len, ('abc',)) == 3
    JalDB.invalidate_cache()
    assert cache not in DbCache._all
    assert cache._cache


# A row written inside a transaction and cached is gone from the cache once the transaction is rolled back
def test_rollback_empties_the_caches(prepare_db_taxes):
    name = JalAccount(1).name()
    JalDB().start_transaction()
    JalDB._exec("UPDATE accounts SET name='Pending' WHERE id=1")
    JalAccount.db_cache.clear_cache()
    assert JalAccount(1).name() == 'Pending'
    JalDB().rollback_transaction()
    assert JalAccount(1).name() == name


# Opening a database leaves nothing cached from the one that was open before
def test_opening_a_database_empties_the_caches(prepare_db_taxes):
    name = JalAccount(1).name()
    JalDB._exec("UPDATE accounts SET name='Renamed' WHERE id=1", commit=True)
    assert JalAccount(1).name() == name
    JalDB.connection().close()
    assert JalDB().init_db().code == JalDBError.NoError
    assert JalAccount(1).name() == 'Renamed'
