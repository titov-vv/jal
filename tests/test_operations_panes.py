import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from decimal import Decimal

import pytest
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import QApplication, QMessageBox, QStyleOptionViewItem, QWidget

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, create_actions, create_trades
from tests.test_account_holdings import wallet, _stake, _claim, WALLET, LINK, EUR, USD
from jal.constants import PredefinedAccountType
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.ledger import Ledger
from jal.db.operations import LedgerTransaction
from jal.db.settings import JalSettings
from jal.widgets.icons import JalIcon
from jal.widgets.operations_widget import OperationsWidget


@pytest.fixture
def owner(prepare_db):
    JalIcon()
    parent = QWidget()
    parent.resize(1200, 800)
    parent.show()
    yield parent
    parent.close()          # a window left on screen is repainted by every test that follows
    parent.deleteLater()


def _window(owner, account_id=0) -> OperationsWidget:
    window = OperationsWidget(owner)
    window.resize(1200, 800)
    window.ui.BalanceDate.setDate(QDate(2021, 3, 1))
    window.ui.BalancesCurrencyCombo.setIndex(EUR)
    window.ui.ChooseAccountBtn.account_id = account_id
    window.show()
    QApplication.processEvents()
    return window


# Which of the three panes are on screen: positions, operations, editor
def _shown(window) -> tuple:
    return (not window.ui.PositionsPane.isHidden(), not window.ui.OperationsPane.isHidden(),
            not window.ui.OperationDetails.isHidden())


def _bank(balance='250') -> int:
    bank = JalAccountCreator(currency_id=USD, number='', name='Bank', investing=0, organization=1,
                             account_type=PredefinedAccountType.Bank).commit()
    create_actions([(d2t(210102), bank.id(), 1, [(5, Decimal(balance))])])
    Ledger().rebuild(from_timestamp=0)
    return bank.id()


# ----------------------------------------------------------------------------------------------------------------------
def test_positions_appear_with_an_account_that_holds_them(wallet, owner):
    window = _window(owner)
    assert _shown(window) == (False, True, True)     # all accounts: nothing to list
    window.ui.ChooseAccountBtn.account_id = WALLET
    assert _shown(window) == (True, True, True)
    assert window.positions_model.rowCount(window.positions_model.index(-1, -1)) == 3
    assert window.ui.PositionsTitle.text() == "Positions of ETH wallet as of 01/03/2021"


def test_a_double_click_on_a_group_goes_back_to_all_accounts_without_positions(wallet, owner):
    window = _window(owner, WALLET)
    window.ui.ChooseAccountBtn.account_id = 0
    assert _shown(window) == (False, True, True)
    assert window.ui.OperationsCollapseBtn.isHidden()


def test_a_money_only_account_has_no_positions_and_no_collapse_button(wallet, owner):
    bank = _bank()
    window = _window(owner, bank)
    assert _shown(window) == (False, True, True)
    assert window.ui.OperationsCollapseBtn.isHidden()


def test_a_box_names_the_wallet_in_its_title(wallet, owner):
    box = _stake()
    window = _window(owner, box.id())
    assert window.ui.PositionsTitle.text() == "Positions of LINK pool as of 01/03/2021, staked from ETH wallet"


def test_the_list_follows_the_balances_date_and_currency(wallet, owner):
    _stake()
    window = _window(owner, WALLET)
    model = window.positions_model
    total = lambda: [x for x in [model._root.getChild(i).details() for i in range(model._root.childrenCount())]
                     if x.get('kind') == 'total'][-1]
    assert total()['value_common'] == Decimal('100')      # 100 LINK at 12 less 1,000, at half a euro
    window.ui.BalancesCurrencyCombo.setIndex(USD)
    assert total()['value_common'] == Decimal('200')
    window.ui.BalanceDate.setDate(QDate(2020, 12, 31))    # before the wallet bought anything
    assert not model.hasPositions()
    assert _shown(window) == (False, True, True)


def test_a_ledger_update_reaches_the_list(wallet, owner):
    window = _window(owner, WALLET)
    assert window.positions_model.hasPositions()
    create_trades(WALLET, [(d2t(210102), d2t(210102), LINK, Decimal('-100'), Decimal('12'), Decimal('0'))])
    Ledger().rebuild(from_timestamp=0)
    JalAccount(WALLET).invalidate_cache()
    window.refresh()
    assert not window.positions_model.hasPositions()


# ----------------------------------------------------------------------------------------------------------------------
def test_the_arrows_step_through_the_three_views_and_lead_back(wallet, owner):
    window = _window(owner, WALLET)
    window.ui.PositionsCollapseBtn.click()
    assert _shown(window) == (False, True, True)     # operations only
    window.ui.OperationsCollapseBtn.click()
    assert _shown(window) == (True, True, True)
    window.ui.OperationsCollapseBtn.click()
    assert _shown(window) == (True, False, False)    # positions only, and the editor goes with the operations
    window.ui.PositionsCollapseBtn.click()
    assert _shown(window) == (True, True, True)


def test_coming_back_restores_the_split(wallet, owner):
    window = _window(owner, WALLET)
    window.ui.PositionsOperationsSplitter.setSizes([120, 300])
    QApplication.processEvents()
    saved = window.ui.PositionsOperationsSplitter.sizes()
    window.ui.PositionsCollapseBtn.click()
    QApplication.processEvents()
    window.ui.OperationsCollapseBtn.click()
    QApplication.processEvents()
    assert window.ui.PositionsOperationsSplitter.sizes() == saved


def test_another_account_keeps_the_view(wallet, owner):
    other = JalAccountCreator(currency_id=USD, number='', name='Other', investing=1, organization=1,
                              account_type=PredefinedAccountType.Broker).commit()
    create_trades(other.id(), [(d2t(210102), d2t(210102), LINK, Decimal('1'), Decimal('10'), Decimal('0'))])
    Ledger().rebuild(from_timestamp=0)
    window = _window(owner, WALLET)
    window.ui.PositionsCollapseBtn.click()
    window.ui.ChooseAccountBtn.account_id = other.id()
    assert _shown(window) == (False, True, True)


def test_the_view_and_details_are_remembered(wallet, owner):
    window = _window(owner, WALLET)
    window.ui.OperationsCollapseBtn.click()
    window.close()
    assert _shown(_window(owner, WALLET)) == (True, False, False)
    JalSettings().setValue("OperationPanes", OperationsWidget.SHOW_BOTH)
    window = _window(owner, WALLET)
    window.ui.DetailsToggleBtn.click()
    window.close()
    reopened = _window(owner, WALLET)
    assert _shown(reopened) == (True, True, False)
    assert not reopened.ui.DetailsToggleBtn.isChecked()


# ----------------------------------------------------------------------------------------------------------------------
def _select_first(window):
    window.ui.OperationsTableView.selectRow(0)
    QApplication.processEvents()


def _page(window) -> int:
    return getattr(window.ui.OperationsTabs.currentWidget(), 'operation_type', LedgerTransaction.NA)


def _all_time(window):
    window.operations_model.setDateRange(0, d2t(300101))


def test_a_closed_editor_loads_nothing_and_catches_up_when_opened(wallet, owner):
    window = _window(owner, WALLET)
    _all_time(window)
    window.ui.DetailsToggleBtn.click()
    _select_first(window)
    assert _page(window) == LedgerTransaction.NA
    window.ui.DetailsToggleBtn.click()
    assert _page(window) == LedgerTransaction.Trade


def test_a_double_click_on_an_operation_opens_the_editor(wallet, owner):
    window = _window(owner, WALLET)
    _all_time(window)
    window.ui.DetailsToggleBtn.click()
    _select_first(window)
    window.ui.OperationsTableView.doubleClicked.emit(window.ui.OperationsTableView.currentIndex())
    assert _shown(window) == (True, True, True)
    assert window.ui.DetailsToggleBtn.isChecked()
    assert _page(window) == LedgerTransaction.Trade


# The editor has unsaved changes and the user answers Cancel, so nothing may close
@pytest.mark.parametrize("close", ["DetailsToggleBtn", "OperationsCollapseBtn"])
def test_cancelling_the_prompt_keeps_the_editor(wallet, owner, monkeypatch, close):
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.Cancel)
    window = _window(owner, WALLET)
    _all_time(window)
    _select_first(window)
    window.ui.OperationsTabs.widgets[LedgerTransaction.Trade].modified = True
    getattr(window.ui, close).click()
    assert _shown(window) == (True, True, True)
    assert window.ui.DetailsToggleBtn.isChecked()
    assert window.ui.OperationsTabs.widgets[LedgerTransaction.Trade].modified
    window.ui.OperationsTabs.widgets[LedgerTransaction.Trade].modified = False


def test_the_copy_key_opens_the_editor_first(wallet, owner):
    window = _window(owner, WALLET)
    _all_time(window)
    _select_first(window)
    window.ui.OperationsCollapseBtn.click()
    assert _shown(window) == (True, False, False)
    window.copy_operation()
    assert _shown(window) == (True, True, True)
    assert _page(window) == LedgerTransaction.Trade
    trade = window.ui.OperationsTabs.widgets[LedgerTransaction.Trade]
    trade.revertChanges()


def test_the_new_key_opens_the_editor_before_the_menu(wallet, owner, monkeypatch):
    window = _window(owner, WALLET)
    window.ui.DetailsToggleBtn.click()
    shown_when_clicked = []
    window.ui.NewOperationBtn.setMenu(None)
    window.ui.NewOperationBtn.clicked.connect(lambda: shown_when_clicked.append(_shown(window)))
    window.new_operation_by_key()
    QApplication.processEvents()
    assert shown_when_clicked == [(True, True, True)]


def test_a_heading_spans_the_row_and_no_blank_profit_is_colored(wallet, owner):
    _claim('4')
    window = _window(owner, WALLET)
    model = window.positions_model
    view = window.ui.PositionsTreeView
    assert view.isFirstColumnSpanned(2, model.index(-1, -1))
    assert not view.isFirstColumnSpanned(0, model.index(-1, -1))
    delegate = view.itemDelegateForColumn(model.fieldIndex('p/l'))
    profit, blank = QStyleOptionViewItem(), QStyleOptionViewItem()
    delegate.initStyleOption(profit, model.index(0, model.fieldIndex('p/l')))
    delegate.initStyleOption(blank, model.index(1, model.fieldIndex('p/l')))
    assert profit.backgroundBrush.style() != Qt.NoBrush
    assert blank.backgroundBrush.style() == Qt.NoBrush


def test_shown_rows_mark_a_claim_with_who_owes_it(wallet, owner):
    _claim('4')
    model = _window(owner, WALLET).positions_model
    claims = model.index(2, 0)
    assert model.data(model.index(0, model.fieldIndex('asset_name'), claims)) == 'Arbitrum · FluidMerkleDistributor'
