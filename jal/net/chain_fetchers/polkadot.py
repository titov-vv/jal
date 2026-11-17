import hashlib
import json
import logging
from decimal import Decimal

import xxhash
from bip_utils import SS58Decoder, SS58Encoder

from jal.constants import AssetLocation
from jal.data_import.statement import Statement_ImportError, JSF
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
_SS58_PREFIX = 0
_POOL_PALLET_ID = b"py/nopls"
_POOL_BONDED_ACCOUNT, _POOL_REWARD_ACCOUNT = 0, 1       # pallet-nomination-pools AccountType
# Member calls of pallet-nomination-pools: {call: sign of the change it makes to the wallet's bond}
_POOL_CALLS = {'join': 1, 'bondExtra': 1, 'withdrawUnbonded': -1,
               'unbond': 0, 'claimPayout': 0, 'setClaimPermission': 0, 'poolWithdrawUnbonded': 0}
_STAKING_PROTOCOL = "Polkadot nomination pool"     # protocol named in a pool leg's custody mark; data, not translated


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
    native_dust_threshold = '0.01'      # the existential deposit: the least a new account can be sent

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
        checked = set()
        for extrinsic in [x for x in extrinsics if self._is_new(x)]:
            try:
                if extrinsic['height'] not in checked:
                    self._check_block(extrinsic['height'], [x for x in extrinsics if x['height'] == extrinsic['height']])
                    checked.add(extrinsic['height'])
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

    # ------------------------------------------------------------------------------------------------------------------
    # The indexer sees Balances.Transfer events and signed extrinsics only - an XCM arrival or a mint is not in it.
    # So the wallet's DOT (free + held) must change in the block by exactly what its elements there add up to.
    # The pool bond is read per block, so one block may hold one pool extrinsic only.
    def _check_block(self, height: int, extrinsics: list) -> None:
        if len([x for x in extrinsics if self._touches_pool(x)]) > 1:
            raise _HaltImport(self.tr("several nomination pool transactions in one block"))
        expected = sum(self._net(x) for x in extrinsics)
        actual = sum(self._balances(height)) - sum(self._balances(height - 1))
        if actual != expected:
            raise _HaltImport(self.tr("the wallet's balance changed by ") + f"{self._dot(actual).normalize():f}"
                              + self.tr(" DOT in the block, its history explains ") + f"{self._dot(expected).normalize():f}")

    # Plancks the extrinsic added to the wallet's DOT, free and held together
    def _net(self, extrinsic: dict) -> int:
        own = self._account.address()
        net = sum(self._planck(x['amount']) * ((x.get('to') == own) - (x.get('from') == own))
                  for x in self._transfers(extrinsic) if x.get('success') is True)
        return net - self._fee(extrinsic)

    # The wallet's fee: its own extrinsic's, or that of its failed transfer (which has no extrinsic element). A
    # transfer to the wallet carries the sender's fee, which is never the wallet's.
    def _fee(self, extrinsic: dict) -> int:
        own = self._account.address()
        signed = [x['extrinsic'] for x in extrinsic['elements'] if x.get('extrinsic')]
        if signed:
            return self._planck(signed[0].get('fee'))
        failed = [x for x in self._transfers(extrinsic) if x.get('success') is not True and x.get('from') == own]
        return self._planck(failed[0].get('fee')) if failed else 0

    # Native transfers of the extrinsic, each once: a transfer to the wallet itself has a '-from' and a '-to' element
    @staticmethod
    def _transfers(extrinsic: dict) -> list:
        unique = {}
        for element in extrinsic['elements']:
            transfer = element.get('transfer')
            if transfer:
                key = (transfer.get('eventIdx'), transfer.get('from'), transfer.get('to'), transfer.get('amount'))
                unique.setdefault(key, transfer)
        return list(unique.values())

    def _classify(self, extrinsic: dict) -> None:
        own = self._account.address()
        for kind, reason in (('assetTransfer', self.tr("a transfer of an Asset Hub token")),
                             ('swap', self.tr("a swap")), ('reward', self.tr("a staking reward"))):
            if any(x.get(kind) for x in extrinsic['elements']):
                raise _HaltImport(reason)
        signed = [x['extrinsic'] for x in extrinsic['elements'] if x.get('extrinsic')]
        transfers = self._transfers(extrinsic)
        if len(signed) > 1:
            raise _HaltImport(self.tr("several extrinsics under one index"))
        call = signed[0] if signed else None
        if call is not None and call.get('success') is not True:
            if transfers or self._pool_rewards(extrinsic):
                raise _HaltImport(self.tr("a failed extrinsic that moved coins"))
            self._fee_only(extrinsic, self._fee(extrinsic), JSF.EVENT_FAILED,
                           self.tr("Fee of a failed transaction: ") + f"{call.get('module')}.{call.get('call')}")
            return
        if self._touches_pool(extrinsic):
            self._pool_extrinsic(extrinsic, call)
            return
        if call is None:
            self._unsigned(extrinsic, transfers)
            return
        fee = self._fee(extrinsic)
        name = f"{call.get('module', '')}.{call.get('call', '')}"
        if call.get('module') != 'balances' or not str(call.get('call', '')).startswith('transfer'):
            raise _HaltImport(self.tr("unsupported call ") + name)
        if len(transfers) != 1 or transfers[0].get('success') is not True or transfers[0].get('from') != own:
            raise _HaltImport(self.tr("a transfer extrinsic that isn't one transfer from the wallet"))
        [transfer] = transfers
        if transfer.get('to') == own:
            self._fee_only(extrinsic, fee, JSF.EVENT_NO_OP, self.tr("Fee of a transfer to the wallet itself"))
            return
        native = self._native_asset_id()
        self._add_transfer(extrinsic['timestamp'], native, self._dot(self._planck(transfer['amount'])), False,
                           extrinsic['hash'], fee=self._dot(fee), fee_asset_id=native,
                           counterparty=transfer.get('to', ''))

    # ------------------------------------------------------------------------------------------------------------------
    # Nomination pool. The bond stays in the wallet's own account as a hold (delegated staking) but is booked into the
    # staking box at the pool's bonded account; its size is read from the node, as the indexer doesn't carry it.
    # A reward is paid as a transfer from the pool's reward account plus a PaidOut event: one StakingReward, whoever
    # signed the claim. Compounding is such a payout bonded right away (pallet-nomination-pools do_bond_extra).
    def _pool_extrinsic(self, extrinsic: dict, call) -> None:
        own = self._account.address()
        height = extrinsic['height']
        rewards = self._pool_rewards(extrinsic)
        if any(x.get('isReward') is not True for x in rewards):
            raise _HaltImport(self.tr("a nomination pool slash"))
        member = self._pool_member(height) or self._pool_member(height - 1)
        if member is None:
            raise _HaltImport(self.tr("a nomination pool transaction without a pool membership"))
        pool_id = member[0]
        if any(x.get('poolId') != pool_id for x in rewards):
            raise _HaltImport(self.tr("a reward of another nomination pool"))
        reward_account = self.pool_account(pool_id, _POOL_REWARD_ACCOUNT)
        transfers = self._transfers(extrinsic)
        paid = sum(self._planck(x.get('amount')) for x in rewards)
        if any(x.get('success') is not True or x.get('from') != reward_account or x.get('to') != own
               for x in transfers) or sum(self._planck(x.get('amount')) for x in transfers) != paid:
            raise _HaltImport(self.tr("transfers of a nomination pool transaction don't match its payouts"))
        bond = self._pool_bond(height) - self._pool_bond(height - 1)
        name = call.get('call', '') if call else ''
        if call is None:
            if bond:
                raise _HaltImport(self.tr("the pool bond changed in a transaction the wallet didn't sign"))
        elif call.get('module') != 'nominationPools':
            raise _HaltImport(self.tr("a nomination pool payout inside call ") + f"{call.get('module')}.{name}")
        elif name not in _POOL_CALLS:
            raise _HaltImport(self.tr("unsupported nomination pool call ") + name)
        elif (bond > 0) - (bond < 0) != _POOL_CALLS[name]:
            raise _HaltImport(self.tr("nomination pool call ") + name + self.tr(" changed the bond by ")
                              + f"{self._dot(bond).normalize():f}")
        native = self._native_asset_id()
        note = self.tr("Nomination pool #") + f"{pool_id}"
        for reward in rewards:
            self._add_payment(JSF.PAYMENT_STAKING_REWARD, extrinsic['timestamp'], native,
                              self._dot(self._planck(reward.get('amount'))), extrinsic['hash'],
                              note=note if call else self._joined_note(note, self.tr("claimed by another account")))
        fee = self._fee(extrinsic)
        if bond:
            direction = self.tr("Staked to ") if bond > 0 else self.tr("Withdrawn from ")
            self._add_transfer(extrinsic['timestamp'], native, self._dot(abs(bond)), bond < 0, extrinsic['hash'],
                               note=self._joined_note(self._custody_mark(_STAKING_PROTOCOL), direction + note),
                               fee=self._dot(fee), fee_asset_id=native,
                               counterparty=self.pool_account(pool_id, _POOL_BONDED_ACCOUNT))
        elif call:
            self._fee_only(extrinsic, fee, JSF.EVENT_POSITION_COMMAND, f"{note}: {name}")

    def _touches_pool(self, extrinsic: dict) -> bool:
        return bool(self._pool_rewards(extrinsic)) or any((x.get('extrinsic') or {}).get('module') == 'nominationPools'
                                                          for x in extrinsic['elements'])

    @staticmethod
    def _pool_rewards(extrinsic: dict) -> list:
        return [x['poolReward'] for x in extrinsic['elements'] if x.get('poolReward')]

    # SS58 address of a pool's bonded or reward account: PalletId 'py/nopls' sub-account (AccountType, pool id)
    @staticmethod
    def pool_account(pool_id: int, kind: int) -> str:
        seed = b"modl" + _POOL_PALLET_ID + bytes([kind]) + pool_id.to_bytes(4, 'little')
        return SS58Encoder.Encode(seed.ljust(32, b"\0"), _SS58_PREFIX)

    # ------------------------------------------------------------------------------------------------------------------
    # An extrinsic the wallet didn't sign: a transfer to it, or the wallet's own failed transfer
    def _unsigned(self, extrinsic: dict, transfers: list) -> None:
        own = self._account.address()
        failed = [x for x in transfers if x.get('success') is not True]
        if failed:
            if len(failed) != len(transfers) or any(x.get('from') != own for x in failed):
                raise _HaltImport(self.tr("a failed transfer the wallet didn't send"))
            self._fee_only(extrinsic, self._fee(extrinsic), JSF.EVENT_FAILED, self.tr("Fee of a failed transfer"))
            return
        if any(x.get('from') == own for x in transfers):
            raise _HaltImport(self.tr("the wallet sent coins in an extrinsic it didn't sign"))
        if len(transfers) != 1:
            raise _HaltImport(self.tr("several transfers to the wallet in one extrinsic"))
        [transfer] = transfers
        amount = self._dot(self._planck(transfer['amount']))
        sender = transfer.get('from', '')
        if self._is_native_dust(amount, self._is_own_address(sender)):
            self._add_payment(JSF.PAYMENT_DUST_ATTACK, extrinsic['timestamp'], self._native_asset_id(), amount,
                              extrinsic['hash'])
            return
        self._add_transfer(extrinsic['timestamp'], self._native_asset_id(), amount, True, extrinsic['hash'],
                           counterparty=sender)

    def _fee_only(self, extrinsic: dict, fee: int, event: str, note: str) -> None:
        self._add_payment(JSF.PAYMENT_GAS_FEE, extrinsic['timestamp'], self._native_asset_id(), self._dot(fee),
                          extrinsic['hash'], note=note, event=event)

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
