from pytest import approx

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_fifo, prepare_db_ledger
from constants import PredefinedAsset
from jal.db.ledger import Ledger
from jal.db.helpers import readSQL, executeSQL, readSQLrecord


def test_ledger(prepare_db_ledger):
    actions = [
        (1, 1638349200, 1, 1, [(1, 5, -100.0)]),
        (2, 1638352800, 1, 1, [(2, 6, -30.0), (3, 8, 55.0)]),
        (3, 1638356400, 1, 1, [(4, 7, 84.0)])
    ]

    for action in actions:
        assert executeSQL("INSERT INTO actions (id, timestamp, account_id, peer_id) "
                          "VALUES (:id, :timestamp, :account, :peer)",
                          [(":id", action[0]), (":timestamp", action[1]),
                           (":account", action[2]), (":peer", action[3])], commit=True) is not None
        for detail in action[4]:
            assert executeSQL("INSERT INTO action_details (id, pid, category_id, amount) "
                              "VALUES (:id, :pid, :category, :amount)",
                              [(":id", detail[0]), (":pid", action[0]),
                               (":category", detail[1]), (":amount", detail[2])], commit=True) is not None

    # Build ledger from scratch
    ledger = Ledger()
    ledger.rebuild(from_timestamp=0)

    # validate book amounts
    expected_book_values = [None, 130.0, -139.0, 9.0, None, 0.0]
    query = executeSQL("SELECT MAX(sid) AS msid, book_account, sum_amount, sum_value "
                       "FROM ledger_sums GROUP BY book_account")
    while query.next():
        row = readSQLrecord(query, named=True)
        assert row['sum_amount'] == expected_book_values[row['book_account']]

    actions = [
        (4, 1638360000, 1, 1, [(5, 5, -34.0)]),
        (5, 1638363600, 1, 1, [(6, 7, 11.0)])
    ]

    for action in actions:
        assert executeSQL("INSERT INTO actions (id, timestamp, account_id, peer_id) "
                          "VALUES (:id, :timestamp, :account, :peer)",
                          [(":id", action[0]), (":timestamp", action[1]),
                           (":account", action[2]), (":peer", action[3])], commit=True) is not None
        for detail in action[4]:
            assert executeSQL("INSERT INTO action_details (id, pid, category_id, amount) "
                              "VALUES (:id, :pid, :category, :amount)",
                              [(":id", detail[0]), (":pid", action[0]),
                               (":category", detail[1]), (":amount", detail[2])], commit=True) is not None

    # Build ledger for recent transactions only
    ledger = Ledger()
    ledger.rebuild()

    # validate book amounts
    expected_book_values = [None, 164.0, -150.0, -0.0, None, -14.0]
    query = executeSQL("SELECT MAX(sid) AS msid, book_account, sum_amount, sum_value "
                       "FROM ledger_sums GROUP BY book_account")
    while query.next():
        row = readSQLrecord(query, named=True)
        assert row['sum_amount'] == expected_book_values[row['book_account']]


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
    for asset in test_assets:
        assert executeSQL("INSERT INTO assets (id, name, type_id, full_name) "
                          "VALUES (:id, :name, :type, :full_name)",
                          [(":id", asset[0]), (":name", asset[1]),
                           (":type", PredefinedAsset.Stock), (":full_name", asset[2])], commit=True) is not None
        
    test_corp_actions = [
        (1, 1606899600, 3, 10, 100.0, 11, 100.0, 1.0, 'Symbol change G1 -> G2'),
        (2, 1606986000, 2, 11, 100.0, 12, 20.0, 0.8, 'Spin-off H from G2'),
        (3, 1607763600, 4, 14, 15.0, 14, 30.0, 1.0, 'Split L 15 -> 30'),
        (4, 1607850000, 3, 13, 5.0, 15, 5.0, 1.0, 'Another symbol change K -> M'),
        (5, 1607936412, 1, 14, 30.0, 15, 20.0, 1.0, 'Merger 30 L into 20 M'),
        (6, 1608022800, 4, 15, 25.0, 15, 5.0, 1.0, 'Split M 25 -> 5'),
        (7, 1608368400, 5, 16, 5.0, 16, 6.0, 1.0, 'Stock dividend +1 N')
    ]    
    for action in test_corp_actions:
        assert executeSQL(
            "INSERT INTO corp_actions "
            "(id, timestamp, account_id, type, asset_id, qty, asset_id_new, qty_new, basis_ratio, note) "
            "VALUES (:id, :timestamp, 1, :type, :a_o, :q_o, :a_n, :q_n, :ratio, :note)",
            [(":id", action[0]), (":timestamp", action[1]), (":type", action[2]),
             (":a_o", action[3]), (":q_o", action[4]), (":a_n", action[5]), (":q_n", action[6]),
             (":ratio", action[7]), (":note", action[8])], commit=True) is not None

    test_trades = [
        (1, 1609567200, 1609653600, 4, 10.0, 100.0, 1.0),
        (2, 1609653600, 1609740000, 4, -10.0, 200.0, 5.0),
        (3, 1609653600, 1609740000, 5, 10.0, 100.0, 1.0),
        (4, 1609740000, 1609826400, 5, -3.0, 200.0, 2.0),
        (5, 1609740000, 1609826400, 5, -7.0, 50.0, 3.0),
        (6, 1609826400, 1609912800, 6, 2.0, 100.0, 2.0),
        (7, 1609912800, 1609999200, 6, 8.0, 200.0, 2.0),
        (8, 1609999200, 1610085600, 6, -10.0, 50.0, 2.0),
        (9, 1610085600, 1610172000, 7, -100.0, 1.0, 1.0),
        (10, 1610172000, 1610258400, 7, 50.0, 2.0, 1.0),
        (11, 1610258400, 1610344800, 7, 50.0, 1.5, 1.0),
        (12, 1610344800, 1610431200, 8, -1.3, 100.0, 1.0),
        (13, 1610431200, 1610517600, 8, -1.7, 200.0, 1.0),
        (14, 1610517600, 1610604000, 8, 3.0, 50.0, 1.0),
        (15, 1610604000, 1610690400, 9, 10.0, 100.0, 0.0),
        (16, 1610690400, 1610776800, 9, -7.0, 200.0, 0.0),
        (17, 1610776800, 1610863200, 9, -5.0, 200.0, 0.0),
        (18, 1610863200, 1610949600, 9, -10.0, 200.0, 0.0),
        (19, 1610949600, 1611036000, 9, -8.0, 200.0, 0.0),
        (20, 1611036000, 1611122400, 9, 40.0, 100.0, 0.0),
        (21, 1611122400, 1611208800, 9, -11.0, 200.0, 0.0),
        (22, 1611208800, 1611295200, 9, -18.0, 200.0, 0.0),
        (23, 1611295200, 1611381600, 9, 15.0, 300.0, 0.0),
        (24, 1611381600, 1611468000, 9, -3.0, 200.0, 0.0),
        (25, 1611468000, 1611554400, 9, -2.0, 200.0, 0.0),
        (26, 1611554400, 1611640800, 9, -1.0, 200.0, 0.0),
        (27, 1606813200, 1606856400, 10, 100.0, 10.0, 0.0),
        (28, 1607072400, 1607115600, 11, -100.0, 20.0, 0.0),
        (29, 1607158800, 1607202000, 12, -20.0, 10.0, 0.0),
        (30, 1607580000, 1607634000, 13, 5.0, 20.0, 0.0),
        (31, 1607666400, 1607720400, 14, 10.0, 25.0, 0.0),
        (32, 1607673600, 1607720400, 14, 10.0, 50.0, 0.0),
        (33, 1607680800, 1607720400, 14, -5.0, 40.0, 0.0),
        (34, 1608195600, 1608238800, 15, -5.0, 200.0, 1.0),
        (35, 1608282000, 1608325200, 16, 5.0, 1000.0, 0.0),
        (36, 1608454800, 1608498000, 16, -1.0, 1000.0, 0.0),
        (37, 1608541200, 1608584400, 16, -5.0, 1100.0, 0.0),
        (38, 1608616800, 1608670800, 17, 8.0, 130.0, 0.0),
        (39, 1608624000, 1608670800, 17, -8.0, 120.0, 0.0),
        (40, 1608620400, 1608670800, 17, 22.0, 110.0, 0.0),
        (41, 1608627600, 1608670800, 17, -22.0, 120.0, 0.0),
        (42, 1608703200, 1608757200, 18, 1.0, 1000.0, 0.0),
        (43, 1608706800, 1608757200, 18, -1.0, 2000.0, 0.0),
        (44, 1608710400, 1608757200, 18, -1.0, 1900.0, 0.0),
        (45, 1608714000, 1608757200, 18, 1.0, 2700.0, 0.0),
        (46, 1608717600, 1608757200, 18, -1.0, 3000.0, 0.0),
        (47, 1608721200, 1608757200, 18, -1.0, 2000.0, 0.0),
        (48, 1608724800, 1608757200, 18, 2.0, 2500.0, 0.0)
    ]
    for trade in test_trades:
        assert executeSQL(
            "INSERT INTO trades (id, timestamp, settlement, account_id, asset_id, qty, price, fee) "
            "VALUES (:id, :timestamp, :settlement, 1, :asset, :qty, :price, :fee)",
            [(":id", trade[0]), (":timestamp", trade[1]), (":settlement", trade[2]), (":asset", trade[3]),
             (":qty", trade[4]), (":price", trade[5]), (":fee", trade[6])]) is not None

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
    assert readSQL("SELECT SUM(profit) FROM deals_ext WHERE asset_id=16") == approx(1500)
    assert readSQL("SELECT profit FROM deals_ext WHERE asset_id=16 AND close_timestamp=1608454800") == approx(166.666667)
    assert readSQL("SELECT profit FROM deals_ext WHERE asset_id=16 AND close_timestamp=1608541200") == approx(1333.333333)

    # Order of buy/sell
    assert readSQL("SELECT COUNT(*) FROM deals_ext WHERE asset_id=17") == 2
    assert readSQL("SELECT SUM(profit) FROM deals_ext WHERE asset_id=17") == 140
    assert readSQL("SELECT COUNT(*) FROM deals_ext WHERE asset_id=18") == 4
    assert readSQL("SELECT SUM(qty) FROM deals_ext WHERE asset_id=18") == -2
    assert readSQL("SELECT SUM(profit) FROM deals_ext WHERE asset_id=18") == 200

    # totals
    assert readSQL("SELECT COUNT(*) FROM deals AS d "
                   "LEFT JOIN sequence as os ON os.id = d.open_sid "
                   "LEFT JOIN sequence as cs ON cs.id = d.close_sid") == 41
    assert readSQL("SELECT COUNT(*) FROM deals AS d "
                   "LEFT JOIN sequence as os ON os.id = d.open_sid "
                   "LEFT JOIN sequence as cs ON cs.id = d.close_sid "
                   "WHERE os.type==3 AND cs.type==3") == 27
    assert readSQL("SELECT COUNT(*) FROM deals AS d "
                   "LEFT JOIN sequence as os ON os.id = d.open_sid "
                   "LEFT JOIN sequence as cs ON cs.id = d.close_sid "
                   "WHERE os.type!=5 OR cs.type!=5") == 37
    assert readSQL("SELECT COUNT(*) FROM deals AS d "
                    "LEFT JOIN sequence as os ON os.id = d.open_sid "
                   "LEFT JOIN sequence as cs ON cs.id = d.close_sid "
                   "WHERE os.type==5 AND cs.type==5") == 4

    # validate final amounts
    query = executeSQL("SELECT MAX(sid) AS msid, asset_id, sum_amount, sum_value FROM ledger_sums GROUP BY asset_id")
    while query.next():
        row = readSQLrecord(query, named=True)
        if row['asset_id'] == 2:  # Checking money amount
            assert row['sum_amount'] == 16760
        else:
            assert row['sum_amount'] == 0
        assert row['sum_value'] == 0
