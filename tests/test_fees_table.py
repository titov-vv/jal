# Tests of the 'fees' table - the place a fee is stored, independently of what an operation says about it (that is
# test_fee_api.py) and of what it does to the ledger (test_asset_fee.py and the per-operation files).
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from decimal import Decimal

import sqlparse

from PySide6.QtWidgets import QWidget

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_fifo
from tests.helpers import d2t, create_stocks, create_trades, create_transfers, create_bridges, \
    create_quotes, symbol_id_for, operation_id
from constants import Setup
from jal.db.db import JalDB
from jal.db.account import JalAccountCreator
from jal.db.ledger import Ledger
from jal.widgets.trade_widget import TradeWidget
from jal.db.operations import LedgerTransaction, Transfer, FeeKind


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


def _fees_of(operation_id_value: int) -> int:
    return JalDB._read("SELECT COUNT(*) FROM fees WHERE operation_id=:oid", [(":oid", operation_id_value)])


def _ledger_after(timestamp: int) -> int:
    return JalDB._read("SELECT COUNT(*) FROM ledger WHERE timestamp >= :ts", [(":ts", timestamp)])


# ----------------------------------------------------------------------------------------------------------------------
# The table is a child of the operations root, so it is reached by every path an operation can leave by - not only by
# its own deletion. Both of those paths are below.
def test_a_deleted_operation_takes_its_fees_with_it(prepare_db_fifo):
    _operations_with_fees()
    oid = operation_id(LedgerTransaction.Trade, 2)
    _add_fee(oid, idx=1)            # a second fee, beside the one the trade's own column already mirrors
    assert _fees_of(oid) == 2

    LedgerTransaction.get_operation(LedgerTransaction.Trade, oid).delete()

    assert _fees_of(oid) == 0


# An account takes its operations with it by foreign key, without any operation ever being deleted by name - which is
# the reason the root row is cleaned from the type row and not the other way round
def test_a_deleted_account_takes_the_fees_of_its_operations(prepare_db_fifo):
    _operations_with_fees()
    assert JalDB._read("SELECT COUNT(*) FROM fees") > 0

    JalDB._exec("DELETE FROM accounts WHERE id=1", commit=True)   # every operation of the fixture runs through it

    assert JalDB._read("SELECT COUNT(*) FROM fees") == 0


# A fee row may name an account that is neither leg of its operation, and that account going takes the fee with it
def test_a_deleted_fee_account_takes_the_fee_with_it(prepare_db_fifo):
    _operations_with_fees()
    oid = operation_id(LedgerTransaction.Trade, 2)                # a trade on account 1 ...
    fee_id = _add_fee(oid, account_id=2, idx=1)                   # ... charged to account 2
    assert _fees_of(oid) == 2

    JalDB._exec("DELETE FROM accounts WHERE id=2", commit=True)

    assert JalDB._read("SELECT COUNT(*) FROM fees WHERE id=:id", [(":id", fee_id)]) == 0
    assert _fees_of(oid) == 1                                     # the trade itself belongs to account 1 and stays


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


# The populate, replayed the same way. It sits between the table and the triggers in the delta and the order is
# load-bearing, which is what the ledger test below actually checks.
_POPULATE_FROM = "-- THE FEES THAT ARE ALREADY STORED"
_POPULATE_TO = "-- A FEE EDIT MUST INVALIDATE THE LEDGER"


def _replay_the_populate(project_root):
    with open(project_root + f"/jal/updates/{Setup.UPDATE_PREFIX}{_MIGRATION_DELTA}.sql") as delta:
        text = delta.read()
    start, end = text.index(_POPULATE_FROM), text.index(_POPULATE_TO)
    # The state the LEDGER is in when the delta runs this: the populate comes before the section that creates these,
    # so six thousand inserts pass without one of them clearing the ledger. A replay that left them in place would be
    # replaying a different migration - and the ordering itself is pinned by its own test below. They go first,
    # because emptying the table would otherwise clear the ledger before a single row had been written.
    for event in ('insert', 'update', 'delete'):
        JalDB._exec(f"DROP TRIGGER IF EXISTS fees_after_{event}")
    JalDB._exec("DELETE FROM fees", commit=True)   # the state the delta finds the table in
    for statement in sqlparse.split(text[start:end]):
        stripped = sqlparse.format(statement, strip_comments=True).strip()
        if not stripped:
            continue
        assert JalDB._exec(stripped) is not None, f"Migration statement failed: {statement}"
    JalDB().commit()


# What every stored fee has to become. The parity these assertions state is the bar of the stage: the fee row and the
# columns it was copied from must say the same thing, down to the spelling of the amount.
_PARITY = {
    'trades':      "SELECT oid, account_id, NULL, fee FROM trades WHERE CAST(fee AS REAL) <> 0",
    'transfers':   "SELECT oid, COALESCE(fee_account, withdrawal_account, deposit_account), fee_symbol_id, fee "
                   "FROM transfers WHERE CAST(fee AS REAL) <> 0",
    'conversions': "SELECT oid, account_id, fee_symbol_id, fee_qty FROM conversions WHERE CAST(fee_qty AS REAL) <> 0",
    'swaps':       "SELECT oid, account_id, fee_symbol_id, fee_qty FROM swaps WHERE CAST(fee_qty AS REAL) <> 0",
    'bridges':     "SELECT oid, out_account_id, fee_symbol_id, fee_qty FROM bridges WHERE CAST(fee_qty AS REAL) <> 0",
}


def _sources() -> list:
    rows = []
    for query in _PARITY.values():
        rows += JalDB._read_to_list(query)
    return sorted(rows)


def _stored_fees() -> list:
    return sorted(JalDB._read_to_list("SELECT operation_id, account_id, symbol_id, amount FROM fees WHERE idx = 0"))


def test_the_migration_moves_every_stored_fee(prepare_db_fifo, project_root):
    _operations_with_fees()
    _replay_the_populate(project_root)

    assert JalDB._read("SELECT COUNT(*) FROM fees") == 5    # a trade, a swap, a conversion, a transfer, a bridge
    assert _stored_fees() == _sources()
    assert JalDB._read("SELECT COUNT(*) FROM fees WHERE idx <> 0") == 0


# A fee paid in money is a commission and one denominated in an asset is gas. For a transfer that is a reading of the
# data and not a fact in it, which is the one place a finer 'kind' set would first be wrong.
def test_the_migration_tells_a_commission_from_gas(prepare_db_fifo, project_root):
    _operations_with_fees()
    _replay_the_populate(project_root)

    kinds = dict(JalDB._read_to_list("SELECT kind, COUNT(*) FROM fees GROUP BY kind"))
    assert kinds == {FeeKind.Commission: 1, FeeKind.Gas: 4}   # the trade pays in money, the other four in the coin
    assert JalDB._read("SELECT COUNT(*) FROM fees WHERE (symbol_id IS NULL) <> (kind = :money)",
                       [(":money", FeeKind.Commission)]) == 0


# The zero test is numeric. 'trades.fee' is NOT NULL DEFAULT ('0') and its zeros are spelled several ways, so a
# textual filter migrates fees that are not fees - 337 of them on the live ledger.
def test_a_fee_that_is_zero_however_it_is_spelled_migrates_nothing(prepare_db_fifo, project_root):
    _operations_with_fees()
    for spelling in ('0', '0.0', '0.00', ''):
        create_trades(1, [(d2t(220102), d2t(220102), 4, 1.0, 100.0, 0.0)])
        JalDB._exec("UPDATE trades SET fee=:fee WHERE oid=:oid",
                    [(":fee", spelling), (":oid", JalDB._read("SELECT MAX(oid) FROM trades"))], commit=True)

    _replay_the_populate(project_root)

    assert JalDB._read("SELECT COUNT(*) FROM fees") == 5     # the same five, and not one of the four zeros


# The amount is carried over exactly as it is stored. Canonicalising it here would make the parity above unable to
# tell a migration bug from a change of spelling.
def test_the_migration_copies_the_amount_verbatim(prepare_db_fifo, project_root):
    _operations_with_fees()
    oid = operation_id(LedgerTransaction.Trade, 2)
    JalDB._exec("UPDATE trades SET fee='3.1400' WHERE oid=:oid", [(":oid", oid)], commit=True)

    _replay_the_populate(project_root)

    assert JalDB._read("SELECT amount FROM fees WHERE operation_id=:oid", [(":oid", oid)]) == '3.1400'


# The populate has to come before the triggers are created, and nothing but the order of the file says so. Move the
# section down and every one of six thousand inserts clears the ledger from its operation's moment - the delta would
# still be correct, and it would leave the user with an empty ledger and no word about it.
def test_the_delta_populates_before_it_creates_the_fee_triggers(project_root):
    with open(project_root + f"/jal/updates/{Setup.UPDATE_PREFIX}{_MIGRATION_DELTA}.sql") as delta:
        text = delta.read()

    assert text.index("CREATE TABLE fees") < text.index(_POPULATE_FROM) < text.index("CREATE TRIGGER fees_after_insert")


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
    _replay_the_populate(project_root)
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

    assert len(from_delta) == 31     # the table, its index, and twenty-nine triggers
    for name, declaration in from_delta.items():
        assert name in from_init, f"{name} is created by the delta and by nothing else"
        assert declaration == from_init[name], name


# ----------------------------------------------------------------------------------------------------------------------
# The second copy. Until the fee columns are dropped, the parent column is what the application writes and 'fees'
# follows it - written by nothing but the ten mirror triggers. What these tests watch is that the copy is complete
# whichever of the eight write paths a fee arrives by, because from the stage that makes the ledger sequence read
# 'fees' a fee missing from the table is a fee missing from the ledger.
def test_every_kind_of_operation_mirrors_its_fee(prepare_db_fifo):
    _operations_with_fees()

    assert JalDB._read("SELECT COUNT(*) FROM fees") == 5    # a trade, a swap, a conversion, a transfer, a bridge
    assert _stored_fees() == _sources()


# The migration and the mirror have to say the same thing, or the parity between them would mean nothing. This is the
# one test that compares the two directly - the same operations, stored once by each.
def test_the_mirror_writes_what_the_migration_would_have(prepare_db_fifo, project_root):
    _operations_with_fees()
    mirrored = JalDB._read_to_list("SELECT operation_id, idx, account_id, symbol_id, amount, kind FROM fees "
                                   "ORDER BY operation_id")

    _replay_the_populate(project_root)

    assert JalDB._read_to_list("SELECT operation_id, idx, account_id, symbol_id, amount, kind FROM fees "
                               "ORDER BY operation_id") == mirrored


def test_an_edited_fee_is_mirrored(prepare_db_fifo):
    _operations_with_fees()
    oid = operation_id(LedgerTransaction.Trade, 2)

    JalDB._exec("UPDATE trades SET fee='7.5' WHERE oid=:oid", [(":oid", oid)], commit=True)

    assert JalDB._read("SELECT amount FROM fees WHERE operation_id=:oid", [(":oid", oid)]) == '7.5'
    assert JalDB._read("SELECT COUNT(*) FROM fees WHERE operation_id=:oid", [(":oid", oid)]) == 1
    assert _stored_fees() == _sources()


def test_a_cleared_fee_takes_its_row_with_it(prepare_db_fifo):
    _operations_with_fees()
    oid = operation_id(LedgerTransaction.Trade, 2)
    assert JalDB._read("SELECT COUNT(*) FROM fees WHERE operation_id=:oid", [(":oid", oid)]) == 1

    JalDB._exec("UPDATE trades SET fee='0' WHERE oid=:oid", [(":oid", oid)], commit=True)

    assert JalDB._read("SELECT COUNT(*) FROM fees WHERE operation_id=:oid", [(":oid", oid)]) == 0
    assert _stored_fees() == _sources()


# A fee arriving on an operation that was stored without one - which is what an import adopting a late fee does
def test_a_fee_added_later_is_mirrored(prepare_db_fifo):
    _operations_with_fees()
    oid = operation_id(LedgerTransaction.Trade, 1)                 # the gas-coin trade, bought without a fee
    assert JalDB._read("SELECT COUNT(*) FROM fees WHERE operation_id=:oid", [(":oid", oid)]) == 0

    JalDB._exec("UPDATE trades SET fee='0.25' WHERE oid=:oid", [(":oid", oid)], commit=True)

    assert JalDB._read("SELECT amount FROM fees WHERE operation_id=:oid", [(":oid", oid)]) == '0.25'
    assert _stored_fees() == _sources()


# 'Transfer.update_fee()' reaches the column by raw SQL, one of the three paths that never sees the operation
# dictionary - and the one a statement import uses when it brings a fee for a transfer JAL already stores
def test_a_fee_adopted_by_update_fee_is_mirrored(prepare_db_fifo):
    _operations_with_fees()
    oid = create_transfers([(d2t(220801), 1, 5.0, 2, 5.0, None)])[0]
    assert JalDB._read("SELECT COUNT(*) FROM fees WHERE operation_id=:oid", [(":oid", oid)]) == 0

    assert Transfer(oid).update_fee(Decimal('0.4'), 2, None)

    assert JalDB._read_to_list("SELECT account_id, symbol_id, amount, kind FROM fees WHERE operation_id=:oid",
                               [(":oid", oid)]) == [[2, '', '0.4', FeeKind.Commission]]
    assert _stored_fees() == _sources()


# The editors are the other path that never sees the operation dictionary: they insert and update through a Qt model,
# which writes its own SQL. The trigger does not care, which is the whole reason the copy is kept in the database.
def test_the_editor_mirrors_the_fee_it_saves(prepare_db_fifo):
    _accounts_and_assets()
    parent = QWidget()          # a parentless dialog is collected in a way that aborts the process
    widget = TradeWidget(parent=parent)
    widget.createNew(account_id=1)
    record = widget.model.record(0)
    for field, value in (("symbol_id", symbol_id_for(4, 2)), ("qty", '10'), ("price", '100'),
                         ("fee", '1.75'), ("note", '')):
        record.setValue(field, value)
    widget.model.setRecord(0, record)

    widget._save()

    oid = JalDB._read("SELECT oid FROM trades")
    assert JalDB._read_to_list("SELECT account_id, symbol_id, amount, kind FROM fees WHERE operation_id=:oid",
                               [(":oid", oid)]) == [[1, '', '1.75', FeeKind.Commission]]

    widget.set_id(oid)                       # ... and the same editor re-opened on it, changing the fee
    record = widget.model.record(0)
    record.setValue("fee", '2.5')
    widget.model.setRecord(0, record)
    widget._save()

    assert JalDB._read("SELECT amount FROM fees WHERE operation_id=:oid", [(":oid", oid)]) == '2.5'
    assert _stored_fees() == _sources()


# The mirror owns 'idx = 0' and nothing else. A second fee - the Solana rent, a charge on the other leg of a transfer -
# is written by hand until the write path moves, and a parent being saved must not sweep it away.
def test_a_second_fee_survives_a_parent_write(prepare_db_fifo):
    _operations_with_fees()
    oid = operation_id(LedgerTransaction.Trade, 2)
    _add_fee(oid, amount='0.01', idx=1, kind=FeeKind.Rent)

    JalDB._exec("UPDATE trades SET fee='9' WHERE oid=:oid", [(":oid", oid)], commit=True)

    assert JalDB._read_to_list("SELECT idx, amount, kind FROM fees WHERE operation_id=:oid ORDER BY idx",
                               [(":oid", oid)]) == [[0, '9', FeeKind.Commission], [1, '0.01', FeeKind.Rent]]
