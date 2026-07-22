from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_fifo
from tests.helpers import d2t, create_stocks, create_trades, create_quotes, create_conversions
from constants import BookAccount, PredefinedCategory
from jal.db.ledger import Ledger, LedgerAmounts
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.operations import LedgerTransaction, LedgerError

_WITH_SWAP = (LedgerTransaction.Trade, LedgerTransaction.Swap)   # what the Deals report asks for


# A conversion is not a disposal: the position keeps its cost basis and no profit or loss is realized, even though
# the quantity changes (a rebasing receipt token folds the accrued yield into what it mints).
def test_conversion_keeps_basis_and_realizes_nothing(prepare_db_fifo):
    create_stocks([('USDG', 'Stablecoin'), ('aUSDG', 'Lending receipt')], currency_id=2)   # -> assets 4 and 5
    t_buy, t_convert = d2t(220101), d2t(220201)
    create_trades(1, [(t_buy, t_buy, 4, 30.0, 1.0, 0.0)])                # buy 30 USDG @ 1 -> basis 30
    create_conversions(1, [(t_convert, 4, 30, 5, 37)])                   # supply 30 USDG, receive 37 aUSDG
    Ledger().rebuild(from_timestamp=0)

    assert JalAccount(1).get_asset_amount(t_convert, 4) == Decimal('0')
    assert JalAccount(1).get_asset_amount(t_convert, 5) == Decimal('37')

    # The whole basis moved across, so the position is still worth exactly what was paid for it
    values = LedgerAmounts("value_acc")
    assert values[(BookAccount.Assets, 1, 5)] == Decimal('30')
    # ... and the extra 7 units are NOT income: nothing was booked to the Incomes book
    assert values[(BookAccount.Incomes, 1, 2)] == Decimal('0')
    # ... and no deal was realized, in the tax path or the Deals report
    assert JalAccount(1).closed_trades_list() == []
    assert JalAccount(1).closed_trades_list(close_otypes=_WITH_SWAP) == []


# The lots survive the conversion: each keeps the operation that opened it (and therefore its acquisition date),
# re-scaled so that its value is unchanged. That is what a future holding-period rule needs to stay correct.
def test_conversion_carries_lots_over(prepare_db_fifo):
    create_stocks([('ETH', 'Coin'), ('WETH', 'Wrapped coin')], currency_id=2)
    t_first, t_second, t_convert = d2t(220101), d2t(220115), d2t(220201)
    create_trades(1, [(t_first, t_first, 4, 1.0, 100.0, 0.0)])           # lot 1: 1 ETH @ 100
    create_trades(1, [(t_second, t_second, 4, 1.0, 300.0, 0.0)])         # lot 2: 1 ETH @ 300
    create_conversions(1, [(t_convert, 4, 2, 5, 2)])                     # wrap both, 1:1
    Ledger().rebuild(from_timestamp=0)

    lots = JalAccount(1).open_trades_list(JalAsset(5))
    assert len(lots) == 2                                                # two lots, not one merged position
    assert [x.open_qty(adjusted=True) for x in lots] == [Decimal('1'), Decimal('1')]
    assert [x.open_price(adjusted=True) for x in lots] == [Decimal('100'), Decimal('300')]
    # Both still point at the trades that acquired them, in acquisition order
    assert [x.open_operation().timestamp() for x in lots] == [t_first, t_second]


# A conversion of part of the position leaves the rest of it alone, still at its own basis.
def test_partial_conversion_leaves_the_rest(prepare_db_fifo):
    create_stocks([('ETH', 'Coin'), ('WETH', 'Wrapped coin')], currency_id=2)
    t_buy, t_convert = d2t(220101), d2t(220201)
    create_trades(1, [(t_buy, t_buy, 4, 10.0, 50.0, 0.0)])               # 10 ETH @ 50 -> basis 500
    create_conversions(1, [(t_convert, 4, 4, 5, 4)])                     # wrap 4 of them
    Ledger().rebuild(from_timestamp=0)

    assert JalAccount(1).get_asset_amount(t_convert, 4) == Decimal('6')
    assert JalAccount(1).get_asset_amount(t_convert, 5) == Decimal('4')
    values = LedgerAmounts("value_acc")
    assert values[(BookAccount.Assets, 1, 4)] == Decimal('300')          # 6 * 50 stays behind
    assert values[(BookAccount.Assets, 1, 5)] == Decimal('200')          # 4 * 50 moved across


# Unwrapping is the same operation the other way round and has to return the position to its original basis.
def test_conversion_round_trip_restores_basis(prepare_db_fifo):
    create_stocks([('ETH', 'Coin'), ('WETH', 'Wrapped coin')], currency_id=2)
    t_buy, t_wrap, t_unwrap = d2t(220101), d2t(220201), d2t(220301)
    create_trades(1, [(t_buy, t_buy, 4, 2.0, 150.0, 0.0)])               # 2 ETH @ 150 -> basis 300
    create_conversions(1, [(t_wrap, 4, 2, 5, 2), (t_unwrap, 5, 2, 4, 2)])
    Ledger().rebuild(from_timestamp=0)

    assert JalAccount(1).get_asset_amount(t_unwrap, 5) == Decimal('0')
    lots = JalAccount(1).open_trades_list(JalAsset(4))
    assert len(lots) == 1
    assert lots[0].open_qty(adjusted=True) == Decimal('2')
    assert lots[0].open_price(adjusted=True) == Decimal('150')
    assert JalAccount(1).closed_trades_list(close_otypes=_WITH_SWAP) == []


# Gas is disposed at its own cost basis to Costs/Fees - no profit or loss on the coins spent on it, exactly the
# treatment a swap and a bridge give their gas.
def test_conversion_fee_is_disposed_to_costs(prepare_db_fifo):
    create_stocks([('ETH', 'Coin'), ('WETH', 'Wrapped coin'), ('GAS', 'Native coin')], currency_id=2)  # GAS -> 6
    t_buy, t_convert = d2t(220101), d2t(220201)
    create_trades(1, [(t_buy, t_buy, 4, 2.0, 150.0, 0.0)])
    create_trades(1, [(t_buy, t_buy, 6, 1.0, 10.0, 0.0)])                # hold 1 GAS @ 10
    create_conversions(1, [(t_convert, 4, 2, 5, 2, 6, Decimal('0.5'))])  # 0.5 GAS of gas
    Ledger().rebuild(from_timestamp=0)

    assert JalAccount(1).get_asset_amount(t_convert, 6) == Decimal('0.5')
    costs = JalAccount(1).get_category_turnover(PredefinedCategory.Fees, 0, d2t(220301))
    assert costs == Decimal('5')                                         # 0.5 * 10, the gas at its own basis
    assert JalAccount(1).closed_trades_list(close_otypes=_WITH_SWAP) == []   # gas realizes nothing either


# Converting more than the account holds is an error, not a silently negative position.
def test_conversion_refuses_more_than_available(prepare_db_fifo):
    create_stocks([('ETH', 'Coin'), ('WETH', 'Wrapped coin')], currency_id=2)
    t_buy, t_convert = d2t(220101), d2t(220201)
    create_trades(1, [(t_buy, t_buy, 4, 1.0, 100.0, 0.0)])
    create_conversions(1, [(t_convert, 4, 2, 5, 2)])
    with pytest.raises(LedgerError):
        Ledger().rebuild(from_timestamp=0)


# An asset can't be converted into itself - that describes nothing and would consume the position it re-opens.
def test_conversion_refuses_same_asset(prepare_db_fifo):
    create_stocks([('ETH', 'Coin')], currency_id=2)
    t_buy, t_convert = d2t(220101), d2t(220201)
    create_trades(1, [(t_buy, t_buy, 4, 2.0, 100.0, 0.0)])
    create_conversions(1, [(t_convert, 4, 1, 4, 1)])
    with pytest.raises(LedgerError):
        Ledger().rebuild(from_timestamp=0)


# A conversion is priced by whatever the position cost, not by the market: a quote that appeared meanwhile must not
# leak into the books as a gain.
def test_conversion_ignores_market_quotes(prepare_db_fifo):
    create_stocks([('ETH', 'Coin'), ('WETH', 'Wrapped coin')], currency_id=2)
    t_buy, t_convert = d2t(220101), d2t(220201)
    create_quotes(4, 2, [(t_convert, 999.0)])                            # the coin tripled since it was bought
    create_trades(1, [(t_buy, t_buy, 4, 2.0, 150.0, 0.0)])
    create_conversions(1, [(t_convert, 4, 2, 5, 2)])
    Ledger().rebuild(from_timestamp=0)

    values = LedgerAmounts("value_acc")
    assert values[(BookAccount.Assets, 1, 5)] == Decimal('300')          # the basis, not 2 * 999
    assert JalAccount(1).closed_trades_list(close_otypes=_WITH_SWAP) == []
