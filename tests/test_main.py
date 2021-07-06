import os
from shutil import copyfile
import sqlite3

from tests.fixtures import project_root
from constants import Setup
from jal.db.helpers import init_and_check_db, get_dbfilename, LedgerInitError
from jal.db.backup_restore import JalBackup


# ----------------------------------------------------------------------------------------------------------------------
def test_db_creation(tmp_path, project_root):
    # Prepare environment
    src_path = project_root + os.sep + 'jal' + os.sep + Setup.INIT_SCRIPT_PATH
    target_path = str(tmp_path) + os.sep + Setup.INIT_SCRIPT_PATH
    copyfile(src_path, target_path)

    error = init_and_check_db(str(tmp_path) + os.sep)

    # Check that sqlite db file was created
    result_path = str(tmp_path) + os.sep + Setup.DB_PATH
    assert os.path.exists(result_path)
    assert os.path.getsize(result_path) > 0
    assert error.code == LedgerInitError.EmptyDbInitialized

    os.remove(target_path)  # Clean db init script
    os.remove(get_dbfilename(str(tmp_path) + os.sep))  # Clean db file


def test_invalid_backup(tmp_path, project_root):
    # Prepare environment
    src_path = project_root + os.sep + 'jal' + os.sep + Setup.INIT_SCRIPT_PATH
    target_path = str(tmp_path) + os.sep + Setup.INIT_SCRIPT_PATH
    copyfile(src_path, target_path)
    init_and_check_db(str(tmp_path) + os.sep)

    # Here backup is created without parent window - need to use with care
    db_file_name = get_dbfilename(str(tmp_path) + os.sep)
    
    invalid_backup = JalBackup(None, db_file_name)
    invalid_backup.backup_name = project_root + os.sep + "tests" + os.sep + "test_data" + os.sep + "invalid_backup.tgz"
    assert not invalid_backup.validate_backup()

    os.remove(target_path)  # Clean db init script
    os.remove(get_dbfilename(str(tmp_path) + os.sep))  # Clean db file


def test_backup_load(tmp_path, project_root):
    # Prepare environment
    src_path = project_root + os.sep + 'jal' + os.sep + Setup.INIT_SCRIPT_PATH
    target_path = str(tmp_path) + os.sep + Setup.INIT_SCRIPT_PATH
    copyfile(src_path, target_path)
    init_and_check_db(str(tmp_path) + os.sep)

    # Here backup is created without parent window - need to use with care
    db_file_name = get_dbfilename(str(tmp_path) + os.sep)
    backup = JalBackup(None, db_file_name)
    backup.backup_name = project_root + os.sep + "tests" + os.sep + "test_data" + os.sep + "deals_set.tgz"

    assert backup.validate_backup()
    # Check validation
    assert backup._backup_label_date == '2021/01/01 00:00:00+0300'

    backup.do_restore()

    # Check restoration
    db = sqlite3.connect(db_file_name)
    cursor = db.cursor()
    cursor.execute("SELECT COUNT(*) FROM settings")
    assert cursor.fetchone()[0] == 7
    db.close()

    os.remove(target_path)  # Clean db init script
    os.remove(get_dbfilename(str(tmp_path) + os.sep))  # Clean db file
