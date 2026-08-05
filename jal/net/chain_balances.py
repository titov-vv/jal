import json
import logging
from decimal import Decimal, DecimalException

from PySide6.QtWidgets import QApplication

from jal.constants import AssetLocation, PredefinedAccountType
from jal.db.account import JalAccount
from jal.db.chain_balance import JalChainBalance
from jal.db.db import JalDB
from jal.db.settings import JalSettings
from jal.db.staking import JalStakingBox
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

# Call data of ERC-20 'decimals()' - the function selector alone, as it takes no arguments. It is the only way to
# learn the scale of a balance, which is reported as a bare integer (see _token_decimals).
_ERC20_DECIMALS = '0x313ce567'

# Decimals is a uint8, but no real token is anywhere near that: 18 is the usual value and 36 leaves generous room.
# An answer beyond this is not a token with very many decimal places, it is a call that returned something else.
_MAX_TOKEN_DECIMALS = 36


# ----------------------------------------------------------------------------------------------------------------------
# Reads what a chain really holds and records it in 'chain_balances'.
#
# This exists because a whole class of balance growth is INVISIBLE to a fetcher: a Solana stake account is credited
# its epoch rewards with no transaction behind it, a Hyperliquid delegation auto-compounds its rewards without ever
# touching the ledger feed, and an Aave aToken grows through a reserve index that emits nothing at all. A fetcher can
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

    def tr(self, text):
        return QApplication.translate("ChainBalanceReader", text)

    # Waits for a request while keeping the application responsive, exactly as the fetchers and the quote downloader
    # do - QThread.wait() would freeze the window instead.
    @staticmethod
    def _wait_for(request) -> None:
        while request.isRunning():
            QApplication.processEvents()

    def _post(self, url: str, request: dict):
        web_request = WebRequest(WebRequest.POST_JSON, url, params=request)
        self._wait_for(web_request)
        try:
            return json.loads(web_request.data())
        except (json.JSONDecodeError, TypeError):
            return None

    def _get(self, url: str, params: dict):
        web_request = WebRequest(WebRequest.GET, url, params=params)
        self._wait_for(web_request)
        try:
            return json.loads(web_request.data())
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
    # wallet that still holds anything. Anything else is refused and said out loud - an aggregate that cannot be split
    # must never be distributed across the boxes that share it, and a silently multiplied accrual is exactly the kind
    # of wrong number this whole feature exists to avoid producing.
    def _box_may_take_account_total(self, box: JalStakingBox, wallet: JalAccount, timestamp: int) -> bool:
        siblings = [x for x in self._boxes_of_wallet(wallet.id()) if x.id() != box.id() and x.holdings(timestamp)]
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
    # REBASING ASSETS. The other half of what this module reads, and the one the whole design was built from: an Aave
    # aToken's balance is a scaled number times the reserve's liquidity index, and that index rises EVERY BLOCK with
    # no event and no transfer behind it. A fetcher that can only book what a chain announces is therefore short by
    # the entire accrued interest - 2.24% on the position this was measured against, and growing.
    #
    # Unlike a staking box, the trigger is the ASSET rather than the account: the flag says this token's quantity can
    # grow on its own (AssetData.Rebasing), and it is set by hand per asset because inferring it from a ticker prefix
    # would eventually add invented quantity to a position that never grows. Share tokens must never carry it -
    # Fluid's fTokens and stkAAVE hold a fixed quantity whose PRICE accrues, which the quote source already reports.

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
        answer = self._get(chain.api_root, {"chainid": chain.chain_id, "module": "proxy", "action": "eth_call",
                                            "to": contract, "data": _ERC20_DECIMALS, "tag": "latest",
                                            "apikey": api_key})
        result = answer.get('result') if isinstance(answer, dict) else None
        if not result or not isinstance(result, str) or not result.startswith('0x') or len(result) < 3:
            logging.warning(self.tr("Could not read the decimals of token ") + f"{asset.symbol()} ({contract})")
            return None
        try:
            decimals = int(result, 16)
        except ValueError:
            logging.warning(self.tr("Unreadable decimals of token ") + f"{asset.symbol()} ({contract})")
            return None
        if not 0 <= decimals <= _MAX_TOKEN_DECIMALS:
            logging.warning(self.tr("Implausible decimals of token ") + f"{asset.symbol()}: {decimals}")
            return None
        asset.set_decimals(decimals)
        return decimals

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
    # A venue that is absent is absent on purpose. Tron's frozen TRX is a fixed quantity whose rewards are a separate
    # pot paid out by an explicit claim - a receivable, not balance growth. A CEX staking box has no API to ask at
    # all. A box of an unlisted venue simply never gets a row, which is the correct outcome rather than a gap.
    def _box_readers(self) -> dict:
        return {AssetLocation.HL_BLOCKCHAIN: self._hyperliquid_box_balance,
                AssetLocation.SOL_BLOCKCHAIN: self._solana_box_balance}

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
