import logging
from dataclasses import dataclass
from decimal import Decimal, DecimalException
from jal.constants import Setup, TokenVerdict
from jal.db.settings import JalSettings
from jal.db.token_blacklist import JalTokenBlacklist
from jal.net.token_lists import TokenListProvider


# ----------------------------------------------------------------------------------------------------------------------
# Describes one token that a blockchain fetcher has found in a wallet and is about to import.
# Everything except the chain and the address is a hint that helps to tell an unsolicited dust airdrop
# from a token the user really holds; a fetcher that can't tell should leave the defaults.
@dataclass
class TokenCandidate:
    location_id: int                        # blockchain, see AssetLocation.*_BLOCKCHAIN
    address: str                            # contract/mint address of the token
    symbol: str = ''                        # ticker as seen on-chain - never trust it, anyone may deploy 'USDC'
    name: str = ''                          # token name as seen on-chain - equally untrusted
    incoming: bool = True                   # True if the token was received, False if it was sent by the user
    from_swap: bool = False                 # True if the token was acquired by a swap/trade made by the user
    known_counterparty: bool = False        # True if the user had operations with the sending address before
    amount: Decimal = Decimal('0')          # amount of the transfer
    value: Decimal = None                   # value of the transfer in account currency, None if it can't be priced


# ----------------------------------------------------------------------------------------------------------------------
# Implements the unknown/spam token policy: wallets receive worthless or fraudulent tokens that nobody asked for,
# and importing them would fill the asset tables, the balances and the tax reports with garbage carrying
# attacker-controlled names. Tokens are classified in three layers, the first two automatic:
#  1. the token is on an allow-list -> import it;
#  2. the token looks like a dust airdrop (came in from an unknown address, is worthless or unpriceable, or is on a
#     block-list) -> blacklist it: no asset, no symbol and no operation is created, but the token is recorded in
#     'token_blacklist' so the user may review the decision and undo it (the next fetch will then import the token);
#  3. anything else -> import it, as the user was involved in acquiring it.
# The policy applies to data fetched from blockchains only - broker statements are trusted and are not filtered.
class TokenFilter:
    def __init__(self, lists: TokenListProvider = None, dust_threshold: Decimal = None):
        self._lists = lists if lists is not None else TokenListProvider()
        self._dust_threshold = self._configured_threshold() if dust_threshold is None else dust_threshold

    # The threshold is user-editable in the preferences dialog ('TokenDustThreshold'). A value that isn't a
    # number is ignored in favour of the built-in default - a broken setting must not stop an import.
    @staticmethod
    def _configured_threshold() -> Decimal:
        value = JalSettings().getStr("TokenDustThreshold", Setup.TOKEN_DUST_THRESHOLD)
        try:
            return Decimal(value)
        except DecimalException:
            logging.warning(f"Invalid dust threshold setting '{value}', using default of {Setup.TOKEN_DUST_THRESHOLD}")
            return Decimal(Setup.TOKEN_DUST_THRESHOLD)

    # Amount below which an unsolicited incoming transfer is treated as dust. Exposed because the native coin of a
    # chain doesn't go through classify() - it has no contract address and can never be blacklisted as a token -
    # yet address-poisoning dust arrives in the native coin just as it does in tokens.
    def dust_threshold(self) -> Decimal:
        return self._dust_threshold

    # Returns TokenVerdict.Import or TokenVerdict.Blacklist for the given token without modifying anything
    def classify(self, candidate: TokenCandidate) -> int:
        # An existing blacklist record is the final word - if the user un-blacklisted the token the record is gone
        # and the token goes through the layers below again.
        if JalTokenBlacklist.is_blacklisted(candidate.location_id, candidate.address):
            return TokenVerdict.Blacklist
        if self._lists.is_allowlisted(candidate.location_id, candidate.address):   # Layer 1
            return TokenVerdict.Import
        # Layer 3 taken before layer 2: a token received from a swap was chosen by the user, so it is never dust
        if candidate.from_swap:
            return TokenVerdict.Import
        if self._is_dust(candidate):                                               # Layer 2
            return TokenVerdict.Blacklist
        return TokenVerdict.Import

    # Classifies the token and quarantines it if it was rejected. Returns True if the token may be imported.
    def accept(self, candidate: TokenCandidate) -> bool:
        verdict = self.classify(candidate)
        if verdict == TokenVerdict.Import:
            return True
        if not JalTokenBlacklist.is_blacklisted(candidate.location_id, candidate.address):
            JalTokenBlacklist.add(candidate.location_id, candidate.address,
                                  name_hint=candidate.symbol if candidate.symbol else candidate.name, auto=True)
        return False

    # A dust airdrop is an incoming token from an address the user never dealt with, that is either known to be
    # fraudulent or carries no meaningful value (including a value that can't be established at all).
    def _is_dust(self, candidate: TokenCandidate) -> bool:
        if not candidate.incoming or candidate.known_counterparty:
            return False
        if self._lists.is_blocklisted(candidate.location_id, candidate.address):
            return True
        return candidate.value is None or candidate.value < self._dust_threshold

    # Convenience wrapper for fetchers: returns the subset of candidates that may be imported, quarantining the rest
    def filter(self, candidates: list) -> list:
        accepted = [x for x in candidates if self.accept(x)]
        if len(accepted) != len(candidates):
            logging.info(f"{len(candidates) - len(accepted)} token(s) were blacklisted as unsolicited")
        return accepted
