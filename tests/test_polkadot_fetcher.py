import json
from decimal import Decimal

import pytest
from bip_utils import SS58Encoder

from tests.fixtures import project_root, data_path, prepare_db
from jal.constants import PredefinedAccountType, AssetLocation, AccountData
from jal.data_import.statement import Statement_ImportError
from jal.db.account import JalAccountCreator
from jal.net.chain_fetchers import polkadot
from jal.net.chain_fetchers.polkadot import PolkadotFetcher, _HaltImport, _PAGE_SIZE

WALLET = SS58Encoder.Encode(bytes(range(32)), 0)          # made up
SENDER = SS58Encoder.Encode(bytes(range(1, 33)), 0)       # made up
FINAL = 1000


def element(height: int, element_id: str, extrinsic_index=2, extrinsic_hash=None, **fields) -> dict:
    return dict({"id": element_id, "blockNumber": height, "extrinsicIdx": extrinsic_index,
                 "extrinsicHash": extrinsic_hash, "timestamp": str(height * 6 + 7)}, **fields)


# Shapes of the two real elements of a wallet (the arrival of a swap and a pool join), recorded 2026-11-17
ARRIVAL = element(500, "500-6-to", extrinsic_hash="0xarrival",
                  transfer={"to": WALLET, "fee": "9207820", "from": SENDER, "amount": "220745833000",
                            "success": True, "eventIdx": 6})
JOIN = element(600, "600-2-extrinsic", extrinsic_hash="0xjoin",
               extrinsic={"fee": "7858149", "call": "join", "hash": "0xjoin", "module": "nominationPools",
                          "success": True})


# A fake indexer serving its elements in the block range asked for, oldest first, by offset
class FakeIndexer:
    def __init__(self, elements: list, indexed: int = FINAL, page_size: int = _PAGE_SIZE):
        self.elements = elements
        self.indexed = indexed
        self.page_size = page_size
        self.calls = []

    def query(self, query, variables):
        if "_metadata" in query:
            return {"_metadata": {"lastProcessedHeight": self.indexed}}
        self.calls.append(dict(variables))
        rows = sorted([x for x in self.elements if variables["floor"] <= x["blockNumber"] <= variables["top"]],
                      key=lambda x: (x["blockNumber"], x["id"]))
        start = variables["offset"]
        page = rows[start:start + min(variables["first"], self.page_size)]
        return {"historyElements": {"totalCount": len(rows), "nodes": page}}


@pytest.fixture
def dot_wallet(prepare_db):
    account = JalAccountCreator(currency_id=2, number='', name='DOT wallet', investing=1, organization=1,
                                account_type=PredefinedAccountType.Wallet, address=WALLET,
                                chain=AssetLocation.DOT_BLOCKCHAIN).commit()
    yield account


# A fetcher on the fake indexer whose classifier only records what it was given, halting at the keys in 'halt_at'
@pytest.fixture
def make_fetcher():
    def make(indexer: FakeIndexer, halt_at=(), final=FINAL):
        fetcher = PolkadotFetcher()
        fetcher._query = indexer.query
        fetcher._final_height = lambda: final
        fetcher.classified = []

        def classify(extrinsic):
            if extrinsic['key'] in halt_at:
                raise _HaltImport("test")
            fetcher.classified.append(extrinsic)
        fetcher._classify = classify
        return fetcher
    yield make


def run(fetcher, wallet) -> dict:
    fetcher.fetch(wallet)
    wallet.set_data(AccountData.SyncCursor, fetcher._new_cursor)
    return json.loads(fetcher._new_cursor)


# ----------------------------------------------------------------------------------------------------------------------
# Elements of one extrinsic come together; an element outside any extrinsic stands alone under its own id
def test_elements_are_grouped_by_extrinsic(make_fetcher, dot_wallet):
    reward = element(600, "600-9-reward", extrinsic_index=2, extrinsic_hash="0xjoin", poolReward={"amount": "5"})
    xcm = element(550, "550-3-to", extrinsic_index=None, transfer={"amount": "1"})
    fetcher = make_fetcher(FakeIndexer([JOIN, reward, ARRIVAL, xcm]))
    cursor = run(fetcher, dot_wallet)
    assert [x['key'] for x in fetcher.classified] == ["500-2", "550-3-to", "600-2"]
    arrival, delivered, join = fetcher.classified
    assert (arrival['hash'], arrival['height'], arrival['timestamp']) == ("0xarrival", 500, 3007)
    assert delivered['hash'] == "550-3-to"
    assert join['hash'] == "0xjoin" and [x['id'] for x in join['elements']] == ["600-2-extrinsic", "600-9-reward"]
    assert cursor == {'height': 600, 'hashes': ['600-2']}


# Several extrinsics in one block: the cursor lists each one imported, so a halt between them loses nothing
def test_halt_keeps_cursor_before_extrinsic(make_fetcher, dot_wallet):
    indexer = FakeIndexer([element(400, "400-1-to", 1), element(500, "500-1-to", 1), element(500, "500-4-to", 4),
                           element(600, "600-1-to", 1)])
    fetcher = make_fetcher(indexer, halt_at={"500-4"})
    assert run(fetcher, dot_wallet) == {'height': 500, 'hashes': ['500-1']}
    assert [x['key'] for x in fetcher.classified] == ["400-1", "500-1"]
    fetcher = make_fetcher(indexer)
    assert run(fetcher, dot_wallet) == {'height': 600, 'hashes': ['600-1']}
    assert [x['key'] for x in fetcher.classified] == ["500-4", "600-1"]


# The read starts at the cursor's block and ends at the lower of the final block and what the indexer has reached
def test_read_range_and_paging(make_fetcher, dot_wallet):
    dot_wallet.set_data(AccountData.SyncCursor, json.dumps({'height': 700, 'hashes': ['700-1']}))
    indexer = FakeIndexer([element(h, f"{h}-1-to", 1) for h in range(600, 1000, 10)], indexed=950, page_size=5)
    fetcher = make_fetcher(indexer)
    run(fetcher, dot_wallet)
    assert {(x['floor'], x['top']) for x in indexer.calls} == {(700, 950)}
    # The fake caps pages at 5 rows: a short page is not the end, 'totalCount' (26 rows in 700..950) is
    assert [x['offset'] for x in indexer.calls] == list(range(0, 26, 5))
    assert [x['key'] for x in fetcher.classified] == [f"{h}-1" for h in range(710, 960, 10)]


def test_full_pages_are_followed(make_fetcher, dot_wallet):
    indexer = FakeIndexer([element(h, f"{h}-1-to", 1) for h in range(1, 2 * _PAGE_SIZE + 2)])
    fetcher = make_fetcher(indexer)
    run(fetcher, dot_wallet)
    assert [x['offset'] for x in indexer.calls] == [0, _PAGE_SIZE, 2 * _PAGE_SIZE]
    assert len(fetcher.classified) == 2 * _PAGE_SIZE + 1


def test_unfinal_blocks_wait(make_fetcher, dot_wallet):
    indexer = FakeIndexer([element(FINAL, "a-1-to", 1), element(FINAL + 1, "b-1-to", 1)], indexed=FINAL + 1)
    fetcher = make_fetcher(indexer)
    assert run(fetcher, dot_wallet) == {'height': FINAL, 'hashes': [f'{FINAL}-1']}
    fetcher = make_fetcher(indexer, final=FINAL + 1)
    assert run(fetcher, dot_wallet) == {'height': FINAL + 1, 'hashes': [f'{FINAL + 1}-1']}


def test_invalid_address_refused(make_fetcher, dot_wallet):
    dot_wallet.set_data(AccountData.Address, SS58Encoder.Encode(bytes(range(32)), 42))
    with pytest.raises(Statement_ImportError):
        make_fetcher(FakeIndexer([])).fetch(dot_wallet)


def test_amounts_are_exact():
    assert PolkadotFetcher._dot(220745833000) == Decimal("22.0745833")
    assert PolkadotFetcher._dot(12345678 * 10 ** 10 + 1) == Decimal("12345678.0000000001")
    with pytest.raises(Statement_ImportError):
        PolkadotFetcher._planck("2.2e10")


# ----------------------------------------------------------------------------------------------------------------------
# Node answers at the join block, recorded 2026-11-17; none of them carries the wallet's address
ACCOUNT = "0x01000000010000000200000000000000437e088002000000000000000000000000b4f9e430000000000000000000000000" \
          "00000000000000000000000000000000000000000000000000000000000080"
MEMBER = "0x3600000000b4f9e43000000000000000000000000637bdd1843f2207000000000000000000"
POOL_NAME = "0x4501e29ca8204e6f76612057616c6c657420e29ca820e2809420506f6f6c20233120e28094206e6f766177616c6c65742e696f" \
            "20e28094205265636f6d6d656e6465642076616c696461746f727320f09f8e81"
BOND = "0x00b4f9e4300000000000000000000000"


# A fake node: storage by key prefix, runtime calls by name, block hashes made of the height
class FakeNode:
    def __init__(self, storage: dict, calls: dict):
        self.storage = storage
        self.calls = calls
        self.asked = []

    def rpc(self, method, params):
        self.asked.append((method, params))
        if method == "chain_getBlockHash":
            return f"0xblock{params[0]}"
        if method == "state_getStorage":
            return next((value for prefix, value in self.storage.items() if params[0][2:].startswith(prefix)), None)
        if method == "state_call":
            return self.calls[params[0]]
        raise AssertionError(method)


@pytest.fixture
def node_fetcher(dot_wallet):
    def make(storage: dict, calls: dict = None):
        fetcher = PolkadotFetcher()
        fetcher._account = dot_wallet
        fetcher.node = FakeNode(storage, calls or {})
        fetcher._rpc = fetcher.node.rpc
        return fetcher
    yield make


def test_balances_free_and_held(node_fetcher):
    fetcher = node_fetcher({polkadot._SYSTEM_ACCOUNT: ACCOUNT})
    assert fetcher._balances(600) == (10737974851, 210000000000)
    method, params = fetcher.node.asked[-1]
    assert params == ["0x" + polkadot._SYSTEM_ACCOUNT + fetcher._blake2_128_concat(bytes(range(32))), "0xblock600"]
    assert node_fetcher({})._balances(600) == (0, 0)


def test_pool_membership_and_name(node_fetcher):
    fetcher = node_fetcher({polkadot._POOL_MEMBERS: MEMBER, polkadot._POOL_METADATA: POOL_NAME})
    assert fetcher._pool_member(600) == (54, 210000000000)
    assert fetcher._pool_name(54, 600) == "✨ Nova Wallet ✨ — Pool #1 — novawallet.io — Recommended validators 🎁"
    assert node_fetcher({})._pool_member(600) is None
    assert node_fetcher({})._pool_name(54, 600) == ''


def test_runtime_calls(node_fetcher):
    fetcher = node_fetcher({}, {"NominationPoolsApi_member_total_balance": BOND,
                                "NominationPoolsApi_pending_rewards": "0x" + "00" * 16})
    assert fetcher._pool_bond(600) == 210000000000
    assert fetcher._pending_rewards(600) == 0
    assert fetcher.node.asked[-1][1] == ["NominationPoolsApi_pending_rewards", "0x" + bytes(range(32)).hex(),
                                         "0xblock600"]
    fetcher = node_fetcher({}, {"NominationPoolsApi_pending_rewards": "0x00"})
    with pytest.raises(Statement_ImportError):
        fetcher._pending_rewards(600)


# Key hashers against keys read from the live chain: a PoolMembers key, and pool 54's Metadata key
def test_storage_key_hashers():
    member = bytes.fromhex("a0135e8c81718eb259acb06810eaf0c771ebc036ec9775941a4bce968c7ea527")
    assert PolkadotFetcher._twox64_concat(member) == "000242917cd31423" + member.hex()
    assert PolkadotFetcher._twox64_concat((54).to_bytes(4, 'little')) == "0381a5fc457aa15c36000000"


def test_scale_compact():
    assert PolkadotFetcher._compact(bytes([0b00000100])) == (1, 1)
    assert PolkadotFetcher._compact(bytes.fromhex("4501")) == (81, 2)
    assert PolkadotFetcher._compact(bytes.fromhex("feffffff")) == (2 ** 30 - 1, 4)
    assert PolkadotFetcher._compact(bytes.fromhex("0300000040")) == (2 ** 30, 5)


# ----------------------------------------------------------------------------------------------------------------------
# A stand-in for WebRequest answering with the text given
class FakeRequest:
    POST_JSON = 'POST_JSON'
    answer = ''

    def __init__(self, operation, url, params=None, headers=None, binary=False, expected_errors=()):
        pass

    def wait(self, deadline=0):
        return True

    def data(self):
        return FakeRequest.answer


# A failed request, an error list or an unexpected envelope stops the fetch instead of reading as an empty history
def test_unexpected_answer_stops_fetch(monkeypatch, dot_wallet):
    monkeypatch.setattr(polkadot, "WebRequest", FakeRequest)
    fetcher = PolkadotFetcher()
    fetcher._account = dot_wallet
    for answer in ('', '[]', '{"data": null}',
                   '{"errors": [{"message": "canceling statement due to statement timeout"}], "data": {}}'):
        FakeRequest.answer = answer
        with pytest.raises(Statement_ImportError):
            fetcher._query(polkadot._HISTORY_QUERY, {})
    for answer in ('', '{"jsonrpc": "2.0", "id": 1, "error": {"code": -32601, "message": "Method not found"}}'):
        FakeRequest.answer = answer
        with pytest.raises(Statement_ImportError):
            fetcher._rpc("chain_getFinalizedHead", [])
