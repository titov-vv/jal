import json

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_ibkr, prepare_db_moex
from data_import.broker_statements.ibkr import StatementIBKR
from data_import.broker_statements.tvoy import StatementTvoyBroker
from data_import.broker_statements.kit import StatementKIT
from data_import.broker_statements.just2trade import StatementJ2T
from data_import.broker_statements.vtb import StatementVTB
from jal.data_import.statement import JSF

from constants import PredefinedAsset
from tests.helpers import create_assets


# ----------------------------------------------------------------------------------------------------------------------
# Reads a golden JSF fixture and returns (statement data, expected id map).
# Db matches are stored in the optional 'db_ids' section of the fixture (with string keys as it is JSON).
def load_expected_statement(filename):
    with open(filename, 'r', encoding='utf-8') as json_file:
        expected = json.load(json_file)
    expected_map = {JSF.ACCOUNTS: {}, JSF.ASSETS: {}, JSF.SYMBOLS: {}, JSF.ASSET_PAYMENTS: {}}
    for domain, matches in expected.pop(JSF.DB_IDS, {}).items():
        expected_map[domain] = {int(k): v for k, v in matches.items()}
    return expected, expected_map


# ----------------------------------------------------------------------------------------------------------------------
def test_statement_ibkr(tmp_path, project_root, data_path, prepare_db_ibkr):
    # Test big major things
    statement, expected_map = load_expected_statement(data_path + 'ibkr.json')
    IBKR = StatementIBKR()
    IBKR.load(data_path + 'ibkr.xml')
    assert IBKR._data == statement
    assert IBKR._id_map == expected_map

    # Test rights issue
    statement, expected_map = load_expected_statement(data_path + 'ibkr_rights.json')
    IBKR = StatementIBKR()
    IBKR.load(data_path + 'ibkr_rights.xml')
    assert IBKR._data == statement
    assert IBKR._id_map == expected_map


# ----------------------------------------------------------------------------------------------------------------------
# This test normally generates warning message:
# WARNING  root:tvoy.py:280 Asset transfer was skipped as it will be loaded from the destination account report: Перевод ЦБ с субсчета 12345 на субсчет 54321. Код клиента 01495.
def test_statement_tvoy(tmp_path, project_root, data_path, prepare_db_moex):
    statement, expected_map = load_expected_statement(data_path + 'tvoy.json')
    Tvoy = StatementTvoyBroker()
    Tvoy.load(data_path + 'tvoy.zip')
    assert Tvoy._data == statement
    assert Tvoy._id_map == expected_map


# ----------------------------------------------------------------------------------------------------------------------
def test_statement_kit(tmp_path, project_root, data_path, prepare_db_moex):
    statement, expected_map = load_expected_statement(data_path + 'kit.json')
    KIT = StatementKIT()
    KIT.load(data_path + 'kit.xlsx')
    assert KIT._data == statement
    assert KIT._id_map == expected_map


# ----------------------------------------------------------------------------------------------------------------------
def test_statement_just2trade(tmp_path, project_root, data_path, prepare_db_moex):
    create_assets([('JNJ', 'JOHNSON & JOHNSON', 'US4781601046', 1, PredefinedAsset.Stock, 0)])   # ID = 9

    statement, expected_map = load_expected_statement(data_path + 'j2t.json')
    J2T = StatementJ2T()
    J2T.load(data_path + 'j2t.xlsx')
    assert J2T._data == statement
    assert J2T._id_map == expected_map


# ----------------------------------------------------------------------------------------------------------------------
def test_statement_vtb(tmp_path, project_root, data_path, prepare_db_moex):
    statement, expected_map = load_expected_statement(data_path + 'vtb.json')
    vtb = StatementVTB()
    vtb.load(data_path + 'vtb.xls')
    assert vtb._data == statement
    assert vtb._id_map == expected_map
