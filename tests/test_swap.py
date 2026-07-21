from decimal import Decimal

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_fifo
from tests.helpers import d2t, create_stocks, create_trades, create_quotes, create_swaps
from constants import BookAccount
from jal.db.ledger import Ledger, LedgerAmounts
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.operations import LedgerTransaction

_WITH_SWAP = (LedgerTransaction.Trade, LedgerTransaction.Swap)   # what the Deals report asks for


# A swap is a genuine disposal: the out asset is closed at market value and the profit/loss realized, while the in
# asset opens as a new lot at that same value. It is NOT a basis-preserving SymbolChange.
def test_swap_realizes_pnl_and_opens_new_lot(prepare_db_fifo):
    create_stocks([('A', 'Asset A'), ('B', 'Asset B')], currency_id=2)   # A -> asset 4, B -> asset 5
    t_buy, t_swap = d2t(220101), d2t(220201)
    create_quotes(4, 2, [(t_swap, 150.0)])                               # A is worth 150 at swap time
    create_trades(1, [(t_buy, t_buy, 4, 10.0, 100.0, 0.0)])              # buy 10 A @ 100 -> basis 1000
    create_swaps(1, [(t_swap, 4, 10, 5, 20)])                            # swap 10 A -> 20 B
    Ledger().rebuild(from_timestamp=0)

    # The disposed asset is gone, the acquired one is present at its full quantity
    assert JalAccount(1).get_asset_amount(t_swap, 4) == Decimal('0')
    assert JalAccount(1).get_asset_amount(t_swap, 5) == Decimal('20')

    # Realized profit = market value (10*150=1500) - basis (1000) = 500
    deals = JalAccount(1).closed_trades_list(close_otypes=_WITH_SWAP)
    assert len(deals) == 1 and deals[0].profit() == Decimal('500')

    # The acquired asset opens as a new lot at the swap-implied cost (1500 / 20 = 75)
    open_b = JalAccount(1).open_trades_list(JalAsset(5))
    assert len(open_b) == 1
    assert open_b[0].open_price() == Decimal('75')
    assert open_b[0].open_qty() == Decimal('20')


# Swap-realized deals show up in the Deals report but must stay out of the (Trade-only) tax reports until crypto
# tax treatment is designed - decision #26.
def test_swap_deals_are_in_deals_report_not_in_tax(prepare_db_fifo):
    create_stocks([('A', 'Asset A'), ('B', 'Asset B')], currency_id=2)
    t_buy, t_swap = d2t(220101), d2t(220201)
    create_quotes(4, 2, [(t_swap, 150.0)])
    create_trades(1, [(t_buy, t_buy, 4, 10.0, 100.0, 0.0)])
    create_swaps(1, [(t_swap, 4, 10, 5, 20)])
    Ledger().rebuild(from_timestamp=0)

    assert JalAccount(1).closed_trades_list() == []                      # tax path: Trade only
    deals = JalAccount(1).closed_trades_list(close_otypes=_WITH_SWAP)
    assert len(deals) == 1 and deals[0].profit() == Decimal('500')


# The swap value falls back to the acquired asset when the disposed one has no quote at all (crypto sources quote
# only one side of a pair for the first tokens a wallet ever sees).
def test_swap_values_from_in_asset_when_out_has_no_quote(prepare_db_fifo):
    create_stocks([('A', 'Asset A'), ('B', 'Asset B')], currency_id=2)
    t_buy, t_swap = d2t(220101), d2t(220201)
    create_quotes(5, 2, [(t_swap, 80.0)])                                # only B (the acquired asset) is priced
    create_trades(1, [(t_buy, t_buy, 4, 10.0, 100.0, 0.0)])
    create_swaps(1, [(t_swap, 4, 10, 5, 20)])                            # value falls back to 20 * 80 = 1600
    Ledger().rebuild(from_timestamp=0)

    open_b = JalAccount(1).open_trades_list(JalAsset(5))
    assert open_b[0].open_price() == Decimal('80')                       # 1600 / 20
    deals = JalAccount(1).closed_trades_list(close_otypes=_WITH_SWAP)
    assert deals[0].profit() == Decimal('600')                           # 1600 - 1000 basis


# Gas paid for the swap is disposed at its cost basis to Costs (no P&L on the gas), like the standalone GasFee.
def test_swap_fee_is_disposed_to_costs(prepare_db_fifo):
    create_stocks([('A', 'Asset A'), ('B', 'Asset B'), ('GAS', 'Native coin')], currency_id=2)  # GAS -> asset 6
    t_buy, t_swap = d2t(220101), d2t(220201)
    create_quotes(4, 2, [(t_swap, 150.0)])
    create_trades(1, [(t_buy, t_buy, 4, 10.0, 100.0, 0.0)])
    create_trades(1, [(t_buy, t_buy, 6, 1.0, 10.0, 0.0)])               # hold 1 GAS @ 10 (basis 10)
    create_swaps(1, [(t_swap, 4, 10, 5, 20, 6, Decimal('0.5'))])        # 0.5 GAS gas fee
    Ledger().rebuild(from_timestamp=0)

    # Half the GAS lot is spent on the fee, disposed at basis (0.5 * 10 = 5) to Costs (in account currency, asset 2)
    assert JalAccount(1).get_asset_amount(t_swap, 6) == Decimal('0.5')
    amounts = LedgerAmounts("amount_acc")
    assert amounts[(BookAccount.Costs, 1, 2)] == Decimal('5')
    # The gas disposal doesn't create a closed deal, so it never pollutes the Deals/tax reports
    assert len(JalAccount(1).closed_trades_list(close_otypes=_WITH_SWAP)) == 1
