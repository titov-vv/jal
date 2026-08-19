import logging
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


# What every lot of 'asset_id' held on 'account_id' consists of: the quantity it holds and its 'c_qty', which only
# relates that quantity to the operation that opened the lot and takes no part in any quantity math.
def _lots(account_id, asset_id) -> list:
    lots = JalAccount(account_id).open_trades_list(JalAsset(asset_id))
    return [(x.open_qty(), x.q_adjustment()) for x in lots]


def _lots_total(account_id, asset_id) -> Decimal:
    return sum((x[0] for x in _lots(account_id, asset_id)), Decimal('0'))


def _book_amount(account_id, asset_id) -> Decimal:
    return LedgerAmounts("amount_acc")[(BookAccount.Assets, account_id, asset_id)]


# ----------------------------------------------------------------------------------------------------------------------
# A conversion delivers a quantity and that quantity is allocated over the lots it carries over, so the lots add up
# to exactly what the books hold. Scaling each lot by the in/out ratio instead - a ratio of two arbitrary amounts,
# almost never representable - used to leave them summing to 7516.085141999999999999999999 against 7516.085142 in the
# books. The numbers are a real chain of conversions taken from a live database (aEthUSDT).
def test_conversion_allocates_the_delivered_quantity_over_the_lots(prepare_db_fifo):
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
        (Decimal('4516.76331'), Decimal('0.999999999803524694172791776')),
        (Decimal('2999.321832'), Decimal('1.001449703169971084948814349'))
    ]
    assert _book_amount(1, 5) == Decimal('7516.085142')
    assert _lots_total(1, 5) == _book_amount(1, 5)


# ----------------------------------------------------------------------------------------------------------------------
# A corporate action allocates the same way, per result asset: a split of 3 shares into 7 gives two of the three lots
# their own share and the last one the remainder, because three sevenths-of-three do not make a whole.
def test_corporate_action_allocates_the_result_quantity_over_the_lots(prepare_db_fifo):
    create_stocks([('A', 'A SHARE'), ('B', 'B SHARE')], currency_id=2)
    t1, t2 = d2t(220101), d2t(220201)
    create_trades(1, [(t1, t1, 4, Decimal('1'), Decimal('100'), Decimal('0')),
                      (t1, t1, 4, Decimal('1'), Decimal('200'), Decimal('0')),
                      (t1, t1, 4, Decimal('1'), Decimal('300'), Decimal('0'))])
    create_corporate_actions(1, [(t2, CorporateAction.Split, 4, Decimal('3'), 'Split 3 A -> 7 B',
                                  [(5, Decimal('7'), Decimal('1'))])])
    Ledger().rebuild(from_timestamp=0)

    third = Decimal('2.333333333333333333333333333')      # 7/3 as far as the decimal context goes
    assert _lots(1, 5) == [(third, third), (third, third),
                           (Decimal('2.333333333333333333333333334'), Decimal('2.333333333333333333333333334'))]
    assert _book_amount(1, 5) == Decimal('7')
    assert _lots_total(1, 5) == _book_amount(1, 5)      # the last lot took the remainder, not its own scaled share


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

    assert _lots(2, 4) == [(Decimal('3'), Decimal('1'))]
    assert _book_amount(2, 4) == Decimal('3')
    lot = JalAccount(2).open_trades_list(JalAsset(4))[0]
    assert (lot.open_price(), lot.p_adjustment()) == (Decimal('1000'), Decimal('0.9333333333333333333333333333'))


# ----------------------------------------------------------------------------------------------------------------------
# Partial consumption is a plain subtraction now. Dividing the taken quantity back by 'c_qty' to store the remainder
# in the lot's own units was the second rounding source, and left the lot holding 1999.999999999999999999999999.
def test_partial_consumption_subtracts_what_was_taken(prepare_db_fifo):
    JalAccount(1).set_data(AccountData.Precision, 18)
    create_stocks([('USDT', 'Stablecoin'), ('aEthUSDT', 'Lending receipt')], currency_id=2)
    t1, t2 = d2t(220101), d2t(220201)
    create_trades(1, [(t1, t1, 4, Decimal('2994.98'), Decimal('1'), Decimal('0'))])
    create_conversions(1, [(t1, 4, '2994.98', 5, '2999.321832'),
                           (t2, 5, '999.321832', 4, '999')])
    Ledger().rebuild(from_timestamp=0)

    assert _lots(1, 5) == [(Decimal('2000'), Decimal('1.001449703169971084948814349'))]
    assert _book_amount(1, 5) == Decimal('2000')      # 2999.321832 - 999.321832, exact in the books


# ----------------------------------------------------------------------------------------------------------------------
# A position whose account cannot represent the quantity it holds is described by two different numbers: the books
# round every posting to the account precision, the lot keeps all of its digits. It shows up on the disposal that
# closes the position - which either comes up short and stops the rebuild or leaves a dust lot nothing can consume -
# so a completed rebuild says so while the position is still just sitting there.
def test_rebuild_reports_a_position_its_account_cannot_hold(prepare_db_fifo, caplog):
    create_stocks([('NEAR', 'Near Protocol')], currency_id=2)   # bought on an account left at the default precision
    create_trades(1, [(d2t(220101), d2t(220101), 4, Decimal('29.0187'), Decimal('5'), Decimal('0'))])
    with caplog.at_level(logging.WARNING):
        Ledger().rebuild(from_timestamp=0)

    assert _lots_total(1, 4) == Decimal('29.0187')      # what was actually bought
    assert _book_amount(1, 4) == Decimal('29.02')       # what the books could hold of it
    warnings = [x.message for x in caplog.records if x.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "NEAR" in warnings[0] and "29.0187 vs 29.02" in warnings[0] and "precision 2" in warnings[0]


# ...and it stays quiet when the two agree, which is every position on an account that can hold what it bought.
def test_rebuild_is_quiet_when_lots_match_the_books(prepare_db_fifo, caplog):
    JalAccount(1).set_data(AccountData.Precision, 18)
    create_stocks([('NEAR', 'Near Protocol')], currency_id=2)
    create_trades(1, [(d2t(220101), d2t(220101), 4, Decimal('29.0187'), Decimal('5'), Decimal('0'))])
    with caplog.at_level(logging.WARNING):
        Ledger().rebuild(from_timestamp=0)

    assert _lots_total(1, 4) == _book_amount(1, 4)
    assert [x.message for x in caplog.records if x.levelno == logging.WARNING] == []
