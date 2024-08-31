import json

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_ibkr, prepare_db_moex
from data_import.broker_statements.ibkr import StatementIBKR
from data_import.broker_statements.tvoy import StatementTvoyBroker
from data_import.broker_statements.kit import StatementKIT
from data_import.broker_statements.just2trade import StatementJ2T
from data_import.broker_statements.open_portfolio import StatementOpenPortfolio
from data_import.broker_statements.vtb import StatementVTB

from constants import PredefinedAsset
from tests.helpers import create_assets


# ----------------------------------------------------------------------------------------------------------------------
def test_statement_ibkr(tmp_path, project_root, data_path, prepare_db_ibkr):
    # Test big major things
    with open(data_path + 'ibkr.json', 'r', encoding='utf-8') as json_file:
        statement = json.load(json_file)
    IBKR = StatementIBKR()
    IBKR.load(data_path + 'ibkr.xml')
    assert IBKR._data == statement

    # Test rights issue
    with open(data_path + 'ibkr_rights.json', 'r', encoding='utf-8') as json_file:
        statement = json.load(json_file)
    IBKR = StatementIBKR()
    IBKR.load(data_path + 'ibkr_rights.xml')
    assert IBKR._data == statement


# ----------------------------------------------------------------------------------------------------------------------
# This test normally generates warning message:
# WARNING  root:tvoy.py:280 Asset transfer was skipped as it will be loaded from the destination account report: Перевод ЦБ с субсчета 12345 на субсчет 54321. Код клиента 01495.
def test_statement_tvoy(tmp_path, project_root, data_path, prepare_db_moex):
    with open(data_path + 'tvoy.json', 'r', encoding='utf-8') as json_file:
        statement = json.load(json_file)
    Tvoy = StatementTvoyBroker()
    Tvoy.load(data_path + 'tvoy.zip')
    assert Tvoy._data == statement


# ----------------------------------------------------------------------------------------------------------------------
def test_statement_kit(tmp_path, project_root, data_path, prepare_db_moex):
    with open(data_path + 'kit.json', 'r', encoding='utf-8') as json_file:
        statement = json.load(json_file)
    KIT = StatementKIT()
    KIT.load(data_path + 'kit.xlsx')
    assert KIT._data == statement


# ----------------------------------------------------------------------------------------------------------------------
def test_statement_just2trade(tmp_path, project_root, data_path, prepare_db_moex):
    create_assets([('JNJ', 'JOHNSON & JOHNSON', 'US4781601046', 1, PredefinedAsset.Stock, 0)])   # ID = 5

    with open(data_path + 'j2t.json', 'r', encoding='utf-8') as json_file:
        statement = json.load(json_file)
    J2T = StatementJ2T()
    J2T.load(data_path + 'j2t.xlsx')
    assert J2T._data == statement


# ----------------------------------------------------------------------------------------------------------------------
def test_statement_open_portfolio(tmp_path, project_root, data_path, prepare_db_moex):
    with open(data_path + 'pof_converted.json', 'r', encoding='utf-8') as json_file:
        statement = json.load(json_file)
    OpenPortfolio = StatementOpenPortfolio()
    OpenPortfolio.load(data_path + 'pof.json')
    assert OpenPortfolio._data == statement


# ----------------------------------------------------------------------------------------------------------------------
def test_statement_vtb(tmp_path, project_root, data_path, prepare_db_moex):
    with open(data_path + 'vtb.json', 'r', encoding='utf-8') as json_file:
        statement = json.load(json_file)
    vtb = StatementVTB()
    vtb.load(data_path + 'vtb.xls')
    assert vtb._data == statement
