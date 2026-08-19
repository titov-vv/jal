from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_fifo
from tests.helpers import d2t, create_stocks, create_trades, create_quotes, create_conversions, symbol_id_for
from constants import AccountData, BookAccount, PredefinedCategory
from jal.db.ledger import Ledger, LedgerAmounts
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.operations import LedgerTransaction, LedgerError, LedgerAssetShortage
from jal.db.db import JalDB
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


# ----------------------------------------------------------------------------------------------------------------------
# COMPLETING A HALTED LEDGER. Booking the residue is only half of it: the halt is where the numbers are, so the pass
# rebuilds, reads what it stopped on, books it and rebuilds again - which is what turns a stopped ledger back into a
# complete one, whatever route stopped it.
def test_a_halted_ledger_is_completed_by_absorbing_its_residues(prepare_db_fifo):
    JalAccount(1).set_data(AccountData.Precision, 18)   # every ledger posting is rounded to it
    create_stocks([('USDG', 'Stablecoin'), ('aEthUSDG', 'Lending receipt')], currency_id=2)
    t_buy, t_supply, t_exit = d2t(220101), d2t(220201), d2t(220301)
    create_trades(1, [(t_buy, t_buy, 4, Decimal('50246.880296'), Decimal('1'), Decimal('0'))])
    create_conversions(1, [(t_supply, 4, '50246.880296', 5, '50246.880296')])
    create_conversions(1, [(t_exit, 5, '50246.880299', 4, '50251.319007')])
    ledger = Ledger()
    with pytest.raises(LedgerAssetShortage):
        ledger.rebuild(from_timestamp=0)

    assert ledger.absorb_residues() == 1
    assert ledger.stopped_by is None                                    # the rebuild after it ran to the end
    assert JalAccount(1).get_asset_amount(t_exit, 5) == Decimal('0')    # the whole position was converted
    assert JalAccount(1).get_asset_amount(t_exit, 4) == Decimal('50251.319007')


# A shortage the reconciler refuses ends the pass instead of being worked around: the ledger stays exactly where it
# stopped and nothing is written, which is what a missed transaction has to look like.
def test_a_shortage_that_is_no_residue_leaves_the_ledger_stopped(prepare_db_fifo):
    JalAccount(1).set_data(AccountData.Precision, 18)   # every ledger posting is rounded to it
    create_stocks([('USDG', 'Stablecoin'), ('aEthUSDG', 'Lending receipt')], currency_id=2)
    t_buy, t_supply, t_exit = d2t(220101), d2t(220201), d2t(220301)
    create_trades(1, [(t_buy, t_buy, 4, Decimal('50246.880296'), Decimal('1'), Decimal('0'))])
    create_conversions(1, [(t_supply, 4, '50246.880296', 5, '50246.880296')])
    create_conversions(1, [(t_exit, 5, '50247', 4, '50251.319007')])    # 0.119704 missing - a supply never imported
    ledger = Ledger()
    with pytest.raises(LedgerAssetShortage):
        ledger.rebuild(from_timestamp=0)

    assert ledger.absorb_residues() == 0
    assert isinstance(ledger.stopped_by, LedgerAssetShortage)
    assert JalDB._read("SELECT COUNT(*) FROM asset_payments") == 0


# A stop is taken between the passes, each of which is a full rebuild, and leaves the books as they were
def test_a_stop_ends_the_absorption_before_anything_is_booked(prepare_db_fifo):
    JalAccount(1).set_data(AccountData.Precision, 18)   # every ledger posting is rounded to it
    create_stocks([('USDG', 'Stablecoin'), ('aEthUSDG', 'Lending receipt')], currency_id=2)
    t_buy, t_supply, t_exit = d2t(220101), d2t(220201), d2t(220301)
    create_trades(1, [(t_buy, t_buy, 4, Decimal('50246.880296'), Decimal('1'), Decimal('0'))])
    create_conversions(1, [(t_supply, 4, '50246.880296', 5, '50246.880296')])
    create_conversions(1, [(t_exit, 5, '50246.880299', 4, '50251.319007')])

    assert Ledger().absorb_residues(interrupted=lambda: True) == 0
    assert JalDB._read("SELECT COUNT(*) FROM asset_payments") == 0


# ----------------------------------------------------------------------------------------------------------------------
# REALIZING ACCRUED INTEREST. A rebasing position also earns real interest, and unlike the truncation crumb above it
# is a quantity of real value: the position these figures come from had booked 7637.22561 aEthUSDG against 7810.33702
# really held on chain - 2.27%, and $173. Nothing about its SIZE distinguishes that from a transaction that was
# missed, which is why it is not a heuristic that decides but an independent measurement of what the chain holds.
#
# It is unrealized while the position is open and is recognized only when a withdrawal turns it into something the
# wallet actually received - one operation per position lifetime, valued at the market of that day.
_LEDGER_QTY = Decimal('7637.22561')          # what the books hold after supplying
_CHAIN_QTY = Decimal('7810.33702')           # what the chain says is really there
_ACCRUED = _CHAIN_QTY - _LEDGER_QTY          # 173.11141


# Builds the position and stops the ledger on a withdrawal of 'withdrawn'. 'measured' is what the chain was last seen
# holding - None when it was never read.
def _rebasing_position(withdrawn, measured=_CHAIN_QTY):
    from jal.db.chain_balance import JalChainBalance
    from jal.constants import AssetData
    from jal.db.db import JalDB
    JalAccount(1).set_data(AccountData.Precision, 18)
    create_stocks([('USDG', 'Stablecoin'), ('aEthUSDG', 'Lending receipt')], currency_id=2)
    t_buy, t_supply, t_exit = d2t(220101), d2t(220201), d2t(220301)
    create_trades(1, [(t_buy, t_buy, 4, _LEDGER_QTY, Decimal('1'), Decimal('0'))])
    create_conversions(1, [(t_supply, 4, str(_LEDGER_QTY), 5, str(_LEDGER_QTY))])
    create_conversions(1, [(t_exit, 5, str(withdrawn), 4, str(withdrawn))])
    create_quotes(5, 2, [(t_buy, Decimal('1')), (t_exit, Decimal('1'))])   # a reward has to be priced to be booked
    # Only a token whose quantity can grow on its own may have a shortage explained as interest
    JalDB()._exec("INSERT OR REPLACE INTO asset_data(asset_id, datatype, value) VALUES(5, :dt, '1')",
                  [(":dt", AssetData.Rebasing)], commit=True)
    JalAsset(5).invalidate_cache()
    if measured is not None:
        JalChainBalance().store(d2t(220401), 1, 5, measured)
    return t_exit


# CASE 1 - the withdrawal fits inside what the books hold. There is no shortage, the ledger never stops, and the
# interest stays unrealized and still in the position, which is exactly right: nothing has been taken out of it.
def test_a_withdrawal_within_the_books_realizes_nothing(prepare_db_fifo):
    from jal.db.chain_balance import JalChainBalance
    t_exit = _rebasing_position(Decimal('3000'))
    Ledger().rebuild(from_timestamp=0)                                  # completes, no shortage

    assert JalAccount(1).get_asset_amount(t_exit, 5) == _LEDGER_QTY - Decimal('3000')
    # The measurement survives untouched - the accrual is still there and still unrealized
    assert JalChainBalance().latest(1, 5, d2t(220501))['amount'] == _CHAIN_QTY


# CASE 2 - the withdrawal digs into the accrual without closing the position. The WHOLE tracked delta is recognized,
# not just the part that was missing: booking only the shortage would empty the books while the chain still held a
# remainder, and a ledger-driven portfolio would drop that remainder out of sight.
def test_a_withdrawal_beyond_the_books_realizes_the_whole_accrual(prepare_db_fifo):
    from jal.db.chain_balance import JalChainBalance
    t_exit = _rebasing_position(Decimal('7700'))

    with pytest.raises(LedgerAssetShortage) as stop:
        Ledger().rebuild(from_timestamp=0)
    assert stop.value.shortage() == Decimal('7700') - _LEDGER_QTY       # 62.77439, far past any crumb
    assert RebaseResidue().refusal_to_absorb(stop.value) != ''          # not a rounding residue...
    assert RebaseResidue().refusal_to_realize(stop.value) == ''         # ...but it is accrued interest
    assert RebaseResidue().absorb(stop.value)

    Ledger().rebuild(from_timestamp=0)                                  # completes now
    # 7637.22561 + 173.11141 - 7700 = 110.33702, and the chain agrees - no orphaned remainder
    assert JalAccount(1).get_asset_amount(t_exit, 5) == _CHAIN_QTY - Decimal('7700')
    # The spent measurement is forgotten: compared against books that have just risen by the whole delta it would
    # report the withdrawn quantity as a fresh accrual and recognize it a second time.
    assert JalChainBalance().latest(1, 5, d2t(220501)) is None


# The accrual is INCOME and is booked as one - valued at the market of the day, opening a lot at that basis. That is
# the opposite of the truncation crumb, which comes in free precisely so that it moves no basis.
def test_the_realized_accrual_is_income_at_market_value(prepare_db_fifo):
    t_exit = _rebasing_position(Decimal('7700'))
    with pytest.raises(LedgerAssetShortage) as stop:
        Ledger().rebuild(from_timestamp=0)
    RebaseResidue().absorb(stop.value)
    Ledger().rebuild(from_timestamp=0)

    payments = JalDB()._read_to_list(
        "SELECT type, amount FROM asset_payments WHERE account_id=1 AND symbol_id=:s",
        [(":s", symbol_id_for(5, 2))], named=True)
    assert len(payments) == 1
    assert int(payments[0]['type']) == 8                                # AssetPayment.StakingReward
    assert Decimal(payments[0]['amount']) == _ACCRUED
    # ...and it carried VALUE into the position. The ledger posting of a rebase crumb is worth exactly zero; this one
    # is worth the accrued quantity at the market of the day, which is what makes it income rather than a correction.
    booked = JalDB()._read_to_list(
        "SELECT amount, value FROM ledger WHERE otype=2 AND account_id=1 AND asset_id=5 AND book_account=:assets",
        [(":assets", BookAccount.Assets)], named=True)
    assert len(booked) == 1
    assert Decimal(booked[0]['amount']) == _ACCRUED
    assert Decimal(booked[0]['value']) == _ACCRUED * Decimal('1')


# CASE 3 - the full close. Everything the chain holds comes out, so the whole accrual is realized and the position
# ends at exactly zero on both sides.
def test_a_full_close_realizes_the_accrual_and_empties_the_position(prepare_db_fifo):
    t_exit = _rebasing_position(_CHAIN_QTY)

    with pytest.raises(LedgerAssetShortage) as stop:
        Ledger().rebuild(from_timestamp=0)
    assert stop.value.shortage() == _ACCRUED
    assert RebaseResidue().absorb(stop.value)

    Ledger().rebuild(from_timestamp=0)
    assert JalAccount(1).get_asset_amount(t_exit, 5) == Decimal('0')
    assert JalAccount(1).open_trades_list(JalAsset(5)) == []            # nothing left behind


# CASE 4 - THE GUARD. A withdrawal asking for more than the chain was ever seen holding is not accrual: it is a
# movement that was missed, and it must still stop the ledger dead. This is the case a size-and-value heuristic
# cannot judge - 173 of interest and 200 of a missed transfer look alike by every measure except this one.
def test_a_shortage_beyond_the_measured_balance_still_halts(prepare_db_fifo):
    _rebasing_position(_CHAIN_QTY + Decimal('100'))

    with pytest.raises(LedgerAssetShortage) as stop:
        Ledger().rebuild(from_timestamp=0)
    assert RebaseResidue().refusal_to_realize(stop.value) != ''
    assert not RebaseResidue().absorb(stop.value)

    with pytest.raises(LedgerAssetShortage):                            # and it stays stopped
        Ledger().rebuild(from_timestamp=0)


# Without a measurement there is nothing to judge the shortage against, so it is refused. An unread position behaves
# exactly as it did before any of this existed.
def test_an_unmeasured_position_is_never_absorbed(prepare_db_fifo):
    _rebasing_position(Decimal('7700'), measured=None)

    with pytest.raises(LedgerAssetShortage) as stop:
        Ledger().rebuild(from_timestamp=0)
    assert RebaseResidue().refusal_to_realize(stop.value) != ''
    assert not RebaseResidue().absorb(stop.value)


# The flag is the licence. On an ordinary token a shortage means a movement was missed - which is what the ledger
# stopping is FOR - and no measurement may explain it away.
def test_an_unflagged_asset_is_never_absorbed_as_accrual(prepare_db_fifo):
    from jal.db.chain_balance import JalChainBalance
    from jal.constants import AssetData
    _rebasing_position(Decimal('7700'))
    JalDB()._exec("DELETE FROM asset_data WHERE asset_id=5 AND datatype=:dt",
                  [(":dt", AssetData.Rebasing)], commit=True)
    JalAsset(5).invalidate_cache()

    with pytest.raises(LedgerAssetShortage) as stop:
        Ledger().rebuild(from_timestamp=0)
    assert RebaseResidue().refusal_to_realize(stop.value) != ''
    assert not RebaseResidue().absorb(stop.value)
