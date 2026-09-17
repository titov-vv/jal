# Tests of the SHAPE of the rows the operations table draws - how many lines a row is and what stands on them.
# What is booked by those operations is the subject of test_swap.py, test_conversion.py, test_bridge.py and
# test_asset_fee.py; nothing is asked of the ledger here beyond the balances the rows print.
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from decimal import Decimal

import pytest

from PySide6.QtCore import QSortFilterProxyModel
from PySide6.QtWidgets import QTableView

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_fifo
from tests.helpers import d2t, create_stocks, create_trades, create_quotes, create_bridges, \
    create_cross_chain_swaps, create_coupons
from jal.db.ledger import Ledger
from jal.db.account import JalAccountCreator
from jal.db.operations import LedgerTransaction, AssetPayment, ChainAction, Swap, Conversion, Transfer, Bridge
from jal.db.operations_model import OperationsModel
from jal.widgets.delegates import transaction_link


# One of every operation that has a fee part, each carrying a transaction hash, plus a stand-alone gas payment.
def _ledger_with_every_fee(gas_symbol, asset):
    t_buy = d2t(220101)
    create_trades(1, [(t_buy, t_buy, asset, 100.0, 100.0, 0.0)])
    create_trades(1, [(t_buy, t_buy, gas_symbol, 10.0, 10.0, 0.0)])
    LedgerTransaction.create_new(LedgerTransaction.Swap, {
        'timestamp': d2t(220201), 'account_id': 1, 'tx_hash': '0xswap', 'out_symbol_id': asset,
        'out_qty': Decimal('10'), 'in_symbol_id': 5, 'in_qty': Decimal('20'),
        'fee_symbol_id': gas_symbol, 'fee_qty': Decimal('0.5'), 'note': ''})
    LedgerTransaction.create_new(LedgerTransaction.Conversion, {
        'timestamp': d2t(220202), 'account_id': 1, 'tx_hash': '0xconversion', 'out_symbol_id': asset,
        'out_qty': Decimal('10'), 'in_symbol_id': 5, 'in_qty': Decimal('10'),
        'fee_symbol_id': gas_symbol, 'fee_qty': Decimal('0.5'), 'note': ''})
    LedgerTransaction.create_new(LedgerTransaction.Transfer, {
        'withdrawal_timestamp': d2t(220203), 'withdrawal_account': 1, 'withdrawal': Decimal('5'),
        'deposit_timestamp': d2t(220203), 'deposit_account': 2, 'deposit': Decimal('5'), 'symbol_id': asset,
        'fee_account': 1, 'fee': Decimal('0.5'), 'fee_symbol_id': gas_symbol, 'number': '0xtransfer'})
    create_bridges([{'out_ts': d2t(220204), 'out_acc': 1, 'out_qty': 5.0, 'out_hash': '0xbridge',
                     'in_ts': d2t(220205), 'in_acc': 2, 'in_qty': 5.0, 'asset': asset,
                     'fee_asset': gas_symbol, 'fee_qty': 0.5}])
    LedgerTransaction.create_new(LedgerTransaction.ChainAction,
                                 {'timestamp': d2t(220206), 'type': ChainAction.Authorization, 'account_id': 1,
                                  'number': '0xstandalone', 'note': '',
                                  'fee': Decimal('0.5'), 'fee_symbol_id': gas_symbol, 'fee_account': 1})
    create_cross_chain_swaps([{'ts': d2t(220207), 'acc': 1, 'out_asset': asset, 'out_qty': 10.0, 'hash': '0xleg',
                               'in_ts': d2t(220208), 'in_acc': 2, 'in_asset': 5, 'in_qty': 20.0,
                               'fee_asset': gas_symbol, 'fee_qty': 0.5, 'note': 'a note'}])


@pytest.fixture
def every_fee(prepare_db_fifo):
    JalAccountCreator(currency_id=2, number='U2', name='Other', investing=1, organization=1).commit()
    create_stocks([('A', 'Asset A'), ('B', 'Asset B'), ('GAS', 'Native coin')], currency_id=2)  # 4, 5 and 6
    create_quotes(4, 2, [(d2t(220201), 150.0), (d2t(220207), 150.0)])   # the two swaps are valued at their date
    _ledger_with_every_fee(gas_symbol=6, asset=4)
    Ledger().rebuild(from_timestamp=0)


# The list as the operations table draws it: every row, as (operation, [Timestamp, Account, Notes]).
@pytest.fixture
def drawn_rows(every_fee):
    model = OperationsModel(QTableView())
    model.setDateRange(0, d2t(220301))
    rows = []
    for row in range(model.rowCount()):
        odata = model._data[row]
        operation = LedgerTransaction.get_operation(odata['otype'], odata['oid'], odata['opart'])
        rows.append((operation, [model.data_text(operation, column) for column in range(3)]))
    yield rows


# A fee is not a transaction of its own - the operation it belongs to names the transaction on the row right above -
# so a fee row prints no hash under its timestamp. It is a rule for the whole family: a transfer, a bridge, a swap
# and a conversion all draw their fee the same way, one line tall and telling only the account it was paid from.
def test_a_fee_row_names_no_transaction(drawn_rows):
    fee_rows = [(op, cells) for op, cells in drawn_rows if op.is_fee_row()]
    assert [op.type() for op, _ in fee_rows] == [LedgerTransaction.Swap, LedgerTransaction.Conversion,
                                                 LedgerTransaction.Transfer, LedgerTransaction.Bridge,
                                                 LedgerTransaction.ChainAction, LedgerTransaction.Swap]
    for operation, (timestamp, account, description) in fee_rows:
        where = operation.name()
        assert operation.number() == '', where          # the hash belongs to the transaction, not to its gas
        assert "\n" not in timestamp, where
        assert "\n" not in account, where               # ... and neither does the asset name: 1 line, 1 row
        assert operation.view_rows() == 1, where
        if operation.type() == LedgerTransaction.ChainAction:
            # The cost of an event is the whole of it, so the row says what the charge WAS instead of repeating the
            # event the row above already names - and a rent is not called a fee, being locked and not consumed.
            assert description in (operation.tr("Gas"), operation.tr("Rent")), where
        else:
            assert description.split(" (")[0].endswith("fee"), where   # the note rides the same line, so still 1


# Every column of a row is drawn inside the height the operation asked for, so a column that writes more lines than
# view_rows() has its tail cut off - invisibly, since nothing marks the row as truncated. The check is worth having
# for the whole list: the two asset legs of a bridge reserved one line while naming a transaction and an asset.
def test_no_row_writes_more_lines_than_it_reserved(drawn_rows):
    clipped = []
    for operation, cells in drawn_rows:
        lines = max([len(str(cell).split("\n")) for cell in cells]
                    + [len(operation.value_change()), len(operation.value_total())])
        if lines > operation.view_rows():
            clipped.append(f"{operation.name()}: {lines} lines in {operation.view_rows()} row(s)")
    assert clipped == []


# A cell holding fewer lines than its row is tall is drawn vertically centred, which leaves a one-line note sitting
# half a line below the columns beside it. The Notes column therefore fills the height its operation asked for -
# the note is simply the last line of it, empty when there is none (see Trade.description, the oldest of them).
def test_the_notes_column_fills_the_height_of_its_row(drawn_rows):
    misaligned = [f"{operation.name()}: {notes!r} in {operation.view_rows()} row(s)"
                  for operation, (_timestamp, _account, notes) in drawn_rows
                  if len(notes.split("\n")) != operation.view_rows()]
    assert misaligned == []


# The scope of that rule is a fee PART. The event that burned the gas is an operation in its own right and the
# hash is the only thing that identifies it, so it keeps it - while the cost row beneath it does not.
def test_a_chain_action_keeps_its_hash(drawn_rows):
    rows = [(op, cells) for op, cells in drawn_rows if op.type() == LedgerTransaction.ChainAction]
    assert len(rows) == 2                      # the event, and what it cost
    event, (timestamp, _account, _description) = [x for x in rows if not x[0].is_fee_row()][0]
    assert event.number() == '0xstandalone'
    assert timestamp.endswith("\n# 0xstandalone")
    cost, (cost_timestamp, _account, _description) = [x for x in rows if x[0].is_fee_row()][0]
    assert "0xstandalone" not in cost_timestamp


# ----------------------------------------------------------------------------------------------------------------------
# A filter that hides the source rows a test names, the way the search string of the operations table hides rows.
class _HidingProxy(QSortFilterProxyModel):
    def __init__(self, parent):
        super().__init__(parent)
        self.hidden = lambda row: False

    def filterAcceptsRow(self, source_row, source_parent):
        return not self.hidden(source_row)


# The operations table as the main window builds it: the model behind a filtering proxy, with its delegates set.
def _table(end: int):
    view = QTableView()
    model = OperationsModel(view)
    proxy = _HidingProxy(view)
    proxy.setSourceModel(model)
    view.setModel(proxy)
    model.configureView()
    model.setDateRange(0, end)
    return view, model, proxy


# Every visible row as ((otype, opart), (tied above, tied below, same account above)).
def _links(view, model) -> list:
    proxy = view.model()
    rows = []
    for row in range(proxy.rowCount()):
        index = proxy.index(row, 0)
        odata = model._data[proxy.mapToSource(index).row()]
        rows.append(((odata['otype'], odata['opart']), transaction_link(index)))
    return rows


_ALONE = (False, False, False)
_LEADS = (False, True, False)


# Rows of one transaction and one second are drawn as a group: a fee under its operation, a transfer's legs under
# each other. A leg that arrives in another second or names no transaction stands alone, as a row of its own.
def test_rows_of_one_transaction_are_tied(every_fee):
    view, model, _ = _table(d2t(220301))
    T = LedgerTransaction
    assert _links(view, model) == [
        ((T.IncomeSpending, 0), _ALONE), ((T.Trade, 0), _ALONE), ((T.Trade, 0), _ALONE),
        ((T.Swap, Swap.Whole), _LEADS), ((T.Swap, Swap.Fee), (True, False, True)),
        ((T.Conversion, Conversion.Whole), _LEADS), ((T.Conversion, Conversion.Fee), (True, False, True)),
        ((T.Transfer, Transfer.Outgoing), _LEADS),
        ((T.Transfer, Transfer.Fee), (True, True, False)),         # the payer alone is not what the leg above says
        ((T.Transfer, Transfer.Incoming), (True, False, False)),   # neither is the arriving end
        ((T.Bridge, Bridge.Outgoing), _LEADS), ((T.Bridge, Bridge.Fee), (True, False, True)),
        ((T.Bridge, Bridge.Incoming), _ALONE),                      # another second, and no hash of its own
        ((T.ChainAction, ChainAction.Whole), _LEADS), ((T.ChainAction, ChainAction.Fee), (True, False, True)),
        ((T.Swap, Swap.Outgoing), _LEADS), ((T.Swap, Swap.Fee), (True, False, True)),
        ((T.Swap, Swap.Incoming), _ALONE)]


# number() is blank on a fee row, so the group needs the transaction from an accessor that is not
def test_a_fee_row_still_knows_its_transaction(drawn_rows):
    fees = [op for op, _ in drawn_rows if op.is_fee_row()]
    assert [op.transaction() for op in fees] == ['0xswap', '0xconversion', '0xtransfer', '0xbridge',
                                                 '0xstandalone', '0xleg']
    assert all([op.number() == '' for op in fees])


# The tie is a property of the rows the view SHOWS: a filter that hides the head of a group leaves the rest of it
# joined to nothing that is gone.
def test_a_hidden_row_breaks_the_tie(every_fee):
    view, model, proxy = _table(d2t(220301))
    swap = lambda row: model._data[row]['otype'] == LedgerTransaction.Swap and model._data[row]['opart'] == Swap.Whole
    proxy.hidden = swap
    proxy.invalidate()
    links = _links(view, model)
    assert ((LedgerTransaction.Swap, Swap.Whole), _LEADS) not in links
    assert links[3] == ((LedgerTransaction.Swap, Swap.Fee), _ALONE)
    transfer = lambda row: model._data[row]['otype'] == LedgerTransaction.Transfer \
                           and model._data[row]['opart'] == Transfer.Fee
    proxy.hidden = transfer
    proxy.invalidate()
    links = _links(view, model)
    assert ((LedgerTransaction.Transfer, Transfer.Outgoing), _LEADS) in links    # the remaining two still meet
    assert ((LedgerTransaction.Transfer, Transfer.Incoming), (True, False, False)) in links


# Operations of one kind in one second list their parts one kind of part after another (A, B, A's fee, B's fee), so
# a fee may stand beside another operation's row. The numbers differ and nothing is tied - the rows read as they did
# before there were groups, instead of the fee being drawn under an operation it doesn't belong to.
def test_interleaved_parts_stay_apart(prepare_db_fifo):
    JalAccountCreator(currency_id=2, number='U2', name='Other', investing=1, organization=1).commit()
    create_stocks([('A', 'Asset A'), ('B', 'Asset B'), ('GAS', 'Native coin')], currency_id=2)
    second = d2t(220207)
    create_cross_chain_swaps([{'ts': second, 'acc': 1, 'out_asset': 4, 'out_qty': 1.0, 'hash': f'0x{x}',
                               'in_ts': d2t(220208), 'in_acc': 2, 'in_asset': 5, 'in_qty': 2.0,
                               'fee_asset': 6, 'fee_qty': 0.5} for x in ('a', 'b')])
    Ledger.refresh_sequence()
    view, model, _ = _table(d2t(220207))
    assert [x[0][1] for x in _links(view, model)[1:]] == [Swap.Outgoing, Swap.Outgoing, Swap.Fee, Swap.Fee]
    assert [x[1] for x in _links(view, model)] == [_ALONE] * 5


# The number of a broker statement groups as a hash does - the accrued interest paid with a bond sits above the
# trade that bought it. A blank number and the same number in another second never do.
def test_a_statement_number_groups_within_one_second(prepare_db_fifo):
    create_stocks([('BOND', 'A bond')], currency_id=2)
    create_coupons([(d2t(220301), 1, 4, -5.0, 0.0, '', '777')])
    create_trades(1, [(d2t(220301), d2t(220303), 4, 1.0, 100.0, 0.0, '777'),
                      (d2t(220302), d2t(220303), 4, 1.0, 100.0, 0.0, '777'),
                      (d2t(220304), d2t(220304), 4, 1.0, 100.0, 0.0, ''),
                      (d2t(220304), d2t(220304), 4, 2.0, 100.0, 0.0, ''),
                      (d2t(220305), d2t(220305), 4, 1.0, 100.0, 0.0, ' '),
                      (d2t(220305), d2t(220305), 4, 2.0, 100.0, 0.0, ' ')])
    Ledger.refresh_sequence()
    view, model, _ = _table(d2t(220401))
    T = LedgerTransaction
    assert _links(view, model) == [((T.IncomeSpending, 0), _ALONE),
                                   ((T.AssetPayment, 0), _LEADS), ((T.Trade, 0), (True, False, True))] \
        + [((T.Trade, 0), _ALONE)] * 5


# The group is drawn by hand in the first column; drawing it must hold for a selected and a plain row alike.
def test_a_group_is_painted(every_fee):
    view, model, _ = _table(d2t(220301))
    view.resize(900, 700)
    assert not view.grab().isNull()
    view.selectRow(4)   # the swap's fee - a tied row
    assert not view.grab().isNull()
    view.setEnabled(False)
    assert not view.grab().isNull()


# A quantity is stored in its canonical form, where a round number is spelled '3E+2' - so a row that prints one has
# to write it out. It reads as a quantity of a coin and never as a power of ten, whatever the number is.
def test_a_quantity_is_never_printed_in_exponent_form(drawn_rows):
    exponents = [f"{op.name()}: {cells[2]!r}" for op, cells in drawn_rows if "E+" in cells[2] or "E-" in cells[2]]
    assert exponents == []
    swap = [cells[2] for op, cells in drawn_rows
            if op.type() == LedgerTransaction.Swap and not op.is_fee_row()][0]
    assert swap.startswith("10 A -> 20 B")
    wrapping = [cells[2] for op, cells in drawn_rows
                if op.type() == LedgerTransaction.Conversion and not op.is_fee_row()][0]
    assert wrapping.startswith("10 A -> 10 B")


# Writing it out is not rounding it: a fraction keeps every digit it has, and a bridge that kept part of what it
# carried states the difference the same way.
def test_a_fractional_quantity_keeps_its_digits(prepare_db_fifo):
    JalAccountCreator(currency_id=2, number='U2', name='Other', investing=1, organization=1).commit()
    create_stocks([('A', 'Asset A'), ('B', 'Asset B')], currency_id=2)   # 4 and 5
    LedgerTransaction.create_new(LedgerTransaction.Conversion, {
        'timestamp': d2t(220202), 'account_id': 1, 'tx_hash': '0x1', 'out_symbol_id': 4,
        'out_qty': Decimal('0.5000'), 'in_symbol_id': 5, 'in_qty': Decimal('1234000'), 'note': ''})
    create_bridges([{'out_ts': d2t(220204), 'out_acc': 1, 'out_qty': 100.0, 'out_hash': '0x2',
                     'in_ts': d2t(220204), 'in_acc': 2, 'in_qty': 90.0, 'asset': 4}])
    Ledger.refresh_sequence()
    model = OperationsModel(QTableView())
    model.setDateRange(0, d2t(220301))
    texts = [model.data_text(LedgerTransaction.get_operation(x['otype'], x['oid'], x['opart']), 2)
             for x in model._data]
    assert any([x.startswith("0.5 A -> 1234000 B") for x in texts])
    assert any(["[" + LedgerTransaction.tr("In-kind fee:") + " 10 A]" in x for x in texts])
