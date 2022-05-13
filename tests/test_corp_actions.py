from tests.fixtures import project_root, data_path, prepare_db, prepare_db_fifo
from jal.db.ledger import Ledger
from jal.db.helpers import readSQL
from jal.db.operations import CorporateAction
from tests.helpers import create_stocks, create_quotes, create_trades, create_corporate_actions


def test_spin_off(prepare_db_fifo):
    # Prepare trades and corporate actions setup
    test_assets = [
        (4, 'A', 'A SHARE'),
        (5, 'B', 'B SHARE')
    ]
    create_stocks(test_assets, currency_id=2)

    test_corp_actions = [
        (1622548800, CorporateAction.SpinOff, 4, 100.0, 5, 5.0, 1.0, 'Spin-off 5 B from 100 A'),   # 01/06/2021, cost basis 0.0
        (1627819200, CorporateAction.Split, 4, 104.0, 4, 13.0, 1.0, 'Split A 104 -> 13')           # 01/08/2021
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
    assert readSQL("SELECT * FROM ledger WHERE asset_id=4 AND timestamp<1628615520 ORDER BY id DESC LIMIT 1") == [11, 1627819200, 5, 2, 4, 4, 1, 13.0, 1452.0, 13.0, 1452.0, '', '', '']
    assert readSQL("SELECT * FROM ledger WHERE asset_id=5 AND timestamp<1628615520 ORDER BY id DESC LIMIT 1") == [7, 1622548800, 5, 1, 4, 5, 1, 5.0, 0.0, 5.0, 0.0, '', '', '']
    assert readSQL("SELECT * FROM ledger WHERE book_account=3 AND timestamp<1628615520 ORDER BY id DESC LIMIT 1") == [8, 1625140800, 3, 2, 3, 2, 1, -52.0, 0.0, 8548.0, 0.0, '', '', '']
    assert readSQL("SELECT profit FROM deals_ext WHERE close_timestamp>=1629047520") == 498.0


def test_symbol_change(prepare_db_fifo):
    # Prepare trades and corporate actions setup
    test_assets = [
        (4, 'A', 'A SHARE'),
        (5, 'B', 'B SHARE')
    ]
    create_stocks(test_assets, currency_id=2)

    test_corp_actions = [
        (1622548800, CorporateAction.SymbolChange, 4, 100.0, 5, 100.0, 1.0, 'Symbol change 100 A -> 100 B')
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

    assert readSQL("SELECT * FROM deals_ext WHERE asset_id=4") == [1, 'Inv. Account', 4, 'A', 1619870400, 1622548800, 10.0, 10.0, 100.0, 0.0, 0.0, 0.0, -3]
    assert readSQL("SELECT * FROM deals_ext WHERE asset_id=5") == [1, 'Inv. Account', 5, 'B', 1622548800, 1625140800, 10.0, 20.0, 100.0, 0.0, 1000.0, 100.0, 3]


def test_delisting(prepare_db_fifo):
    create_stocks([(4, 'A', 'A SHARE')], currency_id=2)

    test_corp_actions = [
        (1622548800, CorporateAction.Delisting, 4, 100.0, 4, 0.0, 1.0, 'Delisting 100 A')
    ]
    create_corporate_actions(1, test_corp_actions)

    test_trades = [
        (1619870400, 1619870400, 4, 100.0, 10.0, 0.0)      # Buy  100 A x 10.00 01/05/2021
    ]
    create_trades(1, test_trades)

    # Build ledger
    ledger = Ledger()
    ledger.rebuild(from_timestamp=0)

    assert readSQL("SELECT * FROM deals_ext WHERE asset_id=4") == [1, 'Inv. Account', 4, 'A', 1619870400, 1622548800, 10.0, 10.0, 100.0, 0.0, 0.0, 0.0, -5]
    assert readSQL("SELECT * FROM ledger_totals WHERE asset_id=4 ORDER BY id DESC LIMIT 1") == [5, 5, 1, 1622548800, 4, 4, 1, 0.0, 0.0]
    assert readSQL("SELECT * FROM ledger WHERE book_account=1") == [6, 1622548800, 5, 1, 1, 2, 1, 1000.0, 0.0, 1000.0, 0.0, 1, 9, '']
