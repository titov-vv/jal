import base64
import json
from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from tests.test_near_classifier import WALLET, FRIEND, NEAR, block, txn, receipt, refunds, fetch, payments, halted
from jal.constants import PredefinedAccountType, AssetLocation, AccountData
from jal.data_import.statement import JSF
from jal.db.account import JalAccountCreator, JalAccount
from jal.db.chain_balance import JalChainBalance
from jal.db.ledger import Ledger
from jal.db.staking import JalStakingBox
from jal.net.chain_balances import ChainBalanceReader

POOL = "example.poolv1.near"
FEE = 531_065_291_953_700_000_000


@pytest.fixture
def near_wallet(prepare_db):
    yield JalAccountCreator(currency_id=2, number='', name='NEAR wallet', investing=1, organization=1, precision=24,
                            account_type=PredefinedAccountType.Wallet, address=WALLET,
                            chain=AssetLocation.NEAR_BLOCKCHAIN).commit()


def event(height: int, tx_hash: str, kind: str, amount: int, pool: str = POOL) -> dict:
    return {"transaction_hash": tx_hash, "block": block(height), "type": kind, "amount": str(amount),
            "contract": pool}


def pool_call(height: int, tx_hash: str, method: str, deposit: int = 0, pool: str = POOL) -> list:
    return [txn(height, tx_hash, WALLET, pool, "FUNCTION_CALL", deposit, FEE, method=method),
            receipt(height + 1, tx_hash, WALLET, pool, deposit, action="FUNCTION_CALL", method=method),
            *refunds(height + 1, tx_hash)]


# The user's first stake, in its real shape: the pool's share rounding stakes 1 yocto less than was deposited
def stake(height: int, tx_hash: str, amount: int) -> list:
    return pool_call(height, tx_hash, "deposit_and_stake", amount) + \
        [event(height, tx_hash, "DEPOSIT", amount), event(height, tx_hash, "STAKE", amount - 1)]


def withdrawal(height: int, tx_hash: str, amount: int, method: str = "withdraw_all") -> list:
    return pool_call(height, tx_hash, method) + [receipt(height + 2, tx_hash, POOL, WALLET, amount),
                                                 event(height, tx_hash, "WITHDRAW", amount)]


def set_stakes(wallet, stakes: dict) -> None:
    wallet.set_data(AccountData.StakeAccounts, json.dumps({k: str(v) for k, v in stakes.items()}))


# ----------------------------------------------------------------------------------------------------------------------
def test_stake_is_a_transfer_to_the_pool(near_wallet):
    deposit = 28 * NEAR + NEAR // 2
    fetcher, data = fetch(near_wallet, *stake(200, "stake", deposit))
    [transfer] = data[JSF.TRANSFERS]
    assert transfer['account'] == [1, 0, 1] and transfer['counterparty_address'] == POOL
    assert transfer['withdrawal'] == Decimal("28.5") and transfer['fee'] == Decimal("0.0005310652919537")
    assert POOL in transfer['description']
    assert not data[JSF.ASSET_PAYMENTS] and not fetcher.skipped()
    assert fetcher._stakes == {POOL: deposit}


# A box at the pool's address takes the stake by itself, and the staked amount is remembered once imported
def test_stake_lands_in_the_box_of_the_pool(near_wallet):
    box = JalStakingBox.create(near_wallet, "NEAR staking", protocol="NEAR staking",
                               chain=AssetLocation.NEAR_BLOCKCHAIN, address=POOL)
    fetcher, data = fetch(near_wallet, *stake(200, "stake", 3 * NEAR))
    [transfer] = data[JSF.TRANSFERS]
    assert fetcher.mapped_id(JSF.ACCOUNTS, transfer['account'][1]) == box.id()
    fetcher.import_fetched()
    assert json.loads(JalAccount(near_wallet.id()).get_data(AccountData.StakeAccounts)) == {POOL: str(3 * NEAR)}


@pytest.mark.parametrize("method", ["unstake", "unstake_all", "stake", "stake_all"])
def test_pool_command_is_only_a_fee(near_wallet, method):
    kind = "UNSTAKE" if method.startswith("un") else "STAKE"
    _, data = fetch(near_wallet, *pool_call(300, "cmd", method), event(300, "cmd", kind, 30 * NEAR))
    assert not data[JSF.TRANSFERS]
    [fee] = payments(data, JSF.PAYMENT_GAS_FEE)
    assert fee['event'] == JSF.EVENT_POSITION_COMMAND and fee['description'] == f"{POOL}: {method}()"


# Principal first: the reward is only what comes back above everything that was put in
def test_withdrawal_splits_principal_and_reward(near_wallet):
    set_stakes(near_wallet, {POOL: 28 * NEAR + NEAR // 2})
    fetcher, data = fetch(near_wallet, *withdrawal(400, "out", 30 * NEAR + 1))
    [transfer] = data[JSF.TRANSFERS]
    assert transfer['account'] == [0, 1, 1] and transfer['counterparty_address'] == POOL
    assert transfer['withdrawal'] == Decimal("28.5") and transfer['fee'] == Decimal("0.0005310652919537")
    [reward] = payments(data, JSF.PAYMENT_STAKING_REWARD)
    assert reward['amount'] == Decimal("1.500000000000000000000001")
    assert fetcher._stakes == {}


def test_partial_withdrawal_is_all_principal(near_wallet):
    set_stakes(near_wallet, {POOL: 28 * NEAR})
    fetcher, data = fetch(near_wallet, *withdrawal(400, "out", 10 * NEAR, method="withdraw"))
    assert data[JSF.TRANSFERS][0]['withdrawal'] == Decimal(10)
    assert not payments(data, JSF.PAYMENT_STAKING_REWARD)
    assert fetcher._stakes == {POOL: 18 * NEAR}


# A deposit JAL never saw leaves nothing to measure a yield against: no income is invented out of it
def test_withdrawal_without_its_deposit_is_all_principal(near_wallet):
    fetcher, data = fetch(near_wallet, *withdrawal(400, "out", 30 * NEAR))
    assert data[JSF.TRANSFERS][0]['withdrawal'] == Decimal(30)
    assert not payments(data, JSF.PAYMENT_STAKING_REWARD)
    assert any("predates" in x for x in fetcher.skipped())


# A halt takes back what the halting transaction did to the staking state, and keeps what came before it
def test_halt_restores_the_staking_state(near_wallet):
    bad = stake(300, "bad", 2 * NEAR)
    bad[-2] = event(300, "bad", "DEPOSIT", NEAR)               # the event doesn't match the deposit
    fetcher, data = fetch(near_wallet, *stake(200, "good", 5 * NEAR), *bad)
    assert halted(fetcher) and len(data[JSF.TRANSFERS]) == 1
    assert fetcher._stakes == {POOL: 5 * NEAR}


@pytest.mark.parametrize("rows", [
    # a staking event of another pool
    pool_call(200, "t", "deposit_and_stake", NEAR) + [event(200, "t", "DEPOSIT", NEAR, pool="other.poolv1.near")],
    # a withdrawal that isn't the event's amount
    pool_call(200, "t", "withdraw_all") + [receipt(202, "t", POOL, WALLET, 2 * NEAR), event(200, "t", "WITHDRAW", NEAR)],
    # a withdrawal paid by somebody other than the pool
    pool_call(200, "t", "withdraw_all") + [receipt(202, "t", FRIEND, WALLET, NEAR), event(200, "t", "WITHDRAW", NEAR)],
    # a command that moved coins
    pool_call(200, "t", "unstake") + [receipt(202, "t", POOL, WALLET, NEAR), event(200, "t", "UNSTAKE", NEAR)],
    # a staking call to an account that isn't named as a pool
    pool_call(200, "t", "deposit_and_stake", NEAR, pool="pool-lookalike.near")
    + [event(200, "t", "DEPOSIT", NEAR, pool="pool-lookalike.near")],
    # a staking event in a plain transfer; staking events are read only when a receipt involves a pool
    [txn(200, "t", WALLET, FRIEND, "TRANSFER", NEAR, FEE), receipt(201, "t", WALLET, FRIEND, NEAR),
     receipt(201, "t", POOL, WALLET, 0), event(200, "t", "DEPOSIT", NEAR)],
    # a staking event in somebody else's transaction
    [receipt(200, "t", FRIEND, WALLET, NEAR), receipt(201, "t", POOL, WALLET, 0), event(200, "t", "WITHDRAW", NEAR)],
])
def test_unsupported_staking_shapes_halt(near_wallet, rows):
    fetcher, data = fetch(near_wallet, *rows)
    assert halted(fetcher) and not data[JSF.TRANSFERS] and not data[JSF.ASSET_PAYMENTS]


# ----------------------------------------------------------------------------------------------------------------------
# The box is valued by the pool's view of the wallet: staked plus unstaked, the 1 yocto of share rounding included
def test_box_is_read_from_the_pool(near_wallet, monkeypatch):
    box = JalStakingBox.create(near_wallet, "NEAR staking", protocol="NEAR staking",
                               chain=AssetLocation.NEAR_BLOCKCHAIN, address=POOL)
    fetcher, _ = fetch(near_wallet, receipt(100, "in", FRIEND, WALLET, 40 * NEAR), *stake(200, "stake", 28 * NEAR))
    fetcher.import_fetched()
    Ledger().rebuild(from_timestamp=0)
    asked = []

    def rpc(self, url, request):
        params = request['params']
        asked.append((params['account_id'], json.loads(base64.b64decode(params['args_base64']))))
        view = {"account_id": WALLET, "unstaked_balance": "1", "staked_balance": str(28 * NEAR + 7 * 10 ** 20 - 1),
                "can_withdraw": True}
        return {"jsonrpc": "2.0", "id": "jal", "result": {"result": list(json.dumps(view).encode())}}
    monkeypatch.setattr(ChainBalanceReader, "_post", rpc)
    now = 1_700_001_000
    assert ChainBalanceReader().read_staking_boxes(now) == 1
    assert asked == [(POOL, {"account_id": WALLET})]
    [holding] = box.holdings(now)
    assert holding['amount'] == Decimal(28)
    assert JalChainBalance().latest(box.id(), holding['asset'].id(), now)['amount'] == Decimal("28.0007")
