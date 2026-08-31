from decimal import Decimal

from bip_utils.utils.crypto import Kekkak256

# ----------------------------------------------------------------------------------------------------------------------
# How Merkl reports what it owes an account, and nothing else - the module knows the protocol, not JAL's accounts.
#
# Merkl pays campaign rewards through a merkle distribution: an off-chain tree is built for every epoch, its root is
# published to the Distributor contract, and an account claims by presenting its leaf with a proof. So what is owed is
# split between two places, and neither half alone is the answer:
#     amount                        the account's lifetime entry in the published tree, from the API
#   - claimed(account, token)       what the contract has already paid out, from the chain
#   = what is still claimable
# The subtraction is what keeps this from ever double-counting: the moment a claim goes through, the on-chain figure
# rises and the receivable falls to zero - at the same time as the claim itself is imported as a StakingReward.
#
# The API also reports 'pending', the part still accruing inside the current epoch. It has no proof and cannot be
# claimed today, so it is recorded but never valued.
#
# The tree is NOT trusted as served. A leaf is rebuilt from (account, token, amount), walked up through the proof and
# compared with the root the contract itself published - two eth_calls and O(log n) hashes, no bulk download. An
# altered amount changes the leaf, the walk lands somewhere else, and the answer is thrown away. What survives is a
# quantity the Distributor would actually honour.

# Merkl's Distributor, normalized. It is deployed at the same address on every chain Merkl serves, Ethereum and
# Arbitrum included - see the REWARD entries in net/chain_fetchers/protocols.py, where the same address is registered
# per chain so that a CLAIM is recognized when it is imported.
DISTRIBUTOR = '0x3ef3d8ba38ebe18db133cec108f4d14ce00dd9ae'

# One call per wallet covers every chain: 'chainId' takes a comma-separated list and the answer is one block per chain.
API_URL = "https://api.merkl.xyz/v4/users/{address}/rewards"

# Call data of the Distributor views - the function selector, followed by the arguments for the one that takes them.
SELECTOR_MERKLE_ROOT = '0x49590657'  # getMerkleRoot() - the root a proof has to walk to
SELECTOR_CLAIMED = '0x0c9cbf0e'      # claimed(address,address) -> (uint208 amount, uint48 timestamp, bytes32 root)

# 'claimed' answers with three words and only the first is a quantity; the other two say when the last claim happened
# and under which root, neither of which is needed here.
_CLAIMED_WORDS = 3


def _keccak(data: bytes) -> bytes:
    return Kekkak256.QuickDigest(data)


# One value as abi.encode writes it: padded to a full 32-byte word. An address is 20 bytes and pads on the LEFT.
def _word(address: str) -> bytes:
    try:
        return bytes.fromhex(address.lower().removeprefix('0x')).rjust(32, b'\0')
    except ValueError:
        return b''


# Leaf of one (account, token, amount) entry, exactly as the Distributor computes it before verifying a proof:
#     keccak256(abi.encode(account, token, amount))
# Note it is a SINGLE hash - unlike stake.link's double-hashed leaf - and that abi.encode pads every value to 32
# bytes, which is what makes this different from the packed encoding.
def leaf(account: str, token: str, amount: int) -> bytes:
    account, token = _word(account), _word(token)
    if not account or not token or amount < 0:
        return b''
    return _keccak(account + token + amount.to_bytes(32, 'big'))


# Root the given leaf walks to through its proof, as OpenZeppelin's MerkleProof verifies it: every pair of nodes is
# hashed in sorted order, so the proof needs no left/right flags. b'' when a proof element isn't a 32-byte hash.
def proof_root(node: bytes, proofs: list) -> bytes:
    if not node or not isinstance(proofs, list):
        return b''
    for element in proofs:
        if not isinstance(element, str):
            return b''
        try:
            sibling = bytes.fromhex(element.removeprefix('0x'))
        except ValueError:
            return b''
        if len(sibling) != 32:
            return b''
        node = _keccak(node + sibling if node < sibling else sibling + node)
    return node


# The entry's amount in wei, but ONLY if the tree really says so - otherwise None.
#
# This is the whole reason the proof is walked rather than the API's number being taken at face value: a reward is
# money, and the API is the one part of this reading that JAL neither controls nor can check afterwards. An amount
# whose leaf doesn't reach the published root is refused, and refusing is the only safe answer - a wrong figure here
# would be displayed as value the account owns.
def verified_amount(account: str, token: str, amount: int, proofs: list, expected_root: bytes):
    if not expected_root or len(expected_root) != 32:
        return None
    node = leaf(account, token, amount)
    if not node:
        return None
    return amount if proof_root(node, proofs) == expected_root else None


# Call data of claimed(address,address): the selector followed by both arguments as full 32-byte words.
def claimed_call(account: str, token: str) -> str:
    account, token = _word(account), _word(token)
    if not account or not token:
        return ''
    return SELECTOR_CLAIMED + account.hex() + token.hex()


# The quantity out of what claimed() answered - the first of its three words. An answer of a different length is not
# a short answer to read leniently, it is a call that returned something else, and reading it would invent a figure.
def claimed_amount(answer: str):
    try:
        data = bytes.fromhex(answer.removeprefix('0x'))
    except (ValueError, AttributeError):
        return None
    if len(data) != 32 * _CLAIMED_WORDS:
        return None
    return int.from_bytes(data[:32], 'big')


# The rewards the answer holds for one chain, or None when it says nothing about that chain at all.
#
# The answer is a list of {chain: {...}, rewards: [...]} blocks, one per chain asked about. A chain with no campaign
# for this wallet is simply absent, which is not an error - it is the ordinary state of most wallets on most chains.
def chain_rewards(answer, chain_id: int):
    if not isinstance(answer, list):
        return None
    for block in answer:
        if not isinstance(block, dict) or not isinstance(block.get('chain'), dict):
            continue
        if block['chain'].get('id') != chain_id:
            continue
        rewards = block.get('rewards')
        return rewards if isinstance(rewards, list) else []
    return []


# One reward line reduced to what JAL needs, as {'address', 'symbol', 'decimals', 'amount', 'pending', 'proofs'},
# or None when the line isn't shaped like a reward. Every numeric field of the API is a decimal STRING.
def reward_entry(reward):
    if not isinstance(reward, dict) or not isinstance(reward.get('token'), dict):
        return None
    token = reward['token']
    try:
        return {'address': str(token['address']), 'symbol': str(token['symbol']), 'decimals': int(token['decimals']),
                'amount': int(reward['amount']), 'pending': int(reward.get('pending', 0)),
                'proofs': reward.get('proofs', [])}
    except (KeyError, TypeError, ValueError):
        return None


# A bare integer of 'decimals' places scaled to whole tokens.
def quantity(raw: int, decimals: int) -> Decimal:
    return Decimal(raw) / (Decimal('10') ** decimals)
