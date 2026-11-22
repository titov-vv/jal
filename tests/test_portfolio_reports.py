from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_fifo
from tests.helpers import d2t, create_stocks, create_trades, create_dividends, symbol_id_for
from jal.db.db import JalDB
from jal.db.ledger import Ledger
from jal.db.operations import LedgerTransaction, AssetPayment, AssetIncome
from jal.db.portfolio import JalPortfolio, PortfolioLots
from jal.reports.assets_payments import AssetsPaymentsReportWindow
from jal.reports.deals import DealsReportWindow
from jal.reports.reports import Reports

USD, S = 2, 4
T1, T2, T3, T4 = d2t(220101), d2t(220201), d2t(220301), d2t(220401)


def _tag(name) -> int:
    return JalDB._read("SELECT id FROM tags WHERE tag=:tag", [(":tag", name)])


def _trade(timestamp) -> int:
    return JalDB._read("SELECT oid FROM trades WHERE timestamp=:ts", [(":ts", timestamp)])


# 10 S bought at 100 on T1 (portfolio Cash) and 5 at 110 on T2 (portfolio Card)
@pytest.fixture
def two_portfolios(prepare_db_fifo):
    PortfolioLots.forget()
    create_stocks([('S', 'Stock S')], currency_id=USD)
    create_trades(1, [(T1, T1, S, 10.0, 100.0, 0.0), (T2, T2, S, 5.0, 110.0, 0.0)])
    Ledger().rebuild(from_timestamp=0)
    JalPortfolio.assign(_trade(T1), _tag('Cash'))
    JalPortfolio.assign(_trade(T2), _tag('Card'))
    yield
    PortfolioLots.forget()


def _choose(window, portfolio):
    window.ui.PortfolioCombo.refresh()
    window.ui.PortfolioCombo.setCurrentIndex(window.ui.PortfolioCombo.findData(portfolio))


def _deals(portfolio) -> list:
    window = DealsReportWindow(Reports(None, None))
    window.ui.ReportRange.setRange(T1, T4)
    window.ui.ReportAccountEdit.selection_done(1)
    _choose(window, portfolio)
    return [(x.qty(), x.profit()) for x in window.trades_model._trades]


def _payments(portfolio) -> list:
    window = AssetsPaymentsReportWindow(Reports(None, None))
    window.ui.ReportRange.setRange(T1, T4)
    window.ui.ReportAccountEdit.selection_done(1)
    _choose(window, portfolio)
    model = window.payments_model
    return [(amount, tax) for _x, amount, tax in model._data], model._total, model._total_tax


def test_the_filter_lists_the_portfolios_in_use(two_portfolios):
    window = DealsReportWindow(Reports(None, None))
    combo = window.ui.PortfolioCombo
    assert [combo.itemText(i) for i in range(combo.count())] == ["All", "Card", "Cash", "Unassigned"]
    assert combo.selected() is None
    combo.setCurrentIndex(combo.findData(_tag('Cash')))
    JalPortfolio.assign(_trade(T2), JalPortfolio.Unassigned)
    combo.refresh()
    assert [combo.itemText(i) for i in range(combo.count())] == ["All", "Cash", "Unassigned"]
    assert combo.selected() == _tag('Cash')


# A sale of 8 assigned to Card takes Card's 5 first and the other 3 from Cash; the unfiltered report stays plain FIFO
def test_deals_by_portfolio_follow_the_portfolio_replay(two_portfolios):
    create_trades(1, [(T3, T3, S, -8.0, 130.0, 0.0)])
    Ledger().rebuild(from_timestamp=0)
    JalPortfolio.assign(_trade(T3), _tag('Card'))
    assert _deals(_tag('Card')) == [(Decimal('5'), Decimal('100'))]
    assert _deals(_tag('Cash')) == [(Decimal('3'), Decimal('90'))]
    assert _deals(JalPortfolio.Unassigned) == []
    assert _deals(None) == [(Decimal('8'), Decimal('240'))]


# Only buys assigned: the live deals are filtered, no replay runs
def test_deals_without_assigned_sales_need_no_replay(two_portfolios):
    create_trades(1, [(T3, T3, S, -12.0, 130.0, 0.0)])
    Ledger().rebuild(from_timestamp=0)
    assert _deals(_tag('Cash')) == [(Decimal('10'), Decimal('300'))]
    assert _deals(_tag('Card')) == [(Decimal('2'), Decimal('40'))]
    assert PortfolioLots._store is None


# 30 paid (3 withheld) on 15 shares held 10 : 5 - the parts add up to the payment
def test_a_payment_is_shared_out_by_quantity_held(two_portfolios):
    create_dividends([(d2t(220215), 1, S, Decimal('30'), Decimal('3'), 'dividend')])
    assert _payments(_tag('Cash')) == ([(Decimal('20'), Decimal('2'))], Decimal('20'), Decimal('2'))
    assert _payments(_tag('Card')) == ([(Decimal('10'), Decimal('1'))], Decimal('10'), Decimal('1'))
    assert _payments(JalPortfolio.Unassigned) == ([], Decimal('0'), Decimal('0'))
    assert _payments(None) == ([(Decimal('30'), Decimal('3'))], Decimal('30'), Decimal('3'))


# Holders are counted before the ex-date: Card's shares, bought on it, get nothing
def test_a_payment_follows_the_holders_before_the_ex_date(two_portfolios):
    LedgerTransaction.create_new(LedgerTransaction.AssetPayment, {
        'timestamp': d2t(220215), 'ex_date': T2, 'type': AssetPayment.Dividend, 'account_id': 1,
        'symbol_id': symbol_id_for(S), 'amount': '30', 'tax': '3', 'number': '', 'note': 'dividend'})
    assert _payments(_tag('Cash'))[0] == [(Decimal('30'), Decimal('3'))]
    assert _payments(_tag('Card'))[0] == []


# Nothing held at payment time (and no ex-date): the payment stays Unassigned
def test_a_payment_after_the_position_is_closed_is_unassigned(two_portfolios):
    create_trades(1, [(T3, T3, S, -15.0, 130.0, 0.0)])
    create_dividends([(T4 - 1, 1, S, Decimal('30'), Decimal('3'), 'dividend')])
    Ledger().rebuild(from_timestamp=0)
    assert _payments(JalPortfolio.Unassigned)[0] == [(Decimal('30'), Decimal('3'))]
    assert _payments(_tag('Cash'))[0] == []


# An asset income opens a lot, so it goes whole to its own portfolio
def test_an_asset_income_goes_to_its_own_portfolio(two_portfolios):
    oid = LedgerTransaction.create_new(LedgerTransaction.AssetIncome, {
        'timestamp': d2t(220215), 'type': AssetIncome.StockDividend, 'account_id': 1,
        'symbol_id': symbol_id_for(S), 'amount': '2', 'price': '120', 'tax': '0.5', 'number': '',
        'note': 'stock dividend'}).id()
    Ledger().rebuild(from_timestamp=0)
    JalPortfolio.assign(oid, _tag('Card'))
    assert _payments(_tag('Card'))[0] == [(Decimal('2'), Decimal('0.5'))]
    assert _payments(_tag('Cash'))[0] == []


def test_shares_add_up_to_the_value():
    parts = PortfolioLots.share_out(Decimal('10'), {1: Decimal('1'), 2: Decimal('1'), 3: Decimal('1')})
    assert sum(parts.values(), Decimal('0')) == Decimal('10')
    assert parts[1] == parts[2] == Decimal('10') / Decimal('3')
    assert PortfolioLots.share_out(Decimal('7'), {}) == {JalPortfolio.Unassigned: Decimal('7')}
