import json
import logging
from decimal import Decimal

from jal.constants import AssetLocation, PredefinedAccountType
from jal.data_import.statement import Statement_ImportError, JSF
from jal.data_import.token_filter import TokenFilter, TokenCandidate
from jal.db.account import JalAccount
from jal.db.settings import JalSettings
from jal.db.symbol import JalSymbol
from jal.db.token_blacklist import normalize_address, is_evm_address
from jal.net.chain_fetchers.fetcher import ChainFetcher
from jal.net.web_request import WebRequest

# This module has no JAL_FETCHER_CLASS on purpose: it is the shared base of the EVM chains, not a selectable chain
# itself. Each concrete chain (Ethereum, Arbitrum, ...) is a thin subclass in its own module that only sets the
# Etherscan 'chainid' and the native coin - see ethereum.py / arbitrum.py.

# Etherscan moved to a single V2 endpoint that serves every chain it supports through one 'chainid' parameter and
# one API key. So every EVM chain shares this root and the same 'ApiKey_Etherscan' key.
_API_ROOT = "https://api.etherscan.io/v2/api"
_PAGE_SIZE = 10000                # Maximum 'offset' the API accepts
_MAX_PAGES = 20                   # Stops a runaway paging loop on an address with a very long history
_WEI = Decimal('10') ** 18        # 1 coin = 10^18 wei, the unit every native amount is returned in
_NO_TRANSACTIONS = "No transactions found"   # status=0 message that means "empty history", not an error

_METHOD_APPROVE = '0x095ea7b3'    # approve(address,uint256) selector, the one gas-only call worth naming apart


# ----------------------------------------------------------------------------------------------------------------------
# Fetches the transaction history of an EVM wallet from Etherscan and turns it into JSF.
#
# Three account endpoints are read and they do not overlap: 'txlist' returns the top-level transactions the wallet
# sent or received (native coin movements and the gas of everything it initiated), 'tokentx' returns ERC-20 token
# movements, and 'txlistinternal' returns the native coin that contracts moved on the wallet's behalf (a swap output,
# a withdrawal). They are tied together by transaction hash: the wallet pays the gas of a transaction only when it is
# the top-level sender, so gas is charged once per hash and attached to a single leg of that transaction - see
# _process_leftover_gas for the calls that moved nothing and only burned gas.
class EVMFetcher(ChainFetcher):
    chain_id = 0                  # Etherscan V2 'chainid' of this chain
    native_symbol = ''            # Ticker of the native coin, e.g. 'ETH'
    native_name = ''              # Human name of the native coin, e.g. 'Ethereum'
    icon_name = ''

    def __init__(self):
        super().__init__()
        self._filter = TokenFilter()
        self._new_cursor = ''
        self._gas = {}            # {tx_hash: Decimal} gas the wallet owes, emptied as it is attached to a leg
        self._gas_tx = {}         # {tx_hash: record} of the wallet's own transactions, kept for the gas note
        self._own_tx = set()      # hashes of the transactions the wallet itself sent, see _process_token

    # ------------------------------------------------------------------------------------------------------------------
    def _api_key(self) -> str:
        key = JalSettings().getStr("ApiKey_Etherscan").strip()
        if not key:
            raise Statement_ImportError(
                self.tr("Etherscan API key isn't set - fill it in Settings/Preferences/Blockchain"))
        return key

    # The wallet address, lower-cased the way every EVM address is stored and the way Etherscan returns 'from'/'to',
    # so a direct string comparison decides the direction of a transfer.
    def _address(self) -> str:
        return normalize_address(self.location_id, self._account.address())

    def _norm(self, address: str) -> str:
        return normalize_address(self.location_id, address)

    # Executes one paged GET against an Etherscan 'account' action and returns the 'result' list. Paging is by page
    # number (the API caps 'offset' at _PAGE_SIZE), and a short page means the history is exhausted.
    def _get_pages(self, action: str, start_block: int) -> list:
        records = []
        for page in range(1, _MAX_PAGES + 1):
            params = {"chainid": self.chain_id, "module": "account", "action": action,
                      "address": self._account.address(), "startblock": start_block, "endblock": 99999999,
                      "page": page, "offset": _PAGE_SIZE, "sort": "asc", "apikey": self._api_key()}
            request = WebRequest(WebRequest.GET, _API_ROOT, params=params)
            self._wait_for(request)
            try:
                answer = json.loads(request.data())
            except (json.JSONDecodeError, TypeError):
                raise Statement_ImportError(self.tr("Unexpected answer from Etherscan: ") + f"{request.data()}")
            result = answer.get('result', [])
            # status=0 is both "no transactions" (an ordinary empty history) and a real error (a bad key, a rate
            # limit); the two are told apart by the message, since only the error carries a string result.
            if str(answer.get('status', '0')) != '1':
                if answer.get('message', '') == _NO_TRANSACTIONS:
                    break
                raise Statement_ImportError(self.tr("Etherscan request failed: ") + f"{result or answer}")
            records += result
            if len(result) < _PAGE_SIZE:
                break
        else:
            logging.warning(self.tr("Too many pages returned by Etherscan, the history may be incomplete"))
        return records

    # The cursor is the block number of the last imported transaction; the next fetch starts at the following block.
    # A block is immutable once mined, so everything up to and including the cursor block was already seen in full.
    def _start_block(self) -> int:
        cursor = self._cursor()
        try:
            return int(cursor) + 1
        except (TypeError, ValueError):
            return 0

    # ------------------------------------------------------------------------------------------------------------------
    def _fetch(self) -> str:
        address = self._address()
        if not is_evm_address(address):
            raise Statement_ImportError(self.tr("Not a valid EVM address: ") + address)
        start_block = self._start_block()
        native = self._get_pages("txlist", start_block)
        tokens = self._get_pages("tokentx", start_block)
        internal = self._get_pages("txlistinternal", start_block)
        self._index_gas(native)
        latest = start_block - 1

        # Native transfers are processed first so an outgoing coin movement claims the transaction's gas before a
        # token leg of the same transaction can; whatever is left over on a wallet-initiated call becomes a GasFee.
        for record in native:
            latest = max(latest, self._block_of(record))
            self._process_native(record)
        for record in tokens:
            latest = max(latest, self._block_of(record))
            self._process_token(record)
        for record in internal:
            latest = max(latest, self._block_of(record))
            self._process_internal(record)
        self._process_leftover_gas()
        return str(latest) if latest > start_block - 1 else ''

    # Gas the wallet owes for each transaction it initiated, keyed by hash. Gas is gasUsed*gasPrice in wei and is
    # borne by the top-level sender only; a transaction the wallet merely received (an incoming transfer, an
    # airdrop) has the wallet neither as 'from' nor even present in txlist, so it never appears here.
    def _index_gas(self, native: list) -> None:
        self._gas = {}
        self._gas_tx = {}
        self._own_tx = set()
        address = self._address()
        for record in native:
            if self._norm(record.get('from', '')) != address:
                continue
            tx_hash = record.get('hash', '')
            self._own_tx.add(tx_hash)
            try:
                fee = Decimal(record.get('gasUsed', '0')) * Decimal(record.get('gasPrice', '0')) / _WEI
            except ArithmeticError:
                fee = Decimal('0')
            if fee > Decimal('0'):
                self._gas[tx_hash] = fee
                self._gas_tx[tx_hash] = record

    # Attaches this transaction's gas to the leg being created, but only once: the second leg of the same
    # transaction (a swap's token output next to its coin input) reads back zero, so gas is never counted twice.
    def _take_gas(self, tx_hash: str) -> Decimal:
        return self._gas.pop(tx_hash, Decimal('0'))

    # ------------------------------------------------------------------------------------------------------------------
    def _process_native(self, record: dict) -> None:
        tx_hash = record.get('hash', '')
        # A reverted transaction moved nothing but still cost gas; the value in the record never actually changed
        # hands, so no transfer is made and the gas is left for _process_leftover_gas to turn into a GasFee.
        if record.get('isError', '0') == '1':
            return
        try:
            amount = Decimal(record.get('value', '0')) / _WEI
        except ArithmeticError:
            self._skip(self.tr("native transfer with an unreadable amount"), tx_hash)
            return
        if amount <= Decimal('0'):   # a contract call that carried no coin - its token/internal legs cover it
            return
        incoming = self._norm(record.get('to', '')) == self._address()
        # Native coin transfers are NOT dust-filtered, unlike tokens. The token dust filter compares a fiat VALUE
        # to the threshold; the native coin can only be priced from stored quotes that a fresh wallet doesn't have
        # yet, and a raw amount-vs-threshold check (as on the Tron fetcher) is a unit mismatch that would drop a
        # legitimate sub-1-ETH transfer as "dust". Native poisoning is also far less harmful than token spam: it
        # creates no attacker-named asset, only a small, visibly-labelled ETH transfer the user can ignore. See
        # LONG_TERM_IMPROVEMENTS for a value-based native dust check once native pricing is available at fetch time.
        asset_id = self._native_asset_id()
        fee = self._take_gas(tx_hash) if not incoming else Decimal('0')
        self._add_transfer(self._timestamp_of(record), asset_id, amount, incoming, tx_hash,
                           note=self._counterparty_note(record),
                           fee=fee, fee_asset_id=asset_id if fee > Decimal('0') else None)

    def _process_token(self, record: dict) -> None:
        address = self._norm(record.get('contractAddress', ''))
        tx_hash = record.get('hash', '')
        if not is_evm_address(address):
            self._skip(self.tr("token with a malformed contract address"), tx_hash)
            return
        symbol = record.get('tokenSymbol', '')
        name = record.get('tokenName', '')
        incoming = self._norm(record.get('to', '')) == self._address()
        try:
            decimals = int(record.get('tokenDecimal', '0'))
            amount = Decimal(record.get('value', '0')) / (Decimal('10') ** decimals)
        except (ValueError, ArithmeticError):
            self._skip(self.tr("token transfer with an unreadable amount"), tx_hash)
            return
        if amount <= Decimal('0'):
            # A zero-value ERC-20 Transfer event carries no operation. Scam contracts emit them in bulk to poison a
            # wallet's history, and some legitimate contracts emit them too; either way there is nothing to import.
            self._skip(self.tr("zero-amount token transfer"), tx_hash)
            return
        # The spam policy runs before anything is created: a rejected token becomes no asset, no symbol and no
        # operation, so attacker-chosen names never reach the database (CRYPTO_PATH section 2.4). Both hints below
        # matter for a real token: without them an incoming transfer of an asset JAL can't price is dust by
        # definition, which would quarantine the very first USDT a wallet ever receives.
        #
        # Provenance is the decisive signal on an EVM chain: Etherscan lists every Transfer *event* that names the
        # wallet, and a scam contract can emit events that spoof the wallet as sender OR receiver without it ever
        # acting. Only a transaction the wallet itself sent (its hash is in _own_tx) is genuinely user-driven, so
        # such a movement is trusted (from_swap); any other event is unsolicited and must face the dust filter,
        # whichever direction it claims - otherwise a spoofed "outgoing" fake-USDT transfer would sail straight in,
        # because the shared filter never treats an outgoing transfer as dust.
        initiated = tx_hash in self._own_tx
        counterparty = record.get('from', '') if incoming else record.get('to', '')
        candidate = TokenCandidate(location_id=self.location_id, address=address, symbol=symbol, name=name,
                                   incoming=incoming or not initiated, from_swap=initiated, amount=amount,
                                   known_counterparty=self._is_own_address(counterparty),
                                   value=self._value_of(address, amount, self._timestamp_of(record)))
        if not self._filter.accept(candidate):
            self._skip(self.tr("token quarantined as dust/spam"), tx_hash)
            return
        asset_id = self._token_asset_id(symbol, name, address=address)
        # Gas is charged in the native coin, never in the token that moved, and only when the wallet sent the token
        fee = self._take_gas(tx_hash) if not incoming else Decimal('0')
        fee_asset_id = self._native_asset_id() if fee > Decimal('0') else None
        self._add_transfer(self._timestamp_of(record), asset_id, amount, incoming, tx_hash,
                           note=self._counterparty_note(record), fee=fee, fee_asset_id=fee_asset_id)

    # Native coin that a contract moved for the wallet: the output side of a swap, a withdrawal from a staking or
    # DeFi contract, a refund. Its gas belongs to the parent transaction and was accounted from txlist, so an
    # internal transfer never carries a fee of its own.
    def _process_internal(self, record: dict) -> None:
        tx_hash = record.get('hash', '')
        if record.get('isError', '0') == '1':
            return
        try:
            amount = Decimal(record.get('value', '0')) / _WEI
        except ArithmeticError:
            self._skip(self.tr("internal transfer with an unreadable amount"), tx_hash)
            return
        if amount <= Decimal('0'):
            return
        incoming = self._norm(record.get('to', '')) == self._address()   # native coin isn't dust-filtered, see above
        asset_id = self._native_asset_id()
        fee = self._take_gas(tx_hash) if not incoming else Decimal('0')
        self._add_transfer(self._timestamp_of(record), asset_id, amount, incoming, tx_hash,
                           note=self._counterparty_note(record),
                           fee=fee, fee_asset_id=asset_id if fee > Decimal('0') else None)

    # Every wallet-initiated transaction whose gas no transfer claimed: a token approval, a contract call that moved
    # nothing, or a transaction that reverted - the gas is charged in all three cases and would otherwise vanish.
    def _process_leftover_gas(self) -> None:
        for tx_hash, fee in self._gas.items():
            record = self._gas_tx.get(tx_hash, {})
            self._add_payment(JSF.PAYMENT_GAS_FEE, self._timestamp_of(record), self._native_asset_id(), fee,
                              tx_hash, note=self._gas_note(record))
        self._gas = {}

    # Describes what the gas was spent on: Etherscan reports a reverted transaction through 'isError', and the
    # method selector tells an approval from any other call (CRYPTO_PATH decision #32).
    def _gas_note(self, record: dict) -> str:
        if record.get('isError', '0') == '1':
            return self.tr("Gas: failed transaction")
        if record.get('methodId', '') == _METHOD_APPROVE:
            return self.tr("Gas: token approval")
        return self.tr("Gas: contract call")

    # ------------------------------------------------------------------------------------------------------------------
    # True if the address is one of the user's own wallets. A transfer between two wallets of the same person is
    # never an unsolicited airdrop, whatever the token is worth.
    def _is_own_address(self, address: str) -> bool:
        address = self._norm(address)
        if not address:
            return False
        return any(self._norm(x.address()) == address for x in self.wallets())

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

    # The native coin - which has no contract address behind it
    def _native_asset_id(self) -> int:
        return self._token_asset_id(self.native_symbol, self.native_name, address='')

    def _block_of(self, record: dict) -> int:
        try:
            return int(record.get('blockNumber', 0))
        except (TypeError, ValueError):
            return 0

    def _timestamp_of(self, record: dict) -> int:
        # Etherscan reports seconds of true UTC time; JAL stores seconds in its own local-wall-clock convention.
        try:
            seconds = int(record.get('timeStamp', 0))
        except (TypeError, ValueError):
            seconds = 0
        return self._local_timestamp(seconds)

    # The counterparty addresses are put in the note only when the other side is NOT an account JAL already knows:
    # a transfer between two of the user's own wallets needs no address note, while an outside address is worth
    # recording so the user can identify (or later name) the counterparty. Sender is shown first.
    def _counterparty_note(self, record: dict) -> str:
        sender, receiver = record.get('from', ''), record.get('to', '')
        counterparty = sender if self._norm(receiver) == self._address() else receiver
        if self._is_known_account(counterparty):
            return ''
        return f"{sender} → {receiver}"

    # True if the address belongs to any wallet account JAL holds (on any chain - an EVM address is shared across
    # EVM chains, and addresses of different chains never collide, so a cross-chain check is safe).
    def _is_known_account(self, address: str) -> bool:
        address = self._norm(address)
        if not address:
            return False
        for account in JalAccount.get_all_accounts(active_only=True):
            if account.account_type() == PredefinedAccountType.Wallet and \
                    normalize_address(account.chain(), account.address()) == address:
                return True
        return False
