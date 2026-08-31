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
    # No number, so the account starts with no attribute rows at all - adding one here would otherwise collide
    # with the existing 'Number' row and AccountDataModel would refuse it with a modal warning.
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
                   dialog.ui.OrganizationLbl, dialog.ui.OrganizationCombo, dialog.ui.ActiveCheck,
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
