from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_fifo
from jal.constants import BookAccount
from jal.db.ledger import Ledger, LedgerAmounts
from jal.db.account import JalAccount
from jal.db.operations import CorporateAction, LedgerError
from tests.helpers import d2t, dt2t, create_stocks, create_quotes, create_trades, create_corporate_actions


def test_spin_off(prepare_db_fifo):
    # Prepare trades and corporate actions setup
    create_stocks([('A', 'A SHARE'), ('B', 'B SHARE')], currency_id=2)  # id = 4, 5

    test_corp_actions = [
        (dt2t(2106011200), CorporateAction.SpinOff, 4, 100.0, 'Spin-off 5 B from 100 A', [(4, 100.0, 1.0), (5, 5.0, 0.0)]),
        (dt2t(2108011200), CorporateAction.Split, 4, 104.0, 'Split A 104 -> 13', [(4, 13.0, 1.0)])
    ]
    create_corporate_actions(1, test_corp_actions)

    test_trades = [
        (d2t(210501), d2t(210503), 4, 100.0, 14.0, 0.0),        # Buy 100 A x 14.00 01/05/2021
        (d2t(210701), d2t(210703), 4, 4.0, 13.0, 0.0),          # Buy   4 A x 13.00 01/07/2021
        (dt2t(2108151700), d2t(210817), 4, -13.0, 150.0, 0.0)   # Sell 13 A x 150.00 15/08/2021
    ]
    create_trades(1, test_trades)

    create_quotes(2, 2, [(d2t(210301), 70.0)])
    create_quotes(4, 2, [(d2t(210401), 15.0)])
    create_quotes(5, 2, [(d2t(210401), 2.0)])
    create_quotes(4, 2, [(d2t(210811), 100.0)])

    # Build ledger
    ledger = Ledger()
    ledger.rebuild(from_timestamp=0)

    # Check ledger amounts before selling
    op_timestamp = LedgerAmounts("timestamp", timestamp=d2t(210810))
    amount = LedgerAmounts("amount", timestamp=d2t(210810))
    total_amount = LedgerAmounts("amount_acc", timestamp=d2t(210810))
    total_value = LedgerAmounts("value_acc", timestamp=d2t(210810))

    assert op_timestamp[(BookAccount.Money, 1, 2)] == d2t(210701)
    assert amount[(BookAccount.Money, 1, 2)] == Decimal('-52')
    assert total_amount[(BookAccount.Money, 1, 2)] == Decimal('8548')
    assert total_value[(BookAccount.Money, 1, 2)] == Decimal('0')

    assert op_timestamp[(BookAccount.Assets, 1, 4)] == dt2t(2108011200)
    assert amount[(BookAccount.Assets, 1, 4)] == Decimal('13')
    assert total_amount[(BookAccount.Assets, 1, 4)] == Decimal('13')
    assert total_value[(BookAccount.Assets, 1, 4)] == Decimal('1452')

    assert op_timestamp[(BookAccount.Assets, 1, 5)] == dt2t(2106011200)
    assert amount[(BookAccount.Assets, 1, 5)] == Decimal('5')
    assert total_amount[(BookAccount.Assets, 1, 5)] == Decimal('5')
    assert total_value[(BookAccount.Assets, 1, 5)] == Decimal('0')

    trades = [x for x in JalAccount(1).closed_trades_list() if x.close_operation().timestamp() >= dt2t(2108151700)]
    assert len(trades) == 2
    assert [x.profit() for x in trades] == [Decimal('475'), Decimal('23')]


def test_symbol_change(prepare_db_fifo):
    # Prepare trades and corporate actions setup
    test_assets = [
        ('A', 'A SHARE'),  # id = 4
        ('B', 'B SHARE')   # id = 5
    ]
    create_stocks(test_assets, currency_id=2)

    test_corp_actions = [
        (d2t(210601), CorporateAction.SymbolChange, 4, 100.0, 'Symbol change 100 A -> 100 B', [(5, 100.0, 1.0)])
    ]
    create_corporate_actions(1, test_corp_actions)

    test_trades = [
        (d2t(210501), d2t(210501), 4, 100.0, 10.0, 0.0),      # Buy  100 A x 10.00 01/05/2021
        (d2t(210701), d2t(210701), 5, -100.0, 20.0, 0.0)      # Sell 100 B x 20.00 01/07/2021
    ]
    create_trades(1, test_trades)

    # Build ledger
    ledger = Ledger()
    ledger.rebuild(from_timestamp=0)

    trades = JalAccount(1).closed_trades_list()
    assert trades[0].dump() == ['B', d2t(210501), d2t(210701), Decimal('1E+1'), Decimal('2E+1'), Decimal('1E+2'), Decimal('0'), Decimal('1000'), Decimal('100')]


def test_delisting(prepare_db_fifo):
    create_stocks([('A', 'A SHARE')], currency_id=2)  # ID = 4

    test_corp_actions = [
        (d2t(210801), CorporateAction.Delisting, 4, 100.0, 'Delisting 100 A', [])
    ]
    create_corporate_actions(1, test_corp_actions)

    test_trades = [
        (d2t(210501), d2t(210501), 4, 100.0, 10.0, 0.0)      # Buy  100 A x 10.00 01/05/2021
    ]
    create_trades(1, test_trades)

    # Build ledger
    ledger = Ledger()
    ledger.rebuild(from_timestamp=0)

    trades = JalAccount(1).closed_trades_list()
    assert len(trades) == 0

    amounts = LedgerAmounts("amount_acc")
    assert amounts[(BookAccount.Costs, 1, 2)] == Decimal('1E+3')
    assert amounts[(BookAccount.Money, 1, 2)] == Decimal('9E+3')
    assert amounts[(BookAccount.Assets, 1, 4)] == Decimal('0')

    values = LedgerAmounts("value_acc")
    assert values[(BookAccount.Assets, 1, 4)] == Decimal('0')


# ----------------------------------------------------------------------------------------------------------------------
# A split of a short position: its lots stay short, each with twice the quantity at half the price
def test_split_of_short_position(prepare_db_fifo):
    create_stocks([('A', 'A SHARE')], currency_id=2)  # id = 4

    test_corp_actions = [
        (d2t(210701), CorporateAction.Split, 4, -100.0, 'Split A -100 -> -200', [(4, -200.0, 1.0)])
    ]
    create_corporate_actions(1, test_corp_actions)

    test_trades = [
        (d2t(210501), d2t(210503), 4, -60.0, 20.0, 1.0),      # Sell 60 A x 20.00 01/05/2021
        (d2t(210601), d2t(210603), 4, -40.0, 30.0, 2.0),      # Sell 40 A x 30.00 01/06/2021
        (d2t(210801), d2t(210803), 4, 150.0, 8.0, 0.0),       # Buy 150 A x  8.00 01/08/2021
        (d2t(210901), d2t(210903), 4, 50.0, 5.0, 0.0)         # Buy  50 A x  5.00 01/09/2021
    ]
    create_trades(1, test_trades)

    ledger = Ledger()
    ledger.rebuild(from_timestamp=0)

    # The position right after the split: -200 pieces that keep the value they were sold for (60 x 20 + 40 x 30)
    total_amount = LedgerAmounts("amount_acc", timestamp=d2t(210710))
    total_value = LedgerAmounts("value_acc", timestamp=d2t(210710))
    assert total_amount[(BookAccount.Assets, 1, 4)] == Decimal('-200')
    assert total_value[(BookAccount.Assets, 1, 4)] == Decimal('-2400')

    # 120 x (10 - 8) - 1 | 30 x (15 - 8) - 2 x 30/80 | 50 x (15 - 5) - 2 x 50/80
    trades = JalAccount(1).closed_trades_list()
    assert [(x.qty(), x.open_qty(), x.open_price(adjusted=True)) for x in trades] == [
        (Decimal('-120'), Decimal('-60'), Decimal('10')),
        (Decimal('-30'), Decimal('-15'), Decimal('15')),
        (Decimal('-50'), Decimal('-25'), Decimal('15'))
    ]
    assert [x.profit() for x in trades] == [Decimal('239'), Decimal('209.25'), Decimal('498.75')]
    assert all(x.modified_by()[0].type() == CorporateAction._otype for x in trades)

    total_amount = LedgerAmounts("amount_acc")
    total_value = LedgerAmounts("value_acc")
    assert total_amount[(BookAccount.Assets, 1, 4)] == Decimal('0')
    assert total_value[(BookAccount.Assets, 1, 4)] == Decimal('0')
    assert total_amount[(BookAccount.Money, 1, 2)] == Decimal('10947')   # 10000 + 1199 + 1198 - 1200 - 250


# A short position moves to another symbol with its lots
def test_symbol_change_of_short_position(prepare_db_fifo):
    create_stocks([('A', 'A SHARE'), ('B', 'B SHARE')], currency_id=2)  # id = 4, 5

    test_corp_actions = [
        (d2t(210601), CorporateAction.SymbolChange, 4, -100.0, 'Symbol change -100 A -> -100 B', [(5, -100.0, 1.0)])
    ]
    create_corporate_actions(1, test_corp_actions)

    test_trades = [
        (d2t(210501), d2t(210501), 4, -100.0, 20.0, 0.0),     # Sell 100 A x 20.00 01/05/2021
        (d2t(210701), d2t(210701), 5, 100.0, 15.0, 0.0)       # Buy  100 B x 15.00 01/07/2021
    ]
    create_trades(1, test_trades)

    ledger = Ledger()
    ledger.rebuild(from_timestamp=0)

    total_amount = LedgerAmounts("amount_acc", timestamp=d2t(210610))
    total_value = LedgerAmounts("value_acc", timestamp=d2t(210610))
    assert total_amount[(BookAccount.Assets, 1, 4)] == Decimal('0')
    assert total_amount[(BookAccount.Assets, 1, 5)] == Decimal('-100')
    assert total_value[(BookAccount.Assets, 1, 5)] == Decimal('-2000')

    trades = JalAccount(1).closed_trades_list()
    assert [(x.symbol(), x.qty(), x.profit()) for x in trades] == [('B', Decimal('-100'), Decimal('500'))]


# Only a split and a symbol change are carried out for a short position, and they keep it short
@pytest.mark.parametrize("action", [
    (CorporateAction.SpinOff, 4, -100.0, 'Spin-off', [(4, -100.0, 0.9), (5, -5.0, 0.1)]),
    (CorporateAction.Merger, 4, -100.0, 'Merger', [(5, -50.0, 1.0)]),
    (CorporateAction.Delisting, 4, -100.0, 'Delisting', []),
    (CorporateAction.Split, 4, -100.0, 'Split that turns the position long', [(4, 200.0, 1.0)]),
    (CorporateAction.Split, 4, 100.0, 'Split of a long position that is short', [(4, 200.0, 1.0)])
])
def test_unsupported_action_on_short_position_halts_the_ledger(prepare_db_fifo, action):
    create_stocks([('A', 'A SHARE'), ('B', 'B SHARE')], currency_id=2)  # id = 4, 5
    create_trades(1, [(d2t(210501), d2t(210501), 4, -100.0, 20.0, 0.0)])
    create_corporate_actions(1, [(d2t(210601),) + action])
    with pytest.raises(LedgerError):
        Ledger().rebuild(from_timestamp=0)
