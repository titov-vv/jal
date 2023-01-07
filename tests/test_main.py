import os
from shutil import copyfile
import sqlite3
from decimal import Decimal

from tests.fixtures import project_root
from constants import Setup
from jal.db.db import JalDB, JalDBError
from jal.db.asset import JalAsset
from jal.db.helpers import get_dbfilename, localize_decimal
from jal.db.backup_restore import JalBackup
from tests.helpers import pop2minor_digits, d2t, dt2t


# ----------------------------------------------------------------------------------------------------------------------
def test_number_formatting():
    assert localize_decimal(Decimal('123.123')) == '123,123'
    assert localize_decimal(Decimal('123.123'), percent=True) == '12\xa0312,3'
    assert localize_decimal(Decimal('1234567890.123456789'), precision=5) == '1\xa0234\xa0567\xa0890,12346'
    assert localize_decimal(Decimal('1234567890.12345678900')) == '1\xa0234\xa0567\xa0890,123456789'
    assert localize_decimal(Decimal('1.234567'), precision=3) == '1,235'
    assert localize_decimal(Decimal('123.1234567'), precision=5) == '123,12346'
    assert localize_decimal(Decimal('1234.123'), precision=5) == '1\xa0234,12300'
    assert localize_decimal(Decimal('120')) == '120'
    assert localize_decimal(Decimal('13000')) == '13\xa0000'


def test_helpers():
    assert pop2minor_digits(12345) == (45, 123)
    assert d2t(230107) == 1673049600
    assert dt2t(1806212020) == 1529612400


# ----------------------------------------------------------------------------------------------------------------------
def test_db_creation(tmp_path, project_root):
    # Prepare environment
    src_path = project_root + os.sep + 'jal' + os.sep + Setup.INIT_SCRIPT_PATH
    target_path = str(tmp_path) + os.sep + Setup.INIT_SCRIPT_PATH
    copyfile(src_path, target_path)

    error = JalDB().init_db(str(tmp_path) + os.sep)

    # Check that sqlite db file was created
    result_path = str(tmp_path) + os.sep + Setup.DB_PATH
    assert os.path.exists(result_path)
    assert os.path.getsize(result_path) > 0
    assert error.code == JalDBError.NoError
    # Verify db encoding
    assert JalAsset(1).name() == 'Российский Рубль'

    # Clean up db
    JalDB.connection().close()
    os.remove(target_path)  # Clean db init script
    os.remove(get_dbfilename(str(tmp_path) + os.sep))  # Clean db file


def test_invalid_backup(tmp_path, project_root):
    # Prepare environment
    src_path = project_root + os.sep + 'jal' + os.sep + Setup.INIT_SCRIPT_PATH
    target_path = str(tmp_path) + os.sep + Setup.INIT_SCRIPT_PATH
    copyfile(src_path, target_path)
    JalDB().init_db(str(tmp_path) + os.sep)

    # Here backup is created without parent window - need to use with care
    db_file_name = get_dbfilename(str(tmp_path) + os.sep)
    
    invalid_backup = JalBackup(None, db_file_name)
    invalid_backup.backup_name = project_root + os.sep + "tests" + os.sep + "test_data" + os.sep + "invalid_backup.tgz"
    assert not invalid_backup.validate_backup()

    # Clean up db
    JalDB.connection().close()
    os.remove(target_path)  # Clean db init script
    os.remove(get_dbfilename(str(tmp_path) + os.sep))  # Clean db file


def test_backup_load(tmp_path, project_root):
    # Prepare environment
    src_path = project_root + os.sep + 'jal' + os.sep + Setup.INIT_SCRIPT_PATH
    target_path = str(tmp_path) + os.sep + Setup.INIT_SCRIPT_PATH
    copyfile(src_path, target_path)
    JalDB().init_db(str(tmp_path) + os.sep)

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

    # Clean up db
    JalDB.connection().close()
    os.remove(target_path)  # Clean db init script
    os.remove(get_dbfilename(str(tmp_path) + os.sep))  # Clean db file
