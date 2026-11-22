from decimal import Decimal

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QDialog, QTableView, QStyleOptionViewItem

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_fifo
from tests.helpers import d2t, create_stocks, create_trades, create_quotes, create_dividends
from jal.db.db import JalDB
from jal.db.ledger import Ledger
from jal.db.operations import LedgerTransaction
from jal.db.operations_model import OperationsModel
from jal.db.portfolio import JalPortfolio
from jal.widgets.delegates import PORTFOLIO_ROLE, TransactionTieDelegate
from jal.widgets.position_details import PositionDetails, LotsModel
from jal.widgets.selection_dialog import SelectReferenceDialog

USD, S = 2, 4
T1, T2, T3, T4 = d2t(220101), d2t(220201), d2t(220301), d2t(220401)


def _tag(name) -> int:
    return JalDB._read("SELECT id FROM tags WHERE tag=:tag", [(":tag", name)])


def _trade(timestamp) -> int:
    return JalDB._read("SELECT oid FROM trades WHERE timestamp=:ts", [(":ts", timestamp)])


# Two lots of S on account 1: 10 bought at 100 on T1 and 5 at 110 on T2
@pytest.fixture
def two_lots(prepare_db_fifo):
    create_stocks([('S', 'Stock S')], currency_id=USD)
    create_trades(1, [(T1, T1, S, 10.0, 100.0, 0.0), (T2, T2, S, 5.0, 110.0, 0.0)])
    create_quotes(S, USD, [(T3, 120.0)])
    Ledger().rebuild(from_timestamp=0)
    yield


def _window(parent) -> PositionDetails:
    return PositionDetails(1, S, USD, T4, parent=parent)


def _pick(monkeypatch, tag_id):
    def pick(dialog):
        dialog.selected_id = tag_id
        return QDialog.Accepted
    monkeypatch.setattr(SelectReferenceDialog, "exec", pick)


# "Assign tag" on a lot operation sets its portfolio; on an operation that opens no lot it does nothing
def test_assign_tag_sets_the_portfolio_of_a_lot_operation(two_lots):
    LedgerTransaction.get_operation(LedgerTransaction.Trade, _trade(T1)).assign_tag(_tag('Cash'))
    assert JalPortfolio.assignments() == {_trade(T1): _tag('Cash')}
    create_dividends([(T3, 1, S, 10.0, 0.0, 'dividend')])
    dividend = JalDB._read("SELECT oid FROM asset_payments")
    LedgerTransaction.get_operation(LedgerTransaction.AssetPayment, dividend).assign_tag(_tag('Cash'))
    assert JalPortfolio.assignments() == {_trade(T1): _tag('Cash')}


# The operations list knows the portfolio of each row's operation
def test_the_operations_list_carries_the_portfolio(two_lots):
    parent = QWidget()
    view = QTableView(parent)
    model = OperationsModel(view)
    view.setModel(model)
    model.setDateRange(0, T4)
    rows = {model._data[x]['oid']: x for x in range(model.rowCount())}
    model.assign_tag_to_rows([rows[_trade(T2)]], _tag('Card'))
    rows = {model._data[x]['oid']: x for x in range(model.rowCount())}
    assert model.data(model.index(rows[_trade(T2)], 1), PORTFOLIO_ROLE) == _tag('Card')
    assert model.data(model.index(rows[_trade(T1)], 1), PORTFOLIO_ROLE) == 0
    assert "Portfolio: Card" in model.data(model.index(rows[_trade(T2)], 1), Qt.ToolTipRole)
    delegate = TransactionTieDelegate(view)
    for oid, marked in ((_trade(T2), True), (_trade(T1), False)):
        option = QStyleOptionViewItem()
        delegate.initStyleOption(option, model.index(rows[oid], 1))
        assert bool(option.features & QStyleOptionViewItem.HasDecoration) == marked
        assert option.decorationPosition == QStyleOptionViewItem.Right or not marked


def test_position_details_assign_the_checked_lots(two_lots, monkeypatch):
    parent = QWidget()
    window = _window(parent)
    model = window.model
    assert [model.data(model.index(x, LotsModel.PORTFOLIO)) for x in range(2)] == ['', '']
    assert model.footerData(LotsModel.PORTFOLIO) is None          # nothing split, no hint
    model.setData(model.index(0, LotsModel.CHECK), Qt.Unchecked.value, Qt.CheckStateRole)
    _pick(monkeypatch, _tag('Card'))
    window.assign_portfolio(model.assignable_lots(True))
    assert JalPortfolio.assignments() == {_trade(T2): _tag('Card')}
    assert [model.data(model.index(x, LotsModel.PORTFOLIO)) for x in range(2)] == ['', 'Card']
    assert model.footerData(LotsModel.PORTFOLIO) == "1 unassigned"

    _pick(monkeypatch, _tag('Cash'))
    window.assign_portfolio(model.unassigned_lots())                # the upkeep action leaves assigned lots alone
    assert JalPortfolio.assignments() == {_trade(T1): _tag('Cash'), _trade(T2): _tag('Card')}
    assert model.footerData(LotsModel.PORTFOLIO) is None

    window.set_portfolio(model.assignable_lots(True), JalPortfolio.Unassigned)
    assert JalPortfolio.assignments() == {_trade(T1): _tag('Cash')}


# A short lot takes no portfolio: assigning it would tag the sale that opened it
def test_a_short_lot_is_not_assignable(prepare_db_fifo):
    create_stocks([('S', 'Stock S')], currency_id=USD)
    create_trades(1, [(T1, T1, S, -10.0, 100.0, 0.0)])
    create_quotes(S, USD, [(T3, 120.0)])
    Ledger().rebuild(from_timestamp=0)
    parent = QWidget()
    window = _window(parent)
    assert len(window.lots) == 1
    assert window.model.assignable_lots(False) == [] and window.model.unassigned_lots() == []
