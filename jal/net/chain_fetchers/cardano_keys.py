from bip_utils import AdaShelleyStakingAddrEncoder, Bech32ChecksumError, Bech32Decoder, Bip32ChainCode, Bip32Depth, \
    Bip32KeyData, Bip32KholawEd25519

from jal.db.token_blacklist import is_cardano_account_key, is_cardano_stake_address, normalize_address
from jal.constants import AssetLocation

# ----------------------------------------------------------------------------------------------------------------------
# The stake address of a Cardano wallet, which is what the chain is queried by: every payment address of the wallet
# carries the same stake credential, so one stake address stands for all of them (no address scan, no gap limit).
#
# A wallet account holds either the stake address itself or the account public key exported from the wallet. The
# stake key is the account key's child '2/0' (CIP-1852 role 2 = staking), derived without any private material.
_ACCOUNT_KEY_HRP = 'acct_xvk'
_ACCOUNT_DEPTH = 3          # m / 1852' / 1815' / account'
_STAKING_ROLE = 2
_STAKING_INDEX = 0


# Stake address of a wallet given by either form; ValueError for anything else
def stake_address(address: str) -> str:
    address = normalize_address(AssetLocation.ADA_BLOCKCHAIN, address)
    if is_cardano_stake_address(address):
        return address
    if not is_cardano_account_key(address):
        raise ValueError(f"Not a Cardano stake address or account public key: {address}")
    try:
        raw = Bech32Decoder.Decode(_ACCOUNT_KEY_HRP, address)
        account = Bip32KholawEd25519.FromPublicKey(
            raw[:32], Bip32KeyData(chain_code=Bip32ChainCode(raw[32:]), depth=Bip32Depth(_ACCOUNT_DEPTH)))
        stake_key = account.ChildKey(_STAKING_ROLE).ChildKey(_STAKING_INDEX).PublicKey()
    except (ValueError, TypeError, Bech32ChecksumError) as error:
        raise ValueError(f"Not a valid Cardano account public key: {error}")
    return AdaShelleyStakingAddrEncoder.EncodeKey(stake_key.KeyObject())
