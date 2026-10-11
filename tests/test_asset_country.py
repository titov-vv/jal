import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QWidget, QInputDialog

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, create_stocks, create_quotes, create_trades
from jal.constants import AccountStatus, PredefinedAccountType
from jal.db.account import JalAccountCreator
from jal.db.asset import JalAsset
from jal.db.country import JalCountry
from jal.db.db import JalDB
from jal.db.ledger import Ledger
from jal.reports.portfolio import PortfolioReportWindow

USD = 2


def _stock() -> int:
    create_stocks([('AAPL', 'Apple Inc.')], currency_id=USD)
    return JalDB._read("SELECT asset_id FROM asset_symbol WHERE symbol='AAPL'")


def _stored_country(asset_id: int) -> int:
    return JalDB._read("SELECT country_id FROM assets WHERE id=:id", [(":id", asset_id)])


def test_the_country_of_an_asset_is_stored(prepare_db):
    asset_id = _stock()
    us = JalCountry(data={'code': 'us'}, search=True).id()
    assert JalAsset(asset_id).country().id() == 0
    JalAsset(asset_id).set_country(us)
    assert _stored_country(asset_id) == us
    assert JalAsset(asset_id).country().code() == 'us'   # a second object reads it through the shared cache


def test_the_country_list_names_every_country_once(prepare_db):
    names = JalCountry.names()
    assert len(names) == JalDB._read("SELECT COUNT(*) FROM countries")
    assert len(set(names.values())) == len(names)   # the dialog answers with a name, so a name must mean one country
    assert list(names.values()) == sorted(names.values())


# Stands for the Reports object, which a report window asks for the area it lives in
class _Reports(QWidget):
    def mdi_area(self):
        return self

    def save_report(self, name, model):
        pass


def _report_with_a_position(asset_id: int) -> PortfolioReportWindow:
    account = JalAccountCreator(currency_id=USD, number='U1', name='Broker', investing=1,
                                account_type=PredefinedAccountType.Broker).commit()
    create_quotes(asset_id, USD, [(d2t(210101), 100)])
    create_trades(account.id(), [(d2t(210101), d2t(210103), asset_id, 10, 100, 0)])
    Ledger().rebuild(from_timestamp=0)
    window = PortfolioReportWindow(_Reports())
    window.ui.GroupCombo.setCurrentIndex(window.ui.GroupCombo.findData("country_id;asset_id"))
    window.ui.PortfolioDate.setDate(QDate(2021, 3, 1))
    return window


# The country group of the report the asset is listed under
def _group_of(window, asset_id: int) -> int:
    model = window.holdings_model
    for country in [model._root.getChild(row) for row in range(model._root.childrenCount())]:
        if asset_id in [country.getChild(row).details()['asset_id'] for row in range(country.childrenCount())]:
            return country.details()['country_id']


def test_the_report_sets_the_country_and_regroups(prepare_db, monkeypatch):
    asset_id = _stock()
    window = _report_with_a_position(asset_id)
    model = window.holdings_model
    us = JalCountry(data={'code': 'us'}, search=True)
    assert _group_of(window, asset_id) == 0
    position = model.index(0, 0, model.index(0, 0))   # the asset's group row, which states no currency
    offered = {}

    def pick(parent, title, label, items, current, editable):
        offered.update(label=label, current=items[current])
        return us.name(), True
    monkeypatch.setattr(QInputDialog, "getItem", pick)
    window.setCountry(position)
    assert 'AAPL' in offered['label']
    assert offered['current'] == JalCountry(0).name()   # the dialog opens on the country the asset has
    assert _stored_country(asset_id) == us.id()
    assert _group_of(window, asset_id) == us.id()


def test_a_cancelled_dialog_changes_nothing(prepare_db, monkeypatch):
    asset_id = _stock()
    window = _report_with_a_position(asset_id)
    model = window.holdings_model
    monkeypatch.setattr(QInputDialog, "getItem", lambda *args: (JalCountry(1).name(), False))
    window.setCountry(model.index(0, 0, model.index(0, 0)))
    assert _stored_country(asset_id) == 0
