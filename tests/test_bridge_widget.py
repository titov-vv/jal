import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, create_assets, create_bridges
from constants import PredefinedAsset, PredefinedAccountType
from jal.db.account import JalAccountCreator
from jal.db.operations import LedgerTransaction
from jal.widgets.bridge_widget import BridgeWidget
from jal.widgets.operations_tabs import JalOperationsTabs

ETH = 4
ACC1, ACC2 = 1, 2


@pytest.fixture
def accounts(prepare_db):
    JalAccountCreator(currency_id=2, number='', name='Chain1', investing=1, organization=1,
                      account_type=PredefinedAccountType.Broker).commit()
    JalAccountCreator(currency_id=2, number='', name='Chain2', investing=1, organization=1,
                      account_type=PredefinedAccountType.Broker).commit()
    create_assets([('ETH', 'Ethereum', '', 2, PredefinedAsset.Crypto, 0)])
    yield


# The operations panel must build with the Bridge widget registered at index == otype (8), or selecting a bridge
# row would switch the stack to the wrong page.
def test_operations_tabs_include_bridge(accounts):
    tabs = JalOperationsTabs(None)
    assert LedgerTransaction.Bridge in tabs.widgets
    assert isinstance(tabs.widgets[LedgerTransaction.Bridge], BridgeWidget)
    assert tabs.indexOf(tabs.widgets[LedgerTransaction.Bridge]) == LedgerTransaction.Bridge


def test_bridge_widget_prepare_new(accounts):
    widget = BridgeWidget()
    widget.prepareNew(ACC1)
    assert widget.operation_type == LedgerTransaction.Bridge


def test_bridge_widget_shows_complete_bridge(accounts):
    create_bridges([{'asset': ETH, 'out_ts': d2t(210103), 'out_acc': ACC1, 'out_qty': 2,
                     'in_ts': d2t(210104), 'in_acc': ACC2, 'in_qty': 2}])
    widget = BridgeWidget()
    widget.set_id(1)
    assert widget.model.rowCount() == 1
    row = widget.model.record(0)
    assert Decimal(row.value("out_qty")) == Decimal('2')
    assert Decimal(row.value("in_qty")) == Decimal('2')


# A pending half (one leg NULL) must display without error - this is what the operations list shows before matching.
def test_bridge_widget_shows_pending_half(accounts):
    create_bridges([{'asset': ETH, 'out_ts': d2t(210103), 'out_acc': ACC1, 'out_qty': 2}])   # send-only, in_* NULL
    widget = BridgeWidget()
    widget.set_id(1)
    assert widget.model.rowCount() == 1
    row = widget.model.record(0)
    assert Decimal(row.value("out_qty")) == Decimal('2')
    assert row.isNull("in_account_id") or not row.value("in_account_id")   # the receive leg is empty
