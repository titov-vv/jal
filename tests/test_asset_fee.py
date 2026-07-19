from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, create_assets, create_actions, create_trades, symbol_id_for
from constants import PredefinedAsset, PredefinedCategory, PredefinedAccountType, AssetLocation
from jal.db.db import JalDB
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.asset import JalAsset
from jal.db.ledger import Ledger
from jal.db.operations import LedgerTransaction, Transfer

# Two wallet accounts on the same chain - gas is paid out of the one the transfer leaves from
WALLET_A, WALLET_B = 1, 2
TRX, USDT = 4, 5     # asset ids created by the fixture, right after the three seeded currencies


@pytest.fixture
def wallets(prepare_db):
    JalAccountCreator(currency_id=2, number='', name='Wallet A', investing=1, organization=1,
                      account_type=PredefinedAccountType.Wallet, address='TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t',
                      chain=AssetLocation.TRX_BLOCKCHAIN).commit()
    JalAccountCreator(currency_id=2, number='', name='Wallet B', investing=1, organization=1,
                      account_type=PredefinedAccountType.Wallet, address='TMuA6YqfCeX8EhbfYEg5y7S4DqzSJireY9',
                      chain=AssetLocation.TRX_BLOCKCHAIN).commit()
    create_assets([
        ('TRX', 'Tron', '', 2, PredefinedAsset.Crypto, 0),        # ID = 4
        ('USDT', 'Tether USD', '', 2, PredefinedAsset.Crypto, 0)  # ID = 5
    ])
    create_actions([(d2t(210101), WALLET_A, 1, [(PredefinedCategory.StartingBalance, 10000.0)])])
    yield


def _buy(account_id, timestamp, asset_id, qty, price):
    # Amounts are passed as floats, the way every other test builds trades - Decimal doesn't bind as a query parameter
    create_trades(account_id, [(timestamp, timestamp, asset_id, float(qty), float(price), 0.0)])


def _transfer(asset_id, amount, timestamp, fee=None, fee_asset=None):
    data = {'withdrawal_timestamp': timestamp, 'withdrawal_account': WALLET_A, 'withdrawal': str(amount),
            'deposit_timestamp': timestamp, 'deposit_account': WALLET_B, 'deposit': str(amount),
            'symbol_id': symbol_id_for(asset_id)}
    if fee is not None:
        data['fee_account'] = WALLET_A
        data['fee'] = str(fee)
        if fee_asset is not None:
            data['fee_symbol_id'] = symbol_id_for(fee_asset)
    return LedgerTransaction.create_new(LedgerTransaction.Transfer, data)


def _amount(account_id, asset_id, timestamp=None) -> Decimal:
    return JalAccount(account_id).get_asset_amount(d2t(210201) if timestamp is None else timestamp, asset_id)


# Total quantity held in the open FIFO lots of an account. It must always agree with the ledger amount - they are
# two independent stores of the same position, and a disposal that updates one but not the other breaks cost basis
# for every later operation without changing any visible balance.
def _open_lots(account_id: int, asset_id: int) -> Decimal:
    lots = JalAccount(account_id).open_trades_list(JalAsset(asset_id))
    return sum((lot.open_qty(adjusted=True) for lot in lots), Decimal('0'))


def _closed_deals_of(asset_id: int) -> list:
    deals = []
    query = JalDB._exec("SELECT id FROM trades_closed WHERE asset_id=:asset", [(":asset", asset_id)])
    while query.next():
        deals.append(JalDB._read_record(query, cast=[int]))
    return deals


# ----------------------------------------------------------------------------------------------------------------------
def test_gas_fee_in_another_asset(wallets):
    # 100 TRX and 1000 USDT held; 500 USDT is moved out paying 10 TRX of gas
    _buy(WALLET_A, d2t(210102), TRX, 100, '0.20')
    _buy(WALLET_A, d2t(210102), USDT, 1000, '1.00')
    _transfer(USDT, 500, d2t(210103), fee=10, fee_asset=TRX)
    Ledger().rebuild(from_timestamp=0)

    # The gas leaves the TRX position of the sending wallet and not the USDT one that is being transferred
    assert _amount(WALLET_A, TRX) == Decimal('90')
    assert _amount(WALLET_A, USDT) == Decimal('500')
    assert _amount(WALLET_B, USDT) == Decimal('500')
    assert _amount(WALLET_B, TRX) == Decimal('0')      # gas never travels to the destination


def test_gas_fee_creates_no_deal(wallets):
    _buy(WALLET_A, d2t(210102), TRX, 100, '0.20')
    _buy(WALLET_A, d2t(210102), USDT, 1000, '1.00')
    _transfer(USDT, 500, d2t(210103), fee=10, fee_asset=TRX)
    Ledger().rebuild(from_timestamp=0)

    # Gas is an expense and not a disposal, so it leaves no closed deal and realizes no profit or loss
    assert _closed_deals_of(TRX) == []


def test_gas_fee_in_the_transferred_asset(wallets):
    # The case that an unguarded implementation double counts: TRX is transferred AND the gas is TRX, from the
    # same account. A deal recorded for the fee would be indistinguishable from the transfer's own deal - same
    # operation, account and asset - and would be re-opened at the destination along with it.
    _buy(WALLET_A, d2t(210102), TRX, 100, '0.20')
    _transfer(TRX, 50, d2t(210103), fee=10, fee_asset=TRX)
    Ledger().rebuild(from_timestamp=0)

    assert _amount(WALLET_A, TRX) == Decimal('40')     # 100 - 50 transferred - 10 burned
    assert _amount(WALLET_B, TRX) == Decimal('50')     # exactly the transferred amount, not 60
    # The ledger amount alone doesn't catch this: it is the open lots that get corrupted. Recording a deal for the
    # fee makes the incoming leg re-open the fee's lot over the transfer's, leaving the destination with 10 units of
    # cost basis behind a balance of 50 - invisible until something is sold out of that account.
    assert _open_lots(WALLET_A, TRX) == Decimal('40')
    assert _open_lots(WALLET_B, TRX) == Decimal('50')


def test_gas_fee_is_shown_in_its_own_asset(wallets):
    _buy(WALLET_A, d2t(210102), TRX, 100, '0.20')
    _buy(WALLET_A, d2t(210102), USDT, 1000, '1.00')
    _transfer(USDT, 500, d2t(210103), fee=10, fee_asset=TRX)
    Ledger().rebuild(from_timestamp=0)

    fee = Transfer(1, Transfer.Fee)
    assert fee.value_currency() == 'TRX'               # the asset the fee was paid in, not the account currency
    assert fee.value_change() == [Decimal('-10')]


def test_money_fee_is_unaffected(wallets):
    # A transfer whose fee is an ordinary money amount must keep behaving exactly as it did before
    _buy(WALLET_A, d2t(210102), USDT, 1000, '1.00')
    _transfer(USDT, 500, d2t(210103), fee=3)
    Ledger().rebuild(from_timestamp=0)

    fee = Transfer(1, Transfer.Fee)
    assert fee.value_currency() == 'USD'               # the currency of the fee account
    assert _amount(WALLET_A, USDT) == Decimal('500')
