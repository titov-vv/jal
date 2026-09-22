from decimal import Decimal

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_ledger
from tests.helpers import d2t
from constants import Setup, PredefinedCategory
from jal.db.db import JalDB, JalDBError
from jal.db.operations import LedgerTransaction, IncomeSpending

NUMBER = "503340855:FS 0421/000317"


def _spending(number=None) -> int:
    data = {'timestamp': d2t(260814), 'account_id': 1, 'peer_id': 1,
            'lines': [{'category_id': PredefinedCategory.Fees, 'amount': Decimal('-11.94'), 'note': 'Lidl'}]}
    if number is not None:
        data['number'] = number
    return LedgerTransaction.create_new(LedgerTransaction.IncomeSpending, data).id()


# ----------------------------------------------------------------------------------------------------------------------
def test_number_is_stored_and_found(prepare_db_ledger):
    oid = _spending(NUMBER)
    assert IncomeSpending(oid).number() == NUMBER
    assert IncomeSpending.find_by_number(NUMBER) == oid
    assert IncomeSpending.find_by_number("503340855:FS 0421/000318") == 0


def test_hand_entered_operations_have_no_number(prepare_db_ledger):
    oid = _spending()
    assert IncomeSpending(oid).number() == ''
    assert IncomeSpending.find_by_number('') == 0                  # an empty id never matches a hand-entered row
    assert _spending() != oid                                       # nor does it make two of them duplicates


# The delta is replayed from the shipped file on a database taken back to version 78 by hand
def test_delta_adds_an_empty_number_to_existing_operations(prepare_db_ledger, project_root):
    oid = _spending()
    assert JalDB._exec("ALTER TABLE actions DROP COLUMN number", commit=True) is not None
    JalDB._exec("UPDATE settings SET value=78 WHERE name='SchemaVersion'", commit=True)
    delta = project_root + f"/jal/updates/{Setup.UPDATE_PREFIX}79.sql"
    assert JalDB().run_sql_script(delta).code == JalDBError.NoError
    assert JalDB._read("SELECT value FROM settings WHERE name='SchemaVersion'") == '79'
    assert JalDB._read("SELECT number FROM actions WHERE oid=:oid", [(":oid", oid)]) == ''
    assert IncomeSpending(oid).number() == ''
