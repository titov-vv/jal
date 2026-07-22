from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, create_assets, create_actions, create_trades, create_bridges, symbol_id_for
from constants import PredefinedAsset, PredefinedCategory, PredefinedAccountType
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.asset import JalAsset
from jal.db.db import JalDB
from jal.db.ledger import Ledger
from jal.db.operations import LedgerError

# Seeded currencies are RUB=1, USD=2, EUR=3; the first created asset gets id 4
ETH = 4
ACC1, ACC2, ACC_EUR = 1, 2, 3          # ACC1/ACC2 are USD, ACC_EUR is EUR


@pytest.fixture
def accounts(prepare_db):
    JalAccountCreator(currency_id=2, number='', name='Acc1', investing=1, organization=1,
                      account_type=PredefinedAccountType.Broker).commit()   # USD
    JalAccountCreator(currency_id=2, number='', name='Acc2', investing=1, organization=1,
                      account_type=PredefinedAccountType.Broker).commit()   # USD
    JalAccountCreator(currency_id=3, number='', name='AccEur', investing=1, organization=1,
                      account_type=PredefinedAccountType.Broker).commit()   # EUR
    create_assets([('ETH', 'Ethereum', '', 2, PredefinedAsset.Crypto, 0)])   # ID = 4
    create_actions([(d2t(210101), ACC1, 1, [(PredefinedCategory.StartingBalance, 100000.0)])])
    yield


def _amount(account_id) -> Decimal:
    return JalAccount(account_id).get_asset_amount(d2t(211231), ETH)


def _open_qty(account_id) -> Decimal:
    lots = JalAccount(account_id).open_trades_list(JalAsset(ETH))
    return sum((lot.open_qty(adjusted=True) for lot in lots), Decimal('0'))


def _open_basis(account_id) -> Decimal:
    lots = JalAccount(account_id).open_trades_list(JalAsset(ETH))
    return sum((lot.open_qty(adjusted=True) * lot.open_price(adjusted=True) for lot in lots), Decimal('0'))


def _closed_trade_count(account_id) -> int:
    return len(JalAccount(account_id).closed_trades_list(JalAsset(ETH)))   # default: only Trade-closed (real sales)


# A complete bridge carries the cost basis across chains and realizes no profit/loss (like a transfer).
def test_complete_bridge_carries_basis_with_no_pnl(accounts):
    create_trades(ACC1, [(d2t(210102), d2t(210102), ETH, 3.0, 1000.0, 0.0)])   # 3 ETH @1000, one lot
    create_bridges([{'asset': ETH, 'out_ts': d2t(210103), 'out_acc': ACC1, 'out_qty': 2,
                     'in_ts': d2t(210104), 'in_acc': ACC2, 'in_qty': 2}])
    Ledger().rebuild(from_timestamp=0)

    assert _amount(ACC1) == Decimal('1') and _open_qty(ACC1) == Decimal('1')
    assert _amount(ACC2) == Decimal('2') and _open_qty(ACC2) == Decimal('2')
    assert _open_basis(ACC2) == Decimal('2000')             # basis carried, not recomputed
    assert _closed_trade_count(ACC1) == 0 and _closed_trade_count(ACC2) == 0   # a bridge is not a taxable disposal


# A pending half - the sending leg alone, which is all an import can produce - removes the asset from the
# source (its value is parked in transit) and delivers nothing until its arrival is matched in.
def test_send_only_half_parks_value_in_transit(accounts):
    create_trades(ACC1, [(d2t(210102), d2t(210102), ETH, 3.0, 1000.0, 0.0)])
    create_bridges([{'asset': ETH, 'out_ts': d2t(210103), 'out_acc': ACC1, 'out_qty': 2}])   # in_* omitted
    Ledger().rebuild(from_timestamp=0)

    assert _amount(ACC1) == Decimal('1') and _open_qty(ACC1) == Decimal('1')   # the 2 ETH left the source
    assert _amount(ACC2) == Decimal('0') and _open_qty(ACC2) == Decimal('0')   # nothing arrived anywhere


def _fill_in_leg(oid, in_ts, in_acc, in_qty):
    JalDB._exec("UPDATE bridges SET in_timestamp=:ts, in_account_id=:acc, in_symbol_id=:sym, in_qty=:qty WHERE oid=:oid",
                [(":ts", in_ts), (":acc", in_acc), (":sym", symbol_id_for(ETH, JalAccount(in_acc).currency())),
                 (":qty", str(in_qty)), (":oid", oid)], commit=True)


# Matching a send-only half by filling its receive leg turns it into a complete bridge that carries the real basis.
def test_matching_send_then_receive_carries_basis(accounts):
    create_trades(ACC1, [(d2t(210102), d2t(210102), ETH, 3.0, 1000.0, 0.0)])
    oid = create_bridges([{'asset': ETH, 'out_ts': d2t(210103), 'out_acc': ACC1, 'out_qty': 2}])[0]
    Ledger().rebuild(from_timestamp=0)
    assert _open_qty(ACC2) == Decimal('0')                  # pending: nothing on the destination yet

    _fill_in_leg(oid, d2t(210104), ACC2, 2)                 # match: the receive leg arrives
    Ledger().rebuild(from_timestamp=0)
    assert _open_qty(ACC1) == Decimal('1')
    assert _open_qty(ACC2) == Decimal('2') and _open_basis(ACC2) == Decimal('2000')   # real carried basis


# An in-kind bridge fee (received less than sent) is disposed from the destination at basis - the arriving lot keeps
# the basis of exactly what arrived, the fee's basis goes to Costs, and no profit/loss is realized.
def test_in_kind_fee_disposed_at_basis(accounts):
    create_trades(ACC1, [(d2t(210102), d2t(210102), ETH, 3.0, 1000.0, 0.0)])
    create_bridges([{'asset': ETH, 'out_ts': d2t(210103), 'out_acc': ACC1, 'out_qty': 2,
                     'in_ts': d2t(210104), 'in_acc': ACC2, 'in_qty': '1.98'}])   # 0.02 ETH in-kind fee
    Ledger().rebuild(from_timestamp=0)

    assert _amount(ACC2) == Decimal('1.98') and _open_qty(ACC2) == Decimal('1.98')
    assert _open_basis(ACC2) == Decimal('1980')             # 1.98 * 1000, the fee (0.02*1000=20) went to Costs
    assert _closed_trade_count(ACC2) == 0                   # basis disposal, not a taxable deal


# Same-account bridges are forbidden (they would shadow a partially bridged lot in trades_opened).
def test_same_account_bridge_is_rejected(accounts):
    create_trades(ACC1, [(d2t(210102), d2t(210102), ETH, 3.0, 1000.0, 0.0)])
    create_bridges([{'asset': ETH, 'out_ts': d2t(210103), 'out_acc': ACC1, 'out_qty': 2,
                     'in_ts': d2t(210104), 'in_acc': ACC1, 'in_qty': 2}])
    with pytest.raises(LedgerError):
        Ledger().rebuild(from_timestamp=0)
