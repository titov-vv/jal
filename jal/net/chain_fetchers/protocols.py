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


# {location_id: {normalized_address: ProtocolCategory}}. Every address below is marked with the protocol it belongs to;
# entries flagged "VERIFY" are pending the user's confirmation of the exact on-chain address (CRYPTO_PATH decision #40).
_REGISTRY = {
    AssetLocation.ETH_BLOCKCHAIN: {
        '0x66a9893cc07d91d95644aedd05d03f95e1dba8af': ProtocolCategory.SWAP,        # Uniswap Universal Router (V4) - VERIFY
        '0x9008d19f58aabd9ed0d60971565aa8510560ab41': ProtocolCategory.SWAP,        # CoW Protocol GPv2Settlement - VERIFY
        '0x1231deb6f5749ef6ce6943a275a1d3e7486f4eae': ProtocolCategory.AGGREGATOR,  # LI.FI Diamond (Jumper) - VERIFY
        '0xa6e941eab67569ca4522f70d343714ff51d571c4': ProtocolCategory.AGGREGATOR,  # Magpie / Fly.trade Router V3.1 - VERIFY
        '0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2': ProtocolCategory.LENDING,     # Aave v3 Pool - VERIFY
        # The entries below were read off the wallet's own history and each one's category is what its transactions
        # actually do (see the shapes quoted next to them), not what its name suggests. For Fluid and stkGHO the
        # contract the wallet calls IS the receipt token's own contract - the registry is keyed by address, so that
        # is fine.
        '0xd01607c3c5ecaba394d8be377a08590149325722': ProtocolCategory.LENDING,     # Aave WrappedTokenGateway: 0.1546 ETH -> 0.15468900016691433 aEthWETH
        '0xce6ced23118edeb23054e06118a702797b13fc2f': ProtocolCategory.LENDING,     # Aave Umbrella: 7.570364 aEthUSDT -> 6.582313 stkwaEthUSDT.v1
        '0x1a88df1cfe15af22b3c4c783d4e6f7f9e0c1885d': ProtocolCategory.LENDING,     # stkGHO / Aave Safety Module: GHO <-> stkGHO, exactly 1:1
        '0x6a29a46e21c730dca1d8b23d637c101cec605c5b': ProtocolCategory.LENDING,     # Fluid fGHO vault: 51426.334 GHO -> 47034.887 fGHO
        '0x5c20b550819128074fd538edf79791733ccedd18': ProtocolCategory.LENDING,     # Fluid fUSDT vault: 34101.87 USDT -> 29052.162587 fUSDT
        '0x90551c1795392094fe6d29b758eccd233cfaa260': ProtocolCategory.LENDING,     # Fluid fWETH vault: 0.3 ETH -> 0.280388106858573068 fWETH
        '0x3ef3d8ba38ebe18db133cec108f4d14ce00dd9ae': ProtocolCategory.REWARD,      # Merkl Distributor - VERIFY
        '0x4655ce3d625a63d30ba704087e52b4c31e38188b': ProtocolCategory.REWARD,      # Pays out aEthUSDT with no counter-leg
    },
    AssetLocation.ARB_BLOCKCHAIN: {
        '0xa51afafe0263b40edaef0df8781ea9aa03e381a3': ProtocolCategory.SWAP,        # Uniswap Universal Router (V4) - VERIFY
        '0x4c60051384bd2d3c01bfc845cf5f4b44bcbe9de5': ProtocolCategory.SWAP,        # Uniswap Universal Router (v1) - VERIFY
        '0x9008d19f58aabd9ed0d60971565aa8510560ab41': ProtocolCategory.SWAP,        # CoW Protocol GPv2Settlement - VERIFY
        '0x1231deb6f5749ef6ce6943a275a1d3e7486f4eae': ProtocolCategory.AGGREGATOR,  # LI.FI Diamond (Jumper) - VERIFY
        '0xfb1b08ba6ba284934d817ea3c9d18f592cc59a50': ProtocolCategory.AGGREGATOR,  # Magpie / Fly.trade Router V3 - VERIFY
        '0x794a61358d6845594f94dc1db02a252b5b4814ad': ProtocolCategory.LENDING,     # Aave v3 Pool - VERIFY
        '0x2df1c51e09aecf9cacb7bc98cb1742757f163df7': ProtocolCategory.BRIDGE,      # Hyperliquid Bridge2 - VERIFY
        '0x3ef3d8ba38ebe18db133cec108f4d14ce00dd9ae': ProtocolCategory.REWARD,      # Merkl Distributor - VERIFY
    },
}

# Protocols the user named that are NOT in the table above, and why:
#  - Fluid (Instadapp): its users interact with many per-market vault/DEX contracts, not one router - the exact
#    addresses you use need to be listed (each as LENDING, or the DEX as SWAP). They self-reveal: an unregistered
#    Fluid contract halts the import and reports its address, which you then add here.
#  - RocketX: no single public router address was confirmed - add the address it reports when first met.
#  - Trocador: an asset-changing bridge that routes through deposit addresses rather than a contract the wallet calls,
#    so it isn't a registry entry - it belongs to the P5 cross-chain "pending half-bridge" matching instead.


# Returns the ProtocolCategory a contract belongs to on the given chain, or None when the address is not a known
# protocol. The address is normalized before the lookup, so the caller may pass it in whatever case the chain reported.
def protocol_category(location_id: int, address: str):
    if not address:
        return None
    normalized = normalize_address(location_id, address)
    return _REGISTRY.get(location_id, {}).get(normalized)
