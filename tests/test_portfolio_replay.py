from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, create_stocks, create_trades, create_transfers, create_corporate_actions
from tests.test_lot_replay import OPENED, CLOSED, _rows
from jal.constants import PredefinedAccountType, PredefinedCategory
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.asset import JalAsset
from jal.db.basis_policy import JalPolicy
from jal.db.db import JalDB
from jal.db.ledger import Ledger
from jal.db.lots import ScratchLotStore, replay
from jal.db.operations import CorporateAction
from jal.db.portfolio import JalPortfolio, PortfolioPolicy
from tests.helpers import create_actions

ACC1, ACC2 = 1, 2
S, T = 4, 5
T1, T2, T3, T4 = d2t(220101), d2t(220201), d2t(220301), d2t(220401)


# Two USD accounts, stocks S and T; 10 S bought at 100 on T1 and 5 S at 110 on T2, both on account 1
@pytest.fixture
def two_lots(prepare_db):
    for name in ('Acc 1', 'Acc 2'):
        JalAccountCreator(currency_id=2, number='', name=name, investing=1, organization=1,
                          account_type=PredefinedAccountType.Broker).commit()
    create_actions([(T1 - 1, ACC1, 1, [(PredefinedCategory.StartingBalance, 10000.0)])])
    create_stocks([('S', 'Stock S'), ('T', 'Stock T')], currency_id=2)
    create_trades(ACC1, [(T1, T1, S, 10.0, 100.0, 0.0), (T2, T2, S, 5.0, 110.0, 0.0)])
    yield


def _tag(name) -> int:
    return JalDB._read("SELECT id FROM tags WHERE tag=:tag", [(":tag", name)])


def _trade(timestamp) -> int:
    return JalDB._read("SELECT oid FROM trades WHERE timestamp=:ts", [(":ts", timestamp)])


# Portfolio A owns the first buy, B the second
def _assign_buys():
    JalPortfolio.assign(_trade(T1), _tag('Cash'))
    JalPortfolio.assign(_trade(T2), _tag('Card'))
    return _tag('Cash'), _tag('Card')


# The portfolio replay of the built ledger: ({(account, asset): [(portfolio, adjusted price, qty)]}, deals) where
# deals are (open_oid, open_price, close_qty) in the order they were written
def _replay(positions):
    Ledger().rebuild(from_timestamp=0)
    store = ScratchLotStore()
    try:
        portfolio = JalPortfolio()
        replay(store, PortfolioPolicy(JalPolicy(), portfolio))
        held = {}
        for account_id, asset_id in positions:
            lots = JalAccount(account_id).open_trades_list(JalAsset(asset_id), store=store)
            held[(account_id, asset_id)] = [(portfolio.of_lot(x), x.open_price(adjusted=True), x.open_qty())
                                            for x in lots]
        deals = JalDB._read_to_list(f"SELECT open_oid, open_price, close_qty FROM {store.schema()}.trades_closed "
                                    "ORDER BY id")
        return held, [(int(x[0]), Decimal(x[1]), Decimal(x[2])) for x in deals]
    finally:
        store.detach()


def test_a_sale_takes_its_own_portfolio_first(two_lots):
    a, b = _assign_buys()
    create_trades(ACC1, [(T3, T3, S, -5.0, 120.0, 0.0)])
    JalPortfolio.assign(_trade(T3), b)
    held, deals = _replay([(ACC1, S)])
    assert deals == [(_trade(T2), Decimal('110'), Decimal('5'))]
    assert held[(ACC1, S)] == [(a, Decimal('100'), Decimal('10'))]


def test_a_sale_larger_than_its_portfolio_spills_in_fifo_order(two_lots):
    a, b = _assign_buys()
    create_trades(ACC1, [(T3, T3, S, -8.0, 120.0, 0.0)])
    JalPortfolio.assign(_trade(T3), b)
    held, deals = _replay([(ACC1, S)])
    assert deals == [(_trade(T2), Decimal('110'), Decimal('5')), (_trade(T1), Decimal('100'), Decimal('3'))]
    assert held[(ACC1, S)] == [(a, Decimal('100'), Decimal('7'))]


def test_an_untagged_sale_is_plain_fifo(two_lots):
    a, b = _assign_buys()
    create_trades(ACC1, [(T3, T3, S, -8.0, 120.0, 0.0)])
    held, deals = _replay([(ACC1, S)])
    assert deals == [(_trade(T1), Decimal('100'), Decimal('8'))]
    assert held[(ACC1, S)] == [(a, Decimal('100'), Decimal('2')), (b, Decimal('110'), Decimal('5'))]


# With no tagged disposal the wrapper is neutral: the portfolio replay writes what the rebuild wrote, row for row
def test_without_tagged_disposals_the_replay_equals_the_ledger(two_lots):
    _assign_buys()
    create_trades(ACC1, [(T3, T3, S, -8.0, 120.0, 0.0)])
    create_transfers([(T4, ACC1, 4, ACC2, 4, S)])
    Ledger().rebuild(from_timestamp=0)
    store = ScratchLotStore()
    try:
        replay(store, PortfolioPolicy(JalPolicy(), JalPortfolio()))
        assert _rows('trades_opened', OPENED, store.schema()) == _rows('trades_opened', OPENED)
        assert _rows('trades_closed', CLOSED, store.schema()) == _rows('trades_closed', CLOSED)
    finally:
        store.detach()


def test_a_tagged_transfer_moves_its_portfolio_and_the_lots_keep_it(two_lots):
    a, b = _assign_buys()
    transfer = create_transfers([(T3, ACC1, 5, ACC2, 5, S)])[0]
    JalPortfolio.assign(transfer, b)
    held, _ = _replay([(ACC1, S), (ACC2, S)])
    assert held[(ACC1, S)] == [(a, Decimal('100'), Decimal('10'))]
    assert held[(ACC2, S)] == [(b, Decimal('110'), Decimal('5'))]


def test_a_split_keeps_the_portfolio(two_lots):
    a, b = _assign_buys()
    create_corporate_actions(ACC1, [(T3, CorporateAction.Split, S, 15, 'split', [(S, 30, 1.0)])])
    create_trades(ACC1, [(T4, T4, S, -10.0, 60.0, 0.0)])
    JalPortfolio.assign(_trade(T4), b)
    held, _ = _replay([(ACC1, S)])
    assert held[(ACC1, S)] == [(a, Decimal('50'), Decimal('20'))]


def test_a_spin_off_result_keeps_the_portfolio(two_lots):
    a, b = _assign_buys()
    create_corporate_actions(ACC1, [(T3, CorporateAction.SpinOff, S, 15, 'spin-off', [(S, 15, 0.8), (T, 30, 0.2)])])
    held, _ = _replay([(ACC1, S), (ACC1, T)])
    assert held[(ACC1, S)] == [(a, Decimal('80'), Decimal('10')), (b, Decimal('88'), Decimal('5'))]
    assert held[(ACC1, T)] == [(a, Decimal('10'), Decimal('20')), (b, Decimal('11'), Decimal('10'))]


# A short belongs to no portfolio; the buy that covers it closes it and opens the rest in its own portfolio
def test_a_short_is_unassigned_and_the_covering_buy_opens_the_rest(prepare_db):
    JalAccountCreator(currency_id=2, number='', name='Acc 1', investing=1, organization=1,
                      account_type=PredefinedAccountType.Broker).commit()
    create_actions([(T1 - 1, ACC1, 1, [(PredefinedCategory.StartingBalance, 10000.0)])])
    create_stocks([('S', 'Stock S')], currency_id=2)
    create_trades(ACC1, [(T1, T1, S, -10.0, 100.0, 0.0), (T2, T2, S, 15.0, 90.0, 0.0)])
    b = _tag('Card')
    JalPortfolio.assign(_trade(T1), b)
    JalPortfolio.assign(_trade(T2), b)
    held, deals = _replay([(ACC1, S)])
    assert deals == [(_trade(T1), Decimal('100'), Decimal('-10'))]
    assert held[(ACC1, S)] == [(b, Decimal('90'), Decimal('5'))]
