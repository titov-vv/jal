import os
import ast
import sys
import subprocess
import pytest
from os.path import dirname, abspath, join

# Top-level directories inside the 'jal' package. A bare "from db.xxx import ..." resolves only when
# the 'jal' directory itself is on sys.path; run.py and the tests import "from jal.db.xxx ..." instead.
JAL_SUBMODULES = {
    'compile_ui', 'constants', 'create_pro', 'data_export', 'data_import', 'db',
    'img', 'languages', 'net', 'reports', 'run_designer', 'ui',
    'universal_cache', 'updates', 'widgets',
}

ROOT_DIR = dirname(dirname(abspath(__file__)))
JAL_DIR = join(ROOT_DIR, 'jal')
TESTS_DIR = join(ROOT_DIR, 'tests')


@pytest.mark.parametrize("top_dir", [JAL_DIR, TESTS_DIR])
def test_no_bare_submodule_imports(top_dir):
    """Every jal/*.py and tests/*.py must import jal modules via the 'jal.' prefix, so that
    the application starts correctly through run.py (jal/ is not on sys.path)."""
    offenders = []
    for cur, _dirs, files in os.walk(top_dir):
        for name in files:
            if not name.endswith('.py'):
                continue
            path = join(cur, name)
            with open(path, encoding='utf-8') as f:
                tree = ast.parse(f.read(), path)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    if node.module.split('.')[0] in JAL_SUBMODULES:
                        offenders.append(f"{path}:{node.lineno}: from {node.module} import ...")
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split('.')[0] in JAL_SUBMODULES:
                            offenders.append(f"{path}:{node.lineno}: import {alias.name}")
    assert not offenders, "Imports missing 'jal.' prefix:\n" + "\n".join(offenders)


def test_application_import_chain():
    """Reproduce run.py's import with a clean path (jal/ NOT on sys.path) to catch
    imports that only resolve under the test harness."""
    env = dict(os.environ)
    env['QT_QPA_PLATFORM'] = 'offscreen'
    env['PYTHONPATH'] = ROOT_DIR  # repo root only -- deliberately not jal/
    result = subprocess.run(
        [sys.executable, '-c', 'from jal.jal import main; from jal.widgets.main_window import MainWindow'],
        cwd=ROOT_DIR, env=env, capture_output=True, text=True,
    )
    assert result.returncode == 0, f"Application import chain failed:\n{result.stderr}"
