import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from decimal import Decimal

import pytest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialogButtonBox

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, create_assets, create_actions, create_quotes, create_trades, symbol_id_for
from constants import PredefinedAsset, PredefinedCategory, PredefinedAccountType, AssetLocation
from jal.db.account import JalAccountCreator
from jal.db.ledger import Ledger
from jal.db.operations import LedgerTransaction
from jal.widgets.transfer_assign_dialog import TransferAssignDialog

# ----------------------------------------------------------------------------------------------------------------------
# The dialog that names the account at the end a leg doesn't know.
#
# The assignment itself is the user's assertion, so what the dialog owes them is the consequences of it BEFORE it is
# made: whether the account could have sent what arrived, and what the asset will be recorded as having cost. That
# second one is the whole reason this is a dialog rather than a menu item - an asset crossing between accounts kept
# in different currencies has to have its cost restated, and a value left empty becomes a zero that is taxed as
# though the asset had been free.

USDT = 4
WALLET_A, WALLET_B, WALLET_EUR = 1, 2, 3
USD, EUR = 2, 3
ARB2_ADDRESS = '0x' + '9' * 40


@pytest.fixture
def funded(prepare_db):
    JalAccountCreator(currency_id=USD, number='', name='USD wallet', investing=1, organization=1,
                      account_type=PredefinedAccountType.Wallet, address='0x' + '1' * 40,
                      chain=AssetLocation.ARB_BLOCKCHAIN).commit()
    JalAccountCreator(currency_id=USD, number='', name='USD wallet 2', investing=1, organization=1,
                      account_type=PredefinedAccountType.Wallet, address='0x' + '2' * 40,
                      chain=AssetLocation.ARB_BLOCKCHAIN).commit()
    JalAccountCreator(currency_id=EUR, number='', name='EUR wallet', investing=1, organization=1,
                      account_type=PredefinedAccountType.Wallet, address=ARB2_ADDRESS,
                      chain=AssetLocation.ARB_BLOCKCHAIN).commit()
    create_assets([('USDT', 'Tether USD', '', USD, PredefinedAsset.Crypto, 0)])   # ID = USDT
    create_actions([(d2t(210101), WALLET_A, 1, [(PredefinedCategory.StartingBalance, 10000.0)])])
    create_trades(WALLET_A, [(d2t(210102), d2t(210102), USDT, 1000.0, 1.0, 0.0)])   # 1000 USDT at basis 1.0
    yield


def _transfer(from_account, to_account, amount, timestamp, asset_id=USDT, deposit=0, address=None):
    data = {'withdrawal_timestamp': timestamp, 'withdrawal_account': from_account, 'withdrawal': str(amount),
            'deposit_timestamp': timestamp, 'deposit_account': to_account, 'deposit': str(deposit),
            'number': '', 'note': '', 'counterparty_address': address,
            'symbol_id': symbol_id_for(asset_id) if asset_id else None}
    return LedgerTransaction.create_new(LedgerTransaction.Transfer, data)


def _ok(dialog) -> bool:
    return dialog._buttons.button(QDialogButtonBox.Ok).isEnabled()


# One currency at both ends: the basis travels with the asset untouched, so there is nothing to ask about
def test_no_value_is_asked_for_when_both_ends_share_a_currency(funded):
    transfer = _transfer(WALLET_A, None, 400, d2t(210103))
    Ledger().rebuild(from_timestamp=0)

    dialog = TransferAssignDialog(transfer.id())
    dialog._account.selection_done(WALLET_B)

    assert dialog._amount_shown is False
    assert _ok(dialog) is True


# Two currencies: what the sending account paid has to be restated in the currency it arrives in, and the dialog
# offers what that comes to - as a starting point, which is why the field stays editable.
def test_the_cost_basis_of_a_crossing_is_computed_and_offered(funded):
    create_quotes(USD, EUR, [(d2t(210103), 0.5)])
    transfer = _transfer(WALLET_A, None, 400, d2t(210103))
    Ledger().rebuild(from_timestamp=0)

    dialog = TransferAssignDialog(transfer.id())
    dialog._account.selection_done(WALLET_EUR)

    assert dialog._amount_shown is True
    assert dialog._amount.text() == '200.00'        # 400 that cost 400 USD, at 0.5 EUR to the dollar
    assert _ok(dialog) is True


# Nothing is offered that isn't known: without a rate the field is left empty for the user to fill, and the dialog
# will not be completed until they do.
def test_no_value_is_offered_when_there_is_no_rate(funded):
    transfer = _transfer(WALLET_A, None, 400, d2t(210103))
    Ledger().rebuild(from_timestamp=0)

    dialog = TransferAssignDialog(transfer.id())
    dialog._account.selection_done(WALLET_EUR)

    assert dialog._amount.text() == ''
    assert _ok(dialog) is False                     # ... and it cannot be assigned while it is empty
    QTest.keyClicks(dialog._amount, '180')
    assert _ok(dialog) is True


# Typing the value is all the user does when none could be offered - no account is chosen again afterwards and no
# date is touched, so the assignment has to become possible on the keystrokes themselves. It didn't: the button was
# decided only when the choice was re-read, and the dialog could not be completed at all where a rate was missing or
# too old to be used - which is precisely where the value has to be entered by hand.
def test_the_value_typed_by_hand_makes_the_assignment_possible(funded):
    create_quotes(USD, EUR, [(d2t(180103), 0.5)])   # the newest rate stored, and years before the transfer
    transfer = _transfer(WALLET_A, None, 400, d2t(210103))
    Ledger().rebuild(from_timestamp=0)

    dialog = TransferAssignDialog(transfer.id())
    dialog._account.selection_done(WALLET_EUR)

    assert dialog._amount.text() == ''              # a rate that old is not offered as a value
    assert _ok(dialog) is False
    QTest.keyClicks(dialog._amount, '180')
    assert _ok(dialog) is True                      # ... and nothing else happens before the button is pressed
    dialog._amount.clear()
    QTest.keyClicks(dialog._amount, '   ')          # emptied again, and it is waiting for a value once more
    assert _ok(dialog) is False


# A number the user has entered is theirs: re-reading the choice recomputes what is displayed around it, but never
# writes over what they typed.
def test_a_value_the_user_entered_is_not_recomputed_over(funded):
    create_quotes(USD, EUR, [(d2t(210103), 0.5)])
    transfer = _transfer(WALLET_A, None, 400, d2t(210103))
    Ledger().rebuild(from_timestamp=0)

    dialog = TransferAssignDialog(transfer.id())
    dialog._account.selection_done(WALLET_EUR)
    dialog._amount.clear()
    QTest.keyClicks(dialog._amount, '333')
    dialog._choice_changed()

    assert dialog._amount.text() == '333'


# The address a chain fetch recorded may already name an account of the user's, and then the dialog is a
# confirmation rather than a question. It is only offered - the chain an address is resolved on is itself a
# deduction when the end that IS known is not a wallet of that chain.
def test_the_account_an_address_names_is_preselected(funded):
    transfer = _transfer(WALLET_A, None, 400, d2t(210103), address=ARB2_ADDRESS)
    Ledger().rebuild(from_timestamp=0)

    dialog = TransferAssignDialog(transfer.id())

    assert dialog._account.selected_id == WALLET_EUR


def test_an_account_that_could_not_have_sent_it_cannot_be_assigned(funded):
    transfer = _transfer(None, WALLET_A, 400, d2t(210103))
    Ledger().rebuild(from_timestamp=0)

    dialog = TransferAssignDialog(transfer.id())
    dialog._account.selection_done(WALLET_B)          # holds no USDT at all, so it cannot be where this came from

    assert _ok(dialog) is False
    assert 'short' in dialog._status.text()


def test_assigning_writes_the_account_and_the_basis(funded):
    create_quotes(USD, EUR, [(d2t(210103), 0.5)])
    transfer = _transfer(WALLET_A, None, 400, d2t(210103))
    Ledger().rebuild(from_timestamp=0)

    dialog = TransferAssignDialog(transfer.id())
    dialog._account.selection_done(WALLET_EUR)
    dialog.accept()

    assert dialog.changed is True
    stored = LedgerTransaction._read("SELECT deposit_account, deposit FROM transfers WHERE oid=:oid",
                                     [(":oid", transfer.id())], named=True)
    assert int(stored['deposit_account']) == WALLET_EUR
    assert Decimal(stored['deposit']) == Decimal('200')
