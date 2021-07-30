import json

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_ibkr, prepare_db_xls
from jal.data_import.statement_ibkr import StatementIBKR
from jal.data_import.statement_uralsib import StatementUKFU
from jal.data_import.statement_kit import StatementKIT
from jal.data_import.statement_psb import StatementPSB
from jal.data_import.statement_openbroker import StatementOpenBroker


# ----------------------------------------------------------------------------------------------------------------------
def test_statement_ibkr(tmp_path, project_root, data_path, prepare_db_ibkr):
    with open(data_path + 'ibkr.json', 'r') as json_file:
        statement = json.load(json_file)

    IBKR = StatementIBKR()
    IBKR.load(data_path + 'ibkr.xml')
    assert IBKR._data == statement


# ----------------------------------------------------------------------------------------------------------------------
def test_statement_uralsib(tmp_path, project_root, data_path, prepare_db_xls):
    with open(data_path + 'ukfu.json', 'r') as json_file:
        statement = json.load(json_file)

    UKFU = StatementUKFU()
    UKFU.load(data_path + 'ukfu.zip')
    assert UKFU._data == statement


# ----------------------------------------------------------------------------------------------------------------------
def test_statement_kit(tmp_path, project_root, data_path, prepare_db_xls):
    with open(data_path + 'kit.json', 'r') as json_file:
        statement = json.load(json_file)

    KIT = StatementKIT()
    KIT.load(data_path + 'kit.xlsx')
    assert KIT._data == statement


# ----------------------------------------------------------------------------------------------------------------------
def test_statement_psb(tmp_path, project_root, data_path, prepare_db_xls):
    with open(data_path + 'psb.json', 'r') as json_file:
        statement = json.load(json_file)

    PSB = StatementPSB()
    PSB.load(data_path + 'psb.xlsx')
    assert PSB._data == statement

# ----------------------------------------------------------------------------------------------------------------------
def test_statement_open(tmp_path, project_root, data_path, prepare_db_xls):
    with open(data_path + 'open.json', 'r') as json_file:
        statement = json.load(json_file)

    OpenBroker = StatementOpenBroker()
    OpenBroker.load(data_path + 'open.xml')
    assert OpenBroker._data == statement
