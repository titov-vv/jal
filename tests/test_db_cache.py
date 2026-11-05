import gc

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_taxes
from jal.db.db import JalDB
from jal.db.account import JalAccount
from jal.db.asset import JalAsset


class _OwnCache(JalDB):   # a cache of its own in every instance
    def __init__(self):
        super().__init__(cached=True)
        self.cleared = False

    def invalidate_cache(self):
        self.cleared = True


# One instance per class-level cache is kept however many are made, and invalidating still reaches the class cache
def test_class_cache_keeps_one_instance(prepare_db_taxes):
    accounts = [JalAccount(1) for _ in range(1000)]
    assert len([x for x in JalDB._class_caches.values() if type(x) is JalAccount]) == 1
    del accounts
    gc.collect()
    name = JalAccount(1).name()
    JalDB._exec("UPDATE accounts SET name='Renamed' WHERE id=1", commit=True)
    assert JalAccount(1).name() == name
    JalDB().invalidate_cache()
    assert JalAccount(1).name() == 'Renamed'
    assert JalAsset(1).symbol()   # another class cache registered beside it


# An instance with a cache of its own is invalidated while alive and leaves the registry when it is gone
def test_instance_cache_is_held_weakly(prepare_db):
    alive, gone = _OwnCache(), _OwnCache()
    gone_id = id(gone)
    del gone
    gc.collect()
    assert gone_id not in JalDB._instance_caches
    JalDB().invalidate_cache()
    assert alive.cleared
