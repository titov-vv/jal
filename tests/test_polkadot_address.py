from bip_utils import SS58Encoder
from jal.constants import AssetLocation
from jal.db.token_blacklist import is_polkadot_address, is_valid_address, normalize_address

TREASURY = "13UVJyLnbVp9RBZYFwFGyDvVd1y27Tt8tkntv6Q7JVPhFsTB"   # Polkadot treasury, public
MADE_UP = SS58Encoder.Encode(bytes(range(32)), 0)
GENERIC = SS58Encoder.Encode(bytes(range(32)), 42)               # same key, generic Substrate prefix ('5...')
KUSAMA = SS58Encoder.Encode(bytes(range(32)), 2)


def test_valid_polkadot_addresses():
    for address in (TREASURY, MADE_UP):
        assert is_polkadot_address(address), address
        assert is_valid_address(AssetLocation.DOT_BLOCKCHAIN, address), address


def test_invalid_polkadot_addresses():
    broken_checksum = TREASURY[:-1] + ("C" if TREASURY[-1] != "C" else "D")
    for address in ("", "1", "abc", "0x" + "ab" * 32, broken_checksum, TREASURY.lower(), GENERIC, KUSAMA,
                    TREASURY + "1"):
        assert not is_polkadot_address(address), address
        assert not is_valid_address(AssetLocation.DOT_BLOCKCHAIN, address), address


# SS58 is case-sensitive base58, so the stored form is the typed one
def test_polkadot_address_stored_verbatim():
    assert normalize_address(AssetLocation.DOT_BLOCKCHAIN, f" {TREASURY} ") == TREASURY
