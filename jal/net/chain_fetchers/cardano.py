import json
import logging
from decimal import Decimal

from PySide6.QtCore import QT_TRANSLATE_NOOP

from jal.constants import AssetLocation
from jal.data_import.statement import Statement_ImportError, JSF
from jal.db.settings_registry import SettingsRegistry, SettingDescriptor
from jal.net.chain_fetchers.cardano_keys import stake_address
from jal.net.chain_fetchers.fetcher import ChainFetcher
from jal.net.web_request import WebRequest

JAL_FETCHER_CLASS = "CardanoFetcher"

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
_LOVELACE = Decimal('1000000')     # 1 ADA


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
    native_dust_threshold = '1.5'    # an output can't hold less than ~1 ADA, so dust is sent at just about that

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

    # ------------------------------------------------------------------------------------------------------------------
    # What the transaction did to the wallet, decided on its own lovelace: inputs and outputs carrying its stake
    # address, withdrawals from its reward account. With 'sent' = spent + withdrawn - received - fee:
    #   spent nothing -> incoming transfer;  withdrew -> staking reward;  sent > 0 -> outgoing transfer;
    #   sent = 0 -> fee only (an own move, a delegation);  sent < 0 -> co-funded, halts
    def _classify(self, transaction: dict) -> None:
        tx_hash = transaction['tx_hash']
        own_inputs = [x for x in transaction.get('inputs') or [] if self._is_own(x)]
        own_outputs = [x for x in transaction.get('outputs') or [] if self._is_own(x)]
        self._check_shape(transaction, own_inputs + own_outputs)
        timestamp = int(transaction.get('tx_timestamp', 0))
        spent = sum(self._lovelace(x.get('value')) for x in own_inputs)
        received = sum(self._lovelace(x.get('value')) for x in own_outputs)
        withdrawn = sum(self._lovelace(x.get('amount')) for x in transaction.get('withdrawals') or []
                        if x.get('stake_addr') == self._stake_address)
        fee = self._lovelace(transaction.get('fee'))
        if spent == 0:
            if withdrawn or self._own_certificates(transaction):
                raise _HaltImport(self.tr("the wallet's stake key acted in a transaction it didn't fund"))
            self._incoming(transaction, received, timestamp, tx_hash)
            return
        if self._lovelace(transaction.get('deposit')) != 0:
            raise _HaltImport(self.tr("a deposit is paid or refunded - not supported yet"))
        if self._lovelace(transaction.get('treasury_donation')) != 0:
            raise _HaltImport(self.tr("a donation to the treasury"))
        sent = spent + withdrawn - received - fee
        if sent < 0:
            raise _HaltImport(self.tr("transaction funded by the wallet and by somebody else at once"))
        native = self._native_asset_id()
        fee_on_reward = withdrawn > 0 and sent == 0
        if withdrawn:
            self._add_payment(JSF.PAYMENT_STAKING_REWARD, timestamp, native, self._ada(withdrawn), tx_hash,
                              note=self.tr("Staking rewards withdrawn"),
                              fee=self._ada(fee) if fee_on_reward else Decimal('0'), fee_asset_id=native)
        if sent > 0:
            receivers = self._counterparties(transaction.get('outputs') or [])
            self._add_transfer(timestamp, native, self._ada(sent), False, tx_hash,
                               note=self._addresses_note(receivers), fee=self._ada(fee), fee_asset_id=native,
                               counterparty=receivers[0] if len(receivers) == 1 else '')
        elif not withdrawn:
            self._fee_only(transaction, self._ada(fee), timestamp, tx_hash)

    def _incoming(self, transaction: dict, received: int, timestamp: int, tx_hash: str) -> None:
        if received <= 0:
            self._skip(self.tr("transaction that moved nothing of the wallet's"), tx_hash)
            return
        senders = self._counterparties(transaction.get('inputs') or [])
        counterparty = senders[0] if len(senders) == 1 else ''
        note = self._addresses_note(senders)
        amount = self._ada(received)
        if self._is_native_dust(amount, self._is_own_address(counterparty)):
            self._add_payment(JSF.PAYMENT_DUST_ATTACK, timestamp, self._native_asset_id(), amount, tx_hash, note=note)
            return
        self._add_transfer(timestamp, self._native_asset_id(), amount, True, tx_hash,
                           note=note, counterparty=counterparty)

    # Nothing left the wallet but the fee: a move between its own addresses, or a certificate (a delegation)
    def _fee_only(self, transaction: dict, fee: Decimal, timestamp: int, tx_hash: str) -> None:
        if transaction.get('certificates') or transaction.get('voting_procedures'):
            note, event = self.tr("Fee of a staking or governance certificate"), JSF.EVENT_POSITION_COMMAND
        else:
            note, event = self.tr("Fee of a transfer between the wallet's own addresses"), JSF.EVENT_NO_OP
        self._add_payment(JSF.PAYMENT_GAS_FEE, timestamp, self._native_asset_id(), fee, tx_hash,
                          note=note, event=event)

    # Shapes the classification above can't account for
    def _check_shape(self, transaction: dict, own_entries: list) -> None:
        if any(x.get('asset_list') for x in own_entries):
            raise _HaltImport(self.tr("native tokens are not supported yet"))
        if transaction.get('collateral_inputs') or transaction.get('plutus_contracts') \
                or transaction.get('native_scripts'):
            raise _HaltImport(self.tr("a script transaction"))

    def _is_own(self, entry: dict) -> bool:
        return entry.get('stake_addr') == self._stake_address

    def _own_certificates(self, transaction: dict) -> list:
        return [x for x in transaction.get('certificates') or []
                if (x.get('info') or {}).get('stake_address') == self._stake_address]

    # The other ends of the transaction, in order and without repeats: a wallet by its stake address, else the address
    def _counterparties(self, entries: list) -> list:
        ends = []
        for entry in entries:
            if self._is_own(entry):
                continue
            end = entry.get('stake_addr') or (entry.get('payment_addr') or {}).get('bech32', '')
            if end and end not in ends:
                ends.append(end)
        return ends

    def _addresses_note(self, addresses: list) -> str:
        if len(addresses) < 2:
            return ''
        shown = ", ".join(addresses[:3])
        return self.tr("Several addresses: ") + (shown + ", ..." if len(addresses) > 3 else shown)

    # Koios reports every amount as a string of integer lovelace
    @staticmethod
    def _lovelace(value) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            raise Statement_ImportError(f"Unreadable Cardano amount: {value}")

    @staticmethod
    def _ada(lovelace: int) -> Decimal:
        return Decimal(lovelace) / _LOVELACE


SettingsRegistry.register(SettingDescriptor(
    key="DustThreshold_ADA",
    page=QT_TRANSLATE_NOOP("Preferences", "Blockchain"),
    label=QT_TRANSLATE_NOOP("Preferences", "ADA dust threshold"), default=CardanoFetcher.native_dust_threshold,
    tooltip=QT_TRANSLATE_NOOP("Preferences",
                              "An incoming ADA transfer below this amount, from an address you never dealt with, "
                              "is recorded as a dust attack instead of an ordinary transfer.")))
