import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, create_assets
from constants import PredefinedAsset, PredefinedAccountType, AssetLocation
from PySide6.QtWidgets import QWidget
from jal.db.account import JalAccountCreator
from jal.db.operations import LedgerTransaction, ChainAction
from jal.widgets.chain_action_widget import ChainActionWidget
from jal.widgets.operations_tabs import JalOperationsTabs

ETH = 4
ACC = 1


@pytest.fixture
def wallet(prepare_db):
    JalAccountCreator(currency_id=2, number='', name='Wallet', investing=1, organization=1,
                      account_type=PredefinedAccountType.Wallet, address='0x' + '1' * 40,
                      chain=AssetLocation.ETH_BLOCKCHAIN).commit()
    create_assets([('ETH', 'Ethereum', '', 2, PredefinedAsset.Crypto, 0)])
    yield


# The operations panel must build with the Action widget on a page of its own - the stack is searched by
# operation type, and a missing page would leave an action with no editor at all.
def test_operations_tabs_include_chain_action(wallet):
    tabs = JalOperationsTabs(None)
    assert LedgerTransaction.ChainAction in tabs.widgets
    assert isinstance(tabs.widgets[LedgerTransaction.ChainAction], ChainActionWidget)


# An event needn't concern an asset: a failed call or a plain contract call names none, and 'chain_actions.symbol_id'
# is nullable for exactly that reason. So the Subject selector must not paint itself as a missing required value,
# the way the account it happened on does.
def test_the_subject_is_not_demanded(wallet):
    parent = QWidget()
    widget = ChainActionWidget(parent=parent)
    widget.prepareNew(ACC)
    assert widget.ui.symbol_widget._validate is False
    assert widget.ui.account_widget._validate is True


# ... and an action stored without a subject opens with an empty one, rather than being refused or made up
def test_an_action_without_a_subject_is_shown(wallet):
    operation = LedgerTransaction.create_new(LedgerTransaction.ChainAction, {
        'timestamp': d2t(220206), 'type': ChainAction.FailedTransaction, 'account_id': ACC, 'number': '0xfailed',
        'note': '', 'fee': Decimal('0.5'), 'fee_symbol_id': ETH, 'fee_account': ACC})
    parent = QWidget()
    widget = ChainActionWidget(parent=parent)
    widget.set_id(operation.id())
    assert widget.ui.symbol_widget.selected_id == 0
    assert widget.ui.number.text() == '0xfailed'
