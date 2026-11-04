from PySide6.QtWidgets import QWidget, QDialogButtonBox

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_taxes
from tests.helpers import d2t, create_stocks, create_trades, create_dividends, operation_id
from jal.db.country import JalCountry
from jal.db.operations import LedgerTransaction
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
    pt_decision, pt_note = dialog._rows['pt']
    ru_decision, ru_note = dialog._rows['ru']
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
    pt_decision, pt_note = dialog._rows['pt']
    ru_decision, ru_note = dialog._rows['ru']
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
