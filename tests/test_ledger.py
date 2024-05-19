from decimal import Decimal

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_fifo, prepare_db_ledger
from tests.helpers import d2t, create_stocks, create_actions, create_trades, create_quotes, \
    create_corporate_actions, create_stock_dividends, create_transfers
from constants import BookAccount, PredefinedCategory
from jal.db.ledger import Ledger, LedgerAmounts
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.peer import JalPeer
from jal.db.operations import LedgerTransaction, AssetPayment


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
    amounts = LedgerAmounts("amount_acc")
    expected_book_amounts = {
        BookAccount.Costs: Decimal('130'),
        BookAccount.Incomes: Decimal('-139'),
        BookAccount.Money: Decimal('9'),
        BookAccount.Assets: Decimal('0'),
        BookAccount.Liabilities: Decimal('0'),
        BookAccount.Transfers: Decimal('0')
    }
    for book in expected_book_amounts:
        assert amounts[(book, 1, 1)] == expected_book_amounts[book]

    actions = [
        (1638360000, 1, 1, [(5, -34.0)]),
        (1638363600, 1, 1, [(7, 11.0)])
    ]
    create_actions(actions)

    # Build ledger for recent transactions only
    ledger = Ledger()
    ledger.rebuild()

    # validate book amounts and values
    amounts = LedgerAmounts("amount_acc")
    values = LedgerAmounts("value_acc")
    expected_book_amounts = {
        BookAccount.Costs: Decimal('164'),
        BookAccount.Incomes: Decimal('-1.5E+2'),
        BookAccount.Money: Decimal('0'),
        BookAccount.Assets: Decimal('0'),
        BookAccount.Liabilities: Decimal('-14'),
        BookAccount.Transfers: Decimal('0')
    }
    expected_book_values = {
        BookAccount.Costs: Decimal('0'),
        BookAccount.Incomes: Decimal('0'),
        BookAccount.Money: Decimal('0'),
        BookAccount.Assets: Decimal('0'),
        BookAccount.Liabilities: Decimal('0'),
        BookAccount.Transfers: Decimal('0')
    }
    for book in expected_book_amounts:
        assert amounts[(book, 1, 1)] == expected_book_amounts[book]
        assert values[(book, 1, 1)] == expected_book_values[book]

    # Re-build from the middle - validation should pass again
    ledger.rebuild(from_timestamp=1638352800)
    for book in expected_book_amounts:
        assert amounts[(book, 1, 1)] == expected_book_amounts[book]
        assert values[(book, 1, 1)] == expected_book_values[book]


def test_ledger_rounding(prepare_db_fifo):
    create_stocks([('A', 'A SHARE'), ('B', 'B SHARE')], currency_id=1)  # id = 4, 5
    test_trades = [
        (1609567200, 1609653600, 4, 2.0, 100.0, 1.0),  # + 2 A @ 100.0
        (1609891200, 1609977600, 5, -1.0, 200.0, 1.0),   # -1 B @ 200.0
        (1610064000, 1610150400, 5, -1.0, 200.0, 1.0),   # -1 B @ 200.0
        (1610236800, 1610323200, 5, -1.0, 200.0, 1.0)    # -1 B @ 200.0
    ]
    create_trades(1, test_trades)
    test_corp_actions = [
        (1609729200, 4, 4, 2.0, 'Split 2 A -> 3 B', [(5, 3.0, 1.0)])
    ]
    create_corporate_actions(1, test_corp_actions)

    ledger = Ledger()
    ledger.rebuild(from_timestamp=0)

    amount = LedgerAmounts("amount")
    amount_acc = LedgerAmounts("amount_acc")
    value_acc = LedgerAmounts("value_acc")
    assert amount_acc[(BookAccount.Assets, 1, 5)] == Decimal('0')
    assert value_acc[(BookAccount.Assets, 1, 5)] == Decimal('0')
    assert amount_acc[(BookAccount.Incomes, 1, 2)] == Decimal('-10400')
    assert amount[(BookAccount.Incomes, 1, 2)] == Decimal('-133.34')

def test_buy_sell_change(prepare_db_fifo):
    # Prepare single stock
    create_stocks([('A', 'A SHARE')], currency_id=2)  # id = 4

    test_trades = [
        (1609567200, 1609653600, 4, 10.0, 100.0, 1.0),
        (1609729200, 1609815600, 4, -7.0, 200.0, 5.0)
    ]
    create_trades(1, test_trades)

    # insert action between trades to shift frontier
    create_actions([(1609642800, 1, 1, [(7, 100.0)])])

    # Build ledger
    ledger = Ledger()
    ledger.rebuild(from_timestamp=0)

    # Validate initial deal quantity
    trades = JalAccount(1).closed_trades_list()
    assert len(trades) == 1
    assert trades[0].qty() == Decimal('7')

    # Modify closing deal quantity
    LedgerTransaction.get_operation(LedgerTransaction.Trade, 2).update_qty(Decimal('-5'))

    # Re-build ledger from last actual data
    ledger.rebuild()

    # Check that deal quantity remains correct
    trades = JalAccount(1).closed_trades_list()
    assert len(trades) == 1
    assert trades[0].qty() == Decimal('5')

    trades = JalAccount(1).open_trades_list(JalAsset(4))
    assert len(trades) == 1

    # Add one more trade
    create_trades(1, [(1609815600, 1609902000, 4, -8.0, 150.0, 3.0)])

    # Re-build ledger from last actual data
    ledger.rebuild()

    # Check that deal quantity remains correct
    trades = JalAccount(1).closed_trades_list()
    assert len(trades) == 2
    open_trades = JalAccount(1).open_trades_list(JalAsset(4))
    assert len(open_trades) == 1

    LedgerTransaction.get_operation(LedgerTransaction.Trade, 2).delete()

    open_trades = JalAccount(1).open_trades_list(JalAsset(4))
    assert len(open_trades) == 1
    assert ledger.getCurrentFrontier() < 1609729200

    # Re-build ledger from last actual data
    ledger.rebuild()

    # Check that deal quantity remains correct
    trades = JalAccount(1).closed_trades_list()
    assert len(trades) == 1
    assert trades[0].qty() == Decimal('8')


def test_stock_dividend_change(prepare_db_fifo):
    # Prepare single stock
    create_stocks([('A', 'A SHARE')], currency_id=2)   # id = 4

    test_trades = [
        (1628852820, 1629158400, 4, 2.0, 53.13, 0.34645725),
        (1628852820, 1629158400, 4, 8.0, 53.13, -0.0152),
        (1643628654, 1643760000, 4, 5.0, 47.528, 0.35125725),
        (1644351123, 1644523923, 4, -17.0, 60.0, 0.0)
    ]
    create_trades(1, test_trades)

    # Insert a stock dividend between trades
    stock_dividends = [
        (AssetPayment.StockDividend, 1643907900, 1, 4, 2.0, 2, 54.0, 0.0, 'Stock dividend +2 A')
    ]
    create_stock_dividends(stock_dividends)

    # insert action between trades and stock dividend to shift frontier
    create_actions([(1643746000, 1, 1, [(7, 100.0)])])

    # Build ledger
    ledger = Ledger()
    ledger.rebuild(from_timestamp=0)

    # Validate initial deal quantity
    trades = JalAccount(1).closed_trades_list()
    assert len(trades) == 4

    # Modify stock dividend
    LedgerTransaction.get_operation(LedgerTransaction.AssetPayment, 1).update_amount(Decimal('3.0'))

    # Re-build ledger from last actual data
    ledger.rebuild()

    # Check that deal quantity remains correct
    trades = JalAccount(1).closed_trades_list()
    assert len(trades) == 4

    # Put quotation back and rebuild
    create_quotes(4, 2, [(1643907900, 54.0)])

    # Re-build ledger from last actual data
    ledger.rebuild()

    # Check that deal quantity remains correct
    trades = JalAccount(1).closed_trades_list()
    assert len(trades) == 4


def test_fifo(prepare_db_fifo):
    # Prepare an account to transfer asset from
    transfer_account = JalAccount(
        data={'name': 'Transfer Acc.', 'number': '12345', 'currency': 2, 'active': 1, 'investing': 1, 'organization': 1, 'precision': 10},
        create=True)
    assert transfer_account.id() == 2
    create_actions([(d2t(240101), 2, 1, [(PredefinedCategory.StartingBalance, 1000.0)])])
    # Prepare trades and corporate actions setup
    test_assets = [
        ('A', 'A SHARE'),   # asset_id == 4, single buy and sell operation
        ('B', 'B SHARE'),   # 1 buy operation closed with 2 sells
        ('C', 'C SHARE'),   # 2 buy operations closed with 1 sell
        ('D', 'D SHARE'),   # 1 short sell with 2 buy operations
        ('E', 'E SHARE'),   # 2 short sells closed with 1 buy operation
        ('F', 'F SHARE'),   # multiple buy-sell operations with 11 deals as result
        ('G1', 'G SHARE BEFORE'),    # 1 buy operation that is closed with symbol change
        ('G2', 'G SHARE AFTER'),     # this stock appears after symbol change, then spins-off H and closed with 1 sell
        ('H', 'H SPIN-OFF FROM G'),  # spun-off from G2 and closed with single sell
        ('K', 'K SHARE'),   # 1 buy closed with symbol change to M
        ('L', 'L SHARE'),   # buy, buy, sell in 1 day (1 deal), split 1:2, conversion to M
        ('M', 'M SHARE'),   # symbol change from K and 2 conversions from L, then split 5:1, 1 sell (3 deals)
        ('N', 'N WITH STOCK DIVIDEND'),  # 5 buy, then 1 stock dividend, then sell 1 and 5 (3 deals)
        ('O', 'O SHARE'),   # buy/sell, buy/sell
        ('P', 'P SHARE'),   # buy/sell, sell/buy, sell/sell/buy (4 deals)
        ('Q', 'Q SHARE'),   # 3 buy via 2 sells and buy/sell (5 deals in total)
        ('R', 'WITH ASSET TRANSFER')  # id == 20, buy on 2 different accounts, transfer and sell (3 deals)
    ]
    create_stocks(test_assets, currency_id=2)

    test_corp_actions = [
        (1606899600, 3, 10, 100.0, 'Symbol change G1 -> G2', [(11, 100.0, 1.0)]),
        (1606986000, 2, 11, 100.0, 'Spin-off H from G2', [(11, 100.0, 0.8), (12, 20.0, 0.2)]),
        (d2t(201214), 4, 14, 15.0, 'Split L 15 -> 30', [(14, 30.0, 1.0)]),
        (d2t(201215), 3, 13, 5.0, 'Another symbol change K -> M', [(15, 5.0, 1.0)]),
        (d2t(201216), 1, 14, 30.0, 'Merger 30 L into 20 M', [(15, 20.0, 1.0)]),
        (d2t(201217), 4, 15, 25.0, 'Split M 25 -> 5', [(15, 5.0, 1.0)])
    ]
    create_corporate_actions(1, test_corp_actions)

    stock_dividends = [
        (AssetPayment.StockDividend, 1608368400, 1, 16, 1.0, 2, 1050.0, 60.0, 'Stock dividend +1 N')
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
        (d2t(201210), d2t(201210), 13, 5.0, 20.0, 0.0),
        (d2t(201211), d2t(201211), 14, 10.0, 25.0, 0.0),
        (d2t(201212), d2t(201212), 14, 10.0, 50.0, 0.0),
        (d2t(201213), d2t(201213), 14, -5.0, 40.0, 0.0),
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
        (1608724800, 1608757200, 18, 2.0, 2500.0, 0.0),
        (d2t(210405), d2t(210406), 19, +5.0, 100, 0.0),
        (d2t(210405), d2t(210406), 19, +12.0, 100, 0.0),
        (d2t(210405), d2t(210406), 19, +8.0, 100, 0.0),
        (d2t(210409), d2t(210410), 19, -20.0, 200, 0.0),
        (d2t(210409), d2t(210410), 19, -5.0, 200, 0.0),
        (d2t(210501), d2t(210502), 19, +10.0, 200, 0.0),
        (d2t(210510), d2t(210511), 19, -10.0, 100, 0.0),
        (d2t(240503), d2t(210504), 20, +10.0, 200, 0.0),  # Buy the same asset R after transfer
        (d2t(240507), d2t(210508), 20, -3.0, 200, 0.0),   # Sell asset R after transfer in 3 different operations
        (d2t(240509), d2t(210510), 20, -10.0, 200, 0.0),
        (d2t(240511), d2t(210512), 20, -7.0, 200, 0.0)
    ]
    create_trades(1, test_trades)

    transfer_trades = [
        (d2t(240501), d2t(240502), 20, +10.0, 100, 0.0)   # Buy asset R for further transfer to another account
    ]
    create_trades(2, transfer_trades)
    create_transfers([(d2t(240505), 2, 10.0, 1, 0.0, 20)])  # Move asset R from acc.id2 to acc.id1 (with no currency/value change)

    # Build ledger
    ledger = Ledger()
    ledger.rebuild(from_timestamp=0)

    # Check single deal
    trades = JalAccount(1).closed_trades_list(asset=JalAsset(4))
    assert len(trades) == 1
    assert trades[0].profit() == Decimal('994.0')
    assert trades[0].fee() == Decimal('6.0')

    # One buy multiple sells
    trades = JalAccount(1).closed_trades_list(asset=JalAsset(5))
    assert len(trades) == 2
    assert sum([x.profit() for x in trades]) == Decimal('-56')
    assert sum([x.fee() for x in trades]) == Decimal('6')

    # Multiple buy one sell
    trades = JalAccount(1).closed_trades_list(asset=JalAsset(6))
    assert len(trades) == 2
    assert sum([x.profit() for x in trades]) == Decimal('-1306')
    assert sum([x.fee() for x in trades]) == Decimal('6')

    # One sell multiple buys
    trades = JalAccount(1).closed_trades_list(asset=JalAsset(7))
    assert len(trades) == 2
    assert sum([x.profit() for x in trades]) == Decimal('-78')
    assert sum([x.fee() for x in trades]) == Decimal('3')

    # Multiple sells one buy
    trades = JalAccount(1).closed_trades_list(asset=JalAsset(8))
    assert len(trades) == 2
    assert sum([x.profit() for x in trades]) == Decimal('317')
    assert sum([x.fee() for x in trades]) == Decimal('3')

    # Multiple buys and sells
    trades = JalAccount(1).closed_trades_list(asset=JalAsset(9))
    assert len(trades) == 11
    assert sum([x.profit() for x in trades]) == Decimal('3500')
    assert sum([x.fee() for x in trades]) == Decimal('0')

    trades = JalAccount(1).closed_trades_list(asset=JalAsset(19))
    assert len(trades) == 5
    assert [x.qty() for x in trades if x.asset().id() == 19] == [Decimal('5'), Decimal('12'), Decimal('3'), Decimal('5'), Decimal('10')]

    # Symbol change
    trades = JalAccount(1).closed_trades_list(asset=JalAsset(10))
    assert len(trades) == 0
    trades = JalAccount(1).closed_trades_list(asset=JalAsset(11))
    assert len(trades) == 1
    assert sum([x.profit() for x in trades]) == Decimal('1200')

    # Spin-off
    trades = JalAccount(1).closed_trades_list(asset=JalAsset(12))
    assert len(trades) == 1
    assert sum([x.profit() for x in trades]) == Decimal('0')

    # Multiple corp actions
    trades = JalAccount(1).closed_trades_list(asset=JalAsset(13))
    assert len(trades) == 0
    trades = JalAccount(1).closed_trades_list(asset=JalAsset(14))
    assert len(trades) == 1
    assert trades[0].profit() == Decimal('75')
    trades = JalAccount(1).closed_trades_list(asset=JalAsset(15))
    assert len(trades) == 2
    assert [x.profit() for x in trades] == [Decimal('99.80'), Decimal('174.20')]

    # Stock dividend
    trades = JalAccount(1).closed_trades_list(asset=JalAsset(16))
    assert len(trades) == 3
    assert sum([x.profit() for x in trades]) == Decimal('450')
    assert sum([x.profit() for x in trades if x.close_operation().timestamp() == 1608454800]) == Decimal('0')
    assert sum([x.profit() for x in trades if x.open_operation().timestamp() == 1608368400]) == Decimal('50')

    # Order of buy/sell
    trades = JalAccount(1).closed_trades_list(asset=JalAsset(17))
    assert len(trades) == 2
    assert sum([x.profit() for x in trades]) == Decimal('140')
    trades = JalAccount(1).closed_trades_list(asset=JalAsset(18))
    assert len(trades) == 4
    assert sum([x.qty() for x in trades]) == Decimal('-2')
    assert sum([x.profit() for x in trades]) == Decimal('200')

    # Deals with transfer
    trades = JalAccount(1).closed_trades_list(asset=JalAsset(20))
    assert len(trades) == 4
    assert [x.qty() for x in trades] == [Decimal('3'), Decimal('7'), Decimal('3'), Decimal('7')]
    assert [x.profit() for x in trades] == [Decimal('300'), Decimal('700'), Decimal('0'), Decimal('0')]

    # totals
    trades = JalAccount(1).closed_trades_list()
    assert len(trades) == 43
    assert len([x for x in trades if x.open_operation().type() == LedgerTransaction.Trade]) == 40

    # validate final amounts
    # validate book amounts and values
    amounts = LedgerAmounts("amount_acc")
    values = LedgerAmounts("value_acc")
    assert amounts[BookAccount.Money, 1, 1] == Decimal('0')
    assert amounts[BookAccount.Money, 1, 2] == Decimal('20200')
    for asset_id in range(4, 18):
        assert values[BookAccount.Assets, 1, asset_id] == Decimal('0')


def test_open_price(prepare_db_fifo):
    test_assets = [
        ('A', 'A SHARE'),  # id == 4
        ('B', 'B SHARE'),
        ('C', 'C SHARE'),
        ('D', 'D SHARE')   # id == 7
    ]
    create_stocks(test_assets, currency_id=2)

    test_trades = [
        (d2t(240501), d2t(240501), 4, 20.0, 100.0, 0),
        (d2t(240502), d2t(240502), 4, 20.0, 120.0, 0),
        (d2t(240503), d2t(240503), 4, 10.0, 110.0, 0),
        (d2t(240504), d2t(240504), 4, -5.0, 110.0, 0),
        (d2t(240505), d2t(240505), 4, -5.0, 110.0, 0),
        (d2t(240501), d2t(240501), 5, 20.0, 100.0, 0),
        (d2t(240503), d2t(240503), 5, -1.0, 400.0, 0),
        (d2t(240505), d2t(240505), 5, -1.0, 300.0, 0)
    ]
    create_trades(1, test_trades)

    test_corp_actions = [
        (d2t(240502), 4, 5, 20.0, 'Split 20 B -> 5 B', [(5, 5.0, 1.0)]),
        (d2t(240504), 2, 5, 4.0, 'Spin-off 1 C from 4 B', [(5, 4.0, 0.75), (6, 1.0, 0.25)]),
        (d2t(240506), 2, 5, 3.0, 'Spin-off 2 D from 3 B', [(5, 3.0, 0.5), (7, 2.0, 0.5)])
    ]
    create_corporate_actions(1, test_corp_actions)

    # Build ledger
    ledger = Ledger()
    ledger.rebuild(from_timestamp=0)

    positions = [(x['remaining_qty'], x['price']) for x in JalAccount(1).open_trades_list(asset=JalAsset(4))]
    assert positions == [(Decimal('10'), Decimal('100')), (Decimal('20'), Decimal('120')), (Decimal('10'), Decimal('110'))]
    positions = [(x['remaining_qty'], x['price']) for x in JalAccount(1).open_trades_list(asset=JalAsset(5))]
    assert positions == [(Decimal('3'), Decimal('150'))]
    positions = [(x['remaining_qty'], x['price']) for x in JalAccount(1).open_trades_list(asset=JalAsset(6))]
    assert positions == [(Decimal('1'), Decimal('400'))]
    positions = [(x['remaining_qty'], x['price']) for x in JalAccount(1).open_trades_list(asset=JalAsset(7))]
    assert positions == [(Decimal('2'), Decimal('225'))]


def test_asset_transfer(prepare_db):
    peer = JalPeer(data={'name': 'Test Peer', 'parent': 0}, create=True)
    account1 = JalAccount(
        data={'name': 'account.USD', 'number': 'U7654321', 'currency': 2, 'active': 1, 'investing': 1, 'organization': 1, 'precision': 10},
        create=True)
    account2 = JalAccount(
        data={'name': 'account.RUB', 'number': 'U7654321', 'currency': 1, 'active': 1, 'investing': 1, 'organization': 1, 'precision': 10},
        create=True)
    assert account1.id() == 1
    assert account2.id() == 2

    # Create starting balance
    create_actions([(d2t(220101), 1, 1, [(4, 1000.0)])])

    # Prepare single stock
    create_stocks([('A.USD', 'A SHARE')], currency_id=2)   # id = 4
    JalAsset(4).add_symbol('A.RUB', 1, '')

    create_trades(1, [(d2t(220201), d2t(220203), 4, 2.0, 100.0, 1.0)])  # Buy A on account.USD in 2 transactions
    create_trades(1, [(d2t(220205), d2t(220207), 4, 3.0, 100.0, 1.0)])
    create_trades(2, [(d2t(220211), d2t(220213), 4, -5.0, 8000.0, 5.0)]) # Sell A from account.RUB in one shot

    create_transfers([(d2t(220207), 1, 5.0, 2, 37500.0, 4)])   # Move A from account.USD to account.RUB with new cost basis of 37500 RUB

    # Build ledger
    ledger = Ledger()
    ledger.rebuild(from_timestamp=0)

    amount = LedgerAmounts("amount")
    value = LedgerAmounts("value")
    assert amount[BookAccount.Transfers, 1, 4] == Decimal('5')
    assert amount[BookAccount.Transfers, 2, 4] == Decimal('-5')
    assert value[BookAccount.Transfers, 1, 4] == Decimal('5E+2')
    assert value[BookAccount.Transfers, 2, 4] == Decimal('-3.75E+4')
    trades = JalAccount(1).closed_trades_list()
    assert len(trades) == 0
    assert sum([x.profit() for x in trades]) == Decimal('0')   # sum of open trades fee
    trades = JalAccount(2).closed_trades_list()
    assert len(trades) == 2
    assert sum([x.profit() for x in trades]) == Decimal('2493')

    # Modify closing deal quantity
    LedgerTransaction.get_operation(LedgerTransaction.Trade, 3).update_price(Decimal('7700'))

    # Build ledger from given date
    ledger = Ledger()
    ledger.rebuild()

    trades = JalAccount(1).closed_trades_list()
    assert len(trades) == 0
    assert sum([x.profit() for x in trades]) == Decimal('0')
    trades = JalAccount(2).closed_trades_list()
    assert len(trades) == 2
    assert sum([x.profit() for x in trades]) == Decimal('993')
