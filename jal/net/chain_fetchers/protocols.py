from jal.constants import AssetLocation
from jal.db.token_blacklist import normalize_address


# ----------------------------------------------------------------------------------------------------------------------
# Registry that maps a DeFi contract address (the "Interacted With / To" of a wallet-initiated transaction) to the kind
# of operation it performs. The EVM per-transaction classifier uses it to tell a swap from a lending deposit or a
# bridge when a single transaction moves one asset out and another in - the leg shapes alone can't distinguish them,
# and an on-chain contract never says what it is, so the mapping is curated knowledge.
#
# It is deliberately NOT self-populating (unlike the cross-chain token unification): a wrong entry here would
# mis-book a financial operation, so every address is human-verified before it lands. Addresses are stored normalized
# (EVM = lower-case) and keyed per chain, because a protocol may deploy at a different address on each chain (and some,
# like the LI.FI diamond, reuse one address everywhere - listed under each chain it is used on all the same).
class ProtocolCategory:
    SWAP = 'swap'             # same-chain DEX / swap router: one asset out, one in -> Swap operation
    AGGREGATOR = 'aggregator'  # does BOTH same-chain swaps and cross-chain bridges - the leg shape decides which
    LENDING = 'lending'       # deposit/withdraw into a lending, wrapping or staking protocol -> Conversion operation
    BRIDGE = 'bridge'         # cross-chain bridge - deferred to P5
    REWARD = 'reward'         # protocol that pays out a claimable reward - booked as a StakingReward
    CUSTODY = 'custody'       # holds the asset for the wallet and issues NO receipt token -> plain transfers


# {location_id: {normalized_address: (ProtocolCategory, name)}}. Every address below is marked with the protocol it
# belongs to.
#
# The name is the protocol as a human calls it, and it is NOT decoration: an operation the fetcher can only record
# partially (a custody transfer, an arriving bridge leg) carries it into the description of what it books, so the
# ledger says which protocol the movement has to be reconciled with rather than just quoting a contract address.
# It is deliberately not translated - a protocol is a proper name and reads the same in every language.
_REGISTRY = {
    AssetLocation.ETH_BLOCKCHAIN: {
        '0x66a9893cc07d91d95644aedd05d03f95e1dba8af': (ProtocolCategory.SWAP, 'Uniswap Universal Router (V4)'),
        '0x9008d19f58aabd9ed0d60971565aa8510560ab41': (ProtocolCategory.SWAP, 'CoW Protocol GPv2Settlement'),
        '0x0000000000001ff3684f28c67538d4d072c22734': (ProtocolCategory.SWAP, '0x Protocol AllowanceHolder'),
        '0x1231deb6f5749ef6ce6943a275a1d3e7486f4eae': (ProtocolCategory.AGGREGATOR, 'LI.FI Diamond (Jumper)'),
        '0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2': (ProtocolCategory.LENDING, 'Aave v3 Pool'),
        '0xd01607c3c5ecaba394d8be377a08590149325722': (ProtocolCategory.LENDING, 'Aave WrappedTokenGateway'),
        '0xce6ced23118edeb23054e06118a702797b13fc2f': (ProtocolCategory.LENDING, 'Aave Umbrella'),
        '0x1a88df1cfe15af22b3c4c783d4e6f7f9e0c1885d': (ProtocolCategory.LENDING, 'Aave Safety Module (stkGHO)'),
        '0x6a29a46e21c730dca1d8b23d637c101cec605c5b': (ProtocolCategory.LENDING, 'Fluid fGHO vault'),
        '0x5c20b550819128074fd538edf79791733ccedd18': (ProtocolCategory.LENDING, 'Fluid fUSDT vault'),
        '0x90551c1795392094fe6d29b758eccd233cfaa260': (ProtocolCategory.LENDING, 'Fluid fWETH vault'),
        '0x89c6340b1a1f4b25d36cd8b063d49045caf3f818': (ProtocolCategory.AGGREGATOR, 'LI.FI Permit2Proxy'),
        '0x4da27a545c0c5b758a6ba100e3a049001de870f5': (ProtocolCategory.LENDING, 'Staked Aave (stkAAVE)'),
        '0x3ef3d8ba38ebe18db133cec108f4d14ce00dd9ae': (ProtocolCategory.REWARD, 'Merkl Distributor'),
        '0x4655ce3d625a63d30ba704087e52b4c31e38188b': (ProtocolCategory.REWARD, 'Aave rewards distributor'),
        '0xddc796a66e8b83d0bccd97df33a6ccfba8fd60ea': (ProtocolCategory.CUSTODY, 'stake.link PriorityPool'),
        '0x7060fe0dd3e31be01efac6b28c8d38018fd163b0': (ProtocolCategory.REWARD, 'FluidMerkleDistributor'),
        '0x6c96de32cea08842dcc4058c14d3aaad7fa41dee': (ProtocolCategory.BRIDGE, 'USDT0 OFT Adapter'),
        '0x80226fc0ee2b096224eeac085bb9a8cba1146f7d': (ProtocolCategory.BRIDGE, 'Chainlink CCIP Router'),
        '0xa95c5ebb86e0de73b4fb8c47a45b792cfea28c23': (ProtocolCategory.CUSTODY, 'stake.link SDL staking'),
        '0xf398e66b1273a34558aebbec550dccaf4acc7714': (ProtocolCategory.REWARD, 'FluidMerkleDistributor'),
        '0xd833484b198d3d05707832cc1c2d62b520d95b8a': (ProtocolCategory.REWARD, 'FluidMerkleDistributor'),
    },
    AssetLocation.ARB_BLOCKCHAIN: {
        '0xa51afafe0263b40edaef0df8781ea9aa03e381a3': (ProtocolCategory.SWAP, 'Uniswap Universal Router (V4)'),
        '0x4c60051384bd2d3c01bfc845cf5f4b44bcbe9de5': (ProtocolCategory.SWAP, 'Uniswap Universal Router (v1)'),
        '0x9008d19f58aabd9ed0d60971565aa8510560ab41': (ProtocolCategory.SWAP, 'CoW Protocol GPv2Settlement'),
        '0x1231deb6f5749ef6ce6943a275a1d3e7486f4eae': (ProtocolCategory.AGGREGATOR, 'LI.FI Diamond (Jumper)'),
        '0x794a61358d6845594f94dc1db02a252b5b4814ad': (ProtocolCategory.LENDING, 'Aave v3 Pool'),
        '0x2df1c51e09aecf9cacb7bc98cb1742757f163df7': (ProtocolCategory.BRIDGE, 'Hyperliquid Bridge2'),
        '0x89c6340b1a1f4b25d36cd8b063d49045caf3f818': (ProtocolCategory.AGGREGATOR, 'LI.FI Permit2Proxy'),
        '0x037dff1c12805707d7c29f163e0f09fc9102657a': (ProtocolCategory.LENDING, 'Fluid fGHO vault'),
        '0x4a03f37e7d3fc243e3f99341d36f4b829bee5e03': (ProtocolCategory.LENDING, 'Fluid fUSDT vault'),
        '0x3ef3d8ba38ebe18db133cec108f4d14ce00dd9ae': (ProtocolCategory.REWARD, 'Merkl Distributor'),
        '0xf36029358a684cddd5103a4b84dc8a832c6e5b40': (ProtocolCategory.REWARD, 'FluidMerkleDistributor'),
        '0x94312a608246cecfce6811db84b3ef4b2619054e': (ProtocolCategory.REWARD, 'FluidMerkleDistributor'),
        '0x14e4a1b13bf7f943c8ff7c51fb60fa964a298d92': (ProtocolCategory.BRIDGE, 'USDT0 OFT'),
        '0x141fa059441e0ca23ce184b6a78bafd2a517dde8': (ProtocolCategory.BRIDGE, 'Chainlink CCIP Router'),
        '0xa95d9c1f655341597c94393fddc30cf3c08e4fce': (ProtocolCategory.BRIDGE, 'Circle CCTP'),
        '0x69460570c93f9de5e2edbc3052bf10125f0ca22d': (ProtocolCategory.AGGREGATOR, 'Rango Diamond'),
        '0xc6868edf1d2a7a8b759856cb8afa333210dfeda6': (ProtocolCategory.AGGREGATOR, 'Aori'),
        '0x4cd00e387622c35bddb9b4c962c136462338bc31': (ProtocolCategory.BRIDGE, 'Relay Depository'),
    },
    AssetLocation.AVAX_BLOCKCHAIN: {},
}

# Why stake.link's PriorityPool is CUSTODY and not LENDING or REWARD (verified on-chain, 2026-07-22; it is the first
# real sighting of the "container that issues no receipt token" case CRYPTO_PATH #56 deferred):
#   0xddc796a6... is an ERC1967Proxy over `PriorityPool`. It takes LINK into a queue for Chainlink's native staking
#   pool, which is usually full. When the queued LINK is finally staked, the pool does NOT send a receipt token back:
#   it credits the account a number of SHARES through a merkle tree published to IPFS (`merkleRoot()` / `ipfsHash()`),
#   and holds the resulting stLINK inside itself until the account calls `claimLSDTokens(amount, shares, proof)`.
#   So a wallet can have its whole balance staked and still show a zero stLINK ERC-20 balance and no stLINK transfer
#   in its token history - there is nothing on-chain in the wallet to convert into.
#   Neither of the neighbouring categories can express that: as LENDING every deposit would halt (one asset out, none
#   in), and as REWARD the LINK the pool gives back - which `unqueueTokens` returns to the wallet unstaked, to the wei
#   it was queued with - would be booked as income the account never earned.
#   As CUSTODY both directions become plain transfers with an unknown counterparty, which the import asks the user to
#   map to an account of their own - the account-as-a-box pattern the term deposits use. The yield accruing inside the
#   pool stays unrecognized until it is claimed, exactly as an Aave position's does between interactions.

# The registry entry of a contract on the given chain as a (category, name) tuple, or None when the address is not a
# known protocol. The address is normalized before the lookup, so the caller may pass it in whatever case the chain
# reported.
def _protocol_entry(location_id: int, address: str):
    if not address:
        return None
    normalized = normalize_address(location_id, address)
    return _REGISTRY.get(location_id, {}).get(normalized)


# Returns the ProtocolCategory a contract belongs to on the given chain, or None when the address is not a known
# protocol.
def protocol_category(location_id: int, address: str):
    entry = _protocol_entry(location_id, address)
    return entry[0] if entry else None


# Returns the human name of a known protocol, or an empty string for an address the registry doesn't hold. Used to
# name the protocol in the description of an operation that has to be reconciled by hand later on.
def protocol_name(location_id: int, address: str) -> str:
    entry = _protocol_entry(location_id, address)
    return entry[1] if entry else ''


# Every name the registry knows, longest first.
#
# It is what lets an operation be traced back to the protocol it went through AFTER it was imported. The name is the
# only part of that which is recorded: an import writes it into the operation's description, and nothing else about
# the contract survives - the address in a transfer is the one the asset moved with (a bridge's token pool), not the
# contract the wallet called. So a reader that wants the protocol looks for these names in the description.
#
# Longest first because the names overlap by design - 'USDT0 OFT' is the whole of 'USDT0 OFT Adapter', which is a
# different contract on a different chain - and the first match found must be the more specific one.
#
# Reading the names rather than the text around them is what makes this survive translation: the sentence an import
# writes around the name is localized and differs between the two ends of one crossing ("Sent through X" on the
# send, "[bridge] X: ..." on the arrival), while the name itself is data and is written the same way in both.
def protocol_names() -> list:
    names = {name for protocols in _REGISTRY.values() for _, name in protocols.values()}
    return sorted(names, key=len, reverse=True)


# Every contract the registry holds for one chain, as (address, name) pairs.
#
# The addresses are stored normalized, so they come out ready to be compared with one the chain reported. It exists
# for the reader that needs the whole set rather than one lookup - address_match.impersonated_target(), which asks
# which KNOWN address a poisoning lookalike was ground to imitate, and for which these contracts are the addresses a
# wallet meets most often and recognizes least well.
def protocol_contracts(location_id: int) -> list:
    return [(address, name) for address, (_, name) in _REGISTRY.get(location_id, {}).items()]
