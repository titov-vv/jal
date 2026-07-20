import json
import logging
from decimal import Decimal

from jal.constants import AssetLocation
from jal.data_import.statement import Statement_ImportError, JSF
from jal.data_import.token_filter import TokenFilter, TokenCandidate
from jal.db.settings import JalSettings
from jal.db.symbol import JalSymbol
from jal.db.token_blacklist import tron_address_from_hex, is_tron_address
from jal.net.chain_fetchers.fetcher import ChainFetcher
from jal.net.web_request import WebRequest

JAL_FETCHER_CLASS = "TronFetcher"

# TronGrid is the reference public API of the Tron network. A personal key is required: keyless access was measured
# at 2 requests before a sustained 429, while the free key allows 15 requests per second (CRYPTO_PATH decision #37).
_API_ROOT = "https://api.trongrid.io"
_PAGE_SIZE = 200                  # Maximum the API accepts
_MAX_PAGES = 100                  # Stops a runaway paging loop on an address with a very long history
_SUN = Decimal('1000000')         # 1 TRX = 10^6 sun, the unit every native amount is returned in

# Selectors of the TRC-20 contract methods that matter. A call whose selector is 'transfer' has a matching record in
# the token endpoint and is only read here for the fee; anything else moves no tokens and merely burns gas.
_METHOD_TRANSFER = 'a9059cbb'         # transfer(address,uint256)
_METHOD_TRANSFER_FROM = '23b872dd'    # transferFrom(address,address,uint256)
_METHOD_APPROVE = '095ea7b3'          # approve(address,uint256)


# ----------------------------------------------------------------------------------------------------------------------
# Fetches the transaction history of a Tron wallet from TronGrid and turns it into JSF.
#
# Two endpoints are needed and they do not overlap: '/transactions/trc20' returns token movements, '/transactions'
# returns native TRX transactions. A TRC-20 transfer appears in BOTH - as a token record and as the
# TriggerSmartContract that carried it - so the two are joined by transaction hash: the token record supplies the
# amounts, the native one supplies the gas that was burned.
class TronFetcher(ChainFetcher):
    location_id = AssetLocation.TRX_BLOCKCHAIN
    icon_name = ''

    def __init__(self):
        super().__init__()
        self.name = self.tr("Tron")
        self._filter = TokenFilter()
        self._new_cursor = ''

    # ------------------------------------------------------------------------------------------------------------------
    def _api_key(self) -> str:
        key = JalSettings().getStr("ApiKey_TronGrid").strip()
        if not key:
            raise Statement_ImportError(
                self.tr("TronGrid API key isn't set - fill it in Settings/Preferences/Blockchain"))
        return key

    # Executes one paged GET against TronGrid and returns the 'data' list. Paging follows the documented
    # fingerprint cursor rather than an offset, which the API caps.
    def _get_pages(self, endpoint: str, params: dict) -> list:
        headers = {"TRON-PRO-API-KEY": self._api_key()}
        records = []
        fingerprint = ''
        for _ in range(_MAX_PAGES):
            query = dict(params, limit=_PAGE_SIZE)
            if fingerprint:
                query['fingerprint'] = fingerprint
            request = WebRequest(WebRequest.GET, f"{_API_ROOT}{endpoint}", params=query, headers=headers)
            self._wait_for(request)
            try:
                answer = json.loads(request.data())
            except (json.JSONDecodeError, TypeError):
                raise Statement_ImportError(self.tr("Unexpected answer from TronGrid: ") + f"{request.data()}")
            if not answer.get('success', False):
                raise Statement_ImportError(self.tr("TronGrid request failed: ") + f"{answer.get('error', answer)}")
            records += answer.get('data', [])
            fingerprint = answer.get('meta', {}).get('fingerprint', '')
            if not fingerprint:
                break
        else:
            logging.warning(self.tr("Too many pages returned by TronGrid, the history may be incomplete"))
        return records

    # The cursor is the block timestamp of the last imported transaction, in milliseconds as the API reports it.
    # It is used as an exclusive lower bound: 'min_timestamp' is inclusive, so 1 ms is added to avoid re-importing
    # the transaction the previous run ended on.
    def _min_timestamp(self) -> int:
        cursor = self._cursor()
        try:
            return int(cursor) + 1
        except (TypeError, ValueError):
            return 0

    # ------------------------------------------------------------------------------------------------------------------
    def _fetch(self) -> str:
        address = self._account.address()
        if not is_tron_address(address):
            raise Statement_ImportError(self.tr("Not a valid Tron address: ") + address)
        params = {'order_by': 'block_timestamp,asc', 'min_timestamp': self._min_timestamp()}
        tokens = self._get_pages(f"/v1/accounts/{address}/transactions/trc20", params)
        native = self._get_pages(f"/v1/accounts/{address}/transactions", params)
        gas = self._gas_by_hash(native)
        latest = self._min_timestamp() - 1

        for record in tokens:
            latest = max(latest, int(record.get('block_timestamp', 0)))
            self._process_token_transfer(record, gas)
        for record in native:
            latest = max(latest, int(record.get('block_timestamp', 0)))
            self._process_native_transaction(record, address)
        return str(latest) if latest > 0 else ''

    # Gas burned by each native transaction, keyed by hash. Tron charges bandwidth and energy, both settled in TRX;
    # 'fee' in the result record is their total and is 0 when the account's free allowance covered the transaction.
    @staticmethod
    def _gas_by_hash(native: list) -> dict:
        gas = {}
        for record in native:
            results = record.get('ret', [])
            fee = results[0].get('fee', 0) if results else 0
            gas[record.get('txID', '')] = Decimal(str(fee)) / _SUN
        return gas

    @staticmethod
    def _contract_of(record: dict) -> dict:
        contracts = record.get('raw_data', {}).get('contract', [])
        return contracts[0] if contracts else {}

    # ------------------------------------------------------------------------------------------------------------------
    def _process_token_transfer(self, record: dict, gas: dict) -> None:
        info = record.get('token_info', {})
        address = info.get('address', '')
        tx_hash = record.get('transaction_id', '')
        if not is_tron_address(address):
            self._skip(self.tr("token with a malformed contract address"), tx_hash)
            return
        incoming = record.get('to', '') == self._account.address()
        try:
            decimals = int(info.get('decimals', 0))
            amount = Decimal(record.get('value', '0')) / (Decimal('10') ** decimals)
        except (ValueError, ArithmeticError):
            self._skip(self.tr("token transfer with an unreadable amount"), tx_hash)
            return
        # The spam policy runs before anything is created: a rejected token becomes no asset, no symbol and no
        # operation, so attacker-chosen names never reach the database (CRYPTO_PATH section 2.4).
        # Both hints below matter for a real token: without them an incoming transfer of an asset JAL can't price
        # is dust by definition, which would quarantine the very first USDT a wallet ever receives.
        counterparty = record.get('from', '') if incoming else record.get('to', '')
        candidate = TokenCandidate(location_id=self.location_id, address=address, symbol=info.get('symbol', ''),
                                   name=info.get('name', ''), incoming=incoming, amount=amount,
                                   known_counterparty=self._is_own_address(counterparty),
                                   value=self._value_of(address, amount, self._timestamp_of(record)))
        if not self._filter.accept(candidate):
            self._skip(self.tr("token quarantined as dust/spam"), tx_hash)
            return
        asset_id = self._token_asset_id(info.get('symbol', ''), info.get('name', ''), address=address)
        # Gas is charged in TRX, never in the token that moved, and only the sender pays it
        fee = gas.get(tx_hash, Decimal('0')) if not incoming else Decimal('0')
        fee_asset_id = self._native_asset_id() if fee > Decimal('0') else None
        self._add_transfer(self._timestamp_of(record), asset_id, amount, incoming, tx_hash,
                           note=self._counterparty_note(record, incoming), fee=fee, fee_asset_id=fee_asset_id)

    def _process_native_transaction(self, record: dict, address: str) -> None:
        contract = self._contract_of(record)
        tx_type = contract.get('type', '')
        tx_hash = record.get('txID', '')
        if tx_type == 'TransferContract':
            self._process_native_transfer(record, contract, address)
            return
        if tx_type == 'TriggerSmartContract':
            # A contract call either carried a token transfer - already imported from the token endpoint, where the
            # amounts are - or moved nothing and only burned gas, which needs the GasFee operation that doesn't
            # exist yet. Either way there is nothing to add here.
            data = contract.get('parameter', {}).get('value', {}).get('data', '')
            if data[:8] in (_METHOD_TRANSFER, _METHOD_TRANSFER_FROM):
                return
            self._process_gas_only_call(record, data)
            return
        if tx_type == 'WithdrawBalanceContract':
            self._process_staking_reward(record)
            return
        if tx_type in ('FreezeBalanceV2Contract', 'UnfreezeBalanceV2Contract',
                       'WithdrawExpireUnfreezeContract', 'VoteWitnessContract'):
            # Freezing, unfreezing and voting move nothing out of the wallet - the TRX stays owned throughout,
            # it only stops being transferable - so there is no operation to record.
            self._skip(self.tr("staking lifecycle, no change of ownership"), tx_hash)
            return
        self._skip(self.tr("unsupported transaction type: ") + tx_type, tx_hash)

    def _process_native_transfer(self, record: dict, contract: dict, address: str) -> None:
        value = contract.get('parameter', {}).get('value', {})
        tx_hash = record.get('txID', '')
        try:
            amount = Decimal(str(value.get('amount', 0))) / _SUN
        except ArithmeticError:
            self._skip(self.tr("native transfer with an unreadable amount"), tx_hash)
            return
        owner = tron_address_from_hex(value.get('owner_address', ''))
        incoming = owner != address
        # Address-poisoning dust: a few sun sent from an address that mimics one the user really deals with, so
        # that a later copy-paste from the history sends funds to the attacker. The same threshold that guards
        # tokens guards the native coin, since the attack and the remedy are identical.
        if incoming and amount < self._filter.dust_threshold():
            self._skip(self.tr("native dust transfer below the threshold"), tx_hash)
            return
        fee = Decimal(str(record.get('ret', [{}])[0].get('fee', 0))) / _SUN if not incoming else Decimal('0')
        asset_id = self._native_asset_id()
        self._add_transfer(self._timestamp_of(record), asset_id, amount, incoming, tx_hash,
                           note=self._native_counterparty_note(value, incoming),
                           fee=fee, fee_asset_id=asset_id if fee > Decimal('0') else None)

    # A call that transferred nothing and only burned gas: a token approval, a contract call, or a transaction
    # that ran out of energy and failed - the fee is charged either way. A call that cost nothing (the account's
    # free bandwidth covered it) leaves no trace worth recording.
    def _process_gas_only_call(self, record: dict, data: str) -> None:
        tx_hash = record.get('txID', '')
        fee = Decimal(str(record.get('ret', [{}])[0].get('fee', 0))) / _SUN
        if fee <= Decimal('0'):
            self._skip(self.tr("contract call that cost no gas"), tx_hash)
            return
        self._add_payment(JSF.PAYMENT_GAS_FEE, self._timestamp_of(record), self._native_asset_id(), fee,
                          tx_hash, note=self._gas_note(record, data))

    # Describes what the gas was spent on. Tron reports a failed transaction through 'contractRet', and the
    # method selector tells an approval from any other call - the distinction decision #32 asks to keep.
    def _gas_note(self, record: dict, data: str) -> str:
        result = record.get('ret', [{}])[0].get('contractRet', '')
        if result and result != 'SUCCESS':
            return self.tr("Gas: failed transaction") + f" ({result})"
        if data[:8] == _METHOD_APPROVE:
            return self.tr("Gas: token approval")
        return self.tr("Gas: contract call")

    # Staking rewards accumulate on-chain and are credited to the wallet when they are claimed. The claimed amount
    # isn't in the contract parameters - it is the 'withdraw_amount' the node reports for the transaction.
    def _process_staking_reward(self, record: dict) -> None:
        tx_hash = record.get('txID', '')
        try:
            amount = Decimal(str(record.get('withdraw_amount', 0))) / _SUN
        except ArithmeticError:
            self._skip(self.tr("staking reward with an unreadable amount"), tx_hash)
            return
        if amount <= Decimal('0'):
            self._skip(self.tr("staking reward claim of zero"), tx_hash)
            return
        self._add_payment(JSF.PAYMENT_STAKING_REWARD, self._timestamp_of(record), self._native_asset_id(), amount,
                          tx_hash, note=self.tr("Staking reward"))

    # ------------------------------------------------------------------------------------------------------------------
    # True if the address is one of the user's own wallets. A transfer between two wallets of the same person is
    # never an unsolicited airdrop, whatever the token is worth.
    def _is_own_address(self, address: str) -> bool:
        if not address:
            return False
        return any(x.address() == address for x in self.wallets())

    # Value of the transfer in the account currency, or None when the token can't be priced. A token JAL already
    # holds is priced from its stored quotes; a token seen for the first time has none, and None is what tells the
    # filter it can't judge the transfer by value (it then relies on the allow-list and the counterparty instead).
    def _value_of(self, address: str, amount: Decimal, timestamp: int):
        id_type = AssetLocation.address_id_of(self.location_id)
        symbol = JalSymbol.find_by_identifier(id_type, address)
        if not symbol.id():
            return None
        rate = symbol.asset().quote(timestamp, self._account.currency())[1]
        return amount * rate if rate else None

    # TRX itself - the native coin, which has no contract address behind it
    def _native_asset_id(self) -> int:
        return self._token_asset_id('TRX', "Tron", address='')

    @staticmethod
    def _timestamp_of(record: dict) -> int:
        return int(record.get('block_timestamp', 0)) // 1000    # The API reports milliseconds, JAL stores seconds

    def _counterparty_note(self, record: dict, incoming: bool) -> str:
        counterparty = record.get('from', '') if incoming else record.get('to', '')
        return (self.tr("From ") if incoming else self.tr("To ")) + counterparty

    def _native_counterparty_note(self, value: dict, incoming: bool) -> str:
        raw = value.get('owner_address', '') if incoming else value.get('to_address', '')
        return (self.tr("From ") if incoming else self.tr("To ")) + tron_address_from_hex(raw)
