import logging
from hashlib import sha256
from datetime import datetime, timezone
from jal.constants import AssetLocation
from jal.db.db import JalDB
from jal.universal_cache import UniversalCache


# Chains where an address is a hex string and its case carries no meaning (EIP-55 checksum casing is
# only a checksum). Solana mint addresses and Tron base58check addresses (the 'T...' form) ARE
# case-sensitive and must be kept verbatim, Bitcoin has no tokens.
_CASE_INSENSITIVE_CHAINS = [AssetLocation.ETH_BLOCKCHAIN, AssetLocation.ARB_BLOCKCHAIN]


# Brings a contract/mint address to the form that is stored in the database. SQLite compares TEXT
# case-sensitively, so every read and every write of an address must pass through this function.
def normalize_address(location_id: int, address: str) -> str:
    if not address:
        return ''
    address = address.strip()
    if location_id in _CASE_INSENSITIVE_CHAINS:
        address = address.lower()
    return address


# ----------------------------------------------------------------------------------------------------------------------
# Tron addresses have two encodings of the very same 20-byte value: the base58check 'T...' form that the user sees
# everywhere (explorers, wallets, the TRC-20 endpoint of TronGrid) and a 21-byte hex form prefixed with 0x41 that
# the raw transaction data of TronGrid returns - and keeps returning even when 'visible=true' is requested.
# JAL stores the base58check form only, so hex addresses must be converted as they are read from the chain.
_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_TRON_PREFIX = 0x41            # First byte of every Tron address in its binary form
_TRON_ADDRESS_LENGTH = 34      # Length of a base58check address, always starting with 'T' due to the 0x41 prefix


def _base58_encode(data: bytes) -> str:
    value = int.from_bytes(data, 'big')
    encoded = ''
    while value:
        value, index = divmod(value, 58)
        encoded = _BASE58_ALPHABET[index] + encoded
    for byte in data:   # Each leading zero byte is encoded as a leading '1' and would be lost by the math above
        if byte:
            break
        encoded = _BASE58_ALPHABET[0] + encoded
    return encoded


def _base58_decode(text: str) -> bytes:
    value = 0
    for char in text:
        index = _BASE58_ALPHABET.find(char)
        if index < 0:
            raise ValueError(f"Invalid base58 character '{char}'")
        value = value * 58 + index
    decoded = value.to_bytes((value.bit_length() + 7) // 8, 'big')
    leading_zeros = len(text) - len(text.lstrip(_BASE58_ALPHABET[0]))
    return b'\x00' * leading_zeros + decoded


# Converts a Tron address from its hex form into the base58check 'T...' form that JAL stores.
# Accepts the 21-byte '41...' form that TronGrid returns, with or without a '0x' prefix, and also the bare 20-byte
# form (as an EVM-style address) - the 0x41 prefix is then added. Returns '' if the value isn't a Tron address,
# so that a caller may pass any address through without checking its shape first.
def tron_address_from_hex(address: str) -> str:
    if not address:
        return ''
    address = address.strip()
    if address.startswith('0x') or address.startswith('0X'):
        address = address[2:]
    try:
        raw = bytes.fromhex(address)
    except ValueError:
        return ''
    if len(raw) == 20:              # A bare 20-byte address gets the Tron prefix that its hex form omitted
        raw = bytes([_TRON_PREFIX]) + raw
    if len(raw) != 21 or raw[0] != _TRON_PREFIX:
        return ''
    checksum = sha256(sha256(raw).digest()).digest()[:4]
    return _base58_encode(raw + checksum)


# True if the given string is a valid Tron base58check address, checksum included. Tron addresses are handed over
# by users (a wallet account address) and by token lists, and a mistyped one must never reach the database:
# a wrong address silently fetches an empty history instead of failing.
def is_tron_address(address: str) -> bool:
    if not address or len(address) != _TRON_ADDRESS_LENGTH:
        return False
    try:
        raw = _base58_decode(address)
    except ValueError:
        return False
    if len(raw) != 25 or raw[0] != _TRON_PREFIX:
        return False
    payload, checksum = raw[:21], raw[21:]
    return sha256(sha256(payload).digest()).digest()[:4] == checksum


# ----------------------------------------------------------------------------------------------------------------------
# A single row of the 'token_blacklist' table: a token that was found in a wallet but must never be imported
# (unsolicited dust airdrop, scam/fake token, or a token the user rejected manually). Blacklisted tokens
# deliberately don't exist as assets or symbols - the point is to keep attacker-controlled names and tickers
# out of the asset tables entirely. Removing a row un-blacklists the token, so the next fetch imports it.
# The object is addressed by the chain + contract address pair, as there is no id known before the first import.
class JalTokenBlacklist(JalDB):
    db_cache = UniversalCache()

    def __init__(self, location_id: int = 0, address: str = '') -> None:
        super().__init__(cached=True)
        try:
            self._location_id = int(location_id)
        except (TypeError, ValueError):
            self._location_id = 0
        self._address = normalize_address(self._location_id, address)
        self._data = self.db_cache.get_data(self._load_entry, (self._location_id, self._address))
        if self._data is None:
            self._data = {}
        self._id = self._data.get('id', 0)

    def invalidate_cache(self):
        self.db_cache.clear_cache()

    # JalTokenBlacklist maintains single cache available for all instances
    @classmethod
    def class_cache(cls) -> True:
        return True

    # Loads a single 'token_blacklist' row (as a dict) or None if the token isn't blacklisted.
    # Used as the loader function behind the shared UniversalCache (keyed by chain + address).
    @classmethod
    def _load_entry(cls, location_id: int, address: str) -> dict:
        return cls._read("SELECT * FROM token_blacklist WHERE location_id=:location_id AND address=:address",
                         [(":location_id", location_id), (":address", address)], named=True)

    def id(self) -> int:
        return self._id

    def location(self) -> int:
        return self._location_id

    def address(self) -> str:
        return self._address

    def name_hint(self) -> str:
        return self._data.get('name_hint', '')

    def added_timestamp(self) -> int:
        return self._data.get('added_ts', 0)

    # True if the token was quarantined automatically by the policy, False if the user added it by hand
    def is_auto(self) -> bool:
        return bool(self._data.get('auto', 0))

    def blacklisted(self) -> bool:
        return self._id != 0

    @classmethod
    def is_blacklisted(cls, location_id: int, address: str) -> bool:
        return cls(location_id, address).blacklisted()

    # Adds a token to the blacklist (or updates the hint of an already blacklisted one) and returns the entry.
    @classmethod
    def add(cls, location_id: int, address: str, name_hint: str = '', auto: bool = True) -> "JalTokenBlacklist":
        address = normalize_address(location_id, address)
        if not address:
            raise ValueError("Can't blacklist a token without an address")
        timestamp = int(datetime.now(tz=timezone.utc).timestamp())
        cls._exec("INSERT OR REPLACE INTO token_blacklist(location_id, address, name_hint, added_ts, auto) "
                  "VALUES(:location_id, :address, :name_hint, :added_ts, :auto)",
                  [(":location_id", location_id), (":address", address), (":name_hint", name_hint),
                   (":added_ts", timestamp), (":auto", 1 if auto else 0)], commit=True)
        cls.db_cache.clear_cache()
        logging.info(f"Token {name_hint} ({address}) was blacklisted for chain {location_id}")
        return cls(location_id, address)

    # Removes a token from the blacklist - it will be imported by the next fetch
    @classmethod
    def remove(cls, location_id: int, address: str) -> None:
        address = normalize_address(location_id, address)
        cls._exec("DELETE FROM token_blacklist WHERE location_id=:location_id AND address=:address",
                  [(":location_id", location_id), (":address", address)], commit=True)
        cls.db_cache.clear_cache()

    # Returns all blacklisted tokens as a list of JalTokenBlacklist
    @classmethod
    def get_all(cls) -> list:
        entries = []
        query = cls._exec("SELECT location_id, address FROM token_blacklist ORDER BY added_ts DESC")
        while query.next():
            location_id, address = cls._read_record(query, cast=[int, str])
            entries.append(cls(location_id, address))
        return entries
