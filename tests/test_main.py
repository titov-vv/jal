import os
from shutil import copyfile
import sqlite3

from pytest import approx

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


def test_fifo(tmp_path, project_root):
    # Prepare environment
    src_path = project_root + os.sep + 'jal' + os.sep + Setup.INIT_SCRIPT_PATH
    target_path = str(tmp_path) + os.sep + Setup.INIT_SCRIPT_PATH
    copyfile(src_path, target_path)
    init_and_check_db(str(tmp_path) + os.sep)
    db_file_name = get_dbfilename(str(tmp_path) + os.sep)
    backup = JalBackup(None, db_file_name)
    backup.backup_name = project_root + os.sep + "tests" + os.sep + "test_data" + os.sep + "deals_set.tgz"
    backup.do_restore()

    error = init_and_check_db(str(tmp_path) + os.sep)

    assert error.code == LedgerInitError.DbInitSuccess

    ledger = Ledger()
    ledger.rebuild(from_timestamp=0)

    # Check single deal
    db_file_name = get_dbfilename(str(tmp_path) + os.sep)
    db = sqlite3.connect(db_file_name)
    cursor = db.cursor()

    # Check single deal
    cursor.execute("SELECT COUNT(*) FROM deals_ext WHERE asset_id=4")
    assert cursor.fetchone()[0] == 1
    cursor.execute("SELECT SUM(profit) FROM deals_ext WHERE asset_id=4")
    assert cursor.fetchone()[0] == 994
    cursor.execute("SELECT SUM(fee) FROM deals_ext WHERE asset_id=4")
    assert cursor.fetchone()[0] == 6

    # One buy multiple sells
    cursor.execute("SELECT COUNT(*) FROM deals_ext WHERE asset_id=5")
    assert cursor.fetchone()[0] == 2
    cursor.execute("SELECT SUM(profit) FROM deals_ext WHERE asset_id=5")
    assert cursor.fetchone()[0] == -56
    cursor.execute("SELECT SUM(fee) FROM deals_ext WHERE asset_id=5")
    assert cursor.fetchone()[0] == 6

    # Multiple buy one sell
    cursor.execute("SELECT COUNT(*) FROM deals_ext WHERE asset_id=6")
    assert cursor.fetchone()[0] == 2
    cursor.execute("SELECT SUM(profit) FROM deals_ext WHERE asset_id=6")
    assert cursor.fetchone()[0] == -1306
    cursor.execute("SELECT SUM(fee) FROM deals_ext WHERE asset_id=6")
    assert cursor.fetchone()[0] == 6

    # One sell multiple buys
    cursor.execute("SELECT COUNT(*) FROM deals_ext WHERE asset_id=7")
    assert cursor.fetchone()[0] == 2
    cursor.execute("SELECT SUM(profit) FROM deals_ext WHERE asset_id=7")
    assert cursor.fetchone()[0] == -78
    cursor.execute("SELECT SUM(fee) FROM deals_ext WHERE asset_id=7")
    assert cursor.fetchone()[0] == 3

    # Multiple sells one buy
    cursor.execute("SELECT COUNT(*) FROM deals_ext WHERE asset_id=8")
    assert cursor.fetchone()[0] == 2
    cursor.execute("SELECT SUM(profit) FROM deals_ext WHERE asset_id=8")
    assert cursor.fetchone()[0] == 317
    cursor.execute("SELECT SUM(fee) FROM deals_ext WHERE asset_id=8")
    assert cursor.fetchone()[0] == 3

    # Multiple buys and sells
    cursor.execute("SELECT COUNT(*) FROM deals_ext WHERE asset_id=9")
    assert cursor.fetchone()[0] == 11
    cursor.execute("SELECT SUM(profit) FROM deals_ext WHERE asset_id=9")
    assert cursor.fetchone()[0] == 3500
    cursor.execute("SELECT SUM(fee) FROM deals_ext WHERE asset_id=9")
    assert cursor.fetchone()[0] == 0

    # Symbol change
    cursor.execute("SELECT COUNT(*) FROM deals_ext WHERE asset_id=10")
    assert cursor.fetchone()[0] == 1
    cursor.execute("SELECT COUNT(*) FROM deals_ext WHERE asset_id=11")
    assert cursor.fetchone()[0] == 1
    cursor.execute("SELECT profit FROM deals_ext WHERE asset_id=11")
    assert cursor.fetchone()[0] == 1200

    # Spin-off
    cursor.execute("SELECT COUNT(*) FROM deals_ext WHERE asset_id=12")
    assert cursor.fetchone()[0] == 1
    cursor.execute("SELECT profit FROM deals_ext WHERE asset_id=12")
    assert cursor.fetchone()[0] == 0

    # Multiple corp actions
    cursor.execute("SELECT COUNT(*) FROM deals_ext WHERE asset_id=13 AND corp_action IS NOT NULL")
    assert cursor.fetchone()[0] == 1
    cursor.execute("SELECT profit FROM deals_ext WHERE asset_id=13")
    assert cursor.fetchone()[0] == 0
    cursor.execute("SELECT COUNT(*) FROM deals_ext WHERE asset_id=14")
    assert cursor.fetchone()[0] == 3
    cursor.execute("SELECT COUNT(*) FROM deals_ext WHERE asset_id=14 AND corp_action IS NOT NULL")
    assert cursor.fetchone()[0] == 2
    cursor.execute("SELECT profit FROM deals_ext WHERE asset_id=14 AND corp_action IS NULL")
    assert cursor.fetchone()[0] == 75
    cursor.execute("SELECT profit FROM deals_ext WHERE asset_id=14 AND corp_action IS NOT NULL")
    assert cursor.fetchone()[0] == 0
    cursor.execute("SELECT COUNT(*) FROM deals_ext WHERE asset_id=15 AND corp_action IS NOT NULL")
    assert cursor.fetchone()[0] == 1
    cursor.execute("SELECT profit FROM deals_ext WHERE asset_id=15")
    assert cursor.fetchone()[0] == 274

    # Stock dividend
    cursor.execute("SELECT COUNT(*) FROM deals_ext WHERE asset_id=16")
    assert cursor.fetchone()[0] == 3
    cursor.execute("SELECT SUM(profit) FROM deals_ext WHERE asset_id=16")
    assert cursor.fetchone()[0] == approx(1500)
    cursor.execute("SELECT profit FROM deals_ext WHERE asset_id=16 AND close_timestamp=1608454800")
    assert cursor.fetchone()[0] == approx(166.666667)
    cursor.execute("SELECT profit FROM deals_ext WHERE asset_id=16 AND close_timestamp=1608541200")
    assert cursor.fetchone()[0] == approx(1333.333333)

    # Order of buy/sell
    cursor.execute("SELECT COUNT(*) FROM deals_ext WHERE asset_id=17")
    assert cursor.fetchone()[0] == 2
    cursor.execute("SELECT SUM(profit) FROM deals_ext WHERE asset_id=17")
    assert cursor.fetchone()[0] == 140
    cursor.execute("SELECT COUNT(*) FROM deals_ext WHERE asset_id=18")
    assert cursor.fetchone()[0] == 4
    cursor.execute("SELECT SUM(qty) FROM deals_ext WHERE asset_id=18")
    assert cursor.fetchone()[0] == -2
    cursor.execute("SELECT SUM(profit) FROM deals_ext WHERE asset_id=18")
    assert cursor.fetchone()[0] == 200

    # totals
    cursor.execute("SELECT COUNT(*) FROM deals AS d "
                   "LEFT JOIN sequence as os ON os.id = d.open_sid "
                   "LEFT JOIN sequence as cs ON cs.id = d.close_sid")
    assert cursor.fetchone()[0] == 41
    cursor.execute("SELECT COUNT(*) FROM deals AS d "
                   "LEFT JOIN sequence as os ON os.id = d.open_sid "
                   "LEFT JOIN sequence as cs ON cs.id = d.close_sid "
                   "WHERE os.type==3 AND cs.type==3")
    assert cursor.fetchone()[0] == 27
    cursor.execute("SELECT COUNT(*) FROM deals AS d "
                   "LEFT JOIN sequence as os ON os.id = d.open_sid "
                   "LEFT JOIN sequence as cs ON cs.id = d.close_sid "
                   "WHERE os.type!=5 OR cs.type!=5")
    assert cursor.fetchone()[0] == 37
    cursor.execute("SELECT COUNT(*) FROM deals AS d "
                   "LEFT JOIN sequence as os ON os.id = d.open_sid "
                   "LEFT JOIN sequence as cs ON cs.id = d.close_sid "
                   "WHERE os.type==5 AND cs.type==5")
    assert cursor.fetchone()[0] == 4

    # validate final amounts
    cursor.execute("SELECT MAX(sid), asset_id, sum_amount, sum_value FROM ledger_sums "
                   "GROUP BY asset_id")
    ledger_sums = cursor.fetchall()
    for row in ledger_sums:
        if row[1] == 1:    # Checking money amount
            assert row[2] == 16760
        else:
            assert row[2] == 0
        assert row[3] == 0

    db.close()
