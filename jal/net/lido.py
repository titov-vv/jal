from jal.constants import AssetLocation

# ----------------------------------------------------------------------------------------------------------------------
# Lido liquid staking on Ethereum mainnet, addresses from https://docs.lido.fi/deployed-contracts/
PROTOCOL = 'Lido'    # AssetData.Protocol of stETH and wstETH

STETH = {AssetLocation.ETH_BLOCKCHAIN: '0xae7ab96520de3a18e5e111b5eaab095312d7fe84'}    # rebasing: quantity grows
WSTETH = {AssetLocation.ETH_BLOCKCHAIN: '0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0'}   # share token: price grows


# The marks of a Lido receipt token as (rebasing, protocol), or None for any other contract
def receipt_marks(location_id: int, contract: str):
    if contract and contract == STETH.get(location_id):
        return True, PROTOCOL
    if contract and contract == WSTETH.get(location_id):
        return False, PROTOCOL
    return None
