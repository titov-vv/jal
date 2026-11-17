import json
from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from jal.constants import PredefinedAccountType, AssetLocation, AccountData
from jal.data_import.statement import Statement_ImportError
from jal.db.account import JalAccountCreator
from jal.net.chain_fetchers import near
from jal.net.chain_fetchers.near import NearFetcher, _HaltImport, _LOOKBACK, _RATE_RETRIES, _REFUND_WAIT

WALLET = "example.near"
FINAL = 1000
MATURE = FINAL - _REFUND_WAIT


def row(height: int, tx_hash: str, **fields) -> dict:
    return dict({"transaction_hash": tx_hash,
                 "block": {"block_height": str(height), "block_timestamp": str(height * 10 ** 9 + 7)}}, **fields)


# A fake NearBlocks: {endpoint: rows}, served newest first in pages with an opaque 'next' token
class FakeNearBlocks:
    def __init__(self, lists: dict, page_size: int = 100):
        self.lists = {x: [] for x in near._LISTS}
        self.lists.update(lists)
        self.page_size = page_size
        self.calls = []

    def get(self, endpoint, params):
        self.calls.append((endpoint, dict(params)))
        rows = sorted(self.lists[endpoint], key=lambda x: -int(x['block']['block_height']))
        start = int(params.get("next", "0"))
        end = start + min(params["limit"], self.page_size)
        answer = {"data": rows[start:end], "meta": {}}
        if end < len(rows):
            answer["meta"]["next_page"] = str(end)
        return answer


@pytest.fixture
def near_wallet(prepare_db):
    account = JalAccountCreator(currency_id=2, number='', name='NEAR wallet', investing=1, organization=1,
                                account_type=PredefinedAccountType.Wallet, address=WALLET,
                                chain=AssetLocation.NEAR_BLOCKCHAIN).commit()
    yield account


# A fetcher on the fake chain whose classifier only records what it was given, halting at the hashes in 'halt_at'
@pytest.fixture
def make_fetcher():
    def make(nearblocks: FakeNearBlocks, halt_at=(), final=FINAL):
        fetcher = NearFetcher()
        fetcher._get = nearblocks.get
        fetcher._final_height = lambda: final
        fetcher.classified = []

        def classify(transaction):
            if transaction['hash'] in halt_at:
                raise _HaltImport("test")
            fetcher.classified.append(transaction)
        fetcher._classify = classify
        return fetcher
    yield make


def run(fetcher, wallet) -> dict:
    fetcher.fetch(wallet)
    wallet.set_data(AccountData.SyncCursor, fetcher._new_cursor)
    return json.loads(fetcher._new_cursor)


# ----------------------------------------------------------------------------------------------------------------------
# Rows of the three lists come together per transaction, which stands at its lowest height and earliest time
def test_rows_are_grouped_by_transaction(make_fetcher, near_wallet):
    nearblocks = FakeNearBlocks({
        "txns": [row(500, "stake")],
        "receipts": [row(501, "stake", predecessor_account_id="system"),
                     row(502, "stake", predecessor_account_id="system"),
                     row(498, "incoming", predecessor_account_id="friend.near")],
        "staking-txns": [row(501, "stake", type="DEPOSIT"), row(501, "stake", type="STAKE")]})
    fetcher = make_fetcher(nearblocks)
    cursor = run(fetcher, near_wallet)
    assert [x['hash'] for x in fetcher.classified] == ["incoming", "stake"]
    incoming, stake = fetcher.classified
    assert (incoming['height'], incoming['timestamp']) == (498, 498)
    assert len(incoming['receipts']) == 1 and not incoming['txns'] and not incoming['staking']
    assert (stake['height'], stake['timestamp']) == (500, 500)
    assert (len(stake['txns']), len(stake['receipts']), len(stake['staking'])) == (1, 2, 2)
    assert cursor == {'height': 500, 'hashes': ['stake']}


# A refund that lands after its transaction was imported is recognized as that transaction's, not as a new one
def test_late_refund_of_imported_transaction(make_fetcher, near_wallet):
    nearblocks = FakeNearBlocks({"txns": [row(500, "a")]})
    run(make_fetcher(nearblocks), near_wallet)
    nearblocks.lists["receipts"] = [row(503, "a", predecessor_account_id="system"), row(600, "b")]
    fetcher = make_fetcher(nearblocks)
    assert run(fetcher, near_wallet) == {'height': 600, 'hashes': ['b']}
    assert [x['hash'] for x in fetcher.classified] == ["b"]


# A transaction too close to the final block waits: its refunds may not have landed yet
def test_recent_transaction_waits(make_fetcher, near_wallet):
    nearblocks = FakeNearBlocks({"txns": [row(MATURE, "old"), row(MATURE + 1, "new")]})
    fetcher = make_fetcher(nearblocks)
    assert run(fetcher, near_wallet) == {'height': MATURE, 'hashes': ['old']}
    assert [x['hash'] for x in fetcher.classified] == ["old"]
    assert list(fetcher._skipped) and "too recent" in list(fetcher._skipped)[0]
    fetcher = make_fetcher(nearblocks, final=FINAL + 1)
    assert run(fetcher, near_wallet) == {'height': MATURE + 1, 'hashes': ['new']}
    assert [x['hash'] for x in fetcher.classified] == ["new"]


# Several transactions in one block: the cursor lists each one imported, so a halt between them loses nothing
def test_halt_keeps_cursor_before_transaction(make_fetcher, near_wallet):
    nearblocks = FakeNearBlocks({"txns": [row(400, "a"), row(500, "b1"), row(500, "b2"), row(600, "c")]})
    fetcher = make_fetcher(nearblocks, halt_at={"b2"})
    assert run(fetcher, near_wallet) == {'height': 500, 'hashes': ['b1']}
    assert [x['hash'] for x in fetcher.classified] == ["a", "b1"]
    fetcher = make_fetcher(nearblocks)
    assert run(fetcher, near_wallet) == {'height': 600, 'hashes': ['c']}
    assert [x['hash'] for x in fetcher.classified] == ["b2", "c"]


# Paging walks back only as far as the cursor less the lookback, following the opaque 'next' token
def test_paging_stops_below_lookback(make_fetcher, near_wallet):
    near_wallet.set_data(AccountData.SyncCursor, json.dumps({'height': 800, 'hashes': ['x']}))
    nearblocks = FakeNearBlocks({"txns": [row(h, f"t{h}") for h in range(600, 900, 10)]}, page_size=5)
    fetcher = make_fetcher(nearblocks)
    run(fetcher, near_wallet)
    txns_calls = [params for endpoint, params in nearblocks.calls if endpoint == "txns"]
    assert txns_calls[0] == {"limit": 100} and txns_calls[1] == {"limit": 100, "next": "5"}
    # Pages of 5 from block 890 down: the 4th ends at 700, the floor itself, so only the 5th (690..650) is below it
    assert 800 - _LOOKBACK == 700
    assert len(txns_calls) == 5
    # t800 stands at the cursor's height but isn't among the hashes imported there
    assert [x['hash'] for x in fetcher.classified] == [f"t{h}" for h in range(800, 900, 10)]


def test_invalid_account_refused(make_fetcher, near_wallet):
    near_wallet.set_data(AccountData.Address, "Not.A.Near.Account")
    with pytest.raises(Statement_ImportError):
        make_fetcher(FakeNearBlocks({})).fetch(near_wallet)


def test_amounts_are_exact():
    yocto = 12345678 * 10 ** 24 + 1
    assert NearFetcher._near(yocto) == Decimal("12345678.000000000000000000000001")
    assert NearFetcher._yocto("30000000000000000000000001") == 30000000000000000000000001
    with pytest.raises(Statement_ImportError):
        NearFetcher._yocto("3e+25")


# ----------------------------------------------------------------------------------------------------------------------
# A stand-in for WebRequest answering with the statuses given, one per request
class FakeRequest:
    GET = 'GET'
    statuses = []
    answer = '{"data": [], "meta": {}}'
    made = 0

    def __init__(self, operation, url, params=None, headers=None, binary=False, expected_errors=()):
        FakeRequest.made += 1
        self._status = FakeRequest.statuses.pop(0)

    def wait(self, deadline=0):
        return True

    def status(self):
        return self._status

    def data(self):
        return FakeRequest.answer if self._status == 200 else ''


@pytest.fixture
def fake_web(monkeypatch, near_wallet):
    monkeypatch.setattr(near, "WebRequest", FakeRequest)
    FakeRequest.made = 0
    FakeRequest.answer = '{"data": [], "meta": {}}'
    fetcher = NearFetcher()
    fetcher._account = near_wallet
    fetcher.pauses = []
    fetcher._pause = lambda seconds: fetcher.pauses.append(seconds)
    yield fetcher


def test_rate_limit_waits_and_retries(fake_web):
    FakeRequest.statuses = [429, 429, 200]
    assert fake_web._get("txns", {"limit": 100})['data'] == []
    assert FakeRequest.made == 3
    assert near._RATE_WAIT in fake_web.pauses


def test_rate_limit_gives_up(fake_web):
    FakeRequest.statuses = [429] * (_RATE_RETRIES + 1)
    with pytest.raises(Statement_ImportError):
        fake_web._get("txns", {"limit": 100})


# A failed request or an unexpected envelope stops the fetch instead of reading as an empty history
def test_unexpected_answer_stops_fetch(fake_web):
    for answer in ('', '[]', '{"data": null, "errors": [{"message": "Server Error"}]}'):
        FakeRequest.statuses = [200]
        FakeRequest.answer = answer
        with pytest.raises(Statement_ImportError):
            fake_web._get("txns", {"limit": 100})
