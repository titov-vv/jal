import json
import logging

from jal.constants import AssetLocation
from jal.data_import.statement import Statement_ImportError
from jal.net.chain_fetchers.cardano_keys import stake_address
from jal.net.chain_fetchers.fetcher import ChainFetcher
from jal.net.web_request import WebRequest

# Koios: a public PostgREST API over cardano-db-sync, keyless on its public tier (koios.rest)
_API_ROOT = "https://api.koios.rest/api/v1"
_PAGE_SIZE = 1000          # rows Koios returns at most per answer
_MAX_PAGES = 100           # stops a runaway paging loop
_BODY_LIMIT = 1000         # bytes; the public tier refuses a larger request body
# Blocks a transaction must be buried under before import (~5 minutes); a younger one may still be rolled back
_CONFIRMATIONS = 15
# What tx_info is asked to include: everything the wallet's balance delta and its certificates are read from
_TX_INFO_FLAGS = {"_inputs": True, "_assets": True, "_withdrawals": True, "_certs": True, "_scripts": True,
                  "_metadata": False, "_bytecode": False}


# Stops the import at a transaction of unsupported shape; the cursor stays before it and the next fetch retries it
class _HaltImport(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


# ----------------------------------------------------------------------------------------------------------------------
# Fetches the transaction history of a Cardano wallet from Koios, queried by the wallet's stake address.
#
# The sync cursor holds {'height': block of the newest imported transaction, 'hashes': those imported in that block}:
# Koios' '_after_block_height' includes the block itself, and a halt may stop the import in the middle of a block.
class CardanoFetcher(ChainFetcher):
    location_id = AssetLocation.ADA_BLOCKCHAIN
    native_symbol = 'ADA'
    native_name = "Cardano"
    display_symbol = 'ADA'
    icon_name = 'cardano.png'

    def __init__(self):
        super().__init__()
        self.name = self.tr("&Cardano")
        self._new_cursor = ''
        self._state = {}
        self._stake_address = ''

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
    # WebRequest answers '' for any HTTP error, so an answer that isn't JSON of the expected type stops the fetch -
    # it must never read as "no transactions".
    def _get(self, endpoint: str, params: dict):
        return self._answer(WebRequest(WebRequest.GET, f"{_API_ROOT}/{endpoint}", params=params), endpoint)

    def _post(self, endpoint: str, body: dict):
        return self._answer(WebRequest(WebRequest.POST_JSON, f"{_API_ROOT}/{endpoint}", params=body), endpoint)

    def _answer(self, request, endpoint: str) -> list:
        self._wait_for(request)
        self._report_page()
        try:
            answer = json.loads(request.data())
        except (json.JSONDecodeError, TypeError):
            answer = None
        if not isinstance(answer, list):
            raise Statement_ImportError(self.tr("Unexpected answer from Koios: ") + f"{endpoint}: {request.data()}")
        return answer

    def _tip_height(self) -> int:
        tip = self._get("tip", {})
        try:
            return int(tip[0]['block_height'])
        except (IndexError, KeyError, TypeError, ValueError):
            raise Statement_ImportError(self.tr("Unexpected chain tip from Koios: ") + f"{tip}")

    # Transactions of the stake address from block 'height' on (inclusive), oldest first. Paging by offset is stable
    # here because the list is ascending: new transactions are appended at its end.
    def _transaction_list(self, height: int) -> list:
        collected = []
        params = {"_stake_address": self._stake_address, "order": "block_height.asc,tx_hash.asc",
                  "limit": _PAGE_SIZE}
        if height:
            params["_after_block_height"] = height
        for page_number in range(_MAX_PAGES):
            page = self._get("account_txs", dict(params, offset=page_number * _PAGE_SIZE))
            try:
                collected += [{'tx_hash': str(x['tx_hash']), 'block_height': int(x['block_height'])} for x in page]
            except (KeyError, TypeError, ValueError):
                raise Statement_ImportError(self.tr("Unexpected transaction list from Koios: ") + f"{page}")
            if len(page) < _PAGE_SIZE:
                return collected
        raise Statement_ImportError(self.tr("Too many pages returned by Koios, the history is incomplete"))

    # Full details of the given transactions as {hash: tx_info}, asked for in batches that fit the body limit
    def _transaction_details(self, hashes: list) -> dict:
        details = {}
        batch = []
        for tx_hash in hashes + [None]:
            if tx_hash is not None and len(json.dumps(self._tx_info_body(batch + [tx_hash]))) <= _BODY_LIMIT:
                batch.append(tx_hash)
                continue
            if batch:
                for entry in self._post("tx_info", self._tx_info_body(batch)):
                    if isinstance(entry, dict) and entry.get('tx_hash') in batch:
                        details[entry['tx_hash']] = entry
            batch = [tx_hash]
        missing = [x for x in hashes if x not in details]
        if missing:    # Koios answers an unknown hash with nothing at all, so a gap is checked explicitly
            raise Statement_ImportError(self.tr("Koios returned no details of transaction ") + missing[0])
        return details

    @staticmethod
    def _tx_info_body(hashes: list) -> dict:
        return dict({"_tx_hashes": hashes}, **_TX_INFO_FLAGS)

    # ------------------------------------------------------------------------------------------------------------------
    def _fetch(self) -> str:
        try:
            self._stake_address = stake_address(self._account.address())
        except ValueError as error:
            raise Statement_ImportError(f"{error}")
        self._state = self._load_state()
        confirmed = self._tip_height() - _CONFIRMATIONS
        listed = [x for x in self._transaction_list(self._state['height'])
                  if not (x['block_height'] == self._state['height'] and x['tx_hash'] in self._state['hashes'])]
        recent = [x for x in listed if x['block_height'] > confirmed]
        for transaction in recent:
            self._skip(self.tr("transaction is too recent, it will be imported next time"), transaction['tx_hash'])
        listed = [x for x in listed if x['block_height'] <= confirmed]
        details = self._transaction_details([x['tx_hash'] for x in listed])
        for transaction in sorted(details.values(), key=self._order_of):
            try:
                self._classify(transaction)
            except _HaltImport as halt:
                self._skip(self.tr("import stopped at an unsupported transaction (") + halt.reason
                           + self.tr("); it will be retried next time"), transaction['tx_hash'])
                break
            self._advance(transaction)
        return json.dumps(self._state)

    @staticmethod
    def _order_of(transaction: dict) -> tuple:
        return int(transaction['block_height']), int(transaction.get('tx_block_index', 0))

    def _advance(self, transaction: dict) -> None:
        height = int(transaction['block_height'])
        if height != self._state['height']:
            self._state = {'height': height, 'hashes': []}
        self._state['hashes'].append(transaction['tx_hash'])

    # What the transaction did to the wallet
    def _classify(self, transaction: dict) -> None:
        raise _HaltImport(self.tr("Cardano transactions are not classified yet"))
