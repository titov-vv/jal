from decimal import Decimal

import pytest
from bip_utils import SS58Encoder

from tests.fixtures import project_root, data_path, prepare_db
from jal.constants import PredefinedAccountType, AssetLocation
from jal.data_import.statement import JSF
from jal.db.account import JalAccountCreator
from jal.net.chain_fetchers.polkadot import PolkadotFetcher

WALLET = SS58Encoder.Encode(bytes(range(32)), 0)          # made up
FRIEND = SS58Encoder.Encode(bytes(range(1, 33)), 0)       # made up
FINAL = 10_000
DOT = 10 ** 10
FEE = 7_858_149                                           # the real fee of a pool join


def element(height: int, element_id: str, index=2, tx_hash="0xhash", **fields) -> dict:
    return dict({"id": element_id, "blockNumber": height, "extrinsicIdx": index, "extrinsicHash": tx_hash,
                 "timestamp": str(1_700_000_000 + height)}, **fields)


def transfer(sender: str, receiver: str, amount: int, fee=0, success=True, event=6) -> dict:
    return {"from": sender, "to": receiver, "amount": str(amount), "fee": str(fee), "success": success,
            "eventIdx": event if success else -1}


def call(module: str, name: str, fee=FEE, success=True) -> dict:
    return {"module": module, "call": name, "fee": str(fee), "success": success, "hash": "0xhash"}


# The elements of a transfer as the indexer writes them: one per side that is the wallet, and the signer's extrinsic
def sent(height: int, receiver: str, amount: int, fee=FEE) -> list:
    data = transfer(WALLET, receiver, amount, fee)
    elements = [element(height, f"{height}-6-from", transfer=data),
                element(height, f"{height}-2-extrinsic", extrinsic=call("balances", "transferKeepAlive", fee))]
    if receiver == WALLET:
        elements.append(element(height, f"{height}-6-to", transfer=data))
    return elements


def received(height: int, sender: str, amount: int) -> list:
    return [element(height, f"{height}-6-to", transfer=transfer(sender, WALLET, amount, fee=9_207_820))]


@pytest.fixture
def dot_wallet(prepare_db):
    yield JalAccountCreator(currency_id=2, number='', name='DOT wallet', investing=1, organization=1, precision=10,
                            account_type=PredefinedAccountType.Wallet, address=WALLET,
                            chain=AssetLocation.DOT_BLOCKCHAIN).commit()


# Fetches the given elements; the node's balance moves by 'deltas' {height: plancks}, or by what they explain
def fetch(wallet, elements, deltas=None) -> tuple:
    fetcher = PolkadotFetcher()
    fetcher._query = lambda query, variables: {"historyElements": {"totalCount": len(elements), "nodes": elements}} \
        if "historyElements" in query else {"_metadata": {"lastProcessedHeight": FINAL}}
    fetcher._final_height = lambda: FINAL
    fetcher._account = wallet
    if deltas is None:
        deltas = {}
        for extrinsic in fetcher._extrinsics(elements):
            deltas[extrinsic['height']] = deltas.get(extrinsic['height'], 0) + fetcher._net(extrinsic)
    fetcher.balance_reads = []

    def balances(height):
        fetcher.balance_reads.append(height)
        return 1000 * DOT + sum(v for h, v in deltas.items() if h <= height), 0
    fetcher._balances = balances
    return fetcher, fetcher.fetch(wallet)


def payments(data, payment_type) -> list:
    return [x for x in data[JSF.ASSET_PAYMENTS] if x['type'] == payment_type]


def halted(fetcher) -> bool:
    return any("import stopped" in x for x in fetcher.skipped())


# ----------------------------------------------------------------------------------------------------------------------
# The real arrival of 18 Feb 2026: its element carries the sender's fee, which is not the wallet's
def test_incoming_transfer(dot_wallet):
    fetcher, data = fetch(dot_wallet, received(100, FRIEND, 220_745_833_000))
    [incoming] = data[JSF.TRANSFERS]
    assert incoming['account'] == [0, 1, 1]
    assert incoming['withdrawal'] == Decimal("22.0745833")
    assert incoming['fee'] == Decimal('0')
    assert incoming['counterparty_address'] == FRIEND
    assert incoming['number'] == "0xhash" and incoming['timestamp'] == 1_700_000_100
    assert not fetcher.skipped()
    assert fetcher.balance_reads == [100, 99]


def test_incoming_dust(dot_wallet):
    _, data = fetch(dot_wallet, received(100, FRIEND, 1))
    assert not data[JSF.TRANSFERS]
    [dust] = payments(data, JSF.PAYMENT_DUST_ATTACK)
    assert dust['amount'] == Decimal("0.0000000001")


# A transfer the wallet signed has two elements, both with the fee: it is taken once
def test_outgoing_transfer_carries_the_fee(dot_wallet):
    fetcher, data = fetch(dot_wallet, sent(100, FRIEND, 5 * DOT))
    [outgoing] = data[JSF.TRANSFERS]
    assert outgoing['account'] == [1, 0, 1]
    assert outgoing['withdrawal'] == Decimal(5)
    assert outgoing['fee'] == Decimal("0.0007858149") and 'fee_symbol' in outgoing
    assert outgoing['counterparty_address'] == FRIEND
    assert not data[JSF.ASSET_PAYMENTS] and not fetcher.skipped()


def test_transfer_to_itself_is_only_a_fee(dot_wallet):
    _, data = fetch(dot_wallet, sent(100, WALLET, DOT))
    assert not data[JSF.TRANSFERS]
    [fee] = payments(data, JSF.PAYMENT_GAS_FEE)
    assert fee['amount'] == Decimal("0.0007858149") and fee['event'] == JSF.EVENT_NO_OP


# A failed transfer call is written as transfer elements with 'success' false and no extrinsic element
def test_failed_transfer_is_only_a_fee(dot_wallet):
    data = transfer(WALLET, FRIEND, 5 * DOT, fee=FEE, success=False)
    _, fetched = fetch(dot_wallet, [element(100, "100-2-from", transfer=data), element(100, "100-2-to", transfer=data)])
    assert not fetched[JSF.TRANSFERS]
    [fee] = payments(fetched, JSF.PAYMENT_GAS_FEE)
    assert fee['amount'] == Decimal("0.0007858149") and fee['event'] == JSF.EVENT_FAILED


def test_failed_extrinsic_is_only_a_fee(dot_wallet):
    _, data = fetch(dot_wallet, [element(100, "100-2-extrinsic", extrinsic=call("nominationPools", "join",
                                                                                success=False))])
    [fee] = payments(data, JSF.PAYMENT_GAS_FEE)
    assert fee['event'] == JSF.EVENT_FAILED and "nominationPools.join" in fee['description']


# Several extrinsics in one block are checked against the block's balance change together
def test_block_balance_covers_all_its_extrinsics(dot_wallet):
    elements = received(100, FRIEND, 3 * DOT) + [dict(x, extrinsicIdx=5, extrinsicHash="0xout")
                                                  for x in sent(100, FRIEND, DOT)]
    fetcher, data = fetch(dot_wallet, elements, deltas={100: 2 * DOT - FEE})
    assert len(data[JSF.TRANSFERS]) == 2 and not fetcher.skipped()
    assert fetcher.balance_reads == [100, 99]


# A balance change the history doesn't explain (an XCM arrival, a fee paid in another asset) stops the import there
def test_unexplained_balance_change_halts(dot_wallet):
    fetcher, data = fetch(dot_wallet, received(100, FRIEND, 3 * DOT) + sent(200, FRIEND, DOT),
                          deltas={100: 3 * DOT, 200: -DOT})
    assert len(data[JSF.TRANSFERS]) == 1 and halted(fetcher)
    assert any("0.0007858149" not in x and "-1" in x for x in fetcher.skipped())


@pytest.mark.parametrize("elements", [
    # a pool call (not classified yet)
    [element(100, "100-2-extrinsic", extrinsic=call("nominationPools", "join"))],
    # any other call
    [element(100, "100-2-extrinsic", extrinsic=call("system", "remark"))],
    # an Asset Hub token
    [element(100, "100-6-to", assetTransfer=dict(transfer(FRIEND, WALLET, 5), assetId="1984"))],
    # a swap, a staking reward, a pool reward
    [element(100, "100-6-from", swap={"assetIdIn": "native", "amountIn": "1"})],
    [element(100, "100-6-reward", index=None, reward={"amount": "1", "isReward": True})],
    [element(100, "100-6-reward", index=None, poolReward={"amount": "1", "isReward": True, "poolId": 54})],
    # the wallet's coins leaving in an extrinsic it didn't sign (a proxy, a multisig)
    [element(100, "100-6-from", transfer=transfer(WALLET, FRIEND, DOT))],
    # a transfer extrinsic that moved somebody else's coins
    [element(100, "100-2-extrinsic", extrinsic=call("balances", "transferKeepAlive")),
     element(100, "100-6-to", transfer=transfer(FRIEND, WALLET, DOT))],
    # two transfers to the wallet in one extrinsic
    received(100, FRIEND, DOT) + [element(100, "100-7-to", transfer=transfer(FRIEND, WALLET, DOT, event=7))],
])
def test_unsupported_shapes_halt(dot_wallet, elements):
    fetcher, data = fetch(dot_wallet, elements)
    assert halted(fetcher) and not data[JSF.TRANSFERS] and not data[JSF.ASSET_PAYMENTS]
