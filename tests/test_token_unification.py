from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from constants import PredefinedAsset, PredefinedAccountType, AssetLocation, SymbolId
from jal.data_import.statement import Statement, JSF
from jal.db.account import JalAccountCreator, JalAccount
from jal.db.asset import JalAsset, JalAssetCreator
from jal.db.symbol import JalSymbol
from jal.db.token_blacklist import JalTokenBlacklist
from jal.net.chain_fetchers.hyperliquid import HyperliquidFetcher
from jal.net.chain_fetchers.tron import TronFetcher

# The same stablecoin lives on several chains under identical ticker but with an unrelated contract on each chain.
USD = 2
ETH_USDT = "0xdac17f958d2ee523a2206206994597c13d831ec7"     # Tether on Ethereum (already known to JAL)
TRX_USDT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"             # Tether on Tron (the freshly fetched token)


@pytest.fixture
def known_usdt(prepare_db):
    # A crypto asset the user already holds, listed on Ethereum and keyed by its Ethereum contract address.
    creator = JalAssetCreator(PredefinedAsset.Crypto, 'Tether USD')
    symbol_id = creator.add_symbol('USDT', USD, location_id=AssetLocation.ETH_BLOCKCHAIN)
    creator.add_identifier(symbol_id, SymbolId.ETH_ADDRESS, ETH_USDT)
    asset = creator.commit()
    JalAccountCreator(currency_id=USD, number='', name='Tron wallet', investing=1, organization=1,
                      account_type=PredefinedAccountType.Wallet, address='TMuA6YqfCeX8EhbfYEg5y7S4DqzSJireY9',
                      chain=AssetLocation.TRX_BLOCKCHAIN).commit()
    yield asset


# Builds a Tron statement that carries the Tron USDT token (no address match in the db) plus one incoming transfer of
# it, exactly as the fetcher would - without touching the network.
def _tron_statement_with_usdt(with_transfer=False):
    statement = TronFetcher()
    statement._account = JalAccount(1)
    statement._data = {JSF.ACCOUNTS: [], JSF.ASSETS: [], JSF.TRANSFERS: []}
    token = statement._token_asset_id('USDT', 'Tether USD', address=TRX_USDT)
    if with_transfer:
        statement._add_transfer(1600000000, token, Decimal('100'), incoming=True, tx_hash='deadbeef')
    return statement, token


# ----------------------------------------------------------------------------------------------------------------------
def test_add_symbol_adds_a_listing_per_chain(prepare_db):
    # One asset that exists on two chains keeps a separate active listing for each - the uniqueness key now includes
    # the location, so the same ticker/currency at a different chain no longer collides or deactivates its sibling.
    creator = JalAssetCreator(PredefinedAsset.Crypto, 'Tether USD')
    creator.commit()
    asset = JalAsset(creator.id())
    eth = asset.add_symbol('USDT', USD, location_id=AssetLocation.ETH_BLOCKCHAIN)
    trx = asset.add_symbol('USDT', USD, location_id=AssetLocation.TRX_BLOCKCHAIN)
    assert eth != trx
    assert set(asset.active_symbol_ids()) == {eth, trx}


def test_add_symbol_keeps_one_listing_for_a_security(prepare_db):
    # A traditional security seen first without a venue and then on an exchange is still a single listing - the
    # exchange is informational and must not split the security into two symbols.
    creator = JalAssetCreator(PredefinedAsset.Stock, 'Some Corp')
    creator.commit()
    asset = JalAsset(creator.id())
    first = asset.add_symbol('ABC', USD, location_id=AssetLocation.UNDEFINED)
    second = asset.add_symbol('ABC', USD, location_id=AssetLocation.NYSE_EXCHANGE)
    assert first == second
    assert asset.active_symbol_ids() == [first]


# ----------------------------------------------------------------------------------------------------------------------
def test_merge_maps_token_onto_the_existing_asset(known_usdt):
    statement, token = _tron_statement_with_usdt()
    statement._token_action_for_tests = (Statement.TOKEN_MERGE, known_usdt.id())
    statement.match_db_ids()

    assert statement.mapped_id(JSF.ASSETS, token) == known_usdt.id()   # merged, not left as a new asset
    statement.import_into_db()
    # The existing asset now carries the Tron listing with its Tron contract address, so a later fetch resolves it
    # by address alone (no more prompt), and both chains stay active on the single asset.
    tron_symbol = JalSymbol.find_by_identifier(SymbolId.TRX_ADDRESS, TRX_USDT)
    assert tron_symbol.asset().id() == known_usdt.id()
    assert len(JalAsset(known_usdt.id()).active_symbol_ids()) == 2   # both chains stay active on the one asset


# ----------------------------------------------------------------------------------------------------------------------
# Once a coin is listed on a chain under its address there, a later fetch of that chain must resolve it SILENTLY -
# no prompt, no second asset. This is what carries a completed unification forward, and it is the whole of what a
# venue-specific wrapper needs: Hyperliquid's UBTC/UETH/USOL are the native coins listed on that chain, so folding
# them into BTC/ETH/SOL is all that is required and no fetcher needs a table of its own mapping them back.
def test_a_token_already_listed_on_its_chain_is_matched_without_asking(prepare_db):
    UBTC = "0x8f254b963e8468305d409b33aa137c67"     # HyperCore token id of Unit's wrapped BTC
    creator = JalAssetCreator(PredefinedAsset.Crypto, 'Bitcoin')
    creator.add_symbol('BTC', USD, location_id=AssetLocation.BTC_BLOCKCHAIN)
    hyperliquid = creator.add_symbol('UBTC', USD, location_id=AssetLocation.HL_BLOCKCHAIN)
    creator.add_identifier(hyperliquid, SymbolId.HL_ADDRESS, UBTC)
    bitcoin = creator.commit()
    JalAccountCreator(currency_id=USD, number='', name='HL wallet', investing=1, organization=1,
                      account_type=PredefinedAccountType.Wallet, address='0x' + '1' * 40,
                      chain=AssetLocation.HL_BLOCKCHAIN).commit()

    statement = HyperliquidFetcher()
    statement._account = JalAccount(1)
    statement._data = {JSF.ACCOUNTS: [], JSF.ASSETS: [], JSF.TRANSFERS: []}
    token = statement._token_asset_id('UBTC', 'Unit Bitcoin', address=UBTC)
    # Asked to fail loudly rather than silently create a second asset: reaching the prompt at all is the bug here
    statement._token_action_for_tests = (Statement.TOKEN_CREATE_NEW, 0)
    statement.match_db_ids()

    assert statement.mapped_id(JSF.ASSETS, token) == bitcoin.id()
    statement.import_into_db()
    assert JalSymbol.find_by_identifier(SymbolId.HL_ADDRESS, UBTC).asset().id() == bitcoin.id()
    assert len(JalAsset(bitcoin.id()).active_symbol_ids()) == 2      # one coin, listed on two chains


def test_create_new_leaves_the_token_unmapped(known_usdt):
    statement, token = _tron_statement_with_usdt()
    statement._token_action_for_tests = (Statement.TOKEN_CREATE_NEW, 0)
    statement.match_db_ids()

    assert statement.mapped_id(JSF.ASSETS, token) == 0   # not merged - import will stage a brand-new asset
    statement.import_into_db()
    new_symbol = JalSymbol.find_by_identifier(SymbolId.TRX_ADDRESS, TRX_USDT)
    assert new_symbol.asset().id() and new_symbol.asset().id() != known_usdt.id()


def test_discard_blacklists_and_drops_the_operations(known_usdt):
    statement, token = _tron_statement_with_usdt(with_transfer=True)
    statement._token_action_for_tests = (Statement.TOKEN_DISCARD, 0)
    statement.match_db_ids()

    # The address is blacklisted so future fetches skip it silently...
    assert JalTokenBlacklist.is_blacklisted(AssetLocation.TRX_BLOCKCHAIN, TRX_USDT)
    # ...and the token together with the transfer that referenced it is gone from the statement.
    assert all(asset['id'] != token for asset in statement._data[JSF.ASSETS])
    assert statement._data[JSF.TRANSFERS] == []


def test_a_token_matching_nothing_is_still_asked_about(prepare_db):
    # A token that resembles nothing is asked about too, and with nothing to suggest. Firing only on a ticker
    # collision was exactly wrong for the case that matters most: a coin RENAMED on one chain ('USDT' is called
    # 'USD₮0' on Arbitrum) collides with nothing, so no question was asked and a second asset was created for a coin
    # the user already held. Answering 'create new' is what used to happen silently.
    JalAccountCreator(currency_id=USD, number='', name='Tron wallet', investing=1, organization=1,
                      account_type=PredefinedAccountType.Wallet, address='TMuA6YqfCeX8EhbfYEg5y7S4DqzSJireY9',
                      chain=AssetLocation.TRX_BLOCKCHAIN).commit()
    statement, token = _tron_statement_with_usdt()

    asked = []

    def record(_asset, _addressed, candidates):
        asked.append(candidates)
        return Statement.TOKEN_CREATE_NEW, 0
    statement.select_token_action = record
    statement.match_db_ids()

    assert asked == [[]]        # asked once, with nothing to offer as a merge target
    assert statement.mapped_id(JSF.ASSETS, token) == 0
    statement.import_into_db()
    assert JalSymbol.find_by_identifier(SymbolId.TRX_ADDRESS, TRX_USDT).asset().id()


# The case the ticker collision was never going to catch: the coin is the same, the ticker is not. It is offered as a
# candidate because 'USD₮0' and 'USDT' are the same string once the decorative glyph is folded back to the letter it
# stands for - a resemblance, offered for the user to accept and never acted on by itself.
def test_a_renamed_coin_is_offered_as_a_candidate(known_usdt):
    statement = TronFetcher()
    statement._account = JalAccount(1)
    statement._data = {JSF.ACCOUNTS: [], JSF.ASSETS: [], JSF.TRANSFERS: []}
    token = statement._token_asset_id('USD₮0', 'USD₮0', address=TRX_USDT)

    offered = []

    def record(_asset, _addressed, candidates):
        offered.append(candidates)
        return Statement.TOKEN_MERGE, candidates[0]
    statement.select_token_action = record
    statement.match_db_ids()

    assert offered == [[known_usdt.id()]]
    assert statement.mapped_id(JSF.ASSETS, token) == known_usdt.id()


# ... while a ticker that merely happens to be short is not turned into a resemblance with everything
def test_an_unrelated_ticker_is_not_offered_as_a_candidate(known_usdt):
    statement = TronFetcher()
    statement._account = JalAccount(1)
    statement._data = {JSF.ACCOUNTS: [], JSF.ASSETS: [], JSF.TRANSFERS: []}
    statement._token_asset_id('SCAM', 'Not Tether', address=TRX_USDT)

    offered = []

    def record(_asset, _addressed, candidates):
        offered.append(candidates)
        return Statement.TOKEN_CREATE_NEW, 0
    statement.select_token_action = record
    statement.match_db_ids()

    assert offered == [[]]
