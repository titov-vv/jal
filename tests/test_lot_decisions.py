from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, symbol_id_for, operation_id, create_assets, create_actions, create_quotes, \
    create_trades, create_transfers, create_conversions, create_bridges, create_swaps, create_corporate_actions, \
    create_stock_dividends
from jal.constants import PredefinedAsset, PredefinedCategory, PredefinedAccountType, SwapTreatment
from jal.db.db import JalDB
from jal.db.account import JalAccountCreator
from jal.db.ledger import Ledger
from jal.db.operations import LedgerTransaction, AssetIncome, CorporateAction

# Characterization of the lot rows each lot decision writes today, as stored TEXT
USD_ACC, EUR_ACC = 1, 2
A, B, GAS, S, T = 4, 5, 6, 7, 8
TRADE, TRANSFER, CONV, SWAP = LedgerTransaction.Trade, LedgerTransaction.Transfer, LedgerTransaction.Conversion, \
    LedgerTransaction.Swap
T0, T1, T2, T3, T4 = d2t(250101), d2t(250102), d2t(250110), d2t(250120), d2t(250201)


# A USD and a EUR account; coins A, B, GAS and stocks S, T; 10 A bought at 100 USD + 10 fee
@pytest.fixture
def lots(prepare_db):
    JalAccountCreator(currency_id=2, number='', name='Acc USD', investing=1, organization=1,
                      account_type=PredefinedAccountType.Broker).commit()
    JalAccountCreator(currency_id=3, number='', name='Acc EUR', investing=1, organization=1,
                      account_type=PredefinedAccountType.Broker).commit()
    create_assets([('AAA', 'Coin A', '', 2, PredefinedAsset.Crypto, 0),
                   ('BBB', 'Coin B', '', 2, PredefinedAsset.Crypto, 0),
                   ('GAS', 'Gas coin', '', 2, PredefinedAsset.Crypto, 0),
                   ('SSS', 'Stock S', '', 2, PredefinedAsset.Stock, 0),
                   ('TTT', 'Stock T', '', 2, PredefinedAsset.Stock, 0)])
    create_actions([(T0, USD_ACC, 1, [(PredefinedCategory.StartingBalance, 10000.0)]),
                    (T0, EUR_ACC, 1, [(PredefinedCategory.StartingBalance, 10000.0)])])
    create_quotes(2, 3, [(x, 0.9) for x in (T1, T2, T3, T4)])
    create_trades(USD_ACC, [(T1, T1, A, 10, 100, 10, "buy-A")])
    yield


def _opened(account_id, asset_id) -> list:
    return JalDB._read_to_list("SELECT timestamp, otype, oid, m_otype, m_oid, acquired, price, remaining_qty, "
                               "c_price, c_qty, c_fx FROM trades_opened WHERE account_id=:account AND asset_id=:asset "
                               "ORDER BY id", [(":account", account_id), (":asset", asset_id)])


def _closed(account_id, asset_id) -> list:
    return JalDB._read_to_list("SELECT open_otype, open_oid, open_timestamp, open_price, open_qty, close_otype, "
                               "close_oid, close_timestamp, close_price, close_qty, c_price, c_qty, c_fx "
                               "FROM trades_closed WHERE account_id=:account AND asset_id=:asset ORDER BY id",
                               [(":account", account_id), (":asset", asset_id)])


def _oid(otype, n=1) -> int:
    return operation_id(otype, n)


# ----------------------------------------------------------------------------------------------------------------------
# D1: a trade closes at its own price, a transfer at the lot's unadjusted open price
def test_d1_close_price_of_a_sale_and_of_a_transfer(lots):
    create_trades(USD_ACC, [(T2, T2, A, -4, 150, 0, "sell-A")])
    create_transfers([(T3, USD_ACC, 6, EUR_ACC, 540, A)])
    Ledger().rebuild(from_timestamp=0)

    buy, sell, move = _oid(TRADE, 1), _oid(TRADE, 2), _oid(TRANSFER, 1)
    assert _closed(USD_ACC, A) == [
        [TRADE, buy, T1, '1E+2', '4', TRADE, sell, T2, '1.5E+2', '4', '1', '1', '1'],
        [TRADE, buy, T1, '1E+2', '6', TRANSFER, move, T3, '1E+2', '6', '1', '1', '1']]
    assert _opened(EUR_ACC, A) == [[T3, TRADE, buy, TRANSFER, move, T1, '1E+2', '6', '1', '1', '0.9']]


# D2: a sale swap closes at the market and opens the received asset anew; a conversion swap carries the lot
@pytest.mark.parametrize("treatment", [SwapTreatment.Sale, SwapTreatment.Conversion])
def test_d2_swap_sale_or_conversion(lots, treatment):
    create_quotes(A, 2, [(T2, 120)])
    create_swaps(USD_ACC, [(T2, A, 10, B, 20)], treatment=treatment)
    Ledger().rebuild(from_timestamp=0)

    buy, swap = _oid(TRADE, 1), _oid(SWAP, 1)
    expected = {
        SwapTreatment.Sale: (
            [[TRADE, buy, T1, '1E+2', '1E+1', SWAP, swap, T2, '1.2E+2', '1E+1', '1', '1', '1']],
            [[T2, SWAP, swap, SWAP, swap, T2, '6E+1', '2E+1', '1', '1', '1']]),
        SwapTreatment.Conversion: (
            [[TRADE, buy, T1, '1E+2', '1E+1', SWAP, swap, T2, '1E+2', '1E+1', '1', '1', '1']],
            [[T2, TRADE, buy, SWAP, swap, T1, '1E+2', '2E+1', '0.5', '2', '1']])}
    assert (_closed(USD_ACC, A), _opened(USD_ACC, B)) == expected[treatment]


# D3: a wrapping and a bridge carry the lot, its date and its cost
def test_d3_wrapping_and_bridge_carry_the_lot(lots):
    create_conversions(USD_ACC, [(T2, A, 10, B, 20)])
    create_bridges([{'asset': B, 'out_ts': T3, 'out_acc': USD_ACC, 'out_qty': 20,
                     'in_ts': T4, 'in_acc': EUR_ACC, 'in_qty': 20}])
    Ledger().rebuild(from_timestamp=0)

    buy, wrap, bridge = _oid(TRADE, 1), _oid(CONV, 1), _oid(LedgerTransaction.Bridge, 1)
    assert _closed(USD_ACC, A) == [[TRADE, buy, T1, '1E+2', '1E+1', CONV, wrap, T2, '1E+2', '1E+1', '1', '1', '1']]
    assert _closed(USD_ACC, B) == [[TRADE, buy, T1, '1E+2', '1E+1', LedgerTransaction.Bridge, bridge, T3, '1E+2',
                                    '2E+1', '0.5', '2', '1']]
    assert _opened(EUR_ACC, B) == [[T4, TRADE, buy, LedgerTransaction.Bridge, bridge, T1, '1E+2', '2E+1', '0.5', '2',
                                    '0.9']]


# D4: a spin-off splits the cost by value_share; the old stock keeps its date, the new one starts at the action
def test_d4_corporate_action_shares_cost_and_dates(lots):
    create_trades(USD_ACC, [(T1, T1, S, 10, 50, 0, "buy-S")])
    create_corporate_actions(USD_ACC, [(T2, CorporateAction.SpinOff, S, 10, 'spin-off',
                                        [(S, 10, 0.8), (T, 5, 0.2)])])
    Ledger().rebuild(from_timestamp=0)

    buy, action = _oid(TRADE, 2), _oid(LedgerTransaction.CorporateAction, 1)
    ca = LedgerTransaction.CorporateAction
    assert _opened(USD_ACC, S) == [[T1, TRADE, buy, TRADE, buy, T1, '5E+1', '1E+1', '1', '1', '1'],
                                   [T2, TRADE, buy, ca, action, T1, '5E+1', '0', '1', '1', '1'],
                                   [T2, TRADE, buy, ca, action, T1, '5E+1', '1E+1', '0.8', '1', '1']]
    assert _opened(USD_ACC, T) == [[T2, TRADE, buy, ca, action, T2, '5E+1', '5', '0.4', '0.5', '1']]


# D5: a stock dividend opens at its stated price, a crypto reward at zero
def test_d5_income_opens_at_its_price(lots):
    create_stock_dividends([(AssetIncome.StockDividend, T2, USD_ACC, S, 2, 2, 55, 0, "dividend")])
    LedgerTransaction.create_new(LedgerTransaction.AssetIncome, {
        'timestamp': T2, 'type': AssetIncome.Reward, 'account_id': USD_ACC, 'symbol_id': symbol_id_for(GAS),
        'amount': Decimal('3'), 'tax': Decimal('0'), 'note': 'reward'})
    Ledger().rebuild(from_timestamp=0)

    income = LedgerTransaction.AssetIncome
    dividend, reward = _oid(income, 1), _oid(income, 2)
    assert _opened(USD_ACC, S) == [[T2, income, dividend, income, dividend, T2, '55', '2', '1', '1', '1']]
    assert _opened(USD_ACC, GAS) == [[T2, income, reward, income, reward, T2, '0', '3', '1', '1', '1']]


# D6: FIFO follows the acquisition date, so a lot carried in with an older date goes before a newer local buy
def test_d6_fifo_by_acquisition_date(lots):
    create_trades(EUR_ACC, [(T2, T2, A, 5, 80, 0, "buy-A-eur")])
    create_transfers([(T3, USD_ACC, 10, EUR_ACC, 900, A)])
    create_trades(EUR_ACC, [(T4, T4, A, -12, 120, 0, "sell-A-eur")])
    Ledger().rebuild(from_timestamp=0)

    buy_usd, buy_eur, sell = _oid(TRADE, 1), _oid(TRADE, 2), _oid(TRADE, 3)
    assert _closed(EUR_ACC, A) == [
        [TRADE, buy_usd, T1, '1E+2', '1E+1', TRADE, sell, T4, '1.2E+2', '1E+1', '1', '1', '0.9'],
        [TRADE, buy_eur, T2, '8E+1', '2', TRADE, sell, T4, '1.2E+2', '2', '1', '1', '1']]
    assert _opened(EUR_ACC, A)[-1] == [T4, TRADE, buy_eur, TRADE, sell, T2, '8E+1', '3', '1', '1', '1']


# D7: a transfer between currencies puts deposit / value into c_fx
def test_d7_transfer_rate_goes_to_c_fx(lots):
    create_transfers([(T2, USD_ACC, 10, EUR_ACC, 918, A)])
    Ledger().rebuild(from_timestamp=0)

    assert _opened(EUR_ACC, A) == [[T2, TRADE, _oid(TRADE, 1), TRANSFER, _oid(TRANSFER, 1), T1, '1E+2', '1E+1', '1',
                                    '1', '0.918']]


# D8: gas leaves the lots at basis and closes no deal
def test_d8_gas_is_consumed_without_a_deal(lots):
    create_trades(USD_ACC, [(T1, T1, GAS, 2, 10, 0, "buy-GAS")])
    create_conversions(USD_ACC, [(T2, A, 10, B, 20, GAS, 0.5)])
    Ledger().rebuild(from_timestamp=0)

    gas_buy, wrap = _oid(TRADE, 2), _oid(CONV, 1)
    assert _closed(USD_ACC, GAS) == []
    assert _opened(USD_ACC, GAS) == [[T1, TRADE, gas_buy, TRADE, gas_buy, T1, '1E+1', '2', '1', '1', '1'],
                                     [T2, TRADE, gas_buy, CONV, wrap, T1, '1E+1', '1.5', '1', '1', '1']]


# D9: an arrival from an unknown source opens a lot of its own at zero
def test_d9_arrival_from_nowhere_opens_at_zero(lots):
    LedgerTransaction.create_new(TRANSFER, {
        'withdrawal_timestamp': T2, 'withdrawal_account': None, 'withdrawal': '7', 'deposit_timestamp': T2,
        'deposit_account': EUR_ACC, 'deposit': '0', 'number': '', 'symbol_id': symbol_id_for(B)})
    Ledger().rebuild(from_timestamp=0)

    move = _oid(TRANSFER, 1)
    assert _opened(EUR_ACC, B) == [[T2, TRANSFER, move, TRANSFER, move, T2, '0', '7', '1', '1', '1']]
