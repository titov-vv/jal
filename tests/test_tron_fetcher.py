import json
from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from constants import PredefinedAccountType, AssetLocation, AccountData, PredefinedAsset, SymbolId, \
    TokenList, TokenListKind
from jal.data_import.statement import JSF
from jal.db.account import JalAccountCreator, JalAccount
from jal.db.asset import JalAsset, JalAssetCreator
from jal.db.symbol import JalSymbol
from jal.db.db import JalDB
from jal.db.settings import JalSettings
from jal.net.chain_fetchers.tron import TronFetcher, _METHOD_TRANSFER
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


def test_native_dust_is_recorded_as_dust_attack(fetcher, tron_wallet):
    data = fetcher.fetch(tron_wallet)
    trx_transfers = [t for t in _transfers(data)
                     if any(s['symbol'] == 'TRX' for a in data[JSF.ASSETS] for s in a[JSF.SYMBOLS]
                            if s['id'] == t['symbol'][0])]
    # The recorded history has incoming transfers of 1-7 sun (well under 0.00001 TRX) - address-poisoning dust,
    # alongside real incoming transfers of tens of TRX. The dust never becomes an ordinary Transfer...
    assert all(t['withdrawal'] >= Decimal('1') for t in trx_transfers if t['account'][0] == 0)
    # ...it is recorded as a DustAttack payment instead, so the balance it moved is still reconciled.
    dust = [p for p in data[JSF.ASSET_PAYMENTS] if p['type'] == JSF.PAYMENT_DUST_ATTACK]
    assert len(dust) == 5                     # the five sub-1-TRX incoming transfers in the recorded history
    assert all(Decimal('0') < p['amount'] < Decimal('0.00001') for p in dust)


# The rule is judged on the RAW COIN AMOUNT against the chain's own threshold, never on a fiat value - unlike the
# old value-based rule, this needs no price data and so is never accidentally inert.
#
# The bounds are derived from the threshold in force instead of being written out as numbers. A literal here
# restates TronFetcher.native_dust_threshold, and goes on asserting the old figure once that default is retuned or
# the user edits the 'DustThreshold_TRX' setting - which is exactly how this test came to disagree with the code it
# covers. What is worth pinning down is the rule: below the bound is dust, the bound itself is not, and a known
# counterparty is never dust at any amount.
def test_is_native_dust_judged_by_raw_amount(fetcher):
    threshold = fetcher._native_dust_threshold()
    assert threshold > Decimal('0'), "this chain must ship a dust threshold, or nothing below can mean anything"
    assert fetcher._is_native_dust(threshold / 10, known_counterparty=False)
    assert fetcher._is_native_dust(threshold - threshold / 1000, known_counterparty=False)
    assert not fetcher._is_native_dust(threshold, known_counterparty=False)   # the bound itself is not dust
    assert not fetcher._is_native_dust(threshold * 10, known_counterparty=False)
    # A transfer between two wallets of the same person is never an unsolicited airdrop, however small
    assert not fetcher._is_native_dust(threshold / 10, known_counterparty=True)


# A dust payment must reach the ledger even though the wallet's very first fetch has no TRX asset or quote of its
# own yet - the zero-basis fallback in AssetPayment.price() is what makes that safe (see the discussion that
# replaced the old value-based dust rule: requiring a quote is exactly what used to make dust detection inert).
def test_dust_attack_reaches_the_database_without_a_price(fetcher, tron_wallet):
    from jal.db.operations import AssetPayment
    fetcher.fetch(tron_wallet)
    fetcher.import_fetched()
    assert JalAsset.find({'symbol': 'TRX', 'type': PredefinedAsset.Crypto}).id() != 0   # created by the import itself
    dust = AssetPayment.get_list(tron_wallet.id(), subtype=AssetPayment.DustAttack)
    assert len(dust) == 5
    assert all(p.amount() > Decimal('0') for p in dust)      # the raw TRX quantity is still recorded correctly
    assert all(p.price() == Decimal('0') for p in dust)      # ...but opened at a zero basis, having no quote to price it


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


# A movement whose far side is an outside address is imported with that side left unknown - the whole quantity still
# reaches the ledger, on the one account that is known, and the import runs through instead of stopping to ask which
# account the outside address stands for.
def test_transfer_with_an_outside_address_is_imported_as_a_pending_leg(fetcher, tron_wallet):
    data = fetcher.fetch(tron_wallet)
    unresolved = [t for t in _transfers(data) if t['account'].count(0) == 1]
    assert unresolved, "the fixture must contain a transfer with an outside address"

    fetcher.import_fetched()

    pending = JalDB._read("SELECT COUNT(*) FROM transfers "
                          "WHERE withdrawal_account IS NULL OR deposit_account IS NULL")
    assert int(pending) == len(unresolved)


# ----------------------------------------------------------------------------------------------------------------------
# A counterparty that is another wallet of the user's own is filled in as the far account of the transfer, instead of
# being left unknown for the user to pick. Both ends of such a transfer are known before the import starts.
# These addresses appear in the recorded history as the far side of a USDT movement.
COUNTERPARTY_OUT = "TUkXLMefWss528dGbu47ivdQ8kRfqxdueT"    # the wallet sends USDT to it
COUNTERPARTY_IN = "TLRwwokbyYiuB42e5BtmsB9KmebspmuAXn"     # ... and receives USDT from it


def _second_wallet(address, name='Tron wallet 2', chain=AssetLocation.TRX_BLOCKCHAIN, currency_id=2):
    return JalAccountCreator(currency_id=currency_id, number='', name=name, investing=1, organization=1,
                             account_type=PredefinedAccountType.Wallet, address=address, chain=chain).commit()


def test_own_counterparty_is_resolved_into_the_transfer(fetcher, tron_wallet):
    other = _second_wallet(COUNTERPARTY_OUT)
    data = fetcher.fetch(tron_wallet)
    internal = [t for t in _transfers(data) if fetcher.mapped_id(JSF.ACCOUNTS, t['account'][1]) == other.id()]
    assert internal, "the transfer to the second wallet should name it as the destination"
    for transfer in internal:
        assert transfer['account'][0] == 1                 # sent by the fetched wallet
        assert transfer['account'].count(0) == 0           # ... and neither side is left for the user to pick
        assert transfer.get('description', '') == ''       # both ends are already known, the address note is noise
    # A transfer with an outside address is unaffected - its far side is still unknown
    assert any(t['account'].count(0) == 1 for t in _transfers(data))


def test_own_counterparty_is_resolved_for_incoming_transfers(fetcher, tron_wallet):
    other = _second_wallet(COUNTERPARTY_IN)
    data = fetcher.fetch(tron_wallet)
    internal = [t for t in _transfers(data) if fetcher.mapped_id(JSF.ACCOUNTS, t['account'][0]) == other.id()]
    assert internal, "the transfer from the second wallet should name it as the source"
    for transfer in internal:
        assert transfer['account'][1] == 1                 # received by the fetched wallet
        assert transfer['account'].count(0) == 0
        assert transfer.get('description', '') == ''       # both ends are already known, the address note is noise


def test_resolved_counterparty_reaches_the_db_complete(fetcher, tron_wallet):
    other = _second_wallet(COUNTERPARTY_OUT)
    data = fetcher.fetch(tron_wallet)
    internal = [t for t in _transfers(data) if t['account'].count(0) == 0]
    assert internal, "the fixture must contain a transfer between the two own wallets"

    fetcher.import_fetched()

    # The transfer is booked on the second wallet as well, and with both of its ends named it is not pending
    assert len(JalAccount(other.id()).dump_transfers()) == len(internal)
    pending = JalDB._read("SELECT COUNT(*) FROM transfers WHERE (withdrawal_account=:id OR deposit_account=:id) "
                          "AND (withdrawal_account IS NULL OR deposit_account IS NULL)", [(":id", other.id())])
    assert int(pending) == 0


def test_counterparty_in_another_currency_is_left_for_the_user(fetcher, tron_wallet):
    # An asset transfer between two currencies takes its destination cost basis from 'deposit', which the fetcher
    # leaves at 0 - and a 0 there wipes the basis of every transferred lot. Such a counterparty is not filled in
    # silently: it stays the user's decision until the basis can be computed.
    _second_wallet(COUNTERPARTY_OUT, currency_id=1)      # RUB, while the fetched wallet is kept in USD
    data = fetcher.fetch(tron_wallet)
    assert all(t['account'].count(0) == 1 for t in _transfers(data))


def test_ambiguous_counterparty_is_left_for_the_user(fetcher, tron_wallet):
    # Two accounts of one chain sharing an address: nothing here can tell which of them the transfer belongs to,
    # so it stays unresolved and the import asks, rather than guessing.
    _second_wallet(COUNTERPARTY_OUT, name='Tron wallet 2')
    _second_wallet(COUNTERPARTY_OUT, name='Tron wallet 3')
    data = fetcher.fetch(tron_wallet)
    assert all(t['account'].count(0) == 1 for t in _transfers(data))


# ----------------------------------------------------------------------------------------------------------------------
# One on-chain transfer between two wallets of the user's own is seen by the fetch of the wallet that sent it AND by
# the fetch of the wallet that received it. Both describe the same movement, so it must reach the database once.
_TX_HASH = 'a' * 64
_TX_TIME = 1758900000000        # ms, as TronGrid reports it
_FEE_ACCOUNT, _FEE = 8, 9       # column positions of the 'transfers' table rows that dump_transfers() returns


def _trc20(sender, receiver, value='1000000', tx_hash=_TX_HASH):
    return {'transaction_id': tx_hash, 'block_timestamp': _TX_TIME, 'from': sender, 'to': receiver, 'value': value,
            'token_info': {'address': USDT_CONTRACT, 'symbol': 'USDT', 'name': 'Tether USD', 'decimals': 6}}


# The contract call that carried the token transfer. It moves nothing by itself (the amounts come from the token
# endpoint) but it is where the gas the sender burned is reported.
def _trigger(fee=1100000, tx_hash=_TX_HASH):
    return {'txID': tx_hash, 'block_timestamp': _TX_TIME, 'ret': [{'fee': fee, 'contractRet': 'SUCCESS'}],
            'raw_data': {'contract': [{'type': 'TriggerSmartContract',
                                       'parameter': {'value': {'data': _METHOD_TRANSFER + '0' * 128}}}]}}


# Runs a fresh TronFetcher for 'wallet' against a hand-built history and imports what it fetched.
def _import_history(wallet, monkeypatch, tokens, native):
    def fake_pages(self, endpoint, params):
        records = tokens if endpoint.endswith('trc20') else native
        return [x for x in records if int(x.get('block_timestamp', 0)) >= params.get('min_timestamp', 0)]

    monkeypatch.setattr(TronFetcher, "_get_pages", fake_pages)
    instance = TronFetcher()
    instance.fetch(wallet)
    instance.import_fetched()
    return instance


def test_transfer_seen_from_both_wallets_is_imported_once(tron_wallet, monkeypatch):
    other = _second_wallet(COUNTERPARTY_OUT)
    history = ([_trc20(WALLET, COUNTERPARTY_OUT)], [_trigger()])
    _import_history(tron_wallet, monkeypatch, *history)
    assert len(JalAccount(tron_wallet.id()).dump_transfers()) == 1
    # The same transaction, now fetched from the wallet that received it - the very same movement, not a second one
    _import_history(other, monkeypatch, *history)
    assert len(JalAccount(other.id()).dump_transfers()) == 1
    assert len(JalAccount(tron_wallet.id()).dump_transfers()) == 1


def test_gas_of_the_sender_reaches_a_transfer_imported_from_the_receiver_first(tron_wallet, monkeypatch):
    # The receiving side knows nothing about the gas - only the sender pays it. Whichever side is imported first,
    # the fee must end up on the stored transfer: it burns a real quantity of TRX that the ledger has to account for.
    other = _second_wallet(COUNTERPARTY_OUT)
    history = ([_trc20(WALLET, COUNTERPARTY_OUT)], [_trigger()])
    _import_history(other, monkeypatch, *history)          # the receiver first, so the transfer is stored without gas
    stored = JalAccount(other.id()).dump_transfers()
    assert len(stored) == 1
    assert not stored[0][_FEE]                              # nothing was charged yet

    _import_history(tron_wallet, monkeypatch, *history)     # ... and now the side that paid the gas
    stored = JalAccount(other.id()).dump_transfers()
    assert len(stored) == 1                                 # still one movement
    assert Decimal(stored[0][_FEE]) == Decimal('1.1')       # with the gas the sender burned
    assert stored[0][_FEE_ACCOUNT] == tron_wallet.id()      # charged to the wallet that sent it


def test_refetching_a_history_creates_no_duplicates(tron_wallet, monkeypatch):
    # The sync cursor normally stops a wallet's history from being fetched twice. When it is reset - or when the
    # very same transaction arrives from the other wallet's fetch - what is already recorded must not be stored again.
    _second_wallet(COUNTERPARTY_OUT)
    history = ([_trc20(WALLET, COUNTERPARTY_OUT)], [_trigger()])
    _import_history(tron_wallet, monkeypatch, *history)
    first = len(JalAccount(tron_wallet.id()).dump_transfers())
    JalAccount(tron_wallet.id()).set_data(AccountData.SyncCursor, '')
    _import_history(JalAccount(tron_wallet.id()), monkeypatch, *history)
    assert len(JalAccount(tron_wallet.id()).dump_transfers()) == first


def test_several_legs_of_one_transaction_are_all_imported(tron_wallet, monkeypatch):
    # One transaction may pay the same address more than once. Those legs share the tx hash, the accounts and the
    # timestamp - everything the duplicate check compares except the quantity - and each is a movement of its own.
    _second_wallet(COUNTERPARTY_OUT)
    history = ([_trc20(WALLET, COUNTERPARTY_OUT, value='1000000'),
                _trc20(WALLET, COUNTERPARTY_OUT, value='2000000')], [_trigger()])
    _import_history(tron_wallet, monkeypatch, *history)
    assert len(JalAccount(tron_wallet.id()).dump_transfers()) == 2


# ----------------------------------------------------------------------------------------------------------------------
# The native coin has no contract address, so an import resolves it by ticker alone. The two wallets of a transfer
# are fetched one after the other, and the first fetch adds a listing of the coin - so the second one has to keep
# resolving the ticker onto the very same asset. Failing that it created a second asset for the coin, the transfer
# it imported named a different symbol than the one already stored, and the two ends of one on-chain transfer
# stopped looking like the same movement - which stored it twice.
_SENDER_HEX = '41ebd8dd5317713d254707c13840396f9aa8e3070e'      # hex form, as raw transaction data reports it
_RECEIVER_HEX = '4182dd6b9966724ae2fdc79b416c7588da67ff1b35'   # the address of the 'tron_wallet' fixture


def _native(owner_hex, to_hex, amount, fee=1100000, tx_hash=_TX_HASH):
    return {'txID': tx_hash, 'block_timestamp': _TX_TIME, 'ret': [{'fee': fee, 'contractRet': 'SUCCESS'}],
            'raw_data': {'contract': [{'type': 'TransferContract',
                                       'parameter': {'value': {'owner_address': owner_hex, 'to_address': to_hex,
                                                               'amount': amount}}}]}}


def test_native_transfer_between_own_wallets_is_imported_once(tron_wallet, monkeypatch):
    from jal.db.token_blacklist import tron_address_from_hex
    # TRX is already known as a wrapped token on Ethereum - one asset, one ticker, a listing on another chain.
    # The fetch below adds its Tron listing, and from then on the ticker names two rows of that same asset.
    wrapped = JalAssetCreator(type_id=PredefinedAsset.Crypto, name='Tron')
    wrapped.add_symbol('TRX', 3, AssetLocation.ETH_BLOCKCHAIN)
    sender = _second_wallet(tron_address_from_hex(_SENDER_HEX), name='Tron wallet 2')
    receiver = tron_wallet                                    # the fixture's wallet is the receiving end
    assert receiver.address() == tron_address_from_hex(_RECEIVER_HEX)
    history = ([], [_native(_SENDER_HEX, _RECEIVER_HEX, 100000000)])   # 100 TRX between the two wallets
    _import_history(sender, monkeypatch, *history)
    _import_history(receiver, monkeypatch, *history)                   # the same movement, seen from its other end
    assert len(JalAsset.get_crypto_assets_by_symbol('TRX')) == 1        # one coin, not a second asset for it
    assert len(JalAccount(sender.id()).dump_transfers()) == 1
    assert len(JalAccount(receiver.id()).dump_transfers()) == 1
