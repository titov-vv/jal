import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from decimal import Decimal

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_ledger
from tests.helpers import d2t
from jal.constants import PredefinedCategory
from PySide6.QtWidgets import QWidget
from jal.db.db import JalDB
from jal.db.operations import LedgerTransaction
from jal.widgets.income_spending_widget import IncomeSpendingWidget

NUMBER = "503340855:FS 0421/000317"


def _widget() -> IncomeSpendingWidget:
    parent = QWidget()
    widget = IncomeSpendingWidget(parent=parent)
    widget._test_parent = parent   # keeps the parent alive as long as the widget
    return widget


def _add_line(widget, amount):
    widget.add_child()
    model = widget.details_model
    row = model.rowCount() - 1
    model.setData(model.index(row, model.fieldIndex("category_id")), PredefinedCategory.Fees)
    model.setData(model.index(row, model.fieldIndex("amount")), amount)


def _count() -> int:
    return JalDB._read("SELECT COUNT(*) FROM actions")


# ----------------------------------------------------------------------------------------------------------------------
# A new operation typed by hand is stored with an empty number
def test_new_operation_is_saved(prepare_db_ledger):
    before = _count()
    widget = _widget()
    widget.createNew(account_id=1)
    widget.model.setData(widget.model.index(0, widget.model.fieldIndex("peer_id")), 1)
    _add_line(widget, '-5.00')
    widget.saveChanges()
    assert _count() == before + 1
    assert JalDB._read("SELECT number FROM actions WHERE oid=(SELECT MAX(oid) FROM actions)") == ''


# A copy of an imported receipt is not the same fiscal document
def test_copy_of_a_receipt_has_no_number(prepare_db_ledger):
    oid = LedgerTransaction.create_new(LedgerTransaction.IncomeSpending, {
        'timestamp': d2t(260814), 'account_id': 1, 'peer_id': 1, 'number': NUMBER,
        'lines': [{'category_id': PredefinedCategory.Fees, 'amount': Decimal('-11.94'), 'note': 'Lidl'}]}).id()
    before = _count()
    widget = _widget()
    widget.set_id(oid)
    widget.copyNew()
    widget.saveChanges()
    assert _count() == before + 1
    assert JalDB._read("SELECT COUNT(*) FROM actions WHERE number=:number", [(":number", NUMBER)]) == 1


# The fiscal id of an imported receipt is shown but can't be edited
def test_number_is_shown_read_only(prepare_db_ledger):
    oid = LedgerTransaction.create_new(LedgerTransaction.IncomeSpending, {
        'timestamp': d2t(260814), 'account_id': 1, 'peer_id': 1, 'number': NUMBER,
        'lines': [{'category_id': PredefinedCategory.Fees, 'amount': Decimal('-11.94'), 'note': 'Lidl'}]}).id()
    widget = _widget()
    widget.set_id(oid)
    assert widget.ui.number.text() == NUMBER
    assert widget.ui.number.isReadOnly()
