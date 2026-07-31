from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_fifo
from tests.helpers import d2t, create_stocks, create_trades, create_quotes, create_conversions, symbol_id_for
from constants import AccountData, BookAccount, PredefinedCategory
from jal.db.ledger import Ledger, LedgerAmounts
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.operations import LedgerTransaction, LedgerError, LedgerAssetShortage
from jal.db.rebase_residue import RebaseResidue

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


# A lot's quantity is stored as 'remaining_qty' scaled by the adjustment 'c_qty', and 'c_qty' is the in/out ratio of
# the conversion that carried the lot over - a ratio of two arbitrary amounts, which is not representable exactly.
# The scaled quantities of the lots therefore no longer add up to the amount the ledger books hold, and a later
# conversion of the whole position used to find its lots a rounding crumb short and abort the ledger rebuild
# ("Processed asset amount is less than conversion amount"). Asking for more digits does not help - the drift stays
# at ~1E-24 whatever the precision - so a difference this small has to be read as "the same number".
# The numbers below are a real chain of conversions taken from a live database.
def test_conversion_absorbs_lot_adjustment_rounding(prepare_db_fifo):
    create_stocks([('USDT', 'Stablecoin'), ('aEthUSDT', 'Lending receipt')], currency_id=2)
    t1, t2, t3, t4 = d2t(220101), d2t(220201), d2t(220301), d2t(220401)
    create_trades(1, [(t1, t1, 4, Decimal('5089.698147'), Decimal('1'), Decimal('0')),
                      (t1, t1, 4, Decimal('2994.98'), Decimal('1'), Decimal('0'))])
    create_conversions(1, [(t1, 4, '5089.698147', 5, '5089.698146'),    # c_qty 0.999999999803524694172791776
                           (t2, 4, '2994.98', 5, '2999.321832'),        # c_qty 1.001449703169971084948814349
                           (t3, 5, '572.934836', 4, '585')])            # partial - leaves both adjusted lots in place
    # 5089.698146 + 2999.321832 - 572.934836 = 7516.085142 in the books, but the two adjusted lots sum to
    # 7516.085141999999999999999999 - the whole position is converted here and must not come up short
    create_conversions(1, [(t4, 5, '7516.085142', 4, '7549.608271')])
    Ledger().rebuild(from_timestamp=0)

    assert JalAccount(1).get_asset_amount(t4, 5) == Decimal('0')
    assert JalAccount(1).open_trades_list(JalAsset(5)) == []            # and no ~1E-25 dust lot is left behind
    assert JalAccount(1).closed_trades_list(close_otypes=_WITH_SWAP) == []


# An Aave aToken balance is a scaled number times the protocol's index, and the amount each Transfer event carries is
# re-derived from that ray math and truncates. The sum of every event a wallet ever saw is therefore a few units of
# the token's last decimal BELOW the balance the protocol really hands back, and a fetcher - which can only book what
# the chain emitted - is short by exactly that. Nothing shows it while the position is open; it surfaces on the
# "withdraw max" that closes the position, which burns the true balance. The ledger then stops on that conversion.
# The numbers are the real ones from a live database: aEthUSDG, 10 transfer events summing to 50246.880296 against a
# closing burn of 50246.880299 - a residue of 3 units of 1E-6, or 6E-11 of the position.
def test_conversion_stops_on_rebase_residue(prepare_db_fifo):
    JalAccount(1).set_data(AccountData.Precision, 18)   # every ledger posting is rounded to it
    create_stocks([('USDG', 'Stablecoin'), ('aEthUSDG', 'Lending receipt')], currency_id=2)
    t_buy, t_supply, t_exit = d2t(220101), d2t(220201), d2t(220301)
    create_trades(1, [(t_buy, t_buy, 4, Decimal('50246.880296'), Decimal('1'), Decimal('0'))])
    create_conversions(1, [(t_supply, 4, '50246.880296', 5, '50246.880296')])
    create_conversions(1, [(t_exit, 5, '50246.880299', 4, '50251.319007')])

    with pytest.raises(LedgerAssetShortage) as stop:
        Ledger().rebuild(from_timestamp=0)
    assert stop.value.shortage() == Decimal('0.000003')
    assert stop.value.symbol_id == symbol_id_for(5, 2)
    assert RebaseResidue().refusal_to_absorb(stop.value) == ''


# The residue is booked where the ledger found it, and booked at zero value: the quantity comes in free, so the
# position's cost basis is exactly what was paid for it and the per-unit basis of the units already held is untouched.
def test_rebase_residue_is_absorbed_at_zero_value(prepare_db_fifo):
    JalAccount(1).set_data(AccountData.Precision, 18)   # every ledger posting is rounded to it
    create_stocks([('USDG', 'Stablecoin'), ('aEthUSDG', 'Lending receipt')], currency_id=2)
    t_buy, t_supply, t_exit = d2t(220101), d2t(220201), d2t(220301)
    create_trades(1, [(t_buy, t_buy, 4, Decimal('50246.880296'), Decimal('1'), Decimal('0'))])
    create_conversions(1, [(t_supply, 4, '50246.880296', 5, '50246.880296')])
    create_conversions(1, [(t_exit, 5, '50246.880299', 4, '50251.319007')])
    with pytest.raises(LedgerAssetShortage) as stop:
        Ledger().rebuild(from_timestamp=0)
    assert RebaseResidue().absorb(stop.value)

    Ledger().rebuild(from_timestamp=0)                                  # completes now
    assert JalAccount(1).get_asset_amount(t_exit, 5) == Decimal('0')    # the whole position was converted
    assert JalAccount(1).get_asset_amount(t_exit, 4) == Decimal('50251.319007')
    values = LedgerAmounts("value_acc")
    # The crumb cost nothing, so what the USDG position is worth is still what was paid for the 50246.880296 bought
    assert values[(BookAccount.Assets, 1, 4)] == Decimal('50246.880296')
    assert values[(BookAccount.Incomes, 1, 2)] == Decimal('0')          # and it is not income either
    assert JalAccount(1).closed_trades_list(close_otypes=_WITH_SWAP) == []


# What keeps this from papering over a genuinely missing transaction: a shortage that is a quantity rather than a
# truncation crumb is refused and the ledger stays stopped, exactly as it did before any of this existed.
def test_real_shortage_is_not_absorbed_as_rebase_residue(prepare_db_fifo):
    JalAccount(1).set_data(AccountData.Precision, 18)   # every ledger posting is rounded to it
    create_stocks([('USDG', 'Stablecoin'), ('aEthUSDG', 'Lending receipt')], currency_id=2)
    t_buy, t_supply, t_exit = d2t(220101), d2t(220201), d2t(220301)
    create_trades(1, [(t_buy, t_buy, 4, Decimal('50246.880296'), Decimal('1'), Decimal('0'))])
    create_conversions(1, [(t_supply, 4, '50246.880296', 5, '50246.880296')])
    create_conversions(1, [(t_exit, 5, '50247', 4, '50251.319007')])    # 0.119704 missing - a supply never imported

    with pytest.raises(LedgerAssetShortage) as stop:
        Ledger().rebuild(from_timestamp=0)
    assert RebaseResidue().refusal_to_absorb(stop.value) != ''
    assert not RebaseResidue().absorb(stop.value)


# A residue that is negligible against the position but worth real money is refused as well: the relative bound alone
# would let it through on a big enough holding of a valuable token.
def test_valuable_rebase_residue_is_not_absorbed(prepare_db_fifo):
    JalAccount(1).set_data(AccountData.Precision, 18)   # every ledger posting is rounded to it
    create_stocks([('WBTC', 'Wrapped coin'), ('aEthWBTC', 'Lending receipt')], currency_id=2)
    t_buy, t_supply, t_exit = d2t(220101), d2t(220201), d2t(220301)
    create_quotes(5, 2, [(t_supply, 100000)])                           # a unit is worth 100k of the account currency
    create_trades(1, [(t_buy, t_buy, 4, Decimal('1000'), Decimal('1'), Decimal('0'))])
    create_conversions(1, [(t_supply, 4, '1000', 5, '1000')])
    create_conversions(1, [(t_exit, 5, '1000.0000009', 4, '1000')])     # 9E-7 of the position, but worth 0.09

    with pytest.raises(LedgerAssetShortage) as stop:
        Ledger().rebuild(from_timestamp=0)
    assert stop.value.shortage() == Decimal('0.0000009')                # inside the relative bound...
    assert RebaseResidue().refusal_to_absorb(stop.value) != ''          # ...but not inside the value one


# Every ledger posting is rounded to the account's precision, so a residue finer than that would be booked as a zero
# and leave the shortage exactly where it was - and the rebuild would come back to it forever. Refused instead: such
# an account is simply too coarse for the asset it holds.
def test_rebase_residue_finer_than_account_precision_is_refused(prepare_db_fifo):
    create_stocks([('USDG', 'Stablecoin'), ('aEthUSDG', 'Lending receipt')], currency_id=2)
    t_buy, t_supply, t_exit = d2t(220101), d2t(220201), d2t(220301)   # account precision left at the default of 2
    create_trades(1, [(t_buy, t_buy, 4, Decimal('50246.88'), Decimal('1'), Decimal('0'))])
    create_conversions(1, [(t_supply, 4, '50246.88', 5, '50246.88')])
    create_conversions(1, [(t_exit, 5, '50246.880003', 4, '50251.319007')])

    with pytest.raises(LedgerAssetShortage) as stop:
        Ledger().rebuild(from_timestamp=0)
    assert RebaseResidue().refusal_to_absorb(stop.value) != ''
    assert not RebaseResidue().absorb(stop.value)
