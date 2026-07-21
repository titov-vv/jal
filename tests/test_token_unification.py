from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from constants import PredefinedAsset, PredefinedAccountType, AssetLocation, SymbolId
from jal.data_import.statement import Statement, JSF
from jal.db.account import JalAccountCreator, JalAccount
from jal.db.asset import JalAsset, JalAssetCreator
from jal.db.symbol import JalSymbol
from jal.db.token_blacklist import JalTokenBlacklist
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


def test_unrelated_ticker_creates_a_new_asset_without_asking(prepare_db):
    # No existing crypto asset shares the ticker, so there is nothing to disambiguate and the prompt never fires.
    JalAccountCreator(currency_id=USD, number='', name='Tron wallet', investing=1, organization=1,
                      account_type=PredefinedAccountType.Wallet, address='TMuA6YqfCeX8EhbfYEg5y7S4DqzSJireY9',
                      chain=AssetLocation.TRX_BLOCKCHAIN).commit()
    statement, token = _tron_statement_with_usdt()

    def fail(*args, **kwargs):
        raise AssertionError("The token prompt must not be shown when no known asset shares the ticker")
    statement.select_token_action = fail
    statement.match_db_ids()

    assert statement.mapped_id(JSF.ASSETS, token) == 0
    statement.import_into_db()
    assert JalSymbol.find_by_identifier(SymbolId.TRX_ADDRESS, TRX_USDT).asset().id()
