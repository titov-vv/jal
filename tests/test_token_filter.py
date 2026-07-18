import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import json
from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from constants import AssetLocation, TokenVerdict
from jal.db.token_blacklist import JalTokenBlacklist, normalize_address
from jal.net.token_lists import TokenListProvider
from jal.data_import.token_filter import TokenFilter, TokenCandidate
from jal.widgets.reference_dialogs import TokenBlacklistDialog


# Addresses of the tokens that the samples in tests/test_data actually contain. The samples are verbatim
# excerpts of the real downloads (captured 2026-07-18), so the parsers are tested against the real shapes -
# including the details that differ between sources: Jupiter keys the mint as 'id', DappRadar spells 'chainId'
# as a string, and MyEtherWallet names the chain in a 'network' field instead of a numeric chain id.
ONEINCH_ETH = "0x111111111117dC0aa78b770fA6A738034120C302"   # Uniswap list, chainId 1, checksum case
ARB_ON_ARB = None                                            # filled from the sample below
SWUSD_ETH = "0x77c6e4a580c0dce4e5c7a17d0bc077188a83a059"     # CoinGecko list, chainId 1
SCAM_ETH = "0x4527a3b4a8a150403090a99b87effc96f2195047"      # DappRadar block-list, chainId '1'
BSC_ONLY = "0x6258d49ca4035431575d997b096723e68d8c92f9"      # DappRadar, chainId '56' - a chain JAL doesn't know
WSOL = "So11111111111111111111111111111111111111112"         # Jupiter verified list
NEW_ETH = "0x2222222222222222222222222222222222222222"       # deliberately on no list at all


# A TokenListProvider fetcher that replays the captured samples instead of downloading.
# 'requests' records how many times the network would have been touched.
class SampleFetcher:
    def __init__(self, path, failing=False):
        self.path = path
        self.requests = []
        self.failing = failing

    def __call__(self, url: str) -> bytes:
        self.requests.append(url)
        if self.failing:
            raise ConnectionError("no network")
        for key, sample in [("jup.ag", "jupiter"), ("tokens.uniswap.org", "uniswap"),
                            ("coingecko", "coingecko"), ("dappradar", "dappradar"), ("MyEtherWallet", "mew")]:
            if key in url:
                return open(self.path + f"token_list_{sample}.json", 'rb').read()
        raise AssertionError(f"Unexpected URL requested: {url}")


@pytest.fixture
def lists(prepare_db, data_path):
    global ARB_ON_ARB
    fetcher = SampleFetcher(data_path)
    provider = TokenListProvider(fetcher=fetcher)
    provider.refresh()
    provider.fetcher = fetcher
    ARB_ON_ARB = [x['address'] for x in json.load(open(data_path + "token_list_uniswap.json"))['tokens']
                  if x['chainId'] == 42161][0]
    yield provider


# ----------------------------------------------------------------------------------------------------------------------
def test_address_normalization():
    # EVM addresses are hex - the checksum case carries no information and must not affect matching
    assert normalize_address(AssetLocation.ETH_BLOCKCHAIN, ONEINCH_ETH) == ONEINCH_ETH.lower()
    assert normalize_address(AssetLocation.ARB_BLOCKCHAIN, "  " + ONEINCH_ETH + " ") == ONEINCH_ETH.lower()
    # Solana mint addresses are base58 - the case is meaningful and must be kept as is
    assert normalize_address(AssetLocation.SOL_BLOCKCHAIN, WSOL) == WSOL
    assert normalize_address(AssetLocation.ETH_BLOCKCHAIN, '') == ''


def test_blacklist_roundtrip(prepare_db):
    assert not JalTokenBlacklist.is_blacklisted(AssetLocation.ETH_BLOCKCHAIN, SCAM_ETH)

    entry = JalTokenBlacklist.add(AssetLocation.ETH_BLOCKCHAIN, SCAM_ETH, name_hint="FAKE", auto=True)
    assert entry.blacklisted()
    assert entry.name_hint() == "FAKE"
    assert entry.is_auto()
    assert entry.added_timestamp() > 0
    assert JalTokenBlacklist.is_blacklisted(AssetLocation.ETH_BLOCKCHAIN, SCAM_ETH)
    # The same address in a different case and on another chain
    assert JalTokenBlacklist.is_blacklisted(AssetLocation.ETH_BLOCKCHAIN, SCAM_ETH.upper())
    assert not JalTokenBlacklist.is_blacklisted(AssetLocation.ARB_BLOCKCHAIN, SCAM_ETH)

    # Repeated blacklisting updates the record instead of creating a second one
    JalTokenBlacklist.add(AssetLocation.ETH_BLOCKCHAIN, SCAM_ETH, name_hint="FAKE2", auto=False)
    assert len(JalTokenBlacklist.get_all()) == 1
    assert JalTokenBlacklist(AssetLocation.ETH_BLOCKCHAIN, SCAM_ETH).name_hint() == "FAKE2"
    assert not JalTokenBlacklist(AssetLocation.ETH_BLOCKCHAIN, SCAM_ETH).is_auto()

    JalTokenBlacklist.remove(AssetLocation.ETH_BLOCKCHAIN, SCAM_ETH)
    assert not JalTokenBlacklist.is_blacklisted(AssetLocation.ETH_BLOCKCHAIN, SCAM_ETH)
    assert JalTokenBlacklist.get_all() == []

    with pytest.raises(ValueError):
        JalTokenBlacklist.add(AssetLocation.ETH_BLOCKCHAIN, '')


# ----------------------------------------------------------------------------------------------------------------------
def test_list_download_and_cache(lists):
    # Allow-lists: the standard 'tokenlists' schema (Uniswap/CoinGecko), Jupiter's own schema and MEW's 'network' one
    assert lists.is_allowlisted(AssetLocation.ETH_BLOCKCHAIN, ONEINCH_ETH)
    assert lists.is_allowlisted(AssetLocation.ETH_BLOCKCHAIN, ONEINCH_ETH.lower())   # checksum case is irrelevant
    assert lists.is_allowlisted(AssetLocation.ETH_BLOCKCHAIN, SWUSD_ETH)
    assert lists.is_allowlisted(AssetLocation.ARB_BLOCKCHAIN, ARB_ON_ARB)            # chainId 42161 lands on Arbitrum
    assert lists.is_allowlisted(AssetLocation.SOL_BLOCKCHAIN, WSOL)

    # A token of one chain is never allow-listed on another one
    assert not lists.is_allowlisted(AssetLocation.ARB_BLOCKCHAIN, ONEINCH_ETH)
    assert not lists.is_allowlisted(AssetLocation.SOL_BLOCKCHAIN, ONEINCH_ETH)
    assert not lists.is_allowlisted(AssetLocation.ETH_BLOCKCHAIN, WSOL)
    assert not lists.is_allowlisted(AssetLocation.ETH_BLOCKCHAIN, NEW_ETH)

    # Block-list, and the entries of chains that JAL doesn't support are dropped
    assert lists.is_blocklisted(AssetLocation.ETH_BLOCKCHAIN, SCAM_ETH)
    assert not lists.is_blocklisted(AssetLocation.ETH_BLOCKCHAIN, BSC_ONLY)          # BSC entry of the same list
    assert not lists.is_blocklisted(AssetLocation.ETH_BLOCKCHAIN, ONEINCH_ETH)


def test_list_refresh_interval(lists):
    downloads = len(lists.fetcher.requests)
    lists.refresh()                       # Nothing is stale yet, so no request is made
    assert len(lists.fetcher.requests) == downloads
    lists.refresh(force=True)
    assert len(lists.fetcher.requests) > downloads


def test_list_download_failure_keeps_cache(lists, data_path):
    broken = TokenListProvider(fetcher=SampleFetcher(data_path, failing=True))
    broken.refresh(force=True)            # Must not raise
    assert broken.is_allowlisted(AssetLocation.ETH_BLOCKCHAIN, ONEINCH_ETH)   # previously cached content survived


# ----------------------------------------------------------------------------------------------------------------------
# Layer 1: an allow-listed token is imported even if it arrived as a worthless unsolicited transfer
def test_allowlisted_token_is_imported(lists):
    token_filter = TokenFilter(lists=lists)
    candidate = TokenCandidate(AssetLocation.ETH_BLOCKCHAIN, ONEINCH_ETH, symbol="1INCH",
                               incoming=True, value=Decimal('0'))
    assert token_filter.classify(candidate) == TokenVerdict.Import
    assert token_filter.accept(candidate)
    assert not JalTokenBlacklist.is_blacklisted(AssetLocation.ETH_BLOCKCHAIN, ONEINCH_ETH)


# Layer 2: an unknown worthless token received from a stranger is quarantined
def test_dust_airdrop_is_blacklisted(lists):
    token_filter = TokenFilter(lists=lists)
    candidate = TokenCandidate(AssetLocation.ETH_BLOCKCHAIN, NEW_ETH, symbol="USDC",   # a fake 'USDC'
                               incoming=True, value=Decimal('0.01'))
    assert token_filter.classify(candidate) == TokenVerdict.Blacklist
    assert not token_filter.accept(candidate)
    entry = JalTokenBlacklist(AssetLocation.ETH_BLOCKCHAIN, NEW_ETH)
    assert entry.blacklisted()
    assert entry.is_auto()
    assert entry.name_hint() == "USDC"


# Layer 2: a token that can't be priced at all is dust as well
def test_unpriceable_token_is_blacklisted(lists):
    token_filter = TokenFilter(lists=lists)
    candidate = TokenCandidate(AssetLocation.ETH_BLOCKCHAIN, NEW_ETH, incoming=True, value=None)
    assert token_filter.classify(candidate) == TokenVerdict.Blacklist


# Layer 2: a block-listed token is quarantined even if its transfer looks valuable
def test_blocklisted_token_is_blacklisted(lists):
    token_filter = TokenFilter(lists=lists)
    candidate = TokenCandidate(AssetLocation.ETH_BLOCKCHAIN, SCAM_ETH, incoming=True, value=Decimal('1000'))
    assert token_filter.classify(candidate) == TokenVerdict.Blacklist


# Layer 3: a token acquired by a swap was chosen by the user and is never dust
def test_swap_acquired_token_is_imported(lists):
    token_filter = TokenFilter(lists=lists)
    candidate = TokenCandidate(AssetLocation.ETH_BLOCKCHAIN, NEW_ETH, from_swap=True, value=None)
    assert token_filter.classify(candidate) == TokenVerdict.Import


# Layer 3: a valuable transfer, or one from a known counterparty, is imported
def test_valuable_and_known_transfers_are_imported(lists):
    token_filter = TokenFilter(lists=lists)
    valuable = TokenCandidate(AssetLocation.ETH_BLOCKCHAIN, NEW_ETH, incoming=True, value=Decimal('100'))
    assert token_filter.classify(valuable) == TokenVerdict.Import
    known = TokenCandidate(AssetLocation.ETH_BLOCKCHAIN, NEW_ETH, incoming=True, value=None, known_counterparty=True)
    assert token_filter.classify(known) == TokenVerdict.Import
    outgoing = TokenCandidate(AssetLocation.ETH_BLOCKCHAIN, NEW_ETH, incoming=False, value=None)
    assert token_filter.classify(outgoing) == TokenVerdict.Import


# An existing blacklist record overrides everything, and removing it lets the token in again
def test_blacklist_record_is_final_and_reversible(lists):
    token_filter = TokenFilter(lists=lists)
    JalTokenBlacklist.add(AssetLocation.ETH_BLOCKCHAIN, ONEINCH_ETH, name_hint="USDC", auto=False)
    allowlisted = TokenCandidate(AssetLocation.ETH_BLOCKCHAIN, ONEINCH_ETH, value=Decimal('100'))
    assert token_filter.classify(allowlisted) == TokenVerdict.Blacklist   # user's decision wins over the allow-list

    JalTokenBlacklist.remove(AssetLocation.ETH_BLOCKCHAIN, ONEINCH_ETH)
    assert token_filter.classify(allowlisted) == TokenVerdict.Import

    # The same for a token that was quarantined automatically - un-blacklisting makes it importable
    dust = TokenCandidate(AssetLocation.ETH_BLOCKCHAIN, NEW_ETH, incoming=True, value=Decimal('0'))
    assert not token_filter.accept(dust)
    JalTokenBlacklist.remove(AssetLocation.ETH_BLOCKCHAIN, NEW_ETH)
    assert token_filter.classify(dust) == TokenVerdict.Blacklist   # the heuristic still rejects it...
    swapped = TokenCandidate(AssetLocation.ETH_BLOCKCHAIN, NEW_ETH, from_swap=True)
    assert token_filter.classify(swapped) == TokenVerdict.Import   # ...but a swap of it is imported


def test_filter_of_a_batch(lists):
    token_filter = TokenFilter(lists=lists)
    candidates = [
        TokenCandidate(AssetLocation.ETH_BLOCKCHAIN, ONEINCH_ETH, symbol="USDC", value=Decimal('50')),
        TokenCandidate(AssetLocation.ETH_BLOCKCHAIN, SCAM_ETH, symbol="FAKE", incoming=True, value=None),
        TokenCandidate(AssetLocation.ETH_BLOCKCHAIN, NEW_ETH, symbol="NEW", from_swap=True)
    ]
    accepted = token_filter.filter(candidates)
    assert [x.address for x in accepted] == [ONEINCH_ETH, NEW_ETH]
    assert JalTokenBlacklist.is_blacklisted(AssetLocation.ETH_BLOCKCHAIN, SCAM_ETH)
    assert len(JalTokenBlacklist.get_all()) == 1


def test_dust_threshold_is_configurable(lists):
    candidate = TokenCandidate(AssetLocation.ETH_BLOCKCHAIN, NEW_ETH, incoming=True, value=Decimal('5'))
    assert TokenFilter(lists=lists).classify(candidate) == TokenVerdict.Import   # default threshold is 1
    assert TokenFilter(lists=lists, dust_threshold=Decimal('10')).classify(candidate) == TokenVerdict.Blacklist


# ----------------------------------------------------------------------------------------------------------------------
# The review dialog is the only way for the user to undo an automatic quarantine
def test_dialog_lists_and_removes(prepare_db):
    JalTokenBlacklist.add(AssetLocation.ETH_BLOCKCHAIN, "0xAbC1111111111111111111111111111111111111", "FAKE")
    JalTokenBlacklist.add(AssetLocation.SOL_BLOCKCHAIN, "SoLmint111111111111111111111111111111111111", "SPAM")
    dialog = TokenBlacklistDialog()
    model = dialog.model
    assert model.rowCount() == 2
    # Chain column is rendered as the enum name by the delegate installed on that column
    column = model.fieldIndex('location_id')
    delegate = dialog.ui.DataView.itemDelegateForColumn(column)
    assert delegate.displayText(model.data(model.index(0, column)), None) in ("Ethereum", "Solana")
    # Deleting a row un-blacklists the token
    dialog.ui.DataView.selectRow(0)
    address = model.data(model.index(0, model.fieldIndex('address')))
    location = model.record(0).value('location_id')
    dialog.OnRemove()
    dialog.OnCommit()
    assert model.rowCount() == 1
    assert not JalTokenBlacklist.is_blacklisted(location, address)
