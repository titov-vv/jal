import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from decimal import Decimal

import pytest
from PySide6.QtCore import QDateTime
from PySide6.QtWidgets import QWidget, QMenu, QDialogButtonBox

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_fifo
from tests.helpers import d2t, create_stocks, create_trades, create_actions
from jal.constants import BookAccount, PredefinedCategory, AccountStatus
from jal.db.db import JalDB
from jal.db.ledger import Ledger, LedgerAmounts
from jal.db.account import JalAccount
from jal.db.operations import LedgerTransaction, CorporateAction
from jal.db.receivable import JalReceivable
from jal.db.helpers import localize_amount
from jal.widgets.account_close_dialog import AccountCloseDialog
from jal.widgets.reference_dialogs import AccountListDialog


def _operations_count() -> int:
    return JalDB._read("SELECT COUNT(*) FROM actions") + JalDB._read("SELECT COUNT(*) FROM asset_actions")


# Cash and two assets of several lots: everything goes to Losses, every book ends at zero, no deal is reported
def test_close_writes_everything_off(prepare_db_fifo):
    create_stocks([('A', 'A SHARE'), ('B', 'B SHARE')], currency_id=2)  # id = 4, 5
    create_trades(1, [(d2t(210501), d2t(210501), 4, 100.0, 10.0, 1.0), (d2t(210601), d2t(210601), 4, 50.0, 12.0, 0.0),
                      (d2t(210701), d2t(210701), 5, 3.0, 100.0, 0.0)])
    Ledger().rebuild(from_timestamp=0)
    account = JalAccount(1)

    refusals, records = account.closure_plan(d2t(211001), 'Closed by the broker')
    assert refusals == []
    assert [(x[0], x[1].get('type'), x[1].get('qty')) for x in records] == [
        (LedgerTransaction.IncomeSpending, None, None),
        (LedgerTransaction.CorporateAction, CorporateAction.WriteOff, Decimal('150')),
        (LedgerTransaction.CorporateAction, CorporateAction.WriteOff, Decimal('3'))]
    assert records[0][1]['lines'][0]['amount'] == Decimal('-8099')

    assert account.close(d2t(211001), 'Closed by the broker') == []
    Ledger().rebuild(from_timestamp=d2t(211001))
    assert JalAccount(1).status() == AccountStatus.Closed
    amounts = LedgerAmounts("amount_acc")
    assert amounts[(BookAccount.Money, 1, 2)] == Decimal('0')
    assert amounts[(BookAccount.Assets, 1, 4)] == Decimal('0')
    assert amounts[(BookAccount.Assets, 1, 5)] == Decimal('0')
    assert account.get_category_turnover(PredefinedCategory.Losses, 0, d2t(211231)) == Decimal('9999')
    assert account.closed_trades_list() == []


# An account with nothing left is only set Closed
def test_close_of_an_empty_account(prepare_db_fifo):
    create_actions([(d2t(210501), 1, 1, [(PredefinedCategory.Fees, -10000.0)])])
    Ledger().rebuild(from_timestamp=0)
    assert JalAccount(1).closure_plan(d2t(211001)) == ([], [])
    assert JalAccount(1).close(d2t(211001)) == []
    assert JalAccount(1).status() == AccountStatus.Closed


def _short_position():
    create_stocks([('A', 'A SHARE')], currency_id=2)  # id = 4
    create_trades(1, [(d2t(210501), d2t(210501), 4, -10.0, 10.0, 0.0)])


def _debt():
    create_actions([(d2t(210501), 1, 1, [(PredefinedCategory.Fees, -10500.0)])])


def _later_operation():
    create_actions([(d2t(211001), 1, 1, [(PredefinedCategory.Fees, -1.0)])])


def _owed():
    JalReceivable().store(d2t(210501), 1, 2, 'merkl', Decimal('5'))


def _closed():
    JalAccount(1).set_status(AccountStatus.Closed)


@pytest.mark.parametrize("setup, refusal", [
    (_short_position, "The account has a short position: " + localize_amount(Decimal('-10')) + " A"),
    (_debt, "The account has a debt: " + localize_amount(Decimal('500')) + " USD"),
    (_later_operation, "The account has operations at or after the closure date"),
    (_owed, "The account is still owed: " + localize_amount(Decimal('5')) + " USD (merkl)"),
    (_closed, "The account is closed already")])
def test_close_is_refused(prepare_db_fifo, setup, refusal):
    setup()
    Ledger().rebuild(from_timestamp=0)
    count = _operations_count()
    assert JalAccount(1).close(d2t(211001)) == [refusal]
    assert _operations_count() == count


# A plan read from a ledger that hasn't seen the latest operation is refused
def test_close_needs_a_current_ledger(prepare_db_fifo):
    Ledger().rebuild(from_timestamp=0)
    create_actions([(d2t(210501), 1, 1, [(PredefinedCategory.Fees, -1.0)])])
    assert JalAccount(1).closure_plan(d2t(211001))[0] == ["The ledger isn't up to date, rebuild it first"]


# ----------------------------------------------------------------------------------------------------------------------
# The dialog shows the plan, refuses a date before the last operation, and closes the account on Ok
def test_close_dialog(prepare_db_fifo):
    create_stocks([('A', 'A SHARE')], currency_id=2)  # id = 4
    create_trades(1, [(d2t(210501), d2t(210501), 4, 10.0, 100.0, 0.0)])
    parent = QWidget()
    dialog = AccountCloseDialog(1, parent=parent)
    ok = dialog._buttons.button(QDialogButtonBox.Ok)

    dialog._closed.setDateTime(QDateTime.fromSecsSinceEpoch(d2t(210401)))
    assert dialog._plan.toPlainText().startswith("The account can't be closed:") and not ok.isEnabled()
    dialog._closed.setDateTime(QDateTime.fromSecsSinceEpoch(d2t(211001)))
    assert dialog._plan.toPlainText() == "Cash to Losses: " + localize_amount(Decimal('9000')) + " USD\n" + \
                                         "Asset to Losses: " + localize_amount(Decimal('10')) + " A"
    assert ok.isEnabled()
    dialog._note.setText('Gone')
    dialog.accept()
    assert JalAccount(1).status() == AccountStatus.Closed
    assert JalDB._read("SELECT note FROM asset_actions") == 'Gone'
    assert LedgerAmounts("amount_acc")[(BookAccount.Money, 1, 2)] == Decimal('0')


# The menu item is there where accounts are managed, disabled for a closed one, and absent where one is picked
def test_close_menu_item(prepare_db_fifo):
    parent = QWidget()
    dialog = AccountListDialog(parent)
    dialog.model.select()
    index = dialog.model.index(0, 0)

    def items():
        menu = QMenu(dialog)
        dialog.customizeContextMenu(menu, index)
        return [(x.text(), x.isEnabled()) for x in menu.actions()]

    assert items() == [("Close account…", True)]
    JalAccount(1).set_status(AccountStatus.Closed)
    assert items() == [("Close account…", False)]
    dialog.selection_enabled = True
    assert items() == []
