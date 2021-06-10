import os
from shutil import copyfile
import sqlite3
import json

# FIXME fix this import to make tests operational separately
from tests.fixtures import project_root
from constants import Setup
from jal.db.helpers import init_and_check_db, get_dbfilename, LedgerInitError
from jal.db.backup_restore import JalBackup
from jal.data_import.statement_ibkr import StatementIBKR
from jal.db.helpers import executeSQL
from PySide2.QtSql import QSqlDatabase


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


def test_statement_ibkr(tmp_path, project_root):
    # Prepare environment
    src_path = project_root + os.sep + 'jal' + os.sep + Setup.INIT_SCRIPT_PATH
    target_path = str(tmp_path) + os.sep + Setup.INIT_SCRIPT_PATH
    copyfile(src_path, target_path)

    # Activate db connection
    error = init_and_check_db(str(tmp_path) + os.sep)
    assert error.code == LedgerInitError.EmptyDbInitialized
    error = init_and_check_db(str(tmp_path) + os.sep)
    assert error.code == LedgerInitError.DbInitSuccess
    db = QSqlDatabase.database(Setup.DB_CONNECTION)
    assert db.isValid()

    # TODO Make a fixture together with test_statement_json_import()
    assert executeSQL("INSERT INTO agents (pid, name) VALUES (0, 'IB')") is not None
    assert executeSQL("INSERT INTO accounts (type_id, name, currency_id, active, number, organization_id) "
                      "VALUES (4, 'IB TEST', 2, 1, 'U7654321', 1)") is not None
    assert executeSQL("INSERT INTO assets (id, name, type_id, full_name, src_id) "
                      "VALUES (4, 'VUG', 4, 'Growth ETF', 0), "
                      "(5, 'EDV', 4, 'VANGUARD EXTENDED DUR TREAS', 0)") is not None
    assert executeSQL("INSERT INTO dividends (id, timestamp, type, account_id, asset_id, amount, tax, note) "
                      "VALUES (1, 1529612400, 1, 1, 5, 16.76, 1.68, "
                      "'EDV (US9219107094) CASH DIVIDEND USD 0.8381 (Ordinary Dividend)'), "
                      "(2, 1533673200, 1, 1, 5, 20.35, 2.04, "
                      "'EDV(US9219107094) CASH DIVIDEND 0.10175000 USD PER SHARE (Ordinary Dividend)')") is not None

    data_path = project_root + os.sep + "tests" + os.sep + "test_data" + os.sep
    with open(data_path + 'ibkr.json', 'r') as json_file:
        statement = json.load(json_file)

    IBKR = StatementIBKR()
    IBKR.load(data_path + 'ibkr.xml')
    assert IBKR._data == statement
