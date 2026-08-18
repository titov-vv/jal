import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from decimal import Decimal

import pytest
from PySide6.QtWidgets import QMessageBox

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import create_stocks, create_trades
from constants import PredefinedAccountType
from jal.db.account import JalAccountCreator
from jal.db.db import JalDB
from jal.db.ledger import Ledger
from jal.db.operations import LedgerTransaction
from jal.widgets.operations_widget import OperationsWidget

from datetime import datetime, timezone

USD = 2
DAY = 24 * 60 * 60


def _ts(days_ago):
    return int(datetime.now(tz=timezone.utc).timestamp()) - days_ago * DAY


@pytest.fixture
def three_trades(prepare_db):
    JalAccountCreator(currency_id=USD, number='', name='Broker', investing=1, organization=1,
                      account_type=PredefinedAccountType.Broker).commit()
    create_stocks([('AAPL', 'Apple Inc.')], USD)
    create_trades(1, [(_ts(4), _ts(4), 4, Decimal('10'), Decimal('100'), Decimal('1')),
                      (_ts(3), _ts(3), 4, Decimal('-4'), Decimal('130'), Decimal('1')),
                      (_ts(2), _ts(2), 4, Decimal('-3'), Decimal('80'), Decimal('1'))])
    JalDB()._exec("UPDATE base_currency SET currency_id=:usd", [(":usd", USD)])
    Ledger().rebuild(from_timestamp=0)
    yield


def _dirty_widget(operations):
    """Select the first operation and leave its editor with an unsaved edit."""
    operations.ui.OperationsTableView.selectRow(0)
    widget = operations.ui.OperationsTabs.widgets[LedgerTransaction.Trade]
    widget.modified = True
    return widget


def _answer(monkeypatch, reply):
    asked = {}

    def fake_warning(self, parent, title, text, buttons=None, default=None):
        asked['title'] = title
        asked['buttons'] = int(buttons) if buttons is not None else 0
        asked['default'] = default
        return reply

    monkeypatch.setattr(QMessageBox, "warning", fake_warning)
    return asked


def _selected_rows(operations):
    return [i.row() for i in operations.ui.OperationsTableView.selectionModel().selectedRows()]


# The prompt offers a real third way out, and lands on Save rather than on the destructive answer.
def test_prompt_offers_save_discard_cancel(three_trades, monkeypatch):
    operations = OperationsWidget(None)
    asked = _answer(monkeypatch, QMessageBox.Discard)
    _dirty_widget(operations)
    operations.ui.OperationsTableView.selectRow(1)
    assert asked['buttons'] == int(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
    assert asked['default'] == QMessageBox.Save


# Cancel keeps the edits AND puts the table back on the operation that owns them - otherwise the highlighted row
# and the editor below it would be showing two different operations.
def test_cancel_keeps_the_edits_and_the_selection(three_trades, monkeypatch):
    operations = OperationsWidget(None)
    _answer(monkeypatch, QMessageBox.Cancel)
    widget = _dirty_widget(operations)
    assert _selected_rows(operations) == [0]

    operations.ui.OperationsTableView.selectRow(1)
    assert widget.modified, "Cancel must not throw the edits away"
    assert _selected_rows(operations) == [0], "the table must go back to the operation still being edited"


# Discard is the answer that loses the edits, and it says so on the button.
def test_discard_drops_the_edits_and_moves_on(three_trades, monkeypatch):
    operations = OperationsWidget(None)
    _answer(monkeypatch, QMessageBox.Discard)
    widget = _dirty_widget(operations)

    operations.ui.OperationsTableView.selectRow(1)
    assert not widget.modified
    assert _selected_rows(operations) == [1]


# A save the widget refuses (its own validation complains) must be treated like Cancel: the move is off, because
# going ahead would leave the pending edits behind with nothing showing them.
def test_refused_save_is_not_a_move(three_trades, monkeypatch):
    operations = OperationsWidget(None)
    _answer(monkeypatch, QMessageBox.Save)
    widget = _dirty_widget(operations)
    monkeypatch.setattr(widget, "saveChanges", lambda: None)   # validation refuses: 'modified' stays True

    operations.ui.OperationsTableView.selectRow(1)
    assert widget.modified
    assert _selected_rows(operations) == [0]


# Nothing pending, nothing asked - the prompt must not appear on an ordinary click.
def test_clean_widget_is_not_interrupted(three_trades, monkeypatch):
    operations = OperationsWidget(None)
    asked = _answer(monkeypatch, QMessageBox.Cancel)
    operations.ui.OperationsTableView.selectRow(0)
    operations.ui.OperationsTableView.selectRow(1)
    assert asked == {}
    assert _selected_rows(operations) == [1]


# ----------------------------------------------------------------------------------------------------------------------
# The reference dialogs asked "You have uncommitted changes. Do you want to close?" - where the answer that reads as
# "no, leave it alone" was the one that threw the edits away. Same three answers here, and Save now actually saves.
def _reference_dialog(monkeypatch, reply):
    from jal.widgets.reference_dialogs import PeerListDialog
    asked = {}

    def fake_warning(self, parent, title, text, buttons=None, default=None):
        asked['buttons'] = int(buttons) if buttons is not None else 0
        asked['default'] = default
        return reply

    monkeypatch.setattr(QMessageBox, "warning", fake_warning)
    dialog = PeerListDialog()
    done = {}
    monkeypatch.setattr(dialog.model, "revertAll", lambda: done.setdefault('reverted', True))
    monkeypatch.setattr(dialog.model, "submitAll", lambda: done.setdefault('saved', True) or True)
    dialog.ui.CommitBtn.setEnabled(True)   # stand in for pending edits in the grid
    return dialog, asked, done


def _close_via_button(dialog, done):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QDialogButtonBox

    def act():
        dialog.ui.DialogButtonBox.button(QDialogButtonBox.Close).click()
        if dialog.isVisible():
            done['stayed_open'] = True
            dialog.done(0)

    QTimer.singleShot(0, act)
    dialog.exec()


def test_reference_dialog_offers_save_discard_cancel(prepare_db, monkeypatch):
    dialog, asked, done = _reference_dialog(monkeypatch, QMessageBox.Save)
    _close_via_button(dialog, done)
    assert asked['buttons'] == int(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
    assert asked['default'] == QMessageBox.Save
    assert done.get('saved') and not done.get('reverted')


def test_reference_dialog_discard_reverts(prepare_db, monkeypatch):
    dialog, _, done = _reference_dialog(monkeypatch, QMessageBox.Discard)
    _close_via_button(dialog, done)
    assert done.get('reverted') and not done.get('saved')


def test_reference_dialog_cancel_stays_open(prepare_db, monkeypatch):
    dialog, _, done = _reference_dialog(monkeypatch, QMessageBox.Cancel)
    _close_via_button(dialog, done)
    assert done.get('stayed_open')
    assert not done.get('saved') and not done.get('reverted')
