import os
from shutil import copyfile
import sqlite3

from tests.fixtures import project_root
from constants import Setup
from jal.db.helpers import init_and_check_db, get_dbfilename, LedgerInitError
from jal.db.backup_restore import JalBackup
from jal.db.ledger import Ledger


def test_db_creation(tmp_path, project_root):
    # Prepare environment
    src_path = project_root + os.sep + 'jal' + os.sep + Setup.INIT_SCRIPT_PATH
    target_path = str(tmp_path) + os.sep + Setup.INIT_SCRIPT_PATH
    copyfile(src_path, target_path)

    _db, error = init_and_check_db(str(tmp_path) + os.sep)

    # Check that sqlite db file was created
    result_path = str(tmp_path) + os.sep + Setup.DB_PATH
    assert os.path.exists(result_path)
    assert os.path.getsize(result_path) > 0
    assert error.code == LedgerInitError.EmptyDbInitialized


def test_backup_load(tmp_path, project_root):
    test_db_creation(tmp_path, project_root)
    project_root = os.path.dirname(os.path.abspath(os.path.dirname(__file__)))

    # Here backup is created without parent window - need to use with care
    db_file_name = get_dbfilename(str(tmp_path) + os.sep)
    backup = JalBackup(None, db_file_name)
    backup.clean_db()
    backup.backup_name = project_root + os.sep + "tests" + os.sep + "test_data" + os.sep + "deals_set.tgz"
    backup.do_restore()

    # Check
    db = sqlite3.connect(db_file_name)
    cursor = db.cursor()
    cursor.execute("SELECT COUNT(*) FROM settings")
    assert cursor.fetchone()[0] == 7
    db.close()


def test_fifo(tmp_path, project_root):
    test_backup_load(tmp_path, project_root)
    db, error = init_and_check_db(str(tmp_path) + os.sep)

    assert error.code == LedgerInitError.DbInitSuccess

    ledger = Ledger(db)
    ledger.rebuild(from_timestamp=0)

    # Check
    db_file_name = get_dbfilename(str(tmp_path) + os.sep)
    db = sqlite3.connect(db_file_name)
    cursor = db.cursor()
    cursor.execute("SELECT COUNT(*) FROM deals_ext")
    assert cursor.fetchone()[0] == 1
    cursor.execute("SELECT SUM(profit) FROM deals_ext")
    assert cursor.fetchone()[0] == 0
    cursor.execute("SELECT SUM(fee) FROM deals_ext")
    assert cursor.fetchone()[0] == 0
    db.close()
