from decimal import Decimal

from jal.net import merkl

# ----------------------------------------------------------------------------------------------------------------------
# What Merkl's distribution says, checked against the arithmetic the Distributor itself performs. Nothing here touches
# the network or the database: the module is the protocol and knows nothing about JAL's accounts, exactly as
# jal/net/stakelink.py does.
#
# The vectors are real - one entry of the live Ethereum tree on 2026-08-30, read for a throwaway address that belongs
# to nobody (0x...01). The root below is what Distributor.getMerkleRoot() answered at that moment, and the proof was
# verified against it end to end, so a change that breaks the leaf shape or the walk fails here rather than on the
# user's screen.
ROOT = bytes.fromhex('da4c4fbc7a0b303813e616e672a837ad898389a982ad9dc57dbd41e618e64b9e')
USER = '0x0000000000000000000000000000000000000001'
TOKEN = '0xD223bbdd0421E394C0df9dFfe568f1dADfFd6f85'
AMOUNT = 9076071563221601707
PROOFS = [
          '0x2a87967b83d72b7eea347b85d8e38d06e8e4f17436eef420e62f20357ef53d02',
          '0x82aab8bf13a37c1106f46bb5684eeea861dc7d0ef83294a33b6e20615043eb47',
          '0xac2af8b5e42967ef5df164eda9a922e07789b1ced13b6d039f5ee01be7344356',
          '0x34a7274a03e7cf95400ec8f0f5e8fb57cd03b333b9df84ad58c5af70136dcbf2',
          '0xde39cce806d80a4f2e259998a0ca6615bab3a0722d79e39846897b69b0ea9daa',
          '0xb252d8f6a019a65349bfc1edef49acd1f51299290760f3a17494d2bcdacadc0e',
          '0xe183cb63e05c632cb6bb562977a4b224056b5008a804513c1b158c928348afdb',
          '0xde5cf78bbf33fdf80ad8a39da0aa4a5848a08725919d088612e79177b3991176',
          '0xc0b88332a739947ee5a4885e1f35173ed5851e0c684f4c471705eb2acb437be7',
          '0x321558ebdbfdad16a00ea307aeba539acbb75be45b2ef58678524e244e25faa1',
          '0xdef3dbea86a99232567cb38d8a73270dfe7d94f395146597990195addef44297',
          '0xb46e2827da5eb51a24614567710ac792196564883fcae5a64fe88c83261e3cc3',
          '0xa7bcf88f631ff3f083be070f721eee6021baf9e140563537499c2182b7c0f0da',
          '0x9d06b071dbbf641e9b14f6dc5bf3571a526789ba3f1c0ec21c72cc46a30bb84a',
          '0x12969de2440c07b30b533637ad56b31df157de7d9affa1826e6d0254fb416081',
          '0x6267ba18741d4cc72aa5afd87bcbf7fe0b8cd2768ced829ac386cdd7e2861441',
          '0x25d04e65ae6d5bea3707e12dd26eebc1f321e287eaaa33f3c0377d5b1825bfce',
          '0x71d73856c5fd6bcbddb06853a0b58e384cba165cba559d7dda789f3ae720654c',
          '0xe59279e5ee45adfefad58b4269518cc9528dbee8ca5458078af8d71344857b3b',
]


def test_a_leaf_is_a_single_hash_of_the_padded_triple():
    leaf = merkl.leaf(USER, TOKEN, AMOUNT)
    assert len(leaf) == 32
    # The address case must not change the leaf - the contract sees 20 bytes, not a string
    assert merkl.leaf(USER.upper().replace('0X', '0x'), TOKEN.lower(), AMOUNT) == leaf


def test_a_malformed_address_yields_no_leaf():
    assert merkl.leaf('not an address', TOKEN, AMOUNT) == b''
    assert merkl.leaf(USER, TOKEN, -1) == b''


# The walk itself, against a root the contract published. This is the whole trust model in one assertion.
def test_a_published_proof_walks_to_the_root_the_contract_holds():
    assert merkl.verified_amount(USER, TOKEN, AMOUNT, PROOFS, ROOT) == AMOUNT


# The reason the walk is done at all: an amount nobody would honour must not become a figure on screen.
def test_an_amount_the_tree_does_not_award_is_refused():
    assert merkl.verified_amount(USER, TOKEN, AMOUNT + 1, PROOFS, ROOT) is None
    assert merkl.verified_amount(USER, TOKEN, AMOUNT - 1, PROOFS, ROOT) is None


def test_a_reward_for_another_account_or_token_is_refused():
    other = '0x0000000000000000000000000000000000000002'
    assert merkl.verified_amount(other, TOKEN, AMOUNT, PROOFS, ROOT) is None
    assert merkl.verified_amount(USER, USER, AMOUNT, PROOFS, ROOT) is None


def test_a_damaged_proof_is_refused_rather_than_walked_partway():
    assert merkl.verified_amount(USER, TOKEN, AMOUNT, PROOFS[:-1], ROOT) is None
    assert merkl.verified_amount(USER, TOKEN, AMOUNT, ['0xnothexatall'], ROOT) is None
    assert merkl.verified_amount(USER, TOKEN, AMOUNT, ['0x1234'], ROOT) is None
    assert merkl.verified_amount(USER, TOKEN, AMOUNT, PROOFS, b'') is None


# A single-leaf tree has an empty proof and the leaf IS the root - a shape the walk has to handle without a special case
def test_an_empty_proof_leaves_the_leaf_as_the_root():
    leaf = merkl.leaf(USER, TOKEN, AMOUNT)
    assert merkl.verified_amount(USER, TOKEN, AMOUNT, [], leaf) == AMOUNT


# claimed() answers with three words and only the first is a quantity. Reading a shorter answer leniently would
# invent a figure out of whatever the call actually returned.
def test_only_the_first_word_of_claimed_is_the_quantity():
    answer = '0x' + format(1234567890, '064x') + format(1700000000, '064x') + 'ab' * 32
    assert merkl.claimed_amount(answer) == 1234567890


def test_an_answer_of_the_wrong_length_is_not_a_quantity():
    assert merkl.claimed_amount('0x' + format(5, '064x')) is None
    assert merkl.claimed_amount('0x') is None
    assert merkl.claimed_amount('') is None
    assert merkl.claimed_amount(None) is None


def test_the_call_data_carries_both_arguments_as_full_words():
    data = merkl.claimed_call(USER, TOKEN)
    assert data.startswith(merkl.SELECTOR_CLAIMED)
    assert len(data) == 10 + 128
    assert data[10:74] == '0' * 63 + '1'                    # the account, left-padded
    assert data[74:].endswith(TOKEN.lower().removeprefix('0x'))
    assert merkl.claimed_call('nonsense', TOKEN) == ''


# One chain's block is picked out of an answer that covers several, and a chain with no campaign is not an error
def test_rewards_are_taken_from_the_block_of_the_chain_asked_about():
    answer = [{'chain': {'id': 1}, 'rewards': [{'a': 1}]}, {'chain': {'id': 42161}, 'rewards': []}]
    assert merkl.chain_rewards(answer, 1) == [{'a': 1}]
    assert merkl.chain_rewards(answer, 42161) == []
    assert merkl.chain_rewards(answer, 43114) == []
    assert merkl.chain_rewards({'not': 'a list'}, 1) is None


def test_a_reward_line_is_reduced_to_what_is_needed():
    entry = merkl.reward_entry({'amount': '100', 'pending': '7', 'proofs': ['0xaa'],
                                'token': {'address': TOKEN, 'symbol': 'GHO', 'decimals': 18}})
    assert entry == {'address': TOKEN, 'symbol': 'GHO', 'decimals': 18,
                     'amount': 100, 'pending': 7, 'proofs': ['0xaa']}


def test_a_line_that_is_not_a_reward_is_refused():
    assert merkl.reward_entry({'amount': '100'}) is None
    assert merkl.reward_entry({'amount': 'lots', 'token': {'address': TOKEN, 'symbol': 'X', 'decimals': 18}}) is None
    assert merkl.reward_entry(None) is None


# A missing 'pending' is zero and not an absent field: the API leaves it out when nothing is accruing
def test_a_missing_pending_is_nothing_accruing():
    entry = merkl.reward_entry({'amount': '100', 'proofs': [],
                                'token': {'address': TOKEN, 'symbol': 'GHO', 'decimals': 18}})
    assert entry['pending'] == 0


# Money must never pass through a float - the scaling is exact all the way down to the last wei
def test_scaling_keeps_every_decimal():
    assert merkl.quantity(9076071563221601707, 18) == Decimal('9.076071563221601707')
    assert merkl.quantity(28258, 6) == Decimal('0.028258')
    assert merkl.quantity(0, 18) == Decimal('0')
