import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from decimal import Decimal

import sqlparse

from PySide6.QtWidgets import QWidget

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_fifo
from tests.helpers import d2t, create_assets, create_actions, create_dividends, create_trades, create_transfers, \
    create_corporate_actions, create_conversions, create_swaps, create_bridges, symbol_id_for, operation_id
from constants import PredefinedAsset, PredefinedCategory, Setup
from jal.db.db import JalDB
from jal.db.account import JalAccountCreator
from jal.db.operations import CorporateAction, LedgerTransaction
from jal.widgets.trade_widget import TradeWidget

# Where the renumbering starts and ends inside the delta. It is run from the shipped file rather than copied here,
# so this test breaks if the migration text stops doing what it says.
_MIGRATION_DELTA = 71   # the delta that introduced the root table, named explicitly and not as the current version
_MIGRATION_FROM = "-- AN OPERATION GETS A PARENT"
_MIGRATION_TO = "-- THE ROOT FOLLOWS ITS TYPE ROW"


_TABLES = [('actions', 1), ('asset_payments', 2), ('trades', 3), ('transfers', 4),
           ('asset_actions', 5), ('conversions', 6), ('swaps', 7), ('bridges', 8)]


# Puts the database back the way version 70 held it, which is the state the delta has to be run against: every type
# table numbers its own rows from 1 - so the ids collide across tables - and there is no root table at all.
# The renumbering is done through the negative id space for the same reason the delta does it: 'UPDATE ... SET oid'
# is checked row by row, so a new id another row still holds fails mid-statement.
_CHILDREN = {'actions': ('action_details', 'pid'), 'asset_actions': ('asset_action_results', 'action_id')}


def _unwind_to_version_70():
    JalDB().enable_fk(False)
    try:
        for table, otype in _TABLES:
            child = _CHILDREN.get(table)
            for sign, source in ((-1, 'x.oid'), (1, '-x.oid')):
                if sign < 0:   # first pass computes the per-table position, second one just flips the sign back
                    expression = (f"-(SELECT COUNT(*) FROM {table} AS y WHERE y.oid<={table}.oid)")
                    JalDB._exec(f"UPDATE {table} SET oid = {expression}")
                    if child:
                        JalDB._exec(f"UPDATE {child[0]} SET {child[1]} = -(SELECT COUNT(*) FROM {table} AS y "
                                    f"WHERE y.oid<={child[0]}.{child[1]})")
                else:
                    JalDB._exec(f"UPDATE {table} SET oid = -oid")
                    if child:
                        JalDB._exec(f"UPDATE {child[0]} SET {child[1]} = -{child[1]}")
        # The watermark names a swap, so it follows the swaps back to their own numbering
        JalDB._exec("UPDATE settings SET value = CAST(COALESCE((SELECT MIN(oid) FROM swaps), 0) AS TEXT) "
                    "WHERE name='LiFiAuditedSwap'")
        JalDB._exec("DROP INDEX IF EXISTS operations_by_type")
        JalDB._exec("DROP TABLE IF EXISTS operations", commit=True)
    finally:
        JalDB().enable_fk(True)


def _replay_the_migration(project_root):
    with open(project_root + f"/jal/updates/{Setup.UPDATE_PREFIX}{_MIGRATION_DELTA}.sql") as delta:
        text = delta.read()
    start, end = text.index(_MIGRATION_FROM), text.index(_MIGRATION_TO)
    # The delta turns foreign keys off around the whole script, outside its transaction where SQLite honours the
    # pragma. The replay has to do the same: ON UPDATE CASCADE must not fire, because the migration moves the two
    # child tables by hand and a cascade on top of that would move them twice.
    JalDB().enable_fk(False)
    try:
        for statement in sqlparse.split(text[start:end]):
            if not sqlparse.format(statement, strip_comments=True).strip():
                continue   # a run of comment lines is not a statement
            assert JalDB._exec(statement.strip()) is not None, f"Migration statement failed: {statement}"
    finally:
        JalDB().enable_fk(True)
    JalDB().commit()


# Operations of every type, deliberately with the colliding per-table ids of version 70: each table numbers from 1,
# so oid 1 means eight different operations. Both children of an operation are represented, and so is the one
# stored oid that lives outside the operation tables.
def _operations_of_every_type():
    create_assets([('AAPL', 'Apple', 'US0378331005', 2, PredefinedAsset.Stock, 0),
                   ('MSFT', 'Microsoft', 'US5949181045', 2, PredefinedAsset.Stock, 0)])
    second = JalAccountCreator(currency_id=2, number='U1111111', name='Second', investing=1, organization=1).commit()
    create_actions([(d2t(210101), 1, 1, [(PredefinedCategory.Spending, 10.0)]),
                    (d2t(210102), 1, 1, [(PredefinedCategory.Spending, 20.0), (PredefinedCategory.Fees, 30.0)])])
    create_dividends([(d2t(210103), 1, 4, Decimal('5'), Decimal('0'), 'dividend'),
                      (d2t(210104), 1, 4, Decimal('6'), Decimal('0'), 'dividend')])
    create_trades(1, [(d2t(210105), d2t(210105), 4, Decimal('10'), Decimal('100'), Decimal('1')),
                      (d2t(210106), d2t(210106), 4, Decimal('-5'), Decimal('110'), Decimal('1'))])
    create_transfers([(d2t(210107), 1, Decimal('100'), second.id(), Decimal('100'), None)])
    create_corporate_actions(1, [(d2t(210108), CorporateAction.SymbolChange, 4, Decimal('5'), 'renamed',
                                  [(5, Decimal('5'), Decimal('1'))])])
    create_conversions(1, [(d2t(210109), 4, Decimal('1'), 5, Decimal('1'))])
    create_swaps(1, [(d2t(210110), 4, Decimal('1'), 5, Decimal('1'))])
    create_bridges([{'out_ts': d2t(210111), 'out_acc': 1, 'out_qty': Decimal('1'),
                     'in_ts': d2t(210112), 'in_acc': second.id(), 'in_qty': Decimal('1'), 'asset': 4}])
    JalDB._exec("INSERT OR REPLACE INTO settings(name, value) VALUES('LiFiAuditedSwap', 1)", commit=True)


def test_the_migration_gives_every_operation_one_continuous_id(prepare_db_fifo, project_root):
    _operations_of_every_type()
    before = {table: JalDB._read(f"SELECT COUNT(*) FROM {table}") for table, _ in _TABLES}
    _unwind_to_version_70()
    # The state the delta is written against: every table numbers from 1, so oid 1 is eight different operations
    assert before['actions'] > 1 and before['trades'] > 1
    assert JalDB._read("SELECT MIN(oid) FROM actions") == JalDB._read("SELECT MIN(oid) FROM trades") == 1

    _replay_the_migration(project_root)

    total = sum(before.values())
    assert JalDB._read("SELECT COUNT(*) FROM operations") == total
    assert JalDB._read("SELECT MIN(id) FROM operations") == 1
    assert JalDB._read("SELECT MAX(id) FROM operations") == total   # continuous: no gaps, no offset blocks
    # Each type keeps its own count, and its rows land in one block that the root names the same way
    for table, otype in _TABLES:
        assert JalDB._read(f"SELECT COUNT(*) FROM {table}") == before[table]
        assert JalDB._read("SELECT COUNT(*) FROM operations WHERE otype=:t", [(":t", otype)]) == before[table]
        assert JalDB._read(f"SELECT COUNT(*) FROM {table} AS x LEFT JOIN operations AS o ON o.id=x.oid "
                           f"WHERE o.id IS NULL OR o.otype<>:t", [(":t", otype)]) == 0


# The two children are moved by hand because the delta runs with foreign keys off, so ON UPDATE CASCADE - which
# both of them declare - never fires. Forget them and every detail row points at nothing.
def test_the_migration_carries_both_children_with_their_parent(prepare_db_fifo, project_root):
    _operations_of_every_type()
    details = JalDB._read("SELECT COUNT(*) FROM action_details")
    results = JalDB._read("SELECT COUNT(*) FROM asset_action_results")
    assert details > 0 and results > 0
    _unwind_to_version_70()

    _replay_the_migration(project_root)

    assert JalDB._read("SELECT COUNT(*) FROM action_details") == details
    assert JalDB._read("SELECT COUNT(*) FROM action_details AS d LEFT JOIN actions AS a ON a.oid=d.pid "
                       "WHERE a.oid IS NULL") == 0
    assert JalDB._read("SELECT COUNT(*) FROM asset_action_results") == results
    assert JalDB._read("SELECT COUNT(*) FROM asset_action_results AS r LEFT JOIN asset_actions AS a "
                       "ON a.oid=r.action_id WHERE a.oid IS NULL") == 0


# 'LiFiAuditedSwap' is the highest swap already audited against the route it came from - a stored swap oid that
# lives outside the operation tables. Left alone it would point into the old numbering; reset to 0 it would
# re-audit every swap over the network.
def test_the_migration_moves_the_audited_swap_watermark(prepare_db_fifo, project_root):
    _operations_of_every_type()
    _unwind_to_version_70()

    _replay_the_migration(project_root)

    # The watermark is stored as text, the way every setting is
    assert int(JalDB._read("SELECT value FROM settings WHERE name='LiFiAuditedSwap'")) == \
           JalDB._read("SELECT oid FROM swaps ORDER BY oid LIMIT 1")


# The watermark is moved as a watermark and not as a row reference: the swap it names may have been deleted since
# it was audited. An exact lookup would yield NULL there, and 'settings.value' is NOT NULL - which would fail the
# whole upgrade on a database that is otherwise perfectly sound.
def test_the_migration_survives_a_watermark_whose_swap_is_gone(prepare_db_fifo, project_root):
    _operations_of_every_type()
    _unwind_to_version_70()
    audited = JalDB._read("SELECT MAX(oid) FROM swaps")
    JalDB._exec("UPDATE settings SET value=:v WHERE name='LiFiAuditedSwap'", [(":v", audited + 5)], commit=True)

    _replay_the_migration(project_root)

    # Everything up to the highest swap there is had been audited, and that is what it still says
    assert int(JalDB._read("SELECT value FROM settings WHERE name='LiFiAuditedSwap'")) == \
           JalDB._read("SELECT MAX(oid) FROM swaps")


# A watermark below every swap that exists means nothing has been audited, and it must not become a real swap id
def test_the_migration_zeroes_a_watermark_below_every_swap(prepare_db_fifo, project_root):
    _operations_of_every_type()
    JalDB._exec("DELETE FROM swaps", commit=True)   # before the unwind: the triggers still reach the root here
    _unwind_to_version_70()
    JalDB._exec("UPDATE settings SET value=1 WHERE name='LiFiAuditedSwap'", commit=True)

    _replay_the_migration(project_root)

    assert int(JalDB._read("SELECT value FROM settings WHERE name='LiFiAuditedSwap'")) == 0


# The order must preserve each type's internal 'oid' order. The ledger is processed in 'timestamp, seq, opart, oid'
# order and each 'seq' maps to exactly one table, so the 'oid' tie-break only ever compares two rows of the SAME
# table - preserving the order within a type is what guarantees FIFO lot consumption cannot move.
def test_the_migration_preserves_the_order_within_each_type(prepare_db_fifo, project_root):
    _operations_of_every_type()
    before = {table: JalDB._read_to_list(f"SELECT oid, timestamp FROM {table} ORDER BY oid")
              for table, _ in _TABLES if table not in ('transfers', 'bridges')}
    _unwind_to_version_70()

    _replay_the_migration(project_root)

    for table, rows in before.items():
        after = JalDB._read_to_list(f"SELECT oid, timestamp FROM {table} ORDER BY oid")
        assert [r[1] for r in after] == [r[1] for r in rows], f"{table} was reshuffled by the renumbering"


# The root is cleaned from the type row and not the other way round, because deleting the operation is not the only
# way a type row goes: an account, an asset listing or an agent takes its operations with it by foreign key.
def test_deleting_an_account_leaves_no_orphan_root(prepare_db_fifo, project_root):
    _operations_of_every_type()
    _unwind_to_version_70()
    _replay_the_migration(project_root)
    assert JalDB._read("SELECT COUNT(*) FROM trades") > 0

    JalDB._exec("DELETE FROM accounts WHERE id=1", commit=True)

    assert JalDB._read("SELECT COUNT(*) FROM trades") == 0
    for table, otype in _TABLES:
        assert JalDB._read("SELECT COUNT(*) FROM operations AS o WHERE o.otype=:t AND NOT EXISTS "
                           f"(SELECT 1 FROM {table} AS x WHERE x.oid=o.id)", [(":t", otype)]) == 0, \
            f"an orphan root survived the cascade that removed its {table} row"


# ----------------------------------------------------------------------------------------------------------------------
# Allocation: every operation takes its id from the root, whichever of the two write paths stored it.
def test_every_operation_gets_exactly_one_root_row(prepare_db_fifo, project_root):
    _operations_of_every_type()

    for table, otype in _TABLES:
        rows = JalDB._read(f"SELECT COUNT(*) FROM {table}")
        assert JalDB._read("SELECT COUNT(*) FROM operations WHERE otype=:t", [(":t", otype)]) == rows
        # ... and it is the SAME id: the type table stores the number the root handed out
        assert JalDB._read(f"SELECT COUNT(*) FROM {table} AS x JOIN operations AS o ON o.id=x.oid "
                           f"WHERE o.otype=:t", [(":t", otype)]) == rows


# An id means one operation and nothing else - which is the whole point, since before the root every table numbered
# its own rows from 1 and oid 1 was eight different operations
def test_ids_do_not_collide_across_types(prepare_db_fifo, project_root):
    _operations_of_every_type()

    ids = []
    for table, _ in _TABLES:
        ids += JalDB._read_to_list(f"SELECT oid FROM {table}")
    assert len(ids) == len(set(ids))
    assert sorted(ids) == JalDB._read_to_list("SELECT id FROM operations ORDER BY id")


# A child of an operation is not an operation: it keeps its own table's numbering and gets no row in the root
def test_a_child_of_an_operation_gets_no_root_row(prepare_db_fifo, project_root):
    create_actions([(d2t(210101), 1, 1, [(PredefinedCategory.Spending, 10.0),
                                         (PredefinedCategory.Spending, 20.0),
                                         (PredefinedCategory.Fees, 30.0)])])

    # The fixture opens with a starting-balance action of one line, so this adds a second action and three lines
    assert JalDB._read("SELECT COUNT(*) FROM action_details") == 4
    assert JalDB._read("SELECT COUNT(*) FROM operations") == 2   # two actions, not two actions and four lines
    assert JalDB._read("SELECT MAX(id) FROM action_details") == 4   # children keep their own table's numbering


def test_deleting_an_operation_takes_its_root_with_it(prepare_db_fifo, project_root):
    _operations_of_every_type()

    for table, otype in _TABLES:
        for oid in JalDB._read_to_list(f"SELECT oid FROM {table}"):
            LedgerTransaction.get_operation(otype, oid).delete()

    assert JalDB._read("SELECT COUNT(*) FROM operations") == 0
    for table, _ in _TABLES:
        assert JalDB._read(f"SELECT COUNT(*) FROM {table}") == 0


# The other deletion path, and the reason the root is cleaned from the type row rather than the other way round:
# an account takes its operations with it by foreign key, and no trigger on 'operations' would ever see that happen
def test_deleting_an_account_takes_the_roots_of_its_operations(prepare_db_fifo, project_root):
    _operations_of_every_type()
    assert JalDB._read("SELECT COUNT(*) FROM operations") > 0

    JalDB._exec("DELETE FROM accounts WHERE id=1", commit=True)

    for table, otype in _TABLES:
        assert JalDB._read("SELECT COUNT(*) FROM operations AS o WHERE o.otype=:t AND NOT EXISTS "
                           f"(SELECT 1 FROM {table} AS x WHERE x.oid=o.id)", [(":t", otype)]) == 0, \
            f"an orphan root survived the cascade that removed its {table} row"


# ----------------------------------------------------------------------------------------------------------------------
# The editor is the OTHER write path: it inserts through the Qt model rather than through create_operation(), and it
# has to take its id from the root just the same - a per-table rowid would collide with every other kind.
def test_the_editor_allocates_its_id_from_the_root(prepare_db_fifo, project_root):
    create_assets([('AAPL', 'Apple', 'US0378331005', 2, PredefinedAsset.Stock, 0)])
    parent = QWidget()          # a parentless dialog is collected in a way that aborts the process
    widget = TradeWidget(parent=parent)
    widget.createNew(account_id=1)
    record = widget.model.record(0)
    record.setValue("symbol_id", symbol_id_for(4, 2))
    record.setValue("qty", '10')
    record.setValue("price", '100')
    record.setValue("note", '')      # NOT NULL, and the note field of the running editor would have filled it
    widget.model.setRecord(0, record)

    widget._save()

    oid = JalDB._read("SELECT oid FROM trades")
    assert JalDB._read("SELECT otype FROM operations WHERE id=:id", [(":id", oid)]) == LedgerTransaction.Trade
    assert JalDB._read("SELECT COUNT(*) FROM operations") == 2   # the fixture's starting-balance action, and this


# The id is taken at INSERT and not when the editor opens, so an operation the user starts and abandons leaves
# nothing behind - no root row, and no gap in the numbering
def test_an_abandoned_new_operation_leaves_no_root_row(prepare_db_fifo, project_root):
    before = JalDB._read("SELECT COUNT(*) FROM operations")
    parent = QWidget()
    widget = TradeWidget(parent=parent)

    widget.createNew(account_id=1)
    widget.revertChanges()

    assert JalDB._read("SELECT COUNT(*) FROM operations") == before


# A submit that fails must not leave the root row it had already taken an id from. The two rows are one write.
def test_a_failed_save_leaves_no_root_row(prepare_db_fifo, project_root):
    create_assets([('AAPL', 'Apple', 'US0378331005', 2, PredefinedAsset.Stock, 0)])
    before = JalDB._read("SELECT COUNT(*) FROM operations")
    parent = QWidget()
    widget = TradeWidget(parent=parent)
    widget.createNew(account_id=1)
    record = widget.model.record(0)
    record.setValue("symbol_id", symbol_id_for(4, 2))
    record.setNull("note")            # 'trades.note' is NOT NULL, so the insert is refused
    widget.model.setRecord(0, record)

    assert widget._save() is False

    assert JalDB._read("SELECT COUNT(*) FROM trades") == 0
    assert JalDB._read("SELECT COUNT(*) FROM operations") == before


# ----------------------------------------------------------------------------------------------------------------------
# 'ledger_sequence' ships empty and nothing reads it yet. What is checked here is the contract the stages that fill
# it will be built on - that it really is keyed on the root, and that the root really does clear it.
def test_the_sequence_table_ships_empty(prepare_db_fifo, project_root):
    _operations_of_every_type()

    assert JalDB._read("SELECT COUNT(*) FROM ledger_sequence") == 0


# The single-column foreign key is the whole reason the root exists: '(otype, oid)' could never be one
def test_a_deleted_operation_takes_its_sequence_rows_with_it(prepare_db_fifo, project_root):
    _operations_of_every_type()
    oid = operation_id(LedgerTransaction.Transfer)
    for part in (-1, 0, 1):
        JalDB._exec("INSERT INTO ledger_sequence (operation_id, opart, timestamp, account_id) "
                    "VALUES (:oid, :part, :ts, 1)", [(":oid", oid), (":part", part), (":ts", d2t(210107))])
    JalDB().commit()
    assert JalDB._read("SELECT COUNT(*) FROM ledger_sequence") == 3

    LedgerTransaction.get_operation(LedgerTransaction.Transfer, oid).delete()

    assert JalDB._read("SELECT COUNT(*) FROM ledger_sequence") == 0


# One row per PART, so an operation may hold several - but only one of each part
def test_a_part_of_an_operation_is_listed_once(prepare_db_fifo, project_root):
    _operations_of_every_type()
    oid = operation_id(LedgerTransaction.Transfer)
    JalDB._exec("INSERT INTO ledger_sequence (operation_id, opart, timestamp, account_id) "
                "VALUES (:oid, 0, :ts, 1)", [(":oid", oid), (":ts", d2t(210107))], commit=True)

    duplicate = JalDB._exec("INSERT INTO ledger_sequence (operation_id, opart, timestamp, account_id) "
                            "VALUES (:oid, 0, :ts, 1)", [(":oid", oid), (":ts", d2t(210107))], commit=True)

    assert duplicate is None    # UNIQUE (operation_id, opart)
    assert JalDB._read("SELECT COUNT(*) FROM ledger_sequence") == 1
