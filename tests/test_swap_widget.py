import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from decimal import Decimal

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_fifo
from tests.helpers import d2t, create_stocks, create_trades, create_quotes, create_swaps
from jal.db.account import JalAccount
from jal.db.operations import LedgerTransaction
from jal.widgets.swap_widget import SwapWidget
from jal.widgets.operations_tabs import JalOperationsTabs


# The whole operations panel must build with the Swap widget registered (otype 7 has an editor)
def test_operations_tabs_include_swap(prepare_db):
    tabs = JalOperationsTabs(None)
    assert LedgerTransaction.Swap in tabs.widgets
    assert isinstance(tabs.widgets[LedgerTransaction.Swap], SwapWidget)


# The draft editor opens a blank swap without error
def test_swap_widget_prepare_new(prepare_db):
    widget = SwapWidget()
    widget.prepareNew(1)
    assert widget.operation_type == LedgerTransaction.Swap


# The editor loads an existing swap operation and exposes its fields through the mapper
def test_swap_widget_shows_existing_swap(prepare_db_fifo):
    create_stocks([('A', 'Asset A'), ('B', 'Asset B')], currency_id=2)
    t_buy, t_swap = d2t(220101), d2t(220201)
    create_quotes(4, 2, [(t_swap, 150.0)])
    create_trades(1, [(t_buy, t_buy, 4, 10.0, 100.0, 0.0)])
    create_swaps(1, [(t_swap, 4, 10, 5, 20)])

    widget = SwapWidget()
    widget.set_id(1)                       # oid of the swap
    assert widget.model.rowCount() == 1
    row = widget.model.record(0)
    assert Decimal(row.value("out_qty")) == Decimal('10')
    assert Decimal(row.value("in_qty")) == Decimal('20')
