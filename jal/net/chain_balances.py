import json
import logging
from decimal import Decimal, DecimalException

from PySide6.QtWidgets import QApplication

from jal.constants import AssetLocation, PredefinedAccountType, PredefinedAsset
from jal.db.account import JalAccount
from jal.db.asset import JalAsset, JalAssetCreator
from jal.db.chain_balance import JalChainBalance
from jal.db.db import JalDB
from jal.db.receivable import JalReceivable
from jal.db.settings import JalSettings
from jal.db.staking import JalStakingBox
from jal.db.symbol import JalSymbol
from jal.db.token_blacklist import normalize_address
from jal.net import aave, merkl, stakelink
from jal.net.web_request import WebRequest

# The keyless 'info' endpoint of HyperCore, the same one HyperliquidFetcher reads its history from
_HL_API_URL = "https://api.hyperliquid.xyz/info"

# The three pots a Hyperliquid staking balance is spread over, and the balance of the box is their SUM.
#
# Reading 'delegated' alone would be wrong in a way that only shows up at the worst moment: undelegating moves HYPE
# to 'undelegated', and withdrawing from the staking balance puts it into a ~7-day queue as 'totalPendingWithdrawal'.
# In both states the coins are still in the box and JAL's ledger still holds them - so a reader that watched
# 'delegated' would show the box collapsing to nothing the instant an unstake began.
# Measured against the real account twice: for ~110 seconds on 2026-08-03 the whole position sat in 'undelegated',
# and on 2026-08-04 it moved wholly into 'totalPendingWithdrawal' with 'delegated' and 'delegations[]' both empty.
# Only the three-field sum read either of them correctly.
_HL_BALANCE_FIELDS = ('delegated', 'undelegated', 'totalPendingWithdrawal')

# Hyperliquid stakes one coin and only one. The reader refuses a box holding anything else rather than attributing
# an account-level HYPE figure to some other asset - see _hyperliquid_box_balance().
_HL_STAKED_SYMBOL = 'HYPE'

# Solana's JSON-RPC, which is a different endpoint from the 'Enhanced Transactions' REST API the fetcher reads its
# history from - 'getAccountInfo' is a plain node method and is not part of that enriched surface. Same Helius key.
_SOL_RPC_URL = "https://mainnet.helius-rpc.com/"
_LAMPORTS = Decimal('10') ** 9      # 1 SOL = 10^9 lamports, the unit a stake account's balance is reported in

# Owner of every native stake account. Checking it is what makes the reading safe: a staking box carries its
# container's address, and if that address were ever wrong - mistyped, or pointing at an ordinary wallet - the whole
# balance sitting there would be read as this position's staked amount. The stake program is the one thing that
# proves the address really is a stake account, and it costs nothing to ask for.
_SOL_STAKE_PROGRAM = 'Stake11111111111111111111111111111111111111'

# Call data of the ERC-20 views that take no arguments - the function selector alone. 'decimals()' is the only way to
# learn the scale of a balance, which is reported as a bare integer (see _token_decimals); 'name()' and 'symbol()' are
# asked only when an asset has to be created for a token JAL has never seen (see _reward_asset).
_ERC20_DECIMALS = '0x313ce567'
_ERC20_NAME = '0x06fdde03'
_ERC20_SYMBOL = '0x95d89b41'

# The cap exists because the length word of a dynamic string comes from the answer itself, and an answer that isn't
# a string would otherwise be read as a request to decode megabytes.
_MAX_TOKEN_NAME = 128

# Decimals is a uint8, but no real token is anywhere near that: 18 is the usual value and 36 leaves generous room.
# An answer beyond this is not a token with very many decimal places, it is a call that returned something else.
_MAX_TOKEN_DECIMALS = 36


# ----------------------------------------------------------------------------------------------------------------------
# Reads what a chain really holds and records it in 'chain_balances'.
#
# This exists because a whole class of balance growth is INVISIBLE to a fetcher: a Solana stake account is credited
# its epoch rewards with no transaction behind it, a Hyperliquid delegation auto-compounds its rewards without ever
# touching the ledger feed, a stake.link position grows through the rebasing of an stLINK balance held inside the
# pool, and an Aave aToken grows through a reserve index that emits nothing at all. A fetcher can
# only book the movements a chain announces, so for these positions the ledger is structurally short of the real
# quantity, and the only way to learn the difference is to ask the chain what the balance IS.
#
# What is read is stored and displayed; it is never turned into an operation. The accrued quantity is an unrealized
# gain, and JAL books unrealized value as valuation data, not as income - income is recognized when it is realized,
# at withdrawal, which the fetchers already do by splitting a withdrawal into principal and reward.
#
# Only positions that CAN grow silently are read. A staking box of a venue known to accrue is one; a rebasing asset
# (AssetData.Rebasing) is the other, and it is deliberately not implemented here yet - the box readers write nothing
# to the ledger and cannot stop a rebuild, while the aToken track needs a realization rule to go with it.
class ChainBalanceReader(JalDB):
    def __init__(self):
        super().__init__()
        self._storage = JalChainBalance()
        self._receivables = JalReceivable()

    def tr(self, text):
        return QApplication.translate("ChainBalanceReader", text)

    # Waits for a request while keeping the application responsive, exactly as the fetchers and the quote downloader
    # do - waiting for the whole request in one go would freeze the window instead (see WebRequest.wait()).
    @staticmethod
    def _wait_for(request) -> None:
        while not request.wait():
            QApplication.processEvents()

    def _post(self, url: str, request: dict):
        web_request = WebRequest(WebRequest.POST_JSON, url, params=request)
        self._wait_for(web_request)
        try:
            return json.loads(web_request.data(), parse_float=Decimal)
        except (json.JSONDecodeError, TypeError):
            return None

    def _get(self, url: str, params: dict):
        web_request = WebRequest(WebRequest.GET, url, params=params)
        self._wait_for(web_request)
        try:
            return json.loads(web_request.data(), parse_float=Decimal)
        except (json.JSONDecodeError, TypeError):
            return None

    # ------------------------------------------------------------------------------------------------------------------
    # The wallet a box was filled from. A box is always created FROM an account and every fill is a transfer, so the
    # relation is recorded even though no column names it - which is what lets an address-less box (a venue's internal
    # staking balance names nothing on a chain) still be tied to the address its balance has to be read at.
    def _wallet_of_box(self, box: JalStakingBox) -> JalAccount:
        wallets = box.source_accounts()
        if len(wallets) != 1:
            return None
        return wallets[0]

    # Every staking box that was ever filled from this wallet.
    #
    # The direction of this query is the whole point, and an earlier draft of the plan had it backwards. Asking a BOX
    # for its wallets catches nothing: the shape that breaks an account-level reading is N BOXES for ONE wallet, and
    # in that shape every box still answers with exactly one wallet, so such a guard passes while the reader writes
    # the same account-level total into all N - each box then measures it against its own partial ledger and the
    # displayed accrual multiplies by N.
    #
    # Nothing in the application prevents that shape: the new-box dialog rejects only a duplicate ADDRESS, and a venue
    # box is address-less by design, so its uniqueness check never runs. Four validators in one Hyperliquid staking
    # balance makes per-validator boxes an obvious thing to reach for, which is what moves this from theoretical to
    # likely - and JAL deliberately does not model a validator as a location (it is a risk attribute of one staking
    # balance, not a place assets live), so one box per venue wallet is the design and not merely the common case.
    def _boxes_of_wallet(self, wallet_id: int) -> list:
        box_ids = self._read_to_list(
            "SELECT DISTINCT t.deposit_account FROM transfers t JOIN accounts a ON a.id=t.deposit_account "
            "WHERE t.withdrawal_account=:wallet AND a.account_type=:type",
            [(":wallet", wallet_id), (":type", PredefinedAccountType.Staking)])
        return [JalStakingBox(int(box_id)) for box_id in box_ids]

    # True when the account-level figure of a venue may be attributed to this box alone: it is the only box of its
    # wallet that still holds anything AND that the same reading would land on. Anything else is refused and said out
    # loud - an aggregate that cannot be split must never be distributed across the boxes that share it, and a
    # silently multiplied accrual is exactly the kind of wrong number this whole feature exists to avoid producing.
    #
    # What "the same reading" means is (chain, address), because that pair is the whole of what a reader asks about:
    # two boxes of one wallet on the same venue get the identical figure, while a wallet that stakes into two
    # DIFFERENT protocols gets two figures that have nothing to do with each other. A guard that looked at every
    # sibling regardless would refuse the second case too - and one wallet holding both a stake.link LINK position
    # and a stake.link SDL one is the ordinary shape, not a corner case.
    def _box_may_take_account_total(self, box: JalStakingBox, wallet: JalAccount, timestamp: int) -> bool:
        siblings = [x for x in self._boxes_of_wallet(wallet.id())
                    if x.id() != box.id() and x.chain() == box.chain() and x.address() == box.address()
                    and x.holdings(timestamp)]
        if siblings:
            logging.warning(self.tr("On-chain balance not read - the wallet has several staking boxes: ")
                            + f"{wallet.name()} ({', '.join(x.name() for x in siblings + [box])})")
            return False
        return True

    # ------------------------------------------------------------------------------------------------------------------
    # The asset a box holds, when it holds exactly one.
    #
    # A venue reports its staking balance as a bare number, not as "N of token X", so the reader has to say which
    # asset that number belongs to - and the only honest source for that is what the box is recorded as holding. A box
    # holding two assets, or none, is left alone rather than guessed at: attributing a HYPE figure to the wrong asset
    # would invent quantity out of nothing.
    @staticmethod
    def _sole_asset_of(box: JalStakingBox, timestamp: int):
        holdings = box.holdings(timestamp)
        if len(holdings) != 1:
            return None
        return holdings[0]['asset']

    # ------------------------------------------------------------------------------------------------------------------
    # Hyperliquid: one 'delegatorSummary' call per box, one number out. There is no decimals problem here - every
    # amount HyperCore reports is a decimal string in human units - and the call is keyless, so this is by far the
    # cheapest of the balance readers.
    def _hyperliquid_box_balance(self, box: JalStakingBox, timestamp: int):
        wallet = self._wallet_of_box(box)
        if wallet is None or not wallet.address():
            return None
        if not self._box_may_take_account_total(box, wallet, timestamp):
            return None
        asset = self._sole_asset_of(box, timestamp)
        if asset is None:
            return None
        # Hyperliquid stakes HYPE and nothing else, so a box holding something else is not a case this reader
        # understands - and 'delegatorSummary' would happily answer with a HYPE figure regardless.
        if _HL_STAKED_SYMBOL not in [x.upper() for x in asset.tickers()]:
            logging.warning(self.tr("On-chain balance not read - unexpected asset in a Hyperliquid staking box: ")
                            + f"{box.name()}")
            return None
        answer = self._post(_HL_API_URL, {"type": "delegatorSummary", "user": wallet.address()})
        if not isinstance(answer, dict):
            logging.warning(self.tr("Unexpected answer from Hyperliquid for account ") + wallet.name())
            return None
        total = Decimal('0')
        for field in _HL_BALANCE_FIELDS:
            if field not in answer:
                # A missing field is not a zero: the venue changing the shape of this answer must not be read as the
                # position having shrunk, which is what a silent default would produce.
                logging.warning(self.tr("Hyperliquid staking balance is missing a field: ") + field)
                return None
            try:
                total += Decimal(str(answer[field]))
            except (DecimalException, ValueError):
                logging.warning(self.tr("Unreadable Hyperliquid staking balance in field: ") + field)
                return None
        return asset.id(), total

    # ------------------------------------------------------------------------------------------------------------------
    # Solana native staking: one 'getAccountInfo' on the stake account, whose lamports ARE the position.
    #
    # This is the same mechanic as Hyperliquid's and the reader is a great deal simpler, because a Solana box knows
    # its own address - a stake account is a real account on the chain, unlike a venue's internal balance. Three
    # consequences follow, and each is the opposite of the Hyperliquid case:
    #  - no wallet has to be resolved: the box's own address is what is asked about;
    #  - no "several boxes share one figure" guard is needed or wanted. Every stake account has its own address and
    #    its own balance, so several Solana boxes on one wallet are perfectly normal - a wallet may stake to as many
    #    validators as it likes, and the new-box dialog already refuses a duplicate address;
    #  - the validator is visible in the answer but is not read: it is an attribute of the position, not a place the
    #    assets live, and the box balance is the whole account either way.
    #
    # The rent-exempt reserve inside those lamports is deliberately NOT deducted. It looks like something that should
    # be corrected for, and correcting it would be a bug: the fetcher books the whole native delta when the stake is
    # made (solana.py, _process_stake), so the recorded principal contains the reserve too and the two figures are
    # already comparable. Subtracting it here would invent a shortfall of ~0.00228 SOL on every Solana box.
    def _solana_box_balance(self, box: JalStakingBox, timestamp: int):
        address = box.address()
        if not address:
            return None
        asset = self._sole_asset_of(box, timestamp)
        if asset is None:
            return None
        key = JalSettings().getStr("ApiKey_Helius").strip()
        if not key:
            logging.warning(self.tr("On-chain balance not read - the Helius API key isn't set"))
            return None
        answer = self._post(f"{_SOL_RPC_URL}?api-key={key}",
                            {"jsonrpc": "2.0", "id": 1, "method": "getAccountInfo",
                             "params": [address, {"encoding": "base64"}]})
        if not isinstance(answer, dict) or 'error' in answer or 'result' not in answer:
            logging.warning(self.tr("Unexpected answer from Helius for stake account ") + address)
            return None
        account = answer['result'].get('value') if isinstance(answer['result'], dict) else None
        if account is None:
            # JSON-RPC says a null value for an existing call means the account is genuinely NOT on the chain - a
            # stake account is closed once it is emptied, so this is the ordinary end of a position's life rather
            # than a failure. Zero is the honest measurement and is recorded as one: it is what lets the books be
            # seen still holding something the chain no longer has, instead of the position quietly freezing at its
            # last reading. (An RPC failure is an 'error' object, handled above, and never reaches here.)
            logging.info(self.tr("Stake account no longer exists on chain: ") + address)
            return asset.id(), Decimal('0')
        if account.get('owner') != _SOL_STAKE_PROGRAM:
            logging.warning(self.tr("On-chain balance not read - the address is not a stake account: ") + address)
            return None
        try:
            return asset.id(), Decimal(str(account['lamports'])) / _LAMPORTS
        except (DecimalException, ValueError, KeyError, TypeError):
            logging.warning(self.tr("Unreadable balance of stake account ") + address)
            return None

    # ------------------------------------------------------------------------------------------------------------------
    # EVM CONTRACTS. What every reading of an EVM chain needs before it can ask anything: which provider serves the
    # chain, which contract an asset is on it, how to call a view and how to scale the bare integer that comes back.
    # Both tracks below go through these - the staking contracts read here and the rebasing assets read after them.

    # {location_id: EVM fetcher class}. The endpoint configuration is read off the fetchers rather than repeated here,
    # so a chain served by a different provider (Avalanche, on Routescan, with its own root and its own key) is
    # already right and cannot drift out of step with the fetcher that shares it.
    @staticmethod
    def _evm_chains() -> dict:
        from jal.net.chain_fetchers.ethereum import EthereumFetcher
        from jal.net.chain_fetchers.arbitrum import ArbitrumFetcher
        from jal.net.chain_fetchers.avalanche import AvalancheFetcher
        return {x.location_id: x for x in (EthereumFetcher, ArbitrumFetcher, AvalancheFetcher)}

    # Contract address of an asset on one chain, or '' when it has no listing there (or none carrying an address).
    def _contract_of(self, asset_id: int, location_id: int) -> str:
        id_type = AssetLocation.address_id_of(location_id)
        if id_type is None:
            return ''
        address = self._read(
            "SELECT i.id_value FROM asset_symbol s JOIN symbol_ids i ON i.symbol_id=s.id "
            "WHERE s.asset_id=:asset_id AND s.location_id=:location_id AND i.id_type=:id_type AND s.active=1 LIMIT 1",
            [(":asset_id", asset_id), (":location_id", location_id), (":id_type", id_type)])
        return address if address else ''

    # One 'eth_call' on a contract, as the hex word it answered with, or '' when it answered with anything else.
    #
    # A view that REVERTS answers with an 'error' object and no result at all, and telling that apart from a number
    # is not a formality here: an arithmetic underflow is how a stake.link view says the arguments it was given
    # don't match the state it holds, and reading such an answer as a quantity would invent one.
    def _eth_call(self, chain, contract: str, data: str, api_key: str) -> str:
        answer = self._get(chain.api_root, {"chainid": chain.chain_id, "module": "proxy", "action": "eth_call",
                                            "to": contract, "data": data, "tag": "latest", "apikey": api_key})
        result = answer.get('result') if isinstance(answer, dict) else None
        if not isinstance(result, str) or not result.startswith('0x') or len(result) < 3:
            return ''
        return result

    # Decimals of a token, asked of the contract once and remembered for good (AssetData.Decimals).
    #
    # A history endpoint reports the decimals beside every amount, which is why importing transfers never needed
    # this; a BALANCE answers with a bare integer and nothing else, so the scale has to come from somewhere and the
    # contract is the only authority on it. Asking on demand rather than recording it at import time is what makes
    # tokens JAL already holds work: a value written only by new imports would leave every existing position unable
    # to be read until it happened to move again.
    #
    # A value outside the plausible range is refused rather than stored. Decimals is a uint8 and an answer of, say,
    # 200 would not be a token with 200 decimal places - it would be a call that returned something else entirely,
    # and using it would divide a balance into nothing.
    def _token_decimals(self, asset: JalAsset, chain, contract: str, api_key: str):
        known = asset.decimals()
        if known is not None:
            return known
        decimals = self._contract_decimals(chain, contract, api_key, asset.symbol())
        if decimals is None:
            return None
        asset.set_decimals(decimals)
        return decimals

    # The same question asked of a token JAL has no asset for yet, which is the state every reward token starts in -
    # nothing can be remembered against an asset that doesn't exist, and the scale is needed before it is created.
    def _contract_decimals(self, chain, contract: str, api_key: str, symbol: str = ''):
        token = f"{symbol} ({contract})" if symbol else contract
        result = self._eth_call(chain, contract, _ERC20_DECIMALS, api_key)
        if not result:
            logging.warning(self.tr("Could not read the decimals of token ") + token)
            return None
        try:
            decimals = int(result, 16)
        except ValueError:
            logging.warning(self.tr("Unreadable decimals of token ") + token)
            return None
        if not 0 <= decimals <= _MAX_TOKEN_DECIMALS:
            logging.warning(self.tr("Implausible decimals of token ") + f"{token}: {decimals}")
            return None
        return decimals

    # The name a token calls itself, or '' when it won't say.
    #
    # It is asked once, when an asset has to be created for a token that has never been seen, and it earns its call:
    # a symbol is not unique and two different contracts sharing one are not a corner case. Aave's USDG receipt is
    # exactly that - '0x7c0477d0...' is "Aave Ethereum USDG" and '0xb0217f23...' is "Aave Ethereum USDG (wrapped)",
    # both answering 'aEthUSDG' - so an asset named after the symbol alone would be indistinguishable from the one
    # already in the database, while the two really are different tokens with different prices.
    def _token_name(self, chain, contract: str, api_key: str) -> str:
        return self._token_string(chain, contract, _ERC20_NAME, api_key)

    # The ticker a token calls itself by. Asked only where the source doesn't report one: an API answer carries the
    # symbol beside every reward, while a contract view answers with a bare integer and says nothing at all.
    def _token_symbol(self, chain, contract: str, api_key: str) -> str:
        return self._token_string(chain, contract, _ERC20_SYMBOL, api_key)

    # One of the string views of a token, decoded. Both are read the same way and both have the same two forms.
    def _token_string(self, chain, contract: str, selector: str, api_key: str) -> str:
        result = self._eth_call(chain, contract, selector, api_key)
        try:
            data = bytes.fromhex(result[2:]) if result else b''
        except ValueError:
            return ''
        # Old tokens answer with a bare bytes32 instead of a dynamic string, and both forms are in circulation
        if len(data) == 32:
            return data.rstrip(b'\0').decode('utf-8', 'ignore').strip()
        if len(data) < 64:
            return ''
        length = int.from_bytes(data[32:64], 'big')
        if not 0 < length <= _MAX_TOKEN_NAME or len(data) < 64 + length:
            return ''
        return data[64:64 + length].decode('utf-8', 'ignore').strip()

    # ------------------------------------------------------------------------------------------------------------------
    # stake.link's LINK PriorityPool - the first staking container whose size cannot be read from the chain alone.
    #
    # Everything about the protocol itself is in jal/net/stakelink.py; what is here is the part that belongs to JAL:
    # which box may be measured, against which asset, and how the answer is turned into a quantity. In short, the
    # position is the LINK still waiting in the pool's queue plus the unclaimed stLINK the pool holds for the
    # account, the second half carrying all of the yield because stLINK rebases. Both halves need the account's entry
    # in a merkle distribution the pool publishes to IPFS and keeps only the root of on-chain, so the payload is
    # verified against that root before a single figure from it is used.
    #
    # Like Hyperliquid and unlike Solana, the figure is per ACCOUNT: the address a box carries is the pool contract,
    # which every one of its users shares, so what identifies the position is the wallet. Hence the same guard.
    def _stakelink_priority_pool_balance(self, box: JalStakingBox, timestamp: int):
        wallet = self._wallet_of_box(box)
        if wallet is None or not wallet.address():
            return None
        if not self._box_may_take_account_total(box, wallet, timestamp):
            return None
        asset = self._sole_asset_of(box, timestamp)
        if asset is None:
            return None
        chain = self._evm_chains().get(box.chain())
        contract = self._contract_of(asset.id(), box.chain())
        if chain is None or not contract:
            return None
        api_key = JalSettings().getStr(chain.api_key_setting).strip()
        if not api_key:
            logging.warning(self.tr("On-chain balance not read - the API key isn't set: ") + chain.api_name)
            return None
        pool = box.address()
        # The pool says which token it takes, and it must be the one the box is recorded as holding. This is the
        # check that makes reading a bare address safe, the same way the stake program is for Solana: were the box
        # ever pointed at another pool, its whole LINK-shaped answer would be booked as this position's quantity.
        staked_token = self._eth_call(chain, pool, stakelink.SELECTOR_TOKEN, api_key)
        if not staked_token or staked_token[-40:].lower() != normalize_address(box.chain(), contract)[-40:]:
            logging.warning(self.tr("On-chain balance not read - the pool does not stake this asset: ")
                            + f"{asset.symbol()} @ {box.name()}")
            return None
        decimals = self._token_decimals(asset, chain, contract, api_key)
        if decimals is None:
            return None
        distribution = self._stakelink_distribution(chain, pool, wallet.address(), api_key)
        if distribution is None:
            return None
        amount, shares = distribution
        # Two calls and neither may be dropped: the first is what has NOT been distributed yet (everything deposited
        # since the last update of the tree is in it), the second is what has, with its accrued yield. Both take the
        # account's entry as their argument and subtract it from what the pool recorded, so a stale or wrong entry
        # makes them revert rather than answer - which is why an empty answer is refused instead of read as zero.
        queued = self._eth_call(chain, pool, stakelink.call_data(stakelink.SELECTOR_QUEUED_TOKENS,
                                                                 wallet.address(), amount), api_key)
        unclaimed = self._eth_call(chain, pool, stakelink.call_data(stakelink.SELECTOR_LSD_TOKENS,
                                                                    wallet.address(), shares), api_key)
        if not queued or not unclaimed:
            logging.warning(self.tr("Could not read the stake.link position of ") + wallet.name())
            return None
        try:
            return asset.id(), stakelink.position(int(queued, 16), int(unclaimed, 16), decimals)
        except (DecimalException, ValueError, TypeError):
            logging.warning(self.tr("Unreadable stake.link position of ") + wallet.name())
            return None

    # The wallet's entry in the distribution the pool has published, as (amount, sharesAmount) in wei.
    #
    # The pool publishes the tree to IPFS and keeps only its root and the content hash on-chain, so this is the one
    # reading in the module that leaves the chain - and the one place where trusting the answer would be a mistake.
    # It isn't trusted: the tree is rebuilt from whatever a gateway serves and its root compared with the on-chain
    # one, so an altered entry anywhere in the file is thrown away with the rest of it. What survives is a pair the
    # contract itself would honour.
    def _stakelink_distribution(self, chain, pool: str, address: str, api_key: str):
        digest = self._eth_call(chain, pool, stakelink.SELECTOR_IPFS_HASH, api_key)
        root = self._eth_call(chain, pool, stakelink.SELECTOR_MERKLE_ROOT, api_key)
        if not digest or not root:
            logging.warning(self.tr("Could not read the stake.link distribution of ") + pool)
            return None
        try:
            digest, root = bytes.fromhex(digest[2:]), bytes.fromhex(root[2:])
        except ValueError:
            logging.warning(self.tr("Unreadable stake.link distribution of ") + pool)
            return None
        if not any(root):
            # Nothing has been distributed yet, which is the ordinary state of a pool whose queue has never been
            # drained. A zero entry is the honest answer: the account's whole position is still in the queue.
            return 0, 0
        cid = stakelink.ipfs_cid(digest)
        if not cid:
            logging.warning(self.tr("Unreadable stake.link distribution of ") + pool)
            return None
        # The whole tree is fetched to read one line of it - there is no per-account endpoint, and the root can only
        # be checked against the whole file anyway. It is a few hundred KB and is asked for once per update.
        for gateway in stakelink.IPFS_GATEWAYS:
            entry = stakelink.distribution_entry(self._get(gateway + cid, {}), root, address)
            if entry is not None:
                return entry
        logging.warning(self.tr("stake.link distribution didn't match the published root, or couldn't be read: ")
                        + cid)
        return None

    # ------------------------------------------------------------------------------------------------------------------
    # REBASING ASSETS. The other half of what this module reads, and the one the whole design was built from: an Aave
    # aToken's balance is a scaled number times the reserve's liquidity index, and that index rises EVERY BLOCK with
    # no event and no transfer behind it. A fetcher that can only book what a chain announces is therefore short by
    # the entire accrued interest - 2.24% on the position this was measured against, and growing.
    #
    # Unlike a staking box, the trigger is the ASSET rather than the account: the flag says this token's quantity can
    # grow on its own (AssetData.Rebasing), and it is set by hand per asset because inferring it from a ticker prefix
    # would eventually add invented quantity to a position that never grows. Share tokens must never carry it -
    # Fluid's fTokens and stkAAVE hold a fixed quantity whose PRICE accrues, which the quote source already reports.

    # What one wallet really holds of one rebasing token, as {asset id: quantity}, or None when it could not be read.
    def _evm_token_balance(self, account: JalAccount, asset: JalAsset, timestamp: int):
        chain = self._evm_chains().get(account.chain())
        contract = self._contract_of(asset.id(), account.chain())
        if chain is None or not contract:
            return None
        api_key = JalSettings().getStr(chain.api_key_setting).strip()
        if not api_key:
            logging.warning(self.tr("On-chain balance not read - the API key isn't set: ") + chain.api_name)
            return None
        decimals = self._token_decimals(asset, chain, contract, api_key)
        if decimals is None:
            return None
        answer = self._get(chain.api_root, {"chainid": chain.chain_id, "module": "account", "action": "tokenbalance",
                                            "contractaddress": contract, "address": account.address(),
                                            "tag": "latest", "apikey": api_key})
        if not isinstance(answer, dict) or str(answer.get('status', '0')) != '1':
            logging.warning(self.tr("Could not read the balance of ") + f"{asset.symbol()} @ {account.name()}")
            return None
        try:
            return asset.id(), Decimal(str(answer['result'])) / (Decimal('10') ** decimals)
        except (DecimalException, ValueError, KeyError, TypeError):
            logging.warning(self.tr("Unreadable balance of ") + f"{asset.symbol()} @ {account.name()}")
            return None

    # Reads and records what every wallet really holds of every FLAGGED asset.
    #
    # Only flagged assets are asked about, and that is what keeps this cheap and keeps the table meaningful: a token
    # that cannot grow on its own would produce a row saying the chain and the books agree, which is worth nothing
    # and would bury the handful of rows that are worth something. In the author's database it is two requests.
    #
    # NOTE, and it cannot be worked around from here: a balance is only ever available for NOW. Asking with a past
    # block was tested at three different blocks and silently returned the latest value every time - the free proxy
    # is not archive-backed - so the interest that has already accrued cannot be back-filled and the series can only
    # start today. It is recognized as income at withdrawal, where the whole tracked delta is realized at once.
    def read_rebasing_assets(self, timestamp: int, locations: list = None) -> int:
        chains = self._evm_chains()
        count = 0
        for account in JalAccount.get_all_accounts(investing_only=True, include_hidden=True):
            if account.chain() not in chains or not account.address():
                continue
            if locations is not None and account.chain() not in locations:
                continue
            for holding in account.assets_list(timestamp):
                if not holding['asset'].rebasing():
                    continue
                measurement = self._evm_token_balance(account, holding['asset'], timestamp)
                if measurement is None:
                    continue
                asset_id, amount = measurement
                self._storage.store(timestamp, account.id(), asset_id, amount)
                count += 1
        return count

    # ------------------------------------------------------------------------------------------------------------------
    # Which venues accrue silently, and how each of them is read. The table is venue knowledge deliberately kept OUT
    # of the storage: 'chain_balances' is keyed by (account, asset) and knows nothing about staking or rebasing, which
    # is what lets the same table serve the box readers here and the rebasing-asset reader that comes later.
    #
    # A venue that is absent is absent on purpose, and most of them are absent for the same reason: what they pay is
    # a RECEIVABLE rather than growth of the staked quantity, and this table measures a quantity. Tron's frozen TRX is
    # a fixed amount whose rewards sit in a separate pot until an explicit claim; stake.link's SDL locking is the same
    # shape and more so - `staked()` never moves and the yield arrives as claimable stLINK, stPOL and stESP, three
    # assets the box does not hold, so its accrual measured in SDL is genuinely zero. Those belong in 'receivables'
    # instead (see read_receivables() below, which reads Merkl and Aave's Safety module, and is where SDL slots in
    # next). A CEX staking box has no API to ask at all. A box of an unlisted venue simply never gets a row, which
    # is the correct outcome, not a gap.
    def _box_readers(self) -> dict:
        return {AssetLocation.HL_BLOCKCHAIN: self._hyperliquid_box_balance,
                AssetLocation.SOL_BLOCKCHAIN: self._solana_box_balance,
                AssetLocation.ETH_BLOCKCHAIN: self._evm_box_balance}

    # The staking contracts of an EVM chain that can be read, as {location: {contract address: reader}}.
    #
    # One more level of dispatch than the other chains need, and the chain is what forces it: an EVM box's address IS
    # the contract holding the position, a chain carries as many staking protocols as anyone cares to deploy on it,
    # and each of them reports what it holds in its own way. So here the chain says nothing and the contract says
    # everything - the same split the protocol registry makes for a transaction's counterparty.
    def _evm_box_readers(self) -> dict:
        return {AssetLocation.ETH_BLOCKCHAIN: {stakelink.PRIORITY_POOL: self._stakelink_priority_pool_balance}}

    # A box of an EVM chain is read by the contract it points at. One pointing at a contract with no reader is left
    # alone, exactly as a box of an unlisted venue is - the absence is the correct outcome, not a gap.
    def _evm_box_balance(self, box: JalStakingBox, timestamp: int):
        if not box.address():
            return None
        reader = self._evm_box_readers().get(box.chain(), {}).get(normalize_address(box.chain(), box.address()))
        return reader(box, timestamp) if reader else None

    # Reads and records the real balance of every staking box whose venue is known to accrue silently.
    #
    # 'locations' filters by chain, so the checkboxes of the quote-update dialog decide which venues are asked - they
    # already list every blockchain, and no new UI is needed for this.
    #
    # A box that is empty in the books is skipped: there is nothing for a measurement to be compared against, and a
    # container that was emptied has no accrual left to show. A box the reader can't resolve is skipped too, and said
    # so in the log - never guessed at.
    def read_staking_boxes(self, timestamp: int, locations: list = None) -> int:
        readers = self._box_readers()
        count = 0
        for box in JalStakingBox.get_boxes(timestamp):
            reader = readers.get(box.chain())
            if reader is None:
                continue
            if locations is not None and box.chain() not in locations:
                continue
            measurement = reader(box, timestamp)
            if measurement is None:
                continue
            asset_id, amount = measurement
            self._storage.store(timestamp, box.id(), asset_id, amount)
            count += 1
        return count

    # ------------------------------------------------------------------------------------------------------------------
    # CLAIMABLE REWARDS. The other kind of unrealized value a chain holds, and the one the tables above deliberately
    # refuse: not a position that grew, but a distributor that OWES the wallet something it has not paid yet.
    #
    # The trigger is the WALLET, like the rebasing-asset reader and unlike a box - a Merkl campaign has no container
    # behind it and Aave's Safety module is a token the wallet itself holds, so in both cases the reward is simply
    # owed to an address. What is read goes into 'receivables', which is keyed by the SOURCE as well as the asset,
    # because several distributors pay the same token to the same wallet.

    # Who may owe a wallet something on each chain, as {location: {contract: reader}} - the same shape
    # _evm_box_readers() uses, and for the same reason: the chain says nothing about who owes the money and the
    # contract says everything, because the contract IS the 'source' a receivable is keyed by.
    #
    # Merkl is registered on every EVM chain JAL reads rather than on a list of its own: its Distributor is deployed
    # at one address everywhere it serves, and a list here would quietly stop asking on a chain added later.
    def _receivable_readers(self) -> dict:
        readers = {location: {merkl.DISTRIBUTOR: self._merkl_claims} for location in self._evm_chains()}
        readers[AssetLocation.ETH_BLOCKCHAIN].update({module: self._aave_claims for module in aave.SAFETY_MODULES})
        return readers

    # Which sources may owe one wallet something, as {contract: (reader, {location: account})}.
    #
    # A source is asked ONCE about every chain the wallet is held on rather than once per chain, because that is
    # what Merkl's single request needs; a source deployed on one chain only gets a group of one and never notices.
    @staticmethod
    def _sources_of(readers: dict, accounts: dict) -> dict:
        sources = {}
        for location, account in accounts.items():
            for contract, reader in readers.get(location, {}).items():
                sources.setdefault(contract, (reader, {}))[1][location] = account
        return sources

    # Reads and records everything the known distributors owe every wallet.
    #
    # Wallets are grouped by ADDRESS rather than asked about one account at a time: JAL models one account per chain,
    # the same address is usually held on several of them, and Merkl answers about every chain in a single call. So a
    # wallet that exists on Ethereum and Arbitrum costs one request, not two.
    #
    # 'locations' filters by chain, exactly as the other two readers do - the checkboxes of the quote-update dialog
    # decide which chains are asked, and no new UI is needed.
    def read_receivables(self, timestamp: int, locations: list = None) -> int:
        readers = self._receivable_readers()
        wallets = {}
        for account in JalAccount.get_all_accounts(investing_only=True, include_hidden=True):
            if account.chain() not in readers or not account.address():
                continue
            if locations is not None and account.chain() not in locations:
                continue
            wallets.setdefault(normalize_address(account.chain(), account.address()), {})[account.chain()] = account
        count = 0
        for address, accounts in wallets.items():
            for source, (reader, holders) in self._sources_of(readers, accounts).items():
                count += reader(timestamp, source, address, holders)
        return count

    # Writes down as zero every claim of one source that the source no longer reports.
    # A stream that has stopped being reported must be recorded rather than left standing: the display reads the
    # latest row, so a claim that quietly disappeared would otherwise be shown as owed for good. Same discipline the
    # Solana reader follows for a stake account that has been closed.
    def _forget_unreported(self, timestamp: int, account: JalAccount, source: str, reported: set) -> None:
        for asset_id, known_source in self._receivables.known_claims(account.id()):
            if known_source == source and asset_id not in reported:
                self._receivables.store(timestamp, account.id(), asset_id, known_source, Decimal('0'), Decimal('0'))

    # ------------------------------------------------------------------------------------------------------------------
    # AAVE'S SAFETY MODULE. Everything about the protocol is in jal/net/aave.py; what is here is the part that belongs
    # to JAL, which asset the answer is about and how a bare integer becomes a quantity.
    # What one Safety module owes one wallet. Returns how many claims were recorded.
    def _aave_claims(self, timestamp: int, source: str, address: str, accounts: dict) -> int:
        chains = self._evm_chains()
        count = 0
        for location, account in accounts.items():
            recorded = self._store_aave_rewards(timestamp, chains[location], account, source, address)
            if recorded is None:
                continue
            count += recorded
        return count

    # One module's reward, stored. None when it could not be read at all, which is what stops a failed reading from
    # being mistaken for "nothing is owed" and zeroing what was recorded before.
    def _store_aave_rewards(self, timestamp: int, chain, account: JalAccount, source: str, address: str):
        api_key = JalSettings().getStr(chain.api_key_setting).strip()
        if not api_key:
            logging.warning(self.tr("Claimable rewards not read - the API key isn't set: ") + chain.api_name)
            return None
        # Which token the module pays is asked of the module rather than assumed: both of them pay AAVE today, and a
        # reward booked against the wrong asset would be wrong in the one way nobody would ever notice.
        token = aave.address_answer(self._eth_call(chain, source, aave.SELECTOR_REWARD_TOKEN, api_key))
        if not token:
            logging.warning(self.tr("Could not read the reward token of ") + source)
            return None
        # The view and not the stored mapping - see the header of jal/net/aave.py. Reading 'stakerRewardsToClaim'
        # instead would have reported 0.003% of the truth on the position this was measured against.
        owed = aave.amount_answer(self._eth_call(chain, source, aave.rewards_call(address), api_key))
        if owed is None:
            logging.warning(self.tr("Could not read the claimable rewards of ") + f"{source} @ {account.name()}")
            return None
        if owed == 0:
            # Nothing is owed, and nothing is invented to say so: an asset is created only for a reward that exists,
            # and a wallet holding none of the staked token would otherwise be given one it will never hold. What
            # this module paid before still gets its zero, which is what keeps a figure that was paid off screen.
            self._forget_unreported(timestamp, account, source, set())
            return 0
        resolved = self._reward_asset(chain, account, token, api_key)
        if resolved is None:
            return None       # the token couldn't be read, which is not the same thing as nothing being owed
        asset, decimals = resolved
        # 'pending' stays at zero: a Safety module has no epoch and no unproven bucket - what it reports is
        # claimable this second.
        self._receivables.store(timestamp, account.id(), asset.id(), source,
                                Decimal(owed) / (Decimal('10') ** decimals))
        self._forget_unreported(timestamp, account, source, {asset.id()})
        return 1

    # ------------------------------------------------------------------------------------------------------------------
    # MERKL, the first source and the only one with a merkle distribution behind it.

    # What Merkl owes one wallet, across every chain that wallet is held on. Returns how many claims were recorded.
    def _merkl_claims(self, timestamp: int, source: str, address: str, accounts: dict) -> int:
        chains = self._evm_chains()
        answer = self._get(merkl.API_URL.format(address=address),
                           {"chainId": ",".join(str(chains[x].chain_id) for x in accounts)})
        if answer is None:
            logging.warning(self.tr("Could not read the claimable rewards of ")
                            + f"{list(accounts.values())[0].name()}")
            return 0
        count = 0
        for location, account in accounts.items():
            chain = chains[location]
            rewards = merkl.chain_rewards(answer, chain.chain_id)
            if rewards is None:
                logging.warning(self.tr("Unexpected answer from Merkl for account ") + account.name())
                continue
            recorded = self._store_merkl_chain(timestamp, chain, account, source, rewards)
            if recorded is None:
                continue
            count += recorded
        return count

    # One chain's worth of claims, stored. None when the chain could not be read at all, which is what stops a
    # failed reading from being mistaken for "nothing is owed" and zeroing what was recorded before.
    def _store_merkl_chain(self, timestamp: int, chain, account: JalAccount, source: str, rewards: list):
        api_key = JalSettings().getStr(chain.api_key_setting).strip()
        if not api_key:
            logging.warning(self.tr("Claimable rewards not read - the API key isn't set: ") + chain.api_name)
            return None
        # The root the CONTRACT published, never the one the API reports beside the proof: while a dispute period is
        # open the two disagree, and the contract's is the one a claim would be verified against.
        root = self._eth_call(chain, source, merkl.SELECTOR_MERKLE_ROOT, api_key)
        try:
            root = bytes.fromhex(root[2:]) if root else b''
        except ValueError:
            root = b''
        if len(root) != 32:
            logging.warning(self.tr("Could not read the Merkl distribution root on ") + chain.api_name)
            return None
        count = 0
        for reward in rewards:
            claim = self._merkl_claim(chain, account, source, reward, root, api_key)
            if claim is None:
                continue
            asset_id, amount, pending = claim
            self._receivables.store(timestamp, account.id(), asset_id, source, amount, pending)
            count += 1
        # Everything Merkl has stopped reporting is written down as zero - see _forget_unreported(). What decides it
        # is what the ANSWER still mentions, not what was successfully stored above.
        self._forget_unreported(timestamp, account, source, self._reported_assets(account, rewards))
        return count

    # The assets the source named in this answer, whether or not each of them could be read. Only assets JAL already
    # knows are looked up: a token it has never seen cannot be one of the claims it recorded before.
    def _reported_assets(self, account: JalAccount, rewards: list) -> set:
        id_type = AssetLocation.address_id_of(account.chain())
        if id_type is None:
            return set()
        reported = set()
        for reward in rewards:
            entry = merkl.reward_entry(reward)
            if entry is None:
                continue
            symbol = JalSymbol.find_by_identifier(id_type, normalize_address(account.chain(), entry['address']))
            if symbol.id():
                reported.add(symbol.asset().id())
        return reported

    # One reward line as (asset_id, claimable, pending), or None when it can't be read or can't be trusted.
    def _merkl_claim(self, chain, account: JalAccount, source: str, reward, root: bytes, api_key: str):
        entry = merkl.reward_entry(reward)
        if entry is None:
            logging.warning(self.tr("Unreadable claimable reward for account ") + account.name())
            return None
        # The proof is walked before anything else is done with the line. An amount that doesn't reach the published
        # root is not a small discrepancy to log and carry on with - it is a number the distributor would not honour.
        if merkl.verified_amount(account.address(), entry['address'], entry['amount'], entry['proofs'], root) is None:
            logging.warning(self.tr("Claimable reward didn't match the published root: ")
                            + f"{entry['symbol']} @ {account.name()}")
            return None
        claimed = merkl.claimed_amount(
            self._eth_call(chain, source, merkl.claimed_call(account.address(), entry['address']), api_key))
        if claimed is None:
            logging.warning(self.tr("Could not read what has already been claimed of ")
                            + f"{entry['symbol']} @ {account.name()}")
            return None
        # What the tree awards MINUS what the contract has already paid. The floor matters: a claim that lands
        # between the API's snapshot and this call leaves 'claimed' ahead of 'amount', and a negative receivable
        # would be displayed as a debt the account owes.
        unclaimed = max(entry['amount'] - claimed, 0)
        # The subtraction comes BEFORE the asset is resolved so that nothing is invented to record a nothing. A
        # campaign that has been claimed to zero is the ordinary state of most streams - Merkl reports them for as
        # long as they existed - and creating a quote-less asset for each of them would fill the asset list with
        # tokens the account has never held and never will. A stream JAL already knows still gets its zero written,
        # because that zero is what stops a stale figure from lingering on screen.
        resolved = self._reward_asset(chain, account, entry['address'], api_key, symbol=entry['symbol'],
                                     decimals=entry['decimals'], create=unclaimed > 0)
        if resolved is None:
            return None
        asset, decimals = resolved
        return asset.id(), merkl.quantity(unclaimed, decimals), merkl.quantity(entry['pending'], decimals)

    # The asset a reward is paid in and the scale of its amounts, as (asset, decimals) - created if JAL has never
    # seen the token and there is something to record. None when the token can't be read, or when nothing is owed in
    # a token JAL doesn't know.
    #
    # Creating it is the deliberate choice here, and it is the opposite of what the balance readers above do - they
    # start from an asset the account already holds and refuse to invent one. A reward is different precisely because
    # the account holds NONE of it: refusing an unknown token would make the whole feature silent for exactly the
    # campaigns it exists to catch, which is a reward in a coin that has never arrived. What is left behind if the
    # campaign is never claimed is an asset with no operations and no quote - visible, harmless and removable.
    #
    # 'symbol' and 'decimals' are what the SOURCE said about the token, for a source that says anything at all: an
    # API reports both beside every reward, while a contract view answers with a bare integer. What is missing is
    # asked of the token itself, and only where it is really needed - a token JAL already knows carries its own
    # decimals, and a ticker is needed only to create one.
    def _reward_asset(self, chain, account: JalAccount, contract: str, api_key: str, symbol: str = '',
                      decimals: int = None, create: bool = True):
        location = account.chain()
        id_type = AssetLocation.address_id_of(location)
        if id_type is None:
            return None
        # A reported value is refused BEFORE anything is created: it would divide the reward into nothing, or into a
        # fortune, and an asset invented for a reward that is then thrown away would be left behind for no reason.
        if decimals is not None and not 0 <= decimals <= _MAX_TOKEN_DECIMALS:
            logging.warning(self.tr("Implausible decimals of token ") + f"{symbol}: {decimals}")
            return None
        address = normalize_address(location, contract)
        listing = JalSymbol.find_by_identifier(id_type, address)
        if listing.id():
            asset = listing.asset()
            if decimals is None:
                decimals = self._token_decimals(asset, chain, address, api_key)
                return (asset, decimals) if decimals is not None else None
            asset.set_decimals(decimals)   # a no-op when the token already has them - see set_decimals()
            return asset, decimals
        if not create:
            return None
        if decimals is None:
            decimals = self._contract_decimals(chain, address, api_key)
            if decimals is None:
                return None
        symbol = symbol or self._token_symbol(chain, address, api_key)
        if not symbol:
            logging.warning(self.tr("Couldn't read the ticker of a claimable reward token: ") + address)
            return None
        # The name comes from the contract rather than from the API, which reports only a ticker. Two different
        # tokens sharing a ticker is not a corner case - see _token_name() - and an asset named after the ticker
        # alone would be impossible to tell from the one already in the database.
        name = self._token_name(chain, address, api_key) or symbol
        logging.info(self.tr("New asset created for a claimable reward: ") + f"{name} ({address})")
        creator = JalAssetCreator(PredefinedAsset.Crypto, name)
        if not creator.id():
            logging.warning(self.tr("Couldn't create an asset for a claimable reward: ") + symbol)
            return None
        symbol_id = creator.add_symbol(symbol, account.currency(), location_id=location)
        creator.add_identifier(symbol_id, id_type, address)
        asset = creator.commit()
        asset.set_decimals(decimals)
        return asset, decimals
