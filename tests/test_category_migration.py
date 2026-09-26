from decimal import Decimal

import pytest
import sqlparse

from tests.fixtures import project_root, data_path, prepare_db
from jal.constants import PredefinedCategory, PredefinedAccountType
from jal.db.account import JalAccountCreator
from jal.db.db import JalDB
from jal.db.ledger import Ledger
from jal.db.operations import LedgerTransaction

_MIGRATION_FROM = "-- PREDEFINED CATEGORY 'DISCOUNTS' TAKES ID 10"
_MIGRATION_TO = "-- Set new DB schema version"


def _run_migration(project_root):
    with open(project_root + "/jal/updates/jal_delta_79.sql", encoding='utf-8') as delta:
        text = delta.read()
    for statement in sqlparse.split(text[text.index(_MIGRATION_FROM):text.index(_MIGRATION_TO)]):
        if not sqlparse.format(statement, strip_comments=True).strip():
            continue
        assert JalDB._exec(statement.strip(), commit=True) is not None, f"Migration statement failed: {statement}"


def _categories() -> dict:
    query = JalDB._exec("SELECT id, pid, name FROM categories WHERE id>=10")
    rows = {}
    while query.next():
        rows[query.value(0)] = (query.value(1), query.value(2))
    return rows


def _category_of_details() -> list:
    query = JalDB._exec("SELECT category_id FROM action_details ORDER BY id")
    rows = []
    while query.next():
        rows.append(query.value(0))
    return rows


# A database of before the category: the user's own categories start at id 10, one of them named 'Discounts'
@pytest.mark.parametrize("foreign_keys", ["OFF", "ON"])
def test_user_category_10_steps_aside_for_discounts(prepare_db, project_root, foreign_keys):
    JalDB._exec("DELETE FROM categories WHERE id=10", commit=True)
    for row in [(10, 2, 'Home'), (11, 10, 'Paint'), (12, 1, 'Discounts')]:
        JalDB._exec("INSERT INTO categories (id, pid, name) VALUES (:id, :pid, :name)",
                    [(":id", row[0]), (":pid", row[1]), (":name", row[2])], commit=True)
    account = JalAccountCreator(currency_id=2, number='U1', name='Wallet', organization=1,
                                account_type=PredefinedAccountType.Cash).commit().id()
    LedgerTransaction.create_new(LedgerTransaction.IncomeSpending, {
        'timestamp': 1_700_000_000, 'account_id': account, 'peer_id': 1,
        'lines': [{'category_id': 10, 'amount': Decimal('-5')}, {'category_id': 11, 'amount': Decimal('-2')},
                  {'category_id': 12, 'amount': Decimal('1')}]})
    Ledger().rebuild(from_timestamp=0)
    assert JalDB._read("SELECT COUNT(*) FROM ledger WHERE category_id=10") > 0

    JalDB._exec(f"PRAGMA foreign_keys = {foreign_keys}")
    assert JalDB._read("PRAGMA foreign_keys") == (1 if foreign_keys == "ON" else 0)
    _run_migration(project_root)
    JalDB._exec("PRAGMA foreign_keys = ON")

    assert _categories() == {10: (2, 'Discounts'), 11: (13, 'Paint'), 12: (1, 'Discounts (user)'),
                             13: (2, 'Home')}
    assert _category_of_details() == [13, 11, 12]
    assert JalDB._read("SELECT COUNT(*) FROM ledger WHERE category_id=10") == 0
    assert 10 in PredefinedCategory()


def test_fresh_database_has_discounts(prepare_db):
    assert _categories() == {10: (PredefinedCategory.Spending, 'Discounts')}
