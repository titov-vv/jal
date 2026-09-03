import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys
import types
from decimal import Decimal

import pytest
from PySide6.QtWidgets import QMessageBox

from tests.fixtures import project_root, data_path, prepare_db
from jal.constants import Setup   # not 'constants' - it is a separate module object, and this one is monkeypatched
from jal.db.db import JalDB, JalDBError
from jal.db.helpers import format_decimal


# A companion is imported by name from the 'jal.updates' package. Tests put theirs into sys.modules instead of
# writing files into the package - importlib.import_module() returns a module that is already there.
@pytest.fixture
def companions():
    installed = []

    def install(delta: int, update):
        name = f"jal.updates.{Setup.UPDATE_PREFIX}{delta}"
        module = types.ModuleType(name)
        module.update = update
        sys.modules[name] = module
        installed.append(name)

    yield install

    for name in installed:
        sys.modules.pop(name, None)


def _declare(delta: int):
    JalDB._exec("INSERT OR REPLACE INTO settings(name, value) VALUES('RunUpdateScript', :delta)",
                [(":delta", delta)], commit=True)


def _declaration():
    return JalDB._read("SELECT value FROM settings WHERE name='RunUpdateScript'")


# The data a companion converts: values that are stored, but not in the canonical spelling of the database
def _make_amounts():
    JalDB._exec("CREATE TABLE test_amounts (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
    for value in ['3.0', '3800.0', '0.567']:
        JalDB._exec("INSERT INTO test_amounts(value) VALUES(:value)", [(":value", value)], commit=True)


def _amounts() -> list:
    return JalDB._read_to_list("SELECT value FROM test_amounts ORDER BY id")


# Rewrites one row per call, so a failure in the middle leaves the table half converted
def _canonicalize(fail_after=None):
    calls = []

    def update():
        calls.append(len(calls) + 1)
        for row_id, value in JalDB._read_to_list("SELECT id, value FROM test_amounts ORDER BY id"):
            if fail_after is not None and row_id > fail_after:
                raise RuntimeError("update script crashed")
            JalDB._exec("UPDATE test_amounts SET value=:value WHERE id=:id",
                        [(":value", format_decimal(Decimal(value))), (":id", row_id)], commit=True)

    return update, calls


# ----------------------------------------------------------------------------------------------------------------------
def test_companion_runs_once(prepare_db, companions):
    update, calls = _canonicalize()
    companions(99, update)
    _make_amounts()
    _declare(99)

    assert JalDB()._run_update_script().code == JalDBError.NoError
    assert calls == [1]
    assert _amounts() == ['3', '3.8E+3', '0.567']
    assert _declaration() is None

    # Nothing declared any longer - the script isn't run at the next start
    assert JalDB()._run_update_script().code == JalDBError.NoError
    assert calls == [1]


def test_companion_failure_keeps_declaration(prepare_db, companions):
    update, calls = _canonicalize(fail_after=1)
    companions(99, update)
    _make_amounts()
    _declare(99)

    error = JalDB()._run_update_script()
    assert error.code == JalDBError.UpdateScriptFailure
    assert f"{Setup.UPDATE_PREFIX}99" in error.details
    assert calls == [1]
    assert _amounts() == ['3', '3800.0', '0.567']   # the conversion stopped in the middle of the table
    assert _declaration() == '99'                   # ... so the next start has to run it again


def test_interrupted_companion_is_rerun(prepare_db, companions):
    crashing, _ = _canonicalize(fail_after=1)
    companions(99, crashing)
    _make_amounts()
    _declare(99)
    assert JalDB()._run_update_script().code == JalDBError.UpdateScriptFailure

    # The fixed script runs again over the half-converted table
    update, calls = _canonicalize()
    companions(99, update)
    assert JalDB()._run_update_script().code == JalDBError.NoError
    assert calls == [1]
    assert _amounts() == ['3', '3.8E+3', '0.567']
    assert _declaration() is None

    # And it is idempotent - a run over converted data changes nothing
    _declare(99)
    assert JalDB()._run_update_script().code == JalDBError.NoError
    assert calls == [1, 2]
    assert _amounts() == ['3', '3.8E+3', '0.567']


def test_leftover_declaration_is_drained_on_start(prepare_db, companions, tmp_path, project_root):
    update, calls = _canonicalize()
    companions(99, update)
    _make_amounts()
    _declare(99)   # an upgrade that died between the delta and its companion

    assert JalDB().init_db().code == JalDBError.NoError
    assert calls == [1]
    assert _amounts() == ['3', '3.8E+3', '0.567']
    assert _declaration() is None


# Records what every companion of 'deltas' saw when it ran, and writes a .sql for each of them that bumps the
# schema version and declares that companion - the shape of a delta that needs code.
def _fake_deltas(deltas, path, companions) -> list:
    path.mkdir()
    executed = []
    for delta in deltas:
        (path / f"{Setup.UPDATE_PREFIX}{delta}.sql").write_text(
            "BEGIN TRANSACTION;\n"
            f"UPDATE settings SET value={delta} WHERE name='SchemaVersion';\n"
            f"INSERT OR REPLACE INTO settings(name, value) VALUES('RunUpdateScript', {delta});\n"
            "COMMIT;\n")

        def update(delta=delta):
            # A companion runs with the schema of its own delta already in place
            executed.append((delta, JalDB._read("SELECT value FROM settings WHERE name='SchemaVersion'")))
        companions(delta, update)
    return executed


# Two deltas applied in one upgrade run: each companion has to run right after its own delta, because the
# declaration is a single settings row that the next delta overwrites.
def test_every_delta_of_an_upgrade_runs_its_own_companion(prepare_db, companions, tmp_path, monkeypatch):
    first, last = Setup.DB_REQUIRED_VERSION + 1, Setup.DB_REQUIRED_VERSION + 2
    executed = _fake_deltas([first, last], tmp_path / Setup.UPDATES_PATH, companions)

    monkeypatch.setattr(JalDB, 'get_app_path', staticmethod(lambda: str(tmp_path) + os.sep))
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args, **kwargs: QMessageBox.Yes)
    monkeypatch.setattr(Setup, 'DB_REQUIRED_VERSION', last)

    assert JalDB().update_db_schema().code == JalDBError.NoError
    assert executed == [(first, str(first)), (last, str(last))]
    assert _declaration() is None


# A companion left pending by a crash is finished before the upgrade that follows applies its first delta -
# otherwise that delta's own declaration would overwrite the pending one and the script would be lost.
def test_leftover_companion_runs_before_the_next_delta(prepare_db, companions, tmp_path, monkeypatch):
    interrupted = Setup.DB_REQUIRED_VERSION
    first, last = interrupted + 1, interrupted + 2
    executed = _fake_deltas([interrupted, first, last], tmp_path / Setup.UPDATES_PATH, companions)
    _declare(interrupted)   # the crash: delta 'interrupted' is committed, its companion never ran

    monkeypatch.setattr(JalDB, 'get_app_path', staticmethod(lambda: str(tmp_path) + os.sep))
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args, **kwargs: QMessageBox.Yes)
    monkeypatch.setattr(Setup, 'DB_REQUIRED_VERSION', last)

    assert JalDB().init_db().code == JalDBError.OutdatedDbSchema
    assert executed == [(interrupted, str(interrupted))]   # drained on start, before any new delta
    assert JalDB().update_db_schema().code == JalDBError.NoError
    assert executed == [(interrupted, str(interrupted)), (first, str(first)), (last, str(last))]
    assert _declaration() is None


# A step that fails stops the upgrade: neither the rest of its own delta's work nor any later delta runs
def test_failed_companion_stops_the_upgrade(prepare_db, companions, tmp_path, monkeypatch):
    first, last = Setup.DB_REQUIRED_VERSION + 1, Setup.DB_REQUIRED_VERSION + 2
    executed = _fake_deltas([last], tmp_path / Setup.UPDATES_PATH, companions)
    (tmp_path / Setup.UPDATES_PATH / f"{Setup.UPDATE_PREFIX}{first}.sql").write_text(
        "BEGIN TRANSACTION;\n"
        f"UPDATE settings SET value={first} WHERE name='SchemaVersion';\n"
        f"INSERT OR REPLACE INTO settings(name, value) VALUES('RunUpdateScript', {first});\n"
        "COMMIT;\n")

    def crash():
        raise RuntimeError("update script crashed")
    companions(first, crash)

    monkeypatch.setattr(JalDB, 'get_app_path', staticmethod(lambda: str(tmp_path) + os.sep))
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args, **kwargs: QMessageBox.Yes)
    monkeypatch.setattr(Setup, 'DB_REQUIRED_VERSION', last)

    assert JalDB().update_db_schema().code == JalDBError.UpdateScriptFailure
    assert executed == []                                            # the delta after the failed step never ran
    assert JalDB._read("SELECT value FROM settings WHERE name='SchemaVersion'") == str(first)
    assert _declaration() == str(first)                              # ... and the failed step is still pending
