from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_taxes
from tests.helpers import d2t, create_assets, create_actions, create_quotes, create_trades, create_transfers, \
    create_conversions, create_bridges, create_swaps, create_cross_chain_swaps, create_corporate_actions, \
    create_stock_dividends, symbol_id_for
from tests.test_lot_decisions import lots, USD_ACC, EUR_ACC, A, B, GAS, S, T, T1, T2, T3, T4
from jal.constants import SwapTreatment
from jal.db.db import JalDB
from jal.db.ledger import Ledger
from jal.db.lots import ScratchLotStore, replay
from jal.db.operations import LedgerTransaction, AssetIncome, CorporateAction

OPENED = "id, timestamp, otype, oid, m_otype, m_oid, account_id, asset_id, price, remaining_qty, c_price, c_qty, c_fx, " \
         "slice_id, acquired"
CLOSED = "id, account_id, asset_id, open_otype, open_oid, open_timestamp, open_price, open_qty, close_otype, " \
         "close_oid, close_timestamp, close_price, close_qty, c_price, c_qty, c_fx"


def _rows(table, columns, schema='main') -> list:
    return JalDB._read_to_list(f"SELECT {columns} FROM {schema}.{table} ORDER BY id")


# The default replay of the built ledger writes the same lots and deals as the rebuild did, row for row
def _assert_replay_equal():
    Ledger().rebuild(from_timestamp=0)
    store = ScratchLotStore()
    try:
        replay(store)
        assert _rows('trades_opened', OPENED, store.schema()) == _rows('trades_opened', OPENED)
        assert _rows('trades_closed', CLOSED, store.schema()) == _rows('trades_closed', CLOSED)
    finally:
        store.detach()


# Every lot path at once: trades and a covered short, transfers across currencies, a pending arrival, a wrapping with gas,
# a bridge with an in-kind fee, sale and conversion swaps on one chain and across, a spin-off, incomes
def test_replay_reproduces_every_lot_path(lots):
    create_quotes(A, 2, [(T2, 120), (T3, 125)])
    create_quotes(B, 2, [(T3, 60)])
    create_trades(USD_ACC, [(T1, T1, GAS, 5, 10, 0, "buy-GAS"), (T1, T1, S, 10, 50, 0, "buy-S"),
                            (T2, T2, A, -2, 130, 0, "sell-A"), (T2, T2, T, -4, 20, 0, "short-T"),
                            (T3, T3, T, 4, 18, 0, "cover-T")])
    create_transfers([(T2, USD_ACC, 3, EUR_ACC, 290, A)])
    LedgerTransaction.create_new(LedgerTransaction.Transfer, {
        'withdrawal_timestamp': T2, 'withdrawal_account': None, 'withdrawal': '7', 'deposit_timestamp': T2,
        'deposit_account': EUR_ACC, 'deposit': '0', 'number': '', 'symbol_id': symbol_id_for(B)})
    create_conversions(USD_ACC, [(T3, A, 2, B, 4, GAS, 0.5)])
    create_bridges([{'asset': B, 'out_ts': T3, 'out_acc': USD_ACC, 'out_qty': 4, 'in_ts': T4, 'in_acc': EUR_ACC,
                     'in_qty': 3.5}])
    create_swaps(USD_ACC, [(T3, A, 1, B, 2)])
    create_swaps(USD_ACC, [(T3, A, 1, B, 2)], treatment=SwapTreatment.Conversion)
    create_cross_chain_swaps([{'ts': T3, 'acc': USD_ACC, 'out_asset': A, 'out_qty': 1, 'in_ts': T4, 'in_acc': EUR_ACC,
                               'in_asset': B, 'in_qty': 2},
                              {'ts': T3, 'acc': USD_ACC, 'out_asset': GAS, 'out_qty': 1, 'in_ts': T4,
                               'in_acc': EUR_ACC, 'in_asset': B, 'in_qty': 2, 'treatment': SwapTreatment.Conversion}])
    create_corporate_actions(USD_ACC, [(T4, CorporateAction.SpinOff, S, 12, 'spin-off', [(S, 12, 0.8), (T, 6, 0.2)])])
    create_stock_dividends([(AssetIncome.StockDividend, T2, USD_ACC, S, 2, 2, 55, 0, "dividend")])
    LedgerTransaction.create_new(LedgerTransaction.AssetIncome, {
        'timestamp': T2, 'type': AssetIncome.Reward, 'account_id': USD_ACC, 'symbol_id': symbol_id_for(GAS),
        'amount': Decimal('3'), 'tax': Decimal('0'), 'note': 'reward'})
    _assert_replay_equal()


# The tax fixture: a long real history of trades, corporate actions, transfers and bonds
def test_replay_reproduces_the_tax_fixture(prepare_db_taxes):
    _assert_replay_equal()
