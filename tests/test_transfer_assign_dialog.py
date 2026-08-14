import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from decimal import Decimal

import pytest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialogButtonBox

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, create_assets, create_actions, create_quotes, create_trades, symbol_id_for
from constants import PredefinedAsset, PredefinedCategory, PredefinedAccountType, AssetLocation
from jal.db.account import JalAccount, JalAccountCreator
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


# ----------------------------------------------------------------------------------------------------------------------
# Staking mode: the same dialog assigning to a STAKING BOX. A box is hidden from every account picker by design, so
# what has to be true here is that it is offered in this mode - and that nothing else is.
def test_staking_mode_offers_boxes_and_nothing_else(funded):
    from jal.db.staking import JalStakingBox

    box = JalStakingBox.create(JalAccount(WALLET_A), "Some validator", protocol='Some protocol')
    transfer = _transfer(WALLET_A, None, 400, d2t(210103))
    Ledger().rebuild(from_timestamp=0)

    dialog = TransferAssignDialog(transfer.id(), staking=True)
    model = dialog._account.model()
    shown = [model.getId(model.index(row, 0)) for row in range(model.rowCount())]
    assert shown == [box.id()]           # the wallets are not offered, the box is

    # ... and assigning to it is an ordinary assignment: one currency at both ends asks for no value at all
    dialog._account.selection_done(box.id())
    assert dialog._amount_shown is False
    assert _ok(dialog) is True

    # The ordinary mode is unchanged by any of this - it offers the accounts and not the box
    plain = TransferAssignDialog(transfer.id())._account.model()
    shown = [plain.getId(plain.index(row, 0)) for row in range(plain.rowCount())]
    assert box.id() not in shown and WALLET_B in shown


# What a new box is prefilled with, when it is created from the leg being settled: the protocol the custody import
# named in the description, the chain the known end tracks and the address the asset moved to. The address is what
# settles every FURTHER stake and unstake on its own, so getting it in here is the point of the whole dialog.
def test_a_box_created_from_a_leg_is_prefilled_from_it(funded):
    note = "[custody] stake.link PriorityPool: held for the wallet - to be merged with its counter-leg or converted"
    data = {'withdrawal_timestamp': d2t(210103), 'withdrawal_account': WALLET_A, 'withdrawal': '400',
            'deposit_timestamp': d2t(210103), 'deposit_account': None, 'deposit': '0', 'number': '', 'note': note,
            'counterparty_address': ARB2_ADDRESS, 'symbol_id': symbol_id_for(USDT)}
    transfer = LedgerTransaction.create_new(LedgerTransaction.Transfer, data)
    Ledger().rebuild(from_timestamp=0)

    dialog = TransferAssignDialog(transfer.id(), staking=True)
    leg = dialog._leg
    assert dialog._protocol_of(leg) == 'stake.link PriorityPool'
    assert dialog._chain_of(leg) == AssetLocation.ARB_BLOCKCHAIN     # the chain the known wallet is on
    assert leg['address'] == ARB2_ADDRESS


# The UNSTAKING direction through the same dialog. An arrival names the SOURCE, so this is where an assignment can
# be wrong in a way the staking direction cannot: a box that never held the asset can't have sent it back. Nothing
# about the mode changes between the two directions - what changes is which end is being named, and that the refusal
# below has something to check.
def test_the_unstaking_leg_is_refused_by_an_empty_box_and_settles_by_address(funded):
    from jal.db.staking import JalStakingBox
    from jal.db.transfer_settlement import TransferSettlement

    pool = '0x' + 'b' * 40      # ... and not ARB2_ADDRESS, which the EUR wallet already holds on this chain
    box = JalStakingBox.create(JalAccount(WALLET_A), "Some validator", protocol='Some protocol',
                               chain=AssetLocation.ARB_BLOCKCHAIN, address=pool)
    _transfer(WALLET_A, None, 400, d2t(210103), address=pool)              # staked ...
    arrival = _transfer(None, WALLET_A, 400, d2t(210201), address=pool)    # ... and unstaked
    Ledger().rebuild(from_timestamp=0)

    dialog = TransferAssignDialog(arrival.id(), staking=True)
    assert dialog._sending() is False           # this leg names where the asset came FROM
    # The box is offered exactly as on the outgoing leg, and preselected from the address the leg recorded
    assert dialog._account.selected_id == box.id()
    assert dialog._amount_shown is False        # one currency at both ends, so no cost basis is asked for
    assert _ok(dialog) is False                 # ... but the box holds nothing yet, so it can't have sent this
    assert 'hold' in dialog._status.text()

    # And once a box carries the address, the dialog is not the route at all: the settlement pass pairs BOTH
    # directions on it, so neither leg is left for anybody to assign by hand.
    assert TransferSettlement().settle_all() == 2
    assert TransferAssignDialog(arrival.id(), staking=True)._leg is None


# The container that has no address - a venue's internal staking balance - is where the dialog IS the only route,
# in both directions. The order is what matters there: the stake has to be recorded before the unstake can come out
# of the box, and the dialog says so rather than letting the ledger discover it later.
def test_both_directions_of_an_addressless_position_go_through_the_dialog(funded):
    from jal.db.staking import JalStakingBox

    box = JalStakingBox.create(JalAccount(WALLET_A), "Venue staking", protocol='Venue staking')
    staked = _transfer(WALLET_A, None, 400, d2t(210103))
    unstaked = _transfer(None, WALLET_A, 400, d2t(210201))
    Ledger().rebuild(from_timestamp=0)

    # Nothing resolves an address-less box, so neither leg is preselected - the user names it
    out_dialog = TransferAssignDialog(staked.id(), staking=True)
    assert out_dialog._account.selected_id == 0
    out_dialog._account.selection_done(box.id())
    assert _ok(out_dialog) is True              # the wallet holds what it staked
    out_dialog.accept()
    assert out_dialog.changed is True
    Ledger().rebuild(from_timestamp=0)

    in_dialog = TransferAssignDialog(unstaked.id(), staking=True)
    in_dialog._account.selection_done(box.id())
    assert _ok(in_dialog) is True               # ... and now the box holds it, so it can give it back
    in_dialog.accept()
    Ledger().rebuild(from_timestamp=0)
    assert JalAccount(WALLET_A).get_asset_amount(d2t(210301), USDT) == Decimal('1000')
    assert JalAccount(box.id()).get_asset_amount(d2t(210301), USDT) == Decimal('0')
