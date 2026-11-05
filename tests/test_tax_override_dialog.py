from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QDialogButtonBox, QTableView, QStyleOptionViewItem

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_taxes
from tests.helpers import d2t, create_stocks, create_trades, create_dividends, create_corporate_actions, operation_id
from jal.db.country import JalCountry
from jal.db.ledger import Ledger
from jal.db.operations_model import OperationsModel
from jal.widgets.delegates import TAX_OVERRIDE_ROLE
from jal.db.operations import LedgerTransaction, CorporateAction
from jal.db.tax_override import JalTaxOverride, TaxOverride
from jal.widgets.tax_override_dialog import TaxOverrideDialog


def _dividend_and_trade() -> tuple:
    create_stocks([('A', 'Asset A')], currency_id=2)   # ID 4
    create_dividends([(d2t(250303), 1, 4, 10.0, 1.0, "Dividend")])
    create_trades(1, [(d2t(250102), d2t(250104), 4, 10, 10, 0, "buy")])
    return operation_id(LedgerTransaction.AssetPayment), operation_id(LedgerTransaction.Trade)


def _ok(dialog):
    return dialog._buttons.button(QDialogButtonBox.Ok)


# One row per jurisdiction; Ok waits for a note; a row set back to "as the report decides" removes its overrides
def test_dialog_writes_and_reads_overrides(prepare_db_taxes):
    dividend, _ = _dividend_and_trade()
    parent = QWidget()
    dialog = TaxOverrideDialog(LedgerTransaction.AssetPayment, dividend, parent=parent)
    assert list(dialog._rows) == ['pt', 'ru']
    pt_decision, _, pt_note = dialog._rows['pt']
    ru_decision, _, ru_note = dialog._rows['ru']
    assert pt_decision.count() == 4   # a dividend takes a treaty decision too
    assert _ok(dialog).isEnabled()
    pt_decision.setCurrentIndex(1)
    assert not _ok(dialog).isEnabled()
    pt_note.setText("Return of capital")
    ru_decision.setCurrentIndex(3)
    ru_note.setText("Broker lost its status")
    assert _ok(dialog).isEnabled()
    dialog.accept()
    assert JalTaxOverride.for_operation(dividend) == [
        {'jurisdiction': 'pt', 'kind': TaxOverride.NotTaxEvent, 'value': '', 'note': "Return of capital"},
        {'jurisdiction': 'ru', 'kind': TaxOverride.Treaty, 'value': TaxOverride.NoTreaty, 'note': "Broker lost its status"}]
    assert JalTaxOverride.describe(dividend) == \
           f"{JalCountry(data={'code': 'pt'}, search=True).name()}: Not a tax event - Return of capital\n" \
           f"{JalCountry(data={'code': 'ru'}, search=True).name()}: No tax treaty - Broker lost its status"

    dialog = TaxOverrideDialog(LedgerTransaction.AssetPayment, dividend, parent=parent)
    pt_decision, _, pt_note = dialog._rows['pt']
    ru_decision, _, ru_note = dialog._rows['ru']
    assert (pt_decision.currentIndex(), pt_note.text()) == (1, "Return of capital")
    assert (ru_decision.currentIndex(), ru_note.text()) == (3, "Broker lost its status")
    pt_decision.setCurrentIndex(0)
    ru_decision.setCurrentIndex(1)   # the treaty decision is replaced, not kept beside
    dialog.accept()
    assert JalTaxOverride.for_operation(dividend) == [
        {'jurisdiction': 'ru', 'kind': TaxOverride.NotTaxEvent, 'value': '', 'note': "Broker lost its status"}]


def test_dialog_offers_treaty_for_dividends_only(prepare_db_taxes):
    _, trade = _dividend_and_trade()
    parent = QWidget()
    dialog = TaxOverrideDialog(LedgerTransaction.Trade, trade, parent=parent)
    assert [dialog._rows[x][0].count() for x in dialog._rows] == [2, 2]


# The asset as the source of a corporate action's cash: offered for a cash payment, in the RU row only
def test_dialog_offers_asset_source_for_cash_in_ru(prepare_db_taxes):
    create_stocks([('A', 'Asset A'), ('B', 'Asset B')], currency_id=2)   # ID 4, 5
    create_trades(1, [(d2t(250102), d2t(250104), 4, 10, 10, 0, "buy")])
    create_corporate_actions(1, [(d2t(250701), CorporateAction.Merger, 4, 10, "A->B + cash", [(5, 5.0, 1.0), (2, 25.5, 0.0)]),
                                 (d2t(250801), CorporateAction.Split, 5, 5, "Split", [(5, 10.0, 1.0)])])
    parent = QWidget()
    merger = TaxOverrideDialog(LedgerTransaction.CorporateAction, operation_id(LedgerTransaction.CorporateAction, 1),
                               parent=parent)
    assert [merger._rows[x][0].count() for x in merger._rows] == [4, 5]   # with a tax event and a price
    ru_decision, _, ru_note = merger._rows['ru']
    ru_decision.setCurrentIndex(2)
    ru_note.setText("Cash paid by the issuer")
    merger.accept()
    assert JalTaxOverride.for_operation(operation_id(LedgerTransaction.CorporateAction, 1)) == [
        {'jurisdiction': 'ru', 'kind': TaxOverride.AssetSource, 'value': TaxOverride.AssetCountry,
         'note': "Cash paid by the issuer"}]
    split = TaxOverrideDialog(LedgerTransaction.CorporateAction, operation_id(LedgerTransaction.CorporateAction, 2),
                              parent=parent)
    assert [split._rows[x][0].count() for x in split._rows] == [2, 2]


# A corporate action into another asset takes a tax event where the rule carries it, and a price per received share
# that the price field holds; Ok waits for a positive price
def test_dialog_takes_a_price_per_received_share(prepare_db_taxes):
    create_stocks([('A', 'Asset A'), ('B', 'Asset B')], currency_id=2)   # ID 4, 5
    create_trades(1, [(d2t(250102), d2t(250104), 4, 10, 10, 0, "buy")])
    create_corporate_actions(1, [(d2t(250701), CorporateAction.Merger, 4, 10, "A->B", [(5, 5.0, 1.0)])])
    action = operation_id(LedgerTransaction.CorporateAction, 1)
    parent = QWidget()
    dialog = TaxOverrideDialog(LedgerTransaction.CorporateAction, action, parent=parent)
    ru_decision, ru_price, ru_note = dialog._rows['ru']
    assert [ru_decision.itemText(i) for i in range(ru_decision.count())][2:] == \
           ["A tax event", "A tax event at a price per received share"]
    assert not ru_price.isEnabled()
    ru_decision.setCurrentIndex(3)
    ru_note.setText("Exchange ratio of the merger")
    assert ru_price.isEnabled() and not _ok(dialog).isEnabled()
    ru_price.setText("-1")
    assert not _ok(dialog).isEnabled()
    ru_price.setText("12.50")
    assert _ok(dialog).isEnabled()
    dialog.accept()
    assert JalTaxOverride.for_operation(action) == [
        {'jurisdiction': 'ru', 'kind': TaxOverride.PricePerShare, 'value': '12.5', 'note': "Exchange ratio of the merger"}]

    dialog = TaxOverrideDialog(LedgerTransaction.CorporateAction, action, parent=parent)
    ru_decision, ru_price, _ = dialog._rows['ru']
    assert (ru_decision.currentIndex(), ru_price.text(), ru_price.isEnabled()) == (3, "12.5", True)


# The operations list marks an overridden operation with the tax glyph at the end of its notes and lists the decisions
# in the tooltips of its first three columns
def test_operations_list_shows_overrides(prepare_db_taxes):
    dividend, trade = _dividend_and_trade()
    Ledger().rebuild(from_timestamp=0)
    view = QTableView()
    model = OperationsModel(view)
    view.setModel(model)
    model.configureView()
    model.setDateRange(0, d2t(251231))
    row = next(i for i, x in enumerate(model._data) if x['oid'] == dividend)
    other = next(i for i, x in enumerate(model._data) if x['oid'] == trade)
    assert not model.data(model.index(row, 2), TAX_OVERRIDE_ROLE)

    JalTaxOverride.set('pt', dividend, TaxOverride.NotTaxEvent, '', "Return of capital")
    model.refresh_tax_overrides()
    assert model.data(model.index(row, 2), TAX_OVERRIDE_ROLE)
    assert not model.data(model.index(other, 2), TAX_OVERRIDE_ROLE)
    decision = JalTaxOverride.describe(dividend)
    assert model.data(model.index(row, 0), Qt.ToolTipRole).split("\n")[1:] == ["Tax treatment:", decision]
    assert model.data(model.index(row, 2), Qt.ToolTipRole) == "Tax treatment:\n" + decision
    assert model.data(model.index(other, 2), Qt.ToolTipRole) is None

    option = QStyleOptionViewItem()
    view.itemDelegateForColumn(2).initStyleOption(option, model.index(row, 2))
    assert option.features & QStyleOptionViewItem.HasDecoration
    assert option.decorationPosition == QStyleOptionViewItem.Right
