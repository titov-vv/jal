import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from decimal import Decimal

import pytest
from PySide6.QtWidgets import QApplication, QWidget

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_fifo
from tests.helpers import d2t, create_assets, create_trades
from jal.constants import PredefinedAsset, PredefinedCategory
from jal.db.db import JalDB
from jal.db.ledger import Ledger
from jal.db.operations import LedgerTransaction
from jal.db.portfolio import JalPortfolio, PortfolioLots
from jal.widgets.icons import JalIcon
from jal.widgets.operations_widget import OperationsWidget

USD, ACME = 2, 4


# A spending with a category and a tag that the list doesn't show, and a trade in a stock with an ISIN
@pytest.fixture
def ledger(prepare_db_fifo):
    PortfolioLots.forget()
    tag = JalDB._exec("INSERT INTO tags (pid, tag) VALUES (0, 'Holiday Trip')", commit=True).lastInsertId()
    LedgerTransaction.create_new(LedgerTransaction.IncomeSpending, {
        'timestamp': d2t(260301), 'account_id': 1, 'peer_id': 1,
        'lines': [{'amount': Decimal('-10'), 'category_id': PredefinedCategory.Fees, 'tag_id': tag, 'note': ''}]})
    create_assets([('ACME', 'Acme Rockets Inc.', 'US0000000ACM', USD, PredefinedAsset.Stock, 0)])
    create_trades(1, [(d2t(260302), d2t(260302), ACME, Decimal('1'), Decimal('100'), Decimal('0'))])
    Ledger().rebuild(from_timestamp=0)
    trade = JalDB._read("SELECT oid FROM trades WHERE timestamp=:ts", [(":ts", d2t(260302))])
    JalPortfolio.assign(trade, JalDB._read("SELECT id FROM tags WHERE tag='Card'"))
    yield
    PortfolioLots.forget()


@pytest.fixture
def window(ledger):
    JalIcon()
    parent = QWidget()
    window = OperationsWidget(parent)
    window.ui.DateRange.setRange(d2t(260201), d2t(260331))
    yield window
    parent.deleteLater()


def _rows(window) -> list:
    model = window.operations_filtered_model
    return [model.index(row, 2).data() for row in range(model.rowCount())]


def _search(window, text) -> list:
    window.ui.SearchString.setText(text)
    window.ui.SearchString.returnPressed.emit()
    return _rows(window)


@pytest.mark.parametrize("text, otype", [
    ("holiday trip", LedgerTransaction.IncomeSpending),     # tag
    ("FEES", LedgerTransaction.IncomeSpending),             # category
    ("us0000000acm", LedgerTransaction.Trade),              # ISIN
    ("card", LedgerTransaction.Trade),                      # portfolio
])
def test_hidden_names_are_searched(window, text, otype):
    assert len(_search(window, text)) == 1
    source = window.operations_filtered_model.mapToSource(window.operations_filtered_model.index(0, 0))
    assert window.operations_model.get_operation(source.row())[0] == otype


def test_shown_text_is_still_searched(window):
    assert len(_rows(window)) == 2
    assert len(_search(window, "acme")) == 1
    assert _search(window, "no such thing") == []
    assert len(_search(window, "  ")) == 2


def test_search_waits_for_a_pause_in_typing(window):
    window.ui.SearchString.setText("rockets")
    assert window._search_timer.isActive()
    assert len(_rows(window)) == 2
    window._search_timer.timeout.emit()
    assert len(_rows(window)) == 1


def test_names_follow_the_period(window):
    assert len(_search(window, "rockets")) == 1
    window.ui.DateRange.setRange(d2t(260401), d2t(260430))
    assert _rows(window) == []
    window.ui.DateRange.setRange(d2t(260201), d2t(260331))
    assert len(_rows(window)) == 1


def test_a_long_list_is_searched_on_enter_only(window, monkeypatch):
    monkeypatch.setattr(OperationsWidget, "LIVE_SEARCH_ROWS", 1)
    window.ui.SearchString.setText("rockets")
    assert not window._search_timer.isActive()
    assert len(_rows(window)) == 2
    window.ui.SearchString.returnPressed.emit()
    assert len(_rows(window)) == 1


# Currencies are left out of the hidden names: a currency code finds only what shows it
def test_currencies_are_not_hidden_names(window):
    names = Ledger.get_search_names(d2t(260201), d2t(260331))
    assert all('usd' not in x.split('\n') for x in names.values())
    assert 'acme' in "\n".join(names.values()).split('\n')
