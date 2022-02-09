from pytest import approx

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_fifo, prepare_db_ledger
from tests.helpers import create_stocks, create_actions, create_trades, create_corporate_actions, create_stock_dividends
from constants import TransactionType, BookAccount
from jal.db.ledger import Ledger
from jal.db.helpers import readSQL, executeSQL, readSQLrecord


#-----------------------------------------------------------------------------------------------------------------------
def test_empty_ledger(prepare_db_ledger):
    # Build ledger from scratch
    ledger = Ledger()
    ledger.rebuild(from_timestamp=0)


def test_ledger(prepare_db_ledger):
    actions = [
        (1638349200, 1, 1, [(5, -100.0)]),
        (1638352800, 1, 1, [(6, -30.0), (8, 55.0)]),
        (1638356400, 1, 1, [(7, 84.0)])
    ]
    create_actions(actions)

    # Build ledger from scratch
    ledger = Ledger()
    ledger.rebuild(from_timestamp=0)

    # validate book amounts
    expected_book_values = [None, 130.0, -139.0, 9.0, None, 0.0]
    query = executeSQL("SELECT MAX(id) AS mid, book_account, amount_acc, value_acc "
                       "FROM ledger GROUP BY book_account")
    while query.next():
        row = readSQLrecord(query, named=True)
        assert row['amount_acc'] == expected_book_values[row['book_account']]

    actions = [
        (1638360000, 1, 1, [(5, -34.0)]),
        (1638363600, 1, 1, [(7, 11.0)])
    ]
    create_actions(actions)

    # Build ledger for recent transactions only
    ledger = Ledger()
    ledger.rebuild()

    # validate book amounts and values
    expected_book_amounts = [None, 164.0, -150.0, -0.0, None, -14.0]
    expected_book_values = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    query = executeSQL("SELECT MAX(id) AS mid, book_account, amount_acc, value_acc "
                       "FROM ledger GROUP BY book_account")
    while query.next():
        row = readSQLrecord(query, named=True)
        assert row['amount_acc'] == expected_book_amounts[row['book_account']]
        assert row['value_acc'] == expected_book_values[row['book_account']]

    # Re-build from the middle - validation should pass again
    ledger.rebuild(from_timestamp=1638352800)
    query = executeSQL("SELECT MAX(id) AS mid, book_account, amount_acc, value_acc "
                       "FROM ledger GROUP BY book_account")
    while query.next():
        row = readSQLrecord(query, named=True)
        assert row['amount_acc'] == expected_book_amounts[row['book_account']]
        assert row['value_acc'] == expected_book_values[row['book_account']]


def test_buy_sell_change(prepare_db_fifo):
    # Prepare single stock
    create_stocks([(4, 'A', 'A SHARE')])

    test_trades = [
        (1, 1609567200, 1609653600, 4, 10.0, 100.0, 1.0),
        (2, 1609729200, 1609815600, 4, -7.0, 200.0, 5.0)
    ]
    for trade in test_trades:
        assert executeSQL(
            "INSERT INTO trades (id, timestamp, settlement, account_id, asset_id, qty, price, fee) "
            "VALUES (:id, :timestamp, :settlement, 1, :asset, :qty, :price, :fee)",
            [(":id", trade[0]), (":timestamp", trade[1]), (":settlement", trade[2]), (":asset", trade[3]),
             (":qty", trade[4]), (":price", trade[5]), (":fee", trade[6])]) is not None

    # insert action between trades to shift frontier
    create_actions([(1609642800, 1, 1, [(7, 100.0)])])

    # Build ledger
    ledger = Ledger()
    ledger.rebuild(from_timestamp=0)

    # Validate initial deal quantity
    assert readSQL("SELECT COUNT(*) FROM deals_ext WHERE asset_id=4") == 1
    assert readSQL("SELECT qty FROM deals WHERE asset_id=4") == 7.0

    # Modify closing deal quantity
    _ = executeSQL("UPDATE trades SET qty=-5 WHERE id=2")

    # Re-build ledger from last actual data
    ledger.rebuild()

    # Check that deal quantity remains correct
    assert readSQL("SELECT COUNT(*) FROM deals_ext WHERE asset_id=4") == 1
    assert readSQL("SELECT COUNT(*) FROM open_trades WHERE asset_id=4") == 1
    assert readSQL("SELECT qty FROM deals WHERE asset_id=4") == 5.0

    # Add one more trade
    assert executeSQL("INSERT INTO trades (id, timestamp, settlement, account_id, asset_id, qty, price, fee) "
                      "VALUES (3, 1609815600, 1609902000, 1, 4, -8, 150, 3.0)") is not None

    # Re-build ledger from last actual data
    ledger.rebuild()

    # Check that deal quantity remains correct
    assert readSQL("SELECT COUNT(*) FROM deals_ext WHERE asset_id=4") == 2

    assert readSQL("SELECT COUNT(*) FROM open_trades") == 2

    _ = executeSQL("DELETE FROM trades WHERE id=2", commit=True)

    assert readSQL("SELECT COUNT(*) FROM open_trades") == 1
    assert readSQL("SELECT COUNT(*) FROM ledger WHERE timestamp>=1609729200") == 0
    # Re-build ledger from last actual data
    ledger.rebuild()

    # Check that deal quantity remains correct
    assert readSQL("SELECT COUNT(*) FROM deals_ext WHERE asset_id=4") == 1
    assert readSQL("SELECT qty FROM deals WHERE asset_id=4") == 8.0


def test_fifo(prepare_db_fifo):
    # Prepare trades and corporate actions setup
    test_assets = [
        (4, 'A', 'A SHARE'),
        (5, 'B', 'B SHARE'),
        (6, 'C', 'C SHARE'),
        (7, 'D', 'D SHARE'),
        (8, 'E', 'E SHARE'),
        (9, 'F', 'F SHARE'),
        (10, 'G1', 'G SHARE BEFORE'),
        (11, 'G2', 'G SHARE AFTER'),
        (12, 'H', 'H SPIN-OFF FROM G'),
        (13, 'K', 'K SHARE'),
        (14, 'L', 'L SHARE'),
        (15, 'M', 'M SHARE'),
        (16, 'N', 'N WITH STOCK DIVIDEND'),
        (17, 'O', 'O SHARE'),
        (18, 'P', 'P SHARE'),
    ]
    create_stocks(test_assets)

    test_corp_actions = [
        (1606899600, 3, 10, 100.0, 11, 100.0, 1.0, 'Symbol change G1 -> G2'),
        (1606986000, 2, 11, 100.0, 12, 20.0, 0.8, 'Spin-off H from G2'),
        (1607763600, 4, 14, 15.0, 14, 30.0, 1.0, 'Split L 15 -> 30'),
        (1607850000, 3, 13, 5.0, 15, 5.0, 1.0, 'Another symbol change K -> M'),
        (1607936412, 1, 14, 30.0, 15, 20.0, 1.0, 'Merger 30 L into 20 M'),
        (1608022800, 4, 15, 25.0, 15, 5.0, 1.0, 'Split M 25 -> 5')
    ]
    create_corporate_actions(1, test_corp_actions)

    stock_dividends = [
        (1608368400, 1, 16, 1.0, 1050.0, 60.0, 'Stock dividend +1 N')
    ]
    create_stock_dividends(stock_dividends)

    test_trades = [
        (1609567200, 1609653600, 4, 10.0, 100.0, 1.0),
        (1609653600, 1609740000, 4, -10.0, 200.0, 5.0),
        (1609653600, 1609740000, 5, 10.0, 100.0, 1.0),
        (1609740000, 1609826400, 5, -3.0, 200.0, 2.0),
        (1609740000, 1609826400, 5, -7.0, 50.0, 3.0),
        (1609826400, 1609912800, 6, 2.0, 100.0, 2.0),
        (1609912800, 1609999200, 6, 8.0, 200.0, 2.0),
        (1609999200, 1610085600, 6, -10.0, 50.0, 2.0),
        (1610085600, 1610172000, 7, -100.0, 1.0, 1.0),
        (1610172000, 1610258400, 7, 50.0, 2.0, 1.0),
        (1610258400, 1610344800, 7, 50.0, 1.5, 1.0),
        (1610344800, 1610431200, 8, -1.3, 100.0, 1.0),
        (1610431200, 1610517600, 8, -1.7, 200.0, 1.0),
        (1610517600, 1610604000, 8, 3.0, 50.0, 1.0),
        (1610604000, 1610690400, 9, 10.0, 100.0, 0.0),
        (1610690400, 1610776800, 9, -7.0, 200.0, 0.0),
        (1610776800, 1610863200, 9, -5.0, 200.0, 0.0),
        (1610863200, 1610949600, 9, -10.0, 200.0, 0.0),
        (1610949600, 1611036000, 9, -8.0, 200.0, 0.0),
        (1611036000, 1611122400, 9, 40.0, 100.0, 0.0),
        (1611122400, 1611208800, 9, -11.0, 200.0, 0.0),
        (1611208800, 1611295200, 9, -18.0, 200.0, 0.0),
        (1611295200, 1611381600, 9, 15.0, 300.0, 0.0),
        (1611381600, 1611468000, 9, -3.0, 200.0, 0.0),
        (1611468000, 1611554400, 9, -2.0, 200.0, 0.0),
        (1611554400, 1611640800, 9, -1.0, 200.0, 0.0),
        (1606813200, 1606856400, 10, 100.0, 10.0, 0.0),
        (1607072400, 1607115600, 11, -100.0, 20.0, 0.0),
        (1607158800, 1607202000, 12, -20.0, 10.0, 0.0),
        (1607580000, 1607634000, 13, 5.0, 20.0, 0.0),
        (1607666400, 1607720400, 14, 10.0, 25.0, 0.0),
        (1607673600, 1607720400, 14, 10.0, 50.0, 0.0),
        (1607680800, 1607720400, 14, -5.0, 40.0, 0.0),
        (1608195600, 1608238800, 15, -5.0, 200.0, 1.0),
        (1608282000, 1608325200, 16, 5.0, 1000.0, 0.0),
        (1608454800, 1608498000, 16, -1.0, 1000.0, 0.0),
        (1608541200, 1608584400, 16, -5.0, 1100.0, 0.0),
        (1608616800, 1608670800, 17, 8.0, 130.0, 0.0),
        (1608624000, 1608670800, 17, -8.0, 120.0, 0.0),
        (1608620400, 1608670800, 17, 22.0, 110.0, 0.0),
        (1608627600, 1608670800, 17, -22.0, 120.0, 0.0),
        (1608703200, 1608757200, 18, 1.0, 1000.0, 0.0),
        (1608706800, 1608757200, 18, -1.0, 2000.0, 0.0),
        (1608710400, 1608757200, 18, -1.0, 1900.0, 0.0),
        (1608714000, 1608757200, 18, 1.0, 2700.0, 0.0),
        (1608717600, 1608757200, 18, -1.0, 3000.0, 0.0),
        (1608721200, 1608757200, 18, -1.0, 2000.0, 0.0),
        (1608724800, 1608757200, 18, 2.0, 2500.0, 0.0)
    ]
    create_trades(1, test_trades)

    # Build ledger
    ledger = Ledger()
    ledger.rebuild(from_timestamp=0)

    # Check single deal
    assert readSQL("SELECT COUNT(*) FROM deals_ext WHERE asset_id=4") == 1
    assert readSQL("SELECT SUM(profit) FROM deals_ext WHERE asset_id=4") == 994
    assert readSQL("SELECT SUM(fee) FROM deals_ext WHERE asset_id=4") == 6
    
    # One buy multiple sells
    assert readSQL("SELECT COUNT(*) FROM deals_ext WHERE asset_id=5") == 2
    assert readSQL("SELECT SUM(profit) FROM deals_ext WHERE asset_id=5") == -56
    assert readSQL("SELECT SUM(fee) FROM deals_ext WHERE asset_id=5") == 6

    # Multiple buy one sell
    assert readSQL("SELECT COUNT(*) FROM deals_ext WHERE asset_id=6") == 2
    assert readSQL("SELECT SUM(profit) FROM deals_ext WHERE asset_id=6") == -1306
    assert readSQL("SELECT SUM(fee) FROM deals_ext WHERE asset_id=6") == 6

    # One sell multiple buys
    assert readSQL("SELECT COUNT(*) FROM deals_ext WHERE asset_id=7") == 2
    assert readSQL("SELECT SUM(profit) FROM deals_ext WHERE asset_id=7") == -78
    assert readSQL("SELECT SUM(fee) FROM deals_ext WHERE asset_id=7") == 3

    # Multiple sells one buy
    assert readSQL("SELECT COUNT(*) FROM deals_ext WHERE asset_id=8") == 2
    assert readSQL("SELECT SUM(profit) FROM deals_ext WHERE asset_id=8") == 317
    assert readSQL("SELECT SUM(fee) FROM deals_ext WHERE asset_id=8") == 3

    # Multiple buys and sells
    assert readSQL("SELECT COUNT(*) FROM deals_ext WHERE asset_id=9") == 11
    assert readSQL("SELECT SUM(profit) FROM deals_ext WHERE asset_id=9") == 3500
    assert readSQL("SELECT SUM(fee) FROM deals_ext WHERE asset_id=9") == 0

    # Symbol change
    assert readSQL("SELECT COUNT(*) FROM deals_ext WHERE asset_id=10") == 1
    assert readSQL("SELECT COUNT(*) FROM deals_ext WHERE asset_id=11") == 1
    assert readSQL("SELECT profit FROM deals_ext WHERE asset_id=11") == 1200

    # Spin-off
    assert readSQL("SELECT COUNT(*) FROM deals_ext WHERE asset_id=12") == 1
    assert readSQL("SELECT profit FROM deals_ext WHERE asset_id=12") == approx(0)

    # Multiple corp actions
    assert readSQL("SELECT COUNT(*) FROM deals_ext WHERE asset_id=13 AND corp_action IS NOT NULL") == 1
    assert readSQL("SELECT profit FROM deals_ext WHERE asset_id=13") == 0
    assert readSQL("SELECT COUNT(*) FROM deals_ext WHERE asset_id=14") == 3
    assert readSQL("SELECT COUNT(*) FROM deals_ext WHERE asset_id=14 AND corp_action IS NOT NULL") == 2
    assert readSQL("SELECT profit FROM deals_ext WHERE asset_id=14 AND corp_action IS NULL") == 75
    assert readSQL("SELECT profit FROM deals_ext WHERE asset_id=14 AND corp_action IS NOT NULL") == 0
    assert readSQL("SELECT COUNT(*) FROM deals_ext WHERE asset_id=15 AND corp_action IS NOT NULL") == 1
    assert readSQL("SELECT profit FROM deals_ext WHERE asset_id=15") == 274

    # Stock dividend
    assert readSQL("SELECT COUNT(*) FROM deals_ext WHERE asset_id=16") == 3
    assert readSQL("SELECT SUM(profit) FROM deals_ext WHERE asset_id=16") == approx(450)
    assert readSQL("SELECT profit FROM deals_ext WHERE asset_id=16 AND close_timestamp=1608454800") == approx(0)
    assert readSQL("SELECT profit FROM deals_ext WHERE asset_id=16 AND open_timestamp=1608368400") == approx(50)

    # Order of buy/sell
    assert readSQL("SELECT COUNT(*) FROM deals_ext WHERE asset_id=17") == 2
    assert readSQL("SELECT SUM(profit) FROM deals_ext WHERE asset_id=17") == 140
    assert readSQL("SELECT COUNT(*) FROM deals_ext WHERE asset_id=18") == 4
    assert readSQL("SELECT SUM(qty) FROM deals_ext WHERE asset_id=18") == -2
    assert readSQL("SELECT SUM(profit) FROM deals_ext WHERE asset_id=18") == 200

    # totals
    assert readSQL("SELECT COUNT(*) FROM deals") == 41
    assert readSQL("SELECT COUNT(*) FROM deals WHERE open_op_type=:trade AND close_op_type=:trade",
                  [(":trade", TransactionType.Trade)]) == 29
    assert readSQL("SELECT COUNT(*) FROM deals WHERE open_op_type!=:corp_action OR close_op_type!=:corp_action",
                  [(":corp_action", TransactionType.CorporateAction)]) == 37
    assert readSQL("SELECT COUNT(*) FROM deals WHERE open_op_type=:corp_action AND close_op_type=:corp_action",
                  [(":corp_action", TransactionType.CorporateAction)]) == 4

    # validate final amounts
    query = executeSQL("SELECT MAX(id) AS mid, asset_id, amount_acc, value_acc FROM ledger "
                       "WHERE book_account=:money OR book_account=:assets GROUP BY asset_id",
                       [(":money", BookAccount.Money), (":assets", BookAccount.Assets)])
    while query.next():
        row = readSQLrecord(query, named=True)
        if row['asset_id'] == 2:  # Checking money amount
            assert row['amount_acc'] == 16700
        else:
            assert row['amount_acc'] == 0
        assert row['value_acc'] == 0
