import pytest
import os
from shutil import copyfile
from PySide6.QtSql import QSqlDatabase

from constants import Setup, PredefinedCategory, PredefinedAsset, AssetData
from jal.db.db import JalDB, JalDBError
from jal.db.settings import JalSettings
from jal.db.helpers import get_dbfilename
from tests.helpers import create_assets, create_dividends


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
    error = JalDB().init_db(str(tmp_path) + os.sep)
    assert error.code == JalDBError.NoError
    db = QSqlDatabase.database(Setup.DB_CONNECTION)
    assert db.isValid()
    language = JalSettings().getLanguage()
    assert language == "en"

    yield

    db.close()
    os.remove(target_path)  # Clean db init script
    os.remove(get_dbfilename(str(tmp_path) + os.sep))  # Clean db file


@pytest.fixture
def prepare_db_ledger(prepare_db):
    assert JalDB._executeSQL("INSERT INTO agents (pid, name) VALUES (0, 'Shop')") is not None
    assert JalDB._executeSQL("INSERT INTO accounts (type_id, name, currency_id, active) "
                             "VALUES (1, 'Wallet', 1, 1)") is not None


@pytest.fixture
def prepare_db_ibkr(prepare_db):
    assert JalDB._executeSQL("INSERT INTO agents (pid, name) VALUES (0, 'IB')") is not None
    assert JalDB._executeSQL("INSERT INTO accounts (type_id, name, currency_id, active, number, organization_id, precision) "
                             "VALUES (4, 'Inv. Account', 2, 1, 'U7654321', 1, 10)") is not None
    test_assets = [
        (4, 'VUG', 'Growth ETF', '', 2, PredefinedAsset.ETF, 0),
        (5, 'EDV', 'VANGUARD EXTENDED DUR TREAS', '', 2, PredefinedAsset.ETF, 0),
        (6, 'ZROZ', '', 'US72201R8824', 2, PredefinedAsset.ETF, 0)
    ]
    create_assets(test_assets, data=[(5, AssetData.RegistrationCode, "921910709")])
    dividends = [
        (1529612400, 1, 5, 16.76, 1.68, "EDV (US9219107094) CASH DIVIDEND USD 0.8381 (Ordinary Dividend)"),
        (1533673200, 1, 5, 20.35, 2.04, "EDV(US9219107094) CASH DIVIDEND 0.10175000 USD PER SHARE (Ordinary Dividend)")
    ]
    create_dividends(dividends)
    yield


@pytest.fixture
def prepare_db_fifo(prepare_db):
    assert JalDB._executeSQL("INSERT INTO agents (pid, name) VALUES (0, 'Test Peer')") is not None
    assert JalDB._executeSQL("INSERT INTO accounts (type_id, name, currency_id, active, number, organization_id) "
                             "VALUES (4, 'Inv. Account', 2, 1, 'U7654321', 1)") is not None
    # Create starting balance
    assert JalDB._executeSQL("INSERT INTO actions (timestamp, account_id, peer_id) VALUES (1604221200, 1, 1)") is not None
    assert JalDB._executeSQL("INSERT INTO action_details (pid, category_id, amount, note) "
                             "VALUES (1, :category, 10000.0, 'Initial balance')",
                             [(":category", PredefinedCategory.StartingBalance)]) is not None


@pytest.fixture
def prepare_db_xls(prepare_db):
    create_assets([(4, 'AFLT', 'АО Аэрофлот', 'RU0009062285', 1, PredefinedAsset.Stock, 0)])
    yield


@pytest.fixture
def prepare_db_moex(prepare_db):   # Create assets in database to be updated from www.moex.com
    test_assets = [
        (4, 'SBER', '', 'RU0009029540', 1, PredefinedAsset.Stock, 0),
        (5, 'SiZ1', 'Si-12.11 Контракт на курс доллар-рубль', '', 1, PredefinedAsset.Derivative, 0),
        (6, 'SU26238RMFS4', '', 'RU000A1038V6', 1, PredefinedAsset.Bond, 0),
        (7, 'МКБ 1P2', '', 'RU000A1014H6', 1, PredefinedAsset.Bond, 0)
    ]
    create_assets(test_assets)
    yield

@pytest.fixture
def prepare_db_taxes(prepare_db):
    assert JalDB._executeSQL("INSERT INTO agents (pid, name) VALUES (0, 'IB')") is not None
    assert JalDB._executeSQL("INSERT INTO accounts (type_id, name, currency_id, active, number, organization_id, country_id, precision) "
                             "VALUES (4, 'Inv. Account', 2, 1, 'U7654321', 1, 2, 3)") is not None
    yield
