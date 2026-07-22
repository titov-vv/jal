from decimal import Decimal

import pytest
import sqlparse

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, create_actions
from constants import PredefinedCategory, PredefinedAccountType, Setup
from jal.db.db import JalDB
from jal.db.ledger import Ledger
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.deposit import JalDepositBox

# Where the term-deposit migration starts and ends inside the delta. It is run from the shipped file rather than
# copied here, so this test breaks if the migration text stops doing what it says.
_MIGRATION_FROM = "-- TERM DEPOSITS BECOME ACCOUNTS"
_MIGRATION_TO = "-- New operation: conversions"

# The old term deposit format: the tables the migration consumes, as they looked in schema version 60.
_OLD_SCHEMA = """
CREATE TABLE term_deposits (
    oid        INTEGER PRIMARY KEY UNIQUE NOT NULL,
    otype      INTEGER NOT NULL DEFAULT (6),
    account_id INTEGER NOT NULL REFERENCES accounts (id) ON DELETE CASCADE ON UPDATE CASCADE,
    note       TEXT
);
CREATE TABLE deposit_actions (
    id          INTEGER PRIMARY KEY UNIQUE NOT NULL,
    deposit_id  INTEGER REFERENCES term_deposits (oid) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
    timestamp   INTEGER NOT NULL,
    action_type INTEGER NOT NULL,
    amount      TEXT    NOT NULL
);
"""

# DepositActions values of the retired format
_OPENING, _TOPUP, _INTEREST, _TAX, _WITHDRAWAL, _CLOSING = 1, 2, 50, 51, 99, 100


def _run_migration(project_root):
    with open(project_root + "/jal/updates/jal_delta_61.sql") as delta:
        text = delta.read()
    start, end = text.index(_MIGRATION_FROM), text.index(_MIGRATION_TO)
    for statement in sqlparse.split(text[start:end]):
        if not sqlparse.format(statement, strip_comments=True).strip():
            continue   # a run of comment lines is not a statement
        assert JalDB._exec(statement.strip()) is not None, f"Migration statement failed: {statement}"


def _make_deposit(oid, account_id, note, actions):
    JalDB._exec("INSERT INTO term_deposits (oid, otype, account_id, note) VALUES (:oid, 6, :account, :note)",
                [(":oid", oid), (":account", account_id), (":note", note)])
    for index, (timestamp, action_type, amount) in enumerate(actions):
        JalDB._exec("INSERT INTO deposit_actions (deposit_id, timestamp, action_type, amount) "
                    "VALUES (:deposit, :timestamp, :type, :amount)",
                    [(":deposit", oid), (":timestamp", timestamp), (":type", action_type), (":amount", str(amount))])


@pytest.fixture
def prepare_old_deposits(prepare_db):
    account = JalAccountCreator(currency_id=2, number='B1234567', name='Bank account',
                               organization=1, account_type=PredefinedAccountType.Bank).commit()
    assert account.id() == 1
    create_actions([(d2t(210101), 1, 1, [(PredefinedCategory.StartingBalance, 10000.0)])])
    for statement in sqlparse.split(_OLD_SCHEMA):
        if statement.strip():
            assert JalDB._exec(statement.strip()) is not None
    yield account


# ----------------------------------------------------------------------------------------------------------------------
# A closed deposit becomes an inactive box whose money went in and came back out, leaving the bank account exactly
# where the retired operation left it: richer by the interest, poorer by the tax withheld from it.
def test_migrated_deposit_reproduces_the_money(prepare_old_deposits):
    t_open, t_top, t_interest, t_close = d2t(210201), d2t(210301), d2t(210401), d2t(210501)
    _make_deposit(1, 1, "Deposit A", [
        (t_open, _OPENING, '1000'), (t_top, _TOPUP, '500'),
        (t_interest, _INTEREST, '60'), (t_interest, _TAX, '10'),
        (t_close, _CLOSING, '1550')])
    _run_migration(_project_root())
    JalAccount.db_cache.clear_cache()
    Ledger().rebuild(from_timestamp=0)

    boxes = JalAccount.get_all_accounts(active_only=False, include_hidden=True)
    box = [x for x in boxes if x.account_type() == PredefinedAccountType.Deposit]
    assert len(box) == 1 and box[0].name() == "Deposit A"
    assert not box[0].is_active()                     # emptied, so it is out of every default view
    assert box[0].currency() == 2 and box[0].organization() == 1

    deposit = JalDepositBox(box[0].id())
    assert deposit.balance(t_top) == Decimal('1500')
    assert deposit.balance(t_interest) == Decimal('1550')
    assert deposit.balance(t_close) == Decimal('0')
    assert deposit.accrued_interest(t_close) == Decimal('50')
    assert deposit.end_date() == t_close
    # 10000 - 1000 - 500 + 1550 = 10050, i.e. up by the interest net of tax - what the old operation produced too
    assert JalAccount(1).get_asset_amount(t_close, 2) == Decimal('10050')


# The closing amount stored on the old action was unreliable; the ledger always moved the balance the deposit had
# actually accumulated, and the migration has to keep doing that - not trust the recorded number.
def test_migration_closes_with_the_accumulated_balance(prepare_old_deposits):
    t_open, t_interest, t_close = d2t(210201), d2t(210401), d2t(210501)
    _make_deposit(1, 1, "Deposit B", [
        (t_open, _OPENING, '1000'), (t_interest, _INTEREST, '54'),
        (t_close, _CLOSING, '1000')])                 # says 1000, but 1054 had accumulated
    _run_migration(_project_root())
    JalAccount.db_cache.clear_cache()
    Ledger().rebuild(from_timestamp=0)

    box = [x for x in JalAccount.get_all_accounts(active_only=False, include_hidden=True)
           if x.account_type() == PredefinedAccountType.Deposit][0]
    assert JalDepositBox(box.id()).balance(t_close) == Decimal('0')
    assert JalAccount(1).get_asset_amount(t_close, 2) == Decimal('10054')


# A running deposit - the old format demanded a closing action even for one, so it was recorded far in the future.
# Such a box has to stay open, with its money still in it.
def test_migration_keeps_a_running_deposit_open(prepare_old_deposits):
    t_open, t_far_future = d2t(210201), Setup.MAX_TIMESTAMP - 1
    _make_deposit(1, 1, "Deposit C", [(t_open, _OPENING, '1000'), (t_far_future, _CLOSING, '0')])
    _run_migration(_project_root())
    JalAccount.db_cache.clear_cache()
    Ledger().rebuild(from_timestamp=0)

    box = [x for x in JalAccount.get_all_accounts(active_only=False, include_hidden=True)
           if x.account_type() == PredefinedAccountType.Deposit][0]
    assert box.is_active()
    assert JalDepositBox(box.id()).balance(d2t(210301)) == Decimal('1000')
    assert [x.id() for x in JalDepositBox.get_deposits(d2t(210301))] == [box.id()]


# Two deposits that were named the same become two boxes with distinguishable names - an account name is unique.
def test_migration_makes_names_unique(prepare_old_deposits):
    t_open, t_close = d2t(210201), d2t(210501)
    _make_deposit(1, 1, "Same name", [(t_open, _OPENING, '100'), (t_close, _CLOSING, '100')])
    _make_deposit(2, 1, "Same name", [(t_open, _OPENING, '200'), (t_close, _CLOSING, '200')])
    _run_migration(_project_root())
    JalAccount.db_cache.clear_cache()

    names = sorted(x.name() for x in JalAccount.get_all_accounts(active_only=False, include_hidden=True)
                   if x.account_type() == PredefinedAccountType.Deposit)
    assert names == ["Same name #1", "Same name #2"]


# A partial withdrawal takes money out without ending the deposit, and the closing then returns only what is left.
def test_migration_handles_a_partial_withdrawal(prepare_old_deposits):
    t_open, t_take, t_close = d2t(210201), d2t(210301), d2t(210501)
    _make_deposit(1, 1, "Deposit F", [
        (t_open, _OPENING, '1000'), (t_take, _WITHDRAWAL, '400'), (t_close, _CLOSING, '600')])
    _run_migration(_project_root())
    JalAccount.db_cache.clear_cache()
    Ledger().rebuild(from_timestamp=0)

    box = [x for x in JalAccount.get_all_accounts(active_only=False, include_hidden=True)
           if x.account_type() == PredefinedAccountType.Deposit][0]
    deposit = JalDepositBox(box.id())
    assert deposit.balance(t_take) == Decimal('600')
    assert deposit.balance(t_close) == Decimal('0')
    assert JalAccount(1).get_asset_amount(t_close, 2) == Decimal('10000')   # nothing was earned or lost


# A tax that had no interest to pair with becomes a spending of its own instead of being dropped.
def test_migration_keeps_a_lonely_tax(prepare_old_deposits):
    t_open, t_tax, t_close = d2t(210201), d2t(210401), d2t(210501)
    _make_deposit(1, 1, "Deposit D", [
        (t_open, _OPENING, '1000'), (t_tax, _TAX, '15'), (t_close, _CLOSING, '985')])
    _run_migration(_project_root())
    JalAccount.db_cache.clear_cache()
    Ledger().rebuild(from_timestamp=0)

    box = [x for x in JalAccount.get_all_accounts(active_only=False, include_hidden=True)
           if x.account_type() == PredefinedAccountType.Deposit][0]
    assert box.get_category_turnover(PredefinedCategory.Taxes, 0, t_close) == Decimal('15')
    assert box.get_category_turnover(PredefinedCategory.Interest, 0, t_close) == Decimal('0')
    assert JalAccount(1).get_asset_amount(t_close, 2) == Decimal('9985')


# The retired tables and their triggers are gone once the migration ran
def test_migration_drops_the_old_tables(prepare_old_deposits):
    _make_deposit(1, 1, "Deposit E", [(d2t(210201), _OPENING, '100'), (d2t(210501), _CLOSING, '100')])
    _run_migration(_project_root())
    for table in ('term_deposits', 'deposit_actions', '_deposit_migration', '_deposit_closing', '_deposit_income'):
        assert JalDB._read("SELECT name FROM sqlite_master WHERE type='table' AND name=:name",
                           [(":name", table)]) is None


def _project_root() -> str:
    import os
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
