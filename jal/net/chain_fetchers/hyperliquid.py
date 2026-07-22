import json
import logging
from hashlib import sha1
from decimal import Decimal, DecimalException

from jal.constants import AssetLocation, AccountData
from jal.data_import.statement import Statement_ImportError, JSF
from jal.data_import.token_filter import TokenCandidate
from jal.db.token_blacklist import is_evm_address
from jal.net.chain_fetchers.fetcher import ChainFetcher
from jal.net.web_request import WebRequest

JAL_FETCHER_CLASS = "HyperliquidFetcher"

# The keyless 'info' endpoint of HyperCore. Every call is a POST with a JSON body naming the request 'type'.
_API_URL = "https://api.hyperliquid.xyz/info"
_PAGE_LIMIT = 2000                 # Maximum number of records one 'ByTime' call returns
_MAX_PAGES = 100                   # Stops a runaway paging loop on an account with a very long history

# Ledger record kinds ('delta.type') that this fetcher understands. Anything else halts the import rather than
# being guessed at - see _classify_ledger.
_DEPOSIT = 'deposit'                        # USDC arriving over the Arbitrum bridge
_WITHDRAW = 'withdraw'                      # USDC leaving over the Arbitrum bridge
_SPOT_TRANSFER = 'spotTransfer'             # any spot token sent to or received from another HyperCore address
_INTERNAL_TRANSFER = 'internalTransfer'     # the same, restricted to the USDC perp balance
_SEND = 'send'                              # a token moved between two order books of the same account
_STAKING_TRANSFER = 'cStakingTransfer'      # HYPE moved between the spot balance and the staking balance
_REWARDS_CLAIM = 'rewardsClaim'             # staking/referral rewards credited to the account
_CLASS_TRANSFER = 'accountClassTransfer'    # USDC moved between the spot and the perp balance of the same account


# Raised for a record whose shape this fetcher does not (yet) support. It stops the import at that record instead
# of guessing - see _fetch for the halt-and-checkpoint that keeps every earlier record and re-tries this one on the
# next fetch. Mirrors solana.py's and evm.py's _HaltImport.
class _HaltImport(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


# ----------------------------------------------------------------------------------------------------------------------
# Fetches the history of a Hyperliquid account from the HyperCore 'info' API and turns it into JSF.
#
# Hyperliquid is treated as an ordinary blockchain wallet (CRYPTO_PATH decision #66): HyperCore is its own L1, an
# account is addressed by a normal 20-byte key, and ChainFetcher asks for nothing more than a Statement filled over
# HTTP and found by an account attribute. What made this the right model rather than an exchange account is that a
# Trade settles in the *account currency* and an account currency must be a Money asset - so an "HL account
# denominated in USDC" would make USDC money globally, and since a transfer carries one symbol for the whole
# operation, the account's commonest movement (USDC arriving from an Arbitrum wallet that holds it as a crypto
# asset) could not be expressed at all. Spot fills are therefore Swaps, not Trades, which also keeps them out of
# the tax reports until the crypto tax track is designed (#26).
#
# Two things differ from a real chain and simplify this fetcher:
#  - there is no gas. A spot fill pays a fee in a token that varies (and is not necessarily one of the two being
#    swapped), and nothing else costs anything, so none of the native-coin machinery of ChainFetcher is used. HYPE
#    is an ordinary spot token here, with a token id like any other - it is not an address-less native coin.
#  - every amount is reported as a decimal string in human units, so no wei/decimals conversion is needed anywhere.
#
# One thing is HARDER than on a real chain and worth stating plainly: a venue lists junk. 'spotMeta' - the venue's
# registry - names every token that has ever been listed, worthless airdrops included, so it identifies a token but
# does NOT vouch for it. The real account received a listed token worth $0 blasted at it by a stranger, so the spam
# filter judges an incoming token by the USD value the venue itself reports for the transfer, not by registry
# membership. See CRYPTO_PATH decision #67.
#
# The account handled here is spot-only. Perpetuals would need an operation JAL doesn't have (positions, funding,
# margin), so every record that belongs to them halts the import instead of being approximated.
class HyperliquidFetcher(ChainFetcher):
    location_id = AssetLocation.HL_BLOCKCHAIN
    # HyperCore has no address-less native coin: HYPE is a spot token identified by a token id like every other,
    # and nothing on this chain is paid in a coin that has no identity. Leaving these empty keeps the native-coin
    # helpers of the base class (which would create a second, address-less HYPE asset) out of reach.
    native_symbol = ''
    native_name = ''
    icon_name = ''

    def __init__(self):
        super().__init__()
        self.name = self.tr("Hyperliquid")
        self._new_cursor = ''
        self._tokens = []        # spotMeta 'tokens', indexed by their own 'index' field
        self._markets = {}       # spot pair name ('@107', 'PURR/USDC') -> (base token, quote token)
        self._staked = None      # {token name: amount staked}, loaded by _fetch - see _process_staking

    # ------------------------------------------------------------------------------------------------------------------
    # One 'info' request. The endpoint is keyless but POST-only, so it never fits the GET-shaped helpers.
    def _post(self, request: dict):
        web_request = WebRequest(WebRequest.POST_JSON, _API_URL, params=request)
        self._wait_for(web_request)
        try:
            answer = json.loads(web_request.data())
        except (json.JSONDecodeError, TypeError):
            raise Statement_ImportError(self.tr("Unexpected answer from Hyperliquid: ") + f"{web_request.data()}")
        if isinstance(answer, dict) and ('error' in answer or 'message' in answer):
            raise Statement_ImportError(self.tr("Hyperliquid request failed: ")
                                        + f"{answer.get('error', answer.get('message'))}")
        return answer

    # Reads a '...ByTime' history in full. Both endpoints cap an answer at _PAGE_LIMIT records and accept an
    # inclusive 'startTime' in milliseconds, so a full page is continued from the time of its last record - and
    # records already returned are dropped by key, because several of them may share the very millisecond the next
    # page has to start from.
    def _history(self, request_type: str, start_ms: int) -> list:
        records = []
        seen = set()
        start = start_ms
        for _ in range(_MAX_PAGES):
            answer = self._post({"type": request_type, "user": self._account.address(), "startTime": start})
            if not isinstance(answer, list):
                raise Statement_ImportError(self.tr("Unexpected answer from Hyperliquid: ") + f"{answer}")
            fresh = [x for x in answer if self._record_key(x) not in seen]
            seen.update(self._record_key(x) for x in fresh)
            records += fresh
            if len(answer) < _PAGE_LIMIT or not fresh:
                break
            start = max(int(x['time']) for x in answer)
        else:
            logging.warning(self.tr("Too many pages returned by Hyperliquid, the history may be incomplete"))
        return records

    # A record's identity, stable across fetches. A fill has a trade id of its own; a ledger record is identified by
    # the transaction it belongs to plus the content of its delta, since one transaction may carry several.
    @staticmethod
    def _record_key(record: dict) -> str:
        if 'tid' in record:
            return f"f{record['tid']}"
        digest = sha1(json.dumps(record.get('delta', {}), sort_keys=True).encode()).hexdigest()[:12]
        return f"l{record.get('hash', '')}:{digest}"

    # ------------------------------------------------------------------------------------------------------------------
    # The cursor is the millisecond of the last imported record together with the keys of the records that share it:
    # 'startTime' is inclusive and an exchange happily produces several fills within one millisecond, so a cursor of
    # "the last millisecond + 1" would silently drop the rest of a group. Reading from that millisecond and skipping
    # what was already imported is exact instead of nearly right.
    def _load_cursor(self) -> tuple:
        stored = self._cursor()
        if not stored:
            return 0, set()
        try:
            data = json.loads(stored)
            return int(data['ts']), set(data.get('seen', []))
        except (json.JSONDecodeError, TypeError, ValueError, KeyError):
            logging.warning(self.tr("Unreadable sync cursor of account ") + self._account.name())
            return 0, set()

    @staticmethod
    def _make_cursor(timestamp_ms: int, keys: set) -> str:
        return json.dumps({"ts": timestamp_ms, "seen": sorted(keys)})

    # ------------------------------------------------------------------------------------------------------------------
    def _fetch(self) -> str:
        address = self._account.address()
        if not is_evm_address(address):
            raise Statement_ImportError(self.tr("Not a valid Hyperliquid address: ") + address)
        self._load_spot_meta()
        self._staked = self._load_staked()
        start_ms, imported = self._load_cursor()

        records = self._collect(start_ms, imported)
        # Records are imported in the order they happened. When one of them has a shape this fetcher can't support
        # it raises _HaltImport: that record is rolled back, the import stops there keeping every earlier one, and
        # the cursor is parked on the last record that did import. The next fetch resumes from it and re-tries the
        # halting record on its own, so nothing needs a manual replay once the shape is learned.
        last_ms, last_keys = start_ms, set(imported)
        for record in records:
            checkpoint = self._checkpoint()
            staked = dict(self._staked)
            try:
                self._classify(record)
            except _HaltImport as halt:
                self._restore(checkpoint)
                self._staked = staked
                self._skip(self.tr("import stopped at an unsupported record (") + halt.reason
                           + self.tr("); it will be retried next time"), record['hash'])
                return self._make_cursor(last_ms, last_keys)
            if record['time'] != last_ms:
                last_ms, last_keys = record['time'], set()
            last_keys.add(record['key'])
        return self._make_cursor(last_ms, last_keys)

    # Both histories of the account, merged into one chronological stream of normalized records. They are separate
    # endpoints describing the same account, so a fill and a ledger movement of the same moment must be ordered
    # against each other; ties are broken deterministically by key so that a re-fetch produces the same order.
    def _collect(self, start_ms: int, imported: set) -> list:
        records = []
        for fill in self._history("userFillsByTime", start_ms):
            records.append({'kind': 'fill', 'time': int(fill['time']), 'hash': fill.get('hash', ''),
                            'key': self._record_key(fill), 'data': fill})
        for entry in self._history("userNonFundingLedgerUpdates", start_ms):
            records.append({'kind': 'ledger', 'time': int(entry['time']), 'hash': entry.get('hash', ''),
                            'key': self._record_key(entry), 'data': entry})
        records = [x for x in records if x['time'] > start_ms or x['key'] not in imported]
        return sorted(records, key=lambda x: (x['time'], x['kind'], x['key']))

    # Snapshot of how many operations (and assets) each JSF section holds, used to roll a partial record back
    def _checkpoint(self) -> dict:
        return {section: len(self._data.get(section, [])) for section in
                (JSF.ASSETS, JSF.TRANSFERS, JSF.ASSET_PAYMENTS, JSF.SWAPS, JSF.BRIDGES, JSF.CONVERSIONS)}

    def _restore(self, checkpoint: dict) -> None:
        for section, length in checkpoint.items():
            if section in self._data:
                del self._data[section][length:]

    def _classify(self, record: dict) -> None:
        timestamp = self._local_timestamp(record['time'] // 1000)
        if record['kind'] == 'fill':
            self._process_fill(record['data'], timestamp, record['hash'])
        else:
            self._classify_ledger(record['data'], timestamp, record['hash'])

    # ------------------------------------------------------------------------------------------------------------------
    # The spot registry of the venue: every token that exists on HyperCore and every market they are paired in.
    # It is fetched once per run because it is what resolves a fill: a fill names its market by an index alias
    # ('@107'), not by a ticker, and a token by a name that only this table maps onto an identity.
    def _load_spot_meta(self) -> None:
        meta = self._post({"type": "spotMeta"})
        try:
            self._tokens = {int(token['index']): token for token in meta['tokens']}
            self._markets = {market['name']: (self._tokens[market['tokens'][0]], self._tokens[market['tokens'][1]])
                             for market in meta['universe']}
        except (TypeError, KeyError, ValueError, IndexError):
            raise Statement_ImportError(self.tr("Unexpected spot token list received from Hyperliquid"))

    # The token behind a reference as the ledger records spell it: either a bare ticker ('USDC') or the unambiguous
    # 'TICKER:tokenid' form the API uses when a ticker isn't unique. A reference that resolves to nothing halts the
    # import - booking a movement against the wrong token would silently corrupt a position.
    def _token_of(self, reference: str) -> dict:
        if ':' in reference:
            _, token_id = reference.split(':', 1)
            for token in self._tokens.values():
                if token.get('tokenId', '').lower() == token_id.lower():
                    return token
            raise _HaltImport(self.tr("unknown token: ") + reference)
        matches = [x for x in self._tokens.values() if x.get('name') == reference]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise _HaltImport(self.tr("unknown token: ") + reference)
        raise _HaltImport(self.tr("ambiguous token ticker: ") + reference)

    # JSF asset id of a Hyperliquid token, keyed by its HyperCore token id. The HyperEVM contract address of the
    # same token is attached as a second identifier where it exists: it is not the token's identity (it is optional
    # and belongs to another chain) but it is what the quote source indexes most Hyperliquid tokens by.
    def _token_asset(self, token: dict) -> int:
        asset_id = self._token_asset_id(token['name'], token.get('fullName') or token['name'],
                                        address=token['tokenId'])
        evm_address = (token.get('evmContract') or {}).get('address', '')
        if evm_address:
            for asset in self._data[JSF.ASSETS]:
                if asset['id'] == asset_id:
                    asset[JSF.SYMBOLS][0]['evm_address'] = evm_address
        return asset_id

    # Applies the spam policy to a token and returns True if it may be imported, quarantining it otherwise.
    #
    # A venue is not the trusted place a chain-agnostic reading would take it for: 'spotMeta' lists every token that
    # has ever been listed, junk included, so being on it says nothing about whether a token is wanted. The real
    # account proves it - it received 101627 units of a listed token 'MAX' worth exactly $0, a textbook
    # address-poisoning airdrop. So membership of the registry is NOT trust (it is only identity), and the filter is
    # driven by the value the venue itself reports for the transfer: an incoming token worth less than the dust
    # threshold, from a stranger, is quarantined exactly as on any chain. 'usd_value' is that figure, in USD (the
    # currency the venue and every crypto quote in JAL are denominated in); a fill's acquired token needs none
    # because a swap the user made is never dust (from_swap). A manual blacklist is still honoured. See CRYPTO_PATH
    # decision #67.
    def _accept_token(self, token: dict, amount: Decimal, incoming: bool, from_swap: bool, usd_value=None) -> bool:
        candidate = TokenCandidate(location_id=self.location_id, address=token['tokenId'],
                                   symbol=token.get('name', ''), name=token.get('fullName') or '',
                                   incoming=incoming, from_swap=from_swap, amount=amount, value=usd_value)
        return self._filter.accept(candidate)

    # ------------------------------------------------------------------------------------------------------------------
    # A spot fill: one token is given away and another received in the same instant, which is exactly a Swap. The
    # quantities are exact (nothing is derived from a price), the fee is charged in a token that varies from fill to
    # fill - already supported by fee_symbol/fee_qty - and 'closedPnl' is discarded: JAL computes FIFO itself and
    # storing the exchange's own figure would create a second, unreconciled truth.
    def _process_fill(self, fill: dict, timestamp: int, tx_hash: str) -> None:
        market = fill.get('coin', '')
        if market not in self._markets:
            # Perpetual markets are named by a bare ticker and are absent from the spot registry. They need an
            # operation JAL doesn't have, so they stop the import instead of being booked as something else.
            raise _HaltImport(self.tr("fill on a market that is not a spot pair: ") + market)
        base, quote = self._markets[market]
        price = self._amount(fill.get('px'), self.tr("fill price"))
        size = self._amount(fill.get('sz'), self.tr("fill size"))
        notional = price * size
        side = fill.get('side', '')
        if side == 'B':          # the base token was bought and paid for with the quote token
            out_token, out_qty, in_token, in_qty = quote, notional, base, size
        elif side == 'A':        # the base token was sold for the quote token
            out_token, out_qty, in_token, in_qty = base, size, quote, notional
        else:
            raise _HaltImport(self.tr("fill with an unrecognized side: ") + str(side))

        fee = self._amount(fill.get('fee', '0'), self.tr("fill fee"))
        if self._amount(fill.get('builderFee', '0'), self.tr("builder fee")) != Decimal('0'):
            # A builder fee is charged on top of the exchange fee and is not necessarily in the same token; nothing
            # in this account has ever carried one, so it is stopped at rather than assumed away.
            raise _HaltImport(self.tr("fill with a builder fee"))
        if fee < Decimal('0'):
            # A negative fee is a maker rebate - the account RECEIVES tokens, which is income and not a cost. There
            # is no honest way to express it as a swap fee, so it waits for a decision instead of being dropped.
            raise _HaltImport(self.tr("fill with a maker rebate (negative fee)"))
        # A token acquired through a fill was chosen by the user, so it is never dust - but the filter still runs,
        # to honour a manual blacklist. It is asked before any asset record is created, so a rejected token leaves
        # nothing behind.
        if not self._accept_token(in_token, in_qty, incoming=True, from_swap=True):
            self._skip(self.tr("fill in a token quarantined as dust/spam"), tx_hash)
            return
        fee_asset_id = self._token_asset(self._token_of(fill.get('feeToken', ''))) if fee > Decimal('0') else None
        note = self.tr("Bought ") if side == 'B' else self.tr("Sold ")
        note += f"{size} {base['name']} @ {price} {quote['name']}"
        self._add_swap(timestamp, self._token_asset(out_token), out_qty, self._token_asset(in_token), in_qty,
                       tx_hash, note=note, fee=fee, fee_asset_id=fee_asset_id)

    # ------------------------------------------------------------------------------------------------------------------
    def _classify_ledger(self, entry: dict, timestamp: int, tx_hash: str) -> None:
        delta = entry.get('delta', {})
        kind = delta.get('type', '')
        if kind == _DEPOSIT:
            return self._process_bridge_deposit(delta, timestamp, tx_hash)
        if kind == _WITHDRAW:
            return self._process_bridge_withdrawal(delta, timestamp, tx_hash)
        if kind in (_SPOT_TRANSFER, _INTERNAL_TRANSFER):
            return self._process_address_transfer(delta, timestamp, tx_hash)
        if kind == _SEND:
            return self._process_send(delta, timestamp, tx_hash)
        if kind == _STAKING_TRANSFER:
            return self._process_staking(delta, timestamp, tx_hash)
        if kind == _REWARDS_CLAIM:
            return self._process_rewards(delta, timestamp, tx_hash)
        if kind == _CLASS_TRANSFER:
            # USDC moved between the spot and the perp balance of the same account. Both are the same JAL account,
            # so nothing left it and there is nothing to book.
            self._skip(self.tr("transfer between the spot and the perpetuals balance"), tx_hash)
            return
        raise _HaltImport(self.tr("unsupported ledger record: ") + (kind or self.tr("unnamed")))

    # USDC arriving over the Arbitrum bridge. It is imported as a plain incoming transfer whose counterparty JAL
    # doesn't know, so the import asks which account it came from - and that is what finally closes the pending
    # bridge half the Arbitrum wallet produced when it sent the money (CRYPTO_PATH #47/#48).
    def _process_bridge_deposit(self, delta: dict, timestamp: int, tx_hash: str) -> None:
        amount = self._amount(delta.get('usdc'), self.tr("deposit amount"))
        token = self._token_of('USDC')
        # A bridge deposit is USDC, so the amount is its own USD value
        if not self._accept_token(token, amount, incoming=True, from_swap=False, usd_value=amount):
            self._skip(self.tr("deposit of a token quarantined as dust/spam"), tx_hash)
            return
        self._add_transfer(timestamp, self._token_asset(token), amount, True, tx_hash,
                           note=self.tr("Deposit over the Hyperliquid bridge"))

    # USDC leaving over the Arbitrum bridge. This is the sending leg of a cross-chain move that the fetcher CAN
    # recognize (the destination is known to be the bridge), so it is added as a pending bridge half and paired
    # afterwards with its arrival on the other chain - the same treatment every other outgoing cross-chain leg gets.
    #
    # 'usdc' is the amount that actually CROSSES, and the withdrawal fee is charged on top of it (the account loses
    # usdc + fee). This was verified on-chain: a withdraw of usdc=6.247435, fee=1.0 arrived on Arbitrum as exactly
    # 6.247435. So the bridged quantity is 'usdc' verbatim and the fee rides the half as a separate cost.
    def _process_bridge_withdrawal(self, delta: dict, timestamp: int, tx_hash: str) -> None:
        crossed = self._amount(delta.get('usdc'), self.tr("withdrawal amount"))
        fee = self._amount(delta.get('fee', '0'), self.tr("withdrawal fee"))
        token_asset = self._token_asset(self._token_of('USDC'))
        self._add_bridge_half(timestamp, token_asset, crossed, tx_hash,
                              note=self.tr("Withdrawal over the Hyperliquid bridge"),
                              fee=fee, fee_asset_id=token_asset if fee > Decimal('0') else None)

    # A token sent to, or received from, another HyperCore address. The counterparty is an address, so it is left
    # unknown and the import asks the user which account it maps to - exactly as an on-chain transfer does.
    def _process_address_transfer(self, delta: dict, timestamp: int, tx_hash: str) -> None:
        address = self._account.address().lower()
        source = str(delta.get('user', '')).lower()
        destination = str(delta.get('destination', '')).lower()
        if (not source and not destination) or (source == address and destination == address):
            # A move between the account's own order books names no outside address (or names only itself). Nothing
            # left the account, so there is nothing to book - but it is reported rather than dropped quietly.
            self._skip(self.tr("transfer within the account's own order books"), tx_hash)
            return
        if destination == address and source != address:
            incoming = True
        elif source == address and destination != address:
            incoming = False
        else:
            # Neither side is this account: there is no movement this fetcher can describe.
            raise _HaltImport(self.tr("transfer whose direction can't be established"))
        reference = delta.get('token', 'USDC')      # an internalTransfer is always in USDC and names no token
        token = self._token_of(reference)
        amount = self._amount(delta.get('amount', delta.get('usdc')), self.tr("transfer amount"))
        # The fee of a transfer is billed to whoever sent it. The same record reaches both sides of the move, so it
        # is only charged here when this account is the sender - otherwise the counterparty's cost would be booked
        # against the receiver.
        fee, fee_token = (Decimal('0'), None) if incoming else self._transfer_fee(delta)
        # The venue reports the USD value of the transfer, which is what decides whether an incoming token is dust -
        # a listed token worth $0 is still an airdrop (see _accept_token).
        usd_value = self._usd_value(delta)
        if incoming and not self._accept_token(token, amount, incoming=True, from_swap=False, usd_value=usd_value):
            self._skip(self.tr("incoming token quarantined as dust/spam"), tx_hash)
            return
        counterparty = source if incoming else destination
        self._add_transfer(timestamp, self._token_asset(token), amount, incoming, tx_hash,
                           note=self._counterparty_note(counterparty, incoming),
                           fee=fee, fee_asset_id=self._token_asset(fee_token) if fee > Decimal('0') else None)

    # The fee of a transfer, with the token it is charged in. A transfer record carries the fee under 'fee' (in the
    # token named by 'feeToken', USDC in the real history) or under 'nativeTokenFee' (paid in the chain's own coin,
    # HYPE). One operation carries a single fee, so a record charging both at once stops the import.
    def _transfer_fee(self, delta: dict) -> tuple:
        fee = self._amount(delta.get('fee', '0'), self.tr("transfer fee"))
        native_fee = self._amount(delta.get('nativeTokenFee', '0'), self.tr("transfer fee"))
        if fee > Decimal('0') and native_fee > Decimal('0'):
            raise _HaltImport(self.tr("transfer charged a fee in two different tokens"))
        if native_fee > Decimal('0'):
            return native_fee, self._token_of('HYPE')
        if fee > Decimal('0'):
            return fee, self._token_of(delta.get('feeToken') or 'USDC')
        return Decimal('0'), None

    # The USD value the venue attaches to a transfer, or None when it names none. It is what the dust filter judges
    # an incoming token by - the venue prices every transfer, so a listed but worthless airdrop is caught by value.
    def _usd_value(self, delta: dict):
        if delta.get('usdcValue') is None:
            return None
        try:
            return Decimal(str(delta['usdcValue']))
        except (DecimalException, ValueError):
            return None

    # A 'send' is an address transfer of one spot token, naming its 'user' (sender) and 'destination'. In the real
    # history every one carries both, whether it went to another person's address (fee 1 USDC) or arrived from one
    # (fee 0); the 'sourceDex'/'destinationDex' fields only say which order books it moved between and don't change
    # what it is to this account. _process_address_transfer books it by direction, and skips it when it names no
    # outside address at all (a move between the account's own books).
    def _process_send(self, delta: dict, timestamp: int, tx_hash: str) -> None:
        self._process_address_transfer(delta, timestamp, tx_hash)

    # ------------------------------------------------------------------------------------------------------------------
    # Staking. HYPE moved into the staking balance keeps belonging to the user and is neither sold nor converted -
    # it simply sits somewhere else while it earns. That is the container pattern (CRYPTO_PATH #50/#61/#63), so both
    # directions are plain transfers whose counterparty JAL doesn't know and the import asks which account the
    # staking balance is.
    #
    # How much was put in is remembered between fetches, which lets a withdrawal that returns MORE than went in be
    # split into the principal - a transfer back out of the box - and a staking reward for the excess. When the
    # deposit predates the sync cursor there is nothing to measure against and the whole amount is booked as
    # returned principal, never as income: inventing income out of a returned deposit is the one error that must
    # not happen here (#61).
    def _process_staking(self, delta: dict, timestamp: int, tx_hash: str) -> None:
        token = self._token_of(delta.get('token', 'HYPE'))
        amount = self._amount(delta.get('amount'), self.tr("staking amount"))
        asset_id = self._token_asset(token)
        name = token['name']
        if delta.get('isDeposit'):
            self._staked[name] = self._staked.get(name, Decimal('0')) + amount
            self._add_transfer(timestamp, asset_id, amount, False, tx_hash,
                               note=self.tr("Staked ") + name)
            return
        staked = self._staked.get(name)
        if staked is None:
            principal, reward = amount, Decimal('0')
            self._skip(self.tr("staking withdrawal whose deposit predates the sync cursor - yield not separated"),
                       tx_hash)
        else:
            principal = min(amount, staked)
            reward = amount - principal
            remaining = staked - principal
            if remaining > Decimal('0'):
                self._staked[name] = remaining
            else:
                self._staked.pop(name, None)
        self._add_transfer(timestamp, asset_id, principal, True, tx_hash,
                           note=self.tr("Unstaked ") + name)
        if reward > Decimal('0'):
            self._add_payment(JSF.PAYMENT_STAKING_REWARD, timestamp, asset_id, reward, tx_hash,
                              note=self.tr("Staking reward"))

    # Rewards credited to the account without anything being given in return
    def _process_rewards(self, delta: dict, timestamp: int, tx_hash: str) -> None:
        token = self._token_of(delta.get('token', 'HYPE'))
        amount = self._amount(delta.get('amount'), self.tr("reward amount"))
        self._add_payment(JSF.PAYMENT_STAKING_REWARD, timestamp, self._token_asset(token), amount, tx_hash,
                          note=self.tr("Reward"))

    # The staking state survives between fetches in the account's own data, as one JSON row (the pattern of #12).
    # Amounts are stored as strings so that a Decimal never passes through a float.
    def _load_staked(self) -> dict:
        stored = self._account.get_data(AccountData.StakeAccounts) or ''
        if not stored:
            return {}
        try:
            return {name: Decimal(amount) for name, amount in json.loads(stored).items()}
        except (json.JSONDecodeError, TypeError, ValueError, ArithmeticError):
            logging.warning(self.tr("Unreadable staking state of account ") + self._account.name())
            return {}

    # Written only once the fetched data has actually reached the database, exactly like the sync cursor: a state
    # saying "this much is staked" must never get ahead of the transfers that put it there.
    def _commit_state(self) -> None:
        if self._staked is None:      # nothing was fetched, so there is nothing to say about the staking balance -
            return                    # writing here would erase a state that is still perfectly valid
        self._account.set_data(AccountData.StakeAccounts,
                               json.dumps({name: str(amount) for name, amount in self._staked.items()}))

    # ------------------------------------------------------------------------------------------------------------------
    # Every amount the API reports is a decimal string in human units. It is parsed strictly: a quantity that can't
    # be read is not a rounding problem but a shape this fetcher doesn't understand, and continuing past it would
    # book a wrong number.
    def _amount(self, value, what: str) -> Decimal:
        if value is None:
            raise _HaltImport(self.tr("record with no ") + what)
        try:
            return Decimal(str(value))
        except (DecimalException, ValueError):
            raise _HaltImport(self.tr("record with an unreadable ") + what)

    # Both sides are shown, sender first, so the note carries the whole movement whichever way it went. A
    # counterparty that is another wallet of the user's own is left out - it says nothing the operation doesn't
    # already show.
    def _counterparty_note(self, counterparty: str, incoming: bool) -> str:
        if not counterparty or self._is_own_address(counterparty):
            return ''
        address = self._account.address()
        return f"{counterparty} → {address}" if incoming else f"{address} → {counterparty}"
