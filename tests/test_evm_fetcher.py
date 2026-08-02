import json
from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from constants import PredefinedAccountType, AssetLocation, AccountData, PredefinedAsset, SymbolId, \
    TokenList, TokenListKind
from jal.data_import.statement import JSF
from jal.db.account import JalAccountCreator, JalAccount
from jal.db.symbol import JalSymbol
from jal.db.settings import JalSettings
from jal.db.token_blacklist import JalTokenBlacklist, is_evm_address
from jal.net.chain_fetchers.ethereum import EthereumFetcher
from jal.net.chain_fetchers.fetcher import TransferMark
from jal.net.chain_fetchers.protocols import _REGISTRY, ProtocolCategory, protocol_category, protocol_name
from jal.net.token_lists import TokenListProvider

# A sample wallet used only by the recorded fixtures - never the address of a real user (see the note in
# tests/local_test_data.json.example on why an on-chain address must not be committed). The USDC contract is the
# real mainnet one, allow-listed below so its transfers survive the spam filter the way a real import would.
WALLET = "0x1111111111111111111111111111111111111111"
USDC_CONTRACT = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
SPAM_CONTRACT = "0x9999999999999999999999999999999999999999"

_FIXTURE = {"txlist": "eth_txlist.json", "tokentx": "eth_tokentx.json", "txlistinternal": "eth_internal.json"}

ARB_WALLET = "0x3333333333333333333333333333333333333333"


@pytest.fixture
def arb_wallet(prepare_db):
    JalSettings().setValue("ApiKey_Etherscan", "test-key")
    TokenListProvider()._store(TokenList.UNISWAP_DEFAULT, TokenListKind.Allow, AssetLocation.ARB_BLOCKCHAIN,
                               [{'address': USDC_CONTRACT, 'symbol': 'USDT0', 'name': 'USD T0'}])
    yield JalAccountCreator(currency_id=2, number='', name='ARB wallet', investing=1, organization=1,
                            account_type=PredefinedAccountType.Wallet, address=ARB_WALLET,
                            chain=AssetLocation.ARB_BLOCKCHAIN).commit()


def _drive_arb(account, monkeypatch, pages):
    from jal.net.chain_fetchers.arbitrum import ArbitrumFetcher

    def fake_pages(self, action, start_block):
        return [r for r in pages.get(action, []) if int(r['blockNumber']) >= start_block]
    monkeypatch.setattr(ArbitrumFetcher, "_get_pages", fake_pages)
    fetcher = ArbitrumFetcher()
    return fetcher, fetcher.fetch(account)


@pytest.fixture
def eth_wallet(prepare_db):
    JalSettings().setValue("ApiKey_Etherscan", "test-key")
    # A wallet receives real tokens from addresses it never dealt with, and JAL has no quote for a token it has
    # never seen - which is exactly the shape of a dust airdrop. The allow-list is what tells the two apart.
    TokenListProvider()._store(TokenList.UNISWAP_DEFAULT, TokenListKind.Allow, AssetLocation.ETH_BLOCKCHAIN,
                               [{'address': USDC_CONTRACT, 'symbol': 'USDC', 'name': 'USD Coin'}])
    account = JalAccountCreator(currency_id=2, number='', name='ETH wallet', investing=1, organization=1,
                                account_type=PredefinedAccountType.Wallet, address=WALLET,
                                chain=AssetLocation.ETH_BLOCKCHAIN).commit()
    assert account.id() == 1
    yield account


# Replaces the network with the recorded Etherscan answers. Returns the fetcher plus the list of (action, start_block)
# requests, so a test may assert on the block cursor that was sent.
@pytest.fixture
def fetcher(eth_wallet, data_path, monkeypatch):
    calls = []

    def fake_pages(self, action, start_block):
        calls.append((action, start_block))
        with open(data_path + _FIXTURE[action], 'r', encoding='utf-8') as f:
            result = json.load(f)['result']
        # The real API filters server-side by startblock; the recorded answer is filtered here instead
        return [x for x in result if int(x.get('blockNumber', 0)) >= start_block]

    monkeypatch.setattr(EthereumFetcher, "_get_pages", fake_pages)
    instance = EthereumFetcher()
    instance.calls = calls
    yield instance


def _transfers(data) -> list:
    return data[JSF.TRANSFERS]


def _swaps(data) -> list:
    return data.get(JSF.SWAPS, [])


def _bridges(data) -> list:
    return data.get(JSF.BRIDGES, [])


def _conversions(data) -> list:
    return data.get(JSF.CONVERSIONS, [])


def _eth_symbol_ids(data) -> list:
    return [s['id'] for a in data[JSF.ASSETS] for s in a[JSF.SYMBOLS] if s['symbol'] == 'ETH']


def _usdc_symbol_ids(data) -> list:
    return [s['id'] for a in data[JSF.ASSETS] for s in a[JSF.SYMBOLS] if s['symbol'] == 'USDC']


# Minimal Etherscan-shaped records, so a test can drive the classifier with a hand-built transaction history.
def _tx(tx_hash, block, frm, to, value=0, gas_used='21000', gas_price='1000000000', is_error='0', method='0x'):
    return {'hash': tx_hash, 'blockNumber': str(block), 'transactionIndex': '0', 'timeStamp': '1758800000',
            'from': frm, 'to': to, 'value': str(value), 'gasUsed': gas_used, 'gasPrice': gas_price,
            'isError': is_error, 'methodId': method}


def _token_tx(tx_hash, block, frm, to, value, contract=USDC_CONTRACT, symbol='USDC', name='USD Coin', decimals='6'):
    return {'hash': tx_hash, 'blockNumber': str(block), 'transactionIndex': '0', 'timeStamp': '1758800000',
            'from': frm, 'to': to, 'value': str(value), 'contractAddress': contract, 'tokenSymbol': symbol,
            'tokenName': name, 'tokenDecimal': decimals}


def _internal_tx(tx_hash, block, frm, to, value):
    return {'hash': tx_hash, 'blockNumber': str(block), 'transactionIndex': '0', 'timeStamp': '1758800000',
            'from': frm, 'to': to, 'value': str(value), 'isError': '0'}


# Runs a fresh EthereumFetcher against a hand-built {action: [records]} history and returns the assembled JSF.
def _drive(eth_wallet, monkeypatch, pages):
    from jal.net.chain_fetchers.ethereum import EthereumFetcher as _EF

    def fake_pages(self, action, start_block):
        return [r for r in pages.get(action, []) if int(r['blockNumber']) >= start_block]
    monkeypatch.setattr(_EF, "_get_pages", fake_pages)
    fetcher = _EF()
    data = fetcher.fetch(eth_wallet)
    return fetcher, data


# ----------------------------------------------------------------------------------------------------------------------
def test_fetch_builds_transfers(fetcher, eth_wallet):
    data = fetcher.fetch(eth_wallet)
    # Plain transfers only: 2 native (a send + a receive), 2 USDC (a send + a receive) and 1 internal native deposit.
    # The two swap transactions are no longer split into transfers - they become Swap operations (see the swap test).
    assert len(_transfers(data)) == 5
    for transfer in _transfers(data):
        assert transfer['withdrawal'] > Decimal('0')               # a real quantity moved
        # 'deposit' is the cost basis in the destination currency, which the fetcher cannot know - left 0 for the
        # user to complete once the counterparty account (and thus its currency) is chosen during import.
        assert transfer['deposit'] == Decimal('0')
        assert transfer['account'].count(0) == 1                   # exactly one side is outside JAL
        assert transfer['number']                                  # the tx hash is always recorded


def test_token_carries_contract_address(fetcher, eth_wallet):
    data = fetcher.fetch(eth_wallet)
    usdc = [a for a in data[JSF.ASSETS] if a['type'] == JSF.ASSET_CRYPTO and a[JSF.SYMBOLS][0]['symbol'] == 'USDC']
    assert len(usdc) == 1
    symbol = usdc[0][JSF.SYMBOLS][0]
    # The contract address identifies the token - the ticker is attacker-controlled and never trusted
    assert symbol['address'] == USDC_CONTRACT
    assert symbol['location'] == AssetLocation.ETH_BLOCKCHAIN


def test_gas_is_attached_to_outgoing_transfers_only(fetcher, eth_wallet):
    data = fetcher.fetch(eth_wallet)
    eth_symbols = _eth_symbol_ids(data)
    outgoing_with_fee = [t for t in _transfers(data) if t['account'][0] == 1 and t['fee'] > Decimal('0')]
    assert len(outgoing_with_fee) == 2          # a native send and a USDC send each paid gas (the swaps are separate)
    for transfer in outgoing_with_fee:
        assert transfer['fee_symbol'] in eth_symbols    # gas is always burned in ETH, whatever asset moved
        assert transfer['account'][2] == 1              # and always by the wallet being fetched
    # Incoming transfers never carry gas - the sender paid it
    assert all(t['fee'] == Decimal('0') for t in _transfers(data) if t['account'][0] == 0)


def test_gas_only_calls_become_gas_fees(fetcher, eth_wallet):
    data = fetcher.fetch(eth_wallet)
    gas = [p for p in data[JSF.ASSET_PAYMENTS] if p['type'] == JSF.PAYMENT_GAS_FEE]
    # The approve() and the reverted transaction both moved nothing but still burned gas
    assert len(gas) == 2
    by_note = {p['description']: p for p in gas}
    assert any('approval' in note.lower() for note in by_note)
    assert any('failed' in note.lower() for note in by_note)
    for payment in gas:
        assert payment['amount'] > Decimal('0')


def test_failed_transaction_makes_no_transfer(fetcher, eth_wallet):
    data = fetcher.fetch(eth_wallet)
    # The reverted transaction carried a value, but it never actually moved, so no transfer is created for it
    assert not any(t['number'].startswith('0xddd') for t in _transfers(data))
    gas = [p for p in data[JSF.ASSET_PAYMENTS] if p['number'].startswith('0xddd')]
    assert len(gas) == 1 and 'failed' in gas[0]['description'].lower()


def test_incoming_internal_native_is_imported(fetcher, eth_wallet):
    data = fetcher.fetch(eth_wallet)
    # A 0.002791 ETH deposit from a contract (an internal transfer) - well above the 0.0001 ETH dust threshold, so
    # it is a plain transfer, not a DustAttack payment (see test_native_dust_is_recorded_as_dust_attack for that).
    deposit = [t for t in _transfers(data) if t['number'].startswith('0x444')]
    assert len(deposit) == 1
    assert deposit[0]['withdrawal'] == Decimal('0.002791')
    assert deposit[0]['account'][0] == 0        # incoming


def test_native_dust_is_recorded_as_dust_attack(eth_wallet, monkeypatch):
    DUST_SENDER = "0x2222222222222222222222222222222222222222"
    # 10_000 wei = 1E-14 ETH, far under the 0.0000001 ETH (100 gwei) default threshold - address-poisoning dust,
    # sent from an address the wallet never dealt with, and not a transaction the wallet itself signed (own=False,
    # no gas). The amount is stated in wei on purpose: the threshold is set on the base-unit scale, not on what the
    # send is worth in fiat, so a fixture that means "negligible" has to be negligible in wei.
    pages = {"txlist": [_tx('0xdust', 100, DUST_SENDER, WALLET, value=10_000)],
            "tokentx": [], "txlistinternal": []}
    _, data = _drive(eth_wallet, monkeypatch, pages)
    assert _transfers(data) == []                     # never an ordinary Transfer implying a real counterparty...
    dust = [p for p in data[JSF.ASSET_PAYMENTS] if p['type'] == JSF.PAYMENT_DUST_ATTACK]
    assert len(dust) == 1                              # ...it is recorded as a DustAttack payment instead
    assert dust[0]['amount'] == Decimal('1E-14')


def test_native_dust_does_not_disrupt_a_real_transfer_in_the_same_block(eth_wallet, monkeypatch):
    DUST_SENDER = "0x2222222222222222222222222222222222222222"
    REAL_SENDER = "0x3333333333333333333333333333333333333333"
    pages = {"txlist": [_tx('0xdust', 100, DUST_SENDER, WALLET, value=10_000),                      # 1E-14 ETH
                        _tx('0xreal', 100, REAL_SENDER, WALLET, value=1_000_000_000_000_000_000)],  # 1 ETH
            "tokentx": [], "txlistinternal": []}
    _, data = _drive(eth_wallet, monkeypatch, pages)
    assert len(_transfers(data)) == 1
    assert _transfers(data)[0]['withdrawal'] == Decimal('1')
    dust = [p for p in data[JSF.ASSET_PAYMENTS] if p['type'] == JSF.PAYMENT_DUST_ATTACK]
    assert len(dust) == 1


# The rule is judged on the RAW COIN AMOUNT against the chain's own threshold, never on a fiat value - it needs no
# price data and so is never accidentally inert (see the discussion behind the redesign).
#
# The bounds are derived from the threshold in force instead of being written out as numbers. A literal here
# restates EVMFetcher.native_dust_threshold, and goes on asserting the old figure once that default is retuned or
# the user edits the 'DustThreshold_ETH' setting - which is exactly how this test came to disagree with the code it
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


def test_spam_token_is_quarantined(fetcher, eth_wallet):
    data = fetcher.fetch(eth_wallet)
    # An unsolicited token from an unknown address, unpriced and not on any allow-list, is exactly what a dust
    # airdrop looks like: it must become no asset even though it calls itself 'USDC'.
    assert all(s.get('address') != SPAM_CONTRACT for a in data[JSF.ASSETS] for s in a[JSF.SYMBOLS])
    assert JalTokenBlacklist.is_blacklisted(AssetLocation.ETH_BLOCKCHAIN, SPAM_CONTRACT)
    assert any('dust' in reason or 'spam' in reason for reason in fetcher.skipped())


def test_cursor_is_used_and_advanced(fetcher, eth_wallet):
    fetcher.fetch(eth_wallet)
    assert fetcher.calls[0][1] == 0             # nothing fetched before, so the whole history from block 0

    fetcher.import_fetched()
    cursor = JalAccount(1).get_data(AccountData.SyncCursor)
    assert cursor and int(cursor) > 0

    # A second run asks only for what happened after the stored block, and finds nothing new
    again = EthereumFetcher()
    again.calls = fetcher.calls
    data = again.fetch(JalAccount(1))
    assert again.calls[-1][1] == int(cursor) + 1
    assert _transfers(data) == []


def test_second_import_is_idempotent(fetcher, eth_wallet):
    fetcher.fetch(eth_wallet)
    fetcher.import_fetched()
    first = len(JalAccount(1).dump_transfers())

    again = EthereumFetcher()
    again.fetch(JalAccount(1))
    again.import_fetched()
    # The cursor makes the second run see nothing, so no operation is duplicated
    assert len(JalAccount(1).dump_transfers()) == first


def test_import_creates_assets_with_address(fetcher, eth_wallet):
    fetcher.fetch(eth_wallet)
    fetcher.import_fetched()

    usdc = JalSymbol.find_by_identifier(SymbolId.ETH_ADDRESS, USDC_CONTRACT)
    assert usdc.id()
    assert usdc.symbol() == 'USDC'
    assert usdc.location() == AssetLocation.ETH_BLOCKCHAIN
    assert usdc.asset().type() == PredefinedAsset.Crypto


def test_native_asset_is_eth_without_address(fetcher, eth_wallet):
    data = fetcher.fetch(eth_wallet)
    eth = [a for a in data[JSF.ASSETS] if a[JSF.SYMBOLS][0]['symbol'] == 'ETH']
    assert len(eth) == 1
    assert 'address' not in eth[0][JSF.SYMBOLS][0]           # the native coin has no contract behind it
    assert eth[0]['name'] == 'Ethereum'


def test_transfer_notes_carry_arrow(fetcher, eth_wallet):
    data = fetcher.fetch(eth_wallet)
    with_party = [t for t in _transfers(data) if t.get('description')]
    assert with_party
    for transfer in with_party:
        assert ' → ' in transfer['description']


def test_zero_amount_token_transfer_is_skipped(fetcher, eth_wallet):
    data = fetcher.fetch(eth_wallet)
    # A zero-value ERC-20 Transfer event (hash 0x666...) carries no operation and must not become a transfer
    assert not any(t['number'].startswith('0x666') for t in _transfers(data))
    assert any('zero-amount' in reason for reason in fetcher.skipped())


def test_spoofed_outgoing_token_is_quarantined(fetcher, eth_wallet):
    data = fetcher.fetch(eth_wallet)
    # A fake-USDT (contract 0x8888...) 'sent' by the wallet in a transaction the wallet never initiated: a scam
    # contract emitted a Transfer event that merely names the wallet as sender. The shared filter never treats an
    # outgoing transfer as dust, so provenance is what stops it - the wallet did not sign this transaction.
    assert not any(t['number'].startswith('0x555') for t in _transfers(data))
    assert all(s.get('address') != "0x8888888888888888888888888888888888888888"
               for a in data[JSF.ASSETS] for s in a[JSF.SYMBOLS])
    assert JalTokenBlacklist.is_blacklisted(AssetLocation.ETH_BLOCKCHAIN,
                                            "0x8888888888888888888888888888888888888888")


# ----------------------------------------------------------------------------------------------------------------------
# Per-transaction classification (the P1 rewrite): a whole transaction becomes one operation.
def test_swaps_are_emitted_for_registered_routers(fetcher, eth_wallet):
    data = fetcher.fetch(eth_wallet)
    swaps = _swaps(data)
    assert len(swaps) == 2
    by_hash = {s['tx_hash'][:5]: s for s in swaps}
    eth_symbols, usdc_symbols = _eth_symbol_ids(data), _usdc_symbol_ids(data)

    # 0x111: ETH -> USDC through CoW (a swap router). One asset out, one in, gas paid in ETH as the fee.
    eth_to_usdc = by_hash['0x111']
    assert eth_to_usdc['out_symbol'] in eth_symbols and eth_to_usdc['out_qty'] == Decimal('0.3')
    assert eth_to_usdc['in_symbol'] in usdc_symbols and eth_to_usdc['in_qty'] == Decimal('900')
    assert eth_to_usdc['fee_symbol'] in eth_symbols
    assert eth_to_usdc['fee_qty'] == Decimal('120000') * Decimal('1000000000') / Decimal('10') ** 18

    # 0x222: USDC -> ETH through LI.FI (an aggregator). Both legs are on this chain, so it is a swap, not a bridge,
    # and its single gas charge lands once as the fee - never double-counted across the two legs.
    usdc_to_eth = by_hash['0x222']
    assert usdc_to_eth['out_symbol'] in usdc_symbols and usdc_to_eth['out_qty'] == Decimal('800')
    assert usdc_to_eth['in_symbol'] in eth_symbols and usdc_to_eth['in_qty'] == Decimal('0.2')
    assert usdc_to_eth['fee_qty'] == Decimal('130000') * Decimal('1000000000') / Decimal('10') ** 18


def test_swap_through_0x_allowance_holder_is_recognized(eth_wallet, monkeypatch):
    allowance_holder = "0x0000000000001ff3684f28c67538d4d072c22734"   # 0x Protocol AllowanceHolder
    a1 = "0xa1" + "0" * 62
    pages = {
        "txlist": [_tx(a1, 100, WALLET, allowance_holder, value=3 * 10 ** 17)],  # 0.3 ETH out
        "tokentx": [_token_tx(a1, 100, allowance_holder, WALLET, 900 * 10 ** 6)],  # 900 USDC in
        "txlistinternal": [],
    }
    fetcher, data = _drive(eth_wallet, monkeypatch, pages)

    assert not fetcher.skipped()
    swaps = _swaps(data)
    assert len(swaps) == 1
    eth_symbols, usdc_symbols = _eth_symbol_ids(data), _usdc_symbol_ids(data)
    assert swaps[0]['out_symbol'] in eth_symbols and swaps[0]['out_qty'] == Decimal('0.3')
    assert swaps[0]['in_symbol'] in usdc_symbols and swaps[0]['in_qty'] == Decimal('900')


# ----------------------------------------------------------------------------------------------------------------------
# An intent-based DEX settles GASLESSLY: the order is signed off-chain and a solver submits the batch, so the wallet is
# neither the 'from' nor the 'to' of the transaction and shows up only in its token legs. The classifier used to read
# the protocol off the wallet's own record, found none, and booked the exchange as two plain transfers.
COW = "0x9008d19f58aabd9ed0d60971565aa8510560ab41"      # CoW Protocol GPv2Settlement
SOLVER = "0x8888888888888888888888888888888888888888"   # whoever submitted the batch - never the wallet
FLUID_CONTRACT = "0x6f40d4a6237c257fff2db00fa0510deeecd303eb"


def test_gasless_settlement_is_a_swap_although_the_wallet_never_signed_it(eth_wallet, monkeypatch):
    g1 = "0x91" + "0" * 62
    pages = {
        "txlist": [_tx(g1, 100, SOLVER, COW, value=0)],    # the SOLVER's transaction, not the wallet's
        "tokentx": [_token_tx(g1, 100, WALLET, COW, 800 * 10 ** 6),                          # 800 USDC out ...
                    _token_tx(g1, 100, COW, WALLET, 21 * 10 ** 18, contract=FLUID_CONTRACT,  # ... 21 FLUID in
                              symbol='FLUID', name='Fluid', decimals='18')],
        "txlistinternal": [],
    }
    fetcher, data = _drive(eth_wallet, monkeypatch, pages)

    assert not fetcher.skipped()
    assert _transfers(data) == []            # no longer two unsettled legs waiting for a counterpart that never comes
    swaps = _swaps(data)
    assert len(swaps) == 1
    fluid_symbols = [s['id'] for a in data[JSF.ASSETS] for s in a[JSF.SYMBOLS] if s['symbol'] == 'FLUID']
    assert swaps[0]['out_symbol'] in _usdc_symbol_ids(data) and swaps[0]['out_qty'] == Decimal('800')
    assert swaps[0]['in_symbol'] in fluid_symbols and swaps[0]['in_qty'] == Decimal('21')
    # The wallet paid no gas for it - a fee invented here would be money it never spent
    assert not swaps[0].get('fee_qty') and not swaps[0].get('fee_symbol')


def test_a_gasless_swap_leg_is_not_quarantined_as_spam(eth_wallet, monkeypatch):
    # Both legs of a solver-submitted settlement look 'incoming from an unknown address' to the spam filter, because
    # the wallet signed nothing. The received token is thinly priced and on no allow-list - and it is still the user's
    # own swap, so quarantining it would delete one side of an exchange the user made.
    g2 = "0x92" + "0" * 62
    pages = {
        "txlist": [_tx(g2, 100, SOLVER, COW, value=0)],
        "tokentx": [_token_tx(g2, 100, WALLET, COW, 800 * 10 ** 6),
                    _token_tx(g2, 100, COW, WALLET, 21 * 10 ** 18, contract=FLUID_CONTRACT,
                              symbol='FLUID', name='Fluid', decimals='18')],
        "txlistinternal": [],
    }
    fetcher, data = _drive(eth_wallet, monkeypatch, pages)

    assert not JalTokenBlacklist.is_blacklisted(AssetLocation.ETH_BLOCKCHAIN, FLUID_CONTRACT)
    assert len(_swaps(data)) == 1
    # ... while a token pushed in by an address that is NOT a registered protocol is quarantined exactly as before
    assert JalTokenBlacklist.is_blacklisted(AssetLocation.ETH_BLOCKCHAIN, SPAM_CONTRACT) is False   # not seen here
    assert not fetcher.skipped()


def test_a_settlement_paying_the_native_coin_is_a_swap(eth_wallet, monkeypatch):
    # The received side may be the native coin, which a contract sends as an internal transaction - the shape the
    # wallet's own FLUID -> ETH settlement had.
    g3 = "0x93" + "0" * 62
    pages = {
        "txlist": [_tx(g3, 100, SOLVER, COW, value=0)],
        "tokentx": [_token_tx(g3, 100, WALLET, COW, 800 * 10 ** 6)],          # 800 USDC out ...
        "txlistinternal": [_internal_tx(g3, 100, COW, WALLET, 2 * 10 ** 17)],  # ... 0.2 ETH in
    }
    fetcher, data = _drive(eth_wallet, monkeypatch, pages)

    swaps = _swaps(data)
    assert len(swaps) == 1
    assert swaps[0]['out_symbol'] in _usdc_symbol_ids(data) and swaps[0]['out_qty'] == Decimal('800')
    assert swaps[0]['in_symbol'] in _eth_symbol_ids(data) and swaps[0]['in_qty'] == Decimal('0.2')


def test_movements_with_different_counterparties_are_not_fused_into_a_swap(eth_wallet, monkeypatch):
    # Two unrelated movements that merely share a transaction are NOT an exchange. Only a pair that both moved with
    # one and the same registered protocol is one - this is what keeps the rule from inventing swaps.
    g4 = "0x94" + "0" * 62
    outsider = "0x2222222222222222222222222222222222222222"
    pages = {
        "txlist": [_tx(g4, 100, SOLVER, COW, value=0)],
        "tokentx": [_token_tx(g4, 100, WALLET, COW, 800 * 10 ** 6)],               # USDC out, with the protocol ...
        "txlistinternal": [_internal_tx(g4, 100, outsider, WALLET, 2 * 10 ** 17)],  # ... ETH in, from someone else
    }
    fetcher, data = _drive(eth_wallet, monkeypatch, pages)

    assert _swaps(data) == []
    assert len(_transfers(data)) == 2


def test_an_unregistered_settlement_stays_two_transfers(eth_wallet, monkeypatch):
    # An unknown contract that both takes and gives is not classified by resemblance to a swap. The wallet signed
    # nothing here, so there is nothing to halt over either - it keeps the plain-transfer treatment it had, and the
    # legs surface in the Unsettled transfers report where the user decides what they were.
    g5 = "0x95" + "0" * 62
    unknown = "0x7777777777777777777777777777777777777777"
    pages = {
        "txlist": [_tx(g5, 100, SOLVER, unknown, value=0)],
        "tokentx": [_token_tx(g5, 100, WALLET, unknown, 800 * 10 ** 6)],
        "txlistinternal": [_internal_tx(g5, 100, unknown, WALLET, 2 * 10 ** 17)],
    }
    fetcher, data = _drive(eth_wallet, monkeypatch, pages)

    assert _swaps(data) == []
    assert len(_transfers(data)) == 2


# ----------------------------------------------------------------------------------------------------------------------
# Address poisoning arrives as the GENUINE token, so the spam filter passes it on the allow-list before its value is
# ever weighed, and the amount is trivial only by convention. What gives it away is the sender: an address ground to
# match the wallet's own at both ends, so that it is copied out of the history in place of the real one.
POISONER = "0x1111beef11111111111111111111111111111111"   # WALLET is 0x1111...1111 - both ends agree


def test_poisoning_dust_is_booked_as_an_attack_and_not_as_a_transfer(eth_wallet, monkeypatch):
    p1 = "0xp1".replace('p', 'a') + "0" * 62
    pages = {
        "txlist": [],
        "tokentx": [_token_tx(p1, 100, POISONER, WALLET, 1000)],   # 0.001 USDC - real USDC, from a lookalike
        "txlistinternal": [],
    }
    fetcher, data = _drive(eth_wallet, monkeypatch, pages)

    assert _transfers(data) == []          # it is nobody's half of anything - it must not wait for a sender
    payments = [x for x in data[JSF.ASSET_PAYMENTS] if x['type'] == JSF.PAYMENT_DUST_ATTACK]
    assert len(payments) == 1
    assert payments[0]['amount'] == Decimal('0.001')
    assert 'ETH wallet' in payments[0]['description']       # it names the wallet being imitated
    # The contract is the REAL USDC one - blacklisting it would throw away every future USDC transfer
    assert not JalTokenBlacklist.is_blacklisted(AssetLocation.ETH_BLOCKCHAIN, USDC_CONTRACT)


def test_a_token_from_an_ordinary_address_is_still_a_transfer(eth_wallet, monkeypatch):
    stranger = "0x2222222222222222222222222222222222222222"
    p2 = "0xa2" + "0" * 62
    pages = {
        "txlist": [],
        "tokentx": [_token_tx(p2, 100, stranger, WALLET, 900 * 10 ** 6)],
        "txlistinternal": [],
    }
    fetcher, data = _drive(eth_wallet, monkeypatch, pages)

    assert len(_transfers(data)) == 1
    assert not [x for x in data[JSF.ASSET_PAYMENTS] if x['type'] == JSF.PAYMENT_DUST_ATTACK]


def test_poisoning_dust_does_not_disturb_a_swap_in_the_same_transaction(eth_wallet, monkeypatch):
    # Taken out before the transaction is classified: left among the deltas, a one-out-one-in swap would look like
    # three assets moving and would halt the import instead
    allowance_holder = "0x0000000000001ff3684f28c67538d4d072c22734"
    p3 = "0xa3" + "0" * 62
    pages = {
        "txlist": [_tx(p3, 100, WALLET, allowance_holder, value=3 * 10 ** 17)],
        "tokentx": [_token_tx(p3, 100, allowance_holder, WALLET, 900 * 10 ** 6),
                    _token_tx(p3, 100, POISONER, WALLET, 1000, contract=SPAM_CONTRACT, symbol='USDC',
                              name='USD Coin')],
        "txlistinternal": [],
    }
    fetcher, data = _drive(eth_wallet, monkeypatch, pages)

    assert len(_swaps(data)) == 1
    assert len([x for x in data[JSF.ASSET_PAYMENTS] if x['type'] == JSF.PAYMENT_DUST_ATTACK]) == 1


def test_import_halts_and_checkpoints_at_an_unregistered_exchange(eth_wallet, monkeypatch):
    unknown = "0x7777777777777777777777777777777777777777"
    other = "0x2222222222222222222222222222222222222222"
    a1, b2 = "0xa1" + "0" * 62, "0xb2" + "0" * 62
    pages = {
        "txlist": [_tx(a1, 100, other, WALLET, value=10 ** 18),                       # block 100: incoming ETH (safe)
                   _tx(b2, 101, WALLET, unknown, value=10 ** 18, method='0xabcdef01')],  # block 101: ETH out ...
        "tokentx": [_token_tx(b2, 101, unknown, WALLET, 900 * 10 ** 6)],                 # ... USDC in => A->B, unknown
        "txlistinternal": [],
    }
    fetcher, data = _drive(eth_wallet, monkeypatch, pages)

    # The safe earlier block is imported; the unregistered one-in-one-out transaction is not guessed at, and its whole
    # block is rolled back - no partial swap, no stray transfer.
    assert len(_transfers(data)) == 1 and _transfers(data)[0]['number'] == a1
    assert _swaps(data) == []
    assert not any(s.get('address') == unknown for a in data[JSF.ASSETS] for s in a[JSF.SYMBOLS])
    assert any('stopped' in reason for reason in fetcher.skipped())
    # The cursor is parked before the halting block, so a later fetch re-tries it once the registry catches up.
    assert fetcher._new_cursor == '100'


# ----------------------------------------------------------------------------------------------------------------------
# The registry is hand-edited curated knowledge, and a malformed entry would go unnoticed until an import met that very
# contract - so its shape is checked here: every address maps to a known category AND to a name, because the name is
# what an operation that has to be reconciled by hand quotes in its description.
def test_protocol_registry_entries_are_a_known_category_and_a_name():
    categories = {value for name, value in vars(ProtocolCategory).items() if not name.startswith('_')}
    for location_id, protocols in _REGISTRY.items():
        for address, entry in protocols.items():
            assert isinstance(entry, tuple) and len(entry) == 2, f"{address} is not a (category, name) pair"
            category, name = entry
            assert category in categories, f"{address} has an unknown category {category}"
            assert name and isinstance(name, str), f"{address} has no protocol name"
            # The lookups take the address in whatever case the chain reported it
            assert protocol_category(location_id, address.upper()) == category
            assert protocol_name(location_id, address.upper()) == name
    # An address the registry doesn't hold has neither a category nor a name, and asking is not an error
    assert protocol_category(AssetLocation.ETH_BLOCKCHAIN, SPAM_CONTRACT) is None
    assert protocol_name(AssetLocation.ETH_BLOCKCHAIN, SPAM_CONTRACT) == ''
    assert protocol_name(AssetLocation.ETH_BLOCKCHAIN, '') == ''


# Supplying to a lending protocol keeps the position and only changes its shape, so it is a Conversion - not a swap
# (which would realize a profit that was never made) and not a pair of transfers.
def test_lending_supply_is_emitted_as_a_conversion(eth_wallet, monkeypatch):
    aave = "0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2"     # registered as ProtocolCategory.LENDING
    c3 = "0xc3" + "0" * 62
    pages = {
        "txlist": [_tx(c3, 100, WALLET, aave, value=10 ** 18, gas_used='120000')],   # supply 1 ETH ...
        "tokentx": [_token_tx(c3, 100, aave, WALLET, 1000 * 10 ** 6)],               # ... receive a receipt token
        "txlistinternal": [],
    }
    fetcher, data = _drive(eth_wallet, monkeypatch, pages)

    assert _transfers(data) == [] and _swaps(data) == [] and _bridges(data) == []
    conversions = _conversions(data)
    assert len(conversions) == 1
    conversion = conversions[0]
    assert conversion['out_symbol'] in _eth_symbol_ids(data) and conversion['out_qty'] == Decimal('1')
    assert conversion['in_symbol'] in _usdc_symbol_ids(data) and conversion['in_qty'] == Decimal('1000')
    assert conversion['fee_qty'] == Decimal('120000') * Decimal('1000000000') / Decimal('10') ** 18   # gas is the fee
    assert fetcher.skipped() == {}


# Withdrawing is the same move backwards, and the quantity coming back is free to exceed what was supplied - a
# rebasing receipt token folds the yield accrued since the last interaction into it.
def test_lending_withdrawal_is_emitted_as_a_conversion(eth_wallet, monkeypatch):
    aave = "0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2"
    c4 = "0xc4" + "0" * 62
    pages = {
        "txlist": [_tx(c4, 100, WALLET, aave, value=0, method='0xb61d27f6')],
        "tokentx": [_token_tx(c4, 100, WALLET, aave, 1000 * 10 ** 6)],     # give back the receipt token ...
        "txlistinternal": [_internal_tx(c4, 100, aave, WALLET, 1050 * 10 ** 15)],   # ... receive 1.05 ETH
    }
    fetcher, data = _drive(eth_wallet, monkeypatch, pages)

    conversions = _conversions(data)
    assert len(conversions) == 1
    assert conversions[0]['out_symbol'] in _usdc_symbol_ids(data) and conversions[0]['out_qty'] == Decimal('1000')
    assert conversions[0]['in_symbol'] in _eth_symbol_ids(data) and conversions[0]['in_qty'] == Decimal('1.05')
    assert _transfers(data) == [] and _swaps(data) == []


# A lending protocol may also just pay out, with nothing going the other way - that is a reward, not a conversion.
def test_lending_payout_without_a_counter_leg_is_a_reward(eth_wallet, monkeypatch):
    aave = "0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2"
    c5 = "0xc5" + "0" * 62
    pages = {
        "txlist": [_tx(c5, 100, WALLET, aave, value=0, method='0xb61d27f6')],
        "tokentx": [_token_tx(c5, 100, aave, WALLET, 7 * 10 ** 6)],
        "txlistinternal": [],
    }
    fetcher, data = _drive(eth_wallet, monkeypatch, pages)

    rewards = [p for p in data[JSF.ASSET_PAYMENTS] if p['type'] == JSF.PAYMENT_STAKING_REWARD]
    assert len(rewards) == 1 and rewards[0]['amount'] == Decimal('7')
    assert _conversions(data) == []


# A shape that is neither of the two still halts rather than being guessed at.
def test_unrecognized_lending_shape_halts(eth_wallet, monkeypatch):
    aave = "0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2"
    c6 = "0xc6" + "0" * 62
    other = "0x8888888888888888888888888888888888888888"
    pages = {
        "txlist": [_tx(c6, 100, WALLET, aave, value=10 ** 18)],            # one asset out ...
        "tokentx": [_token_tx(c6, 100, aave, WALLET, 5 * 10 ** 6),         # ... two different ones in
                    _token_tx(c6, 100, aave, WALLET, 3 * 10 ** 6, contract=other, symbol='OTHER', name='Other')],
        "txlistinternal": [],
    }
    fetcher, data = _drive(eth_wallet, monkeypatch, pages)

    assert _conversions(data) == [] and _transfers(data) == [] and _swaps(data) == []
    assert any('lending' in reason for reason in fetcher.skipped())
    assert fetcher._new_cursor == ''                                 # the very first block halted, so no cursor advance


# ----------------------------------------------------------------------------------------------------------------------
# A custody contract holds the asset and gives no receipt token back, so putting money in is a transfer out - the
# position is not disposed of, it just moves to an account the user names during the import.
def test_custody_deposit_is_emitted_as_a_transfer(eth_wallet, monkeypatch):
    pool = "0xddc796a66e8b83d0bccd97df33a6ccfba8fd60ea"    # registered as ProtocolCategory.CUSTODY
    c7 = "0xc7" + "0" * 62
    pages = {
        "txlist": [_tx(c7, 100, WALLET, pool, value=0, method='0xb61d27f6', gas_used='120000')],
        "tokentx": [_token_tx(c7, 100, WALLET, pool, 1000 * 10 ** 6)],
        "txlistinternal": [],
    }
    fetcher, data = _drive(eth_wallet, monkeypatch, pages)

    transfers = _transfers(data)
    assert len(transfers) == 1
    assert transfers[0]['account'] == [1, 0, 1]                    # money leaves the wallet, the peer is asked for
    assert transfers[0]['withdrawal'] == Decimal('1000')
    assert transfers[0]['fee'] == Decimal('120000') * Decimal('1000000000') / Decimal('10') ** 18
    assert _conversions(data) == [] and _swaps(data) == [] and _bridges(data) == []
    assert data.get(JSF.ASSET_PAYMENTS, []) == []                  # nothing was earned, so nothing is booked as income
    assert fetcher.skipped() == {}
    # A transfer is all a custody movement can be recorded as, so the description says so: the untranslated tag makes
    # these findable in the ledger, the protocol name says which position the leg belongs to, and the counterparty
    # note is kept behind them.
    assert transfers[0]['description'].startswith(f"{TransferMark.CUSTODY} stake.link PriorityPool: ")
    assert f"{WALLET} → {pool}" in transfers[0]['description']


# ... and taking it back is a transfer in. This is the whole point of the category: the same asset returning from a
# custody contract is the wallet's own money, so it must not become a reward - and it must not halt the import either.
def test_custody_return_is_a_transfer_not_a_reward(eth_wallet, monkeypatch):
    pool = "0xddc796a66e8b83d0bccd97df33a6ccfba8fd60ea"
    c8 = "0xc8" + "0" * 62
    pages = {
        "txlist": [_tx(c8, 100, WALLET, pool, value=0, method='0xb61d27f6')],
        "tokentx": [_token_tx(c8, 100, pool, WALLET, 1000 * 10 ** 6)],
        "txlistinternal": [],
    }
    fetcher, data = _drive(eth_wallet, monkeypatch, pages)

    transfers = _transfers(data)
    assert len(transfers) == 1
    assert transfers[0]['account'] == [0, 1, 1] and transfers[0]['withdrawal'] == Decimal('1000')
    # The wallet signed the withdrawal, so its gas is charged - but nothing here is income
    assert [p['type'] for p in data.get(JSF.ASSET_PAYMENTS, [])] == [JSF.PAYMENT_GAS_FEE]
    assert fetcher.skipped() == {} and fetcher._new_cursor == '100'
    assert transfers[0]['description'].startswith(f"{TransferMark.CUSTODY} stake.link PriorityPool: ")


# A protocol reached through the token instead of being called: an ERC-677 transferAndCall() names the TOKEN as the
# contract the wallet interacted with, so the registry lookup on it finds nothing - while the coins went to a
# registered custody pool all the same. This is how LINK is queued into stake.link, and the wallet's own history had
# four such sends recorded as bare transfers while the withdrawals (which call the pool directly) carried the mark.
def test_protocol_reached_through_a_token_is_recognized(eth_wallet, monkeypatch):
    pool = "0xddc796a66e8b83d0bccd97df33a6ccfba8fd60ea"      # registered as ProtocolCategory.CUSTODY
    link = "0x514910771af9ca656af840dff83e8264ecf986ca"      # ... and the token is deliberately NOT registered
    ca = "0xca" + "0" * 62
    pages = {
        # The wallet calls the TOKEN (transferAndCall), and the token moves the coins on to the pool
        "txlist": [_tx(ca, 100, WALLET, link, value=0, method='0x4000aea0')],
        "tokentx": [_token_tx(ca, 100, WALLET, pool, 15 * 10 ** 18, contract=link, symbol='LINK',
                              name='ChainLink Token', decimals='18')],
        "txlistinternal": [],
    }
    fetcher, data = _drive(eth_wallet, monkeypatch, pages)

    transfers = _transfers(data)
    assert len(transfers) == 1
    assert transfers[0]['account'] == [1, 0, 1] and transfers[0]['withdrawal'] == Decimal('15')
    assert transfers[0]['description'].startswith(f"{TransferMark.CUSTODY} stake.link PriorityPool: ")
    assert _conversions(data) == [] and _swaps(data) == [] and _bridges(data) == []
    assert fetcher.skipped() == {}


# The same deduction must not reach a transaction that gives something back: what came in is what tells a purchase
# from a deposit, and the contract the user CHOSE to call is what says which it was. Here the wallet sends a token
# to the custody pool and is paid another one in the same transaction, through a contract that names no protocol -
# so nothing is resolved and the transaction halts naming its contract, exactly as it did before the deduction
# existed. Silently booking it as custody would record a purchase as a deposit into a box.
def test_forwarding_deduction_ignores_a_transaction_that_pays_back(eth_wallet, monkeypatch):
    pool = "0xddc796a66e8b83d0bccd97df33a6ccfba8fd60ea"
    link = "0x514910771af9ca656af840dff83e8264ecf986ca"
    cb = "0xcb" + "0" * 62
    pages = {
        "txlist": [_tx(cb, 100, WALLET, link, value=0, method='0x4000aea0')],
        "tokentx": [_token_tx(cb, 100, WALLET, pool, 15 * 10 ** 18, contract=link, symbol='LINK',
                              name='ChainLink Token', decimals='18'),
                    _token_tx(cb, 100, pool, WALLET, 1000 * 10 ** 6)],
        "txlistinternal": [],
    }
    fetcher, data = _drive(eth_wallet, monkeypatch, pages)

    assert _transfers(data) == [] and _conversions(data) == [] and _swaps(data) == []
    assert any('unregistered contract' in reason for reason in fetcher.skipped())


# A custody contract that hands something back in exchange isn't holding the asset any more - that shape is a
# conversion or a swap and must be classified as one, so it halts instead of being flattened into two transfers.
def test_custody_exchange_shape_halts(eth_wallet, monkeypatch):
    pool = "0xddc796a66e8b83d0bccd97df33a6ccfba8fd60ea"
    c9 = "0xc9" + "0" * 62
    pages = {
        "txlist": [_tx(c9, 100, WALLET, pool, value=10 ** 18)],
        "tokentx": [_token_tx(c9, 100, pool, WALLET, 1000 * 10 ** 6)],
        "txlistinternal": [],
    }
    fetcher, data = _drive(eth_wallet, monkeypatch, pages)

    assert _transfers(data) == [] and _conversions(data) == [] and _swaps(data) == []
    assert any('custody' in reason for reason in fetcher.skipped())
    assert fetcher._new_cursor == ''


def test_bridge_send_is_emitted_as_a_pending_send_half(eth_wallet, monkeypatch):
    lifi = "0x1231deb6f5749ef6ce6943a275a1d3e7486f4eae"     # registered AGGREGATOR; a single leg -> a bridge
    e5 = "0xe5" + "0" * 62
    pages = {
        "txlist": [_tx(e5, 100, WALLET, lifi, value=2 * 10 ** 18, gas_used='120000')],   # send 2 ETH into the bridge
        "tokentx": [],
        "txlistinternal": [],
    }
    fetcher, data = _drive(eth_wallet, monkeypatch, pages)

    assert _swaps(data) == [] and _transfers(data) == []     # not a swap, not a plain transfer
    halves = _bridges(data)
    assert len(halves) == 1
    half = halves[0]
    assert half['qty'] == Decimal('2')                                 # the sending leg only
    assert half['symbol'] in _eth_symbol_ids(data)
    assert half['fee_qty'] == Decimal('120000') * Decimal('1000000000') / Decimal('10') ** 18   # gas rides the send
    # A pending half is an operation of its own kind and needs no mark, but it names the protocol it went through -
    # that is what lets the user recognize its counterpart among the candidates the matcher offers
    assert 'LI.FI Diamond (Jumper)' in half['description']


# The ARRIVING leg of a cross-chain move is never recognized as such: nothing in it says what was sent from the other
# chain (or even whether the asset changed on the way), so it is imported as a plain incoming transfer - the same way a
# relayer-delivered arrival is - and the user pairs it with its pending sending half by hand.
# A LayerZero OFT (USDT0 and its kind) charges for delivering the message in native coin, sent to the very contract
# the asset is bridged through, in the same transaction. On-chain that is two assets leaving at once - and one asset
# out is what a crossing is, so without recognizing the fee every such send would halt the import.
def test_a_bridge_messaging_fee_is_charged_and_does_not_break_the_shape(eth_wallet, monkeypatch):
    usdt0 = "0x6c96de32cea08842dcc4058c14d3aaad7fa41dee"      # USDT0 OFT Adapter, a registered BRIDGE
    m1 = "0xb1" + "0" * 62
    pages = {
        "txlist": [_tx(m1, 100, WALLET, usdt0, value=31344835695747, gas_used='120000')],   # the LZ messaging fee
        "tokentx": [_token_tx(m1, 100, WALLET, usdt0, 5553699)],                            # 5.553699 USDC bridged
        "txlistinternal": [],
    }
    fetcher, data = _drive(eth_wallet, monkeypatch, pages)

    assert not fetcher.skipped()               # it must not halt on "two assets out"
    bridges = _bridges(data)
    assert len(bridges) == 1
    assert bridges[0]['symbol'] in _usdc_symbol_ids(data)
    assert bridges[0]['qty'] == Decimal('5.553699')           # what crosses is the token, whole
    assert _transfers(data) == []                             # the fee is not a movement of its own
    # ... it is charged with the gas, in the native coin, exactly as gas itself is
    gas = Decimal('120000') * Decimal('1000000000') / Decimal('10') ** 18
    assert bridges[0]['fee_qty'] == gas + Decimal('31344835695747') / Decimal('10') ** 18
    assert bridges[0]['fee_symbol'] in _eth_symbol_ids(data)
    assert 'USDT0 OFT Adapter' in bridges[0]['description']


def test_native_coin_sent_elsewhere_is_not_taken_as_a_messaging_fee(eth_wallet, monkeypatch):
    # Only what went to the bridge contract itself is its fee; native coin to anyone else is a movement of its own,
    # and a transaction doing both is a shape nothing here may guess at
    usdt0 = "0x6c96de32cea08842dcc4058c14d3aaad7fa41dee"
    stranger = "0x2222222222222222222222222222222222222222"
    m2 = "0xb2" + "0" * 62
    pages = {
        "txlist": [_tx(m2, 100, WALLET, usdt0, value=0)],
        "tokentx": [_token_tx(m2, 100, WALLET, usdt0, 5553699)],
        "txlistinternal": [_internal_tx(m2, 100, WALLET, stranger, 31344835695747)],
        }
    fetcher, data = _drive(eth_wallet, monkeypatch, pages)

    assert _bridges(data) == []
    assert any('stopped' in reason for reason in fetcher.skipped())


# ... and neither is it a fee when the wallet paid the bridge AND somebody else in the same transaction: the fee is
# what went to the contract, and nothing here can say how much of the two that was.
def test_native_coin_sent_to_the_bridge_and_elsewhere_is_not_taken_as_a_messaging_fee(eth_wallet, monkeypatch):
    usdt0 = "0x6c96de32cea08842dcc4058c14d3aaad7fa41dee"
    stranger = "0x2222222222222222222222222222222222222222"
    m3 = "0xb3" + "0" * 62
    pages = {
        "txlist": [_tx(m3, 100, WALLET, usdt0, value=31344835695747)],
        "tokentx": [_token_tx(m3, 100, WALLET, usdt0, 5553699)],
        "txlistinternal": [_internal_tx(m3, 100, WALLET, stranger, 5000000000000)],
        }
    fetcher, data = _drive(eth_wallet, monkeypatch, pages)

    assert _bridges(data) == []
    assert any('stopped' in reason for reason in fetcher.skipped())


# The fee is quoted before the transaction runs, so the wallet has to cover it in full and the protocol refunds
# whatever it did not spend - a LayerZero OFT out of its ENDPOINT, which is not the adapter the asset was bridged
# through. Two addresses then take part in the native delta, which is what clears its net counterparty
# (_merge_counterparty), and judging the fee by that counterparty refused the send outright - halting the import of
# the very shape this rule exists to accept, and telling a refunded send apart from an unrefunded one by nothing that
# concerns the user.
def test_a_refunded_messaging_fee_is_still_recognized(eth_wallet, monkeypatch):
    usdt0 = "0x6c96de32cea08842dcc4058c14d3aaad7fa41dee"      # USDT0 OFT Adapter, a registered BRIDGE
    endpoint = "0x1a44076050125825900e736c501f859c50fe728c"   # LayerZero EndpointV2, which pays the refund back
    m4 = "0xb4" + "0" * 62
    pages = {
        "txlist": [_tx(m4, 100, WALLET, usdt0, value=23358479028892, gas_used='120000')],   # the quoted fee
        "tokentx": [_token_tx(m4, 100, WALLET, usdt0, 5553699)],                            # 5.553699 USDC bridged
        "txlistinternal": [_internal_tx(m4, 100, endpoint, WALLET, 15320000000)],           # ... its unspent part
    }
    fetcher, data = _drive(eth_wallet, monkeypatch, pages)

    assert not fetcher.skipped()               # it must not halt on "two assets out"
    bridges = _bridges(data)
    assert len(bridges) == 1
    assert bridges[0]['symbol'] in _usdc_symbol_ids(data)
    assert bridges[0]['qty'] == Decimal('5.553699')           # what crosses is the token, whole
    assert _transfers(data) == []                             # neither the fee nor its refund is a movement of its own
    # What is charged is the fee that was really paid - the quote net of what came back - together with the gas
    gas = Decimal('120000') * Decimal('1000000000') / Decimal('10') ** 18
    paid = (Decimal('23358479028892') - Decimal('15320000000')) / Decimal('10') ** 18
    assert bridges[0]['fee_qty'] == gas + paid
    assert bridges[0]['fee_symbol'] in _eth_symbol_ids(data)


def test_a_bridge_send_of_the_native_coin_alone_still_crosses(eth_wallet, monkeypatch):
    # The guard that keeps the fee rule from eating the asset: when native coin is all that left, it IS what crosses
    usdt0 = "0x6c96de32cea08842dcc4058c14d3aaad7fa41dee"
    m3 = "0xb3" + "0" * 62
    pages = {
        "txlist": [_tx(m3, 100, WALLET, usdt0, value=2 * 10 ** 17, gas_used='120000')],
        "tokentx": [], "txlistinternal": [],
    }
    fetcher, data = _drive(eth_wallet, monkeypatch, pages)

    bridges = _bridges(data)
    assert len(bridges) == 1
    assert bridges[0]['symbol'] in _eth_symbol_ids(data) and bridges[0]['qty'] == Decimal('0.2')


def test_bridge_receive_via_own_tx_is_emitted_as_a_plain_transfer(eth_wallet, monkeypatch):
    lifi = "0x1231deb6f5749ef6ce6943a275a1d3e7486f4eae"
    f6 = "0xf6" + "0" * 62
    pages = {
        "txlist": [_tx(f6, 100, WALLET, lifi, value=0, gas_used='90000', method='0xb61d27f6')],   # claim on dest chain
        "tokentx": [_token_tx(f6, 100, lifi, WALLET, 900 * 10 ** 6)],                             # receive 900 USDC
        "txlistinternal": [],
    }
    fetcher, data = _drive(eth_wallet, monkeypatch, pages)

    assert _bridges(data) == []                                        # no pending half is created by an arrival
    transfers = _transfers(data)
    assert len(transfers) == 1 and transfers[0]['withdrawal'] == Decimal('900')
    assert transfers[0]['account'][0] == 0                              # incoming: the source account is unknown
    assert any(p['type'] == JSF.PAYMENT_GAS_FEE for p in data[JSF.ASSET_PAYMENTS])   # its own claim gas is charged
    # ... and the transfer says that this is what it is, so the pending half it belongs to can be found by hand
    assert transfers[0]['description'].startswith(f"{TransferMark.BRIDGE} LI.FI Diamond (Jumper): ")


def test_reward_claim_is_booked_as_a_staking_reward(eth_wallet, monkeypatch):
    merkl = "0x3ef3d8ba38ebe18db133cec108f4d14ce00dd9ae"     # registered as ProtocolCategory.REWARD
    d4 = "0xd4" + "0" * 62
    pages = {
        "txlist": [_tx(d4, 100, WALLET, merkl, value=0, method='0xb61d27f6')],   # claim ...
        "tokentx": [_token_tx(d4, 100, merkl, WALLET, 50 * 10 ** 6)],            # ... 50 USDC reward
        "txlistinternal": [],
    }
    fetcher, data = _drive(eth_wallet, monkeypatch, pages)

    rewards = [p for p in data[JSF.ASSET_PAYMENTS] if p['type'] == JSF.PAYMENT_STAKING_REWARD]
    assert len(rewards) == 1 and rewards[0]['amount'] == Decimal('50')
    assert any(p['type'] == JSF.PAYMENT_GAS_FEE for p in data[JSF.ASSET_PAYMENTS])   # the claim's gas is charged too
    assert _transfers(data) == [] and _swaps(data) == []


# One claim can pay out in several assets at once - a real Merkl claim delivered stkGHO and aEthUSDG together - so
# each received asset becomes a reward of its own instead of the whole claim halting the import.
def test_reward_claim_of_several_assets_pays_each_one(eth_wallet, monkeypatch):
    merkl = "0x3ef3d8ba38ebe18db133cec108f4d14ce00dd9ae"
    other = "0x8888888888888888888888888888888888888888"
    d5 = "0xd5" + "0" * 62
    pages = {
        "txlist": [_tx(d5, 100, WALLET, merkl, value=0, method='0xb61d27f6')],
        "tokentx": [_token_tx(d5, 100, merkl, WALLET, 46 * 10 ** 6),
                    _token_tx(d5, 100, merkl, WALLET, 23 * 10 ** 6, contract=other, symbol='OTHER', name='Other')],
        "txlistinternal": [],
    }
    fetcher, data = _drive(eth_wallet, monkeypatch, pages)

    rewards = [p for p in data[JSF.ASSET_PAYMENTS] if p['type'] == JSF.PAYMENT_STAKING_REWARD]
    assert sorted(p['amount'] for p in rewards) == [Decimal('23'), Decimal('46')]
    assert len({p['symbol'] for p in rewards}) == 2                     # one payment per received asset
    assert fetcher.skipped() == {}


# ----------------------------------------------------------------------------------------------------------------------
def test_is_evm_address_accepts_valid_and_rejects_malformed():
    assert is_evm_address(WALLET)
    assert is_evm_address("0xA0b86991c6218B36c1d19D4a2e9Eb0cE3606eB48")   # checksummed casing is accepted
    assert not is_evm_address("")
    assert not is_evm_address("0x123")                                    # too short
    assert not is_evm_address("1111111111111111111111111111111111111111")  # missing 0x
    assert not is_evm_address("0xZZZ6991c6218b36c1d19d4a2e9eb0ce3606eb48")  # non-hex


def test_counterparty_note_only_for_unknown_addresses(fetcher, eth_wallet):
    fetcher._account = eth_wallet
    external = "0x2222222222222222222222222222222222222222"
    # An outside counterparty is recorded, sender first, so the user can identify it
    assert fetcher._counterparty_note({'from': WALLET, 'to': external}) == f"{WALLET} → {external}"
    assert fetcher._counterparty_note({'from': external, 'to': WALLET}) == f"{external} → {WALLET}"


def test_counterparty_note_empty_between_known_wallets(fetcher, eth_wallet):
    # A second wallet the user owns: a transfer between two known accounts needs no address note
    other = "0x5555555555555555555555555555555555555555"
    JalAccountCreator(currency_id=2, number='', name='ETH wallet 2', investing=1, organization=1,
                      account_type=PredefinedAccountType.Wallet, address=other,
                      chain=AssetLocation.ETH_BLOCKCHAIN).commit()
    fetcher._account = eth_wallet
    assert fetcher._counterparty_note({'from': WALLET, 'to': other}) == ''
    assert fetcher._counterparty_note({'from': other, 'to': WALLET}) == ''


# ----------------------------------------------------------------------------------------------------------------------
# A counterparty that is another wallet of the user's own is filled in as the far account of the transfer instead of
# being left unknown for the user to pick.
OTHER_WALLET = "0x5555555555555555555555555555555555555555"


def _own_wallet(address, name='ETH wallet 2', chain=AssetLocation.ETH_BLOCKCHAIN):
    return JalAccountCreator(currency_id=2, number='', name=name, investing=1, organization=1,
                             account_type=PredefinedAccountType.Wallet, address=address, chain=chain).commit()


def test_own_counterparty_is_resolved_into_the_transfer(eth_wallet, monkeypatch):
    other = _own_wallet(OTHER_WALLET)
    pages = {"txlist": [_tx('0x01', 100, WALLET, OTHER_WALLET, value=10 ** 18)]}
    fetcher, data = _drive(eth_wallet, monkeypatch, pages)
    transfer = _transfers(data)[0]
    assert transfer['account'][0] == 1                                        # sent by the fetched wallet
    assert fetcher.mapped_id(JSF.ACCOUNTS, transfer['account'][1]) == other.id()   # ... to the wallet it went to
    assert transfer['account'].count(0) == 0
    assert transfer.get('description', '') == ''       # both ends are already known, the address note is noise


def test_counterparty_on_another_chain_is_not_resolved(eth_wallet, monkeypatch):
    # One EVM address is commonly registered once per chain. A transfer on Ethereum must never be booked onto the
    # Arbitrum account of the same address - the assets stay on the chain the transfer happened on.
    _own_wallet(OTHER_WALLET, name='ARB wallet', chain=AssetLocation.ARB_BLOCKCHAIN)
    pages = {"txlist": [_tx('0x01', 100, WALLET, OTHER_WALLET, value=10 ** 18)]}
    _fetcher, data = _drive(eth_wallet, monkeypatch, pages)
    assert _transfers(data)[0]['account'].count(0) == 1


def test_counterparty_of_a_netted_movement_is_left_unresolved(eth_wallet, monkeypatch):
    # The wallet's delta for an asset is a NET amount. When several addresses formed it, no single one of them
    # describes the transfer that is emitted, so none is put on it and the import asks as it always did.
    _own_wallet(OTHER_WALLET)
    external = "0x2222222222222222222222222222222222222222"
    pages = {"txlist": [_tx('0x01', 100, WALLET, OTHER_WALLET, value=3 * 10 ** 18)],
             "txlistinternal": [_internal_tx('0x01', 100, external, WALLET, 10 ** 18)]}
    _fetcher, data = _drive(eth_wallet, monkeypatch, pages)
    assert len(_transfers(data)) == 1                    # one netted ETH movement of 2 ETH
    assert _transfers(data)[0]['withdrawal'] == Decimal('2')
    assert _transfers(data)[0]['account'].count(0) == 1
    # ... and with no single counterparty there is no address to keep either
    assert 'counterparty_address' not in _transfers(data)[0]


# ----------------------------------------------------------------------------------------------------------------------
# An end with no account keeps the ADDRESS the transaction named for it. That address is what settles the leg later
# on - exactly, and without a second record of the movement having to exist at all.
def test_an_unresolved_counterparty_is_kept_as_an_address(eth_wallet, monkeypatch):
    external = "0x2222222222222222222222222222222222222222"
    pages = {"txlist": [_tx('0x01', 100, WALLET, external.upper(), value=10 ** 18)]}
    _fetcher, data = _drive(eth_wallet, monkeypatch, pages)
    transfer = _transfers(data)[0]
    assert transfer['account'][1] == 0                          # the destination is an address JAL has no account for
    assert transfer['counterparty_address'] == external         # ... kept as the chain stores it, case and all


def test_a_resolved_counterparty_leaves_no_address_to_settle(eth_wallet, monkeypatch):
    _own_wallet(OTHER_WALLET)
    pages = {"txlist": [_tx('0x01', 100, WALLET, OTHER_WALLET, value=10 ** 18)]}
    _fetcher, data = _drive(eth_wallet, monkeypatch, pages)
    assert 'counterparty_address' not in _transfers(data)[0]    # both ends are accounts, so no end is an address


def test_the_wallets_own_address_is_not_kept_as_a_counterparty(eth_wallet, monkeypatch):
    # A transaction paying the address it was sent from names no counterparty at all. Keeping that address would
    # leave a leg waiting to be settled with the very account it already stands on.
    pages = {"txlist": [_tx('0x01', 100, WALLET, WALLET, value=10 ** 18)]}
    _fetcher, data = _drive(eth_wallet, monkeypatch, pages)
    for transfer in _transfers(data):
        assert 'counterparty_address' not in transfer


# ----------------------------------------------------------------------------------------------------------------------
# The wallet-picker dialog that replaced the single-account selection: a checkbox per wallet plus an "all" checkbox
# that selects or clears the whole list, so any subset of a chain's wallets can be fetched in one run.
class _FakeWallet:
    def __init__(self, wid, name, address):
        self._id, self._name, self._address = wid, name, address
    def id(self):
        return self._id
    def name(self):
        return self._name
    def address(self):
        return self._address


def _wallet_dialog(prepare_db):
    from PySide6.QtCore import Qt
    from jal.net.chain_fetchers.fetchers import WalletSelectDialog
    wallets = [_FakeWallet(1, 'w1', '0xaaa'), _FakeWallet(2, 'w2', '0xbbb'), _FakeWallet(3, 'w3', '0xccc')]
    return WalletSelectDialog('Ethereum', wallets), Qt


def test_wallet_dialog_defaults_to_all_checked(prepare_db):
    dialog, Qt = _wallet_dialog(prepare_db)
    assert dialog.selected_ids() == [1, 2, 3]                 # everything is checked by default
    assert dialog._all.checkState() == Qt.Checked


def test_wallet_dialog_unchecking_one_partially_checks_all(prepare_db):
    dialog, Qt = _wallet_dialog(prepare_db)
    dialog._list.item(1).setCheckState(Qt.Unchecked)
    assert dialog.selected_ids() == [1, 3]
    assert dialog._all.checkState() == Qt.PartiallyChecked    # a mixed selection shows as partially checked


def _click_all(dialog):
    # Reproduces a real click: 'pressed' captures the pre-click state, then 'clicked' acts on it
    dialog._on_all_pressed()
    dialog._on_all_clicked(False)


def test_wallet_dialog_all_checkbox_clears_and_restores(prepare_db):
    dialog, Qt = _wallet_dialog(prepare_db)   # starts fully checked
    _click_all(dialog)                        # a click on a full selection clears everything
    assert dialog.selected_ids() == []
    _click_all(dialog)                        # and the next click checks everything again
    assert dialog.selected_ids() == [1, 2, 3]


def test_wallet_dialog_all_checkbox_from_partial_checks_everything(prepare_db):
    dialog, Qt = _wallet_dialog(prepare_db)
    dialog._list.item(0).setCheckState(Qt.Unchecked)   # partial selection
    assert dialog._all.checkState() == Qt.PartiallyChecked
    _click_all(dialog)                                 # clicking "all" from partial checks every wallet
    assert dialog.selected_ids() == [1, 2, 3]


# ----------------------------------------------------------------------------------------------------------------------
# The other direction of the same bridge, which is NOT the same contract. USD₮0 is the omnichain token itself on the
# L2, so the send BURNS it - the asset leg names the zero address and no protocol at all. What identifies the crossing
# is the transaction's own destination: the OFT contract the wallet called, which is also what it pays the LayerZero
# messaging fee to. (Being an L2 shares no addresses with L1 - and the registry is keyed by chain AND address anyway.)
def test_a_burn_send_on_the_l2_is_a_crossing_not_two_transfers(arb_wallet, monkeypatch):
    oft = "0x14e4a1b13bf7f943c8ff7c51fb60fa964a298d92"      # USDT0 OFT on Arbitrum, a registered BRIDGE
    zero = "0x0000000000000000000000000000000000000000"
    b1 = "0xc1" + "0" * 62
    pages = {
        "txlist": [_tx(b1, 100, ARB_WALLET, oft, value=193521415647447, gas_used='120000')],   # the LZ fee ...
        "tokentx": [_token_tx(b1, 100, ARB_WALLET, zero, 11365836072)],   # ... and the burn of what crosses
        "txlistinternal": [],
    }
    fetcher, data = _drive_arb(arb_wallet, monkeypatch, pages)

    assert not fetcher.skipped()
    halves = _bridges(data)
    assert len(halves) == 1
    assert halves[0]['qty'] == Decimal('11365.836072')      # the burnt amount is what crossed
    assert 'USDT0 OFT' in halves[0]['description']
    assert _transfers(data) == []                            # neither leg is a transfer of its own
    # The fee went to the OFT contract, so it is charged with the gas rather than counted as a second asset leaving
    gas = Decimal('120000') * Decimal('1000000000') / Decimal('10') ** 18
    assert halves[0]['fee_qty'] == gas + Decimal('193521415647447') / Decimal('10') ** 18


# The Ethereum adapter address must NOT be recognized on the L2 - one address on the wrong chain is a different
# contract, and classifying by it would book somebody else's contract as a bridge
def test_the_ethereum_adapter_is_not_a_protocol_on_the_l2():
    adapter = "0x6c96de32cea08842dcc4058c14d3aaad7fa41dee"
    assert protocol_category(AssetLocation.ETH_BLOCKCHAIN, adapter) == ProtocolCategory.BRIDGE
    assert protocol_category(AssetLocation.ARB_BLOCKCHAIN, adapter) is None
    oft = "0x14e4a1b13bf7f943c8ff7c51fb60fa964a298d92"
    assert protocol_category(AssetLocation.ARB_BLOCKCHAIN, oft) == ProtocolCategory.BRIDGE
    assert protocol_category(AssetLocation.ETH_BLOCKCHAIN, oft) is None


# ----------------------------------------------------------------------------------------------------------------------
# Chainlink CCIP (what app.aave.com bridges GHO with) charges its fee IN THE TOKEN BEING BRIDGED, and pays it to the
# OnRamp rather than to the Router the wallet called - so one send moves the same token twice, to two addresses, and
# neither of them is the contract the transaction names. Both legs are the wallet's own outflow of ONE asset, so they
# net into the single asset out that a crossing is and no messaging-fee rule is needed here: what leaves stays
# slightly larger than what arrives, and a matched Bridge accounts for that difference as its in-kind fee.
def test_a_ccip_send_pays_its_fee_in_the_bridged_token_and_still_crosses(eth_wallet, monkeypatch):
    router = "0x80226fc0ee2b096224eeac085bb9a8cba1146f7d"    # Chainlink CCIP Router on Ethereum, a registered BRIDGE
    pool = "0x06179f7c1be40863405f374e7f5f8806c728660a"      # the token pool that takes what crosses ...
    onramp = "0x913814782144864e523c3fdb78e3ca25d2c2aeca"    # ... and the OnRamp that is paid the fee
    c1 = "0xcc" + "0" * 62
    pages = {
        "txlist": [_tx(c1, 100, WALLET, router, value=0, gas_used='120000', method='0x96f4e9f9')],   # ccipSend()
        "tokentx": [_token_tx(c1, 100, WALLET, pool, 48100476931),      # what crosses ...
                    _token_tx(c1, 100, WALLET, onramp, 523068)],        # ... and the CCIP fee, in the same token
        "txlistinternal": [],
    }
    fetcher, data = _drive(eth_wallet, monkeypatch, pages)

    assert not fetcher.skipped()                  # two legs of one token are not "two assets out"
    halves = _bridges(data)
    assert len(halves) == 1
    assert halves[0]['symbol'] in _usdc_symbol_ids(data)
    # The fee is part of what was sent - it is deducted on the way, not before - so the half carries both legs and
    # the arrival, when it is matched in, is what makes the difference an in-kind fee
    assert halves[0]['qty'] == Decimal('48100.476931') + Decimal('0.523068')
    assert halves[0]['fee_qty'] == Decimal('120000') * Decimal('1000000000') / Decimal('10') ** 18   # gas alone
    assert halves[0]['fee_symbol'] in _eth_symbol_ids(data)
    assert 'Chainlink CCIP Router' in halves[0]['description']
    assert _transfers(data) == [] and _swaps(data) == []    # neither leg is a movement of its own


# The Arbitrum Router is a different address, and the same send shape goes through it - with the fee going to an
# OnRamp that CCIP has already replaced once (EVM2EVMOnRamp -> OnRamp) while the Router stayed put. That is why the
# registry names the Router the wallet calls rather than any contract the token actually reaches.
def test_the_ccip_routers_are_one_entry_per_chain(arb_wallet, monkeypatch):
    eth_router = "0x80226fc0ee2b096224eeac085bb9a8cba1146f7d"
    arb_router = "0x141fa059441e0ca23ce184b6a78bafd2a517dde8"
    assert protocol_category(AssetLocation.ETH_BLOCKCHAIN, eth_router) == ProtocolCategory.BRIDGE
    assert protocol_category(AssetLocation.ARB_BLOCKCHAIN, eth_router) is None
    assert protocol_category(AssetLocation.ARB_BLOCKCHAIN, arb_router) == ProtocolCategory.BRIDGE
    assert protocol_category(AssetLocation.ETH_BLOCKCHAIN, arb_router) is None

    pool = "0xb94ab28c6869466a46a42aba834ca2b3cecca5eb"      # the Arbitrum token pool ...
    onramp = "0x76a443768a5e3b8d1aed0105fc250877841deb40"    # ... and the lane's OnRamp of 2026
    c2 = "0xcd" + "0" * 62
    pages = {
        "txlist": [_tx(c2, 100, ARB_WALLET, arb_router, value=0, gas_used='120000', method='0x96f4e9f9')],
        "tokentx": [_token_tx(c2, 100, ARB_WALLET, pool, 48300778335),
                    _token_tx(c2, 100, ARB_WALLET, onramp, 1685806)],
        "txlistinternal": [],
    }
    fetcher, data = _drive_arb(arb_wallet, monkeypatch, pages)

    assert not fetcher.skipped()
    halves = _bridges(data)
    assert len(halves) == 1
    assert halves[0]['qty'] == Decimal('48300.778335') + Decimal('1.685806')
    assert 'Chainlink CCIP Router' in halves[0]['description']
    assert _transfers(data) == []


# The arriving side of a CCIP crossing is not a registry case at all: the OffRamp submits that transaction, so the
# wallet is neither its 'from' nor its 'to' and there is no interacted-with contract to look up. It lands as a plain
# incoming transfer - unmarked, because nothing in it even says a bridge was involved - and the user pairs it with
# its pending half by hand.
def test_a_ccip_arrival_is_an_unmarked_incoming_transfer(eth_wallet, monkeypatch):
    pool = "0x06179f7c1be40863405f374e7f5f8806c728660a"
    c3 = "0xce" + "0" * 62
    pages = {
        "txlist": [],                                                    # the wallet signed nothing here
        "tokentx": [_token_tx(c3, 100, pool, WALLET, 48300778335)],
        "txlistinternal": [],
    }
    fetcher, data = _drive(eth_wallet, monkeypatch, pages)

    assert _bridges(data) == [] and _swaps(data) == []
    transfers = _transfers(data)
    assert len(transfers) == 1 and transfers[0]['withdrawal'] == Decimal('48300.778335')
    assert transfers[0]['account'][0] == 0                               # incoming: the source account is unknown
    assert TransferMark.BRIDGE not in transfers[0]['description']
