from types import SimpleNamespace

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from constants import PredefinedAccountType, AssetLocation, AccountData
from jal.db.account import JalAccount, JalAccountCreator
from jal.net.chain_fetchers.fetcher import ChainFetcher
from jal.net.chain_fetchers.fetchers import ChainFetchers

# 'Stop' during a blockchain fetch. A fetch may only be given up on while it is READING the chain - between the two
# halves of a wallet (import_into_db() and the sync cursor that follows it) an interruption would either lose the
# operations that were fetched or move the cursor past operations that were never stored. These tests pin down where
# the interruption is taken and, just as importantly, where it isn't.

# Two published BIP84 test-vector addresses, so nothing here belongs to anybody
ADDRESS_1 = "bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu"
ADDRESS_2 = "bc1qnjg0jd8228aq7egyzacy8cys3knf9xvrerkf9g"


# Stands in for a WebRequest: it reports "not finished yet" for a few slices of the waiting loop, which is where a
# fetch that is stopped notices it. 'on_slice' is the user pressing the button during one of them.
class _SlowRequest:
    def __init__(self, slices=4, on_slice=None, at=2):
        self._left = slices
        self._on_slice = on_slice
        self._at = at

    def wait(self, deadline=None) -> bool:
        self._left -= 1
        if self._on_slice is not None and self._left == self._at:
            self._on_slice()
        return self._left <= 0


# A fetcher that touches no network: it waits the way a real one does, then reports an empty history. BTC is chosen
# because that chain needs no token lists, so ChainFetchers.load() reaches the fetch without any stubbing.
class _FakeFetcher(ChainFetcher):
    name = 'Fake chain'
    location_id = AssetLocation.BTC_BLOCKCHAIN
    native_symbol = 'BTC'
    native_name = 'Bitcoin'
    fetched = []           # names of the accounts whose fetch was entered, in order
    imported = []          # ... and of those that reached import_fetched()
    interrupt = None       # callable that presses 'Stop' while the first wallet is being read
    interrupt_on_import = None    # ... or while it is being imported

    def _fetch(self) -> str:
        _FakeFetcher.fetched.append(self._account.name())
        hook = _FakeFetcher.interrupt if len(_FakeFetcher.fetched) == 1 else None
        self._wait_for(_SlowRequest(on_slice=hook))
        return f"cursor-{self._account.name()}"

    def import_fetched(self) -> dict:
        _FakeFetcher.imported.append(self._account.name())
        if _FakeFetcher.interrupt_on_import is not None and len(_FakeFetcher.imported) == 1:
            _FakeFetcher.interrupt_on_import()
        return super().import_fetched()


@pytest.fixture
def wallets(prepare_db):
    accounts = []
    for i, address in enumerate((ADDRESS_1, ADDRESS_2), start=1):
        accounts.append(JalAccountCreator(currency_id=2, number='', name=f'BTC wallet {i}', investing=1,
                                          organization=1, account_type=PredefinedAccountType.Wallet,
                                          address=address, chain=AssetLocation.BTC_BLOCKCHAIN).commit())
    yield accounts


@pytest.fixture
def registry(wallets, monkeypatch):
    _FakeFetcher.fetched = []
    _FakeFetcher.imported = []
    _FakeFetcher.interrupt = None
    _FakeFetcher.interrupt_on_import = None
    fetchers = ChainFetchers(None)
    fetchers.items = [{'name': 'Fake chain', 'module': SimpleNamespace(FakeFetcher=_FakeFetcher),
                       'loader_class': 'FakeFetcher', 'location_id': _FakeFetcher.location_id, 'icon': ''}]
    # Both wallets are fetched without asking, and the checks that follow a run are only recorded, not run
    monkeypatch.setattr(fetchers, '_select_wallets', lambda name, accounts: accounts)
    fetchers.checks = []
    for check in ('_settle_transfers', '_absorb_rebase_residue', '_audit_swaps'):
        monkeypatch.setattr(fetchers, check, lambda name=check: fetchers.checks.append(name))
    yield fetchers


def _load(fetchers):
    fetchers.load(SimpleNamespace(data=lambda: 0))


# The sync cursor as the database holds it now. It is read through a fresh account object on purpose: JalAccount
# caches its attributes per instance, so the one the test created still shows what it saw when it was made.
def _cursor(account) -> str:
    return JalAccount(account.id()).get_data(AccountData.SyncCursor) or ''


# ----------------------------------------------------------------------------------------------------------------------
def test_a_fetch_that_is_not_stopped_reads_every_wallet(registry, wallets):
    _load(registry)
    assert _FakeFetcher.fetched == ['BTC wallet 1', 'BTC wallet 2']
    assert _FakeFetcher.imported == ['BTC wallet 1', 'BTC wallet 2']
    assert _cursor(wallets[0]) == 'cursor-BTC wallet 1'
    assert _cursor(wallets[1]) == 'cursor-BTC wallet 2'
    assert registry.checks == ['_settle_transfers', '_absorb_rebase_residue', '_audit_swaps']


def test_stop_while_the_chain_is_being_read_abandons_that_wallet_and_the_rest_of_the_run(registry, wallets):
    _FakeFetcher.interrupt = registry.on_cancel      # pressed while the first wallet is being read
    _load(registry)
    assert _FakeFetcher.fetched == ['BTC wallet 1']  # the second wallet was never started ...
    assert _FakeFetcher.imported == []               # ... and the first one was not imported
    # Nothing was written for it, so its next fetch starts where this one did
    assert _cursor(wallets[0]) == ''
    assert _cursor(wallets[1]) == ''


def test_stop_during_an_import_lets_that_import_finish_and_stops_before_the_next_wallet(registry, wallets):
    _FakeFetcher.interrupt_on_import = registry.on_cancel
    _load(registry)
    # The wallet being imported is carried through to the end - its operations and its cursor stay in step ...
    assert _FakeFetcher.imported == ['BTC wallet 1']
    assert _cursor(wallets[0]) == 'cursor-BTC wallet 1'
    # ... and only then is the run stopped, so the second wallet is left untouched
    assert _FakeFetcher.fetched == ['BTC wallet 1']
    assert _cursor(wallets[1]) == ''


def test_a_stopped_run_does_not_go_on_to_the_checks_that_follow_it(registry):
    _FakeFetcher.interrupt_on_import = registry.on_cancel
    _load(registry)
    assert registry.checks == []


def test_the_next_run_is_not_stopped_by_the_previous_one(registry, wallets):
    _FakeFetcher.interrupt = registry.on_cancel
    _load(registry)
    assert _FakeFetcher.fetched == ['BTC wallet 1']
    _FakeFetcher.fetched = []
    _FakeFetcher.interrupt = None
    _load(registry)
    assert _FakeFetcher.fetched == ['BTC wallet 1', 'BTC wallet 2']


def test_on_cancel_reaches_the_fetcher_that_is_running_now(registry):
    fetcher = _FakeFetcher()
    registry._fetcher = fetcher
    registry.on_cancel()
    assert fetcher._cancelled
    with pytest.raises(KeyboardInterrupt):
        fetcher._wait_for(_SlowRequest())


def test_a_fetcher_nobody_stopped_waits_to_the_end(registry):
    fetcher = _FakeFetcher()
    request = _SlowRequest(slices=3)
    fetcher._wait_for(request)     # returns instead of raising
    assert request._left <= 0      # ... and only once the request was really over
