# Tests of the ONE fee API - what an operation says about the fee it bears, independently of how that fee is stored.
# What a fee does to the ledger is the subject of test_asset_fee.py, test_swap.py, test_conversion.py and
# test_bridge.py; the shape of the row it draws is test_operation_rows.py.
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from collections import Counter
from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_fifo
from tests.helpers import d2t, create_stocks, create_trades, create_bridges, create_quotes, symbol_id_for, \
    nth_operation
from constants import PredefinedCategory
from jal.db.db import JalDB
from jal.db.asset import JalAsset
from jal.db.ledger import Ledger
from jal.db.account import JalAccountCreator
from jal.db.operations import LedgerTransaction, AssetPayment, FeeKind, Trade, Transfer, Conversion, Swap, Bridge


# Three accounts - 1 and 2 are the ends of the transfers below, 3 exists to bear a fee of a transfer that is
# neither of its legs - and two assets: 4 'A', the one that moves, and 5 'GAS', the coin the chains are paid in.
@pytest.fixture
def accounts_and_assets(prepare_db_fifo):
    JalAccountCreator(currency_id=2, number='U2', name='Other', investing=1, organization=1).commit()
    JalAccountCreator(currency_id=2, number='U3', name='Third', investing=1, organization=1).commit()
    create_stocks([('A', 'Asset A'), ('GAS', 'Native coin')], currency_id=2)   # asset ids 4 and 5
    yield


def _transfer(fee_account, fee, fee_symbol_id):
    return LedgerTransaction.create_new(LedgerTransaction.Transfer, {
        'withdrawal_timestamp': d2t(220203), 'withdrawal_account': 1, 'withdrawal': Decimal('5'),
        'deposit_timestamp': d2t(220203), 'deposit_account': 2, 'deposit': Decimal('5'),
        'symbol_id': symbol_id_for(4, 2), 'fee_account': fee_account, 'fee': fee, 'fee_symbol_id': fee_symbol_id})


# Every operation that can bear a fee states it the same way, whatever column it keeps it in
def test_every_carrier_states_its_fee(accounts_and_assets):
    gas = symbol_id_for(5, 2)
    create_trades(1, [(d2t(220101), d2t(220101), 4, 10.0, 100.0, 3.0)])
    swap = LedgerTransaction.create_new(LedgerTransaction.Swap, {
        'timestamp': d2t(220201), 'account_id': 1, 'tx_hash': '', 'out_symbol_id': symbol_id_for(4, 2),
        'out_qty': Decimal('10'), 'in_symbol_id': gas, 'in_qty': Decimal('20'),
        'fee_symbol_id': gas, 'fee_qty': Decimal('0.5'), 'note': ''})
    conversion = LedgerTransaction.create_new(LedgerTransaction.Conversion, {
        'timestamp': d2t(220202), 'account_id': 1, 'tx_hash': '', 'out_symbol_id': symbol_id_for(4, 2),
        'out_qty': Decimal('10'), 'in_symbol_id': gas, 'in_qty': Decimal('10'),
        'fee_symbol_id': gas, 'fee_qty': Decimal('0.25'), 'note': ''})
    transfer = _transfer(fee_account=1, fee=Decimal('0.125'), fee_symbol_id=gas)
    bridge_oid = create_bridges([{'out_ts': d2t(220204), 'out_acc': 1, 'out_qty': 5.0,
                                  'in_ts': d2t(220205), 'in_acc': 2, 'in_qty': 5.0, 'asset': 4,
                                  'fee_asset': 5, 'fee_qty': 0.0625}])[0]
    expected = [
        (nth_operation(LedgerTransaction.Trade, 1),                      Decimal('3'),      0,   1, FeeKind.Commission),
        (Swap(swap.oid()),              Decimal('0.5'),    gas, 1, FeeKind.Gas),
        (Conversion(conversion.oid()),  Decimal('0.25'),   gas, 1, FeeKind.Gas),
        (Transfer(transfer.oid()),      Decimal('0.125'),  gas, 1, FeeKind.Gas),
        (Bridge(bridge_oid),            Decimal('0.0625'), gas, 1, FeeKind.Gas)
    ]
    for operation, amount, symbol_id, account_id, kind in expected:
        where = type(operation).__name__
        assert len(operation.fees()) == 1, where
        fee = operation.fees()[0]
        assert fee.amount() == amount, where
        assert fee.symbol_id() == symbol_id, where
        assert fee.account_id() == account_id, where
        assert fee.kind() == kind, where
        assert fee.is_asset_fee() == bool(symbol_id), where
        assert operation.fee_symbol_id() == symbol_id, where
        assert operation.fee_account_id() == account_id, where


# The scalar rule: a deal absorbs one fee total in its own currency, and a fee paid in anything else is not part of
# the deal at all. fee() is that scalar, so it counts the money fees and leaves an asset-denominated one out.
def test_fee_scalar_counts_money_only(accounts_and_assets):
    money_fee = _transfer(fee_account=1, fee=Decimal('7'), fee_symbol_id=None)
    gas_fee = _transfer(fee_account=1, fee=Decimal('0.5'), fee_symbol_id=symbol_id_for(5, 2))
    create_trades(1, [(d2t(220101), d2t(220101), 4, 10.0, 100.0, 3.0)])
    assert Transfer(money_fee.oid()).fee() == Decimal('7')
    assert Transfer(gas_fee.oid()).fee() == Decimal('0')       # an expense at basis, never a component of the deal
    assert Transfer(gas_fee.oid()).fees()[0].amount() == Decimal('0.5')   # ... but the fee itself is still there
    assert nth_operation(LedgerTransaction.Trade, 1).fee() == Decimal('3')


# A fee carries its own account: a transfer may be charged on the sending leg, on the receiving one, or on neither
def test_a_fee_names_the_account_that_bore_it(accounts_and_assets):
    for account_id in (1, 2, 3):
        transfer = Transfer(_transfer(fee_account=account_id, fee=Decimal('1'), fee_symbol_id=None).oid())
        assert transfer.fees()[0].account_id() == account_id
        assert transfer.fee_account_id() == account_id


# An operation that carries no fee has no fee to state, and its accessors say so rather than raising
def test_an_operation_without_a_fee(accounts_and_assets):
    create_trades(1, [(d2t(220101), d2t(220101), 4, 10.0, 100.0, 0.0)])
    trade = nth_operation(LedgerTransaction.Trade, 1)
    assert trade.fees() == []
    assert trade.fee() == Decimal('0')
    assert trade.fee_symbol_id() == 0
    assert not trade.is_fee_row()


# The fee row predicate is the same test for every carrier - the part the operation is drawn as
def test_is_fee_row_is_the_fee_part(accounts_and_assets):
    transfer = _transfer(fee_account=1, fee=Decimal('1'), fee_symbol_id=None)
    assert Transfer(transfer.oid(), Transfer.Fee).is_fee_row()
    assert not Transfer(transfer.oid(), Transfer.Outgoing).is_fee_row()
    assert not Transfer(transfer.oid(), Transfer.Incoming).is_fee_row()


# One of every fee-bearing operation, with a tagged gas coin, and the ledger built from them.
@pytest.fixture
def ledger_with_every_fee(accounts_and_assets):
    gas, asset = symbol_id_for(5, 2), symbol_id_for(4, 2)
    JalAsset(5).set_tag(JalDB._read("SELECT id FROM tags WHERE tag='Cash'"))   # the gas coin ...
    JalAsset(4).set_tag(JalDB._read("SELECT id FROM tags WHERE tag='Card'"))   # ... and the asset being moved
    create_quotes(4, 2, [(d2t(220201), 150.0)])
    create_trades(1, [(d2t(220101), d2t(220101), 4, 100.0, 100.0, 3.0)])   # a trade with a fee of its own
    create_trades(1, [(d2t(220101), d2t(220101), 5, 10.0, 10.0, 0.0)])     # the gas coin to pay the rest with
    LedgerTransaction.create_new(LedgerTransaction.Swap, {
        'timestamp': d2t(220201), 'account_id': 1, 'tx_hash': '', 'out_symbol_id': asset,
        'out_qty': Decimal('10'), 'in_symbol_id': gas, 'in_qty': Decimal('20'),
        'fee_symbol_id': gas, 'fee_qty': Decimal('0.5'), 'note': ''})
    LedgerTransaction.create_new(LedgerTransaction.Conversion, {
        'timestamp': d2t(220202), 'account_id': 1, 'tx_hash': '', 'out_symbol_id': asset,
        'out_qty': Decimal('10'), 'in_symbol_id': gas, 'in_qty': Decimal('10'), 'note': '',
        'fee_symbol_id': gas, 'fee_qty': Decimal('0.25')})
    _transfer(fee_account=1, fee=Decimal('0.1'), fee_symbol_id=gas)
    create_bridges([{'out_ts': d2t(220204), 'out_acc': 1, 'out_qty': 5.0,          # gas only
                     'in_ts': d2t(220205), 'in_acc': 2, 'in_qty': 5.0, 'asset': 4,
                     'fee_asset': 5, 'fee_qty': 0.05}])
    create_bridges([{'out_ts': d2t(220206), 'out_acc': 1, 'out_qty': 5.0,          # ... and an in-kind fee as well
                     'in_ts': d2t(220207), 'in_acc': 2, 'in_qty': 4.0, 'asset': 4,
                     'fee_asset': 5, 'fee_qty': 0.05}])
    LedgerTransaction.create_new(LedgerTransaction.AssetPayment,
                                 {'timestamp': d2t(220208), 'type': AssetPayment.GasFee, 'account_id': 1,
                                  'symbol_id': gas, 'amount': '0.5', 'tax': '0', 'number': '', 'note': ''})
    Ledger().rebuild(from_timestamp=0)
    yield


# The part a fee is POSTED into is the part the operation is DRAWN as, because the ledger keeps that number and the
# by-category/by-tag/by-counterparty reports rebuild the operation from it (reports/operations_base.py). When the two
# disagreed a bridge fee raised on the assert of its own constructor and a conversion fee came back as the whole
# conversion, telling the reader the amount of the conversion instead of the amount of the gas.
def test_every_fee_posting_rebuilds_as_the_fee_it_is(ledger_with_every_fee):
    postings = Ledger.get_operations_by_category(0, d2t(230101), PredefinedCategory.Fees)
    assert len(postings) == 8      # a trade, a swap, a conversion, a transfer, 2 bridges + 1 in-kind, a gas payment
    # What each of them must say it took: the quantity of the FEE, never the amount of the operation it belonged to
    expected = {(LedgerTransaction.Swap, True): [Decimal('-0.5')],
                (LedgerTransaction.Conversion, True): [Decimal('-0.25')],
                (LedgerTransaction.Transfer, True): [Decimal('-0.1')],
                (LedgerTransaction.Bridge, True): [Decimal('-0.05'), Decimal('-1')],   # gas, and the in-kind fee
                (LedgerTransaction.Trade, False): None,          # a trade's fee is inside the deal it paid for
                (LedgerTransaction.AssetPayment, False): None}   # a stand-alone gas payment IS the operation
    seen = {}
    for posting in postings:
        operation = LedgerTransaction().get_operation(posting['otype'], posting['oid'], posting['opart'])
        key = (operation.type(), operation.is_fee_row())
        assert key in expected, operation.name()
        if expected[key] is not None:
            seen.setdefault(key, set()).update(operation.value_change(part_only=True))
    assert set(seen) | {k for k, v in expected.items() if v is None} == set(expected)
    for key, amounts in seen.items():
        assert amounts == set(expected[key]), str(key)


# Every fee paid in an asset reaches the ledger tagged with that asset's tag. Four of the five routines that used to
# book them disagreed about it, so a tag-based report counted some gas and not the rest.
def test_a_fee_carries_the_tag_of_the_asset_it_was_paid_in(ledger_with_every_fee):
    coin = JalDB._read("SELECT id FROM tags WHERE tag='Cash'")     # the tag of the gas coin
    moved = JalDB._read("SELECT id FROM tags WHERE tag='Card'")    # the tag of the asset the operations move
    postings = Ledger.get_operations_by_category(0, d2t(230101), PredefinedCategory.Fees)
    assert len(postings) == 8
    tagged = Counter()
    for posting in postings:
        operation = LedgerTransaction().get_operation(posting['otype'], posting['oid'], posting['opart'])
        assert posting['tag_id'] != '', operation.name()           # no fee reaches the ledger untagged
        tagged[(operation.type(), operation.is_fee_row(), int(posting['tag_id']))] += 1
    # The five gas charges name the coin they burned; a trade's fee and a bridge's in-kind fee are taken out of the
    # asset the operation itself deals in and name that one.
    assert tagged == Counter({(LedgerTransaction.Trade, False, moved): 1,
                              (LedgerTransaction.Swap, True, coin): 1,
                              (LedgerTransaction.Conversion, True, coin): 1,
                              (LedgerTransaction.Transfer, True, coin): 1,
                              (LedgerTransaction.Bridge, True, coin): 2,
                              (LedgerTransaction.Bridge, True, moved): 1,
                              (LedgerTransaction.AssetPayment, False, coin): 1})
