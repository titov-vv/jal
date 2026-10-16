import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from decimal import Decimal

import pytest
from PySide6.QtTest import QTest

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, create_assets, create_actions, create_quotes, create_trades, symbol_id_for
from jal.constants import PredefinedAsset, PredefinedAccountType, PredefinedCategory, AssetLocation
from jal.db.asset import JalAsset
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.ledger import Ledger
from jal.db.operations import LedgerTransaction, Transfer
from jal.widgets.transfer_match_dialog import TransferMatchDialog

# ----------------------------------------------------------------------------------------------------------------------
# The manual matcher: what is left after everything that could be PROVEN has been settled - the same transaction hash,
# the address the transaction paid, the report of whoever routed a cross-chain move. What reaches this dialog can only
# be judged on resemblance, so it stays the user's decision; the dialog's job is to make the comparison an honest one
# and to refuse the pairs that cannot be transfers at all.

USDT, USDC = 4, 5
WALLET_A, WALLET_B, WALLET_EUR = 1, 2, 3
USD, EUR = 2, 3
ADDRESS_A, ADDRESS_B, ADDRESS_C = '0x' + '1' * 40, '0x' + '2' * 40, '0x' + '3' * 40


@pytest.fixture
def wallets(prepare_db):
    for name, address in (('ARB wallet', ADDRESS_A), ('ARB wallet 2', ADDRESS_B)):
        JalAccountCreator(currency_id=USD, number='', name=name, investing=1, organization=1,
                          account_type=PredefinedAccountType.Wallet, address=address,
                          chain=AssetLocation.ARB_BLOCKCHAIN).commit()
    JalAccountCreator(currency_id=EUR, number='', name='EUR account', investing=1, organization=1,
                      account_type=PredefinedAccountType.Bank).commit()
    create_assets([('USDT', 'Tether USD', '', USD, PredefinedAsset.Crypto, 0),      # ID = USDT
                   ('USDC', 'USD Coin', '', USD, PredefinedAsset.Crypto, 0)])       # ID = USDC
    # Every value in the dialog is stated in the base currency, so that is what the quotes have to reach
    base = JalAsset.get_base_currency()
    for asset, rate in ((USDT, 1.0), (USDC, 1.0), (USD, 75.0), (EUR, 90.0)):
        create_quotes(asset, base, [(d2t(210101), rate)])
    yield


def _leg(from_account, to_account, amount, timestamp, asset_id=USDT, number='', address=None, deposit=0) -> int:
    data = {'withdrawal_timestamp': timestamp, 'withdrawal_account': from_account, 'withdrawal': str(amount),
            'deposit_timestamp': timestamp, 'deposit_account': to_account, 'deposit': str(deposit),
            'number': number, 'note': '', 'counterparty_address': address,
            'symbol_id': symbol_id_for(asset_id) if asset_id else None}
    return LedgerTransaction.create_new(LedgerTransaction.Transfer, data).oid()


def _listed(tree) -> list:
    return [tree.topLevelItem(i).data(0, TransferMatchDialog.OID) for i in range(tree.topLevelItemCount())]


def _select(tree, oid) -> None:
    for i in range(tree.topLevelItemCount()):
        if tree.topLevelItem(i).data(0, TransferMatchDialog.OID) == oid:
            tree.setCurrentItem(tree.topLevelItem(i))
            return
    raise AssertionError(f"Leg {oid} is not offered")


def _match_enabled(dialog) -> bool:
    from PySide6.QtWidgets import QDialogButtonBox
    return dialog._buttons.button(QDialogButtonBox.Ok).isEnabled()


# Each side of the dialog holds one kind of pending leg: what was sent and never arrived anywhere JAL knows, and what
# arrived from a source JAL doesn't know. A transfer is made of exactly one of each.
def test_the_two_panels_hold_the_two_kinds_of_pending_leg(wallets):
    sent = _leg(WALLET_A, None, 400, d2t(210103))
    arrived = _leg(None, WALLET_B, 400, d2t(210104))

    dialog = TransferMatchDialog()

    assert _listed(dialog._sent_panel) == [sent]
    assert _listed(dialog._arrived_panel) == [arrived]


# Among the legs that COULD be paired, the nearest in time comes first
def test_candidates_are_ranked_by_proximity(wallets):
    sent = _leg(WALLET_A, None, 400, d2t(210103))
    later = _leg(None, WALLET_B, 400, d2t(210110))
    sooner = _leg(None, WALLET_B, 400, d2t(210104))

    dialog = TransferMatchDialog()
    _select(dialog._sent_panel, sent)

    assert _listed(dialog._arrived_panel) == [sooner, later]


# ... but time is not the measure on its own, and this is the case that shows why: a money transfer states each side
# in its own currency, so the quantities are not comparable at all and only the VALUES are. 100 USD that came out as
# 90 EUR belongs to the leg it nearly equals, not to the 200 EUR that happened to arrive an hour later. The values
# are computed here from the quotes, at the moment each leg moved, and stored nowhere.
def test_the_value_gap_outweighs_a_closer_date(wallets):
    sent = _leg(WALLET_A, None, 100, d2t(210103), asset_id=None)              # 100 USD = 7500 in base currency
    near_in_time = _leg(None, WALLET_EUR, 100, d2t(210103) + 3600, asset_id=None, deposit=200)    # 18000
    near_in_value = _leg(None, WALLET_EUR, 100, d2t(210104), asset_id=None, deposit=90)           # 8100

    dialog = TransferMatchDialog()
    _select(dialog._sent_panel, sent)

    assert _listed(dialog._arrived_panel) == [near_in_value, near_in_time]


# A leg that cannot form a transfer with the selected one is not a near miss but a different movement, so it sinks
# below every leg that could - even when it is the closest thing in the list.
def test_what_cannot_be_paired_sinks_below_what_can(wallets):
    sent = _leg(WALLET_A, None, 400, d2t(210103))
    other_asset = _leg(None, WALLET_B, 400, d2t(210103), asset_id=USDC)   # same moment, same size, another asset
    pairable = _leg(None, WALLET_B, 400, d2t(210110))

    dialog = TransferMatchDialog()
    _select(dialog._sent_panel, sent)

    assert _listed(dialog._arrived_panel) == [pairable, other_asset]


# What arrived is what was sent - a movement that delivers less is a bridge, an operation with a leg of its own for
# each side, and the matcher may not silently create one. The user is told so instead of finding out by trying.
def test_a_pair_that_cannot_be_a_transfer_is_refused_before_it_is_made(wallets):
    sent = _leg(WALLET_A, None, 400, d2t(210103))
    short = _leg(None, WALLET_B, 399, d2t(210104))

    dialog = TransferMatchDialog()
    _select(dialog._sent_panel, sent)
    _select(dialog._arrived_panel, short)

    assert not _match_enabled(dialog)
    assert "not the two ends of one transfer" in dialog._status.text()
    assert len(Transfer.pending_legs()) == 2      # ... and nothing was written


def test_matching_two_legs_settles_them_into_one_transfer(wallets):
    sent = _leg(WALLET_A, None, 400, d2t(210103))
    arrived = _leg(None, WALLET_B, 400, d2t(210104))

    dialog = TransferMatchDialog()
    _select(dialog._sent_panel, sent)
    _select(dialog._arrived_panel, arrived)
    assert _match_enabled(dialog)
    dialog.accept()

    assert dialog.changed
    assert Transfer.pending_legs() == []
    transfer = Transfer(sent, Transfer.Outgoing)
    assert not transfer.is_pending()
    assert transfer.account_id() == WALLET_A


# A leg the report was opened on is already chosen, so the list the user is looking at is ranked against it at once
def test_the_leg_the_dialog_was_opened_on_is_preselected(wallets):
    _leg(WALLET_A, None, 400, d2t(210103))
    arrived = _leg(None, WALLET_B, 400, d2t(210104))

    dialog = TransferMatchDialog(arrived)

    assert dialog._selected_oid(dialog._arrived_panel) == arrived


# Opening the dialog settles what the addresses already name. An address settles a leg the moment an account holds it,
# and adding that account is exactly what the user does when this list shows a leg they recognize - so the exact
# settlement is re-run here rather than only after an import, and what is left is the genuinely ambiguous residue.
def test_the_dialog_settles_what_the_addresses_name_when_it_opens(wallets):
    sent = _leg(WALLET_A, None, 400, d2t(210103), address=ADDRESS_B)

    dialog = TransferMatchDialog()

    assert dialog.changed
    assert _listed(dialog._sent_panel) == []
    transfer = Transfer(sent, Transfer.Outgoing)
    assert not transfer.is_pending() and transfer.counterparty_address() == ''


# The value shown beside the quantity is read from the quotes as of the moment the leg moved - a later price says
# nothing about a transfer that has already happened
def test_the_value_of_a_leg_is_read_from_the_quote_of_its_own_date(wallets):
    base = JalAsset.get_base_currency()
    create_quotes(USDT, base, [(d2t(210104), 2.0)])
    sent = _leg(WALLET_A, None, 400, d2t(210103))
    later = _leg(WALLET_A, None, 400, d2t(210105))

    dialog = TransferMatchDialog()

    assert dialog._legs[sent]['value'] == Decimal('400')
    assert dialog._legs[later]['value'] == Decimal('800')


# A pair across currencies has its cost restated in the currency it arrives in: the dialog offers what the send took
# out of the sending account at the rate of the day, keeps what the user types instead, and the lots open at that.
def test_a_pair_across_currencies_is_matched_at_the_cost_basis_stated(wallets):
    create_actions([(d2t(210101), WALLET_A, 1, [(PredefinedCategory.StartingBalance, 10000.0)])])
    create_trades(WALLET_A, [(d2t(210102), d2t(210102), USDT, 1000.0, 1.0, 0.0)])   # 1000 USDT at 1.0 USD
    create_quotes(USD, EUR, [(d2t(210103), 0.5)])
    sent = _leg(WALLET_A, None, 400, d2t(210103))
    arrived = _leg(None, WALLET_EUR, 400, d2t(210104))
    Ledger().rebuild(from_timestamp=0)

    dialog = TransferMatchDialog()
    _select(dialog._sent_panel, sent)
    _select(dialog._arrived_panel, arrived)
    assert dialog._basis_shown is True
    assert dialog._basis.text() == '200.00'         # 400 that cost 400 USD, at 0.5 EUR to the dollar
    dialog._basis.clear()
    QTest.keyClicks(dialog._basis, '   ')
    assert _match_enabled(dialog) is False          # nothing is matched across currencies without a basis
    dialog._basis.clear()
    QTest.keyClicks(dialog._basis, '180')
    assert _match_enabled(dialog) is True
    dialog.accept()
    Ledger().rebuild(from_timestamp=0)

    lots = JalAccount(WALLET_EUR).open_trades_list(JalAsset(USDT))
    assert len(lots) == 1 and lots[0].open_price(adjusted=True) == Decimal('0.45')


# One currency at both ends: the basis travels with the lots and nothing is asked for
def test_a_pair_in_one_currency_asks_for_no_cost_basis(wallets):
    sent = _leg(WALLET_A, None, 400, d2t(210103))
    arrived = _leg(None, WALLET_B, 400, d2t(210104))

    dialog = TransferMatchDialog()
    _select(dialog._sent_panel, sent)
    _select(dialog._arrived_panel, arrived)

    assert dialog._basis_shown is False
    assert _match_enabled(dialog) is True
