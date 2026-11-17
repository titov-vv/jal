from jal.constants import AssetLocation
from jal.db.token_blacklist import is_near_account, is_valid_address, normalize_address

IMPLICIT = "98793cd91a3f870fb126f66285808c7e094afcfc4eda8a970f6648cdf0dbd6de"   # 64 hex, made up
ETH_IMPLICIT = "0x" + "ab" * 20


def test_valid_near_accounts():
    for address in ("near", "example.near", "astro-stakers.poolv1.near", "a_b-c.d0.near", "aa", IMPLICIT,
                    ETH_IMPLICIT, "a" * 64):
        assert is_near_account(address), address
        assert is_valid_address(AssetLocation.NEAR_BLOCKCHAIN, address), address


def test_invalid_near_accounts():
    for address in ("", "a", "a" * 65, "Example.near", IMPLICIT.upper(), "a..b", ".near", "near.", "-a", "a-",
                    "a__b", "a-.near", "a b", "a@near", "a.near\n"):
        assert not is_near_account(address), address
        assert not is_valid_address(AssetLocation.NEAR_BLOCKCHAIN, address), address


# NEAR ids are case-sensitive, so the stored form is the typed one (an uppercase id is refused instead of folded)
def test_near_account_stored_verbatim():
    assert normalize_address(AssetLocation.NEAR_BLOCKCHAIN, " example.near ") == "example.near"
    assert normalize_address(AssetLocation.NEAR_BLOCKCHAIN, "Example.near") == "Example.near"
