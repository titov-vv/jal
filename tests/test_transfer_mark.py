import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QWidget

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, create_assets, symbol_id_for
from jal.constants import AssetLocation, PredefinedAccountType, PredefinedAsset, PredefinedCategory, TransferMark
from jal.db.account import JalAccountCreator
from jal.db.db import JalDB
from jal.db.operations import LedgerTransaction, Transfer
from jal.db.transfer_settlement import TransferSettlement
from jal.data_import.statement import Statement
from jal.db.helpers import db_row2dict
from jal.widgets.transfer_widget import TransferWidget

USDT = 4
WALLET_A, WALLET_B = 1, 2
USD = 2
ADDRESS_B = '0x' + '2' * 40
HASH = '0x' + 'a' * 64
HINT = "held for the wallet - to be merged with its counter-leg or converted"
MARKED = f"[custody] stake.link PriorityPool: {HINT}. 0xc2 → 0xdd"
CLEAN = "stake.link PriorityPool. 0xc2 → 0xdd"


@pytest.mark.parametrize("note, expected", [
    (MARKED, CLEAN),
    (f"[custody] Hyperliquid staking: {HINT}. Staked HYPE", "Hyperliquid staking. Staked HYPE"),
    (f"[custody] stake.link PriorityPool: {HINT}", "stake.link PriorityPool"),
    ("[bridge] LI.FI Diamond (Jumper): arriving leg - to be merged", "LI.FI Diamond (Jumper)"),
    ("[bridge] arriving leg - to be merged", ""),
    ("[bridge] arriving leg. Note: details", "Note: details"),
    ("[custody] Solana staking: удерживается для кошелька - будет объединено. Staked", "Solana staking. Staked"),
    ("My own note. With [custody] inside: yes", "My own note. With [custody] inside: yes"),
    ("[custody]", "[custody]"),
    ("", ""),
    (None, None),
])
def test_settled_note(note, expected):
    assert TransferMark.settled_note(note) == expected


@pytest.fixture
def wallets(prepare_db):
    JalAccountCreator(currency_id=USD, number='', name='ARB wallet', investing=1, organization=1,
                      account_type=PredefinedAccountType.Wallet, address='0x' + '1' * 40,
                      chain=AssetLocation.ARB_BLOCKCHAIN).commit()
    JalAccountCreator(currency_id=USD, number='', name='ARB wallet 2', investing=1, organization=1,
                      account_type=PredefinedAccountType.Wallet, address=ADDRESS_B,
                      chain=AssetLocation.ARB_BLOCKCHAIN).commit()
    create_assets([('USDT', 'Tether USD', '', USD, PredefinedAsset.Crypto, 0)])
    yield


def _leg(from_account, to_account, note=MARKED, number='', address=None):
    return {'withdrawal_timestamp': d2t(210103), 'withdrawal_account': from_account, 'withdrawal': '100',
            'deposit_timestamp': d2t(210103), 'deposit_account': to_account, 'deposit': '100', 'number': number,
            'counterparty_address': address, 'symbol_id': symbol_id_for(USDT), 'note': note}


def _store(*args, **kwargs) -> int:
    return LedgerTransaction.create_new(LedgerTransaction.Transfer, _leg(*args, **kwargs)).id()


def _note(table, oid):
    return JalDB._read(f"SELECT note FROM {table} WHERE oid=:oid", [(":oid", oid)])


def _last(table):
    return JalDB._read(f"SELECT MAX(oid) FROM {table}")


def test_merge(wallets):
    sent, arrived = _store(WALLET_A, None), _store(None, WALLET_B, note='')
    assert TransferSettlement().settle_linked(sent, arrived) == ''
    assert _note('transfers', sent) == CLEAN


def test_merge_takes_the_arriving_note_when_the_mark_leaves_nothing(wallets):
    sent, arrived = _store(WALLET_A, None, note="[bridge] arriving leg"), _store(None, WALLET_B, note='Arrived')
    assert TransferSettlement().settle_linked(sent, arrived) == ''
    assert _note('transfers', sent) == 'Arrived'


def test_settled_by_address(wallets):
    oid = _store(WALLET_A, None, address=ADDRESS_B)
    assert TransferSettlement().settle_by_address() == 1
    assert _note('transfers', oid) == CLEAN


def test_assigned_by_hand(wallets):
    sending, arriving = _store(WALLET_A, None), _store(None, WALLET_B)
    assert TransferSettlement().assign_end(sending, WALLET_B, d2t(210103), 100) == ''
    assert TransferSettlement().assign_end(arriving, WALLET_A, d2t(210103), 100) == ''
    assert _note('transfers', sending) == CLEAN
    assert _note('transfers', arriving) == CLEAN


def test_settled_during_import(wallets):
    oid = _store(WALLET_A, None, number=HASH)
    stored = LedgerTransaction.get_operation(LedgerTransaction.Transfer, oid, Transfer.Outgoing)
    assert stored.settle_with(_leg(WALLET_A, WALLET_B, note='', number=HASH))
    assert _note('transfers', oid) == CLEAN


def test_a_settlement_leaves_the_users_own_note_alone(wallets):
    oid = _store(WALLET_A, None, note='My own note', address=ADDRESS_B)
    assert TransferSettlement().settle_by_address() == 1
    assert _note('transfers', oid) == 'My own note'


def test_a_pending_leg_keeps_its_mark(wallets):
    oid = _store(WALLET_A, None)
    assert _note('transfers', oid) == MARKED


def _other_listing() -> int:
    create_assets([('USDC', 'USD Coin', '', USD, PredefinedAsset.Crypto, 0)])
    return JalDB._read("SELECT id FROM asset_symbol WHERE symbol='USDC'")


def _exchange_legs(arriving_account):
    sent = _store(WALLET_A, None, number=HASH)
    data = _leg(None, arriving_account, note='', number=HASH)
    data['symbol_id'] = _other_listing()
    return sent, LedgerTransaction.create_new(LedgerTransaction.Transfer, data).id()


def test_converted_to_swap(wallets):
    sent, arrived = _exchange_legs(WALLET_A)
    assert TransferSettlement().convert_to_swap(sent, arrived) == ''
    assert _note('swaps', _last('swaps')) == CLEAN


def test_converted_to_bridge(wallets):
    other_chain = JalAccountCreator(currency_id=USD, number='', name='ETH wallet', investing=1, organization=1,
                                    account_type=PredefinedAccountType.Wallet, address='0x' + '3' * 40,
                                    chain=AssetLocation.ETH_BLOCKCHAIN).id()
    sent, arrived = _store(WALLET_A, None), _store(None, other_chain, note='')
    assert TransferSettlement().convert_to_bridge(sent, arrived) == ''
    assert _note('bridges', _last('bridges')) == CLEAN


def test_marked_as_dust(wallets):
    oid = _store(None, WALLET_A)
    assert TransferSettlement().mark_as_dust(oid) == ''
    assert _note('asset_incomes', _last('asset_incomes')) == CLEAN


def test_converted_to_income_spending(wallets):
    data = _leg(WALLET_A, None)
    data['symbol_id'] = None
    oid = LedgerTransaction.create_new(LedgerTransaction.Transfer, data).id()
    assert TransferSettlement().convert_to_income_spending(oid, 1, PredefinedCategory.Spending) == ''
    assert _note('actions', _last('actions')) == CLEAN


def _imported(accounts, number) -> str:
    statement = Statement()
    statement.mapped_id = lambda _domain, statement_id: statement_id
    statement._symbol_asset = lambda _symbol: {'id': USDT}
    symbol = symbol_id_for(USDT)
    statement._import_transfers([{'account': accounts, 'symbol': [symbol, symbol], 'timestamp': d2t(210103),
                                  'withdrawal': 100, 'deposit': 100, 'fee': 0, 'number': number,
                                  'description': MARKED}])
    return _note('transfers', _last('transfers'))


def test_an_import_stores_a_complete_transfer_without_the_mark(wallets):
    assert _imported([WALLET_A, WALLET_B, 0], '1') == CLEAN


def test_an_import_keeps_the_mark_of_a_pending_leg(wallets):
    assert _imported([WALLET_A, 0, 0], '1') == MARKED


def _validated_form_note(deposit_account):
    form = QWidget()
    widget = TransferWidget(form)
    widget.createNew(WALLET_A)
    model = widget.model
    for field, value in (("withdrawal_account", WALLET_A), ("deposit_account", deposit_account), ("note", MARKED)):
        model.setData(model.index(0, model.fieldIndex(field)), value)
    assert widget._validated_accounts(db_row2dict(model, 0))
    return model.data(model.index(0, model.fieldIndex("note")))


def test_the_form_removes_the_mark_when_both_ends_are_named(wallets):
    assert _validated_form_note(WALLET_B) == CLEAN


def test_the_form_keeps_the_mark_while_an_end_is_empty(wallets):
    assert _validated_form_note(None) == MARKED
