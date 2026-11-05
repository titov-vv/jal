from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import create_quotes, create_trades, create_swaps, create_conversions, create_corporate_actions
from tests.test_lot_decisions import lots, USD_ACC, A, B, S, T, T1, T2, T3, TRADE, SWAP, CONV
from jal.constants import SwapTreatment
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.symbol import JalSymbol
from jal.db.basis_policy import Basis, Clock, Treatment, JalPolicy
from jal.db.ledger import Ledger
from jal.db.lots import LedgerLotStore, LotEngine, ScratchLotStore, replay
from jal.db.operations import LedgerTransaction, LedgerError, CorporateAction

ACTION = LedgerTransaction.CorporateAction


# A policy that disposes of every exchange, at 'values' {otype: total} where given, else at the market;
# a corporate action result into T is realized at 'result_value'
class DisposingPolicy(JalPolicy):
    def __init__(self, values=None, result_value=None):
        self.values = values or {}
        self.result_value = result_value

    def treatment(self, operation) -> Treatment:
        return Treatment(Basis.DISPOSAL, Clock.RESTART, value=self.values.get(operation.type()))

    def action_result(self, action, result: dict) -> Treatment:
        treatment = super().action_result(action, result)
        if self.result_value is None or JalSymbol(result['symbol_id']).asset().id() != T:
            return treatment
        return Treatment(Basis.DISPOSAL, Clock.RESTART, treatment.share, self.result_value)


@pytest.fixture
def scratch():
    store = ScratchLotStore()
    yield store
    store.detach()


# The ledger built by JAL's rules, then its lots replayed by 'policy'
def _replay(store, policy):
    Ledger().rebuild(from_timestamp=0)
    replay(store, policy)


def _deals(store, asset_id, otypes, realized=False) -> list:
    return [(x.close_operation().type(), x.qty(), x.close_price(), round(x.profit(), 6)) for x in
            JalAccount(USD_ACC).closed_trades_list(JalAsset(asset_id), otypes, store=store, realized=realized)]


def _lots(store, asset_id) -> list:
    return [(x.open_operation().type(), x.open_qty(), x.open_price(adjusted=True), x.acquired()) for x in
            LotEngine(store).lots(JalAccount(USD_ACC), JalAsset(asset_id))]


# A wrapping disposed of at the market: the out asset's quote, else the in asset's; neither stops the replay
def test_conversion_disposal_at_market(lots, scratch):
    create_quotes(A, 2, [(T2, 120)])
    create_conversions(USD_ACC, [(T2, A, 10, B, 20)])
    _replay(scratch, DisposingPolicy())
    assert _deals(scratch, A, (CONV,)) == [(CONV, Decimal('10'), Decimal('120'), Decimal('190'))]   # 1200-1000-10
    assert _lots(scratch, B) == [(CONV, Decimal('20'), Decimal('60'), T2)]


def test_conversion_disposal_at_the_in_asset_quote(lots, scratch):
    create_quotes(B, 2, [(T2, 55)])
    create_conversions(USD_ACC, [(T2, A, 10, B, 20)])
    _replay(scratch, DisposingPolicy())
    assert _deals(scratch, A, (CONV,)) == [(CONV, Decimal('10'), Decimal('110'), Decimal('90'))]
    assert _lots(scratch, B) == [(CONV, Decimal('20'), Decimal('55'), T2)]


def test_conversion_disposal_without_quotes(lots, scratch):
    create_conversions(USD_ACC, [(T2, A, 10, B, 20)])
    with pytest.raises(LedgerError, match="no quotes to value the wrapping"):
        _replay(scratch, DisposingPolicy())


# The policy's value replaces the market's, for a wrapping and for a swap
@pytest.mark.parametrize("create, otype", [(lambda: create_conversions(USD_ACC, [(T2, A, 10, B, 20)]), CONV),
                                           (lambda: create_swaps(USD_ACC, [(T2, A, 10, B, 20)],
                                                                 treatment=SwapTreatment.Conversion), SWAP)])
def test_disposal_at_the_policy_value(lots, scratch, create, otype):
    create_quotes(A, 2, [(T2, 120)])
    create()
    _replay(scratch, DisposingPolicy(values={otype: Decimal('1500')}))
    assert _deals(scratch, A, (otype,)) == [(otype, Decimal('10'), Decimal('150'), Decimal('490'))]
    assert _lots(scratch, B) == [(otype, Decimal('20'), Decimal('75'), T2)]


# A merger result realized at a value: its share of each lot sold, the received asset opened at that value, the
# other result carried as JAL carries it, and the carry records of the action left as they are
def test_corporate_action_result_realized(lots, scratch):
    create_trades(USD_ACC, [(T1, T1, S, 60, 30, 0, "buy-S-1"), (T1 + 60, T1 + 60, S, 40, 35, 0, "buy-S-2")])
    create_corporate_actions(USD_ACC, [(T2, CorporateAction.Merger, S, 100, "S -> S + T",
                                        [(S, 100, 0.2), (T, 50, 0.8, True)])])
    create_trades(USD_ACC, [(T3, T3, T, -50, 70, 0, "sell-T")])
    _replay(scratch, DisposingPolicy(result_value=Decimal('2560')))

    # 50 T allocated 30 / 20 over the lots: worth 1536 / 1024 against 0.8 of their 1800 / 1400 cost
    assert _deals(scratch, S, (ACTION,), realized=True) == [
        (ACTION, Decimal('60'), Decimal('25.6'), Decimal('96')), (ACTION, Decimal('40'), Decimal('25.6'), Decimal('-96'))]
    assert [x[:2] for x in _deals(scratch, S, (ACTION,))] == [(ACTION, Decimal('60')), (ACTION, Decimal('40'))]
    assert _lots(scratch, S) == [(TRADE, Decimal('60'), Decimal('6'), T1), (TRADE, Decimal('40'), Decimal('7'), T1 + 60)]
    assert _deals(scratch, T, (TRADE,)) == [(TRADE, Decimal('50'), Decimal('70'), Decimal('940'))]   # 3500-2560
    deal, = JalAccount(USD_ACC).closed_trades_list(JalAsset(T), (TRADE,), store=scratch)
    assert (deal.open_operation().type(), deal.acquired()) == (ACTION, T2)


def test_corporate_action_result_needs_a_value(lots, scratch):
    class NoValue(JalPolicy):
        def action_result(self, action, result: dict) -> Treatment:
            return Treatment(Basis.DISPOSAL, Clock.RESTART, Decimal(result['value_share']))

    create_trades(USD_ACC, [(T1, T1, S, 100, 30, 0, "buy-S")])
    create_corporate_actions(USD_ACC, [(T2, CorporateAction.Merger, S, 100, "S -> T", [(T, 50, 1.0)])])
    with pytest.raises(ValueError, match="without a value"):
        _replay(scratch, NoValue())


# The ledger's own store keeps no realized deals
def test_ledger_store_has_no_realized_deals(lots):
    store = LedgerLotStore()
    assert store.deals(USD_ACC, None, (TRADE, ACTION), realized=True) == []
    with pytest.raises(ValueError, match="no realized deals"):
        store.close(USD_ACC, A, TRADE, 1, T1, Decimal('1'), Decimal('1'), ACTION, 1, T2, Decimal('1'), Decimal('1'),
                    Decimal('1'), Decimal('1'), Decimal('1'), realized=True)
