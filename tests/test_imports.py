import os
import ast
import sys
import subprocess
from os.path import dirname, abspath, join

# Top-level directories inside the 'jal' package. Historically some modules were
# imported as e.g. "from db.xxx import ..." which works only when the 'jal'
# directory itself is on sys.path (as tests/conftest.py arranges). It breaks the
# real application launch via run.py, where imports must be "from jal.db.xxx ...".
JAL_SUBMODULES = {
    'compile_ui', 'constants', 'create_pro', 'data_export', 'data_import', 'db',
    'img', 'languages', 'net', 'reports', 'run_designer', 'ui',
    'universal_cache', 'updates', 'widgets',
}

ROOT_DIR = dirname(dirname(abspath(__file__)))
JAL_DIR = join(ROOT_DIR, 'jal')


def test_no_bare_submodule_imports():
    """Every jal/*.py must import sibling modules via the 'jal.' prefix, so that
    the application starts correctly through run.py (jal/ is not on sys.path)."""
    offenders = []
    for cur, _dirs, files in os.walk(JAL_DIR):
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
