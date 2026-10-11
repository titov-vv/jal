import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate, QPoint
from PySide6.QtWidgets import QWidget, QMenu

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, create_stocks, create_quotes, create_trades
from jal.constants import PredefinedAccountType
from jal.db.account import JalAccountCreator
from jal.db.db import JalDB
from jal.db.ledger import Ledger
from jal.reports.portfolio import PortfolioReportWindow
from jal.widgets.icons import JalIcon

USD = 2


# Stands for the Reports object, which a report window asks for the area it lives in
class _Reports(QWidget):
    def mdi_area(self):
        return self

    def save_report(self, name, model):
        pass


def _report(grouping: str) -> PortfolioReportWindow:
    create_stocks([('AAPL', 'Apple Inc.')], currency_id=USD)
    asset_id = JalDB._read("SELECT asset_id FROM asset_symbol WHERE symbol='AAPL'")
    account = JalAccountCreator(currency_id=USD, number='U1', name='Broker', investing=1,
                                account_type=PredefinedAccountType.Broker).commit()
    create_quotes(asset_id, USD, [(d2t(210101), 100)])
    create_trades(account.id(), [(d2t(210101), d2t(210103), asset_id, 10, 100, 0)])
    Ledger().rebuild(from_timestamp=0)
    window = PortfolioReportWindow(_Reports())
    window.ui.GroupCombo.setCurrentIndex(window.ui.GroupCombo.findData(grouping))
    window.ui.PortfolioDate.setDate(QDate(2021, 3, 1))
    return window


# The level entries the context menu of the report offers
def _levels_offered(window, monkeypatch) -> list:
    view = window.ui.PortfolioTreeView
    JalIcon()   # loads the icon cache the menu is built from
    monkeypatch.setattr(QMenu, "popup", lambda menu, pos: None)
    window.onHoldingsContextMenu(QPoint(-1, -1))
    return [action.text() for action in view.findChildren(QMenu)[-1].actions() if "level" in action.text()]


# Which of the nested group rows are open, outermost first
def _open_levels(window) -> list:
    view, model = window.ui.PortfolioTreeView, window.holdings_model
    states, index = [], model.index(0, 0)
    while index.isValid() and index.internalPointer().isGroup():
        states.append(view.isExpanded(index))
        index = model.index(0, 0, index)
    return states


def test_a_level_is_offered_between_collapse_all_and_expand_all(prepare_db, monkeypatch):
    window = _report("status_id;currency_id;account_id")
    assert _levels_offered(window, monkeypatch) == ["Expand to level 2", "Expand to level 3"]
    window.ui.GroupCombo.setCurrentIndex(window.ui.GroupCombo.findData("asset_id"))
    assert _levels_offered(window, monkeypatch) == []


def test_a_level_opens_the_groups_above_it_and_closes_the_rest(prepare_db):
    window = _report("status_id;currency_id;account_id")
    assert _open_levels(window) == [True, True, True]
    window.expandToLevel(2)
    assert _open_levels(window) == [True, False, False]
    window.expandToLevel(3)
    assert _open_levels(window) == [True, True, False]
