import sqlparse
from decimal import Decimal

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_taxes
from tests.helpers import d2t, create_assets, create_trades, symbol_id_for
from jal.constants import PredefinedAsset, PredefinedCategory
from jal.db.account import JalAccount
from jal.db.db import JalDB
from jal.db.ledger import Ledger
from jal.db.operations import LedgerTransaction, AssetPayment

_MIGRATION_FROM = "-- THE RATE OF A TRANSFER BETWEEN CURRENCIES"
_MIGRATION_TO = "-- Set new DB schema version"


def _run_migration(project_root):
    with open(project_root + "/jal/updates/jal_delta_85.sql", encoding='utf-8') as delta:
        text = delta.read()
    for statement in sqlparse.split(text[text.index(_MIGRATION_FROM):text.index(_MIGRATION_TO)]):
        if not sqlparse.format(statement, strip_comments=True).strip():
            continue
        assert JalDB._exec(statement.strip(), commit=True) is not None, f"Migration statement failed: {statement}"


def _columns(table) -> list:
    query = JalDB._exec(f"SELECT name FROM pragma_table_info('{table}')")
    names = []
    while query.next():
        names.append(query.value(0))
    return names


def _types_by_note() -> dict:
    query = JalDB._exec("SELECT note, type FROM asset_payments")
    types = {}
    while query.next():
        types[query.value(0)] = query.value(1)
    return types


# A schema-84 database: no c_fx columns, every asset fee stored as AssetFee
def test_delta_85_upgrade(prepare_db_taxes, project_root):
    create_assets([("ERIC", "Ericsson ADR", "US2948216088", 2, PredefinedAsset.Stock, 'se'),     # ID 4
                   ("EPD", "Enterprise Products LP", "US2937921078", 2, PredefinedAsset.Stock, 'us')])   # ID 5
    create_trades(1, [(d2t(240102), d2t(240104), 4, 100, 10.0, 1.0, "B1")])
    notes = {"ERIC(294821608) ADR Fee USD 0.02 PER SHARE - FEE": AssetPayment.DepositaryFee,
             "ERIC(US2948216088) CASH DIVIDEND USD 0.149817 PER SHARE - FEE": AssetPayment.AssetFee,
             "CFD BORROW FEE FOR ERIC (2.5%)": AssetPayment.PositionFinancing,
             "EPD(US2937921078) CASH DIVIDEND - Extra 10% tax due to IRS section 1446": AssetPayment.AssetFee}
    for i, note in enumerate(notes):
        LedgerTransaction.create_new(LedgerTransaction.AssetPayment, {
            'timestamp': d2t(240201) + i, 'type': AssetPayment.AssetFee, 'account_id': 1,
            'symbol_id': symbol_id_for(5 if note.startswith("EPD") else 4), 'amount': '-1', 'tax': '0', 'note': note})
    Ledger().rebuild(from_timestamp=0)
    for table in ('trades_opened', 'trades_closed'):
        JalDB._exec(f"ALTER TABLE {table} DROP COLUMN c_fx", commit=True)
        assert 'c_fx' not in _columns(table)

    _run_migration(project_root)

    assert _types_by_note() == notes
    for table in ('trades_opened', 'trades_closed'):
        assert 'c_fx' in _columns(table)
    assert JalDB._read("SELECT COUNT(*) FROM trades_opened WHERE c_fx!='1'") == 0
    assert JalDB._read("SELECT COUNT(*) FROM trades_opened") > 0
    Ledger().rebuild(from_timestamp=0)   # the new subtypes are booked like any asset fee
    assert JalAccount(1).get_category_turnover(PredefinedCategory.Fees, d2t(240201), d2t(240202)) == Decimal('4')
