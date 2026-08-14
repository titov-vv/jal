from PySide6.QtCore import QT_TRANSLATE_NOOP

from jal.constants import AssetLocation
from jal.db.settings_registry import SettingsRegistry, SettingDescriptor
from jal.net.chain_fetchers.evm import EVMFetcher

JAL_FETCHER_CLASS = "AvalancheFetcher"


# ----------------------------------------------------------------------------------------------------------------------
# Avalanche C-chain - the EVM-compatible chain of Avalanche, and the only one of its three JAL reads: the X- and
# P-chains have a different model altogether and no EVM address, so nothing of this fetcher would apply to them.
# Every classification is inherited from EVMFetcher; what this chain changes is where the data comes from.
#
# Etherscan's V2 API does know chain id 43114, but serves it on a paid tier only, so the history is read from
# Routescan instead - a different provider exposing the same 'module'/'action' surface, with its own key, its own
# rate limits and its own result window. Its native coin, AVAX, is its own asset and not ETH, so its dust threshold
# and its DeFiLlama pricing key are its own as well (constants.py / downloader.py).
class AvalancheFetcher(EVMFetcher):
    location_id = AssetLocation.AVAX_BLOCKCHAIN
    chain_id = 43114
    native_symbol = 'AVAX'
    native_name = "Avalanche"
    display_symbol = 'AVAX'
    api_root = "https://api.routescan.io/v2/network/mainnet/evm/43114/etherscan/api"
    api_name = "Routescan"
    api_key_setting = "ApiKey_Routescan"
    # Routescan refuses any query whose page x offset exceeds 10000 ("Result window is too large"), so the whole page
    # budget has to fit inside that product - 10 pages of 1000 rather than Etherscan's 20 of 10000. Verified live
    # 2026-07-29: page=10 with offset=1000 is served, page=11 is refused. A history longer than one budget is not
    # lost - the window is per query and the following fetch reads on from where this one stopped (EVMFetcher.
    # _note_window_limit), which is also why the two values must be changed together.
    page_size = 1000
    max_pages = 10
    # AVAX is worth single-digit dollars where ETH is worth thousands, so the inherited ETH threshold would sit far
    # below anything an attacker bothers to send here. The wallet this was validated against was poisoned with
    # 0.0000083608 AVAX, which this value catches.
    native_dust_threshold = '0.0001'

    def __init__(self):
        super().__init__()
        self.name = self.tr("A&valanche")


SettingsRegistry.register(SettingDescriptor(
    key="DustThreshold_AVAX",
    page=QT_TRANSLATE_NOOP("Preferences", "Blockchain"),
    label=QT_TRANSLATE_NOOP("Preferences", "AVAX dust threshold"), default=AvalancheFetcher.native_dust_threshold,
    tooltip=QT_TRANSLATE_NOOP("Preferences",
                              "An incoming AVAX transfer below this amount, from an address you never dealt with, "
                              "is recorded as a dust attack instead of an ordinary transfer.")))
