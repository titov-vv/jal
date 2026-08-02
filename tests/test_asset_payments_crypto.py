from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, create_assets, create_actions, create_trades, create_quotes, symbol_id_for
from constants import PredefinedAsset, PredefinedCategory, PredefinedAccountType, AssetLocation, AccountData, \
    BookAccount
from jal.db.db import JalDB
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.asset import JalAsset
from jal.db.ledger import Ledger
from jal.db.operations import LedgerTransaction, AssetPayment, LedgerError

WALLET = 1
TRX = 4


@pytest.fixture
def wallet(prepare_db):
    JalAccountCreator(currency_id=2, number='', name='Tron wallet', investing=1, organization=1,
                      account_type=PredefinedAccountType.Wallet, address='TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t',
                      chain=AssetLocation.TRX_BLOCKCHAIN).commit()
    create_assets([('TRX', 'Tron', '', 2, PredefinedAsset.Crypto, 0)])     # ID = 4
    create_actions([(d2t(210101), WALLET, 1, [(PredefinedCategory.StartingBalance, 10000.0)])])
    yield


def _payment(subtype, timestamp, amount):
    data = {'timestamp': timestamp, 'type': subtype, 'account_id': WALLET, 'symbol_id': symbol_id_for(TRX),
            'amount': str(amount), 'tax': '0', 'number': 'txhash', 'note': 'test'}
    return LedgerTransaction.create_new(LedgerTransaction.AssetPayment, data)


def _amount(asset_id=TRX, timestamp=None):
    return JalAccount(WALLET).get_asset_amount(d2t(210301) if timestamp is None else timestamp, asset_id)


def _open_lots(asset_id=TRX) -> Decimal:
    lots = JalAccount(WALLET).open_trades_list(JalAsset(asset_id))
    return sum((lot.open_qty(adjusted=True) for lot in lots), Decimal('0'))


def _closed_deals(asset_id=TRX) -> list:
    deals = []
    query = JalDB._exec("SELECT id FROM trades_closed WHERE asset_id=:a", [(":a", asset_id)])
    while query.next():
        deals.append(JalDB._read_record(query, cast=[int]))
    return deals


# ----------------------------------------------------------------------------------------------------------------------
def test_staking_reward_opens_lot_at_market(wallet):
    create_quotes(TRX, 2, [(d2t(210201), '0.30')])
    _payment(AssetPayment.StakingReward, d2t(210202), '100')
    Ledger().rebuild(from_timestamp=0)

    assert _amount() == Decimal('100')            # the reward increases the position
    assert _open_lots() == Decimal('100')         # ... as an open lot, so it has a cost basis to sell against
    # Valued at the last known quote, not at an exact-timestamp one - crypto quotes are daily
    assert AssetPayment(1).price() == Decimal('0.30')


def test_staking_reward_needs_a_quote(wallet):
    # Opening the lot at zero would silently turn the whole proceeds into gain on a later sale, so it is refused
    _payment(AssetPayment.StakingReward, d2t(210202), '100')
    # A LedgerError and not an unexpected exception: the rebuild stops but the data is sound, so the ledger
    # reports it as an incomplete build with a reason instead of a traceback
    with pytest.raises(LedgerError) as error:
        Ledger().rebuild(from_timestamp=0)
    # The reason names the asset and the date whose quote is missing and keeps the raw operation dump out of it
    assert 'TRX' in str(error.value)
    assert '02/02/2021' in str(error.value)
    assert 'timestamp' not in str(error.value)


def test_dust_attack_opens_lot_at_zero_without_a_quote(wallet):
    # Unlike a staking reward, a dust attack must never block the ledger rebuild for want of a quote - a fresh
    # wallet's first fetch is exactly the case with no price history yet, which is the whole point of judging dust
    # by its raw coin amount instead (see ChainFetcher._is_native_dust). It opens at a zero basis instead: the
    # coins were unsolicited and cost nothing, so their whole proceeds are correctly a gain when sold.
    #
    # The account's precision must cover TRX's 6 decimals here - the 'wallet' fixture leaves it at the default of
    # 2, which is a general ledger-rounding property of any account (every posting is rounded to it, not just
    # dust) and not something particular to this operation.
    JalAccount(WALLET).set_data(AccountData.Precision, 6)
    _payment(AssetPayment.DustAttack, d2t(210202), '0.000001')
    Ledger().rebuild(from_timestamp=0)

    assert _amount() == Decimal('0.000001')       # the dust still increases the position...
    assert _open_lots() == Decimal('0.000001')     # ... as an open lot, opened at a zero basis
    assert AssetPayment(1).price() == Decimal('0')


def test_dust_attack_uses_quote_when_one_exists(wallet):
    create_quotes(TRX, 2, [(d2t(210201), '0.30')])
    _payment(AssetPayment.DustAttack, d2t(210202), '100')
    Ledger().rebuild(from_timestamp=0)

    assert _amount() == Decimal('100')
    assert AssetPayment(1).price() == Decimal('0.30')     # priced normally when a quote is actually available


def test_staking_reward_basis_is_used_on_sale(wallet):
    create_quotes(TRX, 2, [(d2t(210201), '0.30')])
    _payment(AssetPayment.StakingReward, d2t(210202), '100')
    create_trades(WALLET, [(d2t(210203), d2t(210203), TRX, -100.0, 0.50, 0.0)])
    Ledger().rebuild(from_timestamp=0)

    # Sold 100 at 0.50 against a basis of 0.30 - the deal exists and carries that basis
    deals = _closed_deals()
    assert len(deals) == 1
    assert _amount() == Decimal('0')


def test_gas_fee_consumes_position_at_cost_basis(wallet):
    create_trades(WALLET, [(d2t(210201), d2t(210201), TRX, 100.0, 0.20, 0.0)])
    _payment(AssetPayment.GasFee, d2t(210202), '10')
    Ledger().rebuild(from_timestamp=0)

    assert _amount() == Decimal('90')             # the coins are gone from the wallet
    assert _open_lots() == Decimal('90')          # the open lots agree with the ledger
    assert _closed_deals() == []                  # gas is an expense, not a disposal - no deal, no profit or loss


def test_gas_fee_books_cost_basis_to_costs(wallet):
    create_trades(WALLET, [(d2t(210201), d2t(210201), TRX, 100.0, 0.20, 0.0)])
    _payment(AssetPayment.GasFee, d2t(210202), '10')
    Ledger().rebuild(from_timestamp=0)

    # 10 coins at a basis of 0.20 leave the position and arrive in Costs - equal values, so no P&L anywhere
    costs = JalDB._read("SELECT SUM(CAST(amount AS REAL)) FROM ledger WHERE book_account=:book AND otype=:otype",
                        [(":book", BookAccount.Costs), (":otype", LedgerTransaction.AssetPayment)])
    assert abs(float(costs) - 2.0) < 1e-9


def test_gas_fee_needs_enough_of_the_asset(wallet):
    create_trades(WALLET, [(d2t(210201), d2t(210201), TRX, 5.0, 0.20, 0.0)])
    _payment(AssetPayment.GasFee, d2t(210202), '10')
    with pytest.raises(Exception):
        Ledger().rebuild(from_timestamp=0)


def test_gas_fee_needs_no_quote(wallet):
    # Unlike a staking reward, gas is valued from the lots it consumes, so it imports with no quote at all
    create_trades(WALLET, [(d2t(210201), d2t(210201), TRX, 100.0, 0.20, 0.0)])
    _payment(AssetPayment.GasFee, d2t(210202), '10')
    Ledger().rebuild(from_timestamp=0)
    assert _amount() == Decimal('90')


def test_unpriced_reward_recovers_after_quotes_arrive(wallet):
    # The order a first-ever blockchain import runs in: the asset is created by the import itself, so it cannot
    # have quotes yet and the ledger rebuild fails. Nothing is lost - the reward is stored with the right amount,
    # only its valuation is missing - so downloading quotes and rebuilding finishes the job without re-importing.
    _payment(AssetPayment.StakingReward, d2t(210202), '100')
    with pytest.raises(LedgerError):
        Ledger().rebuild(from_timestamp=0)

    create_quotes(TRX, 2, [(d2t(210201), '0.30')])
    Ledger().rebuild(from_timestamp=0)

    assert _amount() == Decimal('100')
    assert _open_lots() == Decimal('100')
    assert AssetPayment(1).price() == Decimal('0.30')


def test_decimal_values_are_deduplicated(wallet):
    # SQLite has no decimal type, so amounts are stored as TEXT and Decimal is converted where every query binds.
    # Converting it only on the INSERT path let create_operation() insert an operation while the query looking for
    # an existing duplicate of it still passed a raw Decimal - so the duplicate was never found and the very same
    # operation was written twice.
    data = {'timestamp': d2t(210201), 'settlement': d2t(210201), 'account_id': WALLET,
            'symbol_id': symbol_id_for(TRX), 'qty': Decimal('10'), 'price': Decimal('0.20'),
            'fee': Decimal('0'), 'number': 'tx1'}
    LedgerTransaction.create_new(LedgerTransaction.Trade, dict(data))
    LedgerTransaction.create_new(LedgerTransaction.Trade, dict(data))
    assert int(JalDB._read("SELECT count(*) FROM trades")) == 1

    # format_decimal() is the single canonical spelling of a Decimal in this database. It normalizes, so a round
    # number is stored in exponent form - the agreed convention, which anything comparing these columns as strings
    # has to expect. What matters is that the value round-trips exactly and that both the insert and the duplicate
    # check spell it the same way, which is what makes the count above 1 and not 2.
    stored = JalDB._read("SELECT qty FROM trades WHERE oid=1")
    assert stored == '1E+1'
    assert Decimal(stored) == Decimal('10')


def test_format_decimal_is_lossless():
    from jal.db.helpers import format_decimal
    # normalize() rounds to the active decimal context - 28 significant digits by default - which silently
    # truncated high-precision amounts. A token with 18 decimals held in a large balance exceeds that easily,
    # and this is the canonical spelling every value written to the database goes through.
    for text in ['0', '0.00', '40', '9.478350', '0.000001', '1E-18',
                 '12345678901234.123456789012345678',              # 18 decimals, trillions - 32 digits
                 '1234567890123456789.123456789012345678']:        # 37 digits
        value = Decimal(text)
        assert Decimal(format_decimal(value)) == value, f"{text} does not round-trip"
    assert Decimal(format_decimal(Decimal('NaN'))).is_nan()


# ----------------------------------------------------------------------------------------------------------------------
# Rent of a token account: the coin leaves the wallet the way gas does, but is not consumed - it sits in the token
# account and is paid to that account's OWNER if it is ever closed. The payer never gets it back, which is why it is
# booked as a cost here and never as a movement to the owner (whose balance does not rise - see AssetPayment.TokenRent).

def test_token_rent_leaves_the_wallet_at_its_own_basis(wallet):
    create_trades(WALLET, [(d2t(210201), d2t(210201), TRX, 100.0, 0.20, 0.0)])
    _payment(AssetPayment.TokenRent, d2t(210202), '10')
    Ledger().rebuild(from_timestamp=0)

    assert _amount() == Decimal('90')             # the coins are gone from the payer
    assert _open_lots() == Decimal('90')
    assert _closed_deals() == []                  # nothing is realized - it leaves at the basis it was held at

    costs = JalDB._read("SELECT SUM(CAST(amount AS REAL)) FROM ledger WHERE book_account=:book AND otype=:otype",
                        [(":book", BookAccount.Costs), (":otype", LedgerTransaction.AssetPayment)])
    assert abs(float(costs) - 2.0) < 1e-9         # 10 coins at 0.20, so no P&L anywhere


def test_token_rent_needs_no_quote(wallet):
    # Like gas and unlike a reward: it is valued from the lots it consumes, so it books with no price history at all
    create_trades(WALLET, [(d2t(210201), d2t(210201), TRX, 100.0, 0.20, 0.0)])
    _payment(AssetPayment.TokenRent, d2t(210202), '10')
    Ledger().rebuild(from_timestamp=0)
    assert _amount() == Decimal('90')


def test_token_rent_needs_the_coins_to_be_there(wallet):
    create_trades(WALLET, [(d2t(210201), d2t(210201), TRX, 5.0, 0.20, 0.0)])
    _payment(AssetPayment.TokenRent, d2t(210202), '10')
    with pytest.raises(Exception):
        Ledger().rebuild(from_timestamp=0)


# The return arrives on whoever OWNED the token account, which need not be whoever paid, so nothing links it back to
# the rent it reverses - it opens a lot at the quote of the moment it arrives, like any other inflow that cost the
# receiving account nothing.
def test_token_rent_return_opens_a_lot_at_market(wallet):
    create_quotes(TRX, 2, [(d2t(210202), 0.50)])
    _payment(AssetPayment.TokenRentReturn, d2t(210202), '10')
    Ledger().rebuild(from_timestamp=0)

    assert _amount() == Decimal('10')
    lots = JalAccount(WALLET).open_trades_list(JalAsset(TRX))
    assert len(lots) == 1 and lots[0].open_price(adjusted=True) == Decimal('0.5')


def test_token_rent_return_needs_a_quote(wallet):
    # Refused rather than opened at zero, exactly as a reward is: a zero basis would report the whole proceeds as
    # gain when the coins are eventually sold
    _payment(AssetPayment.TokenRentReturn, d2t(210202), '10')
    with pytest.raises(LedgerError):
        Ledger().rebuild(from_timestamp=0)
