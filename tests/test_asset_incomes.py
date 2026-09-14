# The migration that separates the asset arriving from the money paid on account of it. What an asset income does to
# the ledger is tested in test_asset_payments_crypto.py and test_ledger.py.
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from decimal import Decimal

import sqlparse

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_fifo
from tests.helpers import d2t, create_stocks, symbol_id_for
from constants import Setup
from jal.db.db import JalDB
from jal.db.operations import LedgerTransaction, AssetPayment, AssetIncome, FeeKind

# The subtypes as schema 76 numbered them, which is the state the delta meets. They are renumbered from 1 by it,
# because each of the two classes has a type selector of its own now and the editor maps it by index.
_OLD = {'stock_dividend': 3, 'stock_vesting': 4, 'staking_reward': 8, 'dust_attack': 9, 'reward': 10,
        'rebase': 11, 'rent_returned': 13, 'dividend': 1, 'bond_interest': 2}
_NEW = {'stock_dividend': AssetIncome.StockDividend, 'stock_vesting': AssetIncome.StockVesting,
        'staking_reward': AssetIncome.StakingReward, 'dust_attack': AssetIncome.DustAttack,
        'reward': AssetIncome.Reward, 'rebase': AssetIncome.RebaseAdjustment,
        'rent_returned': AssetIncome.TokenRentReturn}


def _accounts_and_assets():
    create_stocks([('A', 'Asset A'), ('GAS', 'Native coin')], currency_id=2)   # asset ids 4 and 5
    _restore_the_price_column()


# 'asset_payments.price' was dropped by delta 78 once the operations that stated one had left for 'asset_incomes'.
# A migration that ran before that meets a table which still has it, so it is put back before the replay - the way
# test_fees_table.py re-declares the fee columns of schema 74.
def _restore_the_price_column():
    assert JalDB._exec("ALTER TABLE asset_payments ADD COLUMN price TEXT NOT NULL DEFAULT ('')") is not None
    JalDB().commit()


# A payment as schema 76 stored one, whichever of the two it turned out to be
def _payment(subtype, timestamp=None, amount='10', price='', tax='0', note='test', number='n'):
    oid = JalDB().allocate_operation_id(LedgerTransaction.AssetPayment)
    JalDB._exec("INSERT INTO asset_payments (oid, otype, timestamp, ex_date, number, type, account_id, symbol_id, "
                "amount, tax, price, note) VALUES (:oid, 2, :ts, 0, :number, :type, 1, :symbol, :amount, :tax, "
                ":price, :note)",
                [(":oid", oid), (":ts", timestamp if timestamp else d2t(220201)), (":number", number),
                 (":type", subtype), (":symbol", symbol_id_for(4, 2)), (":amount", amount), (":tax", tax),
                 (":price", price), (":note", note)], commit=True)
    return oid


_MIGRATION_DELTA = 77
_MIGRATION_FROM = "-- The subtypes are renumbered from 1"
_MIGRATION_TO = "-- THE TRIGGERS, RE-STATED AND ADDED"


# Run from the shipped file, so that this breaks if the delta stops doing what it says. The three 'asset_payments'
# triggers go first, as they do in the delta - its delete trigger would take the root row of every payment it sees go
# with it, including the ones being MOVED - and the CREATE TABLE is skipped, a test database already having it.
def _replay_the_migration(project_root):
    for event in ('delete', 'insert', 'update'):
        JalDB._exec(f"DROP TRIGGER IF EXISTS asset_payments_after_{event}")
    with open(project_root + f"/jal/updates/{Setup.UPDATE_PREFIX}{_MIGRATION_DELTA}.sql") as delta:
        text = delta.read()
    start, end = text.index(_MIGRATION_FROM), text.index(_MIGRATION_TO)
    for statement in sqlparse.split(text[start:end]):
        stripped = sqlparse.format(statement, strip_comments=True).strip()
        if not stripped:
            continue
        assert JalDB._exec(stripped) is not None, f"Migration statement failed: {statement}"
    JalDB().commit()


def _incomes() -> list:
    return JalDB._read_to_list("SELECT oid, type FROM asset_incomes ORDER BY oid")


def _payments() -> list:
    return JalDB._read_to_list("SELECT oid, type FROM asset_payments ORDER BY oid")


# ----------------------------------------------------------------------------------------------------------------------
# Every subtype whose amount is a QUANTITY of the asset moves, and the money ones stay. Each of the seven is listed
# by name, because a renumbering that swaps two of them silently re-labels real records.
def test_every_asset_denominated_subtype_moves_and_is_renumbered(prepare_db_fifo, project_root):
    _accounts_and_assets()
    moved = {name: _payment(_OLD[name]) for name in _NEW}
    stayed = {name: _payment(_OLD[name]) for name in ('dividend', 'bond_interest')}

    _replay_the_migration(project_root)

    assert _incomes() == sorted([[moved[name], _NEW[name]] for name in _NEW])
    assert _payments() == sorted([[stayed[name], _OLD[name]] for name in stayed])


# The id never moves, which is what lets every fee row, every ledger reference and every open lot that names one of
# these go on naming the same operation.
def test_the_operation_keeps_its_id_and_changes_its_type(prepare_db_fifo, project_root):
    _accounts_and_assets()
    oid = _payment(_OLD['staking_reward'])
    assert JalDB._read("SELECT otype FROM operations WHERE id=:oid", [(":oid", oid)]) == LedgerTransaction.AssetPayment

    _replay_the_migration(project_root)

    assert JalDB._read("SELECT otype FROM operations WHERE id=:oid", [(":oid", oid)]) == LedgerTransaction.AssetIncome
    assert JalDB._read("SELECT COUNT(*) FROM asset_payments WHERE oid=:oid", [(":oid", oid)]) == 0
    assert JalDB._read("SELECT COUNT(*) FROM asset_incomes WHERE oid=:oid", [(":oid", oid)]) == 1


# The gas of a claim was attached to it by delta 76 and is not touched again here: the claim keeps its id, so the fee
# keeps its parent without a single row of 'fees' being rewritten.
def test_a_fee_follows_the_operation_it_belongs_to(prepare_db_fifo, project_root):
    _accounts_and_assets()
    oid = _payment(_OLD['staking_reward'])
    JalDB._exec("INSERT INTO fees (operation_id, idx, account_id, symbol_id, amount, kind) "
                "VALUES (:oid, 0, 1, :symbol, '0.5', :gas)",
                [(":oid", oid), (":symbol", symbol_id_for(5, 2)), (":gas", FeeKind.Gas)], commit=True)

    _replay_the_migration(project_root)

    income = LedgerTransaction.get_operation(LedgerTransaction.AssetIncome, oid)
    assert [(x.amount(), x.kind()) for x in income.fees()] == [(Decimal('0.5'), FeeKind.Gas)]


# Everything the row carried comes with it - including the price, which is the whole cost basis of granted shares
def test_the_row_arrives_whole(prepare_db_fifo, project_root):
    _accounts_and_assets()
    oid = _payment(_OLD['stock_vesting'], amount='7', price='123.45', tax='1.5', note='Vested', number='x1')

    _replay_the_migration(project_root)

    assert JalDB._read_to_list("SELECT amount, price, tax, note, number FROM asset_incomes WHERE oid=:oid",
                               [(":oid", oid)]) == [['7', '123.45', '1.5', 'Vested', 'x1']]
    assert LedgerTransaction.get_operation(LedgerTransaction.AssetIncome, oid).price() == Decimal('123.45')


# Nothing else in the suite would notice the delta and the init script drifting apart: every object is declared twice,
# once for a database created from scratch and once for one being upgraded.
def _created_objects(text: str) -> dict:
    objects = {}
    for statement in sqlparse.split(text):
        stripped = sqlparse.format(statement, strip_comments=True).strip()
        for kind in ("CREATE TABLE", "CREATE INDEX", "CREATE TRIGGER"):
            if stripped.startswith(kind):
                objects[stripped[len(kind):].strip().split()[0]] = stripped
    return objects


# An object a LATER delta restates is compared as that delta leaves it, not as this one wrote it: an upgraded
# database ends where a new one starts, and only the last word about an object says where that is.
def _as_the_upgrade_leaves_it(project_root, name: str, since: int) -> str:
    for version in range(Setup.DB_REQUIRED_VERSION, since - 1, -1):
        with open(project_root + f"/jal/updates/{Setup.UPDATE_PREFIX}{version}.sql") as delta:
            declared = _created_objects(delta.read())
        if name in declared:
            return declared[name]
    raise AssertionError(f"{name} is declared by no delta from {since} on")


def test_the_delta_and_the_init_script_declare_the_same_objects(project_root):
    with open(project_root + "/jal/" + Setup.INIT_SCRIPT_PATH) as init:
        from_init = _created_objects(init.read())
    with open(project_root + f"/jal/updates/{Setup.UPDATE_PREFIX}{_MIGRATION_DELTA}.sql") as delta:
        from_delta = _created_objects(delta.read())

    assert len(from_delta) == 7     # the table and six triggers - its own three, and the three it re-states
    for name in from_delta:
        assert name in from_init, f"{name} is created by the delta and by nothing else"
        assert _as_the_upgrade_leaves_it(project_root, name, _MIGRATION_DELTA) == from_init[name], name


def test_the_delta_puts_the_payment_triggers_back(project_root):
    with open(project_root + f"/jal/updates/{Setup.UPDATE_PREFIX}{_MIGRATION_DELTA}.sql") as delta:
        text = delta.read()

    for event in ('delete', 'insert', 'update'):
        assert text.index(f"DROP TRIGGER IF EXISTS asset_payments_after_{event}") \
               < text.index(f"CREATE TRIGGER asset_payments_after_{event}")


# The two halves are one place in the processing order, which is what keeps FIFO consuming the same lots as before:
# a rank of its own for either of them would move lot consumption wherever the two meet in the same second.
def test_the_two_halves_share_one_rank():
    assert AssetIncome.LedgerRank == AssetPayment.LedgerRank


# ----------------------------------------------------------------------------------------------------------------------
# DELTA 78 - what is left of a payment once the asset half has gone.
_NARROWING_DELTA = 78


# A bond amortization books money in AND reduces the position's basis, which no other operation does. No importer can
# emit one and hand entry was the only way to make one at all, so there are none - but a database that holds one must
# not be guessed at, and the upgrade stops on it instead. This is the guard, replayed against a stored row.
def test_the_upgrade_refuses_a_database_that_holds_a_bond_amortization(prepare_db_fifo, project_root):
    _accounts_and_assets()
    _payment(5)                                    # AssetPayment.BondAmortization as schema 77 numbered it
    with open(project_root + f"/jal/updates/{Setup.UPDATE_PREFIX}{_NARROWING_DELTA}.sql") as delta:
        guard = [x for x in sqlparse.split(delta.read()) if 'asset_payments WHERE type = 5' in x]
    assert len(guard) == 1

    assert JalDB._exec(sqlparse.format(guard[0], strip_comments=True).strip()) is None   # the delta stops here

    assert JalDB._read("SELECT COUNT(*) FROM asset_payments WHERE type = 5") == 1   # ... and nothing was re-labelled


# ... and it is a no-op on every database that holds none, which is every database the live ledger knows of
def test_the_guard_passes_a_database_without_one(prepare_db_fifo, project_root):
    _accounts_and_assets()
    _payment(_OLD['dividend'])
    with open(project_root + f"/jal/updates/{Setup.UPDATE_PREFIX}{_NARROWING_DELTA}.sql") as delta:
        guard = [x for x in sqlparse.split(delta.read()) if 'asset_payments WHERE type = 5' in x]

    assert JalDB._exec(sqlparse.format(guard[0], strip_comments=True).strip()) is not None


# The 'Asset fee/tax' subtype takes the first free number now that the class has three of them
def test_the_asset_fee_subtype_is_renumbered(prepare_db_fifo, project_root):
    _accounts_and_assets()
    oid = _payment(6)                              # AssetPayment.AssetFee as schema 77 numbered it
    with open(project_root + f"/jal/updates/{Setup.UPDATE_PREFIX}{_NARROWING_DELTA}.sql") as delta:
        statement = [x for x in sqlparse.split(delta.read()) if 'SET type = 3' in x][0]

    assert JalDB._exec(sqlparse.format(statement, strip_comments=True).strip()) is not None
    JalDB().commit()

    assert JalDB._read("SELECT type FROM asset_payments WHERE oid=:oid", [(":oid", oid)]) == AssetPayment.AssetFee


# SQLite drops a column an 'UPDATE OF' list names without a word and leaves the list naming it, so the trigger has to
# be re-stated BEFORE the column goes - and a fee edit would otherwise stop invalidating the ledger.
def test_the_delta_restates_the_trigger_before_it_drops_the_column(project_root):
    with open(project_root + f"/jal/updates/{Setup.UPDATE_PREFIX}{_NARROWING_DELTA}.sql") as delta:
        text = delta.read()

    assert text.index("CREATE TRIGGER asset_payments_after_update") < text.index("DROP COLUMN price")
    assert "price" not in text[text.index("CREATE TRIGGER asset_payments_after_update"):text.index("DROP COLUMN price")]
