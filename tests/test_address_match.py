import pytest

from tests.fixtures import project_root, data_path, prepare_db
from constants import AssetLocation, PredefinedAccountType
from jal.db.account import JalAccountCreator
from jal.db.address_match import address_resemblance, is_lookalike, impersonated_account

ETH = AssetLocation.ETH_BLOCKCHAIN
# The wallet address and, under it, the vanity addresses ground to be mistaken for it - taken from a real
# address-poisoning campaign: they agree with it at both ends, which is all an abbreviated display shows.
GENUINE = "0x6da6708a1b5946cade863f7f5792084731c57e63"
POISONED = ["0x6da64f4a6e15251d4c689ce1c3c90c1e7e457e63",     # 4 leading, 5 trailing
            "0x6da6fe2e13dee77f1187a39c01a2106271d27e63",     # 4 leading, 4 trailing
            "0x6da392f64b31d6a158dce1ba20dbd335f3057e63"]     # 3 leading, 5 trailing - the loosest one seen
UNRELATED = "0x6357d3843d715496257e338a878ab0b72040a918"


# ----------------------------------------------------------------------------------------------------------------------
def test_resemblance_counts_both_ends_without_the_chain_prefix():
    # Every EVM address starts '0x', so counting it would credit two unrelated addresses with two digits they
    # didn't earn - and the whole judgement rests on how many digits agreeing is too many to be chance.
    assert address_resemblance(ETH, "0xabcd" + "0" * 32 + "ef12", "0xabcd" + "1" * 32 + "ef12") == (4, 4)
    assert address_resemblance(ETH, "0x" + "a" * 40, "0x" + "b" * 40) == (0, 0)


def test_the_real_poisoning_addresses_are_recognized():
    for address in POISONED:
        assert is_lookalike(ETH, address, GENUINE), address


def test_an_unrelated_address_is_not():
    assert is_lookalike(ETH, UNRELATED, GENUINE) is False


# The one complete resemblance that means nothing: an address is not an imitation of itself
def test_the_address_itself_is_not_a_lookalike():
    assert is_lookalike(ETH, GENUINE, GENUINE) is False
    assert is_lookalike(ETH, GENUINE.upper().replace('0X', '0x'), GENUINE) is False   # EIP-55 casing is a checksum


def test_matching_one_end_only_is_not_enough():
    # Sharing a long prefix and nothing else is what a vanity address or a plain coincidence looks like; the attack
    # needs BOTH ends, because both ends are what an abbreviated address shows.
    assert is_lookalike(ETH, GENUINE[:12] + "f" * 30, GENUINE) is False
    assert is_lookalike(ETH, "0x" + "f" * 30 + GENUINE[-8:], GENUINE) is False


def test_two_digits_at_each_end_are_not_enough():
    # 16^-4 is one in 65536 - too likely among a few hundred counterparties to call it deliberate
    near = "0x" + GENUINE[2:4] + "9" * 36 + GENUINE[-2:]
    assert is_lookalike(ETH, near, GENUINE) is False


# ----------------------------------------------------------------------------------------------------------------------
@pytest.fixture
def wallet(prepare_db):
    yield JalAccountCreator(currency_id=2, number='', name='ETH wallet', investing=1, organization=1,
                            account_type=PredefinedAccountType.Wallet, address=GENUINE,
                            chain=AssetLocation.ETH_BLOCKCHAIN).commit()


def test_the_impersonated_account_is_named(wallet):
    # The row has to be able to say WHICH of the user's wallets is being imitated - that is what makes an entry the
    # user half-recognizes explicable rather than just alarming
    assert impersonated_account(ETH, POISONED[0]).id() == wallet.id()
    assert impersonated_account(ETH, UNRELATED) is None
    assert impersonated_account(ETH, GENUINE) is None


def test_an_address_held_on_another_chain_is_still_impersonated(prepare_db):
    # One EVM address is commonly registered as several accounts, one per chain. An attacker copying the ends of an
    # address the user holds on Ethereum has poisoned it just as effectively where it is met.
    account = JalAccountCreator(currency_id=2, number='', name='ARB wallet', investing=1, organization=1,
                                account_type=PredefinedAccountType.Wallet, address=GENUINE,
                                chain=AssetLocation.ARB_BLOCKCHAIN).commit()
    assert impersonated_account(ETH, POISONED[0]).id() == account.id()
