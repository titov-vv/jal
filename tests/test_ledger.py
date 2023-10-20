from decimal import Decimal

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_fifo, prepare_db_ledger
from tests.helpers import d2t, create_stocks, create_actions, create_trades, create_quotes, \
    create_corporate_actions, create_stock_dividends, create_transfers
from constants import BookAccount, PredefinedAccountType
from jal.db.ledger import Ledger, LedgerAmounts
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.peer import JalPeer
from jal.db.operations import LedgerTransaction, Dividend


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
    expected_book_amounts ={
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
    assert len(open_trades) == 0
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
        (Dividend.StockDividend, 1643907900, 1, 4, 2.0, 2, 54.0, 0.0, 'Stock dividend +2 A')
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
    LedgerTransaction.get_operation(LedgerTransaction.Dividend, 1).update_amount(Decimal('3.0'))

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
    # Prepare trades and corporate actions setup
    test_assets = [
        ('A', 'A SHARE'),   # id 4 -> 18
        ('B', 'B SHARE'),
        ('C', 'C SHARE'),
        ('D', 'D SHARE'),
        ('E', 'E SHARE'),
        ('F', 'F SHARE'),
        ('G1', 'G SHARE BEFORE'),
        ('G2', 'G SHARE AFTER'),
        ('H', 'H SPIN-OFF FROM G'),
        ('K', 'K SHARE'),
        ('L', 'L SHARE'),
        ('M', 'M SHARE'),
        ('N', 'N WITH STOCK DIVIDEND'),
        ('O', 'O SHARE'),
        ('P', 'P SHARE'),
    ]
    create_stocks(test_assets, currency_id=2)

    test_corp_actions = [
        (1606899600, 3, 10, 100.0, 'Symbol change G1 -> G2', [(11, 100.0, 1.0)]),
        (1606986000, 2, 11, 100.0, 'Spin-off H from G2', [(11, 100.0, 0.8), (12, 20.0, 0.2)]),
        (1607763600, 4, 14, 15.0, 'Split L 15 -> 30', [(14, 30.0, 1.0)]),
        (1607850000, 3, 13, 5.0, 'Another symbol change K -> M', [(15, 5.0, 1.0)]),
        (1607936412, 1, 14, 30.0, 'Merger 30 L into 20 M', [(15, 20.0, 1.0)]),
        (1608022800, 4, 15, 25.0, 'Split M 25 -> 5', [(15, 5.0, 1.0)])
    ]
    create_corporate_actions(1, test_corp_actions)

    stock_dividends = [
        (Dividend.StockDividend, 1608368400, 1, 16, 1.0, 2, 1050.0, 60.0, 'Stock dividend +1 N')
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

    trades = JalAccount(1).closed_trades_list()
    # totals
    assert len(trades) == 41
    assert len([x for x in trades if x.open_operation().type() == LedgerTransaction.Trade and x.close_operation().type() == LedgerTransaction.Trade]) == 29
    assert len([x for x in trades if x.open_operation().type() != LedgerTransaction.CorporateAction or x.close_operation().type() != LedgerTransaction.CorporateAction]) == 37
    assert len([x for x in trades if x.open_operation().type() == LedgerTransaction.CorporateAction and x.close_operation().type() == LedgerTransaction.CorporateAction]) == 4

    # Check single deal
    trades = [x for x in JalAccount(1).closed_trades_list() if x.asset().id() == 4]
    assert len(trades) == 1
    assert trades[0].profit() == Decimal('994.0')
    assert trades[0].fee() == Decimal('6.0')

    # One buy multiple sells
    trades = [x for x in JalAccount(1).closed_trades_list() if x.asset().id() == 5]
    assert len(trades) == 2
    assert sum([x.profit() for x in trades]) == Decimal('-56')
    assert sum([x.fee() for x in trades]) == Decimal('6')

    # Multiple buy one sell
    trades = [x for x in JalAccount(1).closed_trades_list() if x.asset().id() == 6]
    assert len(trades) == 2
    assert sum([x.profit() for x in trades]) == Decimal('-1306')
    assert sum([x.fee() for x in trades]) == Decimal('6')

    # One sell multiple buys
    trades = [x for x in JalAccount(1).closed_trades_list() if x.asset().id() == 7]
    assert len(trades) == 2
    assert sum([x.profit() for x in trades]) == Decimal('-78')
    assert sum([x.fee() for x in trades]) == Decimal('3')

    # Multiple sells one buy
    trades = [x for x in JalAccount(1).closed_trades_list() if x.asset().id() == 8]
    assert len(trades) == 2
    assert sum([x.profit() for x in trades]) == Decimal('317')
    assert sum([x.fee() for x in trades]) == Decimal('3')

    # Multiple buys and sells
    trades = [x for x in JalAccount(1).closed_trades_list() if x.asset().id() == 9]
    assert len(trades) == 11
    assert sum([x.profit() for x in trades]) == Decimal('3500')
    assert sum([x.fee() for x in trades]) == Decimal('0')

    # Symbol change
    trades = [x for x in JalAccount(1).closed_trades_list() if x.asset().id() == 10]
    assert len(trades) == 1
    trades = [x for x in JalAccount(1).closed_trades_list() if x.asset().id() == 11]
    assert len(trades) == 2
    assert sum([x.profit() for x in trades]) == Decimal('1200')

    # Spin-off
    trades = [x for x in JalAccount(1).closed_trades_list() if x.asset().id() == 12]
    assert len(trades) == 1
    assert sum([x.profit() for x in trades]) == Decimal('0')

    # Multiple corp actions
    trades = [x for x in JalAccount(1).closed_trades_list() if x.asset().id() == 13]
    assert len(trades) == 1
    assert trades[0].close_operation().type() == LedgerTransaction.CorporateAction
    assert sum([x.profit() for x in trades]) == Decimal('0')
    trades = [x for x in JalAccount(1).closed_trades_list() if x.asset().id() == 14]
    assert len(trades) == 4
    assert len([x for x in trades if x.open_operation().type() != LedgerTransaction.CorporateAction]) == 3
    assert len([x for x in trades if x.close_operation().type() != LedgerTransaction.CorporateAction]) == 1
    assert [x.profit() for x in trades if x.open_operation().type() != LedgerTransaction.CorporateAction] == [Decimal('75'), Decimal('0'), Decimal('0')]
    trades = [x for x in JalAccount(1).closed_trades_list() if x.asset().id() == 15]
    assert len(trades) == 3
    assert len([x for x in trades if x.close_operation().type() != LedgerTransaction.CorporateAction]) == 1
    assert [x.profit() for x in trades] == [Decimal('0'), Decimal('0'), Decimal('274')]

    # Stock dividend
    trades = [x for x in JalAccount(1).closed_trades_list() if x.asset().id() == 16]
    assert len(trades) == 3
    assert sum([x.profit() for x in trades]) == Decimal('450')
    assert sum([x.profit() for x in trades if x.close_operation().timestamp() == 1608454800]) == Decimal('0')
    assert sum([x.profit() for x in trades if x.open_operation().timestamp() == 1608368400]) == Decimal('50')

    # Order of buy/sell
    trades = [x for x in JalAccount(1).closed_trades_list() if x.asset().id() == 17]
    assert len(trades) == 2
    assert sum([x.profit() for x in trades]) == Decimal('140')
    trades = [x for x in JalAccount(1).closed_trades_list() if x.asset().id() == 18]
    assert len(trades) == 4
    assert sum([x.qty() for x in trades]) == Decimal('-2')
    assert sum([x.profit() for x in trades]) == Decimal('200')

    # validate final amounts
    # validate book amounts and values
    amounts = LedgerAmounts("amount_acc")
    values = LedgerAmounts("value_acc")
    assert amounts[BookAccount.Money, 1, 1] == Decimal('0')
    assert amounts[BookAccount.Money, 1, 2] == Decimal('16700')
    for asset_id in range(4, 18):
        assert values[BookAccount.Assets, 1, asset_id] == Decimal('0')


def test_asset_transfer(prepare_db):
    peer = JalPeer(data={'name': 'Test Peer', 'parent': 0}, create=True)
    account1 = JalAccount(
        data={'type': PredefinedAccountType.Investment, 'name': 'account.USD', 'number': 'U7654321', 'currency': 2,
              'active': 1, 'organization': 1, 'precision': 10},
        create=True)
    account2 = JalAccount(
        data={'type': PredefinedAccountType.Investment, 'name': 'account.RUB', 'number': 'U7654321', 'currency': 1,
              'active': 1, 'organization': 1, 'precision': 10},
        create=True)

    # Create starting balance
    create_actions([(d2t(220101), 1, 1, [(4, 1000.0)])])

    # Prepare single stock
    create_stocks([('A.USD', 'A SHARE')], currency_id=2)   # id = 4
    JalAsset(4).add_symbol('A.RUB', 1, '')

    create_trades(1, [(d2t(220201), d2t(220203), 4, 2.0, 100.0, 1.0)])
    create_trades(1, [(d2t(220205), d2t(220207), 4, 3.0, 100.0, 1.0)])
    create_trades(2, [(d2t(220211), d2t(220213), 4, -5.0, 8000.0, 5.0)])

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
    assert len(trades) == 2
    assert sum([x.profit() for x in trades]) == Decimal('-2')   # sum of open trades fee
    trades = JalAccount(2).closed_trades_list()
    assert len(trades) == 1
    assert sum([x.profit() for x in trades]) == Decimal('2495')

    # Modify closing deal quantity
    LedgerTransaction.get_operation(LedgerTransaction.Trade, 3).update_price(Decimal('7700'))

    # Build ledger from given date
    ledger = Ledger()
    ledger.rebuild()

    trades = JalAccount(1).closed_trades_list()
    assert len(trades) == 2
    assert sum([x.profit() for x in trades]) == Decimal('-2')
    trades = JalAccount(2).closed_trades_list()
    assert len(trades) == 1
    assert sum([x.profit() for x in trades]) == Decimal('995')
