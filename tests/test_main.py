import os
from shutil import copyfile

from constants import Setup
from jal.db.helpers import init_and_check_db

def test_db_creation(tmp_path):
    # Prepare environment
    project_root = os.path.dirname(os.path.abspath(os.path.dirname(__file__)))
    src_path = project_root + os.sep + 'jal' + os.sep + Setup.INIT_SCRIPT_PATH
    target_path = str(tmp_path) + os.sep + Setup.INIT_SCRIPT_PATH
    copyfile(src_path, target_path)

    init_and_check_db(str(tmp_path) + os.sep)

    # Check that sqlite db file was created
    result_path = str(tmp_path) + os.sep + Setup.DB_PATH
    assert os.path.exists(result_path)
    assert os.path.getsize(result_path) > 0
