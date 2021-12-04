import pytest
import os
from shutil import copyfile
from PySide6.QtSql import QSqlDatabase

from constants import Setup, PredefinedCategory, PredefinedAsset
from jal.db.helpers import init_and_check_db, LedgerInitError
from jal.db.db import JalDB
from jal.db.helpers import executeSQL, get_dbfilename


@pytest.fixture
def project_root() -> str:
    yield os.path.dirname(os.path.abspath(os.path.dirname(__file__)))


@pytest.fixture
def data_path(project_root) -> str:
    yield project_root + os.sep + "tests" + os.sep + "test_data" + os.sep


@pytest.fixture
def prepare_db(project_root, tmp_path, data_path):
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
    lang_id = JalDB().get_language_id('en')
    assert lang_id == 1

    yield

    os.remove(target_path)  # Clean db init script
    os.remove(get_dbfilename(str(tmp_path) + os.sep))  # Clean db file


@pytest.fixture
def prepare_db_ledger(prepare_db):
    assert executeSQL("INSERT INTO agents (pid, name) VALUES (0, 'Shop')") is not None
    assert executeSQL("INSERT INTO accounts (type_id, name, currency_id, active) "
                      "VALUES (1, 'Wallet', 1, 1)") is not None


@pytest.fixture
def prepare_db_ibkr(prepare_db):
    assert executeSQL("INSERT INTO agents (pid, name) VALUES (0, 'IB')") is not None
    assert executeSQL("INSERT INTO accounts (type_id, name, currency_id, active, number, organization_id) "
                      "VALUES (4, 'Inv. Account', 2, 1, 'U7654321', 1)") is not None
    assert executeSQL("INSERT INTO assets (id, name, type_id, full_name, src_id) "
                      "VALUES (4, 'VUG', 4, 'Growth ETF', 0), "
                      "(5, 'EDV', 4, 'VANGUARD EXTENDED DUR TREAS', 0)") is not None
    assert executeSQL("INSERT INTO dividends (id, timestamp, type, account_id, asset_id, amount, tax, note) "
                      "VALUES (1, 1529612400, 1, 1, 5, 16.76, 1.68, "
                      "'EDV (US9219107094) CASH DIVIDEND USD 0.8381 (Ordinary Dividend)'), "
                      "(2, 1533673200, 1, 1, 5, 20.35, 2.04, "
                      "'EDV(US9219107094) CASH DIVIDEND 0.10175000 USD PER SHARE (Ordinary Dividend)')") is not None

    yield


@pytest.fixture
def prepare_db_fifo(prepare_db):
    assert executeSQL("INSERT INTO agents (pid, name) VALUES (0, 'Test Peer')") is not None
    assert executeSQL("INSERT INTO accounts (type_id, name, currency_id, active, number, organization_id) "
                      "VALUES (4, 'Inv. Account', 2, 1, 'U7654321', 1)") is not None
    # Create starting balance
    assert executeSQL("INSERT INTO actions (timestamp, account_id, peer_id) VALUES (1604221200, 1, 1)") is not None
    assert executeSQL("INSERT INTO action_details (pid, category_id, amount, note) "
                      "VALUES (1, :category, 10000.0, 'Initial balance')",
                      [(":category", PredefinedCategory.StartingBalance)]) is not None


@pytest.fixture
def prepare_db_xls(prepare_db):
    assert executeSQL("INSERT INTO assets (id, name, type_id, full_name, isin, src_id) "
                      "VALUES (4, 'AFLT', :stock, 'АО Аэрофлот', 'RU0009062285', 0)",
                      [(":stock", PredefinedAsset.Stock)]) is not None
    yield


@pytest.fixture
def prepare_db_moex(prepare_db):   # Create SBER stock in database to be updated from www.moex.com
    assert executeSQL("INSERT INTO assets (id, name, type_id, full_name, isin, src_id) "
                      "VALUES (4, 'SBER', :stock, '', '', 0)",
                      [(":stock", PredefinedAsset.Stock)]) is not None
    assert executeSQL("INSERT INTO assets (id, name, type_id, full_name, isin, src_id) "
                      "VALUES (5, 'SiZ1', :derivative, 'Si-12.11 Контракт на курс доллар-рубль', '', 0)",
                      [(":derivative", PredefinedAsset.Derivative)]) is not None
    assert executeSQL("INSERT INTO assets (id, name, type_id, full_name, isin, src_id) "
                      "VALUES (6, 'SU26238RMFS4', :bond, '', 'RU000A1038V6', 0)",
                      [(":bond", PredefinedAsset.Bond)]) is not None
    assert executeSQL("INSERT INTO assets (id, name, type_id, full_name, isin, src_id) "
                      "VALUES (7, 'МКБ 1P2', :bond, '', 'RU000A1014H6', 0)",
                      [(":bond", PredefinedAsset.Bond)]) is not None
    yield

