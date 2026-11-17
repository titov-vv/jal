import hashlib
import json
import logging
from decimal import Decimal

import xxhash
from bip_utils import SS58Decoder

from jal.constants import AssetLocation
from jal.data_import.statement import Statement_ImportError
from jal.db.token_blacklist import is_polkadot_address
from jal.net.chain_fetchers.fetcher import ChainFetcher
from jal.net.web_request import WebRequest

# Nova Wallet's public SubQuery indexer of Polkadot Asset Hub (github.com/novasamatech/subquery-history), keyless
INDEXER_URL = "https://subquery-history-polkadot-ah-prod.novasama-tech.org"
RPC_URL = "https://polkadot-asset-hub-rpc.polkadot.io"      # keyless archive node of Polkadot Asset Hub
_PAGE_SIZE = 100
_MAX_PAGES = 100            # stops a runaway paging loop
_PLANCK_DIGITS = 10         # 1 DOT = 10^10 plancks
_HISTORY_QUERY = """
query($address: String!, $floor: Int!, $top: Int!, $first: Int!, $offset: Int!) {
  historyElements(first: $first, offset: $offset, orderBy: [BLOCK_NUMBER_ASC, ID_ASC],
                  filter: {address: {equalTo: $address},
                           blockNumber: {greaterThanOrEqualTo: $floor, lessThanOrEqualTo: $top}}) {
    totalCount
    nodes { id blockNumber extrinsicIdx extrinsicHash timestamp extrinsic transfer assetTransfer reward poolReward swap }
  }
}"""
_INDEXED_QUERY = "{ _metadata { lastProcessedHeight } }"
# Storage key prefixes: twox128(pallet) + twox128(item), see docs.polkadot.com "storage keys"
_SYSTEM_ACCOUNT = "26aa394eea5630e07c48ae0c9558cef7" "b99d880ec681799c0cf30e8886371da9"
_POOL_MEMBERS = "7a6d38deaa01cb6e76ee69889f169627" "3c5f69e270d5b7a07f9996fe9e4e0488"
_POOL_METADATA = "7a6d38deaa01cb6e76ee69889f169627" "b5f3822e35ca2f31ce3526eab1363fd2"


# Stops the import at an extrinsic of unsupported shape; the cursor stays before it and the next fetch retries it
class _HaltImport(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


# ----------------------------------------------------------------------------------------------------------------------
# Fetches the history of a Polkadot account on Asset Hub, where DOT balances and staking live since the Asset Hub
# migration of 4 Nov 2025; the relay chain is not read.
#
# History comes from the indexer as elements, one per thing that touched the account, grouped per extrinsic here.
# Amounts the indexer doesn't carry (a pool bond) and the pool's state are read from the node at a given block.
# The sync cursor holds {'height': block of the newest imported extrinsic, 'hashes': keys of those imported there}.
class PolkadotFetcher(ChainFetcher):
    location_id = AssetLocation.DOT_BLOCKCHAIN
    native_symbol = 'DOT'
    native_name = "Polkadot"
    display_symbol = 'DOT'
    icon_name = 'polkadot.png'

    def __init__(self):
        super().__init__()
        self.name = self.tr("&Polkadot")
        self._new_cursor = ''
        self._state = {}

    def _load_state(self) -> dict:
        stored = self._cursor()
        if not stored:
            return {'height': 0, 'hashes': []}
        try:
            state = json.loads(stored)
            return {'height': int(state['height']), 'hashes': list(state['hashes'])}
        except (json.JSONDecodeError, TypeError, ValueError, KeyError):
            # Starting over is safe: the import deduplicates by transaction hash what it fetches twice
            logging.warning(self.tr("Unreadable sync position of account ") + self._account.name())
            return {'height': 0, 'hashes': []}

    # ------------------------------------------------------------------------------------------------------------------
    # WebRequest answers '' for any HTTP error, so an answer without 'data' stops the fetch - it must never read as
    # "no history"
    def _query(self, query: str, variables: dict) -> dict:
        request = WebRequest(WebRequest.POST_JSON, INDEXER_URL, params={"query": query, "variables": variables})
        self._wait_for(request)
        self._report_page()
        try:
            answer = json.loads(request.data())
        except (json.JSONDecodeError, TypeError):
            answer = None
        if not isinstance(answer, dict) or answer.get('errors') or not isinstance(answer.get('data'), dict):
            raise Statement_ImportError(self.tr("Unexpected answer from the Polkadot indexer: ") + f"{request.data()}")
        return answer['data']

    # History elements of the wallet in blocks floor..top, oldest first. The range is final, so offsets are stable.
    # The end is 'totalCount', not a short page: a server may cap a page below the size asked for.
    def _history(self, floor: int, top: int) -> list:
        elements = []
        for _page in range(_MAX_PAGES):
            variables = {"address": self._account.address(), "floor": floor, "top": top,
                         "first": _PAGE_SIZE, "offset": len(elements)}
            answer = self._query(_HISTORY_QUERY, variables).get('historyElements') or {}
            page, total = answer.get('nodes'), answer.get('totalCount')
            if not isinstance(page, list) or not isinstance(total, int):
                raise Statement_ImportError(self.tr("Unexpected history page from the Polkadot indexer"))
            elements += page
            if not page or len(elements) >= total:
                return elements
        raise Statement_ImportError(self.tr("Too many pages returned by the Polkadot indexer, the history is incomplete"))

    def _indexed_height(self) -> int:
        try:
            return int(self._query(_INDEXED_QUERY, {})['_metadata']['lastProcessedHeight'])
        except (KeyError, TypeError, ValueError):
            raise Statement_ImportError(self.tr("Unexpected indexer status from the Polkadot indexer"))

    # ------------------------------------------------------------------------------------------------------------------
    def _rpc(self, method: str, params: list):
        request = WebRequest(WebRequest.POST_JSON, RPC_URL,
                             params={"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
        self._wait_for(request)
        try:
            answer = json.loads(request.data())
        except (json.JSONDecodeError, TypeError):
            answer = None
        if not isinstance(answer, dict) or 'result' not in answer:
            raise Statement_ImportError(self.tr("Unexpected answer from Polkadot RPC: ") + f"{method}: {request.data()}")
        return answer['result']

    def _final_height(self) -> int:
        header = self._rpc("chain_getHeader", [self._rpc("chain_getFinalizedHead", [])])
        try:
            return int(header['number'], 16)
        except (KeyError, TypeError, ValueError):
            raise Statement_ImportError(self.tr("Unexpected final block from Polkadot RPC: ") + f"{header}")

    def _block_hash(self, height: int) -> str:
        block_hash = self._rpc("chain_getBlockHash", [height])
        if not isinstance(block_hash, str):
            raise Statement_ImportError(self.tr("Unknown Polkadot block: ") + f"{height}")
        return block_hash

    # SCALE bytes of a storage item at the block, None if it is empty there
    def _storage(self, key: str, height: int):
        value = self._rpc("state_getStorage", ["0x" + key, self._block_hash(height)])
        return None if value is None else self._hex(value)

    # A runtime API call answering a u128 (Balance), at the block
    def _runtime_u128(self, call: str, arguments: bytes, height: int) -> int:
        value = self._hex(self._rpc("state_call", [call, "0x" + arguments.hex(), self._block_hash(height)]))
        if len(value) != 16:
            raise Statement_ImportError(self.tr("Unexpected answer from Polkadot RPC: ") + f"{call}: {value.hex()}")
        return int.from_bytes(value, 'little')

    # (free, reserved) plancks of the wallet at the block; a pool bond is held in 'reserved' (delegated staking)
    def _balances(self, height: int) -> tuple:
        value = self._storage(_SYSTEM_ACCOUNT + self._blake2_128_concat(self._account_id()), height)
        if value is None:
            return 0, 0
        if len(value) < 48:
            raise Statement_ImportError(self.tr("Unreadable Polkadot account data: ") + value.hex())
        return int.from_bytes(value[16:32], 'little'), int.from_bytes(value[32:48], 'little')

    # (pool id, points) of the wallet's pool membership at the block, None if it isn't a member there
    def _pool_member(self, height: int):
        value = self._storage(_POOL_MEMBERS + self._twox64_concat(self._account_id()), height)
        if value is None:
            return None
        if len(value) < 20:
            raise Statement_ImportError(self.tr("Unreadable Polkadot pool membership: ") + value.hex())
        return int.from_bytes(value[0:4], 'little'), int.from_bytes(value[4:20], 'little')

    # Plancks of the wallet's pool bond at the block, rewards that were compounded into it included
    def _pool_bond(self, height: int) -> int:
        return self._runtime_u128("NominationPoolsApi_member_total_balance", self._account_id(), height)

    # Plancks of pool reward the wallet may claim at the block
    def _pending_rewards(self, height: int) -> int:
        return self._runtime_u128("NominationPoolsApi_pending_rewards", self._account_id(), height)

    # The name a pool's operator gave it, '' if none
    def _pool_name(self, pool_id: int, height: int) -> str:
        value = self._storage(_POOL_METADATA + self._twox64_concat(pool_id.to_bytes(4, 'little')), height)
        if not value:
            return ''
        length, offset = self._compact(value)
        return value[offset:offset + length].decode('utf-8', errors='replace').strip()

    # ------------------------------------------------------------------------------------------------------------------
    def _fetch(self) -> str:
        if not is_polkadot_address(self._account.address()):
            raise Statement_ImportError(self.tr("Not a valid Polkadot address: ") + self._account.address())
        self._state = self._load_state()
        top = min(self._final_height(), self._indexed_height())
        extrinsics = self._extrinsics(self._history(self._state['height'], top))
        for extrinsic in [x for x in extrinsics if self._is_new(x)]:
            try:
                self._classify(extrinsic)
            except _HaltImport as halt:
                self._skip(self.tr("import stopped at an unsupported transaction (") + halt.reason
                           + self.tr("); it will be retried next time"), extrinsic['hash'])
                break
            self._advance(extrinsic)
        return json.dumps(self._state)

    # Elements grouped per extrinsic, oldest first. An element outside any extrinsic (a transfer delivered by XCM,
    # a reward paid by the runtime) stands alone under its own id.
    def _extrinsics(self, elements: list) -> list:
        grouped = {}
        for element in elements:
            height = self._height(element)
            index = element.get('extrinsicIdx')
            key = f"{height}-{index}" if index is not None else str(element.get('id', ''))
            if not key:
                raise Statement_ImportError(self.tr("Polkadot history element without an id: ") + f"{element}")
            record = grouped.setdefault(key, {'key': key, 'hash': element.get('extrinsicHash') or key,
                                              'height': height, 'index': index,
                                              'timestamp': self._timestamp(element), 'elements': []})
            record['elements'].append(element)
        return sorted(grouped.values(), key=lambda x: (x['height'], x['index'] is None, x['index'] or 0, x['key']))

    def _is_new(self, extrinsic: dict) -> bool:
        if extrinsic['height'] != self._state['height']:
            return extrinsic['height'] > self._state['height']
        return extrinsic['key'] not in self._state['hashes']

    def _advance(self, extrinsic: dict) -> None:
        if extrinsic['height'] != self._state['height']:
            self._state = {'height': extrinsic['height'], 'hashes': []}
        self._state['hashes'].append(extrinsic['key'])

    def _classify(self, extrinsic: dict) -> None:
        raise _HaltImport(self.tr("Polkadot transactions are not classified yet"))

    # ------------------------------------------------------------------------------------------------------------------
    def _account_id(self) -> bytes:
        return SS58Decoder.Decode(self._account.address())[1]

    @staticmethod
    def _twox64_concat(data: bytes) -> str:
        return xxhash.xxh64(data, seed=0).intdigest().to_bytes(8, 'little').hex() + data.hex()

    @staticmethod
    def _blake2_128_concat(data: bytes) -> str:
        return hashlib.blake2b(data, digest_size=16).hexdigest() + data.hex()

    # SCALE compact integer at the start of the data: (value, its length in bytes)
    @staticmethod
    def _compact(data: bytes) -> tuple:
        mode = data[0] & 0b11
        if mode == 0:
            return data[0] >> 2, 1
        if mode == 1:
            return int.from_bytes(data[:2], 'little') >> 2, 2
        if mode == 2:
            return int.from_bytes(data[:4], 'little') >> 2, 4
        length = (data[0] >> 2) + 4
        return int.from_bytes(data[1:1 + length], 'little'), 1 + length

    @staticmethod
    def _hex(value) -> bytes:
        try:
            return bytes.fromhex(value[2:] if value.startswith("0x") else value)
        except (AttributeError, ValueError):
            raise Statement_ImportError(f"Unreadable Polkadot RPC value: {value}")

    @staticmethod
    def _height(element: dict) -> int:
        try:
            return int(element['blockNumber'])
        except (KeyError, TypeError, ValueError):
            raise Statement_ImportError(f"Unreadable Polkadot block number: {element}")

    @staticmethod
    def _timestamp(element: dict) -> int:
        try:
            return int(element['timestamp'])
        except (KeyError, TypeError, ValueError):
            raise Statement_ImportError(f"Unreadable Polkadot block time: {element}")

    # Amounts are summed as integer plancks
    @staticmethod
    def _planck(value) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            raise Statement_ImportError(f"Unreadable Polkadot amount: {value}")

    @staticmethod
    def _dot(planck: int) -> Decimal:
        return Decimal(f"{planck}e-{_PLANCK_DIGITS}")
