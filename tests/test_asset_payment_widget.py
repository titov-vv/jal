import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, create_assets, create_stock_dividends
from constants import PredefinedAsset, PredefinedAccountType
from PySide6.QtWidgets import QMessageBox
from jal.db.account import JalAccountCreator
from jal.db.operations import AssetPayment
from jal.widgets.asset_payment_widget import AssetPaymentWidget

ACCOUNT = 1
AAPL = 4


@pytest.fixture
def account(prepare_db):
    JalAccountCreator(currency_id=2, number='', name='Broker', investing=1, organization=1,
                      account_type=PredefinedAccountType.Broker).commit()
    create_assets([('AAPL', 'Apple', '', 2, PredefinedAsset.Stock, 0)])
    yield


# The price of a stock dividend/vesting is stored in the operation itself, so it must be typed in by hand -
# there is no quote to take it from.
def test_stock_dividend_price_is_editable(account):
    create_stock_dividends([(AssetPayment.StockDividend, d2t(210101), ACCOUNT, AAPL, Decimal('10'), 2,
                             Decimal('100'), Decimal('0'), '')])
    widget = AssetPaymentWidget()
    widget.set_id(1)
    assert not widget.ui.price_edit.isReadOnly()

    widget.ui.price_edit.setText('123.4567')
    widget.mapper.submit()
    assert Decimal(widget.model.record(0).value("price")) == Decimal('123.4567')
    assert widget._validated()
    widget._save()
    assert AssetPayment(1).price() == Decimal('123.4567')


# A non-numeric price becomes a zero, which validation refuses - shares granted for nothing is not a valid input.
def test_stock_dividend_price_is_validated(account, monkeypatch):
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.Ok)
    create_stock_dividends([(AssetPayment.StockDividend, d2t(210101), ACCOUNT, AAPL, Decimal('10'), 2,
                             Decimal('100'), Decimal('0'), '')])
    widget = AssetPaymentWidget()
    widget.set_id(1)

    widget.ui.price_edit.setText('not a price')
    widget.mapper.submit()
    assert Decimal(widget.model.record(0).value("price")) == Decimal('0')
    assert not widget._validated()
