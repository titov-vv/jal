import json

from tests.fixtures import project_root, data_path, prepare_db
from jal.data_import.statement_ibkr import StatementIBKR


# ----------------------------------------------------------------------------------------------------------------------
def test_statement_ibkr(tmp_path, project_root, data_path, prepare_db):
    with open(data_path + 'ibkr.json', 'r') as json_file:
        statement = json.load(json_file)

    IBKR = StatementIBKR()
    IBKR.load(data_path + 'ibkr.xml')
    assert IBKR._data == statement
