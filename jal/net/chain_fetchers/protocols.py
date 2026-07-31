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
# belongs to; entries flagged "VERIFY" are pending the user's confirmation of the exact on-chain address (CRYPTO_PATH
# decision #40).
#
# The name is the protocol as a human calls it, and it is NOT decoration: an operation the fetcher can only record
# partially (a custody transfer, an arriving bridge leg) carries it into the description of what it books, so the
# ledger says which protocol the movement has to be reconciled with rather than just quoting a contract address.
# It is deliberately not translated - a protocol is a proper name and reads the same in every language.
_REGISTRY = {
    AssetLocation.ETH_BLOCKCHAIN: {
        '0x66a9893cc07d91d95644aedd05d03f95e1dba8af': (ProtocolCategory.SWAP, 'Uniswap Universal Router (V4)'),        # VERIFY
        '0x9008d19f58aabd9ed0d60971565aa8510560ab41': (ProtocolCategory.SWAP, 'CoW Protocol GPv2Settlement'),          # VERIFY
        '0x0000000000001ff3684f28c67538d4d072c22734': (ProtocolCategory.SWAP, '0x Protocol AllowanceHolder'),          # VERIFY
        '0x1231deb6f5749ef6ce6943a275a1d3e7486f4eae': (ProtocolCategory.AGGREGATOR, 'LI.FI Diamond (Jumper)'),         # VERIFY
        '0xa6e941eab67569ca4522f70d343714ff51d571c4': (ProtocolCategory.AGGREGATOR, 'Magpie / Fly.trade Router V3.1'), # VERIFY
        '0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2': (ProtocolCategory.LENDING, 'Aave v3 Pool'),                      # VERIFY
        # The entries below were read off the wallet's own history and each one's category is what its transactions
        # actually do (see the shapes quoted next to them), not what its name suggests. For Fluid and stkGHO the
        # contract the wallet calls IS the receipt token's own contract - the registry is keyed by address, so that
        # is fine.
        '0xd01607c3c5ecaba394d8be377a08590149325722': (ProtocolCategory.LENDING, 'Aave WrappedTokenGateway'),  # 0.1546 ETH -> 0.15468900016691433 aEthWETH
        '0xce6ced23118edeb23054e06118a702797b13fc2f': (ProtocolCategory.LENDING, 'Aave Umbrella'),             # 7.570364 aEthUSDT -> 6.582313 stkwaEthUSDT.v1
        '0x1a88df1cfe15af22b3c4c783d4e6f7f9e0c1885d': (ProtocolCategory.LENDING, 'Aave Safety Module (stkGHO)'),  # GHO <-> stkGHO, exactly 1:1
        '0x6a29a46e21c730dca1d8b23d637c101cec605c5b': (ProtocolCategory.LENDING, 'Fluid fGHO vault'),   # 51426.334 GHO -> 47034.887 fGHO
        '0x5c20b550819128074fd538edf79791733ccedd18': (ProtocolCategory.LENDING, 'Fluid fUSDT vault'),  # 34101.87 USDT -> 29052.162587 fUSDT
        '0x90551c1795392094fe6d29b758eccd233cfaa260': (ProtocolCategory.LENDING, 'Fluid fWETH vault'),  # 0.3 ETH -> 0.280388106858573068 fWETH
        '0x89c6340b1a1f4b25d36cd8b063d49045caf3f818': (ProtocolCategory.AGGREGATOR, 'LI.FI Permit2Proxy'),  # its constructor names the diamond above
        '0x4da27a545c0c5b758a6ba100e3a049001de870f5': (ProtocolCategory.LENDING, 'Staked Aave (stkAAVE)'),  # AAVE <-> stkAAVE, and claims pay AAVE
        '0x3ef3d8ba38ebe18db133cec108f4d14ce00dd9ae': (ProtocolCategory.REWARD, 'Merkl Distributor'),      # VERIFY
        '0x4655ce3d625a63d30ba704087e52b4c31e38188b': (ProtocolCategory.REWARD, 'Aave rewards distributor'),  # pays out aEthUSDT with no counter-leg
        '0xddc796a66e8b83d0bccd97df33a6ccfba8fd60ea': (ProtocolCategory.CUSTODY, 'stake.link PriorityPool'),   # see below
        '0x7060fe0dd3e31be01efac6b28c8d38018fd163b0': (ProtocolCategory.REWARD, 'FluidMerkleDistributor'),  # pays FLUID
        # USDT0's LayerZero OFT Adapter, the lock side of Tether's omnichain USDT: USDT is locked here on Ethereum
        # and USD₮0 is minted on the destination chain (which is why the arriving leg there comes from the zero
        # address and names no contract of its own, so it has no registry entry and is paired by hand).
        # Verified three ways: the wallet's own history shows USDT going in and coming back out of this address on
        # Ethereum with a USD₮0 mint on Arbitrum minutes later for the same amount; usdt0.to's deployment list names
        # it "OFT Adapter" on Ethereum (chain id 1, LZ EID 30101); and Everdawn Labs' audit-report repository lists
        # the same address with 0xdac17f958d2ee523a2206206994597c13d831ec7 (native USDT) as its inner token.
        '0x6c96de32cea08842dcc4058c14d3aaad7fa41dee': (ProtocolCategory.BRIDGE, 'USDT0 OFT Adapter'),
        # Chainlink CCIP, the bridge behind app.aave.com's GHO transfers. The wallet calls the Router and nothing
        # else - the token pool that takes the asset, the OnRamp that is paid the fee and the OffRamp that delivers
        # on the other side are all called by CCIP itself, so the Router is the only address a wallet-signed
        # transaction ever names here. It carries any CCIP token, not GHO alone.
        # Verified: the contract is Chainlink's documented mainnet Router and is named 'Router' in its verified
        # source; the wallet's send of 2026-06-14 calls it with ccipSend() (0x96f4e9f9) and moves GHO in TWO legs -
        # 48100.476931 to the token pool (0x06179f7c1be40863405f374e7f5f8806c728660a) and 0.523069 as the CCIP fee
        # to the OnRamp (0x913814782144864e523c3fdb78e3ca25d2c2aeca) - and 17 minutes later exactly the pool's
        # amount was minted to the wallet on Arbitrum.
        # The fee needs no rule of its own here: it is paid in the very token being bridged, so the two legs net
        # into ONE asset leaving and the crossing keeps its shape. What is sent is therefore slightly more than what
        # arrives, and the difference surfaces as the Bridge's in-kind fee (out_qty - in_qty) once the arrival is
        # matched - which is what it is. That is unlike the LayerZero fee above, paid in the native coin and so a
        # second asset leaving, which _take_messaging_fee has to lift out before the shape can be read.
        # Only the sending side is a registry entry: an arrival is submitted by the OffRamp, so the wallet is neither
        # the 'from' nor the 'to' of that transaction and it has no interacted-with contract to look up - it lands as
        # a plain incoming transfer and is paired by hand, exactly as the USDT0 mint above is.
        '0x80226fc0ee2b096224eeac085bb9a8cba1146f7d': (ProtocolCategory.BRIDGE, 'Chainlink CCIP Router'),
        '0xf398e66b1273a34558aebbec550dccaf4acc7714': (ProtocolCategory.REWARD, 'FluidMerkleDistributor'),  # pays GHO
        '0xd833484b198d3d05707832cc1c2d62b520d95b8a': (ProtocolCategory.REWARD, 'FluidMerkleDistributor'),  # pays FLUID
    },
    AssetLocation.ARB_BLOCKCHAIN: {
        '0xa51afafe0263b40edaef0df8781ea9aa03e381a3': (ProtocolCategory.SWAP, 'Uniswap Universal Router (V4)'),      # VERIFY
        '0x4c60051384bd2d3c01bfc845cf5f4b44bcbe9de5': (ProtocolCategory.SWAP, 'Uniswap Universal Router (v1)'),      # VERIFY
        '0x9008d19f58aabd9ed0d60971565aa8510560ab41': (ProtocolCategory.SWAP, 'CoW Protocol GPv2Settlement'),        # VERIFY
        '0x1231deb6f5749ef6ce6943a275a1d3e7486f4eae': (ProtocolCategory.AGGREGATOR, 'LI.FI Diamond (Jumper)'),       # VERIFY
        '0xfb1b08ba6ba284934d817ea3c9d18f592cc59a50': (ProtocolCategory.AGGREGATOR, 'Magpie / Fly.trade Router V3'), # VERIFY
        '0x794a61358d6845594f94dc1db02a252b5b4814ad': (ProtocolCategory.LENDING, 'Aave v3 Pool'),                    # VERIFY
        '0x2df1c51e09aecf9cacb7bc98cb1742757f163df7': (ProtocolCategory.BRIDGE, 'Hyperliquid Bridge2'),  # verified: the wallet's 4 HL deposits + 1 withdrawal go through it on Arbitrum
        '0x89c6340b1a1f4b25d36cd8b063d49045caf3f818': (ProtocolCategory.AGGREGATOR, 'LI.FI Permit2Proxy'),  # same address as on Ethereum
        # Fluid deploys a separate vault per market per chain, so these are NOT the Ethereum addresses
        '0x037dff1c12805707d7c29f163e0f09fc9102657a': (ProtocolCategory.LENDING, 'Fluid fGHO vault'),   # fToken 'Fluid Gho Token': GHO <-> fGHO
        '0x4a03f37e7d3fc243e3f99341d36f4b829bee5e03': (ProtocolCategory.LENDING, 'Fluid fUSDT vault'),  # fToken 'Fluid Tether USD': USD₮0 <-> fUSDT
        '0x3ef3d8ba38ebe18db133cec108f4d14ce00dd9ae': (ProtocolCategory.REWARD, 'Merkl Distributor'),   # VERIFY
        '0xf36029358a684cddd5103a4b84dc8a832c6e5b40': (ProtocolCategory.REWARD, 'FluidMerkleDistributor'),  # pays FLUID
        '0x94312a608246cecfce6811db84b3ef4b2619054e': (ProtocolCategory.REWARD, 'FluidMerkleDistributor'),  # pays FLUID
        # The other end of the USDT0 bridge, and NOT the address it has on Ethereum: there the contract is an
        # adapter that locks real USDT, here USD₮0 is the omnichain token itself, which the send burns. So the two
        # sides are two contracts with two roles, and each needs its entry - a protocol that does reuse one address
        # across chains (the LI.FI diamond above) still needs one per chain, since the registry is keyed by both.
        # Verified: usdt0.to lists it as the Arbitrum "OFT" (against Ethereum's "OFT Adapter"), and the wallet's own
        # history pays it the LayerZero messaging fee in ETH in the very transaction that burns USD₮0 to the zero
        # address - the burn names no contract, so this fee is what identifies the crossing on this side.
        '0x14e4a1b13bf7f943c8ff7c51fb60fa964a298d92': (ProtocolCategory.BRIDGE, 'USDT0 OFT'),
        # The Arbitrum end of Chainlink CCIP - a different address than on Ethereum, and verified on its own: the
        # contract is named 'Router' in its verified source and the wallet's sends of 2025-12-03 and 2026-07-10 call
        # it with ccipSend() (0x96f4e9f9), each answered on Ethereum ~20 minutes later by a release of the same
        # amount from the Ethereum token pool. Same two-leg shape as on Ethereum: the bridged GHO goes to the
        # Arbitrum token pool (0xb94ab28c6869466a46a42aba834ca2b3cecca5eb, unchanged between the two sends) and the
        # fee to the lane's OnRamp - which was 'EVM2EVMOnRamp' (0x67761742ac8a21ec4d76ca18cbd701e5a6f3bef3) in 2025
        # and 'OnRamp' (0x76a443768a5e3b8d1aed0105fc250877841deb40) in 2026. CCIP replaced its onramps in between,
        # which is precisely why the entry is the Router the wallet calls and not a contract the token reaches.
        '0x141fa059441e0ca23ce184b6a78bafd2a517dde8': (ProtocolCategory.BRIDGE, 'Chainlink CCIP Router'),
    },
    # Avalanche C-chain has no entries yet, deliberately. The wallet it was validated against has not sent a single
    # transaction on that chain, so there is no contract whose category could be read off its own history - and a
    # registry entry is never written from documentation or from memory (#58). The chain's DeFi protocols (Trader
    # Joe, Aave v3, LI.FI, ...) deploy at addresses of their own here, NOT at the Ethereum ones a few rows above.
    # Nothing is missed by the table being empty: the first transaction that swaps or lends through a contract halts
    # the import and names the address, which is exactly the evidence an entry has to be based on.
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
#
# Protocols that are deliberately NOT in the table above, and why:
#  - Fluid (Instadapp): there is no single router - each market has its own vault contract (which IS its fToken),
#    per chain. Those the wallet uses are listed above; a new market self-reveals by halting the import.
#  - RocketX: no single public router address was confirmed - add the address it reports when first met.
#  - Trocador: an asset-changing bridge that routes through deposit addresses rather than a contract the wallet calls,
#    so it isn't a registry entry - it belongs to the P5 cross-chain "pending half-bridge" matching instead.


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
