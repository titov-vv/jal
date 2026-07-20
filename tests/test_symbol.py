from decimal import Decimal

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import create_assets, symbol_id_for, create_trades, create_actions
from constants import PredefinedAsset, SymbolId, AssetLocation
from jal.db.account import JalAccountCreator
from jal.db.asset import JalAsset
from jal.db.symbol import JalSymbol
from jal.db.ledger import Ledger
from jal.db.asset_models import SymbolsListModel
from tests.helpers import d2t


# ----------------------------------------------------------------------------------------------------------------------
def test_symbol_load(prepare_db):
    # asset ID 4, single USD (currency id 2) symbol 'VUG' with an ISIN
    create_assets([('VUG', 'Growth ETF', 'US1234567890', 2, PredefinedAsset.ETF, 0)])
    symbol_id = symbol_id_for(4)
    assert symbol_id is not None

    symbol = JalSymbol(symbol_id)
    assert symbol.id() == symbol_id
    assert symbol.symbol() == 'VUG'
    assert symbol.asset().id() == 4
    assert symbol.currency() == 2
    assert symbol.active() is True
    assert symbol.identifier(SymbolId.ISIN) == 'US1234567890'
    assert symbol.identifier(SymbolId.CUSIP) == ''
    assert symbol.identifiers() == {SymbolId.ISIN: 'US1234567890'}


# ----------------------------------------------------------------------------------------------------------------------
def test_empty_symbol(prepare_db):
    # An empty / unknown / NULL symbol must degrade to an empty object with no asset (matches nullable transfers
    # and symbol_id=0 from get_active_symbols)
    for empty in (JalSymbol(0), JalSymbol(None), JalSymbol(99999)):  # 0, coerced-to-0, and a non-existent id
        assert empty.symbol() == ''
        assert empty.asset().id() == 0
        assert empty.currency() is None
        assert empty.identifier(SymbolId.ISIN) == ''
        assert empty.identifiers() == {}
    assert JalSymbol(None).id() == 0  # None is coerced to an empty-symbol id


# ----------------------------------------------------------------------------------------------------------------------
def test_add_and_update_identifier(prepare_db):
    create_assets([('EDV', 'Extended Treasury', '', 2, PredefinedAsset.ETF, 0)])
    symbol_id = symbol_id_for(4)
    symbol = JalSymbol(symbol_id)
    assert symbol.identifier(SymbolId.ISIN) == ''

    symbol.add_identifier(SymbolId.ISIN, 'US9219107094')
    assert JalSymbol(symbol_id).identifier(SymbolId.ISIN) == 'US9219107094'

    # update_identifier must not overwrite an existing identifier
    symbol = JalSymbol(symbol_id)
    symbol.update_identifier(SymbolId.ISIN, 'DIFFERENT')
    assert JalSymbol(symbol_id).identifier(SymbolId.ISIN) == 'US9219107094'

    # update_identifier adds a not-yet-present identifier type
    symbol.update_identifier(SymbolId.CUSIP, '921910709')
    assert JalSymbol(symbol_id).identifier(SymbolId.CUSIP) == '921910709'


# ----------------------------------------------------------------------------------------------------------------------
# A write through JalAsset must invalidate the (separate) JalSymbol cache - otherwise a symbol loaded before the
# write would keep serving stale data (Phase 3 cross-cache invalidation).
def test_jalasset_write_invalidates_symbol_cache(prepare_db):
    create_assets([('A.USD', 'A Share', '', 2, PredefinedAsset.Stock, 0)])  # asset id 4
    old_symbol_id = symbol_id_for(4)
    old_symbol = JalSymbol(old_symbol_id)          # cache the symbol while it is active
    assert old_symbol.active() is True

    # Adding a new symbol for the same currency deactivates the old one
    new_symbol_id = JalAsset(4).add_symbol('A.USD.NEW', 2, location_id=AssetLocation.UNDEFINED)
    assert JalSymbol(old_symbol_id).active() is False  # would still be True if the cache were stale

    # Attaching an identifier through JalAsset must be visible via JalSymbol too
    JalAsset(4).add_identifier(new_symbol_id, SymbolId.ISIN, 'US0000000001')
    assert JalSymbol(new_symbol_id).identifier(SymbolId.ISIN) == 'US0000000001'

# ----------------------------------------------------------------------------------------------------------------------
# get_active_symbols must return JalSymbol objects scoped to the active listing involved in ledger operations.
def test_get_active_symbols_returns_jalsymbol(prepare_db):
    JalAccountCreator(currency_id=2, number='U1', name='Acc', investing=1, organization=1).commit()
    create_assets([('AAPL', 'Apple Inc.', 'US0378331005', 2, PredefinedAsset.Stock, 0)])  # asset id 4
    create_actions([(d2t(220101), 1, 1, [(4, 100000.0)])])  # starting balance so the trade has funds
    create_trades(1, [(d2t(220201), d2t(220203), 4, 10.0, 100.0, 1.0)])
    Ledger().rebuild(from_timestamp=0)

    active = JalSymbol.get_active_symbols(0, d2t(221231))
    entries = [x for x in active if x['symbol'].asset().id() == 4]
    assert len(entries) == 1
    symbol = entries[0]['symbol']
    assert isinstance(symbol, JalSymbol)
    assert symbol.symbol() == 'AAPL'
    assert symbol.identifier(SymbolId.ISIN) == 'US0378331005'
    assert entries[0]['currency'] == 2


# SymbolsListModel.setFilter() has to produce valid SQL when nothing is filtered. An unfiltered list is the normal
# case: SymbolListDialog.set_parameters() forwards whatever the selector widget supplied, and only one call site
# in the whole application (the table-view delegate in delegates.py) supplies a currency - so every symbol selector
# opened from an operation widget lands here. Emitting the WHERE keyword with an empty condition produced
# 'WHERE  ORDER BY s.symbol', a syntax error that made _exec() return None and crashed locateItem().
def test_unfiltered_symbol_list_builds_valid_sql(prepare_db):
    create_assets([('AAPL', 'Apple Inc.', 'US0378331005', 2, PredefinedAsset.Stock, 0)])
    model = SymbolsListModel()

    model.setFilter()
    assert 'WHERE  ' not in model._current_query
    assert model.rowCount() > 0                      # the query executed instead of failing to prepare
    located = model.locateItem(model.record(0).value('id'))
    assert located.isValid()

    # A filter that does select something must still work
    model.setFilter(asset_type=PredefinedAsset.Stock)
    assert 'WHERE a.type_id=' in model._current_query
    assert model.rowCount() > 0
