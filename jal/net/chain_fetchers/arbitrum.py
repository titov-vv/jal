from jal.constants import AssetLocation
from jal.net.chain_fetchers.evm import EVMFetcher

JAL_FETCHER_CLASS = "ArbitrumFetcher"


# ----------------------------------------------------------------------------------------------------------------------
# Arbitrum One, an Ethereum L2 whose native coin is also ETH. It is served by the same Etherscan V2 endpoint and the
# same API key as mainnet, distinguished only by the chain id - so, like every EVM chain, it is a thin subclass.
class ArbitrumFetcher(EVMFetcher):
    location_id = AssetLocation.ARB_BLOCKCHAIN
    chain_id = 42161
    native_symbol = 'ETH'
    native_name = "Ethereum"

    def __init__(self):
        super().__init__()
        self.name = self.tr("Arbitrum")
