from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from tests.test_polkadot_classifier import WALLET, FRIEND, DOT, POOL, BONDED, dot_wallet, fetch, received, pool_call
from jal.constants import AssetLocation, PredefinedAsset
from jal.data_import.statement import JSF
from jal.db.asset import JalAsset
from jal.db.chain_balance import JalChainBalance
from jal.db.ledger import Ledger
from jal.db.receivable import JalReceivable
from jal.db.staking import JalStakingBox
from jal.net import chain_balances
from jal.net.chain_balances import ChainBalanceReader
from jal.net.chain_fetchers.polkadot import PolkadotFetcher

# The box holds the pool bond and is valued by the node's member_total_balance; what the pool owes and hasn't paid is
# a receivable. The node is replaced by answers of the shape it gave for the real wallet on 17 Nov 2026.

NOW = 1_800_000_000
SOURCE = chain_balances._DOT_REWARD_SOURCE


def u128(value: int) -> str:
    return "0x" + value.to_bytes(16, 'little').hex()


def member(pool: int, points: int) -> str:
    return "0x" + (pool.to_bytes(4, 'little') + points.to_bytes(16, 'little')).hex() + "00" * 17


# A fake node: PoolMembers by 'membership', the runtime calls by 'calls'
def node(monkeypatch, membership=None, calls=None) -> list:
    asked = []

    def post(self, url, request):
        asked.append((url, request['method'], request['params']))
        if request['method'] == "state_getStorage":
            return {"jsonrpc": "2.0", "id": 1, "result": membership}
        if request['method'] == "state_call" and request['params'][0] in (calls or {}):
            return {"jsonrpc": "2.0", "id": 1, "result": calls[request['params'][0]]}
        return {"jsonrpc": "2.0", "id": 1, "error": {"code": -32000, "message": "unknown"}}
    monkeypatch.setattr(ChainBalanceReader, "_post", post)
    return asked


# The wallet received 22 DOT and joined pool 54 with 21 of them, imported the way a fetch does it
@pytest.fixture
def staked(dot_wallet):
    box = JalStakingBox.create(dot_wallet, "DOT @Nova #1", protocol="Polkadot nomination pool",
                               chain=AssetLocation.DOT_BLOCKCHAIN, address=BONDED)
    fetcher, data = fetch(dot_wallet, received(100, FRIEND, 22 * DOT) + pool_call(200, "join"),
                          bonds={200: 21 * DOT})
    assert not fetcher.skipped()
    assert fetcher.mapped_id(JSF.ACCOUNTS, data[JSF.TRANSFERS][1]['account'][1]) == box.id()
    fetcher.import_fetched()
    Ledger().rebuild(from_timestamp=0)
    yield dot_wallet, box


def test_box_holds_the_bond(staked):
    _, box = staked
    [holding] = box.holdings(NOW)
    assert holding['amount'] == Decimal(21)


def test_box_is_read_from_the_node(staked, monkeypatch):
    wallet, box = staked
    asked = node(monkeypatch, member(POOL, 21 * DOT), {"NominationPoolsApi_member_total_balance": u128(21 * DOT + 5)})
    assert ChainBalanceReader().read_staking_boxes(NOW) == 1
    account_id = bytes(range(32))
    assert [x[1:] for x in asked] == [("state_getStorage", ["0x" + PolkadotFetcher.pool_member_key(account_id)]),
                                      ("state_call", ["NominationPoolsApi_member_total_balance",
                                                      "0x" + account_id.hex()])]
    [holding] = box.holdings(NOW)
    assert JalChainBalance().latest(box.id(), holding['asset'].id(), NOW)['amount'] == Decimal("21.0000000005")


# A member of another pool is not this box's stake; a member that left reads as an emptied position
def test_box_of_another_pool_is_not_read(staked, monkeypatch):
    _, box = staked
    node(monkeypatch, member(7, DOT), {"NominationPoolsApi_member_total_balance": u128(DOT)})
    assert ChainBalanceReader().read_staking_boxes(NOW) == 0


def test_box_of_a_member_that_left_reads_zero(staked, monkeypatch):
    _, box = staked
    node(monkeypatch, None, {"NominationPoolsApi_member_total_balance": u128(0)})
    assert ChainBalanceReader().read_staking_boxes(NOW) == 1
    [holding] = box.holdings(NOW)
    assert JalChainBalance().latest(box.id(), holding['asset'].id(), NOW)['amount'] == Decimal(0)


def test_box_failed_reading_records_nothing(staked, monkeypatch):
    node(monkeypatch, member(POOL, 21 * DOT), {})
    assert ChainBalanceReader().read_staking_boxes(NOW) == 0


# ----------------------------------------------------------------------------------------------------------------------
# Asked about the wallet only: the box is a DOT account too, at the pool's bonded account
def test_pending_reward_is_a_claim_in_the_wallets_dot(staked, monkeypatch):
    wallet, _ = staked
    asked = node(monkeypatch, calls={"NominationPoolsApi_pending_rewards": u128(123_456_789)})
    assert ChainBalanceReader().read_receivables(NOW, [AssetLocation.DOT_BLOCKCHAIN]) == 1
    assert [x[2] for x in asked] == [["NominationPoolsApi_pending_rewards", "0x" + bytes(range(32)).hex()]]
    [claim] = JalReceivable().claims(wallet.id(), NOW)
    dot = JalAsset.find({'symbol': 'DOT', 'type': PredefinedAsset.Crypto})
    assert (claim['asset_id'], claim['source'], claim['amount']) == (dot.id(), SOURCE, Decimal("0.0123456789"))


def test_claimed_reward_is_written_down_as_zero(staked, monkeypatch):
    wallet, _ = staked
    node(monkeypatch, calls={"NominationPoolsApi_pending_rewards": u128(DOT)})
    ChainBalanceReader().read_receivables(NOW - 86400, [AssetLocation.DOT_BLOCKCHAIN])
    node(monkeypatch, calls={"NominationPoolsApi_pending_rewards": u128(0)})
    assert ChainBalanceReader().read_receivables(NOW, [AssetLocation.DOT_BLOCKCHAIN]) == 0
    assert JalReceivable().claims(wallet.id(), NOW) == []


@pytest.mark.parametrize("answer", [None, "0x", "0x00", "not hex"])
def test_failed_reward_reading_leaves_the_last_one_alone(staked, monkeypatch, answer):
    wallet, _ = staked
    node(monkeypatch, calls={"NominationPoolsApi_pending_rewards": u128(DOT)})
    ChainBalanceReader().read_receivables(NOW - 86400, [AssetLocation.DOT_BLOCKCHAIN])
    node(monkeypatch, calls={"NominationPoolsApi_pending_rewards": answer})
    assert ChainBalanceReader().read_receivables(NOW, [AssetLocation.DOT_BLOCKCHAIN]) == 0
    [claim] = JalReceivable().claims(wallet.id(), NOW)
    assert claim['amount'] == Decimal(1)
