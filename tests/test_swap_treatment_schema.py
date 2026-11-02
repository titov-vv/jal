import pytest
import sqlparse

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_fifo
from tests.helpers import d2t, create_stocks, create_trades, create_quotes, create_swaps
from jal.db.db import JalDB
from jal.db.ledger import Ledger

_PEGGED_TO = 8   # AssetData.PeggedTo
_MIGRATION_FROM = "-- SWAP TREATMENT: AUTO / SALE / CONVERSION"
_MIGRATION_TO = "-- Set new DB schema version"
_PEG_TRIGGERS = ['asset_data_peg_after_delete', 'asset_data_peg_after_insert', 'asset_data_peg_after_update']


def _run_migration(project_root):
    with open(project_root + "/jal/updates/jal_delta_84.sql", encoding='utf-8') as delta:
        text = delta.read()
    for statement in sqlparse.split(text[text.index(_MIGRATION_FROM):text.index(_MIGRATION_TO)]):
        if not sqlparse.format(statement, strip_comments=True).strip():
            continue
        assert JalDB._exec(statement.strip(), commit=True) is not None, f"Migration statement failed: {statement}"


def _trigger_sql(name) -> str:
    return JalDB._read("SELECT sql FROM sqlite_master WHERE type='trigger' AND name=:name", [(":name", name)])


def _peg_triggers() -> list:
    query = JalDB._exec("SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'asset_data_peg_%' "
                        "ORDER BY name")
    names = []
    while query.next():
        names.append(query.value(0))
    return names


def _ledger_from(timestamp) -> int:
    return JalDB._read("SELECT COUNT(*) FROM ledger WHERE timestamp>=:ts", [(":ts", timestamp)])


# Stocks A (4), B (5), C (6): A bought on 1 Jan, swapped into B on 1 Feb; A sold on 1 Mar; ledger rebuilt
def _swap_ledger():
    create_stocks([('A', 'Asset A'), ('B', 'Asset B'), ('C', 'Asset C')], currency_id=2)
    t_buy, t_swap, t_sell = d2t(220101), d2t(220201), d2t(220301)
    create_quotes(4, 2, [(t_swap, 150.0)])
    create_trades(1, [(t_buy, t_buy, 4, 20.0, 100.0, 0.0), (t_sell, t_sell, 4, -10.0, 160.0, 0.0)])
    create_swaps(1, [(t_swap, 4, 10, 5, 20)])
    Ledger().rebuild(from_timestamp=0)
    assert _ledger_from(t_buy) > _ledger_from(t_swap) > 0
    return t_buy, t_swap


# A schema-83 database: the column, the peg triggers and the treatment in the update trigger are all missing
def test_delta_upgrades_swaps(prepare_db_fifo, project_root):
    for name in _PEG_TRIGGERS:
        JalDB._exec(f"DROP TRIGGER {name}", commit=True)
    old_trigger = _trigger_sql('swaps_after_update').replace(", treatment ON swaps", " ON swaps")
    JalDB._exec("DROP TRIGGER swaps_after_update", commit=True)
    JalDB._exec(old_trigger, commit=True)
    JalDB._exec("ALTER TABLE swaps DROP COLUMN treatment", commit=True)
    JalDB._exec("INSERT INTO swaps (timestamp, account_id, out_symbol_id, out_qty, in_symbol_id, in_qty) "
                "VALUES (1, 1, 1, '1', 2, '1')", commit=True)

    _run_migration(project_root)

    assert JalDB._read("SELECT treatment FROM swaps") == 0
    assert "in_qty, treatment ON swaps" in _trigger_sql('swaps_after_update')
    assert _peg_triggers() == _PEG_TRIGGERS


def test_treatment_edit_invalidates_ledger(prepare_db_fifo):
    t_buy, t_swap = _swap_ledger()
    before_swap = _ledger_from(t_buy) - _ledger_from(t_swap)
    JalDB._exec("UPDATE swaps SET treatment=2", commit=True)
    assert _ledger_from(t_swap) == 0
    assert _ledger_from(t_buy) == before_swap


# A peg on either side of the swap re-resolves it: the ledger goes from the swap on, what is earlier stays
@pytest.mark.parametrize("asset_id", [4, 5])
def test_peg_edits_invalidate_ledger_from_the_swap(prepare_db_fifo, asset_id):
    t_buy, t_swap = _swap_ledger()
    before_swap = _ledger_from(t_buy) - _ledger_from(t_swap)

    JalDB._exec("INSERT INTO asset_data (asset_id, datatype, value) VALUES (:asset, :type, '1')",
                [(":asset", asset_id), (":type", _PEGGED_TO)], commit=True)
    assert _ledger_from(t_swap) == 0 and _ledger_from(t_buy) == before_swap
    assert JalDB._read("SELECT COUNT(*) FROM trades_opened WHERE timestamp>=:ts", [(":ts", t_swap)]) == 0

    Ledger().rebuild(from_timestamp=0)
    JalDB._exec("UPDATE asset_data SET value='2' WHERE datatype=:type", [(":type", _PEGGED_TO)], commit=True)
    assert _ledger_from(t_swap) == 0 and _ledger_from(t_buy) == before_swap

    Ledger().rebuild(from_timestamp=0)
    JalDB._exec("DELETE FROM asset_data WHERE datatype=:type", [(":type", _PEGGED_TO)], commit=True)
    assert _ledger_from(t_swap) == 0 and _ledger_from(t_buy) == before_swap


# Another attribute, or a peg on an asset no swap touches, leaves the ledger alone
@pytest.mark.parametrize("asset_id, datatype", [(5, 3), (6, _PEGGED_TO)])
def test_unrelated_asset_data_keeps_ledger(prepare_db_fifo, asset_id, datatype):
    t_buy, _ = _swap_ledger()
    rows = _ledger_from(t_buy)
    JalDB._exec("INSERT INTO asset_data (asset_id, datatype, value) VALUES (:asset, :type, '1')",
                [(":asset", asset_id), (":type", datatype)], commit=True)
    JalDB._exec("UPDATE asset_data SET value='2' WHERE asset_id=:asset", [(":asset", asset_id)], commit=True)
    JalDB._exec("DELETE FROM asset_data WHERE asset_id=:asset", [(":asset", asset_id)], commit=True)
    assert _ledger_from(t_buy) == rows
