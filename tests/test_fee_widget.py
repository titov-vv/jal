# Tests of FeeWidget - the fee of an operation as a widget of its own. What the fee DOES is test_fee_api.py and
# test_fees_table.py; this is only about showing, editing, attaching and detaching one.
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from decimal import Decimal

import pytest

from PySide6.QtWidgets import QWidget

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_fifo
from tests.helpers import d2t, create_stocks, create_trades, symbol_id_for, operation_id
from jal.db.db import JalDB
from jal.db.account import JalAccountCreator
from jal.db.operations import LedgerTransaction, FeeKind
from jal.widgets.fee_widget import FeeWidget


# A live parent for the widgets below - a widget built without one is collected at a moment of Qt's choosing
@pytest.fixture
def qapp_parent(project_root):
    parent = QWidget()
    yield parent
    parent.deleteLater()


# An account that may bear a fee, a second one that may bear it instead, and a crypto asset to pay gas in
@pytest.fixture
def accounts_and_assets(prepare_db_fifo):
    JalAccountCreator(currency_id=2, number='U2', name='Other', investing=1, organization=1).commit()
    create_stocks([('A', 'Asset A'), ('GAS', 'Native coin')], currency_id=2)   # asset ids 4 and 5
    yield


def _widget(parent, kinds, account_may_differ=False, oid=0):
    widget = FeeWidget(parent)
    widget.setup_fees(kinds=kinds, account_may_differ=account_may_differ, parent=parent)
    widget.set_fee_account(1)
    widget.set_operation(oid)
    return widget


def _trade_with_fee(fee) -> int:
    create_trades(1, [(d2t(220101), d2t(220101), 4, 10.0, 100.0, fee)])
    return operation_id(LedgerTransaction.Trade, 1)


# Qt Designer builds the widget with createWidget(parent) and nothing else - no database, no setup_fees() - and what
# it must get is the real fee row rather than a lone "+", so that it can be grabbed and placed on a form.
def test_the_widget_builds_with_no_database_behind_it(qapp_parent):
    widget = FeeWidget(qapp_parent)
    assert widget.amount.isVisible() or not widget.isVisible()   # built, laid out, and not collapsed to the "+"
    assert not widget.add_button.isVisibleTo(widget)
    assert widget.sizeHint().width() > 0


# An operation that carries a fee shows it; one that doesn't shows the "+" that attaches one, and nothing else
def test_a_stored_fee_is_shown_and_an_absent_one_is_a_plus(accounts_and_assets, qapp_parent):
    with_fee = _widget(qapp_parent, [FeeKind.Commission], oid=_trade_with_fee(3.0))
    assert with_fee.fees() == [{'amount': Decimal('3'), 'account_id': 1, 'symbol_id': 0, 'kind': FeeKind.Commission}]
    assert not with_fee.add_button.isVisibleTo(with_fee)
    assert with_fee.del_button.isVisibleTo(with_fee)

    create_trades(1, [(d2t(220201), d2t(220201), 4, 10.0, 100.0, 0.0)])
    without = _widget(qapp_parent, [FeeKind.Commission], oid=operation_id(LedgerTransaction.Trade, 2))
    assert without.fees() == []
    assert without.add_button.isVisibleTo(without)
    assert not without.amount.isVisibleTo(without)


# "+" attaches a fee on the account the parent pushed in, and the row reaches the table only at the parent's save
def test_attaching_a_fee_writes_it_at_submit(accounts_and_assets, qapp_parent):
    oid = _trade_with_fee(0.0)
    widget = _widget(qapp_parent, [FeeKind.Commission], oid=oid)
    widget.attach()
    widget.amount.setText('2.5')
    widget._mapper.submit()

    assert widget.fees()[0]['account_id'] == 1
    assert JalDB._read("SELECT COUNT(*) FROM fees WHERE operation_id=:oid", [(":oid", oid)]) == 0
    assert widget.submit(oid), widget._model.lastError().text()
    assert JalDB._read("SELECT amount FROM fees WHERE operation_id=:oid", [(":oid", oid)]) == '2.5'


# Detaching puts the widget back to its "+" state and takes the row out at the next save; reverting brings it back
def test_detaching_removes_the_fee_and_reverting_restores_it(accounts_and_assets, qapp_parent):
    oid = _trade_with_fee(3.0)
    widget = _widget(qapp_parent, [FeeKind.Commission], oid=oid)
    widget.detach()

    assert widget.fees() == []
    assert widget.add_button.isVisibleTo(widget)
    assert JalDB._read("SELECT COUNT(*) FROM fees WHERE operation_id=:oid", [(":oid", oid)]) == 1   # not saved yet
    widget.revert()
    assert widget.fees()[0]['amount'] == Decimal('3')

    widget.detach()
    assert widget.submit(oid)
    assert JalDB._read("SELECT COUNT(*) FROM fees WHERE operation_id=:oid", [(":oid", oid)]) == 0


# THE RULE OF THE SINGLE WIDGET: it binds the first row and leaves any other alone. Nothing writes a second fee yet,
# so this is what keeps an operation that acquires one from losing it the first time it is opened and saved.
def test_a_second_fee_survives_an_editor_that_does_not_show_it(accounts_and_assets, qapp_parent):
    oid = _trade_with_fee(3.0)
    JalDB._exec("INSERT INTO fees (operation_id, idx, account_id, symbol_id, amount, kind) "
                "VALUES (:oid, 1, 1, NULL, '0.75', :kind)", [(":oid", oid), (":kind", FeeKind.Commission)], commit=True)

    widget = _widget(qapp_parent, [FeeKind.Commission], oid=oid)
    widget.amount.setText('4')
    widget._mapper.submit()
    assert widget.submit(oid)

    assert JalDB._read_to_list("SELECT idx, amount FROM fees WHERE operation_id=:oid ORDER BY idx",
                               [(":oid", oid)]) == [[0, '4'], [1, '0.75']]


# The operation declares what it may be charged and the widget enforces it alone: one kind and there is nothing to
# choose, several and the choice decides whether the fee is denominated in money or in an asset.
def test_the_allowed_kinds_decide_which_controls_exist(accounts_and_assets, qapp_parent):
    money_only = _widget(qapp_parent, [FeeKind.Commission], oid=_trade_with_fee(3.0))
    assert not money_only.kind.isVisibleTo(money_only)
    assert money_only.currency.isVisibleTo(money_only)
    assert not money_only.symbol.isVisibleTo(money_only)

    create_trades(1, [(d2t(220201), d2t(220201), 4, 10.0, 100.0, 1.0)])
    both = _widget(qapp_parent, [FeeKind.Commission, FeeKind.Gas], oid=operation_id(LedgerTransaction.Trade, 2))
    assert both.kind.isVisibleTo(both)
    both.kind.setCurrentIndex(both.kind.findData(FeeKind.Gas))
    both.kind_selected(both.kind.currentIndex())
    assert both.symbol.isVisibleTo(both)
    assert not both.currency.isVisibleTo(both)
    assert both.fees()[0]['kind'] == FeeKind.Gas


# The account is shown only where it can differ from the operation's own; where it can't, the parent pushes its
# selection in - and only when the USER changes it, so that opening an operation rewrites nothing.
def test_the_fee_account_is_pushed_in_where_it_cannot_differ(accounts_and_assets, qapp_parent):
    oid = _trade_with_fee(3.0)
    widget = _widget(qapp_parent, [FeeKind.Commission], oid=oid)
    assert not widget.account.isVisibleTo(widget)

    widget.set_fee_account(2)
    assert widget.fees()[0]['account_id'] == 2

    differing = _widget(qapp_parent, [FeeKind.Commission], account_may_differ=True, oid=oid)
    assert differing.account.isVisibleTo(differing)


# The three rules the five editors carried, now in one place
def test_validation_states_what_is_wrong(accounts_and_assets, qapp_parent):
    oid = _trade_with_fee(0.0)
    widget = _widget(qapp_parent, [FeeKind.Commission, FeeKind.Gas], oid=oid)
    assert widget.validation_error() == ''      # no fee at all is not an error

    widget.attach()
    assert 'amount' in widget.validation_error()
    widget.amount.setText('1')
    widget._mapper.submit()
    assert widget.validation_error() == ''

    widget.kind.setCurrentIndex(widget.kind.findData(FeeKind.Gas))
    widget.kind_selected(widget.kind.currentIndex())
    assert 'gas' in widget.validation_error()
    widget.symbol.selected_id = symbol_id_for(4, 2)     # 'A' is a stock, not a crypto asset
    widget._mapper.submit()
    assert 'crypto' in widget.validation_error()


# Copying an operation copies the fee with it - under no parent yet, which the copy's own save fills in
def test_a_copied_operation_takes_its_fee_along(accounts_and_assets, qapp_parent):
    widget = _widget(qapp_parent, [FeeKind.Commission], oid=_trade_with_fee(3.0))
    widget.copy_to_new()

    assert widget.fees() == [{'amount': Decimal('3'), 'account_id': 1, 'symbol_id': 0, 'kind': FeeKind.Commission}]
    create_trades(1, [(d2t(220201), d2t(220201), 4, 10.0, 100.0, 0.0)])
    copy_oid = operation_id(LedgerTransaction.Trade, 2)
    assert widget.submit(copy_oid), widget._model.lastError().text()
    assert JalDB._read("SELECT amount FROM fees WHERE operation_id=:oid", [(":oid", copy_oid)]) == '3'
