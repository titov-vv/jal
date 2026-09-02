import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt

from tests.fixtures import project_root, data_path, prepare_db
from constants import PredefinedAccountType, AccountData
from jal.db.db import JalDB
from jal.db.account import JalAccount, JalAccountCreator
from jal.widgets.account_dialog import AccountDialog
from jal.db.common_models import TagTreeModel
from jal.widgets.reference_dialogs import TagsListDialog


def _accounts_count():
    return JalDB()._read("SELECT COUNT(*) FROM accounts")


def _data_row_by_type(dialog, datatype):
    model = dialog._data_model
    for row in range(model.rowCount()):
        stored = model.data(model.index(row, model.fieldIndex("datatype")), Qt.EditRole)
        if stored == datatype:
            return row
    return -1


# Creating a new account and cancelling must leave the database untouched (the row inserted to obtain an id for the
# attribute rows has to be rolled back together with everything else).
def test_new_account_cancel_rolls_back(prepare_db):
    dialog = AccountDialog()
    dialog.createNewRecord()
    dialog.ui.NameEdit.setText("Scratch account")
    dialog.onAddData()  # adds a default (Number) attribute row inside the transaction
    dialog.reject()

    JalAccount.db_cache.clear_cache()
    assert _accounts_count() == 0  # neither the account nor its attribute row was persisted


# Confirming a new account persists both the account and its attributes atomically.
def test_new_account_ok_persists(prepare_db):
    dialog = AccountDialog()
    dialog.createNewRecord()
    dialog.ui.NameEdit.setText("Brokerage")
    dialog.ui.TypeCombo.set_key(PredefinedAccountType.Broker)
    dialog.onAddData()  # Number attribute
    row = _data_row_by_type(dialog, AccountData.Number)
    dialog._data_model.setData(dialog._data_model.index(row, dialog._data_model.fieldIndex("value")), "ACC-777")
    dialog.accept()

    JalAccount.db_cache.clear_cache()
    account = JalAccount(1)
    assert account.id() == 1
    assert account.account_type() == PredefinedAccountType.Broker
    assert account.number() == "ACC-777"


# The reported bug: editing an existing account's attribute and then cancelling must NOT persist the change.
def test_edit_attribute_cancel_rolls_back(prepare_db):
    JalAccountCreator(currency_id=2, number='ACC-1', name='Bank', organization=1,
                      account_type=PredefinedAccountType.Bank).commit()

    dialog = AccountDialog()
    dialog.setSelectedId(1)
    row = _data_row_by_type(dialog, AccountData.Number)
    assert row >= 0
    dialog._data_model.setData(dialog._data_model.index(row, dialog._data_model.fieldIndex("value")), "TAMPERED")
    dialog.reject()

    JalAccount.db_cache.clear_cache()
    assert JalAccount(1).number() == "ACC-1"  # original value preserved


# Editing an existing account's attribute and confirming persists the change.
def test_edit_attribute_ok_persists(prepare_db):
    JalAccountCreator(currency_id=2, number='ACC-1', name='Bank', organization=1,
                      account_type=PredefinedAccountType.Bank).commit()

    dialog = AccountDialog()
    dialog.setSelectedId(1)
    row = _data_row_by_type(dialog, AccountData.Number)
    dialog._data_model.setData(dialog._data_model.index(row, dialog._data_model.fieldIndex("value")), "ACC-2")
    dialog.accept()

    JalAccount.db_cache.clear_cache()
    assert JalAccount(1).number() == "ACC-2"


# The tag of an account is an attribute like any other, edited in the same grid - which means the delegate has to
# offer a tag selector for it. The selector's dialog class is handed to AccountDialog rather than imported by it,
# because reference_dialogs imports this module and naming TagsListDialog there would close that circle.
def test_account_tag_is_edited_in_the_attribute_grid(prepare_db):
    from PySide6.QtWidgets import QWidget
    from jal.widgets.reference_selector import ReferenceSelectorWidget

    cash = JalDB._read("SELECT id FROM tags WHERE tag='Cash'")
    # No number, so the account starts with no attribute rows at all and the row added below takes the first
    # attribute type ('Number'), which this test then turns into a tag.
    JalAccountCreator(currency_id=2, number='', name='Bank', organization=1,
                      account_type=PredefinedAccountType.Bank).commit()

    dialog = AccountDialog(None, TagTreeModel, TagsListDialog)
    dialog.setSelectedId(1)
    dialog.onAddData()
    model = dialog._data_model
    row = _data_row_by_type(dialog, AccountData.Number)     # the row is added with the default attribute type
    model.setData(model.index(row, model.fieldIndex("datatype")), AccountData.Tag)
    row = _data_row_by_type(dialog, AccountData.Tag)
    assert row >= 0

    # The value cell of a tag row offers a tag selector, not the plain line editor the other types share
    parent = QWidget()
    value_index = model.index(row, model.fieldIndex("value"))
    editor = dialog._attribute_delegate.createEditor(parent, None, value_index)
    assert isinstance(editor, ReferenceSelectorWidget)
    editor.selected_id = cash
    dialog._attribute_delegate.setModelData(editor, model, value_index)
    dialog.accept()

    JalAccount.db_cache.clear_cache()
    assert JalAccount(1).tag().id() == cash
    # ... and the grid shows the tag by name rather than by the id it stores
    assert model.data(value_index, Qt.DisplayRole) == 'Cash'
    parent.deleteLater()


# An account that already has an attribute must still accept another one. Adding was refused with a modal warning
# whenever the account had an attribute of the type a new row is created with - which is the account number, i.e.
# almost every account. A new row takes the first attribute type the account doesn't have yet instead.
def test_attribute_is_added_to_an_account_that_has_one_already(prepare_db):
    JalAccountCreator(currency_id=2, number='ACC-1', name='Bank', organization=1,
                      account_type=PredefinedAccountType.Bank).commit()

    dialog = AccountDialog()
    dialog.setSelectedId(1)
    model = dialog._data_model
    assert model.rowCount() == 1 and _data_row_by_type(dialog, AccountData.Number) >= 0

    dialog.onAddData()
    assert model.rowCount() == 2
    assert _data_row_by_type(dialog, AccountData.Number) >= 0   # the attribute that was there is untouched...
    assert _data_row_by_type(dialog, AccountData.Credit) >= 0   # ... and the new row got the next free type
    dialog.reject()


# An attribute type may be present only once per account ('account_data' is unique by (account_id, datatype)), so
# re-assigning a row to a type another row already has is refused as it is picked - it used to be left to the
# database, which reported it as a failed submit when the dialog was already being closed by OK.
def test_duplicate_attribute_type_is_refused(prepare_db, monkeypatch):
    from PySide6.QtWidgets import QWidget, QMessageBox
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: warnings.append(args[2]))

    JalAccountCreator(currency_id=2, number='ACC-1', name='Bank', organization=1,
                      account_type=PredefinedAccountType.Bank).commit()
    dialog = AccountDialog()
    dialog.setSelectedId(1)
    model = dialog._data_model
    dialog.onAddData()                                    # a second row, of the next free type
    row = _data_row_by_type(dialog, AccountData.Credit)
    value_index = model.index(row, model.fieldIndex("value"))
    model.setData(value_index, '1000')

    # The user picks 'Account #' for the row that is a credit limit, while another row already keeps it
    parent = QWidget()
    type_index = model.index(row, model.fieldIndex("datatype"))
    editor = dialog._attribute_delegate.createEditor(parent, None, type_index)
    editor.setCurrentIndex(editor.findData(AccountData.Number))
    dialog._attribute_delegate.setModelData(editor, model, type_index)

    assert len(warnings) == 1
    assert _data_row_by_type(dialog, AccountData.Credit) == row     # the row keeps the type it had...
    assert model.data(value_index, Qt.EditRole) == '1000'           # ... and the value that goes with it
    parent.deleteLater()

    dialog.accept()   # the grid submits without a UNIQUE violation
    JalAccount.db_cache.clear_cache()
    assert JalAccount(1).number() == 'ACC-1'
    assert JalDB._read("SELECT COUNT(*) FROM account_data WHERE account_id=1") == 2


# The currency shown by the dialog must survive a mapper submit - reading the combo's key used to re-select the
# model the combo itself is showing, which reset it to the first currency of the table and stored that instead.
def test_account_currency_survives_editing(prepare_db):
    JalAccountCreator(currency_id=2, number='ACC-1', name='Bank', organization=1,
                      account_type=PredefinedAccountType.Bank).commit()
    dialog = AccountDialog()
    dialog.setSelectedId(1)
    assert dialog.ui.CurrencyCombo.currentText() == 'USD'

    dialog.ui.NameEdit.setText("Bank renamed")
    dialog._mapper.submit()   # AutoSubmit does this on every focus change while the dialog is open
    assert dialog.ui.CurrencyCombo.currentText() == 'USD'
    dialog.accept()

    JalAccount.db_cache.clear_cache()
    account = JalAccount(1)
    assert account.name() == "Bank renamed" and account.currency() == 2


# ----------------------------------------------------------------------------------------------------------------------
# An account of a HIDDEN type - a staked position, a term deposit - is shown by this dialog cut down to the two
# things it may show of itself: its name and its icon. Everything else is hidden rather than disabled, because it
# either says "account" where the user is shown none, or carries a value that must not change (see edit_name_only).
def test_name_only_mode_shows_the_name_and_the_icon_alone(prepare_db):
    box = JalAccountCreator(currency_id=2, number='', name='stake.link', investing=1, organization=1,
                            account_type=PredefinedAccountType.Staking).commit()
    dialog = AccountDialog()
    dialog.setSelectedId(box.id())
    dialog.edit_name_only("Staked position")

    assert dialog.windowTitle() == "Staked position"
    assert dialog.ui.NameEdit.isVisibleTo(dialog) and dialog.ui.IconButton.isVisibleTo(dialog)
    for widget in (dialog.ui.CurrencyLbl, dialog.ui.CurrencyCombo, dialog.ui.TypeLbl, dialog.ui.TypeCombo,
                   dialog.ui.OrganizationLbl, dialog.ui.OrganizationWidget, dialog.ui.StatusLbl, dialog.ui.StatusCombo,
                   dialog.ui.InvestingCheck, dialog.ui.ReconciledValue, dialog.ui.DetailsFrame):
        assert not widget.isVisibleTo(dialog), f"{widget.objectName()} is shown in the name-only mode"

    dialog.ui.NameEdit.setText("stake.link PriorityPool")
    dialog.accept()

    JalAccount.db_cache.clear_cache()
    account = JalAccount(box.id())
    assert account.name() == "stake.link PriorityPool"
    # ... and nothing the mode hid was touched by the round trip
    assert account.account_type() == PredefinedAccountType.Staking and account.currency() == 2


# Cancelling the same dialog leaves the name as it was - the transaction it opened is rolled back like any other
def test_name_only_mode_cancel_keeps_the_name(prepare_db):
    box = JalAccountCreator(currency_id=2, number='', name='stake.link', investing=1, organization=1,
                            account_type=PredefinedAccountType.Staking).commit()
    dialog = AccountDialog()
    dialog.setSelectedId(box.id())
    dialog.edit_name_only("Staked position")
    dialog.ui.NameEdit.setText("Renamed by mistake")
    dialog.reject()

    JalAccount.db_cache.clear_cache()
    assert JalAccount(box.id()).name() == 'stake.link'


# ----------------------------------------------------------------------------------------------------------------------
# The bank/broker of an account is picked with the same reference selector as a peer anywhere else in the application:
# it must show the name of the stored peer and write back the id of the chosen one.
def test_bank_broker_is_picked_with_a_peer_selector(prepare_db):
    from jal.db.peer import JalPeer

    bank = JalPeer(data={'name': 'Bank of Test', 'parent': 0}, create=True).id()
    JalAccountCreator(currency_id=2, number='ACC-1', name='Bank', organization=bank,
                      account_type=PredefinedAccountType.Bank).commit()

    dialog = AccountDialog()
    dialog.setSelectedId(1)
    selector = dialog.ui.OrganizationWidget
    assert selector.selected_id == bank and selector.name.text() == 'Bank of Test'

    another = JalPeer(data={'name': 'Broker of Test', 'parent': 0}, create=True).id()
    selector.selection_done(another)
    dialog.accept()

    JalAccount.db_cache.clear_cache()
    assert JalAccount(1).organization() == another


# Clearing the selector stores the predefined 'None' peer: 'accounts.organization_id' is NOT NULL DEFAULT (1)
def test_cleared_bank_broker_falls_back_to_the_none_peer(prepare_db):
    from jal.constants import PredefinedAgents
    from jal.db.peer import JalPeer

    bank = JalPeer(data={'name': 'Bank of Test', 'parent': 0}, create=True).id()
    JalAccountCreator(currency_id=2, number='ACC-1', name='Bank', organization=bank,
                      account_type=PredefinedAccountType.Bank).commit()

    dialog = AccountDialog()
    dialog.setSelectedId(1)
    dialog.ui.OrganizationWidget.on_clean_button_clicked()
    assert dialog.ui.OrganizationWidget.selected_id == PredefinedAgents.Empty
    dialog.accept()

    JalAccount.db_cache.clear_cache()
    assert JalAccount(1).organization() == PredefinedAgents.Empty


# A date attribute ('Opened on', 'Closed on', deposit maturity) had no editor of its own in the grid: it fell through
# to the plain line editor, which neither loaded the stored date nor wrote back what was typed into it - the text
# simply vanished when the cell was left. It gets a calendar editor, and the day it states is stored on no clock.
def test_date_attribute_is_edited_with_a_date_editor(prepare_db):
    from PySide6.QtCore import QDate, QDateTime, QTime, QTimeZone
    from PySide6.QtWidgets import QWidget
    from jal.widgets.delegates import DateTimeEditWithReset

    JalAccountCreator(currency_id=2, number='ACC-1', name='Bank', organization=1,
                      account_type=PredefinedAccountType.Bank).commit()
    dialog = AccountDialog()
    dialog.setSelectedId(1)
    model = dialog._data_model
    dialog.onAddData()
    row = _data_row_by_type(dialog, AccountData.Credit)     # the new row takes the next free type
    model.setData(model.index(row, model.fieldIndex("datatype")), AccountData.OpenDate)
    row = _data_row_by_type(dialog, AccountData.OpenDate)
    value_index = model.index(row, model.fieldIndex("value"))

    parent = QWidget()
    editor = dialog._attribute_delegate.createEditor(parent, None, value_index)
    assert isinstance(editor, DateTimeEditWithReset)
    dialog._attribute_delegate.setEditorData(editor, value_index)   # an empty value must not throw
    opened = QDateTime(QDate(2015, 3, 17), QTime(0, 0), QTimeZone(QTimeZone.UTC))
    editor.setDateTime(opened)
    dialog._attribute_delegate.setModelData(editor, model, value_index)
    assert model.data(value_index, Qt.EditRole) == str(opened.toSecsSinceEpoch())

    # The stored date is loaded back into the editor of a re-opened cell
    reopened = dialog._attribute_delegate.createEditor(parent, None, value_index)
    dialog._attribute_delegate.setEditorData(reopened, value_index)
    assert reopened.dateTime().toSecsSinceEpoch() == opened.toSecsSinceEpoch()
    parent.deleteLater()

    dialog.accept()
    JalAccount.db_cache.clear_cache()
    assert JalAccount(1).opened_on() == opened.toSecsSinceEpoch()
