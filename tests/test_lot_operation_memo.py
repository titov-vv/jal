from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import create_trades
from tests.test_lot_decisions import lots, USD_ACC, A, T2, T3, TRADE
from jal.db.db import JalDB
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.ledger import Ledger
from jal.db.lots import LotEngine
from jal.db.operations import LedgerTransaction


def _loads(monkeypatch) -> list:
    loaded = []
    original = LedgerTransaction.get_operation
    monkeypatch.setattr(LedgerTransaction, 'get_operation',
                        staticmethod(lambda otype, oid, opart=0: loaded.append((otype, oid, opart)) or original(otype, oid, opart)))
    return loaded


# The operation that opened a lot is loaded once by an engine, however many times the position is matched
def test_opening_operation_is_loaded_once(lots, monkeypatch):
    Ledger().rebuild(from_timestamp=0)
    loaded = _loads(monkeypatch)
    engine = LotEngine()
    first = engine.lots(JalAccount(USD_ACC), JalAsset(A))
    second = engine.lots(JalAccount(USD_ACC), JalAsset(A))
    assert len(loaded) == 1
    assert first[0].open_operation() is second[0].open_operation()
    engine.forget()
    engine.lots(JalAccount(USD_ACC), JalAsset(A))
    assert len(loaded) == 2


# A rebuild keeps nothing: the ledger's engine is empty before and after it
def test_rebuild_forgets_the_operations(lots):
    create_trades(USD_ACC, [(T2, T2, A, -4, 150, 0, "sell-A")])
    ledger = Ledger()
    ledger.rebuild(from_timestamp=0)
    assert ledger.lots._operations == {}
    ledger.lots.lots(JalAccount(USD_ACC), JalAsset(A))
    assert ledger.lots._operations
    create_trades(USD_ACC, [(T3, T3, A, -6, 160, 0, "sell-rest")])
    ledger.rebuild(from_timestamp=0)
    assert ledger.lots._operations == {}
    assert JalDB._read("SELECT COUNT(*) FROM trades_closed") == 2
