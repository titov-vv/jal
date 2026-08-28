import json
from bip_utils.utils.crypto import Kekkak256   # bip_utils spells the Keccak-256 class this way (sic)
from jal.constants import AssetLocation, PredefinedAsset, SymbolId, Setup
from jal.db.symbol import JalSymbol

# ----------------------------------------------------------------------------------------------------------------------
# Icon (logo) URL of an asset listing. Both sources below are keyless and answer 404 for something they don't know,
# which is the answer the caller stores as "no icon exists" (see JalIcons.store).
#
# Coins and tokens come from the Trust Wallet asset repository - it is keyed by chain + contract address, which is
# exactly how JAL identifies a token, so the icon is looked up by the same key the quote download uses and a token
# is never given the logo of a same-named token from another chain. A listing of the same asset on another chain is
# a separate row of 'asset_symbol' with its own address, so it gets its own icon for free.
#
# Everything else (shares, ETFs, bonds) comes from Parqet, which serves logos both by ISIN and by ticker. The ISIN
# is preferred: it is unambiguous worldwide, while a ticker is only unique within an exchange.
TRUSTWALLET_URL = "https://raw.githubusercontent.com/trustwallet/assets/master/blockchains/{chain}/{path}"
PARQET_URL = "https://assets.parqet.com/logos/{key}/{value}?format=png&size={size}"

# Folder that keeps the assets of each chain in the Trust Wallet repository. Hyperliquid is stored under the name
# of its EVM chain ('hyperevm') - the only place where the folder name isn't a plain spelling of the chain.
_TRUSTWALLET_CHAINS = {
    AssetLocation.ETH_BLOCKCHAIN: 'ethereum',
    AssetLocation.ARB_BLOCKCHAIN: 'arbitrum',
    AssetLocation.BTC_BLOCKCHAIN: 'bitcoin',
    AssetLocation.SOL_BLOCKCHAIN: 'solana',
    AssetLocation.TRX_BLOCKCHAIN: 'tron',
    AssetLocation.HL_BLOCKCHAIN: 'hyperevm',
    AssetLocation.AVAX_BLOCKCHAIN: 'avalanchec'
}

# Folder whose 'info' logo is the logo of the coin native to each chain. It is not always the chain's own folder -
# the native coin of Arbitrum is bridged ETH, so it wears the Ethereum logo and not the Arbitrum one (the same
# split _LLAMA_NATIVE_COINS makes in the quote downloader). Which ticker counts as the native coin of a chain is
# defined once, in AssetLocation.is_native_coin().
_NATIVE_COIN_FOLDERS = {
    AssetLocation.ETH_BLOCKCHAIN: 'ethereum',
    AssetLocation.ARB_BLOCKCHAIN: 'ethereum',
    AssetLocation.BTC_BLOCKCHAIN: 'bitcoin',
    AssetLocation.SOL_BLOCKCHAIN: 'solana',
    AssetLocation.TRX_BLOCKCHAIN: 'tron',
    AssetLocation.AVAX_BLOCKCHAIN: 'avalanchec',
    AssetLocation.HL_BLOCKCHAIN: 'hyperevm'
}

# A coin held on a centralized exchange has no contract address to be keyed by at all, so only a coin that is the
# native coin of a chain JAL knows can be recognized - by its ticker. A ticker that is not one of them (a token
# held on an exchange, e.g. USDT) gets no icon: a ticker is not unique, and a wrong icon is worse than no icon.
_CEX_NATIVE_COINS = {AssetLocation.native_ticker_of(location): folder
                     for location, folder in _NATIVE_COIN_FOLDERS.items()}


# Returns the EIP-55 checksummed spelling of an EVM address (mixed-case, where the case of each hex letter is a
# checksum bit). JAL stores addresses in whatever case the chain data provided them in, but the Trust Wallet
# repository names its folders by the checksummed form only - a lower-case address gets a 404 there.
# An input that isn't a 0x-prefixed 20-byte hex string is returned unchanged: it is not an EVM address at all
# (a Solana mint or a Tron 'T...' address is used as it is stored, both are case-sensitive by nature).
def eip55_address(address: str) -> str:
    if not address.startswith('0x') or len(address) != 42:
        return address
    body = address[2:].lower()
    try:
        int(body, 16)
    except ValueError:
        return address
    digest = Kekkak256.QuickDigest(body.encode()).hex()
    return '0x' + ''.join(char.upper() if int(digest[i], 16) > 7 else char for i, char in enumerate(body))


# Returns the URL that serves the icon of the given listing, or '' if no source can be asked about it (a currency,
# a listing with neither an address nor an ISIN nor a ticker, a coin on an exchange that isn't a native coin, ...).
# An empty result means "don't ask anyone", not "the source has no icon" - the caller makes no record of it and
# may try again later, e.g. after an ISIN was added to the listing.
def icon_url(symbol: JalSymbol) -> str:
    location = symbol.location()
    if location in _TRUSTWALLET_CHAINS:
        address_id = AssetLocation.address_id_of(location)
        address = symbol.identifier(address_id) if address_id is not None else ''
        if address:
            return TRUSTWALLET_URL.format(chain=_TRUSTWALLET_CHAINS[location],
                                          path=f"assets/{eip55_address(address)}/logo.png")
        # Without an address the only listing that can still be identified is the native coin of the chain, and
        # only by its ticker. A token whose address is unknown gets no icon at all.
        if AssetLocation.is_native_coin(location, symbol.symbol()):
            return TRUSTWALLET_URL.format(chain=_NATIVE_COIN_FOLDERS[location], path="info/logo.png")
        return ''
    if location == AssetLocation.CEX_EXCHANGE:
        folder = _CEX_NATIVE_COINS.get(symbol.symbol().upper())
        return '' if folder is None else TRUSTWALLET_URL.format(chain=folder, path="info/logo.png")
    # Parqet below is a source of company and fund logos, so only a security is looked up there. A currency is
    # displayed with the flag of its country, and a coin whose location says nothing (an import that couldn't tell
    # where it is held) has no key Parqet could answer to - asking would only record a 404 for it forever.
    if symbol.asset().type() in (PredefinedAsset.Money, PredefinedAsset.Crypto):
        return ''
    isin = symbol.identifier(SymbolId.ISIN)
    if isin:
        return PARQET_URL.format(key='isin', value=isin, size=Setup.ICON_STORED_SIZE)
    return PARQET_URL.format(key='symbol', value=symbol.symbol(), size=Setup.ICON_STORED_SIZE) if symbol.symbol() else ''


# ----------------------------------------------------------------------------------------------------------------------
# The logo of a coin that no address keys - a coin held by an exchange, or one native to a chain JAL doesn't support -
# comes from CoinGecko, by the id recorded for the asset (AssetData.CoinGeckoId). The image itself sits on a CDN under
# a name that can't be derived from the id, so it takes one lookup to learn the URL. That lookup is made for every
# pending coin at once: the per-coin endpoint allows about five calls a minute and answers 429 after that, while this
# one returns up to _COINGECKO_IDS_PER_REQUEST coins in a single answer (verified 2026-07-29).
# 'vs_currency' is required by the endpoint although only the logo is taken from the answer.
COINGECKO_ICONS_URL = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&per_page={per_page}&ids={ids}"
_COINGECKO_IDS_PER_REQUEST = 250   # Maximum the endpoint serves in one answer


# Splits the given coin ids into as few requests as the source allows and returns the URL of each. Ids are
# de-duplicated (several listings of one asset share its id) and sorted, so the same set always asks the same way.
def coingecko_icons_urls(coin_ids: list) -> list:
    ids = sorted({x for x in coin_ids if x})
    return [COINGECKO_ICONS_URL.format(per_page=_COINGECKO_IDS_PER_REQUEST, ids=','.join(chunk))
            for chunk in (ids[i:i + _COINGECKO_IDS_PER_REQUEST]
                          for i in range(0, len(ids), _COINGECKO_IDS_PER_REQUEST))]


# Converts an answer of the URL above into {coin id: logo url}. It is a pure function of the downloaded bytes, so it
# may be tested with a stored sample. A coin the source has no logo for is left out of the result: it is answered
# with a placeholder image (its file name starts with 'missing'), which is not a logo and must not be stored as one.
def parse_coingecko_icons(content) -> dict:
    try:
        coins = json.loads(content)
    except (json.decoder.JSONDecodeError, TypeError, ValueError):
        return {}
    icons = {}
    for coin in coins if isinstance(coins, list) else []:
        try:
            coin_id, url = coin['id'], coin.get('image', '')
        except (TypeError, KeyError):
            continue
        if url and not url.rsplit('/', 1)[-1].startswith('missing'):
            icons[coin_id] = url
    return icons
