import pytest
import os
from shutil import copyfile
from PySide6.QtSql import QSqlDatabase

from constants import Setup, PredefinedCategory, PredefinedAsset, AssetData, PredefinedAccountType
from jal.db.db import JalDB, JalDBError
from jal.db.account import JalAccount
from jal.db.peer import JalPeer
from jal.db.settings import JalSettings
from jal.db.helpers import get_dbfilename
from tests.helpers import d2t, dt2t, create_assets, create_actions, create_dividends


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
    peer = JalPeer(data={'name': 'Shop', 'parent': 0}, create=True)
    assert peer.id() == 1
    account = JalAccount(
        data={'type': PredefinedAccountType.Cash, 'name': 'Wallet', 'number': 'N/A', 'currency': 1, 'active': 1},
        create=True)
    assert account.id() == 1


@pytest.fixture
def prepare_db_ibkr(prepare_db):
    peer = JalPeer(data={'name': 'IB', 'parent': 0}, create=True)
    assert peer.id() == 1
    account = JalAccount(
        data={'type': PredefinedAccountType.Investment, 'name': 'Inv. Account', 'number': 'U7654321', 'currency': 2,
              'active': 1, 'organization': 1, 'precision': 10},
        create=True)
    assert account.id() == 1
    test_assets = [
        ('VUG', 'Growth ETF', '', 2, PredefinedAsset.ETF, 0),  # ID = 4
        ('EDV', 'VANGUARD EXTENDED DUR TREAS', '', 2, PredefinedAsset.ETF, 0),  # ID = 5
        ('ZROZ', '', 'US72201R8824', 2, PredefinedAsset.ETF, 0)  # ID = 6
    ]
    create_assets(test_assets, data=[(5, 'reg_number', "921910709")])
    dividends = [
        (dt2t(1806212020), 1, 5, 16.76, 1.68, "EDV (US9219107094) CASH DIVIDEND USD 0.8381 (Ordinary Dividend)"),
        (dt2t(1808072020), 1, 5, 20.35, 2.04, "EDV(US9219107094) CASH DIVIDEND 0.10175000 USD PER SHARE (Ordinary Dividend)")
    ]
    create_dividends(dividends)
    yield


@pytest.fixture
def prepare_db_fifo(prepare_db):
    peer = JalPeer(data={'name': 'Test Peer', 'parent': 0}, create=True)
    assert peer.id() == 1
    account = JalAccount(
        data={'type': PredefinedAccountType.Investment, 'name': 'Inv. Account', 'number': 'U7654321', 'currency': 2,
              'active': 1, 'organization': 1},
        create=True)
    assert account.id() == 1
    create_actions([(d2t(201101), 1, 1, [(PredefinedCategory.StartingBalance, 10000.0)])])  # starting balance


@pytest.fixture
def prepare_db_moex(prepare_db):   # Create assets in database to be updated from www.moex.com
    test_assets = [
        ('SBER', '', 'RU0009029540', 1, PredefinedAsset.Stock, 0),   # asset ID 4 - > 7
        ('SiZ1', 'Si-12.11 Контракт на курс доллар-рубль', '', 1, PredefinedAsset.Derivative, 0),
        ('SU26238RMFS4', '', 'RU000A1038V6', 1, PredefinedAsset.Bond, 0),
        ('МКБ 1P2', '', 'RU000A1014H6', 1, PredefinedAsset.Bond, 0),
        ('AFLT', 'АО Аэрофлот', 'RU0009062285', 1, PredefinedAsset.Stock, 0)
    ]
    create_assets(test_assets)
    yield

@pytest.fixture
def prepare_db_taxes(prepare_db):
    peer = JalPeer(data={'name': 'IB', 'parent': 0}, create=True)
    assert peer.id() == 1
    account = JalAccount(
        data={'type': PredefinedAccountType.Investment, 'name': 'Inv. Account', 'number': 'U7654321', 'currency': 2,
              'active': 1, 'organization': 1, 'country': 'us', 'precision': 3},
        create=True)
    assert account.id() == 1
    yield
