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
from jal.db.settings import JalSettings
from jal.db.token_blacklist import is_solana_address
from jal.net.chain_fetchers.solana import SolanaFetcher, _STAKE_PROGRAM
from jal.net.token_lists import TokenListProvider

# The wallet the recorded fixture was anonymized onto - deterministic, valid, and obviously not anyone's real
# address (see tests/local_test_data.json.example on why an on-chain address must never be committed). Program ids
# and token mints in the fixture are the real, public ones: they are the same for every user of the chain.
WALLET = "JALW6VdPLoxJYjMAhBo5BK897aYkEYUpE9aSPaETA7KF"
JUP_MINT = "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN"
_QUOTE_TS = 1700000000       # Before the recorded history, so every transfer in it resolves to this quote


@pytest.fixture
def sol_wallet(prepare_db):
    JalSettings().setValue("ApiKey_Helius", "test-key")
    # Helius reports a token movement as a mint address with no ticker or name attached, so the allow-list is both
    # what saves a real token from the spam filter and where its name comes from.
    TokenListProvider()._store(TokenList.JUPITER_VERIFIED, TokenListKind.Allow, AssetLocation.SOL_BLOCKCHAIN,
                               [{'address': JUP_MINT, 'symbol': 'JUP', 'name': 'Jupiter'}])
    account = JalAccountCreator(currency_id=2, number='', name='SOL wallet', investing=1, organization=1,
                                account_type=PredefinedAccountType.Wallet, address=WALLET,
                                chain=AssetLocation.SOL_BLOCKCHAIN).commit()
    assert account.id() == 1
    yield account


# Gives the database a priced SOL asset. The native dust rule weighs a transfer's value, so without a quote nothing
# is filtered - which is exactly a brand-new wallet's first fetch, covered separately below.
@pytest.fixture
def priced_sol(sol_wallet):
    asset = JalAssetCreator(type_id=PredefinedAsset.Crypto, name="Solana")
    asset.add_symbol('SOL', 2, AssetLocation.SOL_BLOCKCHAIN)
    JalAsset(asset.id()).set_quotes([{'timestamp': _QUOTE_TS, 'quote': Decimal('150')}], 2)   # 150 USD
    yield asset


# Replaces the network with the recorded Helius answer. Returns the fetcher plus the list of 'until' cursors that
# were requested, so a test may assert on the paging.
@pytest.fixture
def fetcher(sol_wallet, data_path, monkeypatch):
    calls = []

    def fake_transactions(self, until):
        calls.append(until)
        with open(data_path + "sol_transactions.json", 'r', encoding='utf-8') as f:
            records = json.load(f)          # already chronological, as _get_transactions returns it
        if until:      # the real API stops at this signature; the recorded answer is cut here instead
            signatures = [x['signature'] for x in records]
            if until in signatures:
                records = records[signatures.index(until) + 1:]
        return records

    monkeypatch.setattr(SolanaFetcher, "_get_transactions", fake_transactions)
    instance = SolanaFetcher()
    instance.calls = calls
    yield instance


def _transfers(data) -> list:
    return data[JSF.TRANSFERS]


def _payments(data, kind) -> list:
    return [p for p in data.get(JSF.ASSET_PAYMENTS, []) if p['type'] == kind]


def _symbols_of(data, ticker) -> list:
    return [s['id'] for a in data[JSF.ASSETS] for s in a[JSF.SYMBOLS] if s['symbol'] == ticker]


# ----------------------------------------------------------------------------------------------------------------------
def test_is_solana_address_accepts_valid_and_rejects_malformed():
    assert is_solana_address(WALLET)
    assert is_solana_address(JUP_MINT)
    assert is_solana_address(_STAKE_PROGRAM)
    assert not is_solana_address('')
    assert not is_solana_address('too-short')
    assert not is_solana_address('0x1111111111111111111111111111111111111111')   # an EVM address
    assert not is_solana_address(WALLET + 'AAAA')                                # decodes to more than 32 bytes
    assert not is_solana_address(WALLET.replace('J', '0', 1))                    # '0' is not in the base58 alphabet


def test_fetch_builds_transfers(fetcher, sol_wallet):
    data = fetcher.fetch(sol_wallet)
    assert len(_transfers(data)) > 0
    for transfer in _transfers(data):
        assert transfer['withdrawal'] > Decimal('0')
        # 'deposit' is the cost basis in the destination currency, which a fetcher cannot know - the user completes
        # it when the counterparty account is chosen during import (as in the Tron and EVM fetchers)
        assert transfer['deposit'] == Decimal('0')
        assert transfer['account'].count(0) == 1        # exactly one side is outside JAL
        assert transfer['number']                       # the transaction signature is always recorded


def test_native_asset_is_sol_without_address(fetcher, sol_wallet):
    data = fetcher.fetch(sol_wallet)
    sol = [a for a in data[JSF.ASSETS] if a[JSF.SYMBOLS][0]['symbol'] == 'SOL']
    assert len(sol) == 1
    # The native coin has no contract behind it, so it carries no address and is matched by ticker - which is safe
    # only because a chain's own coin is guaranteed by the chain, unlike a token's attacker-chosen ticker.
    assert 'address' not in sol[0][JSF.SYMBOLS][0]
    assert sol[0][JSF.SYMBOLS][0]['location'] == AssetLocation.SOL_BLOCKCHAIN


def test_token_carries_mint_address_and_listed_name(fetcher, sol_wallet):
    data = fetcher.fetch(sol_wallet)
    jup = [a for a in data[JSF.ASSETS] if a[JSF.SYMBOLS][0].get('address') == JUP_MINT]
    assert len(jup) == 1
    # Helius returns the mint only; the ticker and the name come from the allow-list that vouched for the token
    assert jup[0][JSF.SYMBOLS][0]['symbol'] == 'JUP'
    assert jup[0]['name'] == 'Jupiter'
    assert jup[0][JSF.SYMBOLS][0]['location'] == AssetLocation.SOL_BLOCKCHAIN


# The label Helius puts on a transaction describes what the transaction did, not what it did to this wallet: the
# recorded history contains a Jupiter swap typed 'UNKNOWN' and a bridge delivery typed 'SETTLE', and the wallet's
# own balance change is what decides the operation. A transaction that moved nothing of the wallet's is skipped.
def test_transactions_that_dont_touch_the_wallet_are_skipped(fetcher, sol_wallet):
    data = fetcher.fetch(sol_wallet)
    assert any("didn't move any of the wallet's assets" in reason for reason in fetcher.skipped())
    # ...and no operation carries the signature of either routing transaction
    routed = [tx['signature'] for tx in _recorded(fetcher)
              if tx['type'] in ('FULFILL', 'UNKNOWN') and tx['feePayer'] != WALLET]
    assert routed, "the fixture must contain routing transactions to make this meaningful"
    booked = {t['number'] for t in _transfers(data)} | {p['number'] for p in data.get(JSF.ASSET_PAYMENTS, [])}
    assert not (set(routed) & booked)


# An arriving asset is imported as an ordinary incoming transfer even when it is the far leg of a cross-chain move:
# a fetcher cannot tell one from any other receipt, so the user pairs it with its sending half afterwards (#47).
def test_bridge_arrival_is_a_plain_incoming_transfer(fetcher, sol_wallet):
    data = fetcher.fetch(sol_wallet)
    assert not data.get(JSF.BRIDGES)          # nothing is guessed to be a bridge leg
    assert not data.get(JSF.SWAPS)
    settle = [tx for tx in _recorded(fetcher) if tx['type'] == 'SETTLE'][0]
    arrival = [t for t in _transfers(data) if t['number'] == settle['signature']]
    assert len(arrival) == 1
    assert arrival[0]['account'][0] == 0      # incoming: the sending side is the one JAL doesn't know
    assert arrival[0]['fee'] == Decimal('0')  # the wallet didn't pay for it, the bridge relayer did


def test_gas_is_charged_only_when_the_wallet_paid_it(fetcher, sol_wallet):
    data = fetcher.fetch(sol_wallet)
    for transfer in _transfers(data):
        signature = transfer['number']
        payer = [tx['feePayer'] for tx in _recorded(fetcher) if tx['signature'] == signature][0]
        if payer != WALLET:
            assert transfer['fee'] == Decimal('0'), "somebody else's fee must never be charged to the wallet"


# ----------------------------------------------------------------------------------------------------------------------
# Native staking: a stake account holds the wallet's lamports while they earn, so both directions are plain
# transfers to an account JAL doesn't know (the container pattern, CRYPTO_PATH #50/#61).
def test_staking_deposit_is_an_outgoing_transfer(fetcher, sol_wallet):
    data = fetcher.fetch(sol_wallet)
    staked = [tx for tx in _recorded(fetcher) if tx['type'] == 'STAKE_SOL']
    assert len(staked) == 2
    for tx in staked:
        transfer = [t for t in _transfers(data) if t['number'] == tx['signature']]
        assert len(transfer) == 1
        assert transfer[0]['account'][0] == 1                  # outgoing, from the wallet
        assert transfer[0]['fee'] > Decimal('0')               # the wallet signed it, so it paid the gas
        assert 'Staked to' in transfer[0]['description']
    # The amounts are the gross movements, with the transaction fee excluded rather than folded in
    amounts = sorted(t['withdrawal'] for t in _transfers(data)
                     if t['number'] in {tx['signature'] for tx in staked})
    assert amounts == [Decimal('2.919753195'), Decimal('5.90228288')]


def test_deactivation_moves_nothing_and_only_costs_gas(fetcher, sol_wallet):
    data = fetcher.fetch(sol_wallet)
    unstake = [tx for tx in _recorded(fetcher) if tx['type'] == 'UNSTAKE_SOL'][0]
    # The lamports stay in the stake account and change no hands - the stake merely stops earning
    assert not [t for t in _transfers(data) if t['number'] == unstake['signature']]
    gas = [p for p in _payments(data, JSF.PAYMENT_GAS_FEE) if p['number'] == unstake['signature']]
    assert len(gas) == 1
    assert gas[0]['amount'] == Decimal('0.000012755')


# The withdrawal returns more than was staked. The excess is the yield earned inside the container, so it is split
# off as a StakingReward while the principal returns as a transfer - which lands the box account back at zero.
def test_withdrawal_splits_principal_from_yield(fetcher, sol_wallet):
    data = fetcher.fetch(sol_wallet)
    withdrawal = [tx for tx in _recorded(fetcher) if tx['type'] == 'WITHDRAW'][0]
    transfer = [t for t in _transfers(data) if t['number'] == withdrawal['signature']]
    assert len(transfer) == 1
    assert transfer[0]['account'][0] == 0                          # incoming, back into the wallet
    assert transfer[0]['withdrawal'] == Decimal('2.919753195')     # exactly what had been staked
    reward = [p for p in _payments(data, JSF.PAYMENT_STAKING_REWARD) if p['number'] == withdrawal['signature']]
    assert len(reward) == 1
    assert reward[0]['amount'] == Decimal('0.001776114')           # 2.921529309 withdrawn - 2.919753195 staked
    assert transfer[0]['withdrawal'] + reward[0]['amount'] == Decimal('2.921529309')


# A withdrawal from a stake account JAL never saw filled has nothing to measure the yield against. Booking the
# unexplained excess as income would turn a returned deposit into earnings, which is the one error that must not
# happen here - so the whole amount comes back as principal and the user is told the yield wasn't separated.
def test_withdrawal_without_a_known_deposit_is_all_principal(fetcher, sol_wallet, monkeypatch):
    recorded = _recorded(fetcher)
    withdrawal = [tx for tx in recorded if tx['type'] == 'WITHDRAW'][0]
    monkeypatch.setattr(SolanaFetcher, "_get_transactions", lambda self, until: [withdrawal])
    data = fetcher.fetch(sol_wallet)
    assert not _payments(data, JSF.PAYMENT_STAKING_REWARD)
    transfer = [t for t in _transfers(data) if t['number'] == withdrawal['signature']]
    assert transfer[0]['withdrawal'] == Decimal('2.921529309')     # the whole withdrawal, yield included
    assert any("predates the sync cursor" in reason for reason in fetcher.skipped())


# The staking state is what lets a later withdrawal be split, so it must survive between fetches - and, like the
# sync cursor, must never get ahead of the operations that justify it.
def test_staking_state_is_stored_only_after_import(fetcher, sol_wallet):
    staked = [tx for tx in _recorded(fetcher) if tx['type'] == 'STAKE_SOL'][:1]
    fetcher._get_transactions = lambda until: staked
    fetcher.fetch(sol_wallet)
    assert not JalAccount(1).get_data(AccountData.StakeAccounts)   # fetched, but not imported yet
    fetcher.import_fetched()
    stored = json.loads(JalAccount(1).get_data(AccountData.StakeAccounts))
    assert list(stored.values()) == ['2.919753195']


# ----------------------------------------------------------------------------------------------------------------------
def test_native_dust_is_filtered(fetcher, sol_wallet, priced_sol):
    data = fetcher.fetch(sol_wallet)
    sol_symbols = _symbols_of(data, 'SOL')
    incoming = [t for t in _transfers(data) if t['account'][0] == 0 and t['symbol'][0] in sol_symbols]
    # The recorded history receives 1 lamport (1e-9 SOL) blasted at fifteen addresses at once - poisoning dust
    assert incoming, "the fixture has real incoming SOL too, not only dust"
    assert all(t['withdrawal'] > Decimal('0.000001') for t in incoming)
    assert any("dust" in reason for reason in fetcher.skipped())


def test_unpriceable_native_coin_is_imported(fetcher, sol_wallet):
    data = fetcher.fetch(sol_wallet)
    # A brand-new wallet has no SOL asset yet, so nothing can be priced and nothing is judged to be dust: an
    # unquotable amount is not evidence of spam, and silently dropping a real transfer is the worse mistake.
    assert not any("dust" in reason for reason in fetcher.skipped())
    sol_symbols = _symbols_of(data, 'SOL')
    assert any(t['withdrawal'] == Decimal('1E-9') for t in _transfers(data) if t['symbol'][0] in sol_symbols)


# ----------------------------------------------------------------------------------------------------------------------
def test_cursor_is_used_and_advanced(fetcher, sol_wallet):
    fetcher.fetch(sol_wallet)
    assert fetcher.calls[0] == ''                    # nothing fetched before, so the whole history
    fetcher.import_fetched()
    cursor = JalAccount(1).get_data(AccountData.SyncCursor)
    assert is_solana_address(cursor) or len(cursor) > 40      # a signature, the only position the API accepts
    assert cursor == _recorded(fetcher)[-1]['signature']

    # A second run asks only for what happened after the stored position, and finds nothing new
    again = SolanaFetcher()
    again._get_transactions = fetcher._get_transactions
    data = again.fetch(JalAccount(1))
    assert not _transfers(data)


def test_halt_rolls_back_only_the_offending_transaction(fetcher, sol_wallet, monkeypatch):
    recorded = _recorded(fetcher)
    # A transaction the wallet paid for that both spends and receives goes through a program this fetcher has no
    # registry for. It must never be guessed at, so the import stops there and keeps everything before it.
    exchange = dict(recorded[1], signature='HaltingSignature', type='SWAP', instructions=[],
                    accountData=[{'account': WALLET, 'nativeBalanceChange': -1000000000,
                                  'tokenBalanceChanges': [{'userAccount': WALLET, 'mint': JUP_MINT,
                                                           'rawTokenAmount': {'tokenAmount': '5000000',
                                                                              'decimals': 6}}]}],
                    feePayer=WALLET, nativeTransfers=[], tokenTransfers=[])
    monkeypatch.setattr(SolanaFetcher, "_get_transactions",
                        lambda self, until: [recorded[0], exchange, recorded[1]])
    data = fetcher.fetch(sol_wallet)

    booked = {t['number'] for t in _transfers(data)}
    assert recorded[0]['signature'] in booked          # everything before the halt is kept
    assert 'HaltingSignature' not in booked            # the offending transaction is rolled back
    assert recorded[1]['signature'] not in booked      # and so is everything after it
    assert any("unrecognized program" in reason for reason in fetcher.skipped())
    # The cursor parks on the last transaction that did import, so the halting one is retried next time
    fetcher.import_fetched()
    assert JalAccount(1).get_data(AccountData.SyncCursor) == recorded[0]['signature']


def test_import_creates_assets_and_is_idempotent(fetcher, sol_wallet):
    fetcher.fetch(sol_wallet)
    fetcher.import_fetched()
    assert JalAsset.find({'symbol': 'SOL', 'type': PredefinedAsset.Crypto}).id() > 0
    # The token is identified by its mint, never by the ticker the allow-list happens to give it
    jup = JalSymbol.find_by_identifier(SymbolId.SOL_ADDRESS, JUP_MINT)
    assert jup.id() and jup.symbol() == 'JUP'
    assert jup.location() == AssetLocation.SOL_BLOCKCHAIN
    assert jup.asset().type() == PredefinedAsset.Crypto
    first = len(JalAccount(1).dump_transfers())
    assert first > 0

    again = SolanaFetcher()
    again._get_transactions = fetcher._get_transactions
    again.fetch(JalAccount(1))
    again.import_fetched()
    # The cursor makes the second run see nothing, so no operation is duplicated
    assert len(JalAccount(1).dump_transfers()) == first


# ----------------------------------------------------------------------------------------------------------------------
# The recorded fixture, read through the fetcher's own (monkeypatched) accessor so a test never re-opens the file
def _recorded(fetcher) -> list:
    return fetcher._get_transactions('')
