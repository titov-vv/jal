import json
import pytest

from PySide6.QtWidgets import QMessageBox

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_ibkr, prepare_db_moex
from data_import.broker_statements.ibkr import StatementIBKR
from data_import.broker_statements.tvoy import StatementTvoyBroker
from data_import.broker_statements.kit import StatementKIT
from data_import.broker_statements.just2trade import StatementJ2T
from data_import.broker_statements.vtb import StatementVTB
from jal.data_import.statement import JSF, Statement
from jal.db.db import JalDB

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
# tests/test_data/vtb.xls dates from commit cffb14b0 (2025-01-11). Since then vtb.py was patched several times due to
# VTB export changes - header text/offsets, date typing, dividend parsing, asset-skip logic etc.
# Skipped until a current VTB statement is available to re-record vtb.xls + vtb.json.
@pytest.mark.skip(reason="vtb.xls fixture doesn't match current VTB exprot format; needs an update based on a current statement")
def test_statement_vtb(tmp_path, project_root, data_path, prepare_db_moex):
    statement, expected_map = load_expected_statement(data_path + 'vtb.json')
    vtb = StatementVTB()
    vtb.load(data_path + 'vtb.xls')
    assert vtb._data == statement
    assert vtb._id_map == expected_map


# ----------------------------------------------------------------------------------------------------------------------
# The spelling of a stored amount is part of the duplicate key: locate_operation() matches the 'validation' fields
# of an operation as text, so a producer that writes '3800.0' where another writes '3.8E+3' never recognizes what is
# already stored and books the same statement twice. These two tests are the guard for the migration of the importers
# onto Decimal - one for the XLS family, one for the JSF file reader - and must keep passing at every step of it.
# 'actions' (income/spending) are deliberately not counted: LedgerTransaction.IncomeSpending declares no
# 'validation' field at all, so it has no duplicate detection and a re-import doubles it - which is what the
# database does today and is not what these tests are about.
def _operation_counts() -> dict:
    tables = ['trades', 'transfers', 'asset_payments', 'asset_actions']
    return {table: JalDB._read(f"SELECT COUNT(*) FROM {table}") for table in tables}


def _import_statement(statement_class, filename):
    statement = statement_class()
    statement.load(filename)
    statement.validate_format()
    statement.match_db_ids()
    statement.import_into_db()


def test_reimport_creates_nothing_xls(tmp_path, project_root, data_path, prepare_db_moex, monkeypatch):
    # Re-importing a period that is already covered is what the test is about, and that asks the user to confirm
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args, **kwargs: QMessageBox.Yes)
    _import_statement(StatementKIT, data_path + 'kit.xlsx')
    imported = _operation_counts()
    assert sum(imported.values()) > 0
    _import_statement(StatementKIT, data_path + 'kit.xlsx')
    assert _operation_counts() == imported


def test_reimport_creates_nothing_jsf(tmp_path, project_root, data_path, prepare_db_ibkr, monkeypatch):
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args, **kwargs: QMessageBox.Yes)
    _import_statement(Statement, data_path + 'ibkr.json')
    imported = _operation_counts()
    assert sum(imported.values()) > 0
    _import_statement(Statement, data_path + 'ibkr.json')
    assert _operation_counts() == imported
