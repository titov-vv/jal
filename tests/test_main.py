import os
from shutil import copyfile
import sqlite3

from tests.fixtures import fill_deals, project_root
from constants import Setup
from jal.db.helpers import init_and_check_db, get_dbfilename
from jal.db.backup_restore import JalBackup


def test_db_creation(tmp_path, project_root):
    # Prepare environment
    src_path = project_root + os.sep + 'jal' + os.sep + Setup.INIT_SCRIPT_PATH
    target_path = str(tmp_path) + os.sep + Setup.INIT_SCRIPT_PATH
    copyfile(src_path, target_path)

    init_and_check_db(str(tmp_path) + os.sep)

    # Check that sqlite db file was created
    result_path = str(tmp_path) + os.sep + Setup.DB_PATH
    assert os.path.exists(result_path)
    assert os.path.getsize(result_path) > 0


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


def test_fifo(fill_deals):
    pass
