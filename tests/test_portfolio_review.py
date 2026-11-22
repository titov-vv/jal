from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_fifo
from tests.helpers import d2t, create_stocks, create_trades
from jal.db.db import JalDB
from jal.db.ledger import Ledger
from jal.db.portfolio import JalPortfolio, PortfolioLots, PortfolioReview
from jal.reports.portfolio_review import PortfolioReviewReportWindow
from jal.reports.reports import Reports

USD, S, R = 2, 4, 5
T1, T2, T3 = d2t(220101), d2t(220201), d2t(220301)


def _tag(name) -> int:
    return JalDB._read("SELECT id FROM tags WHERE tag=:tag", [(":tag", name)])


def _trade(timestamp, asset=S) -> int:
    return JalDB._read("SELECT t.oid FROM trades t JOIN asset_symbol s ON s.id=t.symbol_id "
                       "WHERE t.timestamp=:ts AND s.asset_id=:asset", [(":ts", timestamp), (":asset", asset)])


# 10 S bought on T1 (portfolio Cash) and 5 on T2 (portfolio Card)
@pytest.fixture
def two_portfolios(prepare_db_fifo):
    PortfolioLots.forget()
    create_stocks([('S', 'Stock S'), ('R', 'Stock R')], currency_id=USD)
    create_trades(1, [(T1, T1, S, 10.0, 100.0, 0.0), (T2, T2, S, 5.0, 110.0, 0.0)])
    Ledger().rebuild(from_timestamp=0)
    JalPortfolio.assign(_trade(T1), _tag('Cash'))
    JalPortfolio.assign(_trade(T2), _tag('Card'))
    yield
    PortfolioLots.forget()


def _items() -> list:
    return [(x['issue'], x['operation'].id(), x['qty'], x['portfolio'], x['others']) for x in PortfolioReview.items()]


def test_nothing_to_review_while_every_lot_is_assigned(two_portfolios):
    assert _items() == []


# A sale of 8 for Card finds 5 Card shares and takes the other 3 from Cash
def test_a_sale_beyond_its_portfolio_spills(two_portfolios):
    create_trades(1, [(T3, T3, S, -8.0, 130.0, 0.0)])
    Ledger().rebuild(from_timestamp=0)
    JalPortfolio.assign(_trade(T3), _tag('Card'))
    assert _items() == [(PortfolioReview.Spill, _trade(T3), Decimal('3'), _tag('Card'), {_tag('Cash')})]


def test_a_sale_within_its_portfolio_does_not_spill(two_portfolios):
    create_trades(1, [(T3, T3, S, -4.0, 130.0, 0.0)])
    Ledger().rebuild(from_timestamp=0)
    JalPortfolio.assign(_trade(T3), _tag('Card'))
    assert _items() == []


# Shorts are never in a portfolio, so a cover assigned to Card takes nobody's lots
def test_covering_a_short_is_no_spill(two_portfolios):
    create_trades(1, [(T2, T2, R, -2.0, 50.0, 0.0), (T3, T3, R, 2.0, 40.0, 0.0), (T3, T3, S, -1.0, 130.0, 0.0)])
    Ledger().rebuild(from_timestamp=0)
    JalPortfolio.assign(_trade(T3, R), _tag('Card'))
    JalPortfolio.assign(_trade(T3), _tag('Cash'))   # an assigned sale, so the replay runs
    assert PortfolioLots.needs_replay()
    assert _items() == []


# An untagged buy beside assigned lots is listed; a position of unassigned lots only is not
def test_unassigned_lots_beside_assigned_ones(two_portfolios):
    create_trades(1, [(T3, T3, S, 3.0, 120.0, 0.0), (T3, T3, R, 7.0, 40.0, 0.0)])
    Ledger().rebuild(from_timestamp=0)
    assert _items() == [(PortfolioReview.Unassigned, _trade(T3), Decimal('3'), JalPortfolio.Unassigned,
                         {_tag('Cash'), _tag('Card')})]


def test_the_review_window_assigns_and_refreshes(two_portfolios):
    create_trades(1, [(T3, T3, S, 3.0, 120.0, 0.0)])
    Ledger().rebuild(from_timestamp=0)
    window = PortfolioReviewReportWindow(Reports(None, None))
    assert window.model.rowCount() == 1
    assert window.model.data_text(window.model.item(0), 1) == "Unassigned"
    assert window.model.data_text(window.model.item(0), 6) == "Card, Cash"
    window.set_portfolio([window.model.item(0)], _tag('Cash'))
    assert window.model.rowCount() == 0
    assert window.ui.SummaryLbl.text() == "0 to review"
