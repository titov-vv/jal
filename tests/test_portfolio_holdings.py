from decimal import Decimal

import pytest
from PySide6.QtCore import QDate, QModelIndex

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_fifo
from tests.helpers import d2t, create_stocks, create_trades, create_quotes
from tests.test_asset_country import _Reports
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.db import JalDB
from jal.db.ledger import Ledger
from jal.db.portfolio import JalPortfolio, PortfolioLots
from jal.reports.portfolio import PortfolioReportWindow

USD, S = 2, 4
T1, T2, T3 = d2t(220101), d2t(220201), d2t(220301)


def _tag(name) -> int:
    return JalDB._read("SELECT id FROM tags WHERE tag=:tag", [(":tag", name)])


def _trade(timestamp) -> int:
    return JalDB._read("SELECT oid FROM trades WHERE timestamp=:ts", [(":ts", timestamp)])


# 10 S bought at 100 on T1 (portfolio Cash) and 5 at 110 on T2 (portfolio Card), quoted 120; no replay is left over
@pytest.fixture
def two_portfolios(prepare_db_fifo):
    PortfolioLots.forget()
    create_stocks([('S', 'Stock S')], currency_id=USD)
    create_trades(1, [(T1, T1, S, 10.0, 100.0, 0.0), (T2, T2, S, 5.0, 110.0, 0.0)])
    create_quotes(S, USD, [(T2, 120.0)])
    Ledger().rebuild(from_timestamp=0)
    JalPortfolio.assign(_trade(T1), _tag('Cash'))
    JalPortfolio.assign(_trade(T2), _tag('Card'))
    yield
    PortfolioLots.forget()


def _portfolios(timestamp) -> list:
    return [(tag, x.open_qty()) for tag, x in PortfolioLots.lots(JalAccount(1), JalAsset(S), timestamp)]


# Assigned buys only: the live lots are the answer and no replay runs
def test_assigned_openers_need_no_replay(two_portfolios):
    assert not PortfolioLots.needs_replay()
    assert _portfolios(T3) == [(_tag('Cash'), Decimal('10')), (_tag('Card'), Decimal('5'))]
    assert PortfolioLots._store is None


# An assigned sale needs the replay; it is kept until an assignment changes or the ledger is rebuilt
def test_an_assigned_sale_replays_and_the_replay_is_kept(two_portfolios):
    create_trades(1, [(T3, T3, S, -5.0, 130.0, 0.0)])
    Ledger().rebuild(from_timestamp=0)
    JalPortfolio.assign(_trade(T3), _tag('Card'))
    assert PortfolioLots.needs_replay()
    assert _portfolios(T3) == [(_tag('Cash'), Decimal('10'))]       # the live lots would say 5 + 5
    store = PortfolioLots._store
    assert not PortfolioLots.needs_replay() and _portfolios(T3) and PortfolioLots._store is store
    JalPortfolio.assign(_trade(T3), _tag('Cash'))
    assert PortfolioLots.needs_replay()
    assert _portfolios(T3) == [(_tag('Cash'), Decimal('5')), (_tag('Card'), Decimal('5'))]
    Ledger().rebuild(from_timestamp=0)
    assert PortfolioLots._store is None


def _report(grouping) -> PortfolioReportWindow:
    window = PortfolioReportWindow(_Reports())
    window.ui.PortfolioDate.setDate(QDate(2022, 3, 1))
    window.ui.GroupCombo.setCurrentIndex(window.ui.GroupCombo.findData(grouping))
    return window


# {group header: [(qty, cost) of each position row under it]}
def _groups(window) -> dict:
    model = window.holdings_model
    groups = {}
    for row in range(model.rowCount(QModelIndex())):
        group = model.index(row, 0)
        items = [model.index(x, 0, group).internalPointer().details() for x in range(model.rowCount(group))]
        groups[group.internalPointer().details()['portfolio']] = [(x['qty'], x['value_i']) for x in items]
    return groups


# Grouped by portfolio, a position splits into its portfolios and money stays unassigned
def test_holdings_split_by_portfolio(two_portfolios):
    window = _report("portfolio_id")
    groups = _groups(window)
    assert groups['Cash'] == [(Decimal('10'), Decimal('1000'))]
    assert groups['Card'] == [(Decimal('5'), Decimal('550'))]
    assert [x[0] for x in groups['Unassigned']] == [JalAccount(1).get_asset_amount(d2t(220301), USD)]


# The position rows of the report, wherever the grouping puts them
def _positions(model, parent=QModelIndex()) -> list:
    rows = []
    for row in range(model.rowCount(parent)):
        index = model.index(row, 0, parent)
        rows += _positions(model, index) if model.rowCount(index) else [index.internalPointer().details()]
    return rows


# Quantities of the parts sum to the position the other groupings show
def test_portfolio_rows_sum_to_the_position(two_portfolios):
    JalPortfolio.assign(_trade(T1), JalPortfolio.Unassigned)
    for grouping in ("portfolio_id", "portfolio_id;account_id", "portfolio_id;asset_id"):
        rows = [x for x in _positions(_report(grouping).holdings_model) if x['asset_id'] == S]
        assert sorted((x['portfolio'], x['qty']) for x in rows) == [('Card', Decimal('5')),
                                                                    ('Unassigned', Decimal('10'))], grouping
    whole = [x for x in _positions(_report("asset_id").holdings_model) if x['asset_id'] == S]
    assert [x['qty'] for x in whole] == [Decimal('15')]
