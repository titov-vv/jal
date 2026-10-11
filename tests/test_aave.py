from jal.net import aave

# ----------------------------------------------------------------------------------------------------------------------
# How Aave's Safety module answers, and how much of an answer may be believed. Nothing here touches the network or the
# database: the module is the protocol and knows nothing about JAL's accounts, exactly as jal/net/merkl.py does.
#
# The vectors are real - the live Ethereum contracts read on 2026-08-31 for one wallet: stkAAVE answered
# REWARD_TOKEN() with AAVE and getTotalRewardsBalance() with 0.006901428237272013 AAVE, which is what the dApp showed
# at that moment to the last digit.
STAKER = '0x0000000000000000000000000000000000000001'
AAVE = '0x7fc66500c84a76ad7e9c93437bfc5ac33e2ddae9'
OWED = 6901428237272013


def test_the_call_data_carries_the_staker_as_a_full_word():
    data = aave.rewards_call(STAKER)
    assert data.startswith(aave.SELECTOR_TOTAL_REWARDS)
    assert len(data) == len(aave.SELECTOR_TOTAL_REWARDS) + 64
    # the address case must not change the call - the contract sees 20 bytes, not a string
    assert aave.rewards_call(STAKER.upper().replace('0X', '0x')) == data


def test_a_staker_that_is_not_an_address_yields_no_call():
    assert aave.rewards_call('not an address') == ''
    assert aave.rewards_call('0x' + 'ab' * 33) == ''


def test_a_one_word_answer_is_the_address_it_holds():
    assert aave.address_answer('0x' + '00' * 12 + AAVE.removeprefix('0x')) == AAVE


# An answer of a different length is a call that returned something else, and the tail of it would be a random
# contract this would then ask for a name and a price.
def test_an_answer_of_the_wrong_length_is_not_an_address():
    assert aave.address_answer('0x' + '00' * 12 + AAVE.removeprefix('0x') + '00' * 32) == ''
    assert aave.address_answer('0x1234') == ''
    assert aave.address_answer('') == ''
    assert aave.address_answer(None) == ''


# The top 12 bytes of an address word are empty by construction, so a word that fills them is not an address at all -
# a hash returned by the wrong view would otherwise become a contract the reader goes on to ask for a name and a
# price. It cannot catch every wrong answer, a small number being padded exactly like an address, which is why the
# reward token is only ever read from the view that returns nothing else.
def test_a_word_that_is_not_padded_like_an_address_is_refused():
    assert aave.address_answer('0x' + 'ab' * 32) == ''
    assert aave.address_answer('0x' + format(2 ** 200, '064x')) == ''


def test_a_one_word_answer_is_the_quantity_it_holds():
    assert aave.amount_answer('0x' + format(OWED, '064x')) == OWED
    assert aave.amount_answer('0x' + '00' * 32) == 0


def test_an_answer_of_the_wrong_length_is_not_a_quantity():
    assert aave.amount_answer('0x' + format(OWED, '064x') + '00' * 32) is None
    assert aave.amount_answer('0x') is None
    assert aave.amount_answer('') is None
    assert aave.amount_answer(None) is None


# Both modules are read by one reader, so the table of them is what says which contracts exist at all
def test_both_safety_modules_are_registered_and_normalized():
    assert aave.SAFETY_MODULES == (aave.STAKED_AAVE, aave.STAKED_GHO)
    assert all(x == x.lower() and len(x) == 42 for x in aave.SAFETY_MODULES)


# ----------------------------------------------------------------------------------------------------------------------
# Aave v4. The selectors are the ones the live Core Hub and Main Spoke answered on 2026-10-11.
def test_v4_call_data_packs_addresses_and_integers_as_words():
    data = aave.call_data(aave.SELECTOR_SPOKE_RESERVE_ID, aave.CORE_HUB, 8)
    assert data == '0x42aef1f1' + '0' * 24 + aave.CORE_HUB[2:] + format(8, '064x')
    assert aave.call_data(aave.SELECTOR_SPOKE_SUPPLIED, 11, STAKER) == '0xf1568a89' + format(11, '064x') + '0' * 24 + STAKER[2:]
    assert aave.call_data(aave.SELECTOR_HUB_ASSET_ID, 'not an address') == ''
    assert aave.call_data(aave.SELECTOR_HUB_ASSET_ID, -1) == ''


def test_v4_spokes_are_registered_per_hub_and_normalized():
    assert aave.V4_SPOKES == {aave.CORE_HUB: (aave.MAIN_SPOKE,)}
    assert all(x == x.lower() and len(x) == 42 for x in (aave.CORE_HUB, aave.MAIN_SPOKE))
