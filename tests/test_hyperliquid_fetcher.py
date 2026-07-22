import json
from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from constants import PredefinedAccountType, AssetLocation, AccountData, SymbolId
from jal.data_import.statement import JSF
from jal.db.account import JalAccountCreator, JalAccount
from jal.db.symbol import JalSymbol
from jal.db.token_blacklist import is_valid_address, JalTokenBlacklist
from jal.net.chain_fetchers.hyperliquid import HyperliquidFetcher, _HaltImport
from jal.net.downloader import llama_coin_keys

# The account the recorded fixtures were anonymized onto - valid in shape and obviously nobody's real address
# (see tests/local_test_data.json.example on why an on-chain address must never be committed). The token ids and
# market aliases in the fixtures are the real, public ones: they are the same for every user of the venue.
WALLET = "0xfa11ba11fa11ba11fa11ba11fa11ba11fa11ba11"
PEER = "0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
USDC_ID = "0x6d1e7cde53ba9467b783cb7c530ce054"
HYPE_ID = "0x0d01dc56dcaaca66ad901c959b4011ec"
UBTC_ID = "0x8f254b963e8468305d409b33aa137c67"
UBTC_EVM = "0x9fdbda0a5e284c32744d2f17ee5c74b284993463"


@pytest.fixture
def hl_account(prepare_db, data_path):
    # There is deliberately NO allow-list: 'spotMeta' lists junk too (the real account got a listed but worthless
    # airdrop), so the fetcher trusts the per-transfer USD value the venue reports, not registry membership. The
    # fetcher resolves a token's identity from its own spotMeta fetch, so nothing has to be seeded here.
    account = JalAccountCreator(currency_id=2, number='', name='HL account', investing=1, organization=1,
                                account_type=PredefinedAccountType.Wallet, address=WALLET,
                                chain=AssetLocation.HL_BLOCKCHAIN).commit()
    assert account.id() == 1
    yield account


# Replaces the network with the recorded answers. Both histories honour 'startTime' the way the real API does
# (inclusive), so a test may assert on what a second fetch picks up.
@pytest.fixture
def fetcher(hl_account, data_path, monkeypatch):
    calls = []

    def fake_post(self, request):
        calls.append(request)
        if request['type'] == 'spotMeta':
            with open(data_path + "hl_spot_meta.json", 'r', encoding='utf-8') as f:
                return json.load(f)
        sample = {"userFillsByTime": "hl_fills.json", "userNonFundingLedgerUpdates": "hl_ledger.json"}
        with open(data_path + sample[request['type']], 'r', encoding='utf-8') as f:
            records = json.load(f)
        return [x for x in records if int(x['time']) >= int(request['startTime'])]

    monkeypatch.setattr(HyperliquidFetcher, "_post", fake_post)
    instance = HyperliquidFetcher()
    instance.calls = calls
    yield instance


# The account's real history, anonymized: every address and hash replaced (the account onto WALLET), while the token
# ids, market aliases, prices and amounts are kept verbatim - they are public and identical for every user. It is
# the exact analogue of the Solana fetcher's recorded fixture, and the whole of it is replayed below.
@pytest.fixture
def real_fetcher(hl_account, data_path, monkeypatch):
    def fake_post(self, request):
        if request['type'] == 'spotMeta':
            with open(data_path + "hl_spot_meta.json", 'r', encoding='utf-8') as f:
                return json.load(f)
        sample = {"userFillsByTime": "hl_real_fills.json", "userNonFundingLedgerUpdates": "hl_real_ledger.json"}
        with open(data_path + sample[request['type']], 'r', encoding='utf-8') as f:
            records = json.load(f)
        return [x for x in records if int(x['time']) >= int(request['startTime'])]

    monkeypatch.setattr(HyperliquidFetcher, "_post", fake_post)
    yield HyperliquidFetcher()


def _swaps(data) -> list:
    return data.get(JSF.SWAPS, [])


def _transfers(data) -> list:
    return data[JSF.TRANSFERS]


def _bridges(data) -> list:
    return data.get(JSF.BRIDGES, [])


def _payments(data, kind) -> list:
    return [p for p in data.get(JSF.ASSET_PAYMENTS, []) if p['type'] == kind]


def _symbol_of(data, ticker):
    ids = [s['id'] for a in data[JSF.ASSETS] for s in a[JSF.SYMBOLS] if s['symbol'] == ticker]
    assert len(ids) == 1
    return ids[0]


# ----------------------------------------------------------------------------------------------------------------------
def test_address_validation_uses_the_evm_shape():
    # HyperCore is its own L1 but reuses Ethereum's address format - the user signs with the same wallet
    assert is_valid_address(AssetLocation.HL_BLOCKCHAIN, WALLET)
    assert not is_valid_address(AssetLocation.HL_BLOCKCHAIN, '')
    assert not is_valid_address(AssetLocation.HL_BLOCKCHAIN, WALLET[:-1])
    assert not is_valid_address(AssetLocation.HL_BLOCKCHAIN, 'JALW6VdPLoxJYjMAhBo5BK897aYkEYUpE9aSPaETA7KF')


def test_a_spot_fill_becomes_a_swap(fetcher, hl_account):
    data = fetcher.fetch(hl_account)
    # A buy gives up the quote token and receives the base one; both quantities are exact and nothing is derived
    buy = [x for x in _swaps(data) if x['tx_hash'].endswith('a1')][0]
    assert buy['out_symbol'] == _symbol_of(data, 'USDC')
    assert buy['out_qty'] == Decimal('3000')          # 0.05 * 60000
    assert buy['in_symbol'] == _symbol_of(data, 'UBTC')
    assert buy['in_qty'] == Decimal('0.05')
    assert buy['fee_qty'] == Decimal('1.5')
    assert buy['fee_symbol'] == _symbol_of(data, 'USDC')
    # A sell is the mirror image of it
    sell = [x for x in _swaps(data) if x['tx_hash'].endswith('a4')][0]
    assert sell['out_symbol'] == _symbol_of(data, 'UBTC')
    assert sell['out_qty'] == Decimal('0.02')
    assert sell['in_symbol'] == _symbol_of(data, 'USDC')
    assert sell['in_qty'] == Decimal('1300')          # 0.02 * 65000


def test_fill_fee_may_be_charged_in_a_third_token(fetcher, hl_account):
    data = fetcher.fetch(hl_account)
    # Hyperliquid bills the fee in a token that varies from fill to fill and is not necessarily one of the two
    # being swapped - here it is the token that was bought, which Swap already supports through fee_symbol/fee_qty
    swap = [x for x in _swaps(data) if x['tx_hash'].endswith('a3')][0]
    assert swap['in_symbol'] == _symbol_of(data, 'HYPE')
    assert swap['fee_symbol'] == _symbol_of(data, 'HYPE')
    assert swap['fee_qty'] == Decimal('0.12')


def test_token_carries_its_id_and_its_hyperevm_address(fetcher, hl_account):
    data = fetcher.fetch(hl_account)
    ubtc = [a for a in data[JSF.ASSETS] if a[JSF.SYMBOLS][0]['symbol'] == 'UBTC'][0]
    symbol = ubtc[JSF.SYMBOLS][0]
    # The HyperCore token id is the identity of the token; the HyperEVM contract address is kept beside it because
    # that is the form the quote source indexes most Hyperliquid tokens by (see llama_coin_keys)
    assert symbol['address'] == UBTC_ID
    assert symbol['evm_address'] == UBTC_EVM
    assert symbol['location'] == AssetLocation.HL_BLOCKCHAIN
    # HYPE has no HyperEVM deployment at all, and is an ordinary token here rather than an address-less native coin
    hype = [a for a in data[JSF.ASSETS] if a[JSF.SYMBOLS][0]['symbol'] == 'HYPE'][0]
    assert hype[JSF.SYMBOLS][0]['address'] == HYPE_ID
    assert 'evm_address' not in hype[JSF.SYMBOLS][0]


def test_bridge_deposit_is_a_plain_incoming_transfer(fetcher, hl_account):
    data = fetcher.fetch(hl_account)
    deposit = [x for x in _transfers(data) if x['number'].endswith('001')][0]
    assert deposit['account'] == [0, 1, 1]            # the sending side is unknown, so the import asks for it
    assert deposit['withdrawal'] == Decimal('5000')
    assert deposit['deposit'] == Decimal('0')         # the cost basis is completed by the user during import


def test_bridge_withdrawal_becomes_a_pending_half(fetcher, hl_account):
    data = fetcher.fetch(hl_account)
    assert len(_bridges(data)) == 1
    half = _bridges(data)[0]
    # 'usdc' is the amount that crosses (verified on-chain: it equals the Arbitrum arrival), and the fee is charged
    # on top of it - the account loses usdc + fee
    assert half['qty'] == Decimal('1000')
    assert half['fee_qty'] == Decimal('1')
    assert half['fee_symbol'] == _symbol_of(data, 'USDC')


def test_transfer_to_another_address_is_outgoing_with_a_note(fetcher, hl_account):
    data = fetcher.fetch(hl_account)
    sent = [x for x in _transfers(data) if x['number'].endswith('007')][0]
    assert sent['account'] == [1, 0, 1]
    assert sent['withdrawal'] == Decimal('100')
    assert sent['description'] == f"{WALLET} → {PEER}"


def test_staking_is_a_box_account_and_the_excess_is_income(fetcher, hl_account):
    data = fetcher.fetch(hl_account)
    staked = [x for x in _transfers(data) if x['number'].endswith('005')][0]
    assert staked['account'] == [1, 0, 1]             # out of the wallet into the container
    assert staked['withdrawal'] == Decimal('15')
    unstaked = [x for x in _transfers(data) if x['number'].endswith('006')][0]
    assert unstaked['account'] == [0, 1, 1]
    # Only the principal comes back as a transfer; the excess earned inside the container is income, which lands
    # the box account at exactly zero
    assert unstaked['withdrawal'] == Decimal('15')
    rewards = _payments(data, JSF.PAYMENT_STAKING_REWARD)
    assert len(rewards) == 1
    assert rewards[0]['amount'] == Decimal('0.5')
    assert rewards[0]['symbol'] == _symbol_of(data, 'HYPE')


def test_unstaking_without_a_known_deposit_is_all_principal(fetcher, hl_account, monkeypatch):
    # A withdrawal whose deposit predates the sync cursor has nothing to measure the yield against. Inventing income
    # out of a returned deposit is the one error that must not happen, so the whole amount is returned principal.
    monkeypatch.setattr(HyperliquidFetcher, "_load_staked", lambda self: {})
    original = HyperliquidFetcher._collect
    monkeypatch.setattr(HyperliquidFetcher, "_collect",
                        lambda self, start, seen: [x for x in original(self, start, seen)
                                                   if x['hash'].endswith('006')])
    data = fetcher.fetch(hl_account)
    assert not _payments(data, JSF.PAYMENT_STAKING_REWARD)
    assert _transfers(data)[0]['withdrawal'] == Decimal('15.5')


def test_move_between_order_books_of_one_account_is_skipped(fetcher, hl_account):
    data = fetcher.fetch(hl_account)
    # Both books belong to the same JAL account, so nothing left it - but it is reported rather than dropped quietly
    assert not [x for x in _transfers(data) if x['number'].endswith('008')]
    assert any('order books' in reason for reason in fetcher.skipped())


def test_worthless_listed_token_is_quarantined_as_dust(fetcher, hl_account):
    data = fetcher.fetch(hl_account)
    # A listed token (PURR is in spotMeta) blasted at the account worth $0 is an airdrop, not a holding: registry
    # membership must not save it. It becomes no asset even though it is a real ticker, and the user may review it.
    assert all(s['symbol'] != 'PURR' for a in data[JSF.ASSETS] for s in a[JSF.SYMBOLS])
    assert JalTokenBlacklist.is_blacklisted(AssetLocation.HL_BLOCKCHAIN,
                                            "0xc1fb593aeffbeb02f85e0308e9956a90")   # PURR token id
    assert any('dust' in reason or 'spam' in reason for reason in fetcher.skipped())


def test_unsupported_record_halts_and_keeps_everything_before_it(fetcher, hl_account):
    data = fetcher.fetch(hl_account)
    # The fixture ends with a vault deposit, which this fetcher has no model for. It must stop there instead of
    # guessing, keeping every earlier record, and say so.
    assert any('vaultDeposit' in reason for reason in fetcher.skipped())
    assert len(_swaps(data)) == 4
    assert _bridges(data)                       # the records before the halt are all there
    cursor = json.loads(fetcher._new_cursor)
    assert cursor['ts'] == 9000000              # parked on the last record that did import, not on the halting one


def test_cursor_keeps_the_keys_of_its_own_millisecond(fetcher, hl_account):
    # 'startTime' is inclusive and an exchange produces several fills within one millisecond, so the cursor carries
    # the identities of the records already imported at its instant - a cursor of "the millisecond + 1" would drop
    # the rest of such a group.
    fetcher.fetch(hl_account)
    fetcher._account.set_data(AccountData.SyncCursor, HyperliquidFetcher._make_cursor(2000000, {'f111111111111111'}))
    again = HyperliquidFetcher()
    again._post = fetcher._post
    data = again.fetch(hl_account)
    imported = {x['tx_hash'][-2:] for x in _swaps(data)}
    assert 'a1' not in imported        # already imported at that very millisecond
    assert 'a2' in imported            # its neighbour in the same millisecond is NOT lost


def test_import_stores_both_identifiers_and_advances_the_cursor(fetcher, hl_account):
    fetcher.fetch(hl_account)
    fetcher.import_fetched()
    # The token is found by its HyperCore token id - that is its identity - and the HyperEVM address it also
    # carries is what the quote downloader reaches for first
    symbol = JalSymbol.find_by_identifier(SymbolId.HL_ADDRESS, UBTC_ID)
    assert symbol.id()
    assert symbol.symbol() == 'UBTC'
    assert symbol.identifier(SymbolId.HL_EVM_ADDRESS) == UBTC_EVM
    assert llama_coin_keys(symbol)[0] == f"hyperliquid:{UBTC_EVM}"
    # A second run resumes from the stored cursor and finds nothing it has already imported
    again = HyperliquidFetcher()
    again._post = fetcher._post
    data = again.fetch(JalAccount(1))
    assert not _swaps(data) and not _transfers(data) and not _bridges(data)


def test_real_history_replays_without_halts(real_fetcher, hl_account):
    # The complete anonymized real history, replayed end to end. It must classify every one of its records without
    # halting, and produce exactly the operations the account's activity implies.
    data = real_fetcher.fetch(hl_account)
    real_fetcher.import_fetched()
    assert not any('unsupported' in reason for reason in real_fetcher.skipped())     # nothing halted
    # 14 spot fills -> 14 swaps
    assert len(_swaps(data)) == 14
    # 4 bridge deposits (in) + 3 sends out + 3 sends in + 2 stakes out = 12 transfers; the $0 MAX airdrop is dust
    assert len(_transfers(data)) == 12
    assert not [a for a in data[JSF.ASSETS] if a[JSF.SYMBOLS][0]['symbol'] == 'MAX']
    assert any('dust' in reason or 'spam' in reason for reason in real_fetcher.skipped())
    # 1 withdrawal -> 1 pending bridge half; both stakes are deposits, so no reward is split out
    assert len(_bridges(data)) == 1
    assert not _payments(data, JSF.PAYMENT_STAKING_REWARD)
    # The fees the venue charged are carried on their operations: three outgoing sends at 1 USDC each, and the
    # withdrawal's 1 USDC, all in USDC
    send_fees = [t for t in _transfers(data) if t.get('fee', Decimal('0')) > Decimal('0')]
    assert len(send_fees) == 3
    assert all(t['fee'] == Decimal('1') for t in send_fees)


def test_perpetual_fill_is_not_guessed_at(fetcher, hl_account):
    # A perpetuals market is named by a bare ticker and is absent from the spot registry. Perps need an operation
    # JAL doesn't have, so such a fill stops the import rather than being booked as a spot swap.
    fetcher._load_spot_meta()
    with pytest.raises(_HaltImport):
        fetcher._process_fill({"coin": "BTC", "px": "60000", "sz": "1", "side": "B", "fee": "0"}, 0, '0x00')


def test_maker_rebate_is_not_guessed_at(fetcher, hl_account):
    # A negative fee means the account RECEIVED tokens - income, not a cost. There is no honest way to express that
    # as a swap fee, so it waits for a decision instead of being silently dropped.
    fetcher._load_spot_meta()
    with pytest.raises(_HaltImport):
        fetcher._process_fill({"coin": "@142", "px": "60000", "sz": "0.01", "side": "B",
                               "fee": "-0.1", "feeToken": "USDC"}, 0, '0x00')
