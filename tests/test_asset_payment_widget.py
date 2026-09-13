import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, create_assets, create_dividends, nth_operation
from constants import PredefinedAsset, PredefinedAccountType
from PySide6.QtWidgets import QMessageBox, QWidget
from jal.db.db import JalDB
from jal.db.account import JalAccountCreator
from jal.db.operations import LedgerTransaction
from jal.widgets.asset_payment_widget import AssetPaymentWidget

ACCOUNT = 1
AAPL = 4


@pytest.fixture
def account(prepare_db):
    JalAccountCreator(currency_id=2, number='', name='Broker', investing=1, organization=1,
                      account_type=PredefinedAccountType.Broker).commit()
    create_assets([('AAPL', 'Apple', '', 2, PredefinedAsset.Stock, 0)])
    yield


# The payment editor drives the fee through the same FeeWidget the other five use, so a fee typed here is a child
# row of the payment and not a stand-alone gas operation of its own.
def test_the_editor_stores_the_fee_of_a_payment(account):
    create_dividends([(d2t(210101), ACCOUNT, AAPL, Decimal('10'), Decimal('0'), '')])
    oid = nth_operation(LedgerTransaction.AssetPayment, 1).id()
    parent = QWidget()          # a parentless dialog is collected in a way that aborts the process
    widget = AssetPaymentWidget(parent=parent)
    widget.set_id(oid)
    assert widget.fee_widget.fees() == []

    widget.fee_widget.attach()
    widget.fee_widget.amount.setText('0.75')
    widget.fee_widget._mapper.submit()
    widget._save()

    assert JalDB._read_to_list("SELECT account_id, symbol_id, amount FROM fees WHERE operation_id=:oid",
                               [(":oid", oid)]) == [[ACCOUNT, '', '0.75']]
    assert nth_operation(LedgerTransaction.AssetPayment, 1).fee() == Decimal('0.75')
