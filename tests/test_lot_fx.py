from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_taxes
from tests.helpers import d2t, create_assets, create_actions, create_quotes, create_trades, create_transfers, \
    create_conversions, create_bridges, create_cross_chain_swaps
from tests.test_taxes_crypto import create_two_hop_lot
from jal.constants import PredefinedAsset, PredefinedCategory, PredefinedAccountType, SwapTreatment
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.asset import JalAsset
from jal.db.ledger import Ledger

USD_ACC, EUR_ACC = 1, 2
A, B = 4, 5
T_BUY, T_MOVE, T_ARRIVE, T_WRAP, T_SELL = d2t(250102), d2t(250110), d2t(250111), d2t(250120), d2t(250201)


# A USD and a EUR account; coins A and B; 10 A bought for 1000 USD + 10 fee; USD/EUR is 0.9 throughout
@pytest.fixture
def accounts(prepare_db):
    JalAccountCreator(currency_id=2, number='', name='Acc USD', investing=1, organization=1,
                      account_type=PredefinedAccountType.Broker).commit()
    JalAccountCreator(currency_id=3, number='', name='Acc EUR', investing=1, organization=1,
                      account_type=PredefinedAccountType.Broker).commit()
    create_assets([('AAA', 'Coin A', '', 2, PredefinedAsset.Crypto, 0),
                   ('BBB', 'Coin B', '', 2, PredefinedAsset.Crypto, 0)])
    create_actions([(d2t(250101), USD_ACC, 1, [(PredefinedCategory.StartingBalance, 10000.0)])])
    create_quotes(2, 3, [(x, 0.9) for x in (T_BUY, T_MOVE, T_ARRIVE, T_WRAP, T_SELL)])
    create_trades(USD_ACC, [(T_BUY, T_BUY, A, 10, 100, 10, "buy-A")])
    yield


def _deal(account_id, asset_id):
    deal, = JalAccount(account_id).closed_trades_list(JalAsset(asset_id))
    return deal


def _lot(account_id, asset_id):
    lot, = JalAccount(account_id).open_trades_list(JalAsset(asset_id))
    return lot


# ----------------------------------------------------------------------------------------------------------------------
# Each hop's rate multiplies into c_fx; the price factor and the native cost stay the purchase's
def test_two_hop_lot_keeps_its_native_cost(prepare_db_taxes):
    create_two_hop_lot()

    deal = _deal(4, 4)
    assert (deal.p_adjustment(), deal.fx_adjustment()) == (Decimal('1'), Decimal('92') / Decimal('8359'))
    assert deal.native_open_amount() == Decimal('6687.20')        # 80 x 83.59 RUB, what was paid
    assert round(deal.open_amount(), 6) == Decimal('73.600000')   # JAL's view, as before


# A transfer to another currency, then a 1:2 wrapping there: the wrapping scales c_price, the transfer sets c_fx
def test_wrapping_after_a_transfer_keeps_both_factors(accounts):
    create_transfers([(T_MOVE, USD_ACC, 10, EUR_ACC, 918, A)])   # 1010 USD of cost restated to 918 EUR
    create_conversions(EUR_ACC, [(T_WRAP, A, 10, B, 20)])
    create_trades(EUR_ACC, [(T_SELL, T_SELL, B, -20, 50, 0, "sell-B")])
    Ledger().rebuild(from_timestamp=0)

    deal = _deal(EUR_ACC, B)
    assert deal.p_adjustment() == Decimal('0.5')
    assert deal.fx_adjustment() == Decimal('918') / Decimal('1000')
    assert deal.native_open_amount() == Decimal('1000')            # in USD, the opening account's currency
    assert deal.open_amount() == Decimal('918')                    # in EUR, JAL's view


# A transfer whose destination value was left at 0: JAL's view carries zero, the native cost survives
def test_zero_deposit_leaves_the_native_cost(accounts):
    create_transfers([(T_MOVE, USD_ACC, 10, EUR_ACC, 0, A)])
    Ledger().rebuild(from_timestamp=0)

    lot = _lot(EUR_ACC, A)
    assert (lot.p_adjustment(), lot.fx_adjustment()) == (Decimal('1'), Decimal('0'))
    assert lot.open_price(adjusted=True) == Decimal('0')
    create_trades(EUR_ACC, [(T_SELL, T_SELL, A, -10, 95, 0, "sell-A")])
    Ledger().rebuild(from_timestamp=0)
    assert _deal(EUR_ACC, A).native_open_amount() == Decimal('1000')


# A bridge to another currency converts at the market rate, into c_fx
def test_bridge_rate_goes_to_c_fx(accounts):
    create_bridges([{'asset': A, 'out_ts': T_MOVE, 'out_acc': USD_ACC, 'out_qty': 10,
                     'in_ts': T_ARRIVE, 'in_acc': EUR_ACC, 'in_qty': 10}])
    Ledger().rebuild(from_timestamp=0)

    lot = _lot(EUR_ACC, A)
    assert (lot.p_adjustment(), lot.fx_adjustment()) == (Decimal('1'), Decimal('0.9'))
    assert lot.open_price(adjusted=True) == Decimal('90.0')


# A cross-chain conversion swap: the quantity ratio goes to c_price, the rate to c_fx
def test_cross_chain_conversion_swap_splits_the_factors(accounts):
    create_cross_chain_swaps([{'ts': T_MOVE, 'acc': USD_ACC, 'out_asset': A, 'out_qty': 10, 'in_ts': T_ARRIVE,
                               'in_acc': EUR_ACC, 'in_asset': B, 'in_qty': 20, 'treatment': SwapTreatment.Conversion}])
    Ledger().rebuild(from_timestamp=0)

    lot = _lot(EUR_ACC, B)
    assert (lot.p_adjustment(), lot.fx_adjustment()) == (Decimal('0.5'), Decimal('0.9'))
    assert lot.open_price(adjusted=True) == Decimal('45.00')       # 100 USD x 0.5 x 0.9
