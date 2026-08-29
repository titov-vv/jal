# Points a standalone jal process at the throw-away demo database instead of the user's real ledger.
# JalDB.get_db_path() honours JAL_TEST_PATH only under pytest, so the redirection has to go through
# the jal.ini that it reads from QStandardPaths.ConfigLocation - hence the private XDG_CONFIG_HOME.
import os
import sys

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
DEMO_DIR = os.path.join(TOOLS_DIR, "demo")          # throw-away database, not published
CONFIG_DIR = os.path.join(DEMO_DIR, "config")
REPO_DIR = os.path.dirname(os.path.dirname(TOOLS_DIR))
DOCS_DIR = os.path.join(REPO_DIR, "docs")                # the published documentation tree
MANUAL_DIR = os.path.join(DOCS_DIR, "manual")           # the user manual the pictures belong to


def prepare_environment(offscreen: bool = True, subdir: str = '') -> None:
    database_dir = os.path.join(DEMO_DIR, subdir) if subdir else DEMO_DIR
    os.makedirs(database_dir, exist_ok=True)
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(os.path.join(CONFIG_DIR, "jal.ini"), 'w') as ini:
        ini.write(f"[main]\ndatabase_path = {database_dir}\n")
    os.environ['XDG_CONFIG_HOME'] = CONFIG_DIR
    os.environ['TZ'] = 'Europe/Berlin'      # demo data is written and read on one and the same clock
    if offscreen:
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    os.environ.setdefault('LOGLEVEL', 'WARNING')
    if REPO_DIR not in sys.path:
        sys.path.insert(0, REPO_DIR)


# The path the application has actually resolved, checked against the one this process asked for. Anything that
# writes or deletes a database file must go through it: a stale jal.ini would otherwise point at another database
# - in the worst case at the real ledger - and the operation would hit the wrong file without a word.
def assert_demo_database(subdir: str = '') -> str:
    from jal.db.settings import JalSettings
    path = JalSettings.path(JalSettings.PATH_DB_FILE)
    expected = os.path.join(DEMO_DIR, subdir, "jal.sqlite") if subdir else os.path.join(DEMO_DIR, "jal.sqlite")
    if path != expected:
        raise RuntimeError(f"Refusing to run: database resolved to '{path}', expected '{expected}'")
    return path
