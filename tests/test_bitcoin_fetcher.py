import json
from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from constants import PredefinedAccountType, AssetLocation, AccountData
from jal.data_import.statement import JSF, Statement_ImportError
from jal.db.account import JalAccountCreator
from jal.net.chain_fetchers.bitcoin import BitcoinFetcher, _GAP_LIMIT
from jal.net.chain_fetchers.hd_wallet import ScriptType

# The fixture wallet is the published BIP84 test vector, so no address in this file belongs to anybody (see
# tests/local_test_data.json.example on why a real one must never be committed). Its account key is serialized with
# 'xpub' version bytes although the account is BIP84 - a real exporter does that, and the script-type detection has
# to survive it.
RECEIVE_0 = "bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu"
RECEIVE_1 = "bc1qnjg0jd8228aq7egyzacy8cys3knf9xvrerkf9g"
CHANGE_0 = "bc1q8c6fshw2dlwun7ekn9qwf37cu2rn755upcp6el"
SENDER = "bc1qku0qh0mc00y8tk0n65x2tqw4trlspak0fnjmfz"       # who paid the wallet, and
RECEIVER = "bc1qx0tpa0ctsy5v8xewdkpf69hhtz5cw0rf5uvyj6"     # whom the wallet paid - both outside it
SATOSHI = Decimal('100000000')


@pytest.fixture
def fixture_data(data_path):
    with open(data_path + "btc_wallet.json", 'r', encoding='utf-8') as f:
        yield json.load(f)


@pytest.fixture
def btc_wallet(prepare_db, fixture_data):
    account = JalAccountCreator(currency_id=2, number='', name='BTC wallet', investing=1, organization=1,
                                account_type=PredefinedAccountType.Wallet, address=fixture_data['xpub'],
                                chain=AssetLocation.BTC_BLOCKCHAIN).commit()
    assert account.id() == 1
    yield account


# Replaces the network with the recorded Esplora answers, serving the same endpoints the real API does: the address
# statistics that the gap scan probes with, and the paged transaction lists. An address the fixture doesn't know is
# answered as unused - which is what the chain says about the addresses of a wallet that isn't there, and what the
# script-type detection walks through before it finds the right one.
@pytest.fixture
def fetcher(btc_wallet, fixture_data, monkeypatch):
    calls = []

    def fake_get(self, endpoint):
        calls.append(endpoint)
        parts = endpoint.strip('/').split('/')
        transactions = [fixture_data['transactions'][x] for x in fixture_data['addresses'].get(parts[1], [])]
        if len(parts) == 2:                       # /address/{address}
            confirmed = [x for x in transactions if x['status']['confirmed']]
            return {"chain_stats": {"tx_count": len(confirmed), "funded_txo_count": len(confirmed)},
                    "mempool_stats": {"tx_count": len(transactions) - len(confirmed)}}
        if len(parts) == 5:                       # /address/{address}/txs/chain/{last_seen_txid} - older pages only
            confirmed = [x for x in transactions if x['status']['confirmed']]
            seen = [x['txid'] for x in confirmed]
            return confirmed[seen.index(parts[4]) + 1:] if parts[4] in seen else []
        return transactions                       # /address/{address}/txs - newest first, mempool included

    monkeypatch.setattr(BitcoinFetcher, "_get", fake_get)
    instance = BitcoinFetcher()
    instance.calls = calls
    yield instance


def _transfers(data) -> list:
    return data[JSF.TRANSFERS]


def _payments(data, payment_type) -> list:
    return [x for x in data[JSF.ASSET_PAYMENTS] if x['type'] == payment_type]


def _btc(satoshi) -> Decimal:
    return Decimal(satoshi) / SATOSHI


# ----------------------------------------------------------------------------------------------------------------------
# The script type is what the chain says it is, not what the key's prefix claims. The fixture key is 'xpub'-prefixed
# BIP84, so trusting the prefix would derive legacy '1...' addresses and report an empty wallet.
def test_script_type_is_detected_not_taken_from_the_prefix(fetcher, btc_wallet):
    fetcher.fetch(btc_wallet)
    assert json.loads(fetcher._new_cursor)['script'] == ScriptType.P2WPKH
    # The prefix still decides what to try first, so the legacy form is probed before the one that works
    probed = [x.split('/')[2] for x in fetcher.calls if x.startswith("/address/")]
    assert probed[0].startswith('1')            # ... the P2PKH form the 'xpub' prefix claims
    assert RECEIVE_0 in probed


def test_incoming_transfer_is_the_wallets_delta(fetcher, btc_wallet):
    data = fetcher.fetch(btc_wallet)
    incoming = [x for x in _transfers(data) if x['account'][0] == 0]
    assert len(incoming) == 1
    assert incoming[0]['withdrawal'] == _btc(944512)
    assert incoming[0]['fee'] == Decimal('0')            # the sender paid the miner, not the wallet
    assert incoming[0]['counterparty_address'] == SENDER
    # The sender's own change output is in the very same transaction and must not be counted as received
    assert incoming[0]['withdrawal'] != _btc(944512 + 400153953)


# The critical shape (BTC pre-requisites note, section 3): a spend whose change comes back to the wallet. What left
# is neither the whole input nor the wallet's balance - it is the delta less the fee, and a fetcher that got this
# wrong would book the change as money sent away.
def test_outgoing_spend_excludes_its_own_change(fetcher, btc_wallet):
    data = fetcher.fetch(btc_wallet)
    outgoing = [x for x in _transfers(data) if x['account'][1] == 0]
    assert len(outgoing) == 1
    assert outgoing[0]['withdrawal'] == _btc(100000)     # what the counterparty got ...
    assert outgoing[0]['fee'] == _btc(141)               # ... and what the miner got, charged to the wallet
    assert outgoing[0]['withdrawal'] != _btc(944512)     # not the whole input that was spent
    assert outgoing[0]['counterparty_address'] == RECEIVER
    assert outgoing[0]['account'][2] == 1                # the fee is always paid by the wallet being fetched


# A transaction that only shuffles coins between the wallet's own addresses moves no asset: the miner is the only
# one paid, so it is a GasFee payment and not a transfer of any amount.
def test_self_move_is_only_a_miner_fee(fetcher, btc_wallet):
    data = fetcher.fetch(btc_wallet)
    fees = _payments(data, JSF.PAYMENT_GAS_FEE)
    assert len(fees) == 1
    assert fees[0]['amount'] == _btc(200)
    assert not [x for x in _transfers(data) if x['number'] == fees[0]['number']]


def test_dust_is_recorded_as_an_attack_not_a_transfer(fetcher, btc_wallet):
    data = fetcher.fetch(btc_wallet)
    dust = _payments(data, JSF.PAYMENT_DUST_ATTACK)
    assert len(dust) == 1
    assert dust[0]['amount'] == _btc(546)                # below the 1000 satoshi default threshold
    assert not [x for x in _transfers(data) if x['number'] == dust[0]['number']]


# An unconfirmed transaction can still be replaced, so it produces nothing - but it is reported rather than dropped
# silently, and the cursor stays behind it so that the next fetch picks it up once it has a block.
def test_unconfirmed_transaction_is_skipped(fetcher, btc_wallet):
    data = fetcher.fetch(btc_wallet)
    assert any("not confirmed" in reason for reason in fetcher.skipped())
    pending = [x for x in _transfers(data) if x['withdrawal'] == _btc(500000)]
    assert not pending
    assert json.loads(fetcher._new_cursor)['addresses'][RECEIVE_1] != ''


def test_both_branches_are_scanned_to_the_gap_limit(fetcher, btc_wallet):
    fetcher.fetch(btc_wallet)
    probed = [x.split('/')[2] for x in fetcher.calls if len(x.split('/')) == 3]
    # The change branch is where the change of the spend landed - a scan that skipped it would miss the address the
    # wallet's own coins are on and read the spend as if everything had left.
    assert CHANGE_0 in probed
    # Receive: two used addresses and then the whole gap window; change: one used address and the gap window. The
    # probes before that belong to the script-type detection, which ends on the first address it finds in use.
    scan = probed[probed.index(RECEIVE_0) + 1:]
    assert len(scan) == (2 + _GAP_LIMIT) + (1 + _GAP_LIMIT)


# The cursor names, for every address in use, the newest transaction that was imported for it - which is both where
# the next fetch resumes and the record of which addresses are worth asking about at all.
def test_cursor_records_every_used_address(fetcher, btc_wallet, fixture_data):
    fetcher.fetch(btc_wallet)
    cursor = json.loads(fetcher._new_cursor)
    assert set(cursor['addresses']) == {RECEIVE_0, RECEIVE_1, CHANGE_0}
    newest_confirmed = {address: [x for x in txids
                                  if fixture_data['transactions'][x]['status']['confirmed']][0]
                        for address, txids in fixture_data['addresses'].items()}
    assert cursor['addresses'] == newest_confirmed


def test_second_fetch_finds_nothing_new(fetcher, btc_wallet):
    data = fetcher.fetch(btc_wallet)
    assert _transfers(data)
    btc_wallet.set_data(AccountData.SyncCursor, fetcher._new_cursor)

    second = BitcoinFetcher()
    second._get = fetcher._get                     # the same recorded answers, with its own call log
    calls = len(fetcher.calls)
    data = second.fetch(btc_wallet)
    assert not _transfers(data)
    assert not data[JSF.ASSET_PAYMENTS]
    # The script type is known and the used addresses need no probing anymore, so the second run is cheaper - but
    # the gap window is still walked, since that is where a new address shows up.
    assert len(fetcher.calls) - calls < calls


# Newly mined coins are income and not a transfer from anybody. Nothing in the validated history has that shape, so
# the import stops there and keeps everything older instead of booking it as something it isn't.
def test_coinbase_halts_the_import(fetcher, btc_wallet, fixture_data):
    spend = [x for x in fixture_data['transactions'].values()
             if x['status'].get('block_height') == 800002][0]
    coinbase = json.loads(json.dumps(spend))
    coinbase['txid'] = 'c0' + spend['txid'][2:]
    coinbase['status']['block_height'] = 800000                 # older than everything else in the fixture
    coinbase['vin'] = [{"is_coinbase": True, "prevout": None}]
    coinbase['vout'] = [{"scriptpubkey_address": RECEIVE_0, "value": 625000000}]
    fixture_data['transactions'][coinbase['txid']] = coinbase
    fixture_data['addresses'][RECEIVE_0] = fixture_data['addresses'][RECEIVE_0] + [coinbase['txid']]

    data = fetcher.fetch(btc_wallet)
    assert not _transfers(data)                                 # the coinbase is the oldest, so nothing follows it
    assert any("coinbase" in reason for reason in fetcher.skipped())
    assert json.loads(fetcher._new_cursor)['addresses'] == {}    # ... and no cursor moved past it


# A wallet may also be watched as a single address. It is the same classification with a one-address wallet, and it
# is faithful only until the address spends - the change then lands on an address it doesn't know.
def test_single_address_wallet(prepare_db, fixture_data, monkeypatch):
    account = JalAccountCreator(currency_id=2, number='', name='BTC address', investing=1, organization=1,
                                account_type=PredefinedAccountType.Wallet, address=RECEIVE_0,
                                chain=AssetLocation.BTC_BLOCKCHAIN).commit()

    def fake_get(self, endpoint):
        parts = endpoint.strip('/').split('/')
        return [fixture_data['transactions'][x] for x in fixture_data['addresses'].get(parts[1], [])]

    monkeypatch.setattr(BitcoinFetcher, "_get", fake_get)
    data = BitcoinFetcher().fetch(account)
    # The receive is seen exactly as the HD scan sees it; the spend, whose change went to an address this account
    # doesn't hold, is now the whole input leaving minus the fee.
    incoming = [x for x in _transfers(data) if x['account'][0] == 0]
    outgoing = [x for x in _transfers(data) if x['account'][1] == 0]
    assert len(incoming) == 1 and incoming[0]['withdrawal'] == _btc(944512)
    assert len(outgoing) == 1 and outgoing[0]['withdrawal'] == _btc(944512 - 141)


def test_account_of_another_chain_is_refused(fetcher, prepare_db):
    account = JalAccountCreator(currency_id=2, number='', name='Not BTC', investing=1, organization=1,
                                account_type=PredefinedAccountType.Wallet,
                                address="JALW6VdPLoxJYjMAhBo5BK897aYkEYUpE9aSPaETA7KF",
                                chain=AssetLocation.SOL_BLOCKCHAIN).commit()
    with pytest.raises(Statement_ImportError):
        fetcher.fetch(account)
