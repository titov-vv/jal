from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import create_assets, symbol_id_for, create_trades, create_actions
from jal.constants import PredefinedAsset, SymbolId, AssetLocation, AssetData
from jal.db.db import JalDB
from jal.db.account import JalAccountCreator
from jal.db.asset import JalAsset, JalAssetCreator
from jal.db.symbol import JalSymbol
from jal.db.receivable import JalReceivable
from jal.db.ledger import Ledger
from jal.db.operations import LedgerTransaction, AssetPayment, LedgerError, AssetIncome
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


# ----------------------------------------------------------------------------------------------------------------------
# An asset the ledger hasn't reached must be reported as well - it is the list the quote downloader works from, and
# an incomplete ledger is exactly the state that needs quotes to be completed. A staking reward that can't be valued
# stops the rebuild (see AssetPayment.price), so a list built from the ledger alone would leave that very asset out
# of the download and nothing would ever complete the ledger.
def test_get_active_symbols_beyond_incomplete_ledger(prepare_db):
    JalAccountCreator(currency_id=2, number='W1', name='Wallet', investing=1, organization=1).commit()
    create_assets([('TRX', 'Tron', '', 2, PredefinedAsset.Crypto, 0)])  # asset id 4, no quotes at all
    create_actions([(d2t(220101), 1, 1, [(4, 1000.0)])])
    reward = {'timestamp': d2t(220301), 'type': AssetIncome.StakingReward, 'account_id': 1,
              'symbol_id': symbol_id_for(4), 'amount': '100', 'tax': '0', 'number': 'txhash', 'note': ''}
    LedgerTransaction.create_new(LedgerTransaction.AssetIncome, reward)
    with pytest.raises(LedgerError):  # The unpriced reward stops the ledger before it books the asset
        Ledger().rebuild(from_timestamp=0)
    assert JalDB._read("SELECT COUNT(*) FROM ledger WHERE asset_id=4") == 0  # nothing about the asset in the ledger

    entries = [x for x in JalSymbol.get_active_symbols(0, d2t(221231)) if x['symbol'].asset().id() == 4]
    assert len(entries) == 1
    assert entries[0]['symbol'].symbol() == 'TRX'
    assert entries[0]['currency'] == 2   # the currency of the account the operation belongs to

    # Only the operations of the requested interval are reported - one that happens later needs no quote yet
    assert [x for x in JalSymbol.get_active_symbols(0, d2t(220201)) if x['symbol'].asset().id() == 4] == []


# ----------------------------------------------------------------------------------------------------------------------
# A reward token an account is only OWED has no ledger row and no operation, yet its claim is valued with its quote.
def test_get_active_symbols_lists_what_is_owed(prepare_db):
    JalAccountCreator(currency_id=2, number='W1', name='Wallet', investing=1, organization=1).commit()
    create_assets([('ARB', 'Arbitrum', '', 2, PredefinedAsset.Crypto, 0)])  # asset id 4, held nowhere
    JalReceivable().store(d2t(220301), 1, 4, '0xdistributor', Decimal('2.5'))

    entries = [x for x in JalSymbol.get_active_symbols(0, d2t(221231)) if x['symbol'].asset().id() == 4]
    assert len(entries) == 1
    assert entries[0]['symbol'].symbol() == 'ARB'
    assert entries[0]['currency'] == 2
    # A reading taken after the requested interval is not listed
    assert [x for x in JalSymbol.get_active_symbols(0, d2t(220201)) if x['symbol'].asset().id() == 4] == []


def test_a_claim_paid_off_is_not_listed(prepare_db):
    JalAccountCreator(currency_id=2, number='W1', name='Wallet', investing=1, organization=1).commit()
    create_assets([('ARB', 'Arbitrum', '', 2, PredefinedAsset.Crypto, 0)])
    JalReceivable().store(d2t(220301), 1, 4, '0xdistributor', Decimal('2.5'))
    JalReceivable().store(d2t(220401), 1, 4, '0xdistributor', Decimal('0'))

    assert [x for x in JalSymbol.get_active_symbols(0, d2t(221231)) if x['symbol'].asset().id() == 4] == []


def test_an_owed_asset_also_in_the_ledger_is_listed_once(prepare_db):
    JalAccountCreator(currency_id=2, number='W1', name='Wallet', investing=1, organization=1).commit()
    create_assets([('ARB', 'Arbitrum', '', 2, PredefinedAsset.Crypto, 0)])
    create_actions([(d2t(220101), 1, 1, [(4, 1000.0)])])  # cash for the trade
    create_trades(1, [(d2t(220201), d2t(220201), 4, 10.0, 1.0, 0.0)])
    Ledger().rebuild(from_timestamp=0)
    assert JalDB._read("SELECT COUNT(*) FROM ledger WHERE asset_id=4 AND book_account=4") > 0
    JalReceivable().store(d2t(220301), 1, 4, '0xdistributor', Decimal('2.5'))

    assert len([x for x in JalSymbol.get_active_symbols(0, d2t(221231)) if x['symbol'].asset().id() == 4]) == 1


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


# Several DIFFERENT tickers of a security in one currency is a real ambiguity, not a duplicate: nothing here can pick
# one of them, so the answer names them both - visibly not a ticker - instead of choosing silently or refusing.
def test_two_different_tickers_of_one_asset_are_both_named(prepare_db):
    asset = JalAssetCreator(type_id=PredefinedAsset.Stock, name='Some Company')
    asset.add_symbol('SC', 2, AssetLocation.NYSE_EXCHANGE)
    asset.add_symbol('SCO', 2, AssetLocation.NASDAQ_EXCHANGE)

    assert JalAsset(asset.id()).symbol(currency=2) == 'SC,SCO'
    assert JalAsset(asset.id()).tickers(currency=2) == ['SC', 'SCO']
    # ... and naming the venue resolves it, which is what a caller that needs one listing has to do
    assert JalAsset(asset.id()).symbol(currency=2, location=AssetLocation.NASDAQ_EXCHANGE) == 'SCO'


# A security with nothing listed in that currency has no ticker there, and says so rather than falling back to one it
# has somewhere else. A crypto listing is kept in its venue's currency and answers in any currency.
def test_an_asset_not_listed_in_that_currency_has_no_ticker(prepare_db):
    stock = JalAssetCreator(type_id=PredefinedAsset.Stock, name='Some Company')
    stock.add_symbol('SC', 2, AssetLocation.NYSE_EXCHANGE)
    assert JalAsset(stock.id()).symbol(currency=3) == ''
    assert JalAsset(stock.id()).tickers(currency=3) == []

    token = JalAssetCreator(type_id=PredefinedAsset.Crypto, name='Tether USD')
    token.add_symbol('USDT', 2, AssetLocation.ETH_BLOCKCHAIN)
    assert JalAsset(token.id()).symbol(currency=3) == 'USDT'


# A currency is one symbol whatever is asked about it - the currency argument is what a ticker is being asked IN, and
# money is the thing it would be asked in
def test_money_is_one_symbol_whatever_currency_is_asked_for(prepare_db):
    assert JalAsset(2).symbol(currency=3) == JalAsset(2).symbol()
    assert len(JalAsset(2).tickers(currency=3)) == 1


# A key that update_data() has no updater for is an error of the caller, on both entry points, and writes nothing.
# A known key with an empty value is skipped silently.
def test_update_data_refuses_an_unknown_key(prepare_db):
    create_assets([('XYZ', 'Test bond', '', 2, PredefinedAsset.Bond, 0)])   # asset id 4
    asset = JalAsset(4)

    with pytest.raises(ValueError, match="Unknown asset data key"):
        asset.update_data({'principal': '1000', AssetData.PrincipalValue: '500'})
    assert JalAsset(4).principal() == Decimal('0')
    with pytest.raises(ValueError, match="Unknown asset data key"):
        JalSymbol(symbol_id_for(4)).update_data({'isin': 'US1234567890', 'bogus': 0})
    assert JalSymbol(symbol_id_for(4)).identifier(SymbolId.ISIN) == ''

    JalSymbol(symbol_id_for(4)).update_data({'isin': 'US1234567890', 'principal': '1000', 'expiry': 0})
    assert JalSymbol(symbol_id_for(4)).identifier(SymbolId.ISIN) == 'US1234567890'
    assert JalAsset(4).principal() == Decimal('1000')


# A crypto asset asked about in a currency, with no chain that narrows it down, is named by its first live listing;
# a chain it is listed on picks that chain's own one
def test_crypto_asset_is_named_by_its_first_live_listing(prepare_db):
    token = JalAssetCreator(type_id=PredefinedAsset.Crypto, name='Tether USD')
    token.add_symbol('USDT', 2, AssetLocation.ETH_BLOCKCHAIN)
    token.add_symbol('USD₮0', 2, AssetLocation.ARB_BLOCKCHAIN)   # renamed on that chain only
    assert JalAsset(token.id()).symbol(currency=3) == 'USDT'
    assert JalAsset(token.id()).tickers(currency=3) == ['USDT']
    assert JalAsset(token.id()).symbol(currency=3, location=AssetLocation.ARB_BLOCKCHAIN) == 'USD₮0'


# A native coin first listed as another chain's wrapper is still named by its own chain's listing
def test_native_coin_is_named_by_its_own_chain_listing(prepare_db):
    coin = JalAssetCreator(type_id=PredefinedAsset.Crypto, name='Solana')
    coin.add_symbol('USOL', 2, AssetLocation.HL_BLOCKCHAIN)
    JalAsset(coin.id()).add_symbol('SOL', 2, AssetLocation.SOL_BLOCKCHAIN)
    assert JalAsset(coin.id()).symbol(currency=3) == 'SOL'
    assert JalAsset(coin.id()).listing_id(currency=3) == JalAsset(coin.id()).listing_id(currency=3, location=AssetLocation.SOL_BLOCKCHAIN)
    assert JalAsset(coin.id()).symbol(currency=3, location=AssetLocation.HL_BLOCKCHAIN) == 'USOL'
