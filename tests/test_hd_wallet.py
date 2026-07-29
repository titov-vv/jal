import pytest
from bip_utils import Bip39SeedGenerator, Bip44, Bip44Coins, Bip49, Bip49Coins, Bip84, Bip84Coins, Bip44Changes, \
    Base58Decoder, Base58Encoder

from tests.fixtures import project_root, local_test_data
from jal.net.chain_fetchers.hd_wallet import HDAccount, ScriptType, RECEIVE_BRANCH, CHANGE_BRANCH, \
    is_extended_key, preferred_script_type

# The BIP39 test-vector mnemonic. It is published in the standard itself and its wallet is the most watched pile of
# empty addresses in existence - which is exactly why derivation is checked against it and never against a wallet
# somebody owns (see tests/local_test_data.json.example).
TEST_MNEMONIC = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"
XPUB_VERSION = bytes.fromhex('0488b21e')


@pytest.fixture
def seed():
    yield Bip39SeedGenerator(TEST_MNEMONIC).Generate()


# The account-level extended public key of one purpose, in the serialization that purpose conventionally uses
# (xpub for BIP44, ypub for BIP49, zpub for BIP84) - i.e. what a wallet exports.
def account_key(seed, purpose, coin):
    return purpose.FromSeed(seed, coin).Purpose().Coin().Account(0).PublicKey().ToExtended()


def account(seed, purpose, coin):
    return purpose.FromSeed(seed, coin).Purpose().Coin().Account(0)


# ----------------------------------------------------------------------------------------------------------------------
# What JAL derives from an exported account key must equal what the full path derivation from the seed gives, for
# every script type it supports. This is the guard against a coin-parameter mix-up or a bip_utils upgrade changing
# an encoder: JAL starts from the account key alone (it never sees private material), so nothing else would notice.
@pytest.mark.parametrize("purpose, coin, script_type", [
    (Bip44, Bip44Coins.BITCOIN, ScriptType.P2PKH),
    (Bip49, Bip49Coins.BITCOIN, ScriptType.P2SH_P2WPKH),
    (Bip84, Bip84Coins.BITCOIN, ScriptType.P2WPKH)])
def test_derivation_matches_full_path(seed, purpose, coin, script_type):
    derived = HDAccount(account_key(seed, purpose, coin))
    reference = account(seed, purpose, coin)
    for index in range(3):
        expected = reference.Change(Bip44Changes.CHAIN_EXT).AddressIndex(index).PublicKey().ToAddress()
        assert derived.address(RECEIVE_BRANCH, index, script_type) == expected
        expected = reference.Change(Bip44Changes.CHAIN_INT).AddressIndex(index).PublicKey().ToAddress()
        assert derived.address(CHANGE_BRANCH, index, script_type) == expected


# The receive and change branches must never produce the same address: the whole point of the change branch is that
# the wallet can tell its own change from a payment it received.
def test_branches_are_disjoint(seed):
    wallet = HDAccount(account_key(seed, Bip84, Bip84Coins.BITCOIN))
    receive = {wallet.address(RECEIVE_BRANCH, i, ScriptType.P2WPKH) for i in range(20)}
    change = {wallet.address(CHANGE_BRANCH, i, ScriptType.P2WPKH) for i in range(20)}
    assert len(receive) == len(change) == 20
    assert not receive & change


# A key re-serialized with different version bytes is the same key: SLIP-132 prefixes say what the exporter thought
# the script type was, and JAL normalizes them away because they can't be trusted (decision #74). The addresses must
# not depend on which of them the key arrived with.
def test_slip132_prefix_does_not_change_the_addresses(seed):
    zpub = account_key(seed, Bip84, Bip84Coins.BITCOIN)
    as_xpub = Base58Encoder.CheckEncode(XPUB_VERSION + Base58Decoder.CheckDecode(zpub)[4:])
    assert zpub[:4] == 'zpub' and as_xpub[:4] == 'xpub'
    for script_type in ScriptType.ALL:
        assert HDAccount(zpub).address(RECEIVE_BRANCH, 0, script_type) == \
               HDAccount(as_xpub).address(RECEIVE_BRANCH, 0, script_type)
    # ... while the prefix is still what the fetcher tries first
    assert preferred_script_type(zpub) == ScriptType.P2WPKH
    assert preferred_script_type(as_xpub) == ScriptType.P2PKH


def test_extended_keys_are_recognized(seed):
    assert is_extended_key(account_key(seed, Bip84, Bip84Coins.BITCOIN))
    assert is_extended_key(account_key(seed, Bip44, Bip44Coins.BITCOIN))
    assert not is_extended_key("bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu")
    assert not is_extended_key("")


# A ledger has no use for spending material and must never store it: an extended PRIVATE key derives the same
# addresses, so nothing but this check would notice that one was pasted into the account.
def test_private_key_is_rejected(seed):
    private = Bip84.FromSeed(seed, Bip84Coins.BITCOIN).Purpose().Coin().Account(0).PrivateKey().ToExtended()
    with pytest.raises(ValueError):
        HDAccount(private)


@pytest.mark.parametrize("key", ["", "nonsense", "bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu",
                                 "zpub6rFR7y4Q2AijBEqTUquhVz398htDFrtymD9xYYfG1m4wAcvPhXNfE3EfH1r1ADqtfSdVCToUG868Rv"])
def test_malformed_keys_are_rejected(key):
    with pytest.raises(ValueError):
        HDAccount(key)


# ----------------------------------------------------------------------------------------------------------------------
# The one check against a wallet that really exists: the user's own key and the first address as their hardware
# wallet displays it. Everything above proves JAL agrees with bip_utils; only this proves that both agree with the
# device. Skipped for anyone without tests/local_test_data.json, and needs no network.
def test_real_wallet_first_address(local_test_data):
    wallet = local_test_data('bitcoin')
    if 'first_address' not in wallet:
        pytest.skip("No 'first_address' in the 'bitcoin' section of tests/local_test_data.json")
    derived = HDAccount(wallet['xpub'])
    # The key is BIP84 whatever its prefix claims - which is the trap this wallet exists to guard against
    assert derived.address(RECEIVE_BRANCH, 0, ScriptType.P2WPKH) == wallet['first_address']
