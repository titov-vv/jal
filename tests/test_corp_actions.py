from decimal import Decimal
from tests.fixtures import project_root, data_path, prepare_db, prepare_db_fifo
from constants import BookAccount
from jal.db.ledger import Ledger, LedgerAmounts
from jal.db.account import JalAccount
from jal.db.operations import CorporateAction
from tests.helpers import d2t, dt2t, create_stocks, create_quotes, create_trades, create_corporate_actions


def test_spin_off(prepare_db_fifo):
    # Prepare trades and corporate actions setup
    create_stocks([('A', 'A SHARE'), ('B', 'B SHARE')], currency_id=2)  # id = 4, 5

    test_corp_actions = [
        (1622548800, CorporateAction.SpinOff, 4, 100.0, 'Spin-off 5 B from 100 A', [(4, 100.0, 1.0), (5, 5.0, 0.0)]),   # 01/06/2021
        (1627819200, CorporateAction.Split, 4, 104.0, 'Split A 104 -> 13', [(4, 13.0, 1.0)])           # 01/08/2021
    ]
    create_corporate_actions(1, test_corp_actions)

    test_trades = [
        (1619870400, 1619870400, 4, 100.0, 14.0, 0.0),   # Buy 100 A x 14.00 01/05/2021
        (1625140800, 1625140800, 4, 4.0, 13.0, 0.0),     # Buy   4 A x 13.00 01/07/2021
        (1629047520, 1629047520, 4, -13.0, 150.0, 0.0)   # Sell 13 A x 150.00 15/08/2021
    ]
    create_trades(1, test_trades)

    create_quotes(2, 2, [(1614600000, 70.0)])
    create_quotes(4, 2, [(1617278400, 15.0)])
    create_quotes(5, 2, [(1617278400, 2.0)])
    create_quotes(4, 2, [(1628683200, 100.0)])

    # Build ledger
    ledger = Ledger()
    ledger.rebuild(from_timestamp=0)

    # Check ledger amounts before selling
    op_timestamp = LedgerAmounts("timestamp", timestamp=d2t(210810))
    amount = LedgerAmounts("amount", timestamp=d2t(210810))
    total_amount = LedgerAmounts("amount_acc", timestamp=d2t(210810))
    total_value = LedgerAmounts("value_acc", timestamp=d2t(210810))

    assert op_timestamp[(BookAccount.Money, 1, 2)] == dt2t(2107011200)
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

    trades = [x for x in JalAccount(1).closed_trades_list() if x.close_operation().timestamp()>=1629047520]
    assert len(trades) == 1
    assert trades[0].profit() == Decimal('497.9999999999999999999999999')


def test_symbol_change(prepare_db_fifo):
    # Prepare trades and corporate actions setup
    test_assets = [
        ('A', 'A SHARE'),  # id = 4
        ('B', 'B SHARE')   # id = 5
    ]
    create_stocks(test_assets, currency_id=2)

    test_corp_actions = [
        (1622548800, CorporateAction.SymbolChange, 4, 100.0, 'Symbol change 100 A -> 100 B', [(5, 100.0, 1.0)])
    ]
    create_corporate_actions(1, test_corp_actions)

    test_trades = [
        (1619870400, 1619870400, 4, 100.0, 10.0, 0.0),      # Buy  100 A x 10.00 01/05/2021
        (1625140800, 1625140800, 5, -100.0, 20.0, 0.0)      # Sell 100 B x 20.00 01/07/2021
    ]
    create_trades(1, test_trades)

    # Build ledgerye
    ledger = Ledger()
    ledger.rebuild(from_timestamp=0)

    trades = JalAccount(1).closed_trades_list()
    assert trades[0].dump() == ['A', 1619870400, 1622548800, Decimal('1E+1'), Decimal('1E+1'), Decimal('1E+2'), Decimal('0'), Decimal('0'), Decimal('0')]
    assert trades[1].dump() == ['B', 1622548800, 1625140800, Decimal('1E+1'), Decimal('2E+1'), Decimal('1E+2'), Decimal('0'), Decimal('1000'), Decimal('100')]


def test_delisting(prepare_db_fifo):
    create_stocks([('A', 'A SHARE')], currency_id=2)  # ID = 4

    test_corp_actions = [
        (1622548800, CorporateAction.Delisting, 4, 100.0, 'Delisting 100 A', [])
    ]
    create_corporate_actions(1, test_corp_actions)

    test_trades = [
        (1619870400, 1619870400, 4, 100.0, 10.0, 0.0)      # Buy  100 A x 10.00 01/05/2021
    ]
    create_trades(1, test_trades)

    # Build ledger
    ledger = Ledger()
    ledger.rebuild(from_timestamp=0)

    trades = JalAccount(1).closed_trades_list()
    assert len(trades) == 1
    assert trades[0].dump() == ['A', 1619870400, 1622548800, Decimal('1E+1'), Decimal('1E+1'), Decimal('1E+2'), Decimal('0'), Decimal('0'), Decimal('0')]

    amounts = LedgerAmounts("amount_acc")
    assert amounts[(BookAccount.Costs, 1, 2)] == Decimal('1E+3')
    assert amounts[(BookAccount.Money, 1, 2)] == Decimal('9E+3')
    assert amounts[(BookAccount.Assets, 1, 4)] == Decimal('0')

    values = LedgerAmounts("value_acc")
    assert values[(BookAccount.Assets, 1, 4)] == Decimal('0')
