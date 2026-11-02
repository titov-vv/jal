from decimal import Decimal

import pytest
from PySide6.QtCharts import QScatterSeries
from PySide6.QtWidgets import QWidget

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, create_assets, create_actions, create_trades, create_quotes, create_swaps, \
    create_transfers, create_conversions, symbol_id_for
from jal.constants import PredefinedAsset, PredefinedCategory, PredefinedAccountType, AssetLocation, BookAccount
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.asset import JalAsset
from jal.db.ledger import Ledger, LedgerAmounts
from jal.db.operations import LedgerTransaction, AssetIncome, ChainAction, FeeKind
from jal.widgets.price_chart import ChartWindow

WALLET, WALLET2 = 1, 2
TRX, USDD = 4, 5
_WITH_SWAP = (LedgerTransaction.Trade, LedgerTransaction.Swap)   # what the Deals report asks for


# Two USD wallets on one chain; TRX quoted 0.30 before the reward and 0.50 from the day it is disposed of
@pytest.fixture
def wallets(prepare_db):
    for name, address in (('Tron wallet', 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t'),
                          ('Tron wallet 2', 'TEkxiTehnzSmSe2XqrBj4w32RUN966rdz8')):
        JalAccountCreator(currency_id=2, number='', name=name, investing=1, organization=1, address=address,
                          account_type=PredefinedAccountType.Wallet, chain=AssetLocation.TRX_BLOCKCHAIN).commit()
    create_assets([('TRX', 'Tron', '', 2, PredefinedAsset.Crypto, 0),        # ID = 4
                   ('USDD', 'Wrapped Tron', '', 2, PredefinedAsset.Crypto, 0)])  # ID = 5
    create_actions([(d2t(210101), WALLET, 1, [(PredefinedCategory.StartingBalance, 10000.0)])])
    create_quotes(TRX, 2, [(d2t(210201), '0.30'), (d2t(210203), '0.50')])
    yield


def _reward(subtype=AssetIncome.StakingReward, timestamp=d2t(210202), amount='100'):
    data = {'timestamp': timestamp, 'type': subtype, 'account_id': WALLET, 'symbol_id': symbol_id_for(TRX),
            'amount': amount, 'tax': '0', 'number': 'txhash', 'note': 'test'}
    return LedgerTransaction.create_new(LedgerTransaction.AssetIncome, data)


# A reward sold by a swap realizes the sale's whole value, its basis being zero: 100 x 0.50
def test_a_reward_sold_by_a_swap_realizes_its_whole_value(wallets):
    _reward()
    create_swaps(WALLET, [(d2t(210204), TRX, 100, USDD, 25)])
    Ledger().rebuild(from_timestamp=0)

    deals = JalAccount(WALLET).closed_trades_list(close_otypes=_WITH_SWAP)
    assert len(deals) == 1
    assert deals[0].open_operation().type() == LedgerTransaction.AssetIncome
    assert deals[0].open_price() == Decimal('0')
    assert deals[0].profit() == Decimal('50')
    assert JalAccount(WALLET).open_trades_list(JalAsset(USDD))[0].open_price() == Decimal('2')   # 50 / 25


# A reward lot carried by a Transfer and a Conversion reaches a Trade-closed deal, which the tax reports read
def test_a_carried_reward_lot_keeps_its_zero_basis_into_a_trade(wallets):
    reward = _reward()
    create_transfers([(d2t(210203), WALLET, 100, WALLET2, 100, TRX)])
    create_conversions(WALLET2, [(d2t(210204), TRX, 100, USDD, 100)])
    create_trades(WALLET2, [(d2t(210205), d2t(210205), USDD, -100.0, 0.50, 0.0)])
    Ledger().rebuild(from_timestamp=0)

    deals = JalAccount(WALLET2).closed_trades_list()   # Trade only, the tax reports' list
    assert len(deals) == 1
    assert deals[0].open_operation().type() == LedgerTransaction.AssetIncome
    assert deals[0].open_operation().oid() == reward.oid()
    assert deals[0].acquired() == d2t(210202)
    assert deals[0].open_price(adjusted=True) == Decimal('0')
    assert deals[0].profit() == Decimal('50')


# Gas paid out of a reward lot is expensed at the reward's basis, which is zero
def test_gas_from_a_reward_lot_costs_nothing(wallets):
    _reward()
    data = {'timestamp': d2t(210204), 'type': ChainAction.Authorization, 'account_id': WALLET, 'number': 'txhash',
            'note': 'test', 'fee': '10', 'fee_symbol_id': symbol_id_for(TRX), 'fee_account': WALLET,
            'fee_kind': FeeKind.Gas}
    LedgerTransaction.create_new(LedgerTransaction.ChainAction, data)
    Ledger().rebuild(from_timestamp=0)

    assert JalAccount(WALLET).get_asset_amount(d2t(210301), TRX) == Decimal('90')
    assert LedgerAmounts("amount_acc")[(BookAccount.Costs, WALLET, 2)] == Decimal('0')


# Every crypto income opens at zero cost although a quote exists; its worth at receipt is still 100 x 0.30
@pytest.mark.parametrize('subtype, worth', [(AssetIncome.StakingReward, '30'), (AssetIncome.Reward, '30'),
                                            (AssetIncome.DustAttack, '30'), (AssetIncome.RebaseAdjustment, '0'),
                                            (AssetIncome.TokenRentReturn, '30'), (AssetIncome.LendingInterest, '30')])
def test_a_crypto_income_opens_at_zero_beside_its_quote(wallets, subtype, worth):
    income = _reward(subtype)
    Ledger().rebuild(from_timestamp=0)

    assert LedgerAmounts("amount_acc")[(BookAccount.Assets, WALLET, TRX)] == Decimal('100')
    assert LedgerAmounts("value_acc")[(BookAccount.Assets, WALLET, TRX)] == Decimal('0')
    assert JalAccount(WALLET).open_trades_list(JalAsset(TRX))[0].open_price() == Decimal('0')
    assert income.amount(currency_id=2) == Decimal(worth)


# Stock grants keep the price their source states
@pytest.mark.parametrize('subtype', [AssetIncome.StockDividend, AssetIncome.StockVesting])
def test_a_stock_grant_keeps_its_stated_price(wallets, subtype):
    data = {'timestamp': d2t(210202), 'type': subtype, 'account_id': WALLET, 'symbol_id': symbol_id_for(TRX),
            'amount': '100', 'price': '0.25', 'tax': '0', 'number': 'n', 'note': 'test'}
    LedgerTransaction.create_new(LedgerTransaction.AssetIncome, data)
    Ledger().rebuild(from_timestamp=0)

    assert LedgerAmounts("value_acc")[(BookAccount.Assets, WALLET, TRX)] == Decimal('25')


# A zero-cost reward lot is drawn on the quote of its day in a series of its own; an unquoted one is left out
def test_the_price_chart_draws_a_reward_on_its_quote(wallets):
    _reward(timestamp=d2t(210115))                            # before any quote
    _reward()
    create_trades(WALLET, [(d2t(210203), d2t(210203), TRX, 10.0, 0.40, 0.0)])
    Ledger().rebuild(from_timestamp=0)

    parent = QWidget()
    chart = ChartWindow(WALLET, TRX, 2, d2t(210301), parent=parent)
    assert chart.ready
    assert sorted((x['income'], x['price']) for x in chart.trades) == [(False, Decimal('0.40')),
                                                                       (True, Decimal('0.30'))]
    assert chart.chart.trade_series.count() == 1
    assert chart.chart.income_series.count() == 1
    assert chart.chart.income_series.markerShape() == QScatterSeries.MarkerShape.MarkerShapeTriangle
    assert chart.range[2] > 0                                 # the axis no longer reaches down to zero

    chart.chart.MouseOverTrade(chart.chart.income_series.at(0), True)
    assert chart.chart.toolTip() == "02/02/2021: +100, cost 0, quote 0.3\nStaking reward\ntest"
