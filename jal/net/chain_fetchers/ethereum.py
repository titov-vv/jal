from jal.constants import AssetLocation
from jal.net.chain_fetchers.evm import EVMFetcher

JAL_FETCHER_CLASS = "EthereumFetcher"


# ----------------------------------------------------------------------------------------------------------------------
# Ethereum mainnet. All of the work is in EVMFetcher; this only pins the Etherscan chain id and the native coin.
class EthereumFetcher(EVMFetcher):
    location_id = AssetLocation.ETH_BLOCKCHAIN
    chain_id = 1
    native_symbol = 'ETH'
    native_name = "Ethereum"

    def __init__(self):
        super().__init__()
        self.name = self.tr("Ethereum")
