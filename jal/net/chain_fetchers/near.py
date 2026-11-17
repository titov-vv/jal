import json
import logging
import time
from decimal import Decimal

from PySide6.QtCore import QThread
from PySide6.QtWidgets import QApplication

from jal.constants import AssetLocation
from jal.data_import.statement import Statement_ImportError
from jal.db.token_blacklist import is_near_account
from jal.net.chain_fetchers.fetcher import ChainFetcher
from jal.net.web_request import WebRequest

# NearBlocks API v3 (api.nearblocks.io/api-docs), keyless; v1/v2 are switched off on 22 Nov 2026
_API_ROOT = "https://api.nearblocks.io/v3/accounts"
_RPC = "https://rpc.mainnet.fastnear.com"     # keyless NEAR JSON-RPC
_PAGE_SIZE = 100            # the largest 'limit' v3 accepts
_MAX_PAGES = 100            # stops a runaway paging loop
_CALL_SPACING = 6.5         # seconds between NearBlocks calls; the keyless tier allows ~10 a minute
_RATE_WAIT = 60             # seconds to wait after an HTTP 429 before the call is repeated
_RATE_RETRIES = 3
_TOO_MANY_REQUESTS = 429
# Blocks a transaction must be below the final block before import, so that its gas refunds have landed
_REFUND_WAIT = 10
# Blocks read below the cursor, so that a late refund of an imported transaction is recognized as such
_LOOKBACK = 100
_YOCTO_DIGITS = 24          # 1 NEAR = 10^24 yoctoNEAR
# The three lists a transaction is put together from: {endpoint: key of its rows in the transaction record}
_LISTS = {"txns": "txns", "receipts": "receipts", "staking-txns": "staking"}


# Stops the import at a transaction of unsupported shape; the cursor stays before it and the next fetch retries it
class _HaltImport(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


# ----------------------------------------------------------------------------------------------------------------------
# Fetches the transaction history of a NEAR account from NearBlocks.
#
# A transaction is put together from its rows in three lists: the transaction itself (deposit, fee), the receipts
# that reached the wallet (transfers, gas refunds, a pool's return) and its staking events.
# The sync cursor holds {'height': height of the newest imported transaction, 'hashes': those imported at it}.
class NearFetcher(ChainFetcher):
    location_id = AssetLocation.NEAR_BLOCKCHAIN
    native_symbol = 'NEAR'
    native_name = "NEAR"
    display_symbol = 'NEAR'
    icon_name = 'near.png'

    def __init__(self):
        super().__init__()
        self.name = self.tr("&NEAR")
        self._new_cursor = ''
        self._state = {}
        self._last_call = 0.0     # time.monotonic() of the latest NearBlocks call

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
    # One page of a NearBlocks list. WebRequest answers '' for any HTTP error, so an answer that isn't the expected
    # envelope stops the fetch - it must never read as "no transactions".
    def _get(self, endpoint: str, params: dict) -> dict:
        url = f"{_API_ROOT}/{self._account.address()}/{endpoint}"
        for _attempt in range(_RATE_RETRIES + 1):
            self._pause(self._last_call + _CALL_SPACING - time.monotonic())
            request = WebRequest(WebRequest.GET, url, params=params, expected_errors=(_TOO_MANY_REQUESTS,))
            self._wait_for(request)
            self._last_call = time.monotonic()
            if request.status() != _TOO_MANY_REQUESTS:
                break
            logging.info(self.tr("NearBlocks rate limit reached, waiting ") + f"{_RATE_WAIT} s")
            self._pause(_RATE_WAIT)
        else:
            raise Statement_ImportError(self.tr("NearBlocks keeps refusing requests, try again later"))
        self._report_page()
        try:
            answer = json.loads(request.data())
        except (json.JSONDecodeError, TypeError):
            answer = None
        if not isinstance(answer, dict) or not isinstance(answer.get('data'), list):
            raise Statement_ImportError(self.tr("Unexpected answer from NearBlocks: ") + f"{endpoint}: {request.data()}")
        return answer

    # Waits without freezing the window; a press of 'Stop' ends the fetch here as in _wait_for()
    def _pause(self, seconds: float) -> None:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            QApplication.processEvents()
            if self._cancelled:
                raise KeyboardInterrupt
            QThread.msleep(100)

    # Rows of a list from the newest down to block 'floor' (inclusive), newest first
    def _list(self, endpoint: str, floor: int) -> list:
        rows = []
        params = {"limit": _PAGE_SIZE}
        for _page in range(_MAX_PAGES):
            answer = self._get(endpoint, params)
            page = answer['data']
            rows += page
            next_page = (answer.get('meta') or {}).get('next_page')
            if not page or not next_page or self._height(page[-1]) < floor:
                return [x for x in rows if self._height(x) >= floor]
            params = {"limit": _PAGE_SIZE, "next": next_page}
        raise Statement_ImportError(self.tr("Too many pages returned by NearBlocks, the history is incomplete"))

    def _final_height(self) -> int:
        body = {"jsonrpc": "2.0", "id": "jal", "method": "block", "params": {"finality": "final"}}
        request = WebRequest(WebRequest.POST_JSON, _RPC, params=body)
        self._wait_for(request)
        try:
            return int(json.loads(request.data())['result']['header']['height'])
        except (json.JSONDecodeError, TypeError, KeyError, ValueError):
            raise Statement_ImportError(self.tr("Unexpected final block from NEAR RPC: ") + f"{request.data()}")

    # ------------------------------------------------------------------------------------------------------------------
    def _fetch(self) -> str:
        if not is_near_account(self._account.address()):
            raise Statement_ImportError(self.tr("Not a valid NEAR account: ") + self._account.address())
        self._state = self._load_state()
        final = self._final_height()
        floor = max(self._state['height'] - _LOOKBACK, 0)
        transactions = self._transactions({endpoint: self._list(endpoint, floor) for endpoint in _LISTS})
        listed = [x for x in transactions if self._is_new(x)]
        for transaction in listed:
            if transaction['height'] > final - _REFUND_WAIT:
                self._skip(self.tr("transaction is too recent, it will be imported next time"), transaction['hash'])
        for transaction in [x for x in listed if x['height'] <= final - _REFUND_WAIT]:
            try:
                self._classify(transaction)
            except _HaltImport as halt:
                self._skip(self.tr("import stopped at an unsupported transaction (") + halt.reason
                           + self.tr("); it will be retried next time"), transaction['hash'])
                break
            self._advance(transaction)
        return json.dumps(self._state)

    # The rows of the lists grouped by transaction, oldest first. A transaction stands at the lowest height and the
    # earliest time among its rows: an incoming transfer has no row of its own in '/txns', only its receipt.
    def _transactions(self, lists: dict) -> list:
        grouped = {}
        for endpoint, rows in lists.items():
            for row in rows:
                tx_hash = row.get('transaction_hash')
                if not tx_hash:
                    raise Statement_ImportError(self.tr("NearBlocks row without a transaction hash: ") + f"{row}")
                record = grouped.setdefault(tx_hash, {'hash': tx_hash, 'height': self._height(row),
                                                      'timestamp': self._timestamp(row),
                                                      **{key: [] for key in _LISTS.values()}})
                record[_LISTS[endpoint]].append(row)
                record['height'] = min(record['height'], self._height(row))
                record['timestamp'] = min(record['timestamp'], self._timestamp(row))
        return sorted(grouped.values(), key=lambda x: (x['height'], x['hash']))

    def _is_new(self, transaction: dict) -> bool:
        if transaction['height'] != self._state['height']:
            return transaction['height'] > self._state['height']
        return transaction['hash'] not in self._state['hashes']

    def _advance(self, transaction: dict) -> None:
        if transaction['height'] != self._state['height']:
            self._state = {'height': transaction['height'], 'hashes': []}
        self._state['hashes'].append(transaction['hash'])

    # What the transaction did to the wallet
    def _classify(self, transaction: dict) -> None:
        raise _HaltImport(self.tr("NEAR transactions are not classified yet"))

    # ------------------------------------------------------------------------------------------------------------------
    # v3 gives every number as a string: heights, nanosecond timestamps and yoctoNEAR amounts
    @staticmethod
    def _height(row: dict) -> int:
        try:
            return int(row['block']['block_height'])
        except (KeyError, TypeError, ValueError):
            raise Statement_ImportError(f"Unreadable NEAR block height: {row}")

    @staticmethod
    def _timestamp(row: dict) -> int:
        try:
            return int(row['block']['block_timestamp']) // 1_000_000_000
        except (KeyError, TypeError, ValueError):
            raise Statement_ImportError(f"Unreadable NEAR block time: {row}")

    # Amounts are summed as integer yocto; a division would round to the 28 digits of the default Decimal context
    @staticmethod
    def _yocto(value) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            raise Statement_ImportError(f"Unreadable NEAR amount: {value}")

    @staticmethod
    def _near(yocto: int) -> Decimal:
        return Decimal(f"{yocto}e-{_YOCTO_DIGITS}")
