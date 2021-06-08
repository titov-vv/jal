import os
from shutil import copyfile
import sqlite3
import json

from pytest import approx

from tests.fixtures import project_root
from constants import Setup
from jal.db.helpers import init_and_check_db, get_dbfilename, LedgerInitError
from jal.db.backup_restore import JalBackup
from jal.db.ledger import Ledger
from jal.data_import.statement_ibkr import StatementIBKR
from jal.data_import.statement import Statement
from jal.db.update import JalDB
from jal.db.helpers import executeSQL, readSQL
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


def test_statement_ibkr(project_root):
    data_path = project_root + os.sep + "tests" + os.sep + "test_data" + os.sep
    with open(data_path + 'ibkr.json', 'r') as json_file:
        statement = json.load(json_file)

    IBKR = StatementIBKR()
    IBKR.load(data_path + 'ibkr.xml')
    assert IBKR._data == statement


def test_statement_json_import(tmp_path, project_root):
    # Prepare environment
    src_path = project_root + os.sep + 'jal' + os.sep + Setup.INIT_SCRIPT_PATH
    target_path = str(tmp_path) + os.sep + Setup.INIT_SCRIPT_PATH
    data_path = project_root + os.sep + "tests" + os.sep + "test_data" + os.sep
    copyfile(src_path, target_path)

    # Activate db connection
    error = init_and_check_db(str(tmp_path) + os.sep)
    assert error.code == LedgerInitError.EmptyDbInitialized
    error = init_and_check_db(str(tmp_path) + os.sep)
    assert error.code == LedgerInitError.DbInitSuccess
    db = QSqlDatabase.database(Setup.DB_CONNECTION)
    assert db.isValid()
    lang_id = JalDB().get_language_id('en')
    assert lang_id == 1

    assert executeSQL("INSERT INTO agents (pid, name) VALUES (0, 'IB')") is not None
    assert executeSQL("INSERT INTO accounts (type_id, name, currency_id, active, number, organization_id) "
                      "VALUES (4, 'IB TEST', 2, 1, 'U7654321', 1)") is not None
    assert executeSQL("INSERT INTO assets (id, name, type_id, full_name, src_id) "
                      "VALUES (4, 'VUG', 4, 'Growth ETF', 0)") is not None

    statement = Statement()
    statement.load(data_path + 'ibkr.json')
    statement.match_db_ids(verbal=False)

    with open(data_path + 'matched.json', 'r') as json_file:
        expected_result = json.load(json_file)

    assert statement._data == expected_result

    statement.import_into_db()

    # validate assets
    test_assets = [
        [1, 'RUB', 1, 'Российский Рубль', '', 0, -1],
        [2, 'USD', 1, 'Доллар США', '', 0, 0],
        [3, 'EUR', 1, 'Евро', '', 0, 0],
        [4, 'VUG', 4, 'Growth ETF', 'US9229087369', 0, 0],
        [5, 'CAD', 1, '', '', 0, -1],
        [6, 'AMZN', 2, 'AMAZON.COM INC', 'US0231351067', 0, 2],
        [7, 'BABA', 2, 'ALIBABA GROUP HOLDING-SP ADR', 'US01609W1027', 0, 2],
        [8, 'D', 2, 'DOMINION ENERGY INC', '', 0, 2],
        [9, 'DM', 2, 'DOMINION ENERGY MIDSTREAM PA', '', 0, 2],
        [10, 'X 6 1/4 03/15/26', 3, 'X 6 1/4 03/15/26', 'US912909AN84', 0, -1],
        [11, 'SPY   200529C00295000', 6, 'SPY 29MAY20 295.0 C', '', 0, -1],
        [12, 'DSKEW', 2, 'DSKEW 27FEB22 11.5 C', 'US23753F1158', 0, 2],
        [13, 'MYL', 2, 'MYLAN NV', 'NL0011031208', 0, -1],
        [14, 'VTRS', 2, 'VIATRIS INC-W/I', 'US92556V1061', 0, 2],
        [15, 'WAB', 2, 'WABTEC CORP', '', 0, 2],
        [16, 'TEF', 2, 'TELEFONICA SA-SPON ADR', 'US8793822086', 0, 2],
        [17, 'EQM', 2, 'EQM MIDSTREAM PARTNERS LP', 'US26885B1008', 0, 2],
        [18, 'ETRN', 2, 'EQUITRANS MIDSTREAM CORP', 'US2946001011', 0, 2],
        [19, 'GE', 2, 'GENERAL ELECTRIC CO', '', 0, 2],
        [20, 'EWLL', 2, 'EWELLNESS HEALTHCARE CORP', 'US30051D1063', 0, -1],
        [21, 'EWLL', 2, 'EWELLNESS HEALTHCARE CORP', 'US30051D2053', 0, -1],
        [22, 'ZROZ', 4, 'PIMCO 25+ YR ZERO CPN US TIF', 'US72201R8824', 0, 2],
        [23, 'AAPL', 2, 'APPLE INC', 'US0378331005', 0, 2],
        [24, 'VLO   200724P00064000', 6, 'VLO 24JUL20 64.0 P', '', 0, -1],
        [25, 'VLO', 2, 'VALERO ENERGY CORP', 'US91913Y1001', 0, 2],
        [26, 'MAC', 2, '', 'US5543821012', 0, 2],
    ]
    assert readSQL("SELECT COUNT(*) FROM assets") == len(test_assets)
    for i, asset in enumerate(test_assets):
        assert readSQL("SELECT * FROM assets WHERE id=:id", [(":id", i + 1)]) == asset

    # validate accounts
    test_accounts = [
        [1, 4, 'IB TEST', 2, 1, 'U7654321', 0, 1, 0],
        [2, 4, 'IB TEST.RUB', 1, 1, 'U7654321', 0, 1, 0],
        [3, 4, 'IB TEST.CAD', 5, 1, 'U7654321', 0, 1, 0],
        [4, 4, 'TEST_ACC.CAD', 5, 1, 'TEST_ACC', 0, 2, 0]
    ]
    assert readSQL("SELECT COUNT(*) FROM accounts") == len(test_accounts)
    for i, account in enumerate(test_accounts):
        assert readSQL("SELECT * FROM accounts WHERE id=:id", [(":id", i+1)]) == account

    # validate peers
    test_peers = [
        [1, 0, 'IB', ''],
        [2, 0, 'Bank for #TEST_ACC', '']
    ]
    assert readSQL("SELECT COUNT(*) FROM agents") == len(test_peers)
    for i, peer in enumerate(test_peers):
        assert readSQL("SELECT * FROM agents WHERE id=:id", [(":id", i + 1)]) == peer

    # validate income/spending
    test_actions = [
        [1, 1, 5, '', -7.96, 0.0, 'BALANCE OF MONTHLY MINIMUM FEE FOR DEC 2019'],
        [2, 2, 5, '', 0.6905565, 0.0, 'COMMISS COMPUTED AFTER TRADE REPORTED (EWLL)'],
        [3, 3, 8, '', 0.5, 0.0, 'RUB CREDIT INT FOR MAY-2020'],
        [4, 4, 6, '', -0.249018, 0.0, 'BABA (ALIBABA GROUP HOLDING-SP ADR) - French Transaction Tax']
    ]
    assert readSQL("SELECT COUNT(amount) FROM action_details") == len(test_actions)
    for i, action in enumerate(test_actions):
        assert readSQL("SELECT * FROM action_details WHERE id=:id", [(":id", i+1)]) == action

    # validate transfers
    test_transfers = [
        [1, 1581322108, 2, 78986.6741, 1581322108, 1, 1234.0, 1, 2.0, '', ''],
        [2, 1590522832, 2, 44.07, 1590522832, 1, 0.621778209, '', '', '', ''],
        [3, 1600374600, 1, 123456.78, 1600374600, 2, 123456.78, '', '', '', 'CASH RECEIPTS / ELECTRONIC FUND TRANSFERS'],
        [4, 1605744000, 1, 1234.0, 1605744000, 1, 1234.0, '', '', '', 'DISBURSEMENT INITIATED BY John Doe']
    ]
    assert readSQL("SELECT COUNT(*) FROM transfers") == len(test_transfers)
    for i, transfer in enumerate(test_transfers):
        assert readSQL("SELECT * FROM transfers WHERE id=:id", [(":id", i+1)]) == transfer

    # validate trades
    test_trades = [
        [1, 1548447900, 1548447900, '', 1, 8, 0.567, 69.2215, 0.0, ''],
        [2, 1579094694, 1579219200, '2661774904', 1, 20, 45000.0, 0.0012, 0.54, ''],
        [3, 1580215513, 1580215513, '2674740000', 1, 4, -1240.0, 54.84, 7.75519312, ''],
        [4, 1580215566, 1580342400, '2674740000', 1, 23, -148.0, 316.68, 1.987792848, ''],
        [5, 1590595065, 1590710400, '2882737839', 1, 10, 2.0, 637.09, 2.0, ''],
        [6, 1592575273, 1592784000, '2931083780', 1, 24, -100.0, 4.54, 1.1058334, ''],
        [7, 1595607600, 1595808000, '2997636969', 1, 24, 100.0, 0.0, 0.0, 'Option assignment'],
        [8, 1595607600, 1595607600, '2997636973', 1, 25, 100.0, 64.0, 0.0, 'Option assignment/exercise'],
        [9, 1603882231, 1604016000, '3183801882', 1, 21, 500000.0, 0.0001, 0.7503675, '']
    ]
    assert readSQL("SELECT COUNT(*) FROM trades") == len(test_trades)
    for i, trade in enumerate(test_trades):
        assert readSQL("SELECT * FROM trades WHERE id=:id", [(":id", i + 1)]) == trade

    # validate asset payments
    test_payments = [
        [1, 1578082800, '', '', 1, 1, 22, 60.2, 6.02, 'ZROZ(US72201R8824) CASH DIVIDEND USD 0.86 PER SHARE (Ordinary Dividend)'],
        [2, 1590595065, '', '2882737839', 2, 1, 10, -25.69, 0.0, 'PURCHASE ACCRUED INT X 6 1/4 03/15/26'],
        [3, 1600128000, '', '', 2, 1, 10, 62.5, 0.0, 'BOND COUPON PAYMENT (X 6 1/4 03/15/26)']
    ]
    assert readSQL("SELECT COUNT(*) FROM dividends") == len(test_payments)
    for i, payment in enumerate(test_payments):
        assert readSQL("SELECT * FROM dividends WHERE id=:id", [(":id", i + 1)]) == payment
