import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt

from tests.fixtures import project_root, data_path, prepare_db
from constants import PredefinedAccountType, AccountData
from jal.db.db import JalDB
from jal.db.account import JalAccount, JalAccountCreator
from jal.widgets.account_dialog import AccountDialog


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
