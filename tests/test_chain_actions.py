# The migration that turns a gas payment into the event that burned it. What a chain action does to the ledger is
# tested in test_asset_payments_crypto.py, and the row it draws in test_operation_rows.py.
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from decimal import Decimal

import sqlparse

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_fifo
from tests.helpers import d2t, create_stocks, create_transfers, symbol_id_for
from constants import Setup
from jal.db.db import JalDB
from jal.db.operations import LedgerTransaction, AssetPayment, ChainAction, FeeKind

_GAS_FEE = 7        # AssetPayment.GasFee and AssetPayment.TokenRent as they were before this delta: the subtypes
_TOKEN_RENT = 12    # are gone from the class, and the rows carrying them are exactly what the migration converts


# Two coins to pay gas in and one asset to be rewarded with, plus the account holding them
def _accounts_and_assets():
    create_stocks([('A', 'Asset A'), ('B', 'Asset B'), ('GAS', 'Native coin')], currency_id=2)   # asset ids 4, 5, 6


# A gas payment as schema 75 stored one: the coin burned IS the operation's amount, and what happened is a sentence
def _gas_payment(timestamp, number, amount, subtype=_GAS_FEE, note='Gas: contract call', account_id=1, asset_id=6):
    oid = JalDB().allocate_operation_id(LedgerTransaction.AssetPayment)
    JalDB._exec("INSERT INTO asset_payments (oid, otype, timestamp, number, type, account_id, symbol_id, amount, "
                "tax, price, note) VALUES (:oid, 2, :ts, :number, :type, :account, :symbol, :amount, '0', '', :note)",
                [(":oid", oid), (":ts", timestamp), (":number", number), (":type", subtype),
                 (":account", account_id), (":symbol", symbol_id_for(asset_id, 2)), (":amount", amount),
                 (":note", note)], commit=True)
    return oid


def _reward(timestamp, number, asset_id, amount='100'):
    return LedgerTransaction.create_new(LedgerTransaction.AssetPayment, {
        'timestamp': timestamp, 'type': AssetPayment.StakingReward, 'account_id': 1,
        'symbol_id': symbol_id_for(asset_id, 2), 'amount': amount, 'tax': '0', 'number': number,
        'note': 'Reward claim'}).id()


_MIGRATION_DELTA = 76
_MIGRATION_FROM = "-- WHO EACH GAS PAYMENT BELONGS TO"
_MIGRATION_TO = "-- THE TRIGGERS, RE-STATED AND ADDED"


# The migration itself, run from the shipped file so that this breaks if it stops doing what it says. The three
# 'asset_payments' triggers go first, as they do in the delta - its delete trigger would take the root row of every
# payment being MOVED with it - and the CREATE TABLE is skipped because a test database already has the table.
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


def _fees_of(oid) -> list:
    return JalDB._read_to_list("SELECT account_id, symbol_id, amount, kind FROM fees WHERE operation_id=:oid "
                               "ORDER BY idx", [(":oid", oid)])


def _actions() -> list:
    return JalDB._read_to_list("SELECT oid, type, number, symbol_id, note FROM chain_actions ORDER BY oid")


# ----------------------------------------------------------------------------------------------------------------------
# The gas that has an owner. The link was in the data all along and simply never drawn: the transaction hash.
def test_gas_becomes_the_fee_of_the_operation_it_paid_for(prepare_db_fifo, project_root):
    _accounts_and_assets()
    claim = _reward(d2t(220201), '0xclaim', 4)
    gas = _gas_payment(d2t(220201), '0xclaim', '0.5')

    _replay_the_migration(project_root)

    assert _fees_of(claim) == [[1, symbol_id_for(6, 2), '0.5', FeeKind.Gas]]
    assert _actions() == []                                            # it is nobody's event, it is a cost
    assert JalDB._read("SELECT COUNT(*) FROM operations WHERE id=:oid", [(":oid", gas)]) == 0
    assert JalDB._read("SELECT COUNT(*) FROM asset_payments WHERE oid=:oid", [(":oid", gas)]) == 0


# The payer is not always the recipient: one claim in the live ledger was submitted by another wallet on its behalf,
# which is the whole reason a fee row carries an account of its own.
def test_the_fee_keeps_the_account_that_bore_it(prepare_db_fifo, project_root):
    _accounts_and_assets()
    from jal.db.account import JalAccountCreator
    JalAccountCreator(currency_id=2, number='U2', name='Other', investing=1, organization=1).commit()
    claim = _reward(d2t(220201), '0xclaim', 4)
    _gas_payment(d2t(220201), '0xclaim', '0.5', account_id=2)

    _replay_the_migration(project_root)

    assert _fees_of(claim) == [[2, symbol_id_for(6, 2), '0.5', FeeKind.Gas]]


# One claim, two assets, one gas row: it goes to the FIRST asset by id, which is the choice the importer makes too
# ('sorted(ins.items())' in evm.py), so a re-import reproduces it instead of adding a second copy.
def test_a_claim_of_several_assets_gives_its_gas_to_the_first_asset(prepare_db_fifo, project_root):
    _accounts_and_assets()
    second = _reward(d2t(220201), '0xclaim', 5)     # created first, but its asset id is the higher one
    first = _reward(d2t(220201), '0xclaim', 4)
    _gas_payment(d2t(220201), '0xclaim', '0.5')

    _replay_the_migration(project_root)

    assert _fees_of(first) == [[1, symbol_id_for(6, 2), '0.5', FeeKind.Gas]]
    assert _fees_of(second) == []


def test_gas_no_outgoing_leg_could_carry_becomes_the_fee_of_its_transfer(prepare_db_fifo, project_root):
    _accounts_and_assets()
    from jal.db.account import JalAccountCreator
    JalAccountCreator(currency_id=2, number='U2', name='Other', investing=1, organization=1).commit()
    transfer = create_transfers([(d2t(220201), 1, 5.0, 2, 5.0, None, '0xsend')])[0]
    _gas_payment(d2t(220201), '0xsend', '0.5')

    _replay_the_migration(project_root)

    assert _fees_of(transfer) == [[1, symbol_id_for(6, 2), '0.5', FeeKind.Gas]]
    assert _actions() == []


# A fee already stored on the parent is not overwritten - the gas takes the next index instead
def test_gas_joins_a_fee_the_operation_already_bears(prepare_db_fifo, project_root):
    _accounts_and_assets()
    from jal.db.account import JalAccountCreator
    JalAccountCreator(currency_id=2, number='U2', name='Other', investing=1, organization=1).commit()
    transfer = create_transfers([(d2t(220201), 1, 5.0, 2, 5.0, None, '0xsend')])[0]
    JalDB._exec("INSERT INTO fees (operation_id, idx, account_id, symbol_id, amount, kind) "
                "VALUES (:oid, 0, 1, NULL, '1', 0)", [(":oid", transfer)], commit=True)
    _gas_payment(d2t(220201), '0xsend', '0.5')

    _replay_the_migration(project_root)

    assert _fees_of(transfer) == [[1, '', '1', FeeKind.Commission],
                                 [1, symbol_id_for(6, 2), '0.5', FeeKind.Gas]]


# ----------------------------------------------------------------------------------------------------------------------
# The gas that stands alone becomes the event that burned it. Its coin moves into the cost row, which is what frees
# 'symbol_id' to mean the subject - and the subject was never recorded, so it migrates empty.
def test_lone_gas_becomes_an_event_with_its_cost_beneath_it(prepare_db_fifo, project_root):
    _accounts_and_assets()
    gas = _gas_payment(d2t(220201), '0xapprove', '0.5', note='Gas: token approval')

    _replay_the_migration(project_root)

    assert _actions() == [[gas, ChainAction.Authorization, '0xapprove', '', 'Gas: token approval']]
    assert _fees_of(gas) == [[1, symbol_id_for(6, 2), '0.5', FeeKind.Gas]]
    assert JalDB._read("SELECT otype FROM operations WHERE id=:oid", [(":oid", gas)]) == LedgerTransaction.ChainAction
    assert JalDB._read("SELECT COUNT(*) FROM asset_payments WHERE oid=:oid", [(":oid", gas)]) == 0


# The event is read back from the note, which is the only place it was ever written - and the note is TRANSLATED,
# so a ledger kept in Russian has to classify exactly as an English one does.
def test_the_event_is_read_from_the_note_in_either_language(prepare_db_fifo, project_root):
    _accounts_and_assets()
    notes = [('Gas: token approval', ChainAction.Authorization),
             ('Газ: одобрение токена (approval)', ChainAction.Authorization),
             ('Gas: failed transaction (OUT_OF_ENERGY)', ChainAction.FailedTransaction),
             ('Газ: неудавшаяся транзакция', ChainAction.FailedTransaction),
             ('Gas: contract call', ChainAction.ContractCall),
             ('Gas: unstaking', ChainAction.ContractCall)]   # finer than the importer can tell apart is not guessed
    for i, (note, _event) in enumerate(notes):
        _gas_payment(d2t(220201) + i, f'0x{i}', '0.5', note=note)

    _replay_the_migration(project_root)

    assert [row[1] for row in _actions()] == [event for _note, event in notes]


# A rent is not gas: it is locked rather than consumed, and 'kind' is the only place that difference is recorded.
def test_a_token_account_rent_keeps_its_own_kind(prepare_db_fifo, project_root):
    _accounts_and_assets()
    rent = _gas_payment(d2t(220201), '0xsend', '0.002', subtype=_TOKEN_RENT,
                        note='Token account rent locked in 4Nd1...')

    _replay_the_migration(project_root)

    assert [row[1] for row in _actions()] == [ChainAction.TokenAccountRent]
    assert _fees_of(rent) == [[1, symbol_id_for(6, 2), '0.002', FeeKind.Rent]]


# A rent belongs to a send that already carries its own gas, and it does NOT join it: two costs of one transaction,
# one consumed and one locked, so only the consumed one is a fee of the send.
def test_a_rent_stays_an_operation_beside_the_send_that_caused_it(prepare_db_fifo, project_root):
    _accounts_and_assets()
    from jal.db.account import JalAccountCreator
    JalAccountCreator(currency_id=2, number='U2', name='Other', investing=1, organization=1).commit()
    transfer = create_transfers([(d2t(220201), 1, 5.0, 2, 5.0, None, '0xsend')])[0]
    JalDB._exec("INSERT INTO fees (operation_id, idx, account_id, symbol_id, amount, kind) "
                "VALUES (:oid, 0, 1, :symbol, '0.00001', 1)",
                [(":oid", transfer), (":symbol", symbol_id_for(6, 2))], commit=True)
    rent = _gas_payment(d2t(220201), '0xsend', '0.002', subtype=_TOKEN_RENT, note='Token account rent locked in 4Nd1')

    _replay_the_migration(project_root)

    assert len(_fees_of(transfer)) == 1                       # the send keeps its gas and gains nothing
    assert [row[0] for row in _actions()] == [rent]
    assert _fees_of(rent)[0][3] == FeeKind.Rent


# An empty hash is not a link. Two hash-less gas payments would otherwise find each other, or be attached to any
# other hash-less operation, which is how a migration keyed on text invents a relationship that is not in the data.
def test_a_gas_payment_without_a_hash_links_to_nothing(prepare_db_fifo, project_root):
    _accounts_and_assets()
    _reward(d2t(220201), '', 4)
    gas = _gas_payment(d2t(220201), '', '0.5')

    _replay_the_migration(project_root)

    assert [row[0] for row in _actions()] == [gas]
    assert _fees_of(gas) == [[1, symbol_id_for(6, 2), '0.5', FeeKind.Gas]]


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


def test_the_delta_and_the_init_script_declare_the_same_objects(project_root):
    with open(project_root + "/jal/" + Setup.INIT_SCRIPT_PATH) as init:
        from_init = _created_objects(init.read())
    with open(project_root + f"/jal/updates/{Setup.UPDATE_PREFIX}{_MIGRATION_DELTA}.sql") as delta:
        from_delta = _created_objects(delta.read())

    assert len(from_delta) == 7     # the table and six triggers - its own three, and the three it re-states
    for name in from_delta:
        assert name in from_init, f"{name} is created by the delta and by nothing else"
        assert from_delta[name] == from_init[name], name


# The 'asset_payments' triggers are re-stated because the migration has to drop them first, and a delta that dropped
# them without putting them back would leave a database that no longer invalidates its ledger when a payment changes.
def test_the_delta_puts_the_payment_triggers_back(project_root):
    with open(project_root + f"/jal/updates/{Setup.UPDATE_PREFIX}{_MIGRATION_DELTA}.sql") as delta:
        text = delta.read()

    for event in ('delete', 'insert', 'update'):
        assert text.index(f"DROP TRIGGER IF EXISTS asset_payments_after_{event}") \
               < text.index(f"CREATE TRIGGER asset_payments_after_{event}")
