# Tests of the SHAPE of the rows the operations table draws - how many lines a row is and what stands on them.
# What is booked by those operations is the subject of test_swap.py, test_conversion.py, test_bridge.py and
# test_asset_fee.py; nothing is asked of the ledger here beyond the balances the rows print.
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from decimal import Decimal

from PySide6.QtWidgets import QTableView

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_fifo
from tests.helpers import d2t, create_stocks, create_trades, create_quotes, create_bridges
from jal.db.ledger import Ledger
from jal.db.account import JalAccountCreator
from jal.db.operations import LedgerTransaction, AssetPayment
from jal.db.operations_model import OperationsModel


# One of every operation that has a fee part, each carrying a transaction hash, plus a stand-alone gas payment.
def _ledger_with_every_fee(gas_symbol=6, asset=4):
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
    LedgerTransaction.create_new(LedgerTransaction.AssetPayment,
                                 {'timestamp': d2t(220206), 'type': AssetPayment.GasFee, 'account_id': 1,
                                  'symbol_id': gas_symbol, 'amount': '0.5', 'tax': '0',
                                  'number': '0xstandalone', 'note': ''})


def _drawn_rows(end=d2t(220301)) -> list:
    model = OperationsModel(QTableView())
    model.setDateRange(0, end)
    rows = []
    for row in range(model.rowCount()):
        odata = model._data[row]
        operation = LedgerTransaction.get_operation(odata['otype'], odata['oid'], odata['opart'])
        rows.append((operation, [model.data_text(operation, column) for column in range(3)]))
    return rows


# A fee is not a transaction of its own - the operation it belongs to names the transaction on the row right above -
# so a fee row prints no hash under its timestamp. It is a rule for the whole family: a transfer, a bridge, a swap
# and a conversion all draw their fee the same way, one line tall and telling only the account it was paid from.
def test_a_fee_row_names_no_transaction(prepare_db_fifo):
    JalAccountCreator(currency_id=2, number='U2', name='Other', investing=1, organization=1).commit()
    create_stocks([('A', 'Asset A'), ('B', 'Asset B'), ('GAS', 'Native coin')], currency_id=2)  # 4, 5 and 6
    create_quotes(4, 2, [(d2t(220201), 150.0)])
    _ledger_with_every_fee()
    Ledger().rebuild(from_timestamp=0)

    fee_rows = [(op, cells) for op, cells in _drawn_rows() if op.is_fee_row()]
    assert [op.type() for op, _ in fee_rows] == [LedgerTransaction.Swap, LedgerTransaction.Conversion,
                                                 LedgerTransaction.Transfer, LedgerTransaction.Bridge]
    for operation, (timestamp, account, description) in fee_rows:
        where = operation.name()
        assert operation.number() == '', where          # the hash belongs to the transaction, not to its gas
        assert "\n" not in timestamp, where
        assert "\n" not in account, where               # ... and neither does the asset name: 1 line, 1 row
        assert operation.view_rows() == 1, where
        assert description.endswith("fee"), where


# Every column of a row is drawn inside the height the operation asked for, so a column that writes more lines than
# view_rows() has its tail cut off - invisibly, since nothing marks the row as truncated. The check is worth having
# for the whole list: the two asset legs of a bridge reserved one line while naming a transaction and an asset.
def test_no_row_writes_more_lines_than_it_reserved(prepare_db_fifo):
    JalAccountCreator(currency_id=2, number='U2', name='Other', investing=1, organization=1).commit()
    create_stocks([('A', 'Asset A'), ('B', 'Asset B'), ('GAS', 'Native coin')], currency_id=2)
    create_quotes(4, 2, [(d2t(220201), 150.0)])
    _ledger_with_every_fee()
    Ledger().rebuild(from_timestamp=0)

    clipped = []
    for operation, cells in _drawn_rows():
        lines = max([len(str(cell).split("\n")) for cell in cells]
                    + [len(operation.value_change()), len(operation.value_total())])
        if lines > operation.view_rows():
            clipped.append(f"{operation.name()}: {lines} lines in {operation.view_rows()} row(s)")
    assert clipped == []


# The scope of that rule is a fee PART. A stand-alone gas payment is an operation in its own right and the hash is
# the only thing that identifies it, so it keeps it.
def test_a_stand_alone_gas_payment_keeps_its_hash(prepare_db_fifo):
    JalAccountCreator(currency_id=2, number='U2', name='Other', investing=1, organization=1).commit()
    create_stocks([('A', 'Asset A'), ('B', 'Asset B'), ('GAS', 'Native coin')], currency_id=2)
    create_quotes(4, 2, [(d2t(220201), 150.0)])
    _ledger_with_every_fee()
    Ledger().rebuild(from_timestamp=0)

    gas = [(op, cells) for op, cells in _drawn_rows() if op.subtype() == AssetPayment.GasFee]
    assert len(gas) == 1
    operation, (timestamp, _account, _description) = gas[0]
    assert not operation.is_fee_row()
    assert operation.number() == '0xstandalone'
    assert timestamp.endswith("\n# 0xstandalone")
