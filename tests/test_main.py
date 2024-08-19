import os
from shutil import copyfile
import sqlite3
from decimal import Decimal
from datetime import datetime, timezone

from tests.fixtures import project_root
from constants import Setup
from jal.db.db import JalDB, JalDBError
from jal.db.settings import JalSettings
from jal.db.asset import JalAsset
from jal.db.helpers import localize_decimal
from jal.widgets.helpers import is_english
from jal.db.backup_restore import JalBackup
from tests.helpers import pop2minor_digits, d2t, d2dt, dt2t


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
    assert localize_decimal(Decimal('-1.23E-8')) == '-0,0000000123'
    assert localize_decimal(Decimal('9.76E-8'), sign=True) == '+0,0000000976'
    assert localize_decimal(Decimal('-321.0')) == '-321'


def test_helpers():
    assert pop2minor_digits(12345) == (45, 123)
    assert d2t(230107) == 1673049600
    assert d2dt(240501) == datetime(2024, 5, 1, tzinfo=timezone.utc)
    assert dt2t(1806212020) == 1529612400
    assert is_english("asdfAF12!@#") == True
    assert is_english("asdfБF12!@#") == False
    assert is_english("asгfAF12!@#") == False


# ----------------------------------------------------------------------------------------------------------------------
def test_db_creation(tmp_path, project_root):
    # Prepare environment
    os.environ['JAL_TEST_PATH'] = str(tmp_path)
    src_path = project_root + os.sep + 'jal' + os.sep + Setup.INIT_SCRIPT_PATH
    target_path = str(tmp_path) + os.sep + Setup.INIT_SCRIPT_PATH
    copyfile(src_path, target_path)

    error = JalDB().init_db()

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
    os.remove(JalSettings.path(JalSettings.PATH_DB_FILE))  # Clean db file


def test_invalid_backup(tmp_path, project_root):
    # Prepare environment
    os.environ['JAL_TEST_PATH'] = str(tmp_path)
    src_path = project_root + os.sep + 'jal' + os.sep + Setup.INIT_SCRIPT_PATH
    target_path = str(tmp_path) + os.sep + Setup.INIT_SCRIPT_PATH
    copyfile(src_path, target_path)
    JalDB().init_db()

    invalid_backup = JalBackup(None)
    invalid_backup.backup_name = project_root + os.sep + "tests" + os.sep + "test_data" + os.sep + "invalid_backup.tgz"
    assert not invalid_backup.validate_backup()

    # Clean up db
    JalDB.connection().close()
    os.remove(target_path)  # Clean db init script
    os.remove(JalSettings.path(JalSettings.PATH_DB_FILE))  # Clean db file


def test_backup_load(tmp_path, project_root):
    # Prepare environment
    os.environ['JAL_TEST_PATH'] = str(tmp_path)
    src_path = project_root + os.sep + 'jal' + os.sep + Setup.INIT_SCRIPT_PATH
    target_path = str(tmp_path) + os.sep + Setup.INIT_SCRIPT_PATH
    copyfile(src_path, target_path)
    JalDB().init_db()

    # Here backup is created without parent window - need to use with care of 'file' member variable
    db_file_name = str(tmp_path) + os.sep + Setup.DB_PATH
    backup = JalBackup(None)
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
    os.remove(JalSettings.path(JalSettings.PATH_DB_FILE))  # Clean db file
