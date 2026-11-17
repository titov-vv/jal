from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from jal.constants import PredefinedAccountType, AssetLocation
from jal.data_import.statement import JSF
from jal.db.account import JalAccountCreator, JalAccount
from jal.db.db import JalDB
from jal.db.ledger import Ledger
from jal.net.chain_fetchers.near import NearFetcher, _LISTS

WALLET = "example.near"
FRIEND = "friend.near"
FINAL = 10_000
NEAR = 10 ** 24


def block(height: int) -> dict:
    return {"block_height": str(height), "block_timestamp": str((1_700_000_000 + height) * 10 ** 9 + 123)}


def txn(height: int, tx_hash: str, signer: str, receiver: str, action: str, deposit: int, fee: int,
        method=None, status=True) -> dict:
    return {"transaction_hash": tx_hash, "block": block(height), "signer_account_id": signer,
            "receiver_account_id": receiver, "actions": [{"action": action, "method": method}],
            "actions_agg": {"deposit": str(deposit)}, "outcomes": {"status": status},
            "outcomes_agg": {"transaction_fee": str(fee)}}


def receipt(height: int, tx_hash: str, sender: str, receiver: str, deposit: int, action="TRANSFER", method=None,
            status=True) -> dict:
    return {"transaction_hash": tx_hash, "block": block(height), "predecessor_account_id": sender,
            "receiver_account_id": receiver, "actions": [{"action": action, "method": method}],
            "actions_agg": {"deposit": str(deposit)}, "outcome": {"status": status}}


# Gas refunds as the runtime sends them, one or two blocks after the transaction
def refunds(height: int, tx_hash: str) -> list:
    return [receipt(height + 1, tx_hash, "system", WALLET, 9_455_496_618_969_300_000_000),
            receipt(height + 2, tx_hash, "system", WALLET, 189_249_412_500_000_000_000)]


@pytest.fixture
def near_wallet(prepare_db):
    yield JalAccountCreator(currency_id=2, number='', name='NEAR wallet', investing=1, organization=1, precision=24,
                            account_type=PredefinedAccountType.Wallet, address=WALLET,
                            chain=AssetLocation.NEAR_BLOCKCHAIN).commit()


# Fetches the given rows from a fake NearBlocks that knows nothing else
def fetch(wallet, *rows) -> tuple:
    lists = {endpoint: [] for endpoint in _LISTS}
    for row in rows:
        endpoint = "staking-txns" if 'type' in row else "txns" if 'signer_account_id' in row else "receipts"
        lists[endpoint].append(row)
    fetcher = NearFetcher()
    fetcher._get = lambda endpoint, params: {"data": lists[endpoint], "meta": {}}
    fetcher._final_height = lambda: FINAL
    return fetcher, fetcher.fetch(wallet)


def payments(data, payment_type) -> list:
    return [x for x in data[JSF.ASSET_PAYMENTS] if x['type'] == payment_type]


def halted(fetcher) -> bool:
    return any("import stopped" in x for x in fetcher.skipped())


# ----------------------------------------------------------------------------------------------------------------------
# The shape of a cross-chain arrival: somebody else's transaction with one transfer receipt to the wallet
def test_incoming_transfer(near_wallet):
    amount = 31_018_734_060_000_000_000_000_001
    fetcher, data = fetch(near_wallet, txn(100, "in", FRIEND, WALLET, "TRANSFER", amount, 834_989_537_500_000_000_000),
                          receipt(101, "in", FRIEND, WALLET, amount))
    [transfer] = data[JSF.TRANSFERS]
    assert transfer['account'] == [0, 1, 1]
    assert transfer['withdrawal'] == Decimal("31.018734060000000000000001")
    assert transfer['fee'] == Decimal('0')                  # the sender paid it
    assert transfer['counterparty_address'] == FRIEND
    assert transfer['number'] == "in" and transfer['timestamp'] == 1_700_000_100
    assert not fetcher.skipped()


def test_incoming_from_several_senders(near_wallet):
    _, data = fetch(near_wallet, receipt(100, "in", FRIEND, WALLET, 2 * NEAR),
                    receipt(101, "in", "other.near", WALLET, NEAR))
    [transfer] = data[JSF.TRANSFERS]
    assert transfer['withdrawal'] == Decimal(3) and 'counterparty_address' not in transfer
    assert FRIEND in transfer['description'] and "other.near" in transfer['description']


def test_outgoing_transfer_carries_the_fee(near_wallet):
    fee = 834_989_537_500_000_000_000
    fetcher, data = fetch(near_wallet, txn(100, "out", WALLET, FRIEND, "TRANSFER", 5 * NEAR, fee),
                          receipt(101, "out", WALLET, FRIEND, 5 * NEAR), *refunds(101, "out"))
    [transfer] = data[JSF.TRANSFERS]
    assert transfer['account'] == [1, 0, 1]
    assert transfer['withdrawal'] == Decimal(5)
    assert transfer['fee'] == Decimal("0.0008349895375") and 'fee_symbol' in transfer
    assert transfer['counterparty_address'] == FRIEND
    assert not data[JSF.ASSET_PAYMENTS] and not fetcher.skipped()


def test_transfer_to_itself_is_only_a_fee(near_wallet):
    _, data = fetch(near_wallet, txn(100, "self", WALLET, WALLET, "TRANSFER", NEAR, 10 ** 21),
                    receipt(101, "self", WALLET, WALLET, NEAR))
    assert not data[JSF.TRANSFERS]
    [fee] = payments(data, JSF.PAYMENT_GAS_FEE)
    assert fee['amount'] == Decimal("0.001") and fee['event'] == JSF.EVENT_NO_OP


def test_access_key_change_is_only_a_fee(near_wallet):
    _, data = fetch(near_wallet, txn(100, "key", WALLET, WALLET, "ADD_KEY", 0, 10 ** 21),
                    receipt(101, "key", WALLET, WALLET, 0, action="ADD_KEY"))
    [fee] = payments(data, JSF.PAYMENT_GAS_FEE)
    assert fee['event'] == JSF.EVENT_AUTHORIZATION


def test_failed_transfer_is_only_a_fee(near_wallet):
    _, data = fetch(near_wallet, txn(100, "fail", WALLET, "nobody.near", "TRANSFER", 5 * NEAR, 10 ** 21, status=False),
                    receipt(101, "fail", WALLET, "nobody.near", 5 * NEAR, status=False),
                    receipt(102, "fail", "system", WALLET, 5 * NEAR), *refunds(102, "fail"))
    assert not data[JSF.TRANSFERS]
    [fee] = payments(data, JSF.PAYMENT_GAS_FEE)
    assert fee['amount'] == Decimal("0.001") and fee['event'] == JSF.EVENT_FAILED


# Without the deposit's own refund receipt the failure may have kept some of it, which only the user can tell
def test_failed_transfer_without_its_refund_halts(near_wallet):
    fetcher, data = fetch(near_wallet, txn(100, "fail", WALLET, "nobody.near", "TRANSFER", 5 * NEAR, 10 ** 21,
                                           status=False), *refunds(101, "fail"))
    assert halted(fetcher) and not data[JSF.ASSET_PAYMENTS]


@pytest.mark.parametrize("rows", [
    # a contract call
    [txn(100, "t", WALLET, "app.near", "FUNCTION_CALL", 0, 10 ** 21, method="ft_transfer"),
     receipt(101, "t", WALLET, "app.near", 0, action="FUNCTION_CALL", method="ft_transfer")],
    # the deposits on the wallet's receipts don't make up the transaction's
    [txn(100, "t", WALLET, FRIEND, "TRANSFER", 5 * NEAR, 10 ** 21), receipt(101, "t", WALLET, FRIEND, 4 * NEAR)],
    # coins coming back to the wallet in its own transaction
    [txn(100, "t", WALLET, FRIEND, "TRANSFER", 5 * NEAR, 10 ** 21), receipt(101, "t", WALLET, FRIEND, 5 * NEAR),
     receipt(102, "t", FRIEND, WALLET, NEAR)],
    # a refund in somebody else's transaction
    [receipt(100, "t", FRIEND, WALLET, NEAR), receipt(101, "t", "system", WALLET, NEAR)],
    # somebody calling the wallet as a contract
    [receipt(100, "t", FRIEND, WALLET, NEAR, action="FUNCTION_CALL", method="anything")],
])
def test_unsupported_shapes_halt(near_wallet, rows):
    fetcher, data = fetch(near_wallet, *rows)
    assert halted(fetcher) and not data[JSF.TRANSFERS] and not data[JSF.ASSET_PAYMENTS]


# All 24 decimals of a NEAR amount survive the import and the ledger of a precision-24 wallet. 9999 NEAR is the
# largest whole part that fits: the ledger rounds in the default 28-digit Decimal context (Ledger.appendTransaction).
def test_amount_keeps_every_digit_through_import(near_wallet):
    amount = 9_999 * NEAR + 1
    fetcher, _ = fetch(near_wallet, receipt(100, "in", FRIEND, WALLET, amount))
    fetcher.import_fetched()
    expected = Decimal("9999.000000000000000000000001")
    [stored] = JalDB._read_to_list("SELECT withdrawal FROM transfers WHERE number='in'")
    assert Decimal(stored) == expected
    Ledger().rebuild(from_timestamp=0)
    [asset_id] = JalDB._read_to_list("SELECT DISTINCT asset_id FROM ledger WHERE account_id=:a",
                                     [(":a", near_wallet.id())])
    assert JalAccount(near_wallet.id()).get_asset_amount(2 ** 31, asset_id) == expected
