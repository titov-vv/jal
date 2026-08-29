import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json

import pytest
from PySide6.QtCore import Qt, QBuffer, QIODevice
from PySide6.QtGui import QIcon, QImage

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import create_assets, symbol_id_for
from constants import AssetLocation, IconOwner, IconSource, PredefinedAsset, SymbolId, Setup
from jal.db.asset import JalAsset, JalAssetCreator
from jal.db.asset_models import SymbolsListModel
from jal.db.icon import JalIcons
from jal.db.symbol import JalSymbol
from jal.net.asset_icons import icon_url, eip55_address, coingecko_icons_urls, parse_coingecko_icons
from jal.net.downloader import QuoteDownloader

PNG = b'\x89PNG\r\n\x1a\n' + b'fake image data'


# Real PNG bytes of a plain square of the given size - the shape an icon is stored in
def _png_image(size: int = 256) -> bytes:
    image = QImage(size, size, QImage.Format_RGB32)
    image.fill(Qt.red)
    buffer = QBuffer()
    buffer.open(QIODevice.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


# A stand-in for WebRequest: every url is answered from a {substring: (status, data)} table and 404 when no
# pattern matches it. Requested urls land in 'log' in the order they were asked for.
def _fake_web_request(answers: dict, log: list):
    class FakeRequest:
        GET = 1     # WebRequest.GET, the operation the downloader asks for

        def __init__(self, _operation, url, binary=False, expected_errors=()):
            log.append(url)
            self._status, self._data = 404, ''
            for pattern, (status, data) in answers.items():
                if pattern in url:
                    self._status, self._data = status, data
                    break

        def isRunning(self):
            return False

        # The answer is ready before the caller ever asks, so the waiting loop ends at once - True is "it finished"
        def wait(self, _deadline=None):
            return True

        def data(self):
            return self._data

        def status(self):
            return self._status

    return FakeRequest


def _crypto_listing(name: str, ticker: str, location: int, address: str = '') -> JalSymbol:
    asset = JalAssetCreator(type_id=PredefinedAsset.Crypto, name=name)
    symbol_id = asset.add_symbol(ticker, 2, location)
    if address:
        asset.add_identifier(symbol_id, AssetLocation.address_id_of(location), address)
    asset.commit()
    return JalSymbol(symbol_id)


# ----------------------------------------------------------------------------------------------------------------------
# The Trust Wallet repository names its folders by the EIP-55 checksummed address only, while JAL keeps an address
# in whatever case the chain data provided - so an address has to be re-cased before it is used in a URL.
def test_eip55_checksum():
    assert eip55_address('0xdac17f958d2ee523a2206206994597c13d831ec7') == '0xdAC17F958D2ee523a2206206994597C13D831ec7'
    assert eip55_address('0xDAC17F958D2EE523A2206206994597C13D831EC7') == '0xdAC17F958D2ee523a2206206994597C13D831ec7'
    assert eip55_address('0xb31f66aa3c1e785363f0875a1b74e27b85fd66c7') == '0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7'
    # Anything that is not an EVM address is left exactly as it is stored - a Solana mint and a Tron address are
    # case-sensitive by nature and re-casing them would produce a different (invalid) address.
    for address in ('TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t', 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v', '', '0x1234'):
        assert eip55_address(address) == address


# ----------------------------------------------------------------------------------------------------------------------
def test_icon_url_of_tokens(prepare_db):
    # A token is addressed by chain + contract address, the same key its quotes are downloaded by
    usdt = _crypto_listing('Tether', 'USDT', AssetLocation.ETH_BLOCKCHAIN, '0xdac17f958d2ee523a2206206994597c13d831ec7')
    assert icon_url(usdt) == "https://raw.githubusercontent.com/trustwallet/assets/master/blockchains/ethereum/" \
                             "assets/0xdAC17F958D2ee523a2206206994597C13D831ec7/logo.png"
    usdt_tron = _crypto_listing('Tether TRC', 'USDT', AssetLocation.TRX_BLOCKCHAIN, 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t')
    assert icon_url(usdt_tron) == "https://raw.githubusercontent.com/trustwallet/assets/master/blockchains/tron/" \
                                  "assets/TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t/logo.png"
    # The same asset listed on two chains gets two different icons - the point of keeping the icon per listing
    assert icon_url(usdt) != icon_url(usdt_tron)


def test_icon_url_of_native_coins(prepare_db):
    # The native coin of a chain has no contract address and is recognized by its ticker
    btc = _crypto_listing('Bitcoin', 'BTC', AssetLocation.BTC_BLOCKCHAIN)
    assert icon_url(btc) == "https://raw.githubusercontent.com/trustwallet/assets/master/blockchains/bitcoin/" \
                            "info/logo.png"
    # Hyperliquid is stored under the name of its EVM chain in the repository
    hype = _crypto_listing('Hyperliquid', 'HYPE', AssetLocation.HL_BLOCKCHAIN)
    assert '/blockchains/hyperevm/info/logo.png' in icon_url(hype)
    # The native coin of Arbitrum is bridged ETH, so it wears the Ethereum logo and not the Arbitrum one
    eth_on_arbitrum = _crypto_listing('Ethereum', 'ETH', AssetLocation.ARB_BLOCKCHAIN)
    assert '/blockchains/ethereum/info/logo.png' in icon_url(eth_on_arbitrum)


# A listing on a chain with no contract address stored is a token JAL has no address for far more often than it is
# the native coin of that chain - and giving it the chain logo painted a whole portfolio of coins (ALGO, DOT, NEAR,
# ... all recorded on the Ethereum location) with the Ethereum logo. Only the native ticker gets the chain logo.
def test_addressless_token_gets_no_icon(prepare_db):
    for ticker, location in (('DOT', AssetLocation.ETH_BLOCKCHAIN), ('NEAR', AssetLocation.ETH_BLOCKCHAIN),
                             ('USDT', AssetLocation.TRX_BLOCKCHAIN), ('ARB', AssetLocation.ARB_BLOCKCHAIN),
                             ('BONK', AssetLocation.SOL_BLOCKCHAIN)):
        assert icon_url(_crypto_listing(f"{ticker} coin", ticker, location)) == ''


def test_icon_url_of_exchange_coins(prepare_db):
    # A coin on a centralized exchange has no address, so only a coin that is the native coin of a known chain
    # can be recognized by its ticker...
    btc = _crypto_listing('Bitcoin', 'BTC', AssetLocation.CEX_EXCHANGE)
    assert icon_url(btc) == "https://raw.githubusercontent.com/trustwallet/assets/master/blockchains/bitcoin/" \
                            "info/logo.png"
    # ... while a token held on an exchange gets no icon rather than a guessed one
    usdt = _crypto_listing('Tether', 'USDT', AssetLocation.CEX_EXCHANGE)
    assert icon_url(usdt) == ''


# A coin is never looked up at Parqet: it serves company and fund logos, so the only thing an unplaceable coin
# (imported without a location) could get from it is a 404 recorded forever.
def test_coin_is_not_looked_up_as_a_security(prepare_db):
    assert icon_url(_crypto_listing('Limewire', 'LMWR', AssetLocation.UNDEFINED)) == ''


def test_icon_url_of_securities(prepare_db):
    create_assets([('AAPL', 'Apple Inc.', 'US0378331005', 2, PredefinedAsset.Stock, 0)])
    symbol = JalSymbol(symbol_id_for(4))
    assert icon_url(symbol) == f"https://assets.parqet.com/logos/isin/US0378331005?format=png&size={Setup.ICON_STORED_SIZE}"

    # A listing with no ISIN falls back to its ticker
    create_assets([('VOO', 'Vanguard S&P 500', '', 2, PredefinedAsset.ETF, 0)])
    assert icon_url(JalSymbol(symbol_id_for(5))) == f"https://assets.parqet.com/logos/symbol/VOO?format=png&size={Setup.ICON_STORED_SIZE}"

    # A currency has no logo to download - it is displayed with the flag of its country
    assert icon_url(JalSymbol(symbol_id_for(2))) == ''


# ----------------------------------------------------------------------------------------------------------------------
# Downloader behavior: a listing is requested once, its answer (image or 'nothing') is remembered, and a repeated
# run downloads nothing at all.
def test_icons_are_downloaded_once(prepare_db, monkeypatch):
    create_assets([('AAPL', 'Apple Inc.', 'US0378331005', 2, PredefinedAsset.Stock, 0),
                   ('NOLOGO', 'Unknown Corp.', 'US0000000001', 2, PredefinedAsset.Stock, 0)])
    known, unknown = JalSymbol(symbol_id_for(4)), JalSymbol(symbol_id_for(5))
    requested = []
    monkeypatch.setattr("jal.net.downloader.WebRequest",
                        _fake_web_request({'US0378331005': (200, PNG)}, requested))
    downloader = QuoteDownloader()

    downloader.download_icons([known, unknown])
    assert len(requested) == 2
    assert JalIcons.image(IconOwner.Symbol, known.id()) == PNG
    assert JalIcons.image(IconOwner.Symbol, unknown.id()) == b''    # Marked as 'no icon exists' rather than left unset

    requested.clear()
    downloader.download_icons([JalSymbol(known.id()), JalSymbol(unknown.id())])
    assert requested == []                          # Neither of them is asked about a second time


# A failure that is not an answer (no connection, server error) must not be remembered as 'there is no icon',
# otherwise a single download made while offline would permanently deprive every asset of its icon.
def test_failed_icon_request_is_retried(prepare_db, monkeypatch):
    create_assets([('AAPL', 'Apple Inc.', 'US0378331005', 2, PredefinedAsset.Stock, 0)])
    symbol = JalSymbol(symbol_id_for(4))
    attempts = []
    monkeypatch.setattr("jal.net.downloader.WebRequest",
                        _fake_web_request({'parqet.com': (0, '')}, attempts))   # No answer received at all
    downloader = QuoteDownloader()

    downloader.download_icons([symbol])
    assert len(attempts) == 1
    assert JalIcons.image(IconOwner.Symbol, symbol.id()) is None            # Nothing was recorded ...
    downloader.download_icons([JalSymbol(symbol.id())])
    assert len(attempts) == 2                               # ... so the next run asks again


# A listing that no source can be asked about (a currency) is skipped without a request and without a record -
# it may become downloadable later, e.g. when an ISIN is added to it.
def test_listing_without_source_is_not_marked(prepare_db, monkeypatch):
    class NoRequest:
        GET = 1

        def __init__(self, *args, **kwargs):
            pytest.fail("No request should be made for a listing that has no icon source")

    monkeypatch.setattr("jal.net.downloader.WebRequest", NoRequest)
    currency = JalSymbol(symbol_id_for(2))    # The base currency of the test database
    QuoteDownloader().download_icons([currency])
    assert JalIcons.image(IconOwner.Symbol, currency.id()) is None


# ----------------------------------------------------------------------------------------------------------------------
# The symbols list shows the logo of a listing before its ticker, and it never queries the image itself: the store
# is asked by id, so no row of this list carries the bytes of a PNG that could end up rendered as text.
def test_symbol_list_displays_icon_before_the_ticker(prepare_db):
    create_assets([('AAPL', 'Apple Inc.', 'US0378331005', 2, PredefinedAsset.Stock, 0)])
    symbol_id = symbol_id_for(4)
    JalIcons.store(IconOwner.Symbol, symbol_id, _png_image(), IconSource.Downloaded)

    model = SymbolsListModel()
    model.setFilter()
    assert model.fieldIndex("icon") == -1                       # the image is no longer a column of this list
    assert 'icon' not in [model.record(0).fieldName(i) for i in range(model.record(0).count())]
    rows = [i for i in range(model.rowCount()) if model.record(i).value('id') == symbol_id]
    assert len(rows) == 1
    index = model.index(rows[0], model.fieldIndex("symbol"))
    assert model.data(index, Qt.DisplayRole) == 'AAPL'           # the ticker keeps its column, the logo joins it

    icon = model.data(index, Qt.DecorationRole)
    assert isinstance(icon, QIcon)
    assert not icon.isNull()
    # The stored image is painted at the size of a grid row - one 256x256 logo must not set the height of every row
    assert max(icon.availableSizes()[0].width(), icon.availableSizes()[0].height()) == JalIcons.grid_size()

    # A listing with no icon (and one the source had no icon for) reserves the same space and shows nothing in it.
    # A currency is no example of that any more - it wears the sign of its ticker (see test_icon_display.py).
    create_assets([('NOLOGO', 'Unknown Corp.', '', 2, PredefinedAsset.Stock, 0)])
    JalIcons.store(IconOwner.Symbol, symbol_id_for(5), b'', IconSource.Downloaded)
    model.setFilter()
    for row in range(model.rowCount()):
        if model.record(row).value('id') == symbol_id_for(5):
            blank = model.data(model.index(row, model.fieldIndex("symbol")), Qt.DecorationRole)
            assert isinstance(blank, QIcon)
            assert blank.availableSizes()[0].width() == JalIcons.grid_size()
            assert blank.pixmap(JalIcons.grid_size()).toImage().pixelColor(0, 0).alpha() == 0   # space, not a picture


# ----------------------------------------------------------------------------------------------------------------------
# A coin that no address keys (held by an exchange, or native to a chain JAL doesn't support) is looked up by the
# CoinGecko id recorded for the asset. The lookup is a pure function of the answer, so it is checked with a sample.
MARKETS_ANSWER = json.dumps([
    {'id': 'polkadot', 'symbol': 'dot', 'image': "https://coin-images.coingecko.com/coins/images/12171/large/polkadot.jpg?1766533446"},
    {'id': 'algorand', 'symbol': 'algo', 'image': "https://coin-images.coingecko.com/coins/images/4380/large/download.png?1696504978"},
    {'id': 'nologocoin', 'symbol': 'nlc', 'image': "https://coin-images.coingecko.com/coins/images/1/large/missing_large.png"},
    {'id': 'blankcoin', 'symbol': 'blank', 'image': ''},
    {'symbol': 'noid'}
])


def test_coingecko_icons_lookup():
    urls = coingecko_icons_urls(['polkadot', 'algorand', 'polkadot', ''])
    assert len(urls) == 1                                 # One request for every coin, ids de-duplicated and sorted
    assert 'ids=algorand,polkadot' in urls[0]
    assert coingecko_icons_urls([]) == [] and coingecko_icons_urls(['']) == []

    icons = parse_coingecko_icons(MARKETS_ANSWER.encode())
    assert icons == {'polkadot': "https://coin-images.coingecko.com/coins/images/12171/large/polkadot.jpg?1766533446",
                     'algorand': "https://coin-images.coingecko.com/coins/images/4380/large/download.png?1696504978"}
    # A coin the source has no logo for is answered with a placeholder image, which must not be stored as its logo
    assert 'nologocoin' not in icons and 'blankcoin' not in icons
    # A malformed answer yields nothing rather than an exception in the middle of a download
    for broken in (b'', b'not json', b'{}', b'[[]]', None):
        assert parse_coingecko_icons(broken) == {}


def test_coin_icon_is_downloaded_by_its_recorded_id(prepare_db, monkeypatch):
    dot = _crypto_listing('Polkadot', 'DOT', AssetLocation.CEX_EXCHANGE)
    dot.asset().update_data({'coin_id': 'polkadot'})
    requested = []
    monkeypatch.setattr("jal.net.downloader.WebRequest",
                        _fake_web_request({'coins/markets': (200, MARKETS_ANSWER.encode()),
                                           'polkadot.jpg': (200, PNG)}, requested))

    QuoteDownloader().download_icons([JalSymbol(dot.id())])
    assert len(requested) == 2                    # the lookup, then the image itself
    assert 'ids=polkadot' in requested[0]
    assert JalIcons.image(IconOwner.Symbol, dot.id()) == PNG


def test_coin_logos_are_looked_up_in_one_request(prepare_db, monkeypatch):
    listings = []
    for ticker, coin_id in (('DOT', 'polkadot'), ('ALGO', 'algorand'), ('NLC', 'nologocoin')):
        listing = _crypto_listing(f"{ticker} coin", ticker, AssetLocation.CEX_EXCHANGE)
        listing.asset().update_data({'coin_id': coin_id})
        listings.append(JalSymbol(listing.id()))
    requested = []
    monkeypatch.setattr("jal.net.downloader.WebRequest",
                        _fake_web_request({'coins/markets': (200, MARKETS_ANSWER.encode()),
                                           'coin-images.coingecko.com': (200, PNG)}, requested))

    QuoteDownloader().download_icons(listings)
    lookups = [x for x in requested if 'coins/markets' in x]
    assert len(lookups) == 1                       # all three coins are asked about together
    assert 'ids=algorand,nologocoin,polkadot' in lookups[0]
    # The two coins with a logo have it, and the one the source has no logo for is left alone rather than given
    # the placeholder image - it has no other source, so nothing is recorded for it either
    icons = [JalIcons.image(IconOwner.Symbol, x.id()) for x in listings]
    assert icons == [PNG, PNG, None]


# A rate limit is the normal answer of this source, and it says nothing about whether a logo exists - so a coin
# whose lookup didn't come through keeps its icon unset and is asked again on the next download.
def test_rate_limited_coin_lookup_is_retried(prepare_db, monkeypatch):
    dot = _crypto_listing('Polkadot', 'DOT', AssetLocation.CEX_EXCHANGE)
    dot.asset().update_data({'coin_id': 'polkadot'})
    requested = []
    monkeypatch.setattr("jal.net.downloader.WebRequest", _fake_web_request({'coins/markets': (429, '')}, requested))

    QuoteDownloader().download_icons([JalSymbol(dot.id())])
    assert len(requested) == 1                     # the lookup failed, so no image was asked for
    assert JalIcons.image(IconOwner.Symbol, dot.id()) is None      # ... and nothing was recorded
    QuoteDownloader().download_icons([JalSymbol(dot.id())])
    assert len(requested) == 2                     # the next run asks again


# The Trust Wallet repository only carries the tokens someone contributed, so a token with a perfectly good address
# is often absent from it. The coin's own logo answers then - and only when neither source has one is the listing
# settled as having no icon.
def test_coin_logo_is_the_fallback_of_an_unknown_token(prepare_db, monkeypatch):
    token = _crypto_listing('Polkadot on ETH', 'DOT', AssetLocation.ETH_BLOCKCHAIN,
                            '0x21c2c96dbfa137d23e1ea2f47bdd8ee63d8f7e02')
    token.asset().update_data({'coin_id': 'polkadot'})
    requested = []
    monkeypatch.setattr("jal.net.downloader.WebRequest",
                        _fake_web_request({'coins/markets': (200, MARKETS_ANSWER.encode()),
                                           'polkadot.jpg': (200, PNG)}, requested))   # trustwallet answers 404

    QuoteDownloader().download_icons([JalSymbol(token.id())])
    assert [x for x in requested if 'trustwallet' in x]      # the address was tried first
    assert JalIcons.image(IconOwner.Symbol, token.id()) == PNG               # and the coin's logo filled in
