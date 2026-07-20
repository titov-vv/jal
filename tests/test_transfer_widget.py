import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from decimal import Decimal

from tests.fixtures import project_root, data_path, prepare_db
from jal.db.db import JalDB
from jal.db.helpers import delocalize_decimal
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.symbol import JalSymbol
from jal.db.operations import LedgerTransaction
from jal.widgets.transfer_widget import TransferWidget
from tests.helpers import create_transfers, create_stocks


def _mapped_widgets(widget, field):
    section = widget.model.fieldIndex(field)
    return [w for w in widget._value_widgets[field] if widget.mapper.mappedSection(w) == section]


def _make_accounts():
    wallet = JalAccountCreator(currency_id=2, number='W-1', name='Wallet', organization=1).id()
    other = JalAccountCreator(currency_id=2, number='W-2', name='Other', organization=1).id()
    return JalAccount(wallet), JalAccount(other)


# The page order of a QStackedWidget is not tied to the item order of the combo that drives it - the two were
# swapped when the form was drawn. Selecting "Fee" must show FeePage and "Gas" must show GasPage.
def test_fee_kind_selects_matching_page(prepare_db):
    widget = TransferWidget()
    for index, expected in ((TransferWidget.NO_FEE, "NoFeePage"),
                            (TransferWidget.MONEY_FEE, "FeePage"),
                            (TransferWidget.ASSET_GAS, "GasPage")):
        widget.ui.FeeGasCombo.setCurrentIndex(index)
        assert widget.ui.FeeGasPages.currentWidget().objectName() == expected


def test_transfer_type_selects_matching_page(prepare_db):
    widget = TransferWidget()
    for index, expected in ((TransferWidget.MONEY_TRANSFER, "MoneyTransferPage"),
                            (TransferWidget.ASSET_TRANSFER, "AssetTransferPage")):
        widget.ui.TransferTypeCombo.setCurrentIndex(index)
        assert widget.ui.MoneyAssetPages.currentWidget().objectName() == expected


# A QDataWidgetMapper writes every mapped widget back on submit, so the editor of the hidden page must not stay
# mapped - it would overwrite the value typed on the visible page with its own stale text.
def test_only_visible_page_editor_is_mapped(prepare_db):
    widget = TransferWidget()

    widget.ui.TransferTypeCombo.setCurrentIndex(TransferWidget.MONEY_TRANSFER)
    assert _mapped_widgets(widget, "withdrawal") == [widget.ui.withdrawal]
    assert _mapped_widgets(widget, "deposit") == [widget.ui.deposit]

    widget.ui.TransferTypeCombo.setCurrentIndex(TransferWidget.ASSET_TRANSFER)
    assert _mapped_widgets(widget, "withdrawal") == [widget.ui.asset_amount]
    assert _mapped_widgets(widget, "deposit") == [widget.ui.asset_cost_basis]

    widget.ui.FeeGasCombo.setCurrentIndex(TransferWidget.MONEY_FEE)
    assert _mapped_widgets(widget, "fee") == [widget.ui.fee]

    widget.ui.FeeGasCombo.setCurrentIndex(TransferWidget.ASSET_GAS)
    assert _mapped_widgets(widget, "fee") == [widget.ui.gas]


# Both combos start at index 0, so a record that is also at index 0 emits no currentIndexChanged. The starting
# mapping has to be applied by the constructor or the shared fields would never be mapped at all.
def test_initial_mapping_is_applied_without_any_combo_change(prepare_db):
    widget = TransferWidget()
    assert _mapped_widgets(widget, "withdrawal") == [widget.ui.withdrawal]
    assert _mapped_widgets(widget, "deposit") == [widget.ui.deposit]
    assert _mapped_widgets(widget, "fee") == [widget.ui.fee]


# Gas is burned by the wallet signing the transaction and GasPage has no account selector, so the fee account has
# to follow 'From' - Transfer.processLedger() refuses a fee without an account.
def test_gas_takes_fee_account_from_source(prepare_db):
    wallet, other = _make_accounts()
    widget = TransferWidget()
    widget.createNew(account_id=wallet.id())
    widget.ui.from_account_widget.selected_id = wallet.id()

    widget.ui.FeeGasCombo.setCurrentIndex(TransferWidget.ASSET_GAS)
    widget.fee_kind_selected(TransferWidget.ASSET_GAS)
    assert widget.ui.fee_account_widget.selected_id == wallet.id()

    widget.ui.from_account_widget.selected_id = other.id()
    widget.account_changed()
    assert widget.ui.fee_account_widget.selected_id == other.id()


# Switching to a money transfer must drop the asset, otherwise Transfer would keep processing the operation as an
# asset move because it tells the two apart by 'symbol_id' being set.
def test_switching_to_money_transfer_clears_asset(prepare_db):
    wallet, _other = _make_accounts()
    widget = TransferWidget()
    widget.createNew(account_id=wallet.id())
    symbol = JalSymbol(JalDB()._read("SELECT id FROM asset_symbol LIMIT 1"))

    widget.ui.TransferTypeCombo.setCurrentIndex(TransferWidget.ASSET_TRANSFER)
    widget.ui.symbol_widget.selected_id = symbol.id()
    assert widget.ui.symbol_widget.selected_id == symbol.id()

    widget.ui.TransferTypeCombo.setCurrentIndex(TransferWidget.MONEY_TRANSFER)
    widget.transfer_type_selected(TransferWidget.MONEY_TRANSFER)
    assert widget.ui.symbol_widget.selected_id == 0


# Selecting a money fee must drop the gas asset - 'fee_symbol_id' is what makes Transfer book the fee against an
# asset position instead of money.
def test_switching_to_money_fee_clears_gas_asset(prepare_db):
    wallet, _other = _make_accounts()
    widget = TransferWidget()
    widget.createNew(account_id=wallet.id())
    symbol = JalSymbol(JalDB()._read("SELECT id FROM asset_symbol LIMIT 1"))

    widget.ui.FeeGasCombo.setCurrentIndex(TransferWidget.ASSET_GAS)
    widget.ui.gas_symbol_widget.selected_id = symbol.id()
    widget.ui.FeeGasCombo.setCurrentIndex(TransferWidget.MONEY_FEE)
    widget.fee_kind_selected(TransferWidget.MONEY_FEE)
    assert widget.ui.gas_symbol_widget.selected_id == 0


# Loading a record must derive both selectors from the data, and must not clear anything while doing so:
# setCurrentIndex() emits currentIndexChanged but never 'activated'.
def test_record_load_derives_modes_without_clearing(prepare_db):
    wallet, other = _make_accounts()
    symbol = JalSymbol(JalDB()._read("SELECT id FROM asset_symbol LIMIT 1"))
    widget = TransferWidget()
    widget.createNew(account_id=wallet.id())
    widget.ui.from_account_widget.selected_id = wallet.id()
    widget.ui.to_account_widget.selected_id = other.id()
    widget.ui.symbol_widget.selected_id = symbol.id()
    widget.ui.gas_symbol_widget.selected_id = symbol.id()
    widget.mapper.submit()

    widget.record_changed(0)
    assert widget.ui.TransferTypeCombo.currentIndex() == TransferWidget.ASSET_TRANSFER
    assert widget.ui.FeeGasCombo.currentIndex() == TransferWidget.ASSET_GAS
    assert widget.ui.symbol_widget.selected_id == symbol.id()      # nothing was cleared by the reload
    assert widget.ui.gas_symbol_widget.selected_id == symbol.id()


# The consequence the mapping swap exists to prevent, checked on the stored value rather than on the mapping
# table: what the user types on the visible page must survive a submit, not be replaced by the empty editor of
# the page that is hidden.
def test_hidden_page_editor_does_not_clobber_stored_amount(prepare_db):
    wallet, other = _make_accounts()
    widget = TransferWidget()
    widget.createNew(account_id=wallet.id())
    widget.ui.from_account_widget.selected_id = wallet.id()
    widget.ui.to_account_widget.selected_id = other.id()

    widget.ui.TransferTypeCombo.setCurrentIndex(TransferWidget.ASSET_TRANSFER)
    widget.ui.asset_amount.setText('12.5')
    widget.mapper.submit()
    stored = widget.model.data(widget.model.index(0, widget.model.fieldIndex("withdrawal")))
    assert Decimal(stored) == Decimal('12.5')

    widget.ui.FeeGasCombo.setCurrentIndex(TransferWidget.ASSET_GAS)
    widget.ui.gas.setText('0.271828')
    widget.mapper.submit()
    stored_fee = widget.model.data(widget.model.index(0, widget.model.fieldIndex("fee")))
    assert Decimal(stored_fee) == Decimal('0.271828')


# Reproduces switching between operations in the Operations table: pick a money transfer, then an asset transfer,
# then the money one again. The mapper populates the widgets mapped at the moment the record loads and only then
# emits currentIndexChanged, which is where the mode - and with it the mapping - is switched. So the editor that
# becomes visible was never loaded, and each record showed the amount of the previously selected one.
def test_switching_between_records_shows_own_values(prepare_db):
    wallet, other = _make_accounts()
    create_stocks([('AAPL', 'Apple Inc.')], currency_id=2)
    asset_id = JalDB()._read("SELECT asset_id FROM asset_symbol WHERE symbol='AAPL'")
    create_transfers([
        (1640995200, wallet.id(), Decimal('50000'), other.id(), Decimal('50000'), None),      # money
        (1641081600, wallet.id(), Decimal('490'), other.id(), Decimal('490'), asset_id),      # asset
    ])
    money_oid = JalDB()._read("SELECT oid FROM transfers WHERE symbol_id IS NULL")
    asset_oid = JalDB()._read("SELECT oid FROM transfers WHERE symbol_id IS NOT NULL")

    widget = TransferWidget()

    widget.set_id(money_oid)
    assert delocalize_decimal(widget.ui.withdrawal.text()) == Decimal('50000')

    widget.set_id(asset_oid)
    assert widget.ui.asset_amount.text() != '', "asset editor was left empty by the mapping swap"
    assert delocalize_decimal(widget.ui.asset_amount.text()) == Decimal('490')

    widget.set_id(money_oid)
    assert delocalize_decimal(widget.ui.withdrawal.text()) == Decimal('50000'), "money editor kept the asset transfer's value"

    widget.set_id(asset_oid)
    assert delocalize_decimal(widget.ui.asset_amount.text()) == Decimal('490'), "asset editor kept the money transfer's value"


# Same one-record-behind failure as above, on the other pair of editors that share a field: 'fee' is written by
# ui.fee on FeePage and by ui.gas on GasPage. Switching between a transfer with a money fee and one paying gas
# has to move both the mode selector and the mapping, and load the editor that becomes visible.
def test_switching_between_fee_kinds_shows_own_values(prepare_db):
    wallet, other = _make_accounts()
    create_stocks([('AAPL', 'Apple Inc.')], currency_id=2)
    symbol_id = JalDB()._read("SELECT id FROM asset_symbol WHERE symbol='AAPL'")
    common = {"withdrawal_account": wallet.id(), "deposit_account": other.id(),
              "withdrawal": Decimal('100'), "deposit": Decimal('100'), "fee_account": wallet.id()}
    LedgerTransaction.create_new(LedgerTransaction.Transfer,
                                 {**common, "withdrawal_timestamp": 1640995200, "deposit_timestamp": 1640995200,
                                  "fee": Decimal('7.5')})                                   # money fee
    LedgerTransaction.create_new(LedgerTransaction.Transfer,
                                 {**common, "withdrawal_timestamp": 1641081600, "deposit_timestamp": 1641081600,
                                  "fee": Decimal('0.271828'), "fee_symbol_id": symbol_id})  # gas
    money_oid = JalDB()._read("SELECT oid FROM transfers WHERE fee_symbol_id IS NULL")
    gas_oid = JalDB()._read("SELECT oid FROM transfers WHERE fee_symbol_id IS NOT NULL")

    widget = TransferWidget()

    widget.set_id(money_oid)
    assert widget.ui.FeeGasCombo.currentIndex() == TransferWidget.MONEY_FEE
    assert delocalize_decimal(widget.ui.fee.text()) == Decimal('7.5')

    widget.set_id(gas_oid)
    assert widget.ui.FeeGasCombo.currentIndex() == TransferWidget.ASSET_GAS
    assert widget.ui.gas.text() != '', "gas editor was left empty by the mapping swap"
    assert delocalize_decimal(widget.ui.gas.text()) == Decimal('0.271828')

    widget.set_id(money_oid)
    assert widget.ui.FeeGasCombo.currentIndex() == TransferWidget.MONEY_FEE
    assert delocalize_decimal(widget.ui.fee.text()) == Decimal('7.5'), "fee editor kept the gas value"

    widget.set_id(gas_oid)
    assert delocalize_decimal(widget.ui.gas.text()) == Decimal('0.271828'), "gas editor kept the money fee value"
