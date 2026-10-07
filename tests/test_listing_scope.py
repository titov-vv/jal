from tests.fixtures import project_root, data_path, prepare_db
from jal.constants import AssetLocation, PredefinedAsset
from jal.db.asset import JalAsset, JalAssetCreator
from jal.db.symbol import JalSymbol

USD = 2
EUR = 3


def test_security_listing_ignores_the_venue(prepare_db):
    stock = JalAssetCreator(PredefinedAsset.Stock, 'Some Company', '').commit()
    first = stock.add_symbol('SC', USD, location_id=AssetLocation.NYSE_EXCHANGE)
    assert stock.add_symbol('SC', USD, location_id=AssetLocation.NASDAQ_EXCHANGE) == first
    assert JalSymbol(first).location() == AssetLocation.NYSE_EXCHANGE     # the first-seen venue is kept
    assert stock.active_symbol_ids() == [first]


def test_token_is_listed_per_chain(prepare_db):
    coin = JalAssetCreator(PredefinedAsset.Crypto, 'Tether', '').commit()
    eth = coin.add_symbol('USDT', USD, location_id=AssetLocation.ETH_BLOCKCHAIN)
    arb = coin.add_symbol('USDT', USD, location_id=AssetLocation.ARB_BLOCKCHAIN)
    assert eth != arb
    assert coin.add_symbol('USDT', USD, location_id=AssetLocation.ETH_BLOCKCHAIN) == eth
    assert sorted(coin.active_symbol_ids()) == [eth, arb]


def test_exchange_coin_does_not_land_on_a_chain_listing(prepare_db):
    coin = JalAssetCreator(PredefinedAsset.Crypto, 'Tether', '').commit()
    eth = coin.add_symbol('USDT', EUR, location_id=AssetLocation.ETH_BLOCKCHAIN)
    kucoin = coin.add_symbol('USDT', EUR, location_id=AssetLocation.CEX_KUCOIN)
    assert kucoin != eth
    assert JalSymbol(kucoin).location() == AssetLocation.CEX_KUCOIN
    assert coin.add_symbol('USDT', EUR, location_id=AssetLocation.CEX_KUCOIN) == kucoin
    assert sorted(coin.active_symbol_ids()) == [eth, kucoin]              # the chain listing stays active


def test_coin_is_listed_per_exchange(prepare_db):
    coin = JalAssetCreator(PredefinedAsset.Crypto, 'Tether', '').commit()
    listings = [coin.add_symbol('USDT', EUR, location_id=x) for x in AssetLocation.CEXES]
    assert len(set(listings)) == len(AssetLocation.CEXES)
    assert sorted(coin.active_symbol_ids()) == sorted(listings)
    assert [JalSymbol(x).location() for x in listings] == AssetLocation.CEXES
