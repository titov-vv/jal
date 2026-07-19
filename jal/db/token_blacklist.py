import logging
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
