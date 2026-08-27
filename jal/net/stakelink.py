import json
from decimal import Decimal

from bip_utils.utils.crypto import Kekkak256

# ----------------------------------------------------------------------------------------------------------------------
# How stake.link reports what it holds for an account, and nothing else - the module knows the protocol, not JAL's
# accounts. It exists because stake.link's LINK position is the one staking container so far whose size cannot be
# read from the chain alone: the amount is split between an on-chain queue and an OFF-CHAIN merkle distribution, of
# which only the root and an IPFS hash are published.
#
# The PriorityPool (an ERC1967 proxy, see the note in net/chain_fetchers/protocols.py) takes LINK into a queue for
# Chainlink's native staking pool. When the queued LINK is finally staked, the pool mints stLINK for itself and
# credits the account a number of SHARES through a merkle tree it publishes to IPFS; the stLINK stays inside the
# pool until the account calls claimLSDTokens(). stLINK is a rebasing token, so the yield lives entirely in the
# share -> token rate and NOTHING is emitted when it grows - which is exactly the case chain_balances.py exists for.
#
# So an account's whole position, valued in LINK, is
#     getQueuedTokens(account, amount)      LINK still waiting in the queue (amount = the tree's entry for it)
#   + getLSDTokens(account, sharesAmount)   = getStakeByShares(sharesAmount - alreadyClaimedShares), i.e. the
#                                            unclaimed stLINK WITH the yield it has accrued
# and both parameters come from the account's entry in the tree. Neither half may be dropped: everything deposited
# since the last distribution is still in the queue, and everything distributed is in the second half only.

# Contract of the LINK PriorityPool on Ethereum mainnet, normalized. It is the address a stake.link staking box
# carries, which is what the balance reader dispatches on - see ChainBalanceReader._evm_box_readers().
PRIORITY_POOL = '0xddc796a66e8b83d0bccd97df33a6ccfba8fd60ea'

# Call data of the PriorityPool views that take no arguments - the function selector alone.
SELECTOR_TOKEN = '0xfc0c546a'          # token() - the asset the pool takes, i.e. LINK
SELECTOR_IPFS_HASH = '0xc623674f'      # ipfsHash() - digest of the published distribution
SELECTOR_MERKLE_ROOT = '0x2eb4a7ab'    # merkleRoot() - root of the same distribution, the thing it is verified against
SELECTOR_QUEUED_TOKENS = '0x766715e7'  # getQueuedTokens(address,uint256)
SELECTOR_LSD_TOKENS = '0x2ab0faf5'     # getLSDTokens(address,uint256)

# Where the published distribution is read from, tried in order. The first is the gateway stake.link's own dApp
# reads it through, so the CID is guaranteed to be pinned there; the second is the public gateway, which needs the
# CID to still be reachable through the DHT. Which of them answers doesn't matter - the payload is verified against
# the on-chain root either way (see distribution_entry), so a gateway cannot make JAL show a quantity that the
# contract would not honour.
IPFS_GATEWAYS = ["https://bronze-elderly-halibut-521.mypinata.cloud/ipfs/", "https://ipfs.io/ipfs/"]

_BASE58 = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
_DAG_PB_SHA256 = b'\x12\x20'   # multihash prefix of a CIDv0: dag-pb, sha2-256, 32 bytes


def _keccak(data: bytes) -> bytes:
    return Kekkak256.QuickDigest(data)


# The CIDv0 the contract's ipfsHash() names. The bytes32 IS the sha2-256 digest of the published object, so the
# whole content identifier is that digest with the multihash prefix in front of it, in base58.
def ipfs_cid(digest: bytes) -> str:
    if len(digest) != 32:
        return ''
    raw = _DAG_PB_SHA256 + digest
    number = int.from_bytes(raw, 'big')
    encoded = ''
    while number:
        number, remainder = divmod(number, 58)
        encoded = _BASE58[remainder] + encoded
    for byte in raw:            # every leading zero byte is one leading '1', which the arithmetic above drops
        if byte:
            break
        encoded = '1' + encoded
    return encoded


# Leaf of one account in the distribution tree, exactly as the contract computes it before verifying a proof:
#     keccak256(bytes.concat(keccak256(abi.encode(account, amount, sharesAmount))))
# abi.encode pads every value to 32 bytes, which is what makes this different from the packed encoding.
def _leaf(address: str, amount: int, shares: int) -> bytes:
    account = bytes.fromhex(address.lower().removeprefix('0x')).rjust(32, b'\0')
    return _keccak(_keccak(account + amount.to_bytes(32, 'big') + shares.to_bytes(32, 'big')))


# Root of the tree the given leaves build, as OpenZeppelin's MerkleProof verifies it: leaves sorted, a complete
# binary tree laid out back to front, and every pair of children hashed in sorted order so the proof needs no
# left/right flags. Reproducing it is what makes the IPFS payload trustworthy - see distribution_entry().
def _merkle_root(leaves: list) -> bytes:
    leaves = sorted(leaves)
    count = len(leaves)
    if not count:
        return b''
    tree = [b'\0' * 32] * (2 * count - 1)
    for index, leaf in enumerate(leaves):
        tree[2 * count - 2 - index] = leaf
    for index in range(count - 2, -1, -1):
        left, right = tree[2 * index + 1], tree[2 * index + 2]
        tree[index] = _keccak(left + right if left < right else right + left)
    return tree[0]


# The published payload is a JSON STRING that contains the JSON object, so it decodes twice. Anything else is not
# the distribution and is refused rather than picked apart.
def _decode_payload(payload):
    for _ in range(2):
        if isinstance(payload, dict):
            return payload
        if not isinstance(payload, str):
            return None
        try:
            payload = json.loads(payload)
        except (json.JSONDecodeError, ValueError):
            return None
    return payload if isinstance(payload, dict) else None


# Call data of a view that takes (address, uint256): the selector followed by both arguments padded to a full
# 32-byte word each, which is what abi.encode does to them.
def call_data(selector: str, address: str, value: int) -> str:
    return selector + address.lower().removeprefix('0x').rjust(64, '0') + format(value, '064x')


# One account's entry in the published distribution as (amount, sharesAmount) in wei, or None when the payload
# doesn't match the root the contract published.
#
# The verification is the whole point of doing this here rather than trusting the gateway: the tree is REBUILT from
# the payload and its root compared with the on-chain one, so an altered entry - anywhere in the file, for anyone -
# changes the root and the payload is thrown away. What is left is a quantity the contract itself would honour.
#
# An account that is absent from the tree is not an error: it queued LINK that no distribution has covered yet, and
# a zero entry is the honest answer for it (the whole position is then still in the queue).
def distribution_entry(payload, expected_root: bytes, address: str):
    data = _decode_payload(payload)
    if data is None or not isinstance(data.get('data'), dict):
        return None
    entries = data['data']
    try:
        leaves = [_leaf(account, int(x['amount']), int(x['sharesAmount'])) for account, x in entries.items()]
    except (KeyError, TypeError, ValueError):
        return None
    if not leaves or _merkle_root(leaves) != expected_root:
        return None
    for account, entry in entries.items():
        if account.lower() == address.lower():
            return int(entry['amount']), int(entry['sharesAmount'])
    return 0, 0


# The two halves of a position added up and scaled to whole tokens. They are kept apart until here because they are
# read with two different calls and either of them may legitimately be zero.
def position(queued: int, unclaimed: int, decimals: int) -> Decimal:
    return (Decimal(queued) + Decimal(unclaimed)) / (Decimal('10') ** decimals)
