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
from jal.net.chain_fetchers.fetcher import TransferMark
from jal.net.chain_fetchers.solana import SolanaFetcher, _STAKE_PROGRAM
from jal.net.token_lists import TokenListProvider

# The wallet the recorded fixture was anonymized onto - deterministic, valid, and obviously not anyone's real
# address - an on-chain address can't be anonymized afterwards, so a real one is never committed. Program ids
# and token mints in the fixture are the real, public ones: they are the same for every user of the chain.
WALLET = "JALW6VdPLoxJYjMAhBo5BK897aYkEYUpE9aSPaETA7KF"
JUP_MINT = "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN"


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


def test_counterparty_note_only_for_unknown_addresses(fetcher, sol_wallet):
    fetcher._account = sol_wallet
    external = "2bSYn32SzmtywQQYSWbENCFWi7cCZjeTDJHMf8gsStm1"
    # An outside counterparty is recorded, sender first, so the user can identify it
    assert fetcher._counterparty_note(external, True) == f"{external} → {WALLET}"
    assert fetcher._counterparty_note(external, False) == f"{WALLET} → {external}"


def test_counterparty_note_empty_between_known_wallets(fetcher, sol_wallet):
    # A second wallet the user owns: a transfer between two known accounts needs no address note
    other = "2bSYn32SzmtywQQYSWbENCFWi7cCZjeTDJHMf8gsStm1"
    JalAccountCreator(currency_id=2, number='', name='SOL wallet 2', investing=1, organization=1,
                      account_type=PredefinedAccountType.Wallet, address=other,
                      chain=AssetLocation.SOL_BLOCKCHAIN).commit()
    fetcher._account = sol_wallet
    assert fetcher._counterparty_note(other, True) == ''
    assert fetcher._counterparty_note(other, False) == ''


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
        # The transfer is all a movement into the container can be recorded as, so it says so: the tag makes these
        # findable in the ledger and the stake account it went to is kept behind it
        assert transfer[0]['description'].startswith(TransferMark.CUSTODY)
        assert 'Staked to' in transfer[0]['description']
        # ... and the stake account is recorded as the counterparty ADDRESS as well, which is what lets a staking
        # box holding it settle this leg without being asked. The note names it too, but nothing can match on text.
        assert transfer[0]['counterparty_address'] in transfer[0]['description']
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
def test_native_dust_is_recorded_as_dust_attack(fetcher, sol_wallet):
    data = fetcher.fetch(sol_wallet)
    sol_symbols = _symbols_of(data, 'SOL')
    incoming = [t for t in _transfers(data) if t['account'][0] == 0 and t['symbol'][0] in sol_symbols]
    # The recorded history has real incoming SOL alongside 1 lamport (1e-9 SOL) blasted at several addresses at
    # once - poisoning dust, well under the 0.001 SOL default threshold. The dust never becomes an ordinary
    # transfer...
    assert incoming, "the fixture has real incoming SOL too, not only dust"
    assert all(t['withdrawal'] >= Decimal('0.001') for t in incoming)
    # ...it is recorded as a DustAttack payment instead, so the balance it moved is still reconciled.
    dust = [p for p in data[JSF.ASSET_PAYMENTS] if p['type'] == JSF.PAYMENT_DUST_ATTACK]
    assert dust, "the fixture has 1-lamport dust blasted at several addresses"
    assert all(p['amount'] == Decimal('1E-9') for p in dust)


# The rule is judged on the RAW COIN AMOUNT against the chain's own threshold, never on a fiat value - unlike the
# old value-based rule, this needs no price data and so is never accidentally inert.
#
# The bounds are derived from the threshold in force instead of being written out as numbers. A literal here
# restates SolanaFetcher.native_dust_threshold, and goes on asserting the old figure once that default is retuned or
# the user edits the 'DustThreshold_SOL' setting - which is exactly how this test came to disagree with the code it
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


# A dust payment must reach the ledger even though the wallet's very first fetch has no SOL asset or quote of its
# own yet - the zero-basis fallback in AssetPayment.price() is what makes that safe (see the discussion that
# replaced the old value-based dust rule: requiring a quote is exactly what used to make dust detection inert).
def test_dust_attack_reaches_the_database_without_a_price(fetcher, sol_wallet):
    from jal.db.operations import AssetPayment
    fetcher.fetch(sol_wallet)
    fetcher.import_fetched()
    assert JalAsset.find({'symbol': 'SOL', 'type': PredefinedAsset.Crypto}).id() != 0   # created by the import itself
    dust = AssetPayment.get_list(sol_wallet.id(), subtype=AssetPayment.DustAttack)
    assert dust
    assert all(p.amount() == Decimal('1E-9') for p in dust)   # the raw SOL quantity is still recorded correctly
    assert all(p.price() == Decimal('0') for p in dust)       # ...but opened at a zero basis, having no quote to price it


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
# Sending a token to an address that has no account for it CREATES one, and the sender pays its rent-exempt minimum.
# The coin leaves the wallet but reaches nobody's balance: a token account is an account of its own, its lamports are
# not part of its owner's balance, and closing it later pays them to the OWNER rather than back to the sender. Left as
# a transfer it waits for a counterpart that does not exist - which is what leg 4596 of the real wallet did.
ATA = "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin"      # the token account created for the recipient
OTHER = "5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9"    # an ordinary wallet address


def _rent_tx(recorded, incoming=False, is_token_account=True):
    lamports = 2039280
    # fee=0 keeps the arithmetic readable: Helius reports 'nativeBalanceChange' NET of the fee and the fetcher adds
    # it back, so a non-zero fee here would make the delta the rent minus the fee rather than the rent
    return dict(recorded, signature='RentSignature', type='TRANSFER', instructions=[], feePayer=WALLET, fee=0,
                accountData=[{'account': WALLET, 'nativeBalanceChange': lamports if incoming else -lamports,
                              'tokenBalanceChanges': []},
                             {'account': ATA, 'nativeBalanceChange': -lamports if incoming else lamports,
                              # what marks it a TOKEN account: its own token balance changed here
                              'tokenBalanceChanges': ([{'userAccount': OTHER, 'mint': JUP_MINT,
                                                        'rawTokenAmount': {'tokenAmount': '1000000',
                                                                           'decimals': 6}}]
                                                      if is_token_account else [])}],
                nativeTransfers=[{'fromUserAccount': ATA if incoming else WALLET,
                                  'toUserAccount': WALLET if incoming else ATA, 'amount': lamports}],
                tokenTransfers=[])


def test_rent_paid_into_a_token_account_is_not_a_transfer(fetcher, sol_wallet, monkeypatch):
    recorded = _recorded(fetcher)
    rent = _rent_tx(recorded[0])
    monkeypatch.setattr(SolanaFetcher, "_get_transactions", lambda self, until: [rent])
    data = fetcher.fetch(sol_wallet)

    assert _transfers(data) == []                     # nothing is left waiting for a counterpart
    paid = _payments(data, JSF.PAYMENT_TOKEN_RENT)
    assert len(paid) == 1
    assert paid[0]['amount'] == Decimal('0.00203928')     # the rent-exempt minimum of a standard token account
    assert ATA in paid[0]['description'] and JUP_MINT in paid[0]['description']


def test_rent_returned_when_the_token_account_is_closed(fetcher, sol_wallet, monkeypatch):
    recorded = _recorded(fetcher)
    monkeypatch.setattr(SolanaFetcher, "_get_transactions", lambda self, until: [_rent_tx(recorded[0], incoming=True)])
    data = fetcher.fetch(sol_wallet)

    assert _transfers(data) == []
    returned = _payments(data, JSF.PAYMENT_TOKEN_RENT_RETURN)
    assert len(returned) == 1 and returned[0]['amount'] == Decimal('0.00203928')
    assert not _payments(data, JSF.PAYMENT_TOKEN_RENT)


# The gas of the transaction must not go missing when the rent is pulled out of the deltas: with nothing else of the
# wallet's moving, the fee falls through to the GasFee that _emit_transfers() charges for a transaction that only
# paid. Without this the wallet quietly keeps the fee it really spent.
def test_the_gas_of_a_rent_payment_is_still_charged(fetcher, sol_wallet, monkeypatch):
    recorded = _recorded(fetcher)
    rent = _rent_tx(recorded[0])
    rent['fee'] = 5000                                     # lamports, paid by the wallet
    rent['accountData'][0]['nativeBalanceChange'] = -2039280 - 5000     # Helius reports the change NET of the fee
    monkeypatch.setattr(SolanaFetcher, "_get_transactions", lambda self, until: [rent])
    data = fetcher.fetch(sol_wallet)

    paid = _payments(data, JSF.PAYMENT_TOKEN_RENT)
    assert len(paid) == 1 and paid[0]['amount'] == Decimal('0.00203928')   # the rent itself is the gross amount
    gas = _payments(data, JSF.PAYMENT_GAS_FEE)
    assert len(gas) == 1 and gas[0]['amount'] == Decimal('0.000005')
    assert _transfers(data) == []


# The rule is "the address is a token account", not "the amount is 2039280" - the rent-exempt minimum differs for a
# Token-2022 account with extensions, so matching on the constant would recognize only the common case.
def test_the_same_amount_to_an_ordinary_address_stays_a_transfer(fetcher, sol_wallet, monkeypatch):
    recorded = _recorded(fetcher)
    plain = _rent_tx(recorded[0], is_token_account=False)
    monkeypatch.setattr(SolanaFetcher, "_get_transactions", lambda self, until: [plain])
    data = fetcher.fetch(sol_wallet)

    assert _payments(data, JSF.PAYMENT_TOKEN_RENT) == []
    transfers = _transfers(data)
    assert len(transfers) == 1 and transfers[0]['withdrawal'] == Decimal('0.00203928')


# ----------------------------------------------------------------------------------------------------------------------
# The recorded fixture, read through the fetcher's own (monkeypatched) accessor so a test never re-opens the file
def _recorded(fetcher) -> list:
    return fetcher._get_transactions('')
