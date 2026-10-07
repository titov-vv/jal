# Interest a rebasing receipt token (an Aave aToken) welds onto a supply or a withdrawal is booked apart from the
# conversion, as a lot of its own at zero cost and dated on the day it arrived.
from decimal import Decimal

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_fifo
from tests.helpers import d2t, create_stocks, create_trades, create_conversions, symbol_id_for
from jal.constants import AssetData, BookAccount
from jal.data_import.statement import Statement, JSF
from jal.db.ledger import Ledger, LedgerAmounts
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.operations import LedgerTransaction, AssetIncome
from jal.db.db import JalDB
from jal.db.lending_interest import split_welded_interest
from jal.updates import jal_delta_80

USDG, A_USDG, STK = 4, 5, 6   # asset ids of _assets()


def _mark(asset_id, datatype, value):
    JalDB()._exec("INSERT OR REPLACE INTO asset_data(asset_id, datatype, value) VALUES(:a, :dt, :v)",
                  [(":a", asset_id), (":dt", datatype), (":v", value)], commit=True)
    JalAsset(asset_id).invalidate_cache()


# A stablecoin, its rebasing aToken and a share token that wraps the aToken
def _assets():
    create_stocks([('USDG', 'Stablecoin'), ('aUSDG', 'Lending receipt'), ('stkUSDG', 'Share token')], currency_id=2)
    _mark(A_USDG, AssetData.Rebasing, '1')
    _mark(A_USDG, AssetData.Protocol, 'Aave v3')
    _mark(STK, AssetData.Protocol, 'Aave Safety Module')


def _conversion(out_asset, out_qty, in_asset, in_qty, timestamp=d2t(220201)):
    return {'timestamp': timestamp, 'account_id': 1, 'tx_hash': '0xabc', 'note': 'Aave v3 Pool',
            'out_symbol_id': symbol_id_for(out_asset, 2), 'out_qty': Decimal(out_qty),
            'in_symbol_id': symbol_id_for(in_asset, 2), 'in_qty': Decimal(in_qty)}


def _incomes():
    return JalDB()._read_to_list("SELECT timestamp, number, type, symbol_id, amount, note FROM asset_incomes "
                                 "ORDER BY timestamp", named=True)


def _stored_conversions():
    return [(Decimal(x['out_qty']), Decimal(x['in_qty'])) for x in JalDB()._read_to_list(
        "SELECT out_qty, in_qty FROM conversions ORDER BY timestamp", named=True)]


# A supply mints 'amount + accrued': the interest is the excess of the aToken received
def test_interest_is_split_off_a_supply(prepare_db_fifo):
    _assets()
    conversion = _conversion(USDG, '40', A_USDG, '43')
    interest = split_welded_interest(conversion)

    assert (conversion['out_qty'], conversion['in_qty']) == (Decimal('40'), Decimal('40'))
    assert interest == {'timestamp': d2t(220201) - 1, 'number': '0xabc', 'type': AssetIncome.LendingInterest,
                        'account_id': 1, 'symbol_id': symbol_id_for(A_USDG, 2), 'amount': Decimal('3'),
                        'note': 'Aave v3 Pool'}


# A withdrawal burns 'amount - accrued': the interest is in the aToken again, and is surrendered with the rest
def test_interest_is_split_off_a_withdrawal(prepare_db_fifo):
    _assets()
    conversion = _conversion(A_USDG, '103', USDG, '105')
    interest = split_welded_interest(conversion)

    assert (conversion['out_qty'], conversion['in_qty']) == (Decimal('105'), Decimal('105'))
    assert interest['symbol_id'] == symbol_id_for(A_USDG, 2) and interest['amount'] == Decimal('2')


# What is not interest is left alone: equal quantities, a truncation shortfall, a pair with no rebasing side and
# a move into a share token, where the difference is the rate between two units
def test_what_is_not_interest_is_left_in_the_conversion(prepare_db_fifo):
    _assets()
    create_stocks([('ETH', 'Coin'), ('WETH', 'Wrapped coin')], currency_id=2)   # assets 7 and 8
    for pair in [(USDG, '40', A_USDG, '40'), (USDG, '40', A_USDG, '39.999999'), (7, '1', 8, '1.05'),
                 (A_USDG, '7.570363', STK, '6.582313'), (STK, '6.582313', A_USDG, '7.6')]:
        conversion = _conversion(*pair)
        assert split_welded_interest(conversion) is None
        assert (conversion['out_qty'], conversion['in_qty']) == (Decimal(pair[1]), Decimal(pair[3]))


# The interest is a lot of its own: zero cost, opened on the day it arrived, and it takes nothing from the basis
# of the principal. No quote is needed to book it.
def test_lending_interest_opens_a_zero_cost_lot_of_its_own(prepare_db_fifo):
    _assets()
    t_buy, t_first, t_second, t_exit = d2t(220101), d2t(220201), d2t(220301), d2t(220401)
    create_trades(1, [(t_buy, t_buy, USDG, Decimal('100'), Decimal('1'), Decimal('0'))])   # basis 100
    statement = Statement()
    statement.set_mapped_id(JSF.ACCOUNTS, 1, 1)
    for asset_id in (USDG, A_USDG):
        statement.set_mapped_id(JSF.SYMBOLS, asset_id, symbol_id_for(asset_id, 2))
    statement._import_conversions([
        {'account': 1, 'timestamp': t_first, 'tx_hash': '0x01', 'description': 'Aave v3 Pool',
         'out_symbol': USDG, 'out_qty': Decimal('60'), 'in_symbol': A_USDG, 'in_qty': Decimal('60')},
        {'account': 1, 'timestamp': t_second, 'tx_hash': '0x02', 'description': 'Aave v3 Pool',     # +3 of interest
         'out_symbol': USDG, 'out_qty': Decimal('40'), 'in_symbol': A_USDG, 'in_qty': Decimal('43')},
        {'account': 1, 'timestamp': t_exit, 'tx_hash': '0x03', 'description': 'Aave v3 Pool',       # +2 of interest
         'out_symbol': A_USDG, 'out_qty': Decimal('103'), 'in_symbol': USDG, 'in_qty': Decimal('105')}])

    assert _stored_conversions() == [(Decimal('60'), Decimal('60')), (Decimal('40'), Decimal('40')),
                                     (Decimal('105'), Decimal('105'))]
    assert [(x['timestamp'], x['number'], int(x['type']), Decimal(x['amount'])) for x in _incomes()] == [
        (t_second - 1, '0x02', AssetIncome.LendingInterest, Decimal('3')),
        (t_exit - 1, '0x03', AssetIncome.LendingInterest, Decimal('2'))]

    Ledger().rebuild(from_timestamp=0)
    assert JalAccount(1).get_asset_amount(t_exit, A_USDG) == Decimal('0')
    assert JalAccount(1).get_asset_amount(t_exit, USDG) == Decimal('105')
    # 105 units are held and they cost what was paid for the 100 that were bought
    assert LedgerAmounts("value_acc")[(BookAccount.Assets, 1, USDG)] == Decimal('100')
    lots = JalAccount(1).open_trades_list(JalAsset(USDG))
    assert sorted((x.open_qty(), x.open_price(adjusted=True), x.open_operation().timestamp()) for x in lots) == [
        (Decimal('2'), Decimal('0'), t_exit - 1), (Decimal('3'), Decimal('0'), t_second - 1),
        (Decimal('40'), Decimal('1'), t_buy), (Decimal('60'), Decimal('1'), t_buy)]
    assert JalAccount(1).closed_trades_list() == []


# Importing the same movements again books nothing twice
def test_a_repeated_import_books_the_interest_once(prepare_db_fifo):
    _assets()
    statement = Statement()
    statement.set_mapped_id(JSF.ACCOUNTS, 1, 1)
    for asset_id in (USDG, A_USDG):
        statement.set_mapped_id(JSF.SYMBOLS, asset_id, symbol_id_for(asset_id, 2))
    supply = {'account': 1, 'timestamp': d2t(220201), 'tx_hash': '0x02', 'description': 'Aave v3 Pool',
              'out_symbol': USDG, 'out_qty': Decimal('40'), 'in_symbol': A_USDG, 'in_qty': Decimal('43')}
    statement._import_conversions([supply])
    statement._import_conversions([supply])

    assert _stored_conversions() == [(Decimal('40'), Decimal('40'))]
    assert len(_incomes()) == 1


# Delta 80 does the same to the conversions stored before it, and may be run again after an interruption
def test_delta_80_splits_the_stored_conversions(prepare_db_fifo):
    _assets()
    t_buy, t_first, t_second, t_exit, t_move = d2t(220101), d2t(220201), d2t(220301), d2t(220401), d2t(220501)
    create_trades(1, [(t_buy, t_buy, USDG, Decimal('110'), Decimal('1'), Decimal('0'))])
    create_conversions(1, [(t_first, USDG, '60', A_USDG, '60'), (t_second, USDG, '40', A_USDG, '43'),
                           (t_exit, A_USDG, '93', USDG, '95'), (t_move, A_USDG, '10', STK, '8.7')])
    jal_delta_80.update()
    jal_delta_80.update()

    assert _stored_conversions() == [(Decimal('60'), Decimal('60')), (Decimal('40'), Decimal('40')),
                                     (Decimal('95'), Decimal('95')), (Decimal('10'), Decimal('8.7'))]
    assert [(x['timestamp'], int(x['type']), x['symbol_id'], Decimal(x['amount'])) for x in _incomes()] == [
        (t_second - 1, AssetIncome.LendingInterest, symbol_id_for(A_USDG, 2), Decimal('3')),
        (t_exit - 1, AssetIncome.LendingInterest, symbol_id_for(A_USDG, 2), Decimal('2'))]
    Ledger().rebuild(from_timestamp=0)
    assert JalAccount(1).get_asset_amount(t_move, A_USDG) == Decimal('0')
    assert JalAccount(1).get_asset_amount(t_move, USDG) == Decimal('105')
