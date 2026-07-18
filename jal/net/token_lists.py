import json
import logging
from datetime import datetime, timezone
from PySide6.QtWidgets import QApplication
from jal.constants import Setup, AssetLocation, TokenList, TokenListKind
from jal.db.db import JalDB
from jal.db.token_blacklist import normalize_address
from jal.net.web_request import WebRequest


# Mapping of EVM chain ids (as they appear in 'tokenlists' JSON) to JAL blockchain locations.
# Different lists spell the same chain id as a number or as a string, so lookups go through _evm_chain().
_EVM_CHAIN_IDS = {
    1: AssetLocation.ETH_BLOCKCHAIN,
    42161: AssetLocation.ARB_BLOCKCHAIN
}

# The same, as MyEtherWallet names its networks
_MEW_NETWORKS = {
    'eth': AssetLocation.ETH_BLOCKCHAIN,
    'arb': AssetLocation.ARB_BLOCKCHAIN
}


def _evm_chain(chain_id) -> int:
    try:
        return _EVM_CHAIN_IDS.get(int(chain_id), AssetLocation.UNDEFINED)
    except (TypeError, ValueError):
        return AssetLocation.UNDEFINED


# ----------------------------------------------------------------------------------------------------------------------
# Parsers below convert a downloaded list into a list of {'location_id', 'address', 'symbol', 'name'} records.
# They are pure functions of the downloaded bytes, so they may be tested with stored samples and no network.
# Records that belong to a chain that JAL doesn't know are dropped silently - the lists cover many more chains
# than JAL supports.
def _parse_tokenlist(content: bytes, chains: list) -> list:   # Standard 'tokenlists' schema (Uniswap, CoinGecko)
    tokens = json.loads(content)['tokens']
    entries = []
    for token in tokens:
        location_id = _evm_chain(token.get('chainId'))
        if location_id not in chains:
            continue
        entries.append({'location_id': location_id, 'address': token['address'],
                        'symbol': token.get('symbol', ''), 'name': token.get('name', '')})
    return entries


def _parse_jupiter(content: bytes, chains: list) -> list:   # Jupiter verified token list (Solana only)
    tokens = json.loads(content)
    return [{'location_id': AssetLocation.SOL_BLOCKCHAIN, 'address': x['id'],
             'symbol': x.get('symbol', ''), 'name': x.get('name', '')} for x in tokens if 'id' in x]


def _parse_dappradar(content: bytes, chains: list) -> list:   # {'tokens': [{'address', 'chainId'}]}, chainId as string
    tokens = json.loads(content)['tokens']
    entries = []
    for token in tokens:
        location_id = _evm_chain(token.get('chainId'))
        if location_id not in chains:
            continue
        entries.append({'location_id': location_id, 'address': token['address'], 'symbol': '', 'name': ''})
    return entries


def _parse_mew(content: bytes, chains: list) -> list:   # Flat list of tokens, chain given by a 'network' name
    tokens = json.loads(content)
    entries = []
    for token in tokens:
        location_id = _MEW_NETWORKS.get(token.get('network'), AssetLocation.UNDEFINED)
        if location_id not in chains:
            continue
        entries.append({'location_id': location_id, 'address': token['contract_address'],
                        'symbol': token.get('symbol', ''), 'name': token.get('name', '')})
    return entries


# ----------------------------------------------------------------------------------------------------------------------
# Downloads and caches the token allow-/block- lists that back the unknown/spam token policy (see
# jal.data_import.token_filter). Lists are stored in the 'token_list_cache' table, together with the role they play
# ('kind' column), so a membership check is a single indexed query and never has to know which list an address
# came from. The timestamp of the last successful download of each (list, chain) pair is kept in
# 'token_list_updates' and drives Setup.TOKEN_LIST_REFRESH_INTERVAL.
# Downloading is best-effort: a failed request is logged and the previously cached (stale) content is kept,
# because a missing list must never break the import of on-chain data.
class TokenListProvider(JalDB):
    # Registry of known remote lists - the only place to modify in order to add or remove a source.
    # 'chains' declares the blockchains a list is authoritative for: a list is never consulted for any other
    # chain, so e.g. a Solana allow-list can't vouch for an EVM address.
    SOURCES = {
        TokenList.JUPITER_VERIFIED: {
            'kind': TokenListKind.Allow,
            'chains': [AssetLocation.SOL_BLOCKCHAIN],
            'url': "https://lite-api.jup.ag/tokens/v2/tag?query=verified",
            'parser': _parse_jupiter
        },
        TokenList.UNISWAP_DEFAULT: {
            'kind': TokenListKind.Allow,
            'chains': [AssetLocation.ETH_BLOCKCHAIN, AssetLocation.ARB_BLOCKCHAIN],
            'url': "https://tokens.uniswap.org",
            'parser': _parse_tokenlist
        },
        TokenList.COINGECKO_LIST: {   # This particular list holds Ethereum mainnet tokens only
            'kind': TokenListKind.Allow,
            'chains': [AssetLocation.ETH_BLOCKCHAIN],
            'url': "https://tokens.coingecko.com/uniswap/all.json",
            'parser': _parse_tokenlist
        },
        TokenList.MEW_TOKENS: {
            'kind': TokenListKind.Allow,
            'chains': [AssetLocation.ETH_BLOCKCHAIN, AssetLocation.ARB_BLOCKCHAIN],
            'url': "https://raw.githubusercontent.com/MyEtherWallet/ethereum-lists/master/dist/master-file.json",
            'parser': _parse_mew
        },
        # The only block-list in use. It is auto-generated but updated rarely (the copy checked on 2026-07-18 was
        # generated in 2024), and it carries no Arbitrum entries - block-lists are a bonus, the dust heuristic
        # in TokenFilter is what actually keeps unsolicited tokens out.
        TokenList.DAPPRADAR_BLACKLIST: {
            'kind': TokenListKind.Block,
            'chains': [AssetLocation.ETH_BLOCKCHAIN],
            'url': "https://raw.githubusercontent.com/dappradar/tokens-blacklist/main/all-tokens.json",
            'parser': _parse_dappradar
        }
    }

    # 'fetcher' is a callable url -> bytes; the default one performs a real HTTP GET. Tests supply their own.
    def __init__(self, fetcher=None):
        super().__init__()
        self._fetch = fetcher if fetcher is not None else self._http_get

    @staticmethod
    def _http_get(url: str) -> bytes:
        request = WebRequest(WebRequest.GET, url)
        while request.isRunning():
            QApplication.processEvents()
        return request.data()

    # True if the address is present on any allow-list that covers the given chain
    def is_allowlisted(self, location_id: int, address: str) -> bool:
        return self._member(TokenListKind.Allow, location_id, address)

    # True if the address is present on any block-list that covers the given chain
    def is_blocklisted(self, location_id: int, address: str) -> bool:
        return self._member(TokenListKind.Block, location_id, address)

    def _member(self, kind: int, location_id: int, address: str) -> bool:
        address = normalize_address(location_id, address)
        if not address:
            return False
        found = self._read("SELECT id FROM token_list_cache "
                           "WHERE kind=:kind AND location_id=:location_id AND address=:address",
                           [(":kind", kind), (":location_id", location_id), (":address", address)])
        return found is not None

    # Downloads the lists that cover 'location_id' (or all known lists if it is None). Pairs downloaded less than
    # Setup.TOKEN_LIST_REFRESH_INTERVAL ago are skipped unless 'force' is set.
    def refresh(self, location_id: int = None, force: bool = False) -> None:
        for list_id, source in self.SOURCES.items():
            chains = [x for x in source['chains'] if location_id is None or x == location_id]
            chains = [x for x in chains if force or self._stale(list_id, x)]
            if not chains:
                continue
            try:
                content = self._fetch(source['url'])
                entries = source['parser'](content, chains)
            except Exception as error:   # Any network or format problem keeps the previously cached content
                logging.warning(f"Failed to update token list '{TokenList().get_name(list_id)}': {error}")
                continue
            for chain in chains:
                self._store(list_id, source['kind'], chain,
                            [x for x in entries if x['location_id'] == chain])

    # True if the (list, chain) pair was never downloaded or was downloaded too long ago
    def _stale(self, list_id: int, location_id: int) -> bool:
        updated = self._read("SELECT updated_ts FROM token_list_updates "
                             "WHERE list_id=:list_id AND location_id=:location_id",
                             [(":list_id", list_id), (":location_id", location_id)])
        if updated is None:
            return True
        age = int(datetime.now(tz=timezone.utc).timestamp()) - int(updated)
        return age >= Setup.TOKEN_LIST_REFRESH_INTERVAL

    # Replaces the cached content of one (list, chain) pair and marks it as updated now
    def _store(self, list_id: int, kind: int, location_id: int, entries: list) -> None:
        self._exec("DELETE FROM token_list_cache WHERE list_id=:list_id AND location_id=:location_id",
                   [(":list_id", list_id), (":location_id", location_id)])
        for entry in entries:
            address = normalize_address(location_id, entry['address'])
            if not address:
                continue
            self._exec("INSERT OR REPLACE INTO token_list_cache(list_id, kind, location_id, address, symbol, name) "
                       "VALUES(:list_id, :kind, :location_id, :address, :symbol, :name)",
                       [(":list_id", list_id), (":kind", kind), (":location_id", location_id),
                        (":address", address), (":symbol", entry.get('symbol', '')), (":name", entry.get('name', ''))])
        self._exec("INSERT OR REPLACE INTO token_list_updates(id, list_id, location_id, updated_ts) "
                   "VALUES((SELECT id FROM token_list_updates WHERE list_id=:list_id AND location_id=:location_id), "
                   ":list_id, :location_id, :updated_ts)",
                   [(":list_id", list_id), (":location_id", location_id),
                    (":updated_ts", int(datetime.now(tz=timezone.utc).timestamp()))], commit=True)
        logging.info(f"Token list '{TokenList().get_name(list_id)}' for chain {location_id}: "
                     f"{len(entries)} entries cached")
