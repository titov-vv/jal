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
from jal.net.token_lists import TokenListProvider

# A sample wallet used only by the recorded fixtures - never the address of a real user (see the note in
# tests/local_test_data.json.example on why an on-chain address must not be committed). The USDC contract is the
# real mainnet one, allow-listed below so its transfers survive the spam filter the way a real import would.
WALLET = "0x1111111111111111111111111111111111111111"
USDC_CONTRACT = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
SPAM_CONTRACT = "0x9999999999999999999999999999999999999999"

_FIXTURE = {"txlist": "eth_txlist.json", "tokentx": "eth_tokentx.json", "txlistinternal": "eth_internal.json"}


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


def _eth_symbol_ids(data) -> list:
    return [s['id'] for a in data[JSF.ASSETS] for s in a[JSF.SYMBOLS] if s['symbol'] == 'ETH']


# ----------------------------------------------------------------------------------------------------------------------
def test_fetch_builds_transfers(fetcher, eth_wallet):
    data = fetcher.fetch(eth_wallet)
    # 5 native transfers (2 top-level, 1 swap-out, 2 internal-in) and 4 USDC transfers survive the spam filter
    assert len(_transfers(data)) == 9
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
    assert len(outgoing_with_fee) == 4          # 2 native sends + 2 token sends each paid gas
    for transfer in outgoing_with_fee:
        assert transfer['fee_symbol'] in eth_symbols    # gas is always burned in ETH, whatever asset moved
        assert transfer['account'][2] == 1              # and always by the wallet being fetched
    # Incoming transfers never carry gas - the sender paid it
    assert all(t['fee'] == Decimal('0') for t in _transfers(data) if t['account'][0] == 0)


def test_gas_is_not_double_counted_on_a_swap(fetcher, eth_wallet):
    data = fetcher.fetch(eth_wallet)
    # The token->ETH swap (hash 0x222...) has an outgoing token leg and an incoming native leg; its gas must land on
    # exactly one of them, so the sum of fees on that transaction equals the single gas charge of 0.00013 ETH.
    legs = [t for t in _transfers(data) if t['number'].startswith('0x222')]
    assert len(legs) == 2
    assert sum((t['fee'] for t in legs), Decimal('0')) == Decimal('130000') * Decimal('1000000000') / Decimal('10') ** 18


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
    # A 0.002791 ETH deposit from a contract (an internal transfer). It is well below the fiat dust threshold of 1,
    # so a naive amount-vs-threshold check would wrongly drop it; the native coin is deliberately not dust-filtered.
    deposit = [t for t in _transfers(data) if t['number'].startswith('0x444')]
    assert len(deposit) == 1
    assert deposit[0]['withdrawal'] == Decimal('0.002791')
    assert deposit[0]['account'][0] == 0        # incoming


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
def test_is_evm_address_accepts_valid_and_rejects_malformed():
    assert is_evm_address(WALLET)
    assert is_evm_address("0xA0b86991c6218B36c1d19D4a2e9Eb0cE3606eB48")   # checksummed casing is accepted
    assert not is_evm_address("")
    assert not is_evm_address("0x123")                                    # too short
    assert not is_evm_address("1111111111111111111111111111111111111111")  # missing 0x
    assert not is_evm_address("0xZZZ6991c6218b36c1d19d4a2e9eb0ce3606eb48")  # non-hex


def test_counterparty_note_shows_both_parties_sender_first():
    from jal.net.chain_fetchers.evm import EVMFetcher
    assert EVMFetcher._counterparty_note({'from': '0xAAA', 'to': '0xBBB'}) == '0xAAA → 0xBBB'


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
