from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, create_assets, create_actions, create_quotes, create_trades
from constants import PredefinedAsset, PredefinedCategory, PredefinedAccountType, AssetLocation
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.asset import JalAsset
from jal.db.cost_basis import carried_basis, STALE_RATE_LIMIT
from jal.db.ledger import Ledger

# ----------------------------------------------------------------------------------------------------------------------
# What a quantity of an asset cost the account holding it - the read-only twin of the FIFO the ledger performs.
#
# It is asked before anything is written, which is the whole point: an operation that has not been recorded yet has
# no value in the ledger to read back, and the cost basis a cross-currency transfer needs has to be decided (and may
# have to be corrected) BEFORE it becomes a row. So the answer must match what the rebuild would compute afterwards,
# and where it can't be sure - lots too small, no rate, a rate from another time - it has to say so rather than
# return a number that looks like every other one.

USDT = 4
WALLET, OTHER = 1, 2
USD, EUR = 2, 3


@pytest.fixture
def funded(prepare_db):
    JalAccountCreator(currency_id=USD, number='', name='USD wallet', investing=1, organization=1,
                      account_type=PredefinedAccountType.Wallet, address='0x' + '1' * 40,
                      chain=AssetLocation.ETH_BLOCKCHAIN).commit()
    JalAccountCreator(currency_id=EUR, number='', name='EUR wallet', investing=1, organization=1,
                      account_type=PredefinedAccountType.Wallet, address='0x' + '2' * 40,
                      chain=AssetLocation.ETH_BLOCKCHAIN).commit()
    create_assets([('USDT', 'Tether USD', '', USD, PredefinedAsset.Crypto, 0)])   # ID = USDT
    create_actions([(d2t(210101), WALLET, 1, [(PredefinedCategory.StartingBalance, 10000.0)])])
    yield


def _basis(qty, timestamp=d2t(210201), account=WALLET, currency=USD) -> dict:
    return carried_basis(JalAccount(account), JalAsset(USDT), Decimal(str(qty)), timestamp, currency)


def test_the_basis_is_what_was_paid_for_the_quantity(funded):
    create_trades(WALLET, [(d2t(210102), d2t(210102), USDT, 1000.0, 1.05, 0.0)])
    Ledger().rebuild(from_timestamp=0)

    basis = _basis(400)

    assert basis['qty'] == Decimal('400') and basis['short'] == Decimal('0')
    assert basis['basis'] == Decimal('420')            # 400 of a lot that cost 1.05 each
    assert basis['lots'] == 1
    assert basis['complete'] is True


# The quantity is taken lot by lot in the order they were opened, exactly as _close_deals_fifo() takes it - a basis
# computed on the average or on the newest lot would disagree with what the rebuild books afterwards.
def test_the_lots_are_taken_in_fifo_order(funded):
    create_trades(WALLET, [(d2t(210102), d2t(210102), USDT, 100.0, 1.0, 0.0),
                           (d2t(210103), d2t(210103), USDT, 100.0, 2.0, 0.0)])
    Ledger().rebuild(from_timestamp=0)

    basis = _basis(150)

    assert basis['basis'] == Decimal('200')            # 100 at 1.00, then 50 at 2.00
    assert basis['lots'] == 2


# The lots as they stood at the moment asked about, not as they stand now: an operation is booked where it belongs
# in time, and what was bought after it is not there to pay for it.
def test_only_the_lots_of_that_moment_are_counted(funded):
    create_trades(WALLET, [(d2t(210102), d2t(210102), USDT, 100.0, 1.0, 0.0),
                           (d2t(210110), d2t(210110), USDT, 100.0, 2.0, 0.0)])
    Ledger().rebuild(from_timestamp=0)

    basis = _basis(150, timestamp=d2t(210105))

    assert basis['qty'] == Decimal('100') and basis['short'] == Decimal('50')
    assert basis['basis'] == Decimal('100')


# An account that never held enough is the shape that matters most: recording the operation anyway raises inside the
# rebuild and stops it, so the shortfall has to be visible before that.
def test_a_quantity_the_lots_cannot_cover_is_reported_as_short(funded):
    create_trades(WALLET, [(d2t(210102), d2t(210102), USDT, 100.0, 1.0, 0.0)])
    Ledger().rebuild(from_timestamp=0)

    basis = _basis(400)

    assert basis['short'] == Decimal('300')
    assert basis['complete'] is False


def test_an_account_that_never_held_the_asset_is_short_of_all_of_it(funded):
    basis = _basis(400, account=OTHER)

    assert basis['qty'] == Decimal('0') and basis['short'] == Decimal('400')
    assert basis['basis'] == Decimal('0')
    assert basis['complete'] is False


# ----------------------------------------------------------------------------------------------------------------------
# The other half of the answer: what that basis amounts to in the currency the asset arrives in

def test_the_basis_is_restated_in_the_currency_asked_for(funded):
    create_trades(WALLET, [(d2t(210102), d2t(210102), USDT, 1000.0, 1.0, 0.0)])
    create_quotes(USD, EUR, [(d2t(210201), 0.5)])
    Ledger().rebuild(from_timestamp=0)

    basis = _basis(400, currency=EUR)

    assert basis['basis'] == Decimal('400')            # what the sending account paid, in its own currency
    assert basis['currency'] == USD
    assert basis['rate'] == Decimal('0.5')
    assert basis['value'] == Decimal('200')            # ... and what that is in the currency it arrives in
    assert basis['complete'] is True


def test_one_currency_at_both_ends_needs_no_rate(funded):
    create_trades(WALLET, [(d2t(210102), d2t(210102), USDT, 1000.0, 1.0, 0.0)])
    Ledger().rebuild(from_timestamp=0)

    basis = _basis(400, currency=USD)

    assert basis['rate'] == Decimal('1') and basis['value'] == basis['basis']
    assert basis['stale'] is False and basis['complete'] is True


# Nothing is invented when there is no rate: the value is zero and 'complete' says the answer isn't one, which is
# what stops it from being offered as a default and leaves the number to the user.
def test_a_missing_rate_is_reported_rather_than_guessed(funded):
    create_trades(WALLET, [(d2t(210102), d2t(210102), USDT, 1000.0, 1.0, 0.0)])
    Ledger().rebuild(from_timestamp=0)

    basis = _basis(400, currency=EUR)

    assert basis['rate_timestamp'] == 0 and basis['rate'] == Decimal('0')
    assert basis['complete'] is False


# JalAsset.quote() answers with the newest rate at or before the date it is asked about and says nothing about how
# old that is - a series that ended years ago answers as confidently as one published this morning. The age is
# therefore part of the answer here, and an answer that old is not offered as a default.
def test_a_rate_from_another_time_is_marked_stale(funded):
    create_trades(WALLET, [(d2t(210102), d2t(210102), USDT, 1000.0, 1.0, 0.0)])
    create_quotes(USD, EUR, [(d2t(210101), 0.5)])
    Ledger().rebuild(from_timestamp=0)

    fresh = _basis(400, timestamp=d2t(210103), currency=EUR)
    stale = _basis(400, timestamp=d2t(210301), currency=EUR)

    assert fresh['stale'] is False and fresh['complete'] is True
    assert stale['stale'] is True and stale['complete'] is False
    assert stale['value'] == Decimal('200')            # still computed - it is the user's to accept or replace
    assert (d2t(210301) - stale['rate_timestamp']) > STALE_RATE_LIMIT


# A pair that has no rate of its own is answered by dividing the two rates of its halves against the base currency,
# and that answer is dated to the moment it was asked about - so a rate made out of a series that ended years ago
# looks exactly like one published that day. Measured on real data, a RUB -> USD rate built this way in May 2025
# came from March 2022, the last month the ECB published RUB, and valued the transfer a fifth below what it was
# worth. It is therefore dated by the older of the two rates it was made of.
def test_a_rate_built_from_two_others_is_as_old_as_the_older_one(funded):
    RUB = 1                                            # the base currency of the database the fixture creates
    create_trades(WALLET, [(d2t(210102), d2t(210102), USDT, 1000.0, 1.0, 0.0)])
    create_quotes(USD, RUB, [(d2t(210101), 70.0)])     # the last USD rate there is ...
    create_quotes(EUR, RUB, [(d2t(210301), 85.0)])     # ... while the other half of the pair is current
    Ledger().rebuild(from_timestamp=0)

    basis = _basis(400, timestamp=d2t(210301), currency=EUR)

    assert basis['rate'] > Decimal('0')                # the rate is still computed - it is all there is
    assert basis['rate_timestamp'] == d2t(210101)      # ... and dated by the half that stopped being published
    assert basis['stale'] is True and basis['complete'] is False


# The same, for the commonest pair of all: when one side IS the base currency the rate is one divided by the other
# side's stored rate, so the whole age of the answer sits in that other side. (With EUR as the base currency, that
# is every EUR -> USD conversion.) The base's own half is a constant one and never dates anything.
def test_a_rate_against_the_base_currency_is_dated_by_the_other_side(funded):
    RUB = 1                                            # the base currency of the database the fixture creates
    JalAccountCreator(currency_id=RUB, number='', name='RUB broker', investing=1, organization=1,
                      account_type=PredefinedAccountType.Broker).commit()
    create_trades(3, [(d2t(210102), d2t(210102), USDT, 1000.0, 80.0, 0.0)])
    create_quotes(USD, RUB, [(d2t(210101), 70.0)])     # the last USD rate, and nothing after it
    Ledger().rebuild(from_timestamp=0)

    basis = _basis(400, timestamp=d2t(210301), account=3, currency=USD)

    assert basis['basis'] == Decimal('32000')          # what the RUB account paid, in RUB
    assert basis['rate'] > Decimal('0')
    assert basis['rate_timestamp'] == d2t(210101)      # dated by the USD/RUB row, not by the moment asked about
    assert basis['stale'] is True and basis['complete'] is False
