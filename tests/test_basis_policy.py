import pytest

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import create_quotes, create_trades, create_swaps, create_conversions
from tests.test_lot_decisions import lots, _opened, _closed, _oid, USD_ACC, A, B, T1, T2, T3, TRADE, SWAP, CONV
from jal.constants import SwapTreatment
from jal.db.basis_policy import Basis, Clock, Treatment, JalPolicy
from jal.db.ledger import Ledger
from jal.db.lots import LotEngine


# A policy that answers otherwise than JAL: every swap is a disposal, a wrapping restarts the date, newest lot first
class OtherPolicy(JalPolicy):
    def treatment(self, operation) -> Treatment:
        if operation.type() == SWAP:
            return Treatment(Basis.DISPOSAL, Clock.RESTART)
        return Treatment(Basis.CARRY, Clock.RESTART)

    def order(self, lots: list) -> list:
        return list(reversed(super().order(lots)))


def _rebuild(policy):
    ledger = Ledger()
    ledger.lots = LotEngine(policy=policy)
    ledger.rebuild(from_timestamp=0)


# A swap booked as a conversion is realized at the market when the policy says it is a disposal
def test_policy_turns_a_conversion_swap_into_a_disposal(lots):
    create_quotes(A, 2, [(T2, 120)])
    create_swaps(USD_ACC, [(T2, A, 10, B, 20)], treatment=SwapTreatment.Conversion)
    _rebuild(OtherPolicy())

    buy, swap = _oid(TRADE, 1), _oid(SWAP, 1)
    assert _closed(USD_ACC, A) == [[TRADE, buy, T1, '1E+2', '1E+1', SWAP, swap, T2, '1.2E+2', '1E+1', '1', '1', '1']]
    assert _opened(USD_ACC, B) == [[T2, SWAP, swap, SWAP, swap, T2, '6E+1', '2E+1', '1', '1', '1']]


# A wrapping carries the cost but restarts the date when the policy says so
def test_policy_restarts_the_date_of_a_wrapping(lots):
    create_conversions(USD_ACC, [(T2, A, 10, B, 20)])
    _rebuild(OtherPolicy())

    assert _opened(USD_ACC, B) == [[T2, TRADE, _oid(TRADE, 1), CONV, _oid(CONV, 1), T2, '1E+2', '2E+1', '0.5', '2', '1']]


# The order the policy gives is the order a disposal takes the lots in
def test_policy_order_decides_which_lot_is_sold(lots):
    create_trades(USD_ACC, [(T2, T2, A, 5, 80, 0, "buy-A-2"), (T3, T3, A, -3, 120, 0, "sell-A")])
    _rebuild(OtherPolicy())

    assert [x[1] for x in _closed(USD_ACC, A)] == [_oid(TRADE, 2)]       # the newest lot, not the first one
    _rebuild(JalPolicy())
    assert [x[1] for x in _closed(USD_ACC, A)] == [_oid(TRADE, 1)]
