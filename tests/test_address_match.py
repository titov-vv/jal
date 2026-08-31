import pytest

from tests.fixtures import project_root, data_path, prepare_db
from constants import AssetLocation, PredefinedAccountType
from jal.db.account import JalAccountCreator
from jal.db.address_match import address_resemblance, is_lookalike, impersonated_target, _thresholds, \
    ACCOUNT, PROTOCOL

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
    target = impersonated_target(ETH, POISONED[0])
    assert target['kind'] == ACCOUNT and target['account'].id() == wallet.id() and target['name'] == 'ETH wallet'
    assert impersonated_target(ETH, UNRELATED) is None
    assert impersonated_target(ETH, GENUINE) is None


def test_an_address_held_on_another_chain_is_still_impersonated(prepare_db):
    # One EVM address is commonly registered as several accounts, one per chain. An attacker copying the ends of an
    # address the user holds on Ethereum has poisoned it just as effectively where it is met.
    account = JalAccountCreator(currency_id=2, number='', name='ARB wallet', investing=1, organization=1,
                                account_type=PredefinedAccountType.Wallet, address=GENUINE,
                                chain=AssetLocation.ARB_BLOCKCHAIN).commit()
    assert impersonated_target(ETH, POISONED[0])['account'].id() == account.id()


# ----------------------------------------------------------------------------------------------------------------------
# The Hyperliquid Bridge2 contract on Arbitrum and the three real lookalikes of it that reached the wallet. None of
# them imitates an account of the user's at all, which is why nothing saw them while only accounts were compared.
ARB = AssetLocation.ARB_BLOCKCHAIN
HL_BRIDGE = "0x2df1c51e09aecf9cacb7bc98cb1742757f163df7"
HL_LOOKALIKES = ["0x2df139edd28fe18eb884c347d05a45757f163df7",     # 4 leading, 10 trailing
                 "0x2df17470c5de6a5d2d41feb8fcf5fb0deeb43df7",     # 4 leading, 4 trailing
                 "0x2df1df582d0a1efc7178fd78b2bcd9aa08a73df7"]     # 4 leading, 4 trailing


def test_a_contract_of_the_registry_is_impersonated_too(prepare_db):
    # Nobody memorizes a bridge's address, which is exactly what makes imitating one work
    for address in HL_LOOKALIKES:
        target = impersonated_target(ARB, address)
        assert target is not None, address
        assert target['kind'] == PROTOCOL and target['name'] == 'Hyperliquid Bridge2', address
        assert target['account'] is None


def test_the_real_contract_is_never_accused_of_imitating_its_own_fakes(prepare_db):
    # The genuine address resembles every lookalike ground to imitate it exactly as closely as they resemble it. A
    # real arrival FROM the bridge must never be painted as poisoning - that would offer the user's own money for
    # write-off as dust.
    assert impersonated_target(ARB, HL_BRIDGE) is None


def test_an_account_wins_over_a_contract(prepare_db):
    # An address that resembles both is the user's own by the stronger claim, and naming the wallet is the more
    # useful answer
    JalAccountCreator(currency_id=2, number='', name='ARB wallet', investing=1, organization=1,
                      account_type=PredefinedAccountType.Wallet, address=HL_LOOKALIKES[0],
                      chain=AssetLocation.ARB_BLOCKCHAIN).commit()
    target = impersonated_target(ARB, HL_LOOKALIKES[1])
    assert target['kind'] == ACCOUNT and target['name'] == 'ARB wallet'


def test_a_contract_of_another_chain_is_not_a_candidate(prepare_db):
    # The registry is asked for the chain the movement happened on: the same address is a different contract (or
    # none at all) elsewhere, and one chain's protocol says nothing about another's.
    assert impersonated_target(ETH, HL_LOOKALIKES[0]) is None


# ----------------------------------------------------------------------------------------------------------------------
# The thresholds are a statement about PROBABILITY and were written for hex, so an address in a richer alphabet must
# not be asked for the same character COUNT - that would demand far more improbability of it than hex was ever asked.
SOL = AssetLocation.SOL_BLOCKCHAIN
SOL_GENUINE = "7FBMXMu2cC2s8jJHbTGz3M6fYEq31GyXGNWwszV34ETP"


def test_thresholds_keep_the_probability_not_the_character_count():
    assert _thresholds(ETH, "0x" + "a" * 40) == (3, 7)          # hex is the baseline and does not move
    assert _thresholds(SOL, SOL_GENUINE) == (2, 5)              # 58^-5 is already stricter than 16^-7
    assert _thresholds(AssetLocation.TRX_BLOCKCHAIN, "T" + "a" * 33) == (2, 5)
    assert _thresholds(AssetLocation.BTC_BLOCKCHAIN, "1" + "a" * 33) == (2, 5)
    assert _thresholds(AssetLocation.BTC_BLOCKCHAIN, "bc1q" + "a" * 38) == (2, 6)   # 32 symbols, told by the prefix


# A base58 lookalike matching three characters at each end is one chance in 38 billion - far past the bar hex is
# held to - and was refused only for being six characters rather than seven.
def test_a_three_and_three_base58_lookalike_is_now_recognized():
    lookalike = SOL_GENUINE[:3] + "Z" * 38 + SOL_GENUINE[-3:]
    assert address_resemblance(SOL, lookalike, SOL_GENUINE) == (3, 3)
    assert is_lookalike(SOL, lookalike, SOL_GENUINE)


# The per-end bar moves too, down to two: it is not the probability claim - the combined bar is - and only asks that
# the resemblance is present at both ends. One character is not a resemblance, so two is where it stops.
def test_one_character_at_one_end_is_never_enough():
    lookalike = SOL_GENUINE[:7] + "Z" * 36 + SOL_GENUINE[-1:]
    assert address_resemblance(SOL, lookalike, SOL_GENUINE) == (7, 1)
    assert is_lookalike(SOL, lookalike, SOL_GENUINE) is False


# The real 0.00001 SOL arrival of 2026-02-15 (leg 4597, payment 2007 of the live database): three characters at the
# front and two at the back, sent 17 seconds after a genuine transfer to another wallet of the same user. Five base58
# characters is one chance in 656 million - stricter than the 1 in 268 million hex is held to - so it was ground
# deliberately, and rounding the per-end bar up to hex's three was the only thing keeping it out.
def test_the_real_solana_poisoning_of_2026_02_15_is_recognized():
    sender = "7FBYsS4zSc2NVvFjxUyPyTjNkZHhwJH5tzrYgGyYszTP"
    assert address_resemblance(SOL, sender, SOL_GENUINE) == (3, 2)
    assert is_lookalike(SOL, sender, SOL_GENUINE)


# Two and two is four characters, one short of the combined bar - the per-end bar dropping to two must not let a pair
# through that the probability claim itself refuses.
def test_two_and_two_in_base58_is_still_one_character_short():
    lookalike = SOL_GENUINE[:2] + "Z" * 40 + SOL_GENUINE[-2:]
    assert address_resemblance(SOL, lookalike, SOL_GENUINE) == (2, 2)
    assert is_lookalike(SOL, lookalike, SOL_GENUINE) is False


# The rescaling for richer alphabets must not touch hex: the total-agreement threshold there stays at 7, so 3
# characters at each end (six total) still falls one short and must not be recognized.
def test_the_hex_chains_are_unchanged():
    body = GENUINE[2:]                                          # the '0x' is stripped before anything is counted
    six_of_seven = "0x" + body[:3] + "9" * 34 + body[-3:]       # 3 + 3 = 6, one short in hex
    assert address_resemblance(ETH, six_of_seven, GENUINE) == (3, 3)
    assert is_lookalike(ETH, six_of_seven, GENUINE) is False
