# Tests of the 'fees' table - the place a fee is stored, independently of what an operation says about it (that is
# test_fee_api.py) and of what it does to the ledger (test_asset_fee.py and the per-operation files).
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from decimal import Decimal

import sqlparse

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_fifo
from tests.helpers import d2t, create_stocks, create_trades, create_bridges, create_quotes, \
    symbol_id_for, operation_id
from constants import Setup
from jal.db.db import JalDB
from jal.db.account import JalAccountCreator
from jal.db.ledger import Ledger
from jal.db.operations import LedgerTransaction


# Two accounts - the ends of the transfers below - and two assets: 4 'A', the one that moves, and 5 'GAS', the coin
# the chains are paid in.
def _accounts_and_assets():
    JalAccountCreator(currency_id=2, number='U2', name='Other', investing=1, organization=1).commit()
    create_stocks([('A', 'Asset A'), ('GAS', 'Native coin')], currency_id=2)   # asset ids 4 and 5


# One operation of every fee-bearing kind, at moments far enough apart to tell which of them a wipe started from.
def _operations_with_fees():
    _accounts_and_assets()
    gas, asset = symbol_id_for(5, 2), symbol_id_for(4, 2)
    for asset_id in (4, 5):        # the swap and the conversion have to be valued to reach the ledger at all
        create_quotes(asset_id, 2, [(d2t(220101), 100.0), (d2t(220301), 100.0), (d2t(220401), 100.0)])
    create_trades(1, [(d2t(220101), d2t(220101), 5, 100.0, 1.0, 0.0)])         # the gas coin to pay the rest with
    create_trades(1, [(d2t(220201), d2t(220201), 4, 10.0, 100.0, 3.0)])        # money fee
    LedgerTransaction.create_new(LedgerTransaction.Swap, {
        'timestamp': d2t(220301), 'account_id': 1, 'tx_hash': '', 'out_symbol_id': asset,
        'out_qty': Decimal('1'), 'in_symbol_id': gas, 'in_qty': Decimal('2'),
        'fee_symbol_id': gas, 'fee_qty': Decimal('0.5'), 'note': ''})
    LedgerTransaction.create_new(LedgerTransaction.Conversion, {
        'timestamp': d2t(220401), 'account_id': 1, 'tx_hash': '', 'out_symbol_id': asset,
        'out_qty': Decimal('1'), 'in_symbol_id': gas, 'in_qty': Decimal('1'),
        'fee_symbol_id': gas, 'fee_qty': Decimal('0.25'), 'note': ''})
    LedgerTransaction.create_new(LedgerTransaction.Transfer, {                 # withdrawn and deposited days apart
        'withdrawal_timestamp': d2t(220501), 'withdrawal_account': 1, 'withdrawal': Decimal('5'),
        'deposit_timestamp': d2t(220505), 'deposit_account': 2, 'deposit': Decimal('5'),
        'symbol_id': asset, 'fee_account': 1, 'fee': Decimal('0.125'), 'fee_symbol_id': gas})
    create_bridges([{'out_ts': d2t(220601), 'out_acc': 1, 'out_qty': 1.0,
                     'in_ts': d2t(220605), 'in_acc': 2, 'in_qty': 1.0, 'asset': 4,
                     'fee_asset': 5, 'fee_qty': 0.0625}])


def _add_fee(operation_id_value: int, amount='1', account_id=1, symbol_id=None, idx=0, kind=0) -> int:
    query = JalDB._exec("INSERT INTO fees (operation_id, idx, account_id, symbol_id, amount, kind) "
                        "VALUES (:oid, :idx, :account, :symbol, :amount, :kind)",
                        [(":oid", operation_id_value), (":idx", idx), (":account", account_id),
                         (":symbol", symbol_id), (":amount", amount), (":kind", kind)], commit=True)
    return query.lastInsertId()


def _ledger_after(timestamp: int) -> int:
    return JalDB._read("SELECT COUNT(*) FROM ledger WHERE timestamp >= :ts", [(":ts", timestamp)])


# ----------------------------------------------------------------------------------------------------------------------
# The table is a child of the operations root, so it is reached by every path an operation can leave by - not only by
# its own deletion. Both of those paths are below.
def test_a_deleted_operation_takes_its_fees_with_it(prepare_db_fifo):
    _operations_with_fees()
    oid = operation_id(LedgerTransaction.Trade, 2)
    for idx in (0, 1):
        _add_fee(oid, idx=idx)
    assert JalDB._read("SELECT COUNT(*) FROM fees") == 2

    LedgerTransaction.get_operation(LedgerTransaction.Trade, oid).delete()

    assert JalDB._read("SELECT COUNT(*) FROM fees") == 0


# An account takes its operations with it by foreign key, without any operation ever being deleted by name - which is
# the reason the root row is cleaned from the type row and not the other way round
def test_a_deleted_account_takes_the_fees_of_its_operations(prepare_db_fifo):
    _operations_with_fees()
    _add_fee(operation_id(LedgerTransaction.Trade, 2))
    _add_fee(operation_id(LedgerTransaction.Swap))
    assert JalDB._read("SELECT COUNT(*) FROM fees") == 2

    JalDB._exec("DELETE FROM accounts WHERE id=1", commit=True)

    assert JalDB._read("SELECT COUNT(*) FROM fees") == 0


# A fee row may name an account that is neither leg of its operation, and that account going takes the fee with it
def test_a_deleted_fee_account_takes_the_fee_with_it(prepare_db_fifo):
    _operations_with_fees()
    _add_fee(operation_id(LedgerTransaction.Trade, 2), account_id=2)

    JalDB._exec("DELETE FROM accounts WHERE id=2", commit=True)

    assert JalDB._read("SELECT COUNT(*) FROM fees") == 0


# ----------------------------------------------------------------------------------------------------------------------
# A fee changes the ledger as much as the operation bearing it does. If it could be written without invalidating the
# ledger, the balance would simply stay wrong and nothing would look amiss.
def test_a_new_fee_invalidates_the_ledger_from_its_operation(prepare_db_fifo):
    _operations_with_fees()
    Ledger().rebuild(from_timestamp=0)
    assert _ledger_after(0) > 0
    before, after = _ledger_after(d2t(220101)), _ledger_after(d2t(220301))
    assert before > after > 0

    _add_fee(operation_id(LedgerTransaction.Swap))       # the swap of 22-03-01

    assert _ledger_after(d2t(220301)) == 0               # everything from the swap on is gone ...
    assert _ledger_after(d2t(220101)) == before - after  # ... and nothing before it


def test_an_edited_fee_invalidates_the_ledger_from_its_operation(prepare_db_fifo):
    _operations_with_fees()
    fee_id = _add_fee(operation_id(LedgerTransaction.Swap))
    Ledger().rebuild(from_timestamp=0)
    kept = _ledger_after(d2t(220101)) - _ledger_after(d2t(220301))

    JalDB._exec("UPDATE fees SET amount='2' WHERE id=:id", [(":id", fee_id)], commit=True)

    assert _ledger_after(d2t(220301)) == 0
    assert _ledger_after(d2t(220101)) == kept


def test_a_removed_fee_invalidates_the_ledger_from_its_operation(prepare_db_fifo):
    _operations_with_fees()
    fee_id = _add_fee(operation_id(LedgerTransaction.Swap))
    Ledger().rebuild(from_timestamp=0)
    kept = _ledger_after(d2t(220101)) - _ledger_after(d2t(220301))

    JalDB._exec("DELETE FROM fees WHERE id=:id", [(":id", fee_id)], commit=True)

    assert _ledger_after(d2t(220301)) == 0
    assert _ledger_after(d2t(220101)) == kept


# A transfer and a bridge have two moments each and the EARLIER one governs the wipe - the fee is borne when the
# operation starts, and the ledger from that point on is what it changes.
def test_a_fee_of_a_two_legged_operation_wipes_from_its_earlier_leg(prepare_db_fifo):
    _operations_with_fees()
    Ledger().rebuild(from_timestamp=0)
    kept = _ledger_after(d2t(220101)) - _ledger_after(d2t(220501))

    _add_fee(operation_id(LedgerTransaction.Transfer))   # withdrawn 22-05-01, deposited 22-05-05

    assert _ledger_after(d2t(220501)) == 0               # from the withdrawal, not from the deposit
    assert _ledger_after(d2t(220101)) == kept


# SQLite's MIN() of several arguments is NULL if ANY of them is, so a transfer with one leg only would answer the
# lookup with NULL - and 'timestamp >= NULL' is never true, which would be a fee that quietly changes nothing.
def test_a_fee_of_a_one_legged_operation_still_invalidates_the_ledger(prepare_db_fifo):
    _operations_with_fees()
    pending = create_bridges([{'out_ts': d2t(220701), 'out_acc': 1, 'out_qty': 1.0, 'asset': 4}])[0]
    Ledger().rebuild(from_timestamp=0)
    assert _ledger_after(d2t(220701)) > 0

    _add_fee(pending)

    assert _ledger_after(d2t(220701)) == 0


# The open lots go with the ledger: four of the five operations that can bear a fee open FIFO positions, and a fee
# left in 'trades_opened' would be consumed by a later deal that no longer paid for it.
def test_a_fee_invalidates_the_open_lots_as_well(prepare_db_fifo):
    _operations_with_fees()
    Ledger().rebuild(from_timestamp=0)
    assert JalDB._read("SELECT COUNT(*) FROM trades_opened WHERE timestamp >= :ts", [(":ts", d2t(220201))]) > 0

    _add_fee(operation_id(LedgerTransaction.Trade, 2))   # the trade of 22-02-01

    assert JalDB._read("SELECT COUNT(*) FROM trades_opened WHERE timestamp >= :ts", [(":ts", d2t(220201))]) == 0


# ----------------------------------------------------------------------------------------------------------------------
# The delta fills the root's moment for every operation that already exists, and from then on the sixteen triggers
# keep it. The fill is run from the shipped file rather than copied here, so this breaks if it stops doing what it says.
_MIGRATION_DELTA = 73
_MIGRATION_FROM = "-- AN OPERATION REMEMBERS WHEN IT HAPPENS"
_MIGRATION_TO = "-- THE MOMENT FOLLOWS ITS TYPE ROW"


def _replay_the_fill(project_root):
    with open(project_root + f"/jal/updates/{Setup.UPDATE_PREFIX}{_MIGRATION_DELTA}.sql") as delta:
        text = delta.read()
    start, end = text.index(_MIGRATION_FROM), text.index(_MIGRATION_TO)
    for statement in sqlparse.split(text[start:end]):
        stripped = sqlparse.format(statement, strip_comments=True).strip()
        if not stripped or stripped.startswith("ALTER TABLE"):
            continue   # a run of comment lines is not a statement, and the column is already there
        assert JalDB._exec(stripped) is not None, f"Migration statement failed: {statement}"
    JalDB().commit()


# The sixteen triggers are re-stated by the delta, so a replay of that section has to be a no-op on a database that
# already carries them - which is what makes the section safe to sit in front of the ledger.
def _replay_the_triggers(project_root):
    with open(project_root + f"/jal/updates/{Setup.UPDATE_PREFIX}{_MIGRATION_DELTA}.sql") as delta:
        text = delta.read()
    start, end = text.index(_MIGRATION_TO), text.index("-- A FEE GETS A TABLE OF ITS OWN")
    for statement in sqlparse.split(text[start:end]):
        stripped = sqlparse.format(statement, strip_comments=True).strip()
        if not stripped:
            continue
        assert JalDB._exec(stripped) is not None, f"Migration statement failed: {statement}"
    JalDB().commit()


# Nothing this delta does touches the ledger: it adds a column, fills it from data the ledger was already built
# from, and re-states sixteen triggers. That is why it ships without asking for a rebuild - and if it ever stopped
# being true, a user would be told the ledger is current when it is not.
def test_the_delta_leaves_the_ledger_alone(prepare_db_fifo, project_root):
    _operations_with_fees()
    Ledger().rebuild(from_timestamp=0)
    ledger = JalDB._read_to_list("SELECT * FROM ledger ORDER BY id")
    closed = JalDB._read_to_list("SELECT * FROM trades_closed ORDER BY rowid")
    assert ledger and closed

    _replay_the_fill(project_root)
    _replay_the_triggers(project_root)

    assert JalDB._read_to_list("SELECT * FROM ledger ORDER BY id") == ledger
    assert JalDB._read_to_list("SELECT * FROM trades_closed ORDER BY rowid") == closed


def test_the_migration_fills_the_moment_of_every_stored_operation(prepare_db_fifo, project_root):
    _operations_with_fees()
    expected = JalDB._read_to_list("SELECT id, timestamp FROM operations ORDER BY id")
    JalDB._exec("UPDATE operations SET timestamp = 0", commit=True)   # the state the delta finds the column in

    _replay_the_fill(project_root)

    assert JalDB._read_to_list("SELECT id, timestamp FROM operations ORDER BY id") == expected
    assert JalDB._read("SELECT COUNT(*) FROM operations WHERE timestamp = 0") == 0


# ----------------------------------------------------------------------------------------------------------------------
# Every object this delta declares is written twice - once for a database created from scratch and once for one being
# upgraded - and nothing else in the suite would notice the two drifting apart.
def _created_objects(text: str) -> dict:
    objects = {}
    for statement in sqlparse.split(text):
        stripped = sqlparse.format(statement, strip_comments=True).strip()
        for kind in ("CREATE TABLE", "CREATE INDEX", "CREATE TRIGGER"):
            if stripped.startswith(kind):
                objects[stripped[len(kind):].strip().split()[0]] = stripped
    return objects


def test_the_delta_and_the_init_script_declare_the_same_objects(project_root):
    with open(project_root + "/jal/" + Setup.INIT_SCRIPT_PATH) as init:
        from_init = _created_objects(init.read())
    with open(project_root + f"/jal/updates/{Setup.UPDATE_PREFIX}{Setup.DB_REQUIRED_VERSION}.sql") as delta:
        from_delta = _created_objects(delta.read())

    assert len(from_delta) == 21     # the table, its index, and nineteen triggers
    for name, declaration in from_delta.items():
        assert name in from_init, f"{name} is created by the delta and by nothing else"
        assert declaration == from_init[name], name
