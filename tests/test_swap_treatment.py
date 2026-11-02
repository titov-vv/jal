import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_fifo
from tests.helpers import d2t, create_trades, create_quotes, create_swaps, create_assets, create_actions, \
    create_cross_chain_swaps, nth_operation, symbol_id_for
from jal.constants import BookAccount, AssetData, PredefinedAsset, PredefinedCategory, PredefinedAccountType, \
    SwapTreatment
from jal.db.ledger import Ledger, LedgerAmounts
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.asset import JalAsset
from jal.db.db import JalDB
from jal.db.operations import LedgerTransaction, LedgerError, Swap, AssetIncome

# Seeded currencies are RUB=1, USD=2, EUR=3; the first created asset gets id 4
A, B = 4, 5
ACC1, ACC2, ACC_EUR = 1, 2, 3          # ACC1/ACC2 are USD, ACC_EUR is EUR
_WITH_SWAP = (LedgerTransaction.Trade, LedgerTransaction.Swap)


@pytest.fixture
def chains(prepare_db_fifo):
    JalAccountCreator(currency_id=2, number='', name='Acc2', investing=1, organization=1,
                      account_type=PredefinedAccountType.Broker).commit()   # USD, id = 2
    JalAccountCreator(currency_id=3, number='', name='AccEur', investing=1, organization=1,
                      account_type=PredefinedAccountType.Broker).commit()   # EUR, id = 3
    create_assets([('A', 'Asset A', '', 2, PredefinedAsset.Crypto, 0),      # id = 4
                   ('B', 'Asset B', '', 2, PredefinedAsset.Crypto, 0)])     # id = 5
    create_actions([(d2t(210101), ACC1, 1, [(PredefinedCategory.StartingBalance, 100000.0)])])
    yield


def _peg(asset_id):
    JalDB._exec("INSERT INTO asset_data (asset_id, datatype, value) VALUES (:asset, :type, 2)",
                [(":asset", asset_id), (":type", AssetData.PeggedTo)], commit=True)
    JalDB().invalidate_cache()


def _profit_rows() -> int:
    return JalDB._read("SELECT COUNT(*) FROM ledger WHERE otype=:swap AND book_account=:incomes",
                       [(":swap", LedgerTransaction.Swap), (":incomes", BookAccount.Incomes)])


def _lots(account_id, asset_id) -> list:
    lots = JalAccount(account_id).open_trades_list(JalAsset(asset_id))
    return [(x.open_operation().id(), x.acquired(), x.open_qty(), x.open_price(adjusted=True)) for x in lots]


def _trade_oid(index) -> int:
    return nth_operation(LedgerTransaction.Trade, index).id()


# Two lots of A: 10 @100 on 1 Jan and 10 @130 on 15 Jan; 15 A -> 30 B on 1 Feb takes all of the first and half of the
# second. Each carries its own cost and date onto B: 10 A -> 20 B at 1000 (50 each), 5 A -> 10 B at 650 (65 each).
def test_conversion_carries_cost_and_date(chains):
    t_buy1, t_buy2, t_swap, t_sell = d2t(220101), d2t(220115), d2t(220201), d2t(220301)
    create_quotes(A, 2, [(t_swap, 150.0)])                                # ignored by a conversion
    create_trades(ACC1, [(t_buy1, t_buy1, A, 10.0, 100.0, 0.0), (t_buy2, t_buy2, A, 10.0, 130.0, 0.0)])
    create_swaps(ACC1, [(t_swap, A, 15, B, 30)], treatment=SwapTreatment.Conversion)
    Ledger().rebuild(from_timestamp=0)

    buy1, buy2 = _trade_oid(1), _trade_oid(2)
    assert _lots(ACC1, A) == [(buy2, t_buy2, Decimal('5'), Decimal('130'))]
    assert _lots(ACC1, B) == [(buy1, t_buy1, Decimal('20'), Decimal('50')), (buy2, t_buy2, Decimal('10'), Decimal('65'))]
    assert _profit_rows() == 0
    amounts = LedgerAmounts("value_acc")
    assert amounts[(BookAccount.Assets, ACC1, B)] == Decimal('1650')     # 1000 + 650
    deals = JalAccount(ACC1).closed_trades_list(close_otypes=_WITH_SWAP)
    assert [x.profit() for x in deals] == [Decimal('0'), Decimal('0')]

    # The result appears when B is sold: 30 B @80 -> 20 * 80 - 1000 and 10 * 80 - 650, dated by the A purchases
    create_trades(ACC1, [(t_sell, t_sell, B, -30.0, 80.0, 0.0)])
    Ledger().rebuild(from_timestamp=0)
    deals = JalAccount(ACC1).closed_trades_list()
    assert sorted((x.acquired(), x.profit()) for x in deals) == [(t_buy1, Decimal('600')), (t_buy2, Decimal('150'))]


# 10 A @100 (1000 USD) arrive as 20 B on the EUR account at 0.8 EUR per USD: 800 EUR, 40 EUR per B, A's date kept
def test_cross_chain_conversion_converts_basis_between_currencies(chains):
    t_buy, t_out, t_in = d2t(220101), d2t(220201), d2t(220203)
    create_quotes(2, 3, [(t_in, 0.8)])
    create_trades(ACC1, [(t_buy, t_buy, A, 10.0, 100.0, 0.0)])
    create_cross_chain_swaps([{'ts': t_out, 'acc': ACC1, 'out_asset': A, 'out_qty': 10, 'in_ts': t_in,
                               'in_acc': ACC_EUR, 'in_asset': B, 'in_qty': 20, 'treatment': SwapTreatment.Conversion}])
    Ledger().rebuild(from_timestamp=0)

    assert JalAccount(ACC_EUR).get_asset_amount(d2t(220202), B) == Decimal('0')   # in transit
    assert _lots(ACC_EUR, B) == [(_trade_oid(1), t_buy, Decimal('20'), Decimal('40'))]
    assert _lots(ACC1, A) == []
    assert _profit_rows() == 0
    # A travels at its basis, as a bridge carries it, and nothing is left in transit
    amounts, values = LedgerAmounts("amount_acc"), LedgerAmounts("value_acc")
    assert (amounts[(BookAccount.Transfers, ACC1, A)], values[(BookAccount.Transfers, ACC1, A)]) == (10, 1000)
    assert (amounts[(BookAccount.Transfers, ACC_EUR, A)], values[(BookAccount.Transfers, ACC_EUR, A)]) == (-10, -800)
    assert values[(BookAccount.Assets, ACC_EUR, B)] == Decimal('800')


# A zero-cost lot (a reward) crosses chains and currencies as a conversion: still zero, still the reward's lot
def test_cross_chain_conversion_carries_a_zero_basis(chains):
    t_reward, t_out, t_in = d2t(220101), d2t(220201), d2t(220203)
    create_quotes(2, 3, [(t_in, 0.8)])
    reward = LedgerTransaction.create_new(LedgerTransaction.AssetIncome, {
        'timestamp': t_reward, 'type': AssetIncome.StakingReward, 'account_id': ACC1, 'symbol_id': symbol_id_for(A),
        'amount': '10', 'tax': '0', 'number': '', 'note': ''})
    create_cross_chain_swaps([{'ts': t_out, 'acc': ACC1, 'out_asset': A, 'out_qty': 10, 'in_ts': t_in,
                               'in_acc': ACC_EUR, 'in_asset': B, 'in_qty': 20, 'treatment': SwapTreatment.Conversion}])
    Ledger().rebuild(from_timestamp=0)

    assert _lots(ACC_EUR, B) == [(reward.id(), t_reward, Decimal('20'), Decimal('0'))]
    amounts = LedgerAmounts("amount_acc")
    assert amounts[(BookAccount.Transfers, ACC1, A)] + amounts[(BookAccount.Transfers, ACC_EUR, A)] == 0


# Auto: a pegged asset on either side makes a sale (10 * 150 - 1000 = 500), none a conversion
@pytest.mark.parametrize("pegged, profit", [(A, Decimal('500')), (B, Decimal('500')), (None, None)])
def test_auto_follows_the_peg(chains, pegged, profit):
    t_buy, t_swap = d2t(220101), d2t(220201)
    if pegged:
        _peg(pegged)
    create_quotes(A, 2, [(t_swap, 150.0)])
    create_trades(ACC1, [(t_buy, t_buy, A, 10.0, 100.0, 0.0)])
    create_swaps(ACC1, [(t_swap, A, 10, B, 20)], treatment=SwapTreatment.Auto)
    Ledger().rebuild(from_timestamp=0)

    swap = nth_operation(LedgerTransaction.Swap, 1, Swap.Whole)
    assert swap.stored_treatment() == SwapTreatment.Auto
    if profit is None:
        assert swap.treatment() == SwapTreatment.Conversion and _profit_rows() == 0
        assert swap.name() == "Swap (conversion)"
    else:
        assert swap.treatment() == SwapTreatment.Sale and _profit_rows() == 1
        assert swap.name() == "Swap"
        assert JalAccount(ACC1).closed_trades_list(close_otypes=_WITH_SWAP)[0].profit() == profit


# A stored treatment wins over the peg
@pytest.mark.parametrize("pegged, treatment, profit_rows", [(B, SwapTreatment.Conversion, 0),
                                                             (None, SwapTreatment.Sale, 1)])
def test_override_beats_the_peg(chains, pegged, treatment, profit_rows):
    t_buy, t_swap = d2t(220101), d2t(220201)
    if pegged:
        _peg(pegged)
    create_quotes(A, 2, [(t_swap, 150.0)])
    create_trades(ACC1, [(t_buy, t_buy, A, 10.0, 100.0, 0.0)])
    create_swaps(ACC1, [(t_swap, A, 10, B, 20)], treatment=treatment)
    Ledger().rebuild(from_timestamp=0)
    assert _profit_rows() == profit_rows


# A conversion asks for no quote; the same swap as a sale can't be valued and stops the rebuild
def test_conversion_needs_no_quote(chains):
    t_buy, t_swap = d2t(220101), d2t(220201)
    create_trades(ACC1, [(t_buy, t_buy, A, 10.0, 100.0, 0.0)])
    create_swaps(ACC1, [(t_swap, A, 10, B, 20)], treatment=SwapTreatment.Auto)
    Ledger().rebuild(from_timestamp=0)
    assert JalAccount(ACC1).get_asset_amount(t_swap, B) == Decimal('20')

    _peg(B)
    with pytest.raises(LedgerError):
        Ledger().rebuild(from_timestamp=0)


# A sale's result posts into a part of its own and draws as the result (it used to share its number with Incoming)
@pytest.mark.parametrize("cross_chain", [False, True])
def test_sale_profit_draws_as_profit(chains, cross_chain):
    t_buy, t_out, t_in = d2t(220101), d2t(220201), d2t(220203)
    create_quotes(A, 2, [(t_out, 150.0)])
    create_trades(ACC1, [(t_buy, t_buy, A, 10.0, 100.0, 0.0)])
    if cross_chain:
        create_cross_chain_swaps([{'ts': t_out, 'acc': ACC1, 'out_asset': A, 'out_qty': 10,
                                   'in_ts': t_in, 'in_acc': ACC2, 'in_asset': B, 'in_qty': 20}])
    else:
        create_swaps(ACC1, [(t_out, A, 10, B, 20)])
    Ledger().rebuild(from_timestamp=0)

    oid, opart = JalDB._read("SELECT oid, opart FROM ledger WHERE otype=:swap AND book_account=:incomes",
                             [(":swap", LedgerTransaction.Swap), (":incomes", BookAccount.Incomes)])
    assert opart == Swap.Profit
    profit = LedgerTransaction.get_operation(LedgerTransaction.Swap, oid, opart)
    assert profit.value_change(part_only=True) == [Decimal('500')]
    assert profit.value_currency() == 'USD'
    assert profit.account_id() == ACC1 and profit.timestamp() == t_out
    assert profit.view_rows() == 1
    if cross_chain:   # the arriving leg still draws as itself
        incoming = LedgerTransaction.get_operation(LedgerTransaction.Swap, oid, Swap.Incoming)
        assert incoming.value_change(part_only=True) == [Decimal('20')]


# The Deals report hides a conversion's zero deals, as it hides a wrapping's. 20 A @100: 10 A -> 20 B sold at 150
# (500), 10 A -> 30 B converted at 1000; then 50 B @80: 20 * 80 - 1500 = 100 and 30 * 80 - 1000 = 1400
def test_deals_report_hides_conversion_deals(chains):
    from jal.reports.deals import DealsReportWindow
    from jal.reports.reports import Reports
    t_buy, t_sale, t_conv, t_sell = d2t(220101), d2t(220201), d2t(220202), d2t(220301)
    create_quotes(A, 2, [(t_sale, 150.0)])
    create_trades(ACC1, [(t_buy, t_buy, A, 20.0, 100.0, 0.0)])
    create_swaps(ACC1, [(t_sale, A, 10, B, 20)], treatment=SwapTreatment.Sale)
    create_swaps(ACC1, [(t_conv, A, 10, B, 30)], treatment=SwapTreatment.Conversion)
    create_trades(ACC1, [(t_sell, t_sell, B, -50.0, 80.0, 0.0)])
    Ledger().rebuild(from_timestamp=0)
    assert len(JalAccount(ACC1).closed_trades_list(close_otypes=_WITH_SWAP)) == 4   # the conversion's zero is there

    window = DealsReportWindow(Reports(None, None))
    window.ui.ReportRange.setRange(d2t(220101), d2t(220401))
    window.ui.ReportAccountEdit.selection_done(ACC1)
    assert sorted(x.profit() for x in window.trades_model._trades) == [Decimal('100'), Decimal('500'), Decimal('1400')]


# A sale's result is listed in the by-category report as the result, for a cross-chain swap too (G9: it was drawn as
# the arriving leg, 20 B, because both used part 1)
@pytest.mark.parametrize("cross_chain", [False, True])
def test_category_report_shows_swap_profit(chains, cross_chain):
    from PySide6.QtWidgets import QTableView
    from jal.reports.category import CategoryOperationsModel
    t_buy, t_out, t_in = d2t(220101), d2t(220201), d2t(220203)
    create_quotes(A, 2, [(t_out, 150.0)])
    create_trades(ACC1, [(t_buy, t_buy, A, 10.0, 100.0, 0.0)])
    if cross_chain:
        create_cross_chain_swaps([{'ts': t_out, 'acc': ACC1, 'out_asset': A, 'out_qty': 10,
                                   'in_ts': t_in, 'in_acc': ACC2, 'in_asset': B, 'in_qty': 20}])
    else:
        create_swaps(ACC1, [(t_out, A, 10, B, 20)])
    Ledger().rebuild(from_timestamp=0)

    view = QTableView()
    model = CategoryOperationsModel(view)
    model.updateView(PredefinedCategory.Profit, (d2t(220101), d2t(220301)), 2)
    assert model.rowCount() == 1
    assert model.data(model.index(0, 6)) == [Decimal('500')]
    assert model.data(model.index(0, 7)) == 'USD'
    assert model._total == Decimal('500')


# A pegged flag set after a rebuild turns an auto swap from a conversion into a sale at the next (incremental)
# rebuild, and removing it turns it back
def test_peg_edit_reclassifies_at_next_rebuild(chains):
    t_buy, t_swap = d2t(220101), d2t(220201)
    create_quotes(A, 2, [(t_swap, 150.0)])
    create_trades(ACC1, [(t_buy, t_buy, A, 10.0, 100.0, 0.0)])
    create_swaps(ACC1, [(t_swap, A, 10, B, 20)], treatment=SwapTreatment.Auto)
    Ledger().rebuild(from_timestamp=0)
    buy = _trade_oid(1)
    swap = nth_operation(LedgerTransaction.Swap, 1).id()
    assert _profit_rows() == 0 and _lots(ACC1, B) == [(buy, t_buy, Decimal('20'), Decimal('50'))]

    _peg(B)
    Ledger().rebuild()
    assert _profit_rows() == 1
    assert _lots(ACC1, B) == [(swap, t_swap, Decimal('20'), Decimal('75'))]   # a new lot at 1500 / 20

    JalDB._exec("DELETE FROM asset_data WHERE datatype=:type", [(":type", AssetData.PeggedTo)], commit=True)
    JalDB().invalidate_cache()
    Ledger().rebuild()
    assert _profit_rows() == 0 and _lots(ACC1, B) == [(buy, t_buy, Decimal('20'), Decimal('50'))]
