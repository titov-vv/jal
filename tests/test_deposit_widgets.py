import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, create_assets, create_actions
from constants import PredefinedAsset, PredefinedAccountType, PredefinedCategory
from jal.db.account import JalAccountCreator
from jal.db.deposit import JalDepositBox
from jal.db.ledger import Ledger
from jal.db.operations import LedgerTransaction
from jal.widgets.conversion_widget import ConversionWidget
from jal.widgets.deposit_dialogs import move_money, record_interest
from jal.widgets.operations_tabs import JalOperationsTabs
from jal.reports.deposits import DepositsListModel, DepositDetailsModel
from jal.reports.reports import Reports


@pytest.fixture
def accounts(prepare_db):
    JalAccountCreator(currency_id=2, number='', name='Wallet', investing=1, organization=1,
                      account_type=PredefinedAccountType.Wallet, address='0x' + '1' * 40,
                      chain=301).commit()   # AssetLocation.ETH_BLOCKCHAIN
    create_assets([('ETH', 'Ethereum', '', 2, PredefinedAsset.Crypto, 0),
                   ('WETH', 'Wrapped Ethereum', '', 2, PredefinedAsset.Crypto, 0)])
    yield


# ----------------------------------------------------------------------------------------------------------------------
# The operations panel must build with the Conversion widget registered at index == otype (6), the slot the retired
# term deposit operation used to hold - the stack addresses its pages by operation type.
def test_operations_tabs_include_conversion(accounts):
    tabs = JalOperationsTabs(None)
    assert LedgerTransaction.Conversion in tabs.widgets
    assert isinstance(tabs.widgets[LedgerTransaction.Conversion], ConversionWidget)
    assert tabs.indexOf(tabs.widgets[LedgerTransaction.Conversion]) == LedgerTransaction.Conversion
    assert tabs.get_operations_list()[LedgerTransaction.Conversion] == "Conversion"


def test_conversion_widget_prepare_new(accounts):
    widget = ConversionWidget()
    widget.prepareNew(1)
    assert widget.operation_type == LedgerTransaction.Conversion


# ----------------------------------------------------------------------------------------------------------------------
# The Deposits window is discovered by the report loader, so it appears in the Reports menu
def test_deposits_report_is_registered(prepare_db):
    reports = Reports(None, None)
    assert "DepositsReportWindow" in [x['window_class'] for x in reports.items]
    assert "TermDepositsReportWindow" not in [x['window_class'] for x in reports.items]


# ----------------------------------------------------------------------------------------------------------------------
@pytest.fixture
def bank_with_deposit(prepare_db):
    JalAccountCreator(currency_id=2, number='B1', name='Bank account', organization=1,
                      account_type=PredefinedAccountType.Bank).commit()
    create_actions([(d2t(210101), 1, 1, [(PredefinedCategory.StartingBalance, 10000.0)])])
    box = JalDepositBox.create("Deposit A", currency_id=2, organization_id=1, end_date=d2t(211231),
                               rate=Decimal('4.25'))
    move_money(1, box.id(), Decimal('1000'), d2t(210201))
    record_interest(box, d2t(210401), Decimal('40'), Decimal('5'))
    Ledger().rebuild(from_timestamp=0)
    yield box


# The model behind the deposits table shows the figures the window promises, and totals them
def test_deposits_list_model_shows_the_deposit(bank_with_deposit):
    from PySide6.QtWidgets import QTableView
    view = QTableView()
    model = DepositsListModel(view)
    view.setModel(model)
    model.updateView(timestamp=d2t(210501))

    assert model.rowCount() == 1
    assert model.data_text(model.deposit(model.index(0, 0)), 0) == "Deposit A"
    assert model.data_text(model.deposit(model.index(0, 0)), 3) == d2t(210201)     # opened
    assert model.data_text(model.deposit(model.index(0, 0)), 4) == d2t(211231)     # ends
    assert model.data_text(model.deposit(model.index(0, 0)), 5) == Decimal('4.25')  # rate
    assert model.data_text(model.deposit(model.index(0, 0)), 6) == Decimal('1035')  # balance
    assert model.data_text(model.deposit(model.index(0, 0)), 7) == Decimal('35')    # interest, net of tax


# ... and the details model lists what happened, with a running balance
def test_deposit_details_model_lists_operations(bank_with_deposit):
    from PySide6.QtWidgets import QTableView
    view = QTableView()
    model = DepositDetailsModel(view)
    model.setDeposit(bank_with_deposit, d2t(210501))

    assert model.rowCount() == 2
    assert model.data(model.index(0, 3)) == Decimal('1000')
    assert model.data(model.index(1, 3)) == Decimal('1035')
    assert model.data(model.index(0, 1)) != ''      # every row names the operation it came from


# The window itself builds, finds its deposit and reacts to a selection (which is what fills the details table)
def test_deposits_window_builds_and_selects(bank_with_deposit):
    from jal.reports.deposits import DepositsReportWindow
    window = DepositsReportWindow(Reports(None, None))
    window.ui.DepositsDate.setDate(window.ui.DepositsDate.date())   # keep the default 'today'
    window.updateReport()

    assert window.deposits_model.rowCount() == 1
    window.ui.ReportTableView.selectRow(0)
    assert window._selected().id() == bank_with_deposit.id()
    assert window.details_model.rowCount() == 2


# Nothing selected means nothing to show - and no exception
def test_deposit_details_model_without_a_deposit(prepare_db):
    from PySide6.QtWidgets import QTableView
    model = DepositDetailsModel(QTableView())
    model.setDeposit(None, d2t(210501))
    assert model.rowCount() == 0
