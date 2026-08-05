import json
import logging
from decimal import Decimal, DecimalException

from PySide6.QtWidgets import QApplication

from jal.constants import AssetLocation, PredefinedAccountType
from jal.db.account import JalAccount
from jal.db.chain_balance import JalChainBalance
from jal.db.db import JalDB
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

    # ------------------------------------------------------------------------------------------------------------------
    # The wallet a box was filled from. A box is always created FROM an account and every fill is a transfer, so the
    # relation is recorded even though no column names it - which is what lets an address-less box (a venue's internal
    # staking balance names nothing on a chain) still be tied to the address its balance has to be read at.
    def _wallet_of_box(self, box_id: int) -> JalAccount:
        wallets = self._read_to_list(
            "SELECT DISTINCT withdrawal_account FROM transfers "
            "WHERE deposit_account=:box AND NOT withdrawal_account IS NULL", [(":box", box_id)])
        if len(wallets) != 1:
            return None
        return JalAccount(int(wallets[0]))

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
        wallet = self._wallet_of_box(box.id())
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
    # Which venues accrue silently, and how each of them is read. The table is venue knowledge deliberately kept OUT
    # of the storage: 'chain_balances' is keyed by (account, asset) and knows nothing about staking or rebasing, which
    # is what lets the same table serve the box readers here and the rebasing-asset reader that comes later.
    #
    # A venue that is absent is absent on purpose. Tron's frozen TRX is a fixed quantity whose rewards are a separate
    # pot paid out by an explicit claim - a receivable, not balance growth. A CEX staking box has no API to ask at
    # all. A box of an unlisted venue simply never gets a row, which is the correct outcome rather than a gap.
    def _box_readers(self) -> dict:
        return {AssetLocation.HL_BLOCKCHAIN: self._hyperliquid_box_balance}

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
