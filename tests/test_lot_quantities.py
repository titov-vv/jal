from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_fifo
from tests.helpers import d2t, create_assets, create_stocks, create_actions, create_trades, create_conversions, \
    create_corporate_actions, create_transfers
from constants import AccountData, BookAccount, PredefinedAsset, PredefinedCategory, PredefinedAccountType
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.asset import JalAsset
from jal.db.ledger import Ledger, LedgerAmounts
from jal.db.operations import CorporateAction


# What every lot of 'asset_id' held on 'account_id' consists of: (stored remaining_qty, stored c_qty, effective qty).
# The lot layer is the only place where these three are different numbers - the books hold a single exact sum.
def _lots(account_id, asset_id) -> list:
    lots = JalAccount(account_id).open_trades_list(JalAsset(asset_id))
    return [(x.open_qty(), x.q_adjustment(), x.open_qty(adjusted=True)) for x in lots]


def _lots_total(account_id, asset_id) -> Decimal:
    return sum((x[2] for x in _lots(account_id, asset_id)), Decimal('0'))


def _book_amount(account_id, asset_id) -> Decimal:
    return LedgerAmounts("amount_acc")[(BookAccount.Assets, account_id, asset_id)]


# ----------------------------------------------------------------------------------------------------------------------
# A conversion carries a lot over by scaling it: the lot keeps the quantity it was opened with and gets 'c_qty', the
# in/out ratio of the conversion, as a coefficient. The ratio of two arbitrary amounts is almost never representable,
# so the effective quantity - the product - is not the quantity the conversion delivered, and the lots no longer add
# up to what the books hold. The numbers are a real chain of conversions taken from a live database (aEthUSDT).
def test_conversion_scales_each_lot_by_an_inexact_ratio(prepare_db_fifo):
    JalAccount(1).set_data(AccountData.Precision, 18)   # so the books keep every digit of what was posted
    create_stocks([('USDT', 'Stablecoin'), ('aEthUSDT', 'Lending receipt')], currency_id=2)
    t1, t2, t3 = d2t(220101), d2t(220201), d2t(220301)
    create_trades(1, [(t1, t1, 4, Decimal('5089.698147'), Decimal('1'), Decimal('0')),
                      (t1, t1, 4, Decimal('2994.98'), Decimal('1'), Decimal('0'))])
    create_conversions(1, [(t1, 4, '5089.698147', 5, '5089.698146'),
                           (t2, 4, '2994.98', 5, '2999.321832'),
                           (t3, 5, '572.934836', 4, '585')])   # partial - leaves both adjusted lots in place
    Ledger().rebuild(from_timestamp=0)

    assert _lots(1, 5) == [
        (Decimal('4516.763310887432452855721868'), Decimal('0.999999999803524694172791776'), Decimal('4516.76331')),
        (Decimal('2994.98'), Decimal('1.001449703169971084948814349'), Decimal('2999.321831999999999999999999'))
    ]
    # The books hold the amounts the conversions delivered, the lots hold a product of ratios - and the two differ
    assert _book_amount(1, 5) == Decimal('7516.085142')
    assert _lots_total(1, 5) == Decimal('7516.085141999999999999999999')


# ----------------------------------------------------------------------------------------------------------------------
# A corporate action does exactly the same to each result asset, and scales every lot of the position independently:
# a split of 3 shares into 7 gives each of the three lots a c_qty of 7/3, and three thirds do not make a whole.
def test_corporate_action_scales_each_lot_by_an_inexact_ratio(prepare_db_fifo):
    create_stocks([('A', 'A SHARE'), ('B', 'B SHARE')], currency_id=2)
    t1, t2 = d2t(220101), d2t(220201)
    create_trades(1, [(t1, t1, 4, Decimal('1'), Decimal('100'), Decimal('0')),
                      (t1, t1, 4, Decimal('1'), Decimal('200'), Decimal('0')),
                      (t1, t1, 4, Decimal('1'), Decimal('300'), Decimal('0'))])
    create_corporate_actions(1, [(t2, CorporateAction.Split, 4, Decimal('3'), 'Split 3 A -> 7 B',
                                  [(5, Decimal('7'), Decimal('1'))])])
    Ledger().rebuild(from_timestamp=0)

    third = Decimal('2.333333333333333333333333333')      # 7/3 as far as the decimal context goes
    assert _lots(1, 5) == [(Decimal('1'), third, third)] * 3
    assert _book_amount(1, 5) == Decimal('7')
    assert _lots_total(1, 5) == Decimal('6.999999999999999999999999999')


# ----------------------------------------------------------------------------------------------------------------------
# A currency-crossing transfer adjusts the PRICE of the carried lots by the FX rate and leaves their quantity alone,
# so 'c_qty' stays 1 and the quantities are exact. This must stay true when 'remaining_qty' changes meaning.
def test_currency_crossing_transfer_leaves_the_quantity_alone(prepare_db):
    JalAccountCreator(currency_id=2, number='', name='Acc.USD', investing=1, organization=1,
                      account_type=PredefinedAccountType.Broker).commit()
    JalAccountCreator(currency_id=3, number='', name='Acc.EUR', investing=1, organization=1,
                      account_type=PredefinedAccountType.Broker).commit()
    create_assets([('ETH', 'Ethereum', '', 2, PredefinedAsset.Crypto, 0)])   # asset id 4
    create_actions([(d2t(210101), 1, 1, [(PredefinedCategory.StartingBalance, 100000.0)])])
    create_trades(1, [(d2t(210102), d2t(210102), 4, Decimal('3'), Decimal('1000'), Decimal('0'))])
    create_transfers([(d2t(210103), 1, Decimal('3'), 2, Decimal('2800'), 4)])
    Ledger().rebuild(from_timestamp=0)

    assert _lots(2, 4) == [(Decimal('3'), Decimal('1'), Decimal('3'))]
    assert _book_amount(2, 4) == Decimal('3')
    lot = JalAccount(2).open_trades_list(JalAsset(4))[0]
    assert (lot.open_price(), lot.p_adjustment()) == (Decimal('1000'), Decimal('0.9333333333333333333333333333'))


# ----------------------------------------------------------------------------------------------------------------------
# Partial consumption divides the taken quantity back by 'c_qty' to store what is left in the lot's own units, which
# is the second rounding source: the stored remainder of a scaled lot is no longer a number anybody entered.
def test_partial_consumption_stores_the_remainder_in_original_units(prepare_db_fifo):
    JalAccount(1).set_data(AccountData.Precision, 18)
    create_stocks([('USDT', 'Stablecoin'), ('aEthUSDT', 'Lending receipt')], currency_id=2)
    t1, t2 = d2t(220101), d2t(220201)
    create_trades(1, [(t1, t1, 4, Decimal('2994.98'), Decimal('1'), Decimal('0'))])
    create_conversions(1, [(t1, 4, '2994.98', 5, '2999.321832'),
                           (t2, 5, '999.321832', 4, '999')])
    Ledger().rebuild(from_timestamp=0)

    assert _lots(1, 5) == [(Decimal('1997.104790853934610375616403'),
                            Decimal('1.001449703169971084948814349'),
                            Decimal('1999.999999999999999999999999'))]
    assert _book_amount(1, 5) == Decimal('2000')      # 2999.321832 - 999.321832, exact in the books
