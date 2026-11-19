import json
import logging
import time
from decimal import Decimal

from PySide6.QtCore import QThread
from PySide6.QtWidgets import QApplication

from jal.constants import AssetLocation, AccountData
from jal.data_import.statement import Statement_ImportError, JSF
from jal.db.token_blacklist import is_near_account
from jal.net.chain_fetchers.fetcher import ChainFetcher
from jal.net.web_request import WebRequest

JAL_FETCHER_CLASS = "NearFetcher"

# NearBlocks API v3 (api.nearblocks.io/api-docs), keyless; v1/v2 are switched off on 22 Nov 2026
_API_ROOT = "https://api.nearblocks.io/v3/accounts"
RPC_URL = "https://rpc.mainnet.fastnear.com"     # keyless NEAR JSON-RPC
_PAGE_SIZE = 100            # the largest 'limit' v3 accepts
_MAX_PAGES = 100            # stops a runaway paging loop
_CALL_SPACING = 10.5        # seconds between NearBlocks calls; the free tier allows 6 a minute
_RATE_WAIT = 20             # seconds to wait after an HTTP 429 before the call is repeated
_RATE_RETRIES = 6
_TOO_MANY_REQUESTS = 429
# Blocks a transaction must be below the final block before import, so that its gas refunds have landed
_REFUND_WAIT = 10
# Blocks read below the cursor, so that a late refund of an imported transaction is recognized as such
_LOOKBACK = 100
_YOCTO_DIGITS = 24          # 1 NEAR = 10^24 yoctoNEAR
# The three lists a transaction is put together from: {endpoint: key of its rows in the transaction record}
_LISTS = {"txns": "txns", "receipts": "receipts", "staking-txns": "staking"}
_SYSTEM = 'system'          # predecessor of a gas refund, and of the deposit a failed call returns
_TRANSFER = 'TRANSFER'
_FUNCTION_CALL = 'FUNCTION_CALL'
_KEY_ACTIONS = ('ADD_KEY', 'DELETE_KEY')
_DELEGATE_ACTION = 'DELEGATE_ACTION'     # the wallet's actions in a meta-transaction signed by a relayer (NEP-366)
# Staking pools are recognized by name: the pool factories create them as sub-accounts
POOL_SUFFIXES = ('.poolv1.near', '.pool.near')
_DEPOSIT_METHODS = ('deposit_and_stake', 'deposit')
_COMMAND_METHODS = ('stake', 'stake_all', 'unstake', 'unstake_all')
_POOL_METHODS = _DEPOSIT_METHODS + _COMMAND_METHODS + ('withdraw', 'withdraw_all')
_EVENT_DEPOSIT, _EVENT_STAKE, _EVENT_UNSTAKE, _EVENT_WITHDRAW = 'DEPOSIT', 'STAKE', 'UNSTAKE', 'WITHDRAW'
_STAKING_PROTOCOL = "NEAR staking"     # protocol named in a pool leg's custody mark; data, so not translated


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
        self._stakes = None       # {pool: yocto staked there}, loaded by _fetch - see _pool_call

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
        request = WebRequest(WebRequest.POST_JSON, RPC_URL, params=body)
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
        self._stakes = self._load_stakes()
        final = self._final_height()
        transactions = self._transactions(self._lists(max(self._state['height'] - _LOOKBACK, 0)))
        listed = [x for x in transactions if self._is_new(x)]
        for transaction in listed:
            if transaction['height'] > final - _REFUND_WAIT:
                self._skip(self.tr("transaction is too recent, it will be imported next time"), transaction['hash'])
        for transaction in [x for x in listed if x['height'] <= final - _REFUND_WAIT]:
            stakes = dict(self._stakes)
            try:
                self._classify(transaction)
            except _HaltImport as halt:
                self._stakes = stakes
                self._skip(self.tr("import stopped at an unsupported transaction (") + halt.reason
                           + self.tr("); it will be retried next time"), transaction['hash'])
                break
            self._advance(transaction)
        return json.dumps(self._state)

    # The three lists down to 'floor'. Every transaction leaves a receipt to or from the wallet, so the other lists are
    # read only if a receipt is new, and the staking events only if a receipt involves a staking pool.
    def _lists(self, floor: int) -> dict:
        lists = {endpoint: [] for endpoint in _LISTS}
        lists['receipts'] = self._list('receipts', floor)
        if not any(self._is_new({'height': self._height(x), 'hash': x.get('transaction_hash')})
                   for x in lists['receipts']):
            return lists
        lists['txns'] = self._list('txns', floor)
        if any((x.get(side) or '').endswith(POOL_SUFFIXES) for x in lists['receipts']
               for side in ('predecessor_account_id', 'receiver_account_id')):
            lists['staking-txns'] = self._list('staking-txns', floor)
        return lists

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

    # ------------------------------------------------------------------------------------------------------------------
    # What the transaction did to the wallet. Its own transaction gives the deposit and the fee; 'system' refunds are
    # left out, as 'transaction_fee' is already the gas net of them.
    def _classify(self, transaction: dict) -> None:
        own = self._account.address()
        signed = [x for x in transaction['txns'] if x.get('signer_account_id') == own]
        if not signed:
            if self._delegated(transaction):
                self._relayed(transaction)
                return
            if transaction['staking'] or any(x.get('predecessor_account_id') == own for x in transaction['receipts']):
                raise _HaltImport(self.tr("the wallet acted in a transaction it didn't sign"))
            self._incoming(transaction)
            return
        if len(transaction['txns']) != 1:
            raise _HaltImport(self.tr("several transactions under one hash"))
        [txn] = signed
        fee = self._yocto((txn.get('outcomes_agg') or {}).get('transaction_fee'))
        if (txn.get('outcomes') or {}).get('status') is not True:
            if transaction['staking']:
                raise _HaltImport(self.tr("a failed transaction with staking events"))
            # The runtime returns a failed deposit in a refund receipt of its own, apart from the gas refunds
            refunds = [self._deposit(x) for x in transaction['receipts'] if x.get('predecessor_account_id') == _SYSTEM
                       and x.get('receiver_account_id') == own]
            if (self._deposit(txn) and self._deposit(txn) not in refunds) or self._arrived(transaction):
                raise _HaltImport(self.tr("a failed transaction that kept part of its deposit"))
            self._fee_only(transaction, fee, JSF.EVENT_FAILED, self.tr("Fee of a failed transaction"))
            return
        actions = [x.get('action') for x in txn.get('actions') or []]
        if len(actions) != 1:
            raise _HaltImport(self.tr("a transaction of several actions"))
        sent = [x for x in transaction['receipts'] if x.get('predecessor_account_id') == own]
        if any((x.get('outcome') or {}).get('status') is not True for x in sent):
            raise _HaltImport(self.tr("a receipt of the transaction failed"))
        deposit = self._deposit(txn)
        if sum(self._deposit(x) for x in sent) != deposit:
            raise _HaltImport(self.tr("the deposits of the transaction don't add up"))
        receiver = txn.get('receiver_account_id', '')
        method = ((txn.get('actions') or [{}])[0]).get('method') or ''
        if actions[0] == _FUNCTION_CALL and receiver.endswith(POOL_SUFFIXES) and method in _POOL_METHODS:
            self._pool_call(transaction, receiver, method, deposit, fee)
            return
        if transaction['staking']:
            raise _HaltImport(self.tr("staking events outside a call to a staking pool"))
        if self._arrived(transaction):
            raise _HaltImport(self.tr("coins came back to the wallet in its own transaction"))
        if actions[0] == _TRANSFER and deposit and receiver != own:
            native = self._native_asset_id()
            self._add_transfer(transaction['timestamp'], native, self._near(deposit), False, transaction['hash'],
                               fee=self._near(fee), fee_asset_id=native, counterparty=receiver)
        elif actions[0] == _TRANSFER:
            self._fee_only(transaction, fee, JSF.EVENT_NO_OP, self.tr("Fee of a transfer to the wallet itself"))
        elif actions[0] in _KEY_ACTIONS and not deposit:
            self._fee_only(transaction, fee, JSF.EVENT_AUTHORIZATION, self.tr("Fee of an access key change"))
        else:
            raise _HaltImport(self.tr("unsupported action ") + f"{actions[0]}")

    # ------------------------------------------------------------------------------------------------------------------
    # Native staking. The pool holds the wallet's coins while they earn, so a deposit and a withdrawal are transfers
    # with the pool as counterparty, which settles them into the staking box at the pool's address. The pool's
    # rewards compound inside it: the excess of a withdrawal over what was put in is the StakingReward, principal
    # first, measured against the amounts remembered per pool in AccountData.StakeAccounts.
    def _pool_call(self, transaction: dict, pool: str, method: str, deposit: int, fee: int) -> None:
        events = transaction['staking']
        if any(x.get('contract') != pool for x in events):
            raise _HaltImport(self.tr("a staking event of another pool"))
        kinds = sorted(x.get('type', '') for x in events)
        arrived = self._arrived(transaction)
        native = self._native_asset_id()
        if method in _DEPOSIT_METHODS:
            amounts = [self._yocto(x.get('amount')) for x in events if x.get('type') == _EVENT_DEPOSIT]
            if arrived or not deposit or amounts != [deposit] or not set(kinds) <= {_EVENT_DEPOSIT, _EVENT_STAKE}:
                raise _HaltImport(self.tr("a pool deposit that doesn't match its staking event"))
            self._stakes[pool] = self._stakes.get(pool, 0) + deposit
            self._add_transfer(transaction['timestamp'], native, self._near(deposit), False, transaction['hash'],
                               note=self._joined_note(self._custody_mark(_STAKING_PROTOCOL),
                                                      self.tr("Staked to ") + pool),
                               fee=self._near(fee), fee_asset_id=native, counterparty=pool)
        elif method in _COMMAND_METHODS:
            if arrived or deposit or not set(kinds) <= {_EVENT_STAKE, _EVENT_UNSTAKE}:
                raise _HaltImport(self.tr("a pool command that moved coins"))
            self._fee_only(transaction, fee, JSF.EVENT_POSITION_COMMAND, f"{pool}: {method}()")
        else:
            returned = sum(self._deposit(x) for x in arrived)
            amounts = [self._yocto(x.get('amount')) for x in events if x.get('type') == _EVENT_WITHDRAW]
            if deposit or not returned or amounts != [returned] or kinds != [_EVENT_WITHDRAW] \
                    or any(x.get('predecessor_account_id') != pool for x in arrived):
                raise _HaltImport(self.tr("a pool withdrawal that doesn't match its staking event"))
            self._pool_withdrawal(transaction, pool, returned, fee)

    def _pool_withdrawal(self, transaction: dict, pool: str, returned: int, fee: int) -> None:
        native = self._native_asset_id()
        staked = self._stakes.get(pool)
        if staked is None:
            # Nothing to measure a yield against: all of it is principal, never income invented out of a deposit
            principal, reward = returned, 0
            self._skip(self.tr("stake withdrawal whose deposit predates the sync cursor - yield not separated"),
                       transaction['hash'])
        else:
            principal = min(returned, staked)
            reward = returned - principal
            if staked > principal:
                self._stakes[pool] = staked - principal
            else:
                self._stakes.pop(pool)
        self._add_transfer(transaction['timestamp'], native, self._near(principal), True, transaction['hash'],
                           note=self._joined_note(self._custody_mark(_STAKING_PROTOCOL),
                                                  self.tr("Withdrawn from ") + pool),
                           fee=self._near(fee), fee_asset_id=native, counterparty=pool)
        if reward:
            self._add_payment(JSF.PAYMENT_STAKING_REWARD, transaction['timestamp'], native, self._near(reward),
                              transaction['hash'], note=self.tr("Staking reward"))

    # {pool: yocto still staked there}, kept between fetches as yocto strings; stored only once the data is imported
    def _load_stakes(self) -> dict:
        stored = self._account.get_data(AccountData.StakeAccounts) or ''
        if not stored:
            return {}
        try:
            return {pool: int(amount) for pool, amount in json.loads(stored).items()}
        except (json.JSONDecodeError, TypeError, ValueError, AttributeError):
            logging.warning(self.tr("Unreadable staking state of account ") + self._account.name())
            return {}

    def _commit_state(self) -> None:
        if self._stakes is None:      # nothing was fetched: the stored state is still valid
            return
        self._account.set_data(AccountData.StakeAccounts,
                               json.dumps({pool: str(amount) for pool, amount in self._stakes.items()}))

    # ------------------------------------------------------------------------------------------------------------------
    # A meta-transaction: a relayer signed and paid the gas of actions the wallet signed off-chain; the delegated
    # actions reach the wallet as a receipt from the relayer
    def _delegated(self, transaction: dict) -> bool:
        return any(x.get('receiver_account_id') == self._account.address()
                   and x.get('predecessor_account_id') not in (self._account.address(), _SYSTEM)
                   and ((x.get('actions') or [{}])[0]).get('action') == _DELEGATE_ACTION
                   for x in transaction['receipts'])

    # Only a relayed call that moved no NEAR is supported: it costs the wallet nothing, so nothing is recorded
    def _relayed(self, transaction: dict) -> None:
        own = self._account.address()
        if transaction['staking']:
            raise _HaltImport(self.tr("a relayed transaction with staking events"))
        if any(self._deposit(x) for x in transaction['receipts'] if own in (x.get('predecessor_account_id'),
                                                                             x.get('receiver_account_id'))):
            raise _HaltImport(self.tr("a relayed transaction that moved coins"))
        self._skip(self.tr("relayed contract call that moved no NEAR (its gas was paid by the relayer)"),
                   transaction['hash'])

    # ------------------------------------------------------------------------------------------------------------------
    # Coins sent to the wallet by somebody else's transaction
    def _incoming(self, transaction: dict) -> None:
        arrived = self._arrived(transaction)
        if len(arrived) != len([x for x in transaction['receipts'] if x.get('receiver_account_id')
                                == self._account.address()]):
            raise _HaltImport(self.tr("a refund or a failed receipt in a transaction the wallet didn't sign"))
        if any(x.get('action') != _TRANSFER for receipt in arrived for x in receipt.get('actions') or []):
            raise _HaltImport(self.tr("a contract call to the wallet"))
        amount = self._near(sum(self._deposit(x) for x in arrived))
        if not amount:
            self._skip(self.tr("transaction that moved nothing of the wallet's"), transaction['hash'])
            return
        senders = list(dict.fromkeys(x.get('predecessor_account_id', '') for x in arrived))
        counterparty = senders[0] if len(senders) == 1 else ''
        note = self.tr("Several senders: ") + ", ".join(senders) if len(senders) > 1 else ''
        if self._is_native_dust(amount, self._is_own_address(counterparty)):
            self._add_payment(JSF.PAYMENT_DUST_ATTACK, transaction['timestamp'], self._native_asset_id(), amount,
                              transaction['hash'], note=note)
            return
        self._add_transfer(transaction['timestamp'], self._native_asset_id(), amount, True, transaction['hash'],
                           note=note, counterparty=counterparty)

    def _fee_only(self, transaction: dict, fee: int, event: str, note: str) -> None:
        self._add_payment(JSF.PAYMENT_GAS_FEE, transaction['timestamp'], self._native_asset_id(), self._near(fee),
                          transaction['hash'], note=note, event=event)

    # Successful receipts that brought coins to the wallet from anyone but itself and 'system'
    def _arrived(self, transaction: dict) -> list:
        own = self._account.address()
        return [x for x in transaction['receipts'] if x.get('receiver_account_id') == own
                and x.get('predecessor_account_id') not in (own, _SYSTEM) and (x.get('outcome') or {}).get('status')
                is True]

    def _deposit(self, row: dict) -> int:
        return self._yocto((row.get('actions_agg') or {}).get('deposit'))

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
