from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_fifo
from tests.helpers import d2t, create_stocks, create_trades, create_quotes, create_swaps, create_assets, \
    create_actions, create_cross_chain_swaps
from constants import BookAccount, PredefinedAsset, PredefinedCategory, PredefinedAccountType
from jal.db.ledger import Ledger, LedgerAmounts
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.asset import JalAsset
from jal.db.operations import LedgerTransaction, LedgerError

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


# A rejected swap must report a ledger error - the message is built from the operation's own fields, and the receiving
# leg of a same-chain swap holds none of them (they are NULL), which must not break the error itself.
def test_invalid_swap_is_reported_as_a_ledger_error(prepare_db_fifo):
    create_stocks([('A', 'Asset A')], currency_id=2)
    t_buy, t_swap = d2t(220101), d2t(220201)
    create_quotes(4, 2, [(t_swap, 150.0)])
    create_trades(1, [(t_buy, t_buy, 4, 10.0, 100.0, 0.0)])
    create_swaps(1, [(t_swap, 4, 10, 4, 20)])                            # an asset can't be swapped into itself
    with pytest.raises(LedgerError):
        Ledger().rebuild(from_timestamp=0)


# ----------------------------------------------------------------------------------------------------------------------
# Cross-chain swaps: the asset is disposed on one account (chain) and the acquired one arrives on another, later.
# Seeded currencies are RUB=1, USD=2, EUR=3; the first created asset gets id 4
A, B, GAS = 4, 5, 6
ACC1, ACC2, ACC_EUR = 1, 2, 3          # ACC1/ACC2 are USD, ACC_EUR is EUR


@pytest.fixture
def chains(prepare_db_fifo):
    JalAccountCreator(currency_id=2, number='', name='Acc2', investing=1, organization=1,
                      account_type=PredefinedAccountType.Broker).commit()   # USD, id = 2
    JalAccountCreator(currency_id=3, number='', name='AccEur', investing=1, organization=1,
                      account_type=PredefinedAccountType.Broker).commit()   # EUR, id = 3
    create_assets([('A', 'Asset A', '', 2, PredefinedAsset.Crypto, 0),      # id = 4
                   ('B', 'Asset B', '', 2, PredefinedAsset.Crypto, 0),      # id = 5
                   ('GAS', 'Native coin', '', 2, PredefinedAsset.Crypto, 0)])   # id = 6
    create_actions([(d2t(210101), ACC1, 1, [(PredefinedCategory.StartingBalance, 100000.0)])])
    yield


def _open_lots(account_id, asset_id) -> list:
    return JalAccount(account_id).open_trades_list(JalAsset(asset_id))


# A cross-chain swap realizes the whole result of the exchange at the moment of disposal (as a same-chain one does)
# and opens the acquired asset on the DESTINATION account at those proceeds - nothing is gained or lost in transit.
def test_cross_chain_swap_disposes_on_source_and_opens_on_destination(chains):
    t_buy, t_out, t_in = d2t(220101), d2t(220201), d2t(220203)
    create_quotes(A, 2, [(t_out, 150.0)])                                  # A is worth 150 when it is sent
    create_trades(ACC1, [(t_buy, t_buy, A, 10.0, 100.0, 0.0)])             # buy 10 A @100 -> basis 1000
    create_cross_chain_swaps([{'ts': t_out, 'acc': ACC1, 'out_asset': A, 'out_qty': 10,
                               'in_ts': t_in, 'in_acc': ACC2, 'in_asset': B, 'in_qty': 20}])
    Ledger().rebuild(from_timestamp=0)

    assert JalAccount(ACC1).get_asset_amount(t_in, A) == Decimal('0')      # the disposed asset left the source
    assert JalAccount(ACC1).get_asset_amount(t_in, B) == Decimal('0')      # and nothing arrived there
    assert JalAccount(ACC2).get_asset_amount(t_in, B) == Decimal('20')     # the acquired asset is on the destination

    # Profit is realized on the source account at market value (10*150=1500) less basis (1000)
    deals = JalAccount(ACC1).closed_trades_list(close_otypes=_WITH_SWAP)
    assert len(deals) == 1 and deals[0].profit() == Decimal('500')
    assert JalAccount(ACC2).closed_trades_list(close_otypes=_WITH_SWAP) == []

    lots = _open_lots(ACC2, B)                                             # new lot at the proceeds: 1500 / 20 = 75
    assert len(lots) == 1 and lots[0].open_price() == Decimal('75') and lots[0].open_qty() == Decimal('20')
    # The proceeds passed through the Transfers book and left nothing behind in transit
    amounts = LedgerAmounts("amount_acc")
    assert amounts[(BookAccount.Transfers, ACC1, 2)] + amounts[(BookAccount.Transfers, ACC2, 2)] == Decimal('0')


# The acquired asset opens at its arrival date, so it is not available on the destination before it arrives
def test_cross_chain_swap_asset_arrives_only_at_its_own_date(chains):
    t_buy, t_out, t_in = d2t(220101), d2t(220201), d2t(220203)
    create_quotes(A, 2, [(t_out, 150.0)])
    create_trades(ACC1, [(t_buy, t_buy, A, 10.0, 100.0, 0.0)])
    create_cross_chain_swaps([{'ts': t_out, 'acc': ACC1, 'out_asset': A, 'out_qty': 10,
                               'in_ts': t_in, 'in_acc': ACC2, 'in_asset': B, 'in_qty': 20}])
    Ledger().rebuild(from_timestamp=0)

    assert JalAccount(ACC1).get_asset_amount(t_out, A) == Decimal('0')     # already gone when sent
    assert JalAccount(ACC2).get_asset_amount(d2t(220202), B) == Decimal('0')   # in transit, not delivered yet
    assert JalAccount(ACC2).get_asset_amount(t_in, B) == Decimal('20')


# Gas is burned on the source chain, so it rides the disposing leg and is expensed at basis (no P&L on gas)
def test_cross_chain_swap_gas_is_paid_on_the_source(chains):
    t_buy, t_out, t_in = d2t(220101), d2t(220201), d2t(220203)
    create_quotes(A, 2, [(t_out, 150.0)])
    create_trades(ACC1, [(t_buy, t_buy, A, 10.0, 100.0, 0.0)])
    create_trades(ACC1, [(t_buy, t_buy, GAS, 1.0, 10.0, 0.0)])             # hold 1 GAS @10 on the source
    create_cross_chain_swaps([{'ts': t_out, 'acc': ACC1, 'out_asset': A, 'out_qty': 10, 'in_ts': t_in,
                               'in_acc': ACC2, 'in_asset': B, 'in_qty': 20, 'fee_asset': GAS, 'fee_qty': 0.5}])
    Ledger().rebuild(from_timestamp=0)

    assert JalAccount(ACC1).get_asset_amount(t_in, GAS) == Decimal('0.5')  # half the lot burned as gas
    amounts = LedgerAmounts("amount_acc")
    assert amounts[(BookAccount.Costs, ACC1, 2)] == Decimal('5')           # 0.5 * 10 basis, on the source account
    assert len(JalAccount(ACC1).closed_trades_list(close_otypes=_WITH_SWAP)) == 1   # gas creates no deal
    assert _open_lots(ACC2, B)[0].open_price() == Decimal('75')            # proceeds are unaffected by the gas


# Accounts kept in different currencies: the proceeds are converted with the FX rate of the arrival date (as a bridge
# converts a carried cost basis - decision #27)
def test_cross_chain_swap_converts_proceeds_between_currencies(chains):
    t_buy, t_out, t_in = d2t(220101), d2t(220201), d2t(220203)
    create_quotes(A, 2, [(t_out, 150.0)])
    create_quotes(2, 3, [(t_in, 0.8)])                                     # 1 USD = 0.8 EUR when the asset arrives
    create_trades(ACC1, [(t_buy, t_buy, A, 10.0, 100.0, 0.0)])
    create_cross_chain_swaps([{'ts': t_out, 'acc': ACC1, 'out_asset': A, 'out_qty': 10,
                               'in_ts': t_in, 'in_acc': ACC_EUR, 'in_asset': B, 'in_qty': 20}])
    Ledger().rebuild(from_timestamp=0)

    # 1500 USD of proceeds become 1200 EUR on the destination -> 60 EUR per unit
    lots = _open_lots(ACC_EUR, B)
    assert len(lots) == 1 and lots[0].open_price() == Decimal('60')
    # P&L is still realized on the source account, in its own currency
    assert JalAccount(ACC1).closed_trades_list(close_otypes=_WITH_SWAP)[0].profit() == Decimal('500')


# An asset can't arrive before it was exchanged - such a swap is rejected instead of being booked backwards
def test_cross_chain_swap_rejects_arrival_before_disposal(chains):
    t_buy, t_out, t_in = d2t(220101), d2t(220203), d2t(220201)
    create_quotes(A, 2, [(t_out, 150.0)])
    create_trades(ACC1, [(t_buy, t_buy, A, 10.0, 100.0, 0.0)])
    create_cross_chain_swaps([{'ts': t_out, 'acc': ACC1, 'out_asset': A, 'out_qty': 10,
                               'in_ts': t_in, 'in_acc': ACC2, 'in_asset': B, 'in_qty': 20}])
    with pytest.raises(LedgerError):
        Ledger().rebuild(from_timestamp=0)
