from decimal import Decimal

import sqlparse

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_fifo
from tests.helpers import d2t, create_assets, create_actions, create_dividends, create_trades, create_transfers, \
    create_corporate_actions, create_conversions, create_swaps, create_bridges
from constants import PredefinedAsset, PredefinedCategory, Setup
from jal.db.db import JalDB
from jal.db.account import JalAccountCreator
from jal.db.operations import CorporateAction

# Where the renumbering starts and ends inside the delta. It is run from the shipped file rather than copied here,
# so this test breaks if the migration text stops doing what it says.
_MIGRATION_DELTA = 71   # the delta that introduced the root table, named explicitly and not as the current version
_MIGRATION_FROM = "-- AN OPERATION GETS A PARENT"
_MIGRATION_TO = "-- THE ROOT FOLLOWS ITS TYPE ROW"


# Puts the database back the way version 70 held it: the type tables number their own rows from 1 and there is no
# root table at all. That is what the fixture below already produces - nothing allocates from 'operations' yet -
# so only the table itself has to go.
def _unwind_to_version_70():
    JalDB._exec("DROP INDEX IF EXISTS operations_by_type")
    JalDB._exec("DROP TABLE IF EXISTS operations", commit=True)


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


_TABLES = [('actions', 1), ('asset_payments', 2), ('trades', 3), ('transfers', 4),
           ('asset_actions', 5), ('conversions', 6), ('swaps', 7), ('bridges', 8)]


def test_the_migration_gives_every_operation_one_continuous_id(prepare_db_fifo, project_root):
    _operations_of_every_type()
    before = {table: JalDB._read(f"SELECT COUNT(*) FROM {table}") for table, _ in _TABLES}
    assert before['actions'] > 1 and before['trades'] > 1     # the ids really do collide across the tables
    assert JalDB._read("SELECT MIN(oid) FROM actions") == JalDB._read("SELECT MIN(oid) FROM trades") == 1
    _unwind_to_version_70()

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
