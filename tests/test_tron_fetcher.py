import json
from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from constants import PredefinedAccountType, AssetLocation, AccountData, PredefinedAsset, SymbolId, \
    TokenList, TokenListKind
from jal.data_import.statement import JSF
from jal.db.account import JalAccountCreator, JalAccount
from jal.db.asset import JalAsset
from jal.db.symbol import JalSymbol
from jal.db.settings import JalSettings
from jal.net.chain_fetchers.tron import TronFetcher
from jal.net.token_lists import TokenListProvider
from jal.db.token_blacklist import JalTokenBlacklist

# The address the fixtures were recorded for - a public wallet, never the address of a real user (see the note in
# tests/local_test_data.json.example on why an on-chain address must not be committed)
WALLET = "TMuA6YqfCeX8EhbfYEg5y7S4DqzSJireY9"
USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"


@pytest.fixture
def tron_wallet(prepare_db):
    JalSettings().setValue("ApiKey_TronGrid", "test-key")
    # A wallet receives real tokens from addresses it never dealt with before, and JAL has no quote for a token it
    # has never seen - which is exactly the shape of a dust airdrop. The allow-list is what tells the two apart, so
    # a realistic run has one loaded (Import / Load token lists in the application).
    TokenListProvider()._store(TokenList.COINGECKO_TRON_LIST, TokenListKind.Allow, AssetLocation.TRX_BLOCKCHAIN,
                               [{'address': USDT_CONTRACT, 'symbol': 'USDT', 'name': 'Tether USD'}])
    account = JalAccountCreator(currency_id=2, number='', name='Tron wallet', investing=1, organization=1,
                                account_type=PredefinedAccountType.Wallet, address=WALLET,
                                chain=AssetLocation.TRX_BLOCKCHAIN).commit()
    assert account.id() == 1
    yield account


# Replaces the network with the recorded TronGrid answers. Returns the fetcher plus the list of endpoints that
# were requested, so a test may assert on the paging/cursor parameters that were sent.
@pytest.fixture
def fetcher(tron_wallet, data_path, monkeypatch):
    calls = []

    def fake_pages(self, endpoint, params):
        calls.append((endpoint, dict(params)))
        name = "tron_trc20.json" if endpoint.endswith("trc20") else "tron_native.json"
        with open(data_path + name, 'r', encoding='utf-8') as f:
            records = json.load(f)['data']
        # The real API filters server-side by min_timestamp; the recorded answer is filtered here instead
        low = params.get('min_timestamp', 0)
        return [x for x in records if int(x.get('block_timestamp', 0)) >= low]

    monkeypatch.setattr(TronFetcher, "_get_pages", fake_pages)
    instance = TronFetcher()
    instance.calls = calls
    yield instance


def _transfers(data) -> list:
    return data[JSF.TRANSFERS]


# ----------------------------------------------------------------------------------------------------------------------
def test_fetch_builds_transfers(fetcher, tron_wallet):
    data = fetcher.fetch(tron_wallet)
    # 5 USDT transfers plus the native TRX transfers that survive the dust filter
    assert len(_transfers(data)) > 0
    for transfer in _transfers(data):
        assert transfer['withdrawal'] > Decimal('0')               # a real quantity moved
        # 'deposit' is the cost basis in the destination currency, which the fetcher cannot know - left 0 for the
        # user to complete once the counterparty account (and thus its currency) is chosen during import.
        assert transfer['deposit'] == Decimal('0')
        assert transfer['account'].count(0) == 1                   # exactly one side is outside JAL
        assert transfer['number']                                  # the tx hash is always recorded


def test_token_carries_contract_address(fetcher, tron_wallet):
    data = fetcher.fetch(tron_wallet)
    usdt = [a for a in data[JSF.ASSETS] if a['type'] == JSF.ASSET_CRYPTO and a[JSF.SYMBOLS][0]['symbol'] == 'USDT']
    assert len(usdt) == 1
    symbol = usdt[0][JSF.SYMBOLS][0]
    # The contract address identifies the token - the ticker is attacker-controlled and never trusted
    assert symbol['address'] == USDT_CONTRACT
    assert symbol['location'] == AssetLocation.TRX_BLOCKCHAIN


def test_gas_is_attached_to_outgoing_transfers(fetcher, tron_wallet):
    data = fetcher.fetch(tron_wallet)
    trx_symbols = [s['id'] for a in data[JSF.ASSETS] for s in a[JSF.SYMBOLS] if s['symbol'] == 'TRX']
    outgoing_with_fee = [t for t in _transfers(data) if t['account'][0] == 1 and t['fee'] > Decimal('0')]
    assert outgoing_with_fee, "at least one outgoing transfer paid gas"
    for transfer in outgoing_with_fee:
        # Gas is always burned in TRX, whatever asset moved
        assert transfer['fee_symbol'] in trx_symbols
        assert transfer['account'][2] == 1        # and always by the wallet being fetched
    # Incoming transfers never carry gas - the sender paid it
    assert all(t['fee'] == Decimal('0') for t in _transfers(data) if t['account'][0] == 0)


def test_unsupported_transactions_are_reported_not_dropped(fetcher, tron_wallet):
    fetcher.fetch(tron_wallet)
    skipped = fetcher.skipped()
    # Freezing, unfreezing and voting change no ownership, so they legitimately produce no operation - but they
    # are still counted, so an unimported transaction is never indistinguishable from an empty history.
    assert skipped
    assert any("staking lifecycle" in reason for reason in skipped)


def test_staking_rewards_are_imported(fetcher, tron_wallet):
    data = fetcher.fetch(tron_wallet)
    rewards = [p for p in data[JSF.ASSET_PAYMENTS] if p['type'] == JSF.PAYMENT_STAKING_REWARD]
    assert len(rewards) == 4                 # 4 WithdrawBalanceContract claims in the recorded history
    assert all(p['amount'] > Decimal('0') for p in rewards)


def test_gas_only_calls_become_gas_fees(fetcher, tron_wallet):
    data = fetcher.fetch(tron_wallet)
    gas = [p for p in data[JSF.ASSET_PAYMENTS] if p['type'] == JSF.PAYMENT_GAS_FEE]
    # The failed approve() moved nothing but still cost 9.478350 TRX of energy
    assert len(gas) == 1
    assert gas[0]['amount'] == Decimal('9.478350')
    assert "failed" in gas[0]['description'].lower()


def test_native_dust_is_filtered(fetcher, tron_wallet):
    data = fetcher.fetch(tron_wallet)
    trx_transfers = [t for t in _transfers(data)
                     if any(s['symbol'] == 'TRX' for a in data[JSF.ASSETS] for s in a[JSF.SYMBOLS]
                            if s['id'] == t['symbol'][0])]
    # The recorded history has incoming transfers of 1-7 sun (0.000001 TRX) - address-poisoning dust
    assert all(t['withdrawal'] >= Decimal('0.001') for t in trx_transfers if t['account'][0] == 0)
    assert any("dust" in reason for reason in fetcher.skipped())


def test_cursor_is_used_and_advanced(fetcher, tron_wallet):
    fetcher.fetch(tron_wallet)
    assert fetcher.calls[0][1]['min_timestamp'] == 0        # nothing fetched before, so the whole history
    assert fetcher.calls[0][1]['order_by'] == 'block_timestamp,asc'

    fetcher.import_fetched()
    cursor = JalAccount(1).get_data(AccountData.SyncCursor)
    assert cursor and int(cursor) > 0

    # A second run asks only for what happened after the stored position, and finds nothing new
    again = TronFetcher()
    again.calls = fetcher.calls
    data = again.fetch(JalAccount(1))
    assert again.calls[-1][1]['min_timestamp'] == int(cursor) + 1
    assert _transfers(data) == []


def test_import_creates_assets_with_address(fetcher, tron_wallet):
    fetcher.fetch(tron_wallet)
    fetcher.import_fetched()

    usdt = JalSymbol.find_by_identifier(SymbolId.TRX_ADDRESS, USDT_CONTRACT)
    assert usdt.id()
    assert usdt.symbol() == 'USDT'
    assert usdt.location() == AssetLocation.TRX_BLOCKCHAIN
    assert usdt.asset().type() == PredefinedAsset.Crypto


def test_second_import_is_idempotent(fetcher, tron_wallet):
    fetcher.fetch(tron_wallet)
    fetcher.import_fetched()
    first = len(JalAccount(1).dump_transfers())

    again = TronFetcher()
    again.fetch(JalAccount(1))
    again.import_fetched()
    # The cursor makes the second run see nothing, so no operation is duplicated
    assert len(JalAccount(1).dump_transfers()) == first


def test_unknown_unpriceable_token_is_quarantined(tron_wallet, data_path, monkeypatch):
    # The other side of the allow-list: a token nobody vouches for, arriving unsolicited from an unknown address
    # and with no price JAL can establish, is exactly what a dust airdrop looks like and must not become an asset.
    SCAM = "TXFBqBbqJommqZf7BV8NNYzePh97UmJodJ"      # a valid Tron address that no list mentions

    def fake_pages(self, endpoint, params):
        if not endpoint.endswith("trc20"):
            return []
        return [{
            "transaction_id": "deadbeef", "block_timestamp": 1758800892000,
            "from": "TLRwwokbyYiuB42e5BtmsB9KmebspmuAXn", "to": WALLET, "value": "1000000",
            "type": "Transfer",
            "token_info": {"symbol": "USDT", "address": SCAM, "decimals": 6, "name": "Tether USD"}
        }]

    monkeypatch.setattr(TronFetcher, "_get_pages", fake_pages)
    fetcher = TronFetcher()
    data = fetcher.fetch(tron_wallet)

    assert data[JSF.TRANSFERS] == []                                    # no operation
    assert data[JSF.ASSETS] == [] or all(a['type'] != JSF.ASSET_CRYPTO for a in data[JSF.ASSETS])
    assert JalTokenBlacklist.is_blacklisted(AssetLocation.TRX_BLOCKCHAIN, SCAM)   # recorded for the user to review
    assert any("dust" in reason or "spam" in reason for reason in fetcher.skipped())


def test_token_is_matched_by_address_not_by_ticker(fetcher, tron_wallet):
    # Anyone may deploy a contract calling itself 'USDT'. Importing must key on the contract address, so a second
    # token with the same ticker becomes its own asset instead of merging into the real one's position.
    fetcher.fetch(tron_wallet)
    fetcher.import_fetched()
    real = JalSymbol.find_by_identifier(SymbolId.TRX_ADDRESS, USDT_CONTRACT)
    assert real.id()

    IMPOSTOR = "TXFBqBbqJommqZf7BV8NNYzePh97UmJodJ"
    TokenListProvider()._store(TokenList.COINGECKO_TRON_LIST, TokenListKind.Allow, AssetLocation.TRX_BLOCKCHAIN,
                               [{'address': USDT_CONTRACT, 'symbol': 'USDT', 'name': 'Tether USD'},
                                {'address': IMPOSTOR, 'symbol': 'USDT', 'name': 'Tether USD'}])

    statement = TronFetcher()
    statement._account = JalAccount(1)
    statement._data = {JSF.ACCOUNTS: [], JSF.ASSETS: [], JSF.TRANSFERS: []}
    fake_asset = statement._token_asset_id('USDT', 'Tether USD', address=IMPOSTOR)
    statement.match_db_ids()
    # The impostor shares the ticker but not the address, so it must not be mapped onto the real USDT asset
    assert statement.mapped_id(JSF.ASSETS, fake_asset) != real.asset().id()


# ----------------------------------------------------------------------------------------------------------------------
# A blockchain reports absolute UTC time, but JAL stores and displays every timestamp as a naive local wall clock
# (now_ts() and every broker importer do the same). Restores the process timezone AND re-runs tzset() on teardown -
# time.tzset() mutates process-global state, so leaving it set would shift timestamps in every later test.
@pytest.fixture
def fixed_tz():
    import os, time
    saved = os.environ.get('TZ')
    os.environ['TZ'] = 'Etc/GMT-2'        # POSIX inverts the sign: this is a fixed UTC+2 zone, no DST
    time.tzset()
    yield 2 * 3600
    if saved is None:
        os.environ.pop('TZ', None)
    else:
        os.environ['TZ'] = saved
    time.tzset()


def test_local_timestamp_shifts_utc_to_local_wall_clock(fixed_tz):
    from datetime import datetime, timezone
    utc_epoch = 1758803292                                    # 2025-09-25 12:28:12 UTC
    stored = TronFetcher._local_timestamp(utc_epoch)
    # JAL renders every stored epoch in UTC, so the stored value must read back as the local wall clock (UTC+2)
    shown = datetime.fromtimestamp(stored, tz=timezone.utc)
    assert shown.strftime('%Y-%m-%d %H:%M:%S') == '2025-09-25 14:28:12'
    assert stored - utc_epoch == fixed_tz                     # shifted by exactly the local offset


def test_local_timestamp_zero_stays_zero():
    assert TronFetcher._local_timestamp(0) == 0               # an empty/absent block_timestamp is not shifted


def test_timestamp_of_matches_now_ts_convention(fixed_tz, prepare_db):
    # A Tron transaction and a manually-created operation at the same instant must land on the same stored value.
    from datetime import datetime, timezone
    from jal.db.helpers import now_ts
    instant = int(datetime.now(tz=timezone.utc).timestamp())
    record = {'block_timestamp': instant * 1000}              # the API reports milliseconds
    assert TronFetcher()._timestamp_of(record) == pytest.approx(now_ts(), abs=2)


def test_token_note_shows_both_parties_sender_first():
    assert TronFetcher._counterparty_note({'from': 'TSENDER', 'to': 'TRECEIVER'}) == 'TSENDER → TRECEIVER'


def test_native_note_shows_both_parties_sender_first():
    from jal.db.token_blacklist import tron_address_from_hex
    value = {'owner_address': '41ebd8dd5317713d254707c13840396f9aa8e3070e',
             'to_address': '4182dd6b9966724ae2fdc79b416c7588da67ff1b35'}
    sender = tron_address_from_hex(value['owner_address'])
    receiver = tron_address_from_hex(value['to_address'])
    assert TronFetcher._native_counterparty_note(value) == f"{sender} → {receiver}"
    assert TronFetcher._native_counterparty_note(value).startswith(sender)   # sender first, regardless of direction


def test_transfer_notes_carry_arrow(fetcher, tron_wallet):
    data = fetcher.fetch(tron_wallet)
    transfers_with_party = [t for t in _transfers(data) if t.get('description')]
    assert transfers_with_party                                              # at least one carried a counterparty
    for transfer in transfers_with_party:
        assert ' → ' in transfer['description']


# ----------------------------------------------------------------------------------------------------------------------
# Pre-fetch guard: a fetch against an empty token-list cache mis-classifies real tokens as spam, so ChainFetchers
# warns and downloads the lists first (and aborts if that fails). QMessageBox is replaced so nothing blocks on a
# dialog, and refresh() is stubbed so no network is touched.
class _RecordingBox:
    Ok = 0
    events = []

    def information(self, _parent, _title, text, *a):
        _RecordingBox.events.append(('info', text))

    def warning(self, _parent, _title, text, *a):
        _RecordingBox.events.append(('warn', text))


def _registry(provider):
    from types import SimpleNamespace
    from jal.net.chain_fetchers.fetchers import ChainFetchers
    return ChainFetchers(SimpleNamespace(token_lists=provider))


def test_is_empty_is_per_chain(prepare_db):
    provider = TokenListProvider()
    assert provider.is_empty()                                        # nothing loaded at all
    assert provider.is_empty(AssetLocation.TRX_BLOCKCHAIN)
    provider._store(TokenList.COINGECKO_TRON_LIST, TokenListKind.Allow, AssetLocation.TRX_BLOCKCHAIN,
                    [{'address': USDT_CONTRACT, 'symbol': 'USDT', 'name': 'Tether USD'}])
    assert not provider.is_empty(AssetLocation.TRX_BLOCKCHAIN)        # this chain now has a list
    assert provider.is_empty(AssetLocation.ETH_BLOCKCHAIN)            # a different chain is still empty
    assert not provider.is_empty()                                    # something is loaded somewhere


def test_ensure_token_lists_skips_download_when_present(prepare_db, monkeypatch):
    import jal.net.chain_fetchers.fetchers as fetchers_mod
    _RecordingBox.events = []
    provider = TokenListProvider()
    provider._store(TokenList.COINGECKO_TRON_LIST, TokenListKind.Allow, AssetLocation.TRX_BLOCKCHAIN,
                    [{'address': USDT_CONTRACT, 'symbol': 'USDT', 'name': 'Tether USD'}])
    refresh_calls = []
    monkeypatch.setattr(provider, 'refresh', lambda **kw: refresh_calls.append(kw))
    monkeypatch.setattr(fetchers_mod, 'QMessageBox', _RecordingBox)

    assert _registry(provider)._ensure_token_lists(AssetLocation.TRX_BLOCKCHAIN) is True
    assert refresh_calls == []                                        # no download when lists already present
    assert _RecordingBox.events == []                                 # and no dialog


def test_ensure_token_lists_downloads_when_empty(prepare_db, monkeypatch):
    import jal.net.chain_fetchers.fetchers as fetchers_mod
    _RecordingBox.events = []
    provider = TokenListProvider()
    assert provider.is_empty(AssetLocation.TRX_BLOCKCHAIN)

    def fake_refresh(location_id=None, force=False):
        provider._store(TokenList.COINGECKO_TRON_LIST, TokenListKind.Allow, location_id,
                        [{'address': USDT_CONTRACT, 'symbol': 'USDT', 'name': 'Tether USD'}])
        return 1
    monkeypatch.setattr(provider, 'refresh', fake_refresh)
    monkeypatch.setattr(fetchers_mod, 'QMessageBox', _RecordingBox)

    assert _registry(provider)._ensure_token_lists(AssetLocation.TRX_BLOCKCHAIN) is True
    assert not provider.is_empty(AssetLocation.TRX_BLOCKCHAIN)        # lists got loaded
    assert [e[0] for e in _RecordingBox.events] == ['info']          # informed once, no warning


def test_ensure_token_lists_aborts_when_download_fails(prepare_db, monkeypatch):
    import jal.net.chain_fetchers.fetchers as fetchers_mod
    _RecordingBox.events = []
    provider = TokenListProvider()
    monkeypatch.setattr(provider, 'refresh', lambda **kw: 0)          # every download failed / cancelled
    monkeypatch.setattr(fetchers_mod, 'QMessageBox', _RecordingBox)

    assert _registry(provider)._ensure_token_lists(AssetLocation.TRX_BLOCKCHAIN) is False
    assert [e[0] for e in _RecordingBox.events] == ['info', 'warn']   # informed, then warned that it aborted


# The import dialog that asks which account an unmatched counterparty maps to must show the amount that actually
# moved. For an incoming asset transfer the quantity lives in 'withdrawal' ('deposit' is the cost basis, left 0 by
# the fetcher), so a naive read of 'deposit' showed "Deposit of 0.00". Outgoing transfers read 'withdrawal' and
# were never affected. select_account() is intercepted to capture the prompt text (and to abort before a real
# selection is needed).
def test_incoming_transfer_prompt_shows_real_amount(fetcher, tron_wallet, monkeypatch):
    from jal.data_import.statement import Statement_ImportError
    fetcher.fetch(tron_wallet)
    prompts = []

    def capture(self, text, account_id, recent_account_id=0):
        prompts.append(text)
        raise Statement_ImportError("stop after capturing the prompt")

    monkeypatch.setattr(type(fetcher), "select_account", capture, raising=False)
    try:
        fetcher.import_fetched()
    except Statement_ImportError:
        pass

    deposit_prompts = [t for t in prompts if t.startswith("Deposit of")]
    assert deposit_prompts, "an incoming transfer from an unknown address should have prompted"
    for text in deposit_prompts:
        assert "Deposit of 0.00" not in text          # the cost-basis 0 must not be shown as the amount
    # at least one prompt shows a real, non-zero quantity
    assert any(not t.startswith("Deposit of 0.00") and t.startswith("Deposit of") for t in deposit_prompts)
