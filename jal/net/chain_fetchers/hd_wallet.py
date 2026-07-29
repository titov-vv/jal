from bip_utils import Base58ChecksumError, Base58Decoder, Base58Encoder, Bip32Slip10Secp256k1, Bip32KeyError, \
    P2PKHAddrEncoder, P2SHAddrEncoder, P2WPKHAddrEncoder

# ----------------------------------------------------------------------------------------------------------------------
# Address derivation for a hierarchical-deterministic (BIP32) Bitcoin wallet.
#
# A modern wallet is not an address but a key tree: every payment received lands on a fresh address and every payment
# sent returns the change to yet another one, so tracking a single address stops being right the moment the wallet is
# used (CRYPTO_PATH note, the 'xpub' companion). What the user exports from the device is the ACCOUNT-LEVEL EXTENDED
# PUBLIC KEY (m/purpose'/0'/account'), from which all of the account's addresses - and nothing else - can be computed
# locally. No private material is involved: an extended PUBLIC key can derive addresses but can not spend from them.
#
# Only the two standard branches of BIP44 are derived: '.../0/i' receive and '.../1/i' change.


# The three script types this module can produce a key's address in. BIP86/Taproot ('bc1p...') is deliberately absent:
# it derives from the same tree but is out of the scope validated against a real wallet, and an untested address form
# would silently report an empty wallet rather than fail.
class ScriptType:
    P2PKH = 'p2pkh'              # BIP44, legacy, '1...'
    P2SH_P2WPKH = 'p2sh-p2wpkh'  # BIP49, SegWit wrapped in P2SH, '3...'
    P2WPKH = 'p2wpkh'            # BIP84, native SegWit, 'bc1q...'
    ALL = [P2WPKH, P2SH_P2WPKH, P2PKH]


RECEIVE_BRANCH = 0
CHANGE_BRANCH = 1

# Version bytes of a mainnet extended public key, and the ones the SLIP-132 variants use instead. SLIP-132 encodes the
# script type of the account into the serialization prefix (ypub/zpub), while the key material behind it is the very
# same BIP32 key - so the prefix is normalized away here and the script type is decided separately, see below.
_XPUB_VERSION = bytes.fromhex('0488b21e')
_SLIP132_SCRIPT_TYPES = {
    'xpub': ScriptType.P2PKH,
    'ypub': ScriptType.P2SH_P2WPKH,
    'zpub': ScriptType.P2WPKH
}
_P2PKH_NET_VERSION = b'\x00'    # first byte of a legacy mainnet address, giving it its leading '1'
_P2SH_NET_VERSION = b'\x05'     # ... and of a P2SH one, giving it its leading '3'
_BECH32_HRP = 'bc'              # human-readable part of a mainnet native SegWit address


# True if the text is an extended public key rather than a plain address. Only mainnet public keys are accepted:
# a private key (xprv/yprv/zprv) is not something JAL has any use for and must never be pasted into a ledger, and
# a testnet key (tpub) belongs to no chain JAL tracks.
def is_extended_key(key: str) -> bool:
    return key[:4].lower() in _SLIP132_SCRIPT_TYPES and len(key) > 100


# The script type the key's own serialization claims - a HINT ONLY, never a conclusion.
#
# Exporters disagree on this: a wallet may hand out an 'xpub'-prefixed key for an account that is really BIP84, and
# then the prefix says legacy '1...' while every address of the account is 'bc1q...'. Deriving the wrong form yields
# perfectly valid addresses that simply belong to nobody, and the wallet looks empty rather than broken. The fetcher
# therefore confirms the type against the chain and keeps this only as the order in which to try (decision #74).
def preferred_script_type(key: str) -> str:
    return _SLIP132_SCRIPT_TYPES.get(key[:4].lower(), ScriptType.P2WPKH)


# ----------------------------------------------------------------------------------------------------------------------
# One account-level extended public key, deriving the addresses of its two branches on demand.
#
# Derivation is pure computation - no network, no private key - but it is not free (a few milliseconds per address),
# and a gap-limit scan asks for the same addresses on every fetch, so both the branch keys and the addresses derived
# from them are cached for the lifetime of the object.
class HDAccount:
    def __init__(self, key: str):
        self._key = key.strip()
        try:
            self._account = Bip32Slip10Secp256k1.FromExtendedKey(self._normalized_key())
        except (Bip32KeyError, Base58ChecksumError, ValueError) as error:
            raise ValueError(f"Not a valid extended public key: {error}")
        if not self._account.IsPublicOnly():   # a private key derives the same addresses, but JAL must never hold one
            raise ValueError("An extended PRIVATE key was given where a public one is expected")
        self._branches = {}
        self._addresses = {}

    # bip_utils validates the version bytes against the key type it is asked for, so a SLIP-132 key (ypub/zpub) is
    # rejected by the plain BIP32 parser although it holds an ordinary BIP32 key. Re-serializing it with the xpub
    # version bytes changes nothing but the four bytes that say how it was named.
    def _normalized_key(self) -> str:
        raw = Base58Decoder.CheckDecode(self._key)
        if raw[:4] == _XPUB_VERSION:
            return self._key
        return Base58Encoder.CheckEncode(_XPUB_VERSION + raw[4:])

    # Address of '.../branch/index' in the given script type
    def address(self, branch: int, index: int, script_type: str) -> str:
        cached = self._addresses.get((branch, index, script_type))
        if cached is None:
            cached = self._encode(self._branch(branch).ChildKey(index).PublicKey(), script_type)
            self._addresses[(branch, index, script_type)] = cached
        return cached

    def _branch(self, branch: int):
        if branch not in self._branches:
            self._branches[branch] = self._account.ChildKey(branch)
        return self._branches[branch]

    @staticmethod
    def _encode(public_key, script_type: str) -> str:
        if script_type == ScriptType.P2WPKH:
            return P2WPKHAddrEncoder.EncodeKey(public_key.KeyObject(), hrp=_BECH32_HRP)
        if script_type == ScriptType.P2SH_P2WPKH:
            return P2SHAddrEncoder.EncodeKey(public_key.KeyObject(), net_ver=_P2SH_NET_VERSION)
        if script_type == ScriptType.P2PKH:
            return P2PKHAddrEncoder.EncodeKey(public_key.KeyObject(), net_ver=_P2PKH_NET_VERSION)
        raise ValueError(f"Unknown script type: {script_type}")
