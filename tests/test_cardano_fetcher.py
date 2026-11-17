import json

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from jal.constants import PredefinedAccountType, AssetLocation, AccountData
from jal.data_import.statement import Statement_ImportError
from jal.db.account import JalAccountCreator
from jal.net.chain_fetchers import cardano
from jal.net.chain_fetchers.cardano import CardanoFetcher, _HaltImport, _BODY_LIMIT, _CONFIRMATIONS, _TX_INFO_FLAGS

# Stake address of the CIP-0019 test-vector mnemonic (tests/test_cardano_keys.py) - nobody's wallet
STAKE_ADDRESS = "stake1uyevw2xnsc0pvn9t9r9c7qryfqfeerchgrlm3ea2nefr9hqxdekzz"
TIP = 1000


def tx_hash(n: int) -> str:
    return f"{n:064x}"


# A fake chain: {hash: block height}, with the block index within a block given by the order of insertion
class FakeKoios:
    def __init__(self, transactions: dict, page_size: int = 1000):
        self.transactions = transactions
        self.page_size = page_size
        self.calls = []
        self.unknown = set()     # hashes tx_info stays silent about

    def get(self, endpoint, params):
        self.calls.append((endpoint, dict(params)))
        if endpoint == "tip":
            return [{"block_height": TIP}]
        assert endpoint == "account_txs" and params["_stake_address"] == STAKE_ADDRESS
        listed = sorted(((h, b) for h, b in self.transactions.items() if b >= params.get("_after_block_height", 0)),
                        key=lambda x: (x[1], x[0]))
        rows = [{"tx_hash": h, "block_height": b, "block_time": b * 20} for h, b in listed]
        return rows[params["offset"]:params["offset"] + self.page_size]

    def post(self, endpoint, body):
        self.calls.append((endpoint, body))
        assert endpoint == "tx_info" and len(json.dumps(body)) <= _BODY_LIMIT
        assert {k: v for k, v in body.items() if k != "_tx_hashes"} == _TX_INFO_FLAGS
        index = {h: i for i, h in enumerate(self.transactions)}
        return [{"tx_hash": h, "block_height": self.transactions[h], "tx_block_index": index[h]}
                for h in body["_tx_hashes"] if h not in self.unknown]


@pytest.fixture
def ada_wallet(prepare_db):
    account = JalAccountCreator(currency_id=2, number='', name='ADA wallet', investing=1, organization=1,
                                account_type=PredefinedAccountType.Wallet, address=STAKE_ADDRESS,
                                chain=AssetLocation.ADA_BLOCKCHAIN).commit()
    yield account


# A fetcher on the fake chain whose classifier only records what it was given, halting at the hashes in 'halt_at'
@pytest.fixture
def make_fetcher():
    def make(koios: FakeKoios, halt_at=()):
        fetcher = CardanoFetcher()
        fetcher._get, fetcher._post = koios.get, koios.post
        fetcher.classified = []

        def classify(transaction):
            if transaction['tx_hash'] in halt_at:
                raise _HaltImport("test")
            fetcher.classified.append(transaction['tx_hash'])
        fetcher._classify = classify
        return fetcher
    yield make


def run(fetcher, wallet) -> dict:
    fetcher.fetch(wallet)
    wallet.set_data(AccountData.SyncCursor, fetcher._new_cursor)
    return json.loads(fetcher._new_cursor)


# ----------------------------------------------------------------------------------------------------------------------
def test_history_is_classified_oldest_first(make_fetcher, ada_wallet):
    chain = {tx_hash(3): 30, tx_hash(1): 10, tx_hash(2): 20, tx_hash(5): 20}
    fetcher = make_fetcher(FakeKoios(chain))
    cursor = run(fetcher, ada_wallet)
    # by block, then by the position within the block - not by hash
    assert fetcher.classified == [tx_hash(1), tx_hash(2), tx_hash(5), tx_hash(3)]
    assert cursor == {'height': 30, 'hashes': [tx_hash(3)]}


def test_account_key_is_queried_by_its_stake_address(make_fetcher, prepare_db):
    key = "acct_xvk1eame4ge0x5yrwpuqs5eyw89kfmjpgfkfh02xzdx6c2k9k2swcr5clf0u634tm82x6nv2j750x3j7938g70ya4k0lv6p" \
          "r59s7etw2vpqgfmule"
    wallet = JalAccountCreator(currency_id=2, number='', name='ADA key', investing=1, organization=1,
                               account_type=PredefinedAccountType.Wallet, address=key,
                               chain=AssetLocation.ADA_BLOCKCHAIN).commit()
    fetcher = make_fetcher(FakeKoios({tx_hash(1): 10}))
    run(fetcher, wallet)                                   # FakeKoios asserts the stake address it is asked for
    assert fetcher.classified == [tx_hash(1)]


# The cursor block is asked for again (the API includes it); what was imported in it is not classified twice
def test_second_fetch_resumes_inside_the_cursor_block(make_fetcher, ada_wallet):
    chain = {tx_hash(1): 10, tx_hash(2): 20}
    koios = FakeKoios(chain)
    run(make_fetcher(koios), ada_wallet)
    chain[tx_hash(3)] = 20                                 # a later transaction of the same block, and a new block
    chain[tx_hash(4)] = 40
    fetcher = make_fetcher(koios)
    cursor = run(fetcher, ada_wallet)
    assert [x for x in koios.calls if x[0] == "account_txs"][-1][1]["_after_block_height"] == 20
    assert fetcher.classified == [tx_hash(3), tx_hash(4)]
    assert cursor == {'height': 40, 'hashes': [tx_hash(4)]}


def test_halt_keeps_the_cursor_before_it(make_fetcher, ada_wallet):
    chain = {tx_hash(1): 10, tx_hash(2): 20, tx_hash(3): 20, tx_hash(4): 30}
    fetcher = make_fetcher(FakeKoios(chain), halt_at={tx_hash(3)})
    cursor = run(fetcher, ada_wallet)
    assert fetcher.classified == [tx_hash(1), tx_hash(2)]
    assert cursor == {'height': 20, 'hashes': [tx_hash(2)]}
    assert any("unsupported transaction" in reason for reason in fetcher.skipped())
    retry = make_fetcher(FakeKoios(chain))                 # the next fetch starts at the halted transaction
    run(retry, ada_wallet)
    assert retry.classified == [tx_hash(3), tx_hash(4)]


def test_recent_transactions_wait(make_fetcher, ada_wallet):
    chain = {tx_hash(1): TIP - _CONFIRMATIONS, tx_hash(2): TIP - _CONFIRMATIONS + 1}
    fetcher = make_fetcher(FakeKoios(chain))
    cursor = run(fetcher, ada_wallet)
    assert fetcher.classified == [tx_hash(1)]
    assert cursor['height'] == TIP - _CONFIRMATIONS
    assert any("too recent" in reason for reason in fetcher.skipped())


def test_long_history_is_paged_and_batched(make_fetcher, ada_wallet, monkeypatch):
    monkeypatch.setattr(cardano, "_PAGE_SIZE", 7)
    chain = {tx_hash(n): 10 + n for n in range(1, 31)}
    koios = FakeKoios(chain, page_size=7)
    fetcher = make_fetcher(koios)
    run(fetcher, ada_wallet)
    assert fetcher.classified == [tx_hash(n) for n in range(1, 31)]
    assert len([x for x in koios.calls if x[0] == "account_txs"]) == 5           # 7+7+7+7+2
    assert len([x for x in koios.calls if x[0] == "tx_info"]) > 1                # FakeKoios checks each body size


def test_missing_details_stop_the_fetch(make_fetcher, ada_wallet):
    koios = FakeKoios({tx_hash(1): 10, tx_hash(2): 20})
    koios.unknown = {tx_hash(2)}
    fetcher = make_fetcher(koios)
    with pytest.raises(Statement_ImportError):
        fetcher.fetch(ada_wallet)


# WebRequest answers '' for an HTTP error (Koios answers a malformed stake address with 500)
class FailedRequest:
    GET, POST_JSON = 1, 2

    def __init__(self, *args, **kwargs):
        pass

    def wait(self, *args):
        return True

    def data(self):
        return ''


def test_error_answer_stops_the_fetch(monkeypatch, ada_wallet):
    monkeypatch.setattr(cardano, "WebRequest", FailedRequest)
    with pytest.raises(Statement_ImportError):
        CardanoFetcher().fetch(ada_wallet)
