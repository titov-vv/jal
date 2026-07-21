from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, create_assets, create_actions, create_trades, create_transfers
from constants import PredefinedAsset, PredefinedCategory, PredefinedAccountType
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.asset import JalAsset
from jal.db.ledger import Ledger

# Seeded currencies are RUB=1, USD=2, EUR=3; the first created asset gets id 4
ETH = 4
ACC1_USD, ACC2_USD, ACC_EUR = 1, 2, 3


@pytest.fixture
def accounts(prepare_db):
    JalAccountCreator(currency_id=2, number='', name='Acc1', investing=1, organization=1,
                      account_type=PredefinedAccountType.Broker).commit()   # USD
    JalAccountCreator(currency_id=2, number='', name='Acc2', investing=1, organization=1,
                      account_type=PredefinedAccountType.Broker).commit()   # USD
    JalAccountCreator(currency_id=3, number='', name='AccEur', investing=1, organization=1,
                      account_type=PredefinedAccountType.Broker).commit()   # EUR
    create_assets([('ETH', 'Ethereum', '', 2, PredefinedAsset.Crypto, 0)])   # ID = 4
    create_actions([(d2t(210101), ACC1_USD, 1, [(PredefinedCategory.StartingBalance, 100000.0)])])
    yield


def _open_qty(account_id) -> Decimal:
    lots = JalAccount(account_id).open_trades_list(JalAsset(ETH))
    return sum((lot.open_qty(adjusted=True) for lot in lots), Decimal('0'))


def _open_basis(account_id) -> Decimal:
    lots = JalAccount(account_id).open_trades_list(JalAsset(ETH))
    return sum((lot.open_qty(adjusted=True) * lot.open_price(adjusted=True) for lot in lots), Decimal('0'))


def _realized_profit(account_id) -> Decimal:
    deals = JalAccount(account_id).closed_trades_list(JalAsset(ETH))   # default: only Trade-closed (real sales)
    return sum((deal.profit() for deal in deals), Decimal('0'))


# The core bug: carrying one lot into the same (account, asset) bucket twice must not lose a slice.
# Buy 3 ETH as ONE lot, move it out in two partial transfers, then sell the 2 ETH that arrived.
# Before the slice_id fix open_trades_list() kept only the latest carry-over row (1 ETH), so the sale
# closed 1 ETH and realized 500 instead of 1000 - the loss lived only in trades_closed / tax reports.
def test_double_partial_transfer_keeps_both_slices(accounts):
    create_trades(ACC1_USD, [(d2t(210102), d2t(210102), ETH, 3.0, 1000.0, 0.0)])   # one lot of 3 ETH @1000
    create_transfers([(d2t(210103), ACC1_USD, 1, ACC2_USD, 1, ETH)])                # first partial carry-over
    create_transfers([(d2t(210104), ACC1_USD, 1, ACC2_USD, 1, ETH)])                # second partial carry-over
    Ledger().rebuild(from_timestamp=0)

    assert _open_qty(ACC1_USD) == Decimal('1')     # 1 ETH stays behind
    assert _open_qty(ACC2_USD) == Decimal('2')     # both carried slices survive (was 1 before the fix)

    create_trades(ACC2_USD, [(d2t(210105), d2t(210105), ETH, -2.0, 1500.0, 0.0)])   # sell the 2 ETH that arrived
    Ledger().rebuild(from_timestamp=0)

    assert _open_qty(ACC2_USD) == Decimal('0')
    deals = JalAccount(ACC2_USD).closed_trades_list(JalAsset(ETH))
    assert len(deals) == 2                          # two lots closed, not one
    assert _realized_profit(ACC2_USD) == Decimal('1000')   # 2 * (1500 - 1000), was 500 before the fix


# Non-regression: repeated partial consumption of a single lot on one account keeps updating the SAME slice
# (slice_id is preserved through _close_deals_fifo), so basis and realized P&L stay correct across sales.
def test_partial_sells_of_one_lot_are_unchanged(accounts):
    create_trades(ACC1_USD, [(d2t(210102), d2t(210102), ETH, 3.0, 1000.0, 0.0)])
    create_trades(ACC1_USD, [(d2t(210103), d2t(210103), ETH, -1.0, 1500.0, 0.0)])   # partial sell 1
    create_trades(ACC1_USD, [(d2t(210104), d2t(210104), ETH, -1.0, 2000.0, 0.0)])   # partial sell 2
    Ledger().rebuild(from_timestamp=0)

    assert _open_qty(ACC1_USD) == Decimal('1')      # 1 ETH remains open
    assert _open_basis(ACC1_USD) == Decimal('1000')
    assert _realized_profit(ACC1_USD) == Decimal('1500')   # (1500-1000) + (2000-1000)


# Cross-currency split: one lot moved out by two transfers whose destination values differ ends up as two slices
# with DIFFERENT bases on the destination. A partial sale must consume them in a deterministic FIFO order; the
# tiebreaker is arrival order (earliest carry first), so the first (900) basis is used before the second (850).
def test_cross_currency_split_partial_sale_uses_earliest_slice_first(accounts):
    create_trades(ACC1_USD, [(d2t(210102), d2t(210102), ETH, 2.0, 1000.0, 0.0)])    # 2 ETH @1000 USD, one lot
    create_transfers([(d2t(210103), ACC1_USD, 1, ACC_EUR, 900, ETH)])   # -> EUR, rescaled to 900 EUR basis (slice S1)
    create_transfers([(d2t(210104), ACC1_USD, 1, ACC_EUR, 850, ETH)])   # -> EUR, rescaled to 850 EUR basis (slice S2)
    Ledger().rebuild(from_timestamp=0)

    assert _open_qty(ACC_EUR) == Decimal('2')
    assert _open_basis(ACC_EUR) == Decimal('1750')  # 900 + 850, both slices present

    create_trades(ACC_EUR, [(d2t(210105), d2t(210105), ETH, -1.0, 1000.0, 0.0)])    # sell 1 ETH @1000 EUR
    Ledger().rebuild(from_timestamp=0)

    assert _open_qty(ACC_EUR) == Decimal('1')
    assert _open_basis(ACC_EUR) == Decimal('850')   # the earliest-arrived 900 slice was consumed, 850 remains
    deals = JalAccount(ACC_EUR).closed_trades_list(JalAsset(ETH))
    assert len(deals) == 1
    assert _realized_profit(ACC_EUR) == Decimal('100')   # 1000 - 900 (S1 first), not 150
