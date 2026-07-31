from decimal import Decimal

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import create_assets, symbol_id_for, create_trades, create_actions
from constants import PredefinedAsset, SymbolId, AssetLocation
from jal.db.account import JalAccountCreator
from jal.db.asset import JalAsset, JalAssetCreator
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


# ----------------------------------------------------------------------------------------------------------------------
# A lookup by ticker has to resolve one unambiguous ASSET - which is not the same thing as one asset_symbol row.
def test_asset_with_two_listings_is_found_by_its_ticker(prepare_db):
    # One asset routinely carries the same ticker in more than one listing: a security quoted on a second venue, or
    # a coin listed both on the chain it is native to and on another chain holding a wrapped form of it. Counting
    # rows made the second listing look like a conflict and left the ticker unresolved - and an import answers an
    # unresolved asset by creating one, ending up with a duplicate of an asset the ledger already had.
    asset = JalAssetCreator(type_id=PredefinedAsset.Crypto, name='Tron')
    asset.add_symbol('TRX', 2, AssetLocation.TRX_BLOCKCHAIN)
    JalAsset(asset.id()).add_symbol('TRX', 3, AssetLocation.ETH_BLOCKCHAIN)   # the same coin, wrapped on Ethereum
    assert JalAsset.find({'symbol': 'TRX', 'type': PredefinedAsset.Crypto}).id() == asset.id()


def test_ticker_shared_by_two_assets_stays_unresolved(prepare_db):
    # Two different assets reusing one ticker is a genuine ambiguity - a blockchain lets anyone deploy a token
    # calling itself anything - and nothing may pick one of them on the strength of the ticker alone.
    genuine = JalAssetCreator(type_id=PredefinedAsset.Crypto, name='Genuine coin')
    genuine.add_symbol('DUP', 2, AssetLocation.TRX_BLOCKCHAIN)
    impostor = JalAssetCreator(type_id=PredefinedAsset.Crypto, name='Impostor')
    impostor.add_symbol('DUP', 2, AssetLocation.ETH_BLOCKCHAIN)
    assert JalAsset.find({'symbol': 'DUP', 'type': PredefinedAsset.Crypto}).id() == 0


# ----------------------------------------------------------------------------------------------------------------------
# Asking an ASSET for its ticker in a given currency
def test_a_currency_alone_does_not_name_one_listing_of_a_token_held_on_several_chains(prepare_db):
    # A blockchain token is a separate active listing per chain (add_symbol scopes the deactivation by location), so
    # the currency alone leaves several of them, and the answer was their texts run together into a ticker that
    # exists nowhere ("USDTUSDT"). The chain is what picks one.
    asset = JalAssetCreator(type_id=PredefinedAsset.Crypto, name='Tether USD')
    asset.add_symbol('USDT', 2, AssetLocation.ETH_BLOCKCHAIN)
    JalAsset(asset.id()).add_symbol('USDT', 2, AssetLocation.ARB_BLOCKCHAIN)

    assert JalAsset(asset.id()).symbol(currency=2, location=AssetLocation.ETH_BLOCKCHAIN) == 'USDT'
    assert JalAsset(asset.id()).symbol(currency=2, location=AssetLocation.ARB_BLOCKCHAIN) == 'USDT'
    # ... and the currency alone is answered by the ticker rather than by the listings that carry it: the two say
    # the same thing, and running them together made a 'USDTUSDT' that exists nowhere
    assert JalAsset(asset.id()).symbol(currency=2) == 'USDT'
    assert JalAsset(asset.id()).symbol() == 'USDT'


# A location the asset isn't listed on says nothing about it, and answering an account that has no chain of its own
# (a broker, an exchange) with an empty ticker would be worse than answering it with what the currency knows.
def test_a_location_the_asset_is_not_listed_on_is_ignored(prepare_db):
    asset = JalAssetCreator(type_id=PredefinedAsset.Crypto, name='Tether USD')
    asset.add_symbol('USDT', 2, AssetLocation.ETH_BLOCKCHAIN)

    assert JalAsset(asset.id()).symbol(currency=2, location=AssetLocation.TRX_BLOCKCHAIN) == 'USDT'
    assert JalAsset(asset.id()).symbol(currency=2, location=0) == 'USDT'


# Several DIFFERENT tickers for one asset in one currency is a real ambiguity, not a duplicate: a token renamed on
# one chain only, or a security quoted under two names. Nothing here can pick one of them, so the answer names them
# both - visibly not a ticker - instead of choosing silently or refusing to answer at all.
def test_two_different_tickers_of_one_asset_are_both_named(prepare_db):
    asset = JalAssetCreator(type_id=PredefinedAsset.Crypto, name='Tether USD')
    asset.add_symbol('USDT', 2, AssetLocation.ETH_BLOCKCHAIN)
    JalAsset(asset.id()).add_symbol('USD0', 2, AssetLocation.ARB_BLOCKCHAIN)   # renamed on that chain only

    assert JalAsset(asset.id()).symbol(currency=2) == 'USDT,USD0'
    assert JalAsset(asset.id()).tickers(currency=2) == ['USDT', 'USD0']
    # ... and naming the chain resolves it, which is what a caller that needs one listing has to do
    assert JalAsset(asset.id()).symbol(currency=2, location=AssetLocation.ARB_BLOCKCHAIN) == 'USD0'


# An asset with nothing listed in that currency has no ticker there, and says so rather than falling back to one it
# has somewhere else
def test_an_asset_not_listed_in_that_currency_has_no_ticker(prepare_db):
    asset = JalAssetCreator(type_id=PredefinedAsset.Crypto, name='Tether USD')
    asset.add_symbol('USDT', 2, AssetLocation.ETH_BLOCKCHAIN)

    assert JalAsset(asset.id()).symbol(currency=3) == ''
    assert JalAsset(asset.id()).tickers(currency=3) == []


# A currency is one symbol whatever is asked about it - the currency argument is what a ticker is being asked IN, and
# money is the thing it would be asked in
def test_money_is_one_symbol_whatever_currency_is_asked_for(prepare_db):
    assert JalAsset(2).symbol(currency=3) == JalAsset(2).symbol()
    assert len(JalAsset(2).tickers(currency=3)) == 1
