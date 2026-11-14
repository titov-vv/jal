import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QWidget

from tests.fixtures import project_root, data_path, prepare_db
from jal.constants import PredefinedAccountType, AccountData
from jal.db.db import JalDB
from jal.db.settings import JalSettings
from jal.db.account import JalAccountCreator
from jal.widgets.account_dialog import AccountDialog
from jal.widgets.symbol_dialog import SymbolDialog


def _account_number():
    return JalDB._read("SELECT value FROM account_data WHERE account_id=1 AND datatype=:datatype",
                       [(":datatype", AccountData.Number)])


def _asset_name():
    return JalDB._read("SELECT full_name FROM assets WHERE id=2")


def _edit_account(owner):
    JalAccountCreator(currency_id=2, number='ACC-1', name='Bank', organization=1,
                      account_type=PredefinedAccountType.Bank).commit()
    dialog = AccountDialog(owner)
    dialog.setSelectedId(1)
    model = dialog._data_model
    row = [x for x in range(model.rowCount())
           if model.record(x).value(model.fieldIndex("datatype")) == AccountData.Number][0]
    model.setData(model.index(row, model.fieldIndex("value")), "TAMPERED")
    assert model.submitAll()
    return dialog


def _edit_asset(owner):
    dialog = SymbolDialog(owner)
    dialog.setSelectedId(2)
    model = dialog._model
    model.setData(model.index(0, model.fieldIndex("full_name")), "TAMPERED")
    assert model.submitAll()
    return dialog


# A picker closed inside the dialog saves its geometry: that write must not commit the edits the dialog holds
def test_cancel_undoes_account_edits_after_a_settings_write(prepare_db):
    owner = QWidget()
    dialog = _edit_account(owner)
    JalSettings().setValue('DlgGeometry_probe', 'x')
    dialog.reject()
    assert _account_number() == 'ACC-1'
    assert JalSettings().getStr('DlgGeometry_probe', 'none') == 'none'   # rolled back with the rest


def test_account_edits_are_committed_by_ok(prepare_db):
    owner = QWidget()
    dialog = _edit_account(owner)
    JalSettings().setValue('DlgGeometry_probe', 'x')
    dialog.accept()
    assert not JalDB._in_transaction
    assert _account_number() == 'TAMPERED'
    assert JalSettings().getStr('DlgGeometry_probe', 'none') == 'x'


def test_cancel_undoes_asset_edits_after_a_settings_write(prepare_db):
    owner = QWidget()
    name = _asset_name()
    dialog = _edit_asset(owner)
    JalSettings().setValue('DlgGeometry_probe', 'x')
    dialog.reject()
    assert not JalDB._in_transaction
    assert _asset_name() == name
