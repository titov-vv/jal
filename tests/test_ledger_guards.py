from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_fifo
from tests.helpers import d2t, create_stocks, create_trades, create_stock_dividends, symbol_id_for
from jal.constants import BookAccount, PredefinedCategory
from jal.db.db import JalDB
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.ledger import Ledger
from jal.db.operations import LedgerTransaction, LedgerError, AssetPayment, AssetIncome

ACCOUNT = 1    # the investment account of the fixture, in USD, held with agent 1
BROKER = 1
A, B = 4, 5    # asset ids created by the fixture, right after the three seeded currencies


@pytest.fixture
def stocks(prepare_db_fifo):
    create_stocks([('A', 'A SHARE'), ('B', 'B SHARE')], currency_id=2)
    yield


def _payment(subtype, amount, tax='0', **fee):
    data = {'timestamp': d2t(210301), 'type': subtype, 'account_id': ACCOUNT, 'symbol_id': symbol_id_for(A),
            'amount': amount, 'tax': tax, 'number': 'n', 'note': 'test', **fee}
    return LedgerTransaction.create_new(LedgerTransaction.AssetPayment, data)


# Everything an operation posted, in the order it was posted: (opart, book, asset, amount, value, category, peer)
def _postings(operation) -> list:
    rows = []
    query = JalDB._exec("SELECT opart, book_account, asset_id, amount, value, category_id, peer_id FROM ledger "
                        "WHERE otype=:otype AND oid=:oid ORDER BY id",
                        [(":otype", operation.type()), (":oid", operation.id())])
    while query.next():
        opart, book, asset, amount, value, category, peer = JalDB._read_record(query)
        rows.append((opart, book, asset, Decimal(amount), Decimal(value) if value else Decimal('0'),
                     category or 0, peer or 0))
    return rows


# ----------------------------------------------------------------------------------------------------------------------
# An asset fee or tax (an ADR fee, the extra tax of an MLP distribution) is stored as a negative payment of the asset
# and is an expense of the 'Fees' category, not a negative dividend.
def test_an_asset_fee_is_booked_as_a_cost_in_fees(stocks):
    fee = _payment(AssetPayment.AssetFee, '-0.53')
    Ledger().rebuild(from_timestamp=0)

    assert _postings(fee) == [
        (0, BookAccount.Money, 2, Decimal('-0.53'), Decimal('0'), 0, 0),
        (AssetPayment.PART_VALUE, BookAccount.Costs, 2, Decimal('0.53'), Decimal('0'), PredefinedCategory.Fees, BROKER)
    ]
    assert JalAccount(ACCOUNT).get_asset_amount(d2t(210302), 2) == Decimal('9999.47')


# The same subtype with a positive amount is a fee given back, and it returns through the same category
def test_a_refunded_asset_fee_is_booked_as_income_in_fees(stocks):
    refund = _payment(AssetPayment.AssetFee, '0.53')
    Ledger().rebuild(from_timestamp=0)

    assert _postings(refund) == [
        (0, BookAccount.Money, 2, Decimal('0.53'), Decimal('0'), 0, 0),
        (AssetPayment.PART_VALUE, BookAccount.Incomes, 2, Decimal('-0.53'), Decimal('0'),
         PredefinedCategory.Fees, BROKER)
    ]
    assert JalAccount(ACCOUNT).get_asset_amount(d2t(210302), 2) == Decimal('10000.53')


# ----------------------------------------------------------------------------------------------------------------------
# A fee of a money payment is booked after the payment itself, and only its cost is posted under the fee part
def test_a_money_fee_of_a_dividend_is_booked_by_its_fee_part(stocks):
    dividend = _payment(AssetPayment.Dividend, '10', tax='1', fee='1.5', fee_account=ACCOUNT)
    Ledger().rebuild(from_timestamp=0)

    assert _postings(dividend) == [
        (0, BookAccount.Money, 2, Decimal('9'), Decimal('0'), 0, 0),
        (AssetPayment.PART_VALUE, BookAccount.Incomes, 2, Decimal('-10'), Decimal('0'),
         PredefinedCategory.Dividends, BROKER),
        (AssetPayment.PART_TAX, BookAccount.Costs, 2, Decimal('1'), Decimal('0'), PredefinedCategory.Taxes, BROKER),
        (0, BookAccount.Money, 2, Decimal('-1.5'), Decimal('0'), 0, 0),
        (AssetPayment.PART_FEE, BookAccount.Costs, 2, Decimal('1.5'), Decimal('0'), PredefinedCategory.Fees, BROKER)
    ]
    assert JalAccount(ACCOUNT).get_asset_amount(d2t(210302), 2) == Decimal('10007.5')


# A fee charged in an asset leaves the position it is held in at the basis of that position: 2 of 10 B bought at 30
def test_an_asset_fee_of_a_dividend_is_disposed_at_its_basis(stocks):
    create_trades(ACCOUNT, [(d2t(210201), d2t(210201), B, 10.0, 30.0, 0.0)])
    dividend = _payment(AssetPayment.Dividend, '10', fee='2', fee_symbol_id=symbol_id_for(B), fee_account=ACCOUNT)
    Ledger().rebuild(from_timestamp=0)

    assert _postings(dividend)[2:] == [
        (0, BookAccount.Assets, B, Decimal('-2'), Decimal('-60'), 0, 0),
        (AssetPayment.PART_FEE, BookAccount.Costs, 2, Decimal('60'), Decimal('0'), PredefinedCategory.Fees, BROKER)
    ]
    assert JalAccount(ACCOUNT).get_asset_amount(d2t(210302), B) == Decimal('8')
    assert sum(lot.open_qty() for lot in JalAccount(ACCOUNT).open_trades_list(JalAsset(B))) == Decimal('8')
    assert JalAccount(ACCOUNT).get_asset_amount(d2t(210302), 2) == Decimal('9710')   # 10000 - 300 + 10


# ----------------------------------------------------------------------------------------------------------------------
# An asset arriving on a short position would have to close a part of it, which isn't implemented. The rebuild stops
# with a reason and books nothing for the operation.
def test_an_asset_income_on_a_short_position_stops_the_rebuild(stocks):
    create_trades(ACCOUNT, [(d2t(210201), d2t(210201), A, -10.0, 100.0, 0.0)])
    create_stock_dividends([(AssetIncome.StockDividend, d2t(210301), ACCOUNT, A, 2.0, 2, 54.0, 0.0, 'Dividend +2 A')])

    ledger = Ledger()
    with pytest.raises(LedgerError, match="asset income closes short trade"):
        ledger.rebuild(from_timestamp=0)

    assert ledger.stopped_by is not None
    assert JalDB._read("SELECT COUNT(*) FROM ledger WHERE otype=:otype",
                       [(":otype", LedgerTransaction.AssetIncome)]) == 0
    assert JalAccount(ACCOUNT).get_asset_amount(d2t(210302), A) == Decimal('-10')


# ----------------------------------------------------------------------------------------------------------------------
# An account may be held with the root of the agents tree (id 0), which is no organization at all. Nothing can be
# attributed to a peer then, and the payment is refused instead of being booked against nobody.
def _detach_the_broker():
    JalDB._exec("UPDATE accounts SET organization_id=0 WHERE id=:id", [(":id", ACCOUNT)])
    JalAccount.db_cache.clear_cache()


def test_a_dividend_needs_the_bank_of_its_account(stocks):
    _detach_the_broker()
    _payment(AssetPayment.Dividend, '10')

    with pytest.raises(LedgerError, match="Can't process dividend as bank isn't set"):
        Ledger().rebuild(from_timestamp=0)

    assert JalDB._read("SELECT COUNT(*) FROM ledger WHERE otype=:otype",
                       [(":otype", LedgerTransaction.AssetPayment)]) == 0


def test_an_asset_income_needs_the_bank_of_its_account(stocks):
    _detach_the_broker()
    create_stock_dividends([(AssetIncome.StockDividend, d2t(210301), ACCOUNT, A, 2.0, 2, 54.0, 0.0, 'Dividend +2 A')])

    with pytest.raises(LedgerError, match="Can't process asset income as bank isn't set"):
        Ledger().rebuild(from_timestamp=0)

    assert JalDB._read("SELECT COUNT(*) FROM ledger WHERE otype=:otype",
                       [(":otype", LedgerTransaction.AssetIncome)]) == 0
