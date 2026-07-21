from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, create_assets, create_actions, create_trades, symbol_id_for
from constants import PredefinedAsset, PredefinedCategory, PredefinedAccountType
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.asset import JalAsset
from jal.db.ledger import Ledger
from jal.db.operations import LedgerTransaction

# Seeded currencies are RUB=1, USD=2, EUR=3; the first created asset gets id 4
USDT = 4
ORIGIN, MID, DEST = 1, 2, 3      # ORIGIN(RUB) -> MID(USD) -> DEST(EUR): every leg crosses a currency boundary


@pytest.fixture
def accounts(prepare_db):
    JalAccountCreator(currency_id=1, number='', name='Origin', investing=1, organization=1,
                      account_type=PredefinedAccountType.Broker).commit()
    JalAccountCreator(currency_id=2, number='', name='Mid', investing=1, organization=1,
                      account_type=PredefinedAccountType.Broker).commit()
    JalAccountCreator(currency_id=3, number='', name='Dest', investing=1, organization=1,
                      account_type=PredefinedAccountType.Broker).commit()
    create_assets([('USDT', 'Tether USD', '', 2, PredefinedAsset.Crypto, 0)])   # ID = 4
    create_actions([(d2t(210101), ORIGIN, 1, [(PredefinedCategory.StartingBalance, 10000.0)])])
    yield


def _transfer(from_account, to_account, asset_id, amount, deposit, timestamp):
    data = {'withdrawal_timestamp': timestamp, 'withdrawal_account': from_account, 'withdrawal': str(amount),
            'deposit_timestamp': timestamp, 'deposit_account': to_account, 'deposit': str(deposit),
            'symbol_id': symbol_id_for(asset_id)}
    return LedgerTransaction.create_new(LedgerTransaction.Transfer, data)


def _amount(account_id, asset_id) -> Decimal:
    return JalAccount(account_id).get_asset_amount(d2t(210201), asset_id)


# Reproduces the DivisionUndefined crash of processAssetTransfer's incoming leg: an asset received with its cost
# basis left as zero (as fetched blockchain transfers are) is later moved out to an account of a DIFFERENT currency.
# The incoming leg divides the destination value by the withdrawn value, which is zero here, so without the guard
# the whole ledger rebuild aborts before the user can fill the cost in.
def test_cross_currency_transfer_of_zero_cost_asset_rebuilds(accounts):
    create_trades(ORIGIN, [(d2t(210102), d2t(210102), USDT, 490.0, 1.0, 0.0)])   # a real, priced lot at the origin
    _transfer(ORIGIN, MID, USDT, 490, 0, d2t(210103))     # received with cost basis left at zero
    _transfer(MID, DEST, USDT, 490, 0, d2t(210104))       # moved cross-currency (USD -> EUR)

    Ledger().rebuild(from_timestamp=0)                    # must not raise DivisionUndefined

    assert _amount(MID, USDT) == Decimal('0')
    assert _amount(DEST, USDT) == Decimal('490')
    # The zero-cost lot arrives still zero-cost - nothing was conjured out of the empty cost basis
    lots = JalAccount(DEST).open_trades_list(JalAsset(USDT))
    total_value = sum((lot.open_qty(adjusted=True) * lot.open_price(adjusted=True) for lot in lots), Decimal('0'))
    assert total_value == Decimal('0')
