import pytest
from bip_utils import AdaShelleyAddrNetworkTags, AdaShelleyStakingAddrEncoder, Bech32Encoder, Bip44Changes, \
    CardanoIcarusSeedGenerator, CardanoShelley, Cip1852, Cip1852Coins

from jal.constants import AssetLocation
from jal.db.token_blacklist import is_cardano_account_key, is_cardano_stake_address, is_valid_address, \
    normalize_address
from jal.net.chain_fetchers.cardano_keys import stake_address

# The mnemonic of the CIP-0019 address test vectors - published, so no address below belongs to anybody
TEST_MNEMONIC = "test walk nut penalty hip pave soap entry language right filter choice"


@pytest.fixture
def account():
    seed = CardanoIcarusSeedGenerator(TEST_MNEMONIC).Generate()
    yield Cip1852.FromSeed(seed, Cip1852Coins.CARDANO_ICARUS).Purpose().Coin().Account(0)


# The account public key in the bech32 form a wallet exports
def account_key(account) -> str:
    public = account.PublicKey()
    return Bech32Encoder.Encode('acct_xvk', public.RawCompressed().ToBytes()[1:] + public.ChainCode().ToBytes())


# The first external payment address of the account
def first_address(account) -> str:
    wallet = CardanoShelley.FromCip1852Object(account)
    return wallet.Change(Bip44Changes.CHAIN_EXT).AddressIndex(0).PublicKeys().ToAddress()


# What is derived from the public account key alone must equal the full-path derivation from the seed
def test_stake_address_matches_full_path(account):
    expected = CardanoShelley.FromCip1852Object(account).StakingObject().PublicKey().ToAddress()
    assert expected.startswith('stake1')
    assert stake_address(account_key(account)) == expected
    assert stake_address(expected) == expected              # a stake address stands for itself


# The payment part of the derived first address is the one CIP-0019 publishes for this mnemonic
def test_test_vector_is_the_published_one(account):
    assert first_address(account).startswith("addr1qx2fxv2umyhttkxyxp8x0dlpdt3k6cwng5pxj3jhsydzer3")


def test_both_wallet_forms_are_valid(account):
    key = account_key(account)
    stake = stake_address(key)
    for address in (key, stake):
        assert is_valid_address(AssetLocation.ADA_BLOCKCHAIN, address)
    assert is_cardano_account_key(key) and not is_cardano_stake_address(key)
    assert is_cardano_stake_address(stake) and not is_cardano_account_key(stake)


def test_malformed_wallet_forms_are_refused(account):
    key = account_key(account)
    stake = stake_address(key)
    script_credential = Bech32Encoder.Encode('stake', b'\xf1' + bytes(28))        # a script's stake address
    testnet = AdaShelleyStakingAddrEncoder.EncodeKey(
        CardanoShelley.FromCip1852Object(account).StakingObject().PublicKey().Bip32Key().KeyObject(),
        net_tag=AdaShelleyAddrNetworkTags.TESTNET)
    short_key = Bech32Encoder.Encode('acct_xvk', bytes(32))
    payment = first_address(account)
    for address in (stake[:-1] + ('q' if stake[-1] != 'q' else 'p'),           # checksum broken
                    key[:-1] + ('q' if key[-1] != 'q' else 'p'),
                    script_credential, testnet, short_key, payment, '', 'stake1'):
        assert not is_valid_address(AssetLocation.ADA_BLOCKCHAIN, address), address
        with pytest.raises(ValueError):
            stake_address(address)


# bech32 is case-insensitive but SQLite TEXT is not, so the stored form is lower case; base58 Byron stays verbatim
def test_bech32_forms_are_stored_in_lower_case(account):
    key = account_key(account)
    assert normalize_address(AssetLocation.ADA_BLOCKCHAIN, key.upper()) == key
    assert stake_address(key.upper()) == stake_address(key)
    byron = "Ae2tdPwUPEZFRbyhz3cpfC2CumGzNkFBN2L42rcUc2yjQpEkxDbkPodpMAi"
    assert normalize_address(AssetLocation.ADA_BLOCKCHAIN, byron) == byron
