import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from tests.fixtures import project_root, data_path, prepare_db
from constants import PredefinedAccountType, AccountData, AssetLocation
from jal.db.account import JalAccount, JalAccountCreator
from jal.widgets.account_dialog import AccountDialog

# A real Tron address (the USDT contract), used because its checksum is valid - the addresses below differ from it
# only in ways that a mistyped address would.
TRX_ADDRESS = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
ETH_ADDRESS = "0x111111111117dC0aa78b770fA6A738034120C302"


# AccountDialog reports invalid data with a modal QMessageBox, which would block a test run forever.
# The fixture replaces it and records the warnings instead, so a test may also assert that one was shown.
@pytest.fixture
def warnings(monkeypatch):
    shown = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: shown.append(args) or QMessageBox.Ok)
    yield shown


def _data_row_by_type(dialog, datatype):
    model = dialog._data_model
    for row in range(model.rowCount()):
        if model.data(model.index(row, model.fieldIndex("datatype")), Qt.EditRole) == datatype:
            return row
    return -1


def _set_attribute(dialog, datatype, value):
    model = dialog._data_model
    dialog.onAddData()   # adds a row of the default type (Number) and writes it out
    row = _data_row_by_type(dialog, model._default_values['datatype'])
    model.setData(model.index(row, model.fieldIndex("datatype")), datatype)
    model.setData(model.index(row, model.fieldIndex("value")), value)
    # The grid is OnManualSubmit: without this the row stays 'Number' in the database and addElement() would
    # refuse to add the next attribute, as an empty row of the default type would still be there.
    model.submitAll()


# ----------------------------------------------------------------------------------------------------------------------
def test_wallet_account_creation(prepare_db):
    account = JalAccountCreator(currency_id=2, number='', name='Tron wallet', organization=1,
                                account_type=PredefinedAccountType.Wallet,
                                address=TRX_ADDRESS, chain=AssetLocation.TRX_BLOCKCHAIN).commit()
    assert account.account_type() == PredefinedAccountType.Wallet
    assert account.address() == TRX_ADDRESS
    assert account.chain() == AssetLocation.TRX_BLOCKCHAIN
    # The attributes are stored in 'account_data' like every other per-account value
    assert account.get_data(AccountData.Address) == TRX_ADDRESS
    assert int(account.get_data(AccountData.Chain)) == AssetLocation.TRX_BLOCKCHAIN


def test_wallet_account_mandatory_attributes(prepare_db):
    # A wallet without a chain, or with a location that isn't a blockchain, is refused
    with pytest.raises(ValueError):
        JalAccountCreator(currency_id=2, number='', name='No chain', organization=1,
                          account_type=PredefinedAccountType.Wallet, address=TRX_ADDRESS)
    with pytest.raises(ValueError):
        JalAccountCreator(currency_id=2, number='', name='Not a chain', organization=1,
                          account_type=PredefinedAccountType.Wallet, address=TRX_ADDRESS,
                          chain=AssetLocation.NYSE_EXCHANGE)
    # A wallet without an address is refused as well
    with pytest.raises(ValueError):
        JalAccountCreator(currency_id=2, number='', name='No address', organization=1,
                          account_type=PredefinedAccountType.Wallet, chain=AssetLocation.TRX_BLOCKCHAIN)
    # Nothing of the above was left behind - the checks run before the account row is written
    assert JalAccount.get_all_accounts(active_only=False) == []

    # Other account types are not affected by the wallet requirements
    JalAccountCreator(currency_id=2, number='ACC-1', name='Bank', organization=1,
                      account_type=PredefinedAccountType.Bank).commit()


def test_wallet_is_not_cloned_by_number(prepare_db):
    # An account number that already exists normally clones that account into the new currency instead of
    # creating one - and the clone path stores no attributes. A wallet must never take it, or it would end up
    # with no address at all despite the mandatory set.
    JalAccountCreator(currency_id=2, number='SHARED', name='Bank', organization=1,
                      account_type=PredefinedAccountType.Bank).commit()
    wallet = JalAccountCreator(currency_id=2, number='SHARED', name='Tron wallet', organization=1,
                               account_type=PredefinedAccountType.Wallet,
                               address=TRX_ADDRESS, chain=AssetLocation.TRX_BLOCKCHAIN).commit()
    assert wallet.id() != 1                       # a new account, not a clone of the bank one
    assert wallet.account_type() == PredefinedAccountType.Wallet
    assert wallet.address() == TRX_ADDRESS
    assert wallet.chain() == AssetLocation.TRX_BLOCKCHAIN


def test_wallet_address_validation(prepare_db):
    # A single altered character breaks the Tron checksum and must be refused
    with pytest.raises(ValueError):
        JalAccountCreator(currency_id=2, number='', name='Typo', organization=1,
                          account_type=PredefinedAccountType.Wallet,
                          address=TRX_ADDRESS[:-1] + 'u', chain=AssetLocation.TRX_BLOCKCHAIN)

    # An address of a chain JAL can't check yet is accepted as it is given, but is still normalized: EVM
    # addresses are case-insensitive, so they are stored lowercase or a later lookup would miss them.
    account = JalAccountCreator(currency_id=2, number='', name='ETH wallet', organization=1,
                                account_type=PredefinedAccountType.Wallet,
                                address='  ' + ETH_ADDRESS + '  ', chain=AssetLocation.ETH_BLOCKCHAIN).commit()
    assert account.address() == ETH_ADDRESS.lower()


def test_sync_cursor_is_internal(prepare_db):
    account = JalAccountCreator(currency_id=2, number='', name='Tron wallet', organization=1,
                                account_type=PredefinedAccountType.Wallet,
                                address=TRX_ADDRESS, chain=AssetLocation.TRX_BLOCKCHAIN).commit()
    # The fetcher writes and reads the cursor through the ordinary attribute interface
    account.set_data(AccountData.SyncCursor, '1784451896000')
    assert account.get_data(AccountData.SyncCursor) == '1784451896000'

    # ... but it is never offered to the user for editing, unlike every other attribute
    assert AccountData.is_internal(AccountData.SyncCursor)
    assert not AccountData.is_internal(AccountData.Address)
    from PySide6.QtWidgets import QComboBox
    combo = QComboBox()
    AccountData().load2combo(combo)
    offered = [combo.itemData(i) for i in range(combo.count())]
    assert AccountData.SyncCursor not in offered
    assert AccountData.Address in offered and AccountData.Chain in offered


# ----------------------------------------------------------------------------------------------------------------------
def test_dialog_creates_wallet(prepare_db, warnings):
    dialog = AccountDialog()
    dialog.createNewRecord()
    dialog.ui.NameEdit.setText("Tron wallet")
    dialog.ui.TypeCombo.set_key(PredefinedAccountType.Wallet)
    _set_attribute(dialog, AccountData.Chain, str(AssetLocation.TRX_BLOCKCHAIN))
    _set_attribute(dialog, AccountData.Address, '  ' + TRX_ADDRESS + '  ')
    dialog.accept()

    JalAccount.db_cache.clear_cache()
    account = JalAccount(1)
    assert account.account_type() == PredefinedAccountType.Wallet
    assert account.address() == TRX_ADDRESS        # surrounding whitespace was stripped on save
    assert account.chain() == AssetLocation.TRX_BLOCKCHAIN


def test_dialog_refuses_incomplete_wallet(prepare_db, warnings):
    # accept() is used rather than validated() directly, because it is accept() that pushes the edited widgets
    # into the model first - and it is the path a user actually takes.
    dialog = AccountDialog()
    dialog.createNewRecord()
    dialog.ui.NameEdit.setText("Wallet without address")
    dialog.ui.TypeCombo.set_key(PredefinedAccountType.Wallet)
    _set_attribute(dialog, AccountData.Chain, str(AssetLocation.TRX_BLOCKCHAIN))
    dialog.accept()                    # the address is missing
    assert len(warnings) == 1
    assert dialog.result() != AccountDialog.Accepted

    _set_attribute(dialog, AccountData.Address, TRX_ADDRESS[:-1] + 'u')
    dialog.accept()                    # ... and now it is present but its checksum is wrong
    assert len(warnings) == 2
    assert dialog.result() != AccountDialog.Accepted

    row = _data_row_by_type(dialog, AccountData.Address)
    dialog._data_model.setData(dialog._data_model.index(row, dialog._data_model.fieldIndex("value")), TRX_ADDRESS)
    dialog.accept()
    assert len(warnings) == 2          # no further complaint once the address is correct

    JalAccount.db_cache.clear_cache()
    assert JalAccount(1).address() == TRX_ADDRESS
