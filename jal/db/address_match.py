from math import ceil, floor, log

from jal.constants import AssetLocation, AccountStatus
from jal.db.account import JalAccount
from jal.db.token_blacklist import normalize_address
from jal.net.chain_fetchers.protocols import protocol_category, protocol_contracts


# ----------------------------------------------------------------------------------------------------------------------
# Recognizes an ADDRESS-POISONING counterparty: an address minted to look like one of the user's own.
#
# The attack is a confidence trick played on the wallet's own history. Nobody reads a 40-digit address; every wallet
# and every explorer abbreviates it to its ends ("0x6da6...7e63"), and that abbreviation is what a user recognizes and
# copies when sending money to themselves. So the attacker grinds a vanity address matching the ENDS of an address the
# victim uses, sends a trivial amount from it, and waits: the poisoned entry now sits in the history looking exactly
# like the victim's own wallet, and the next transfer copied from there goes to the attacker instead.
#
# What makes it detectable is the same thing that makes it work. Matching both ends of an address is astronomically
# unlikely by chance - each hex digit is one of 16, so agreeing on N digits happens with probability 16^-N - while for
# the attacker it is the entire point of the address, ground out deliberately. The thresholds below ask for enough
# digits that coincidence is excluded: 3 at each end and 7 in total is 16^-7, about 4 in a billion per comparison, so
# a wallet with a handful of addresses and a few hundred counterparties expects false positives in the millionths.
# They are deliberately NOT tuned to the ends a particular wallet abbreviates to - what is being measured is that the
# resemblance cannot be an accident, and any display that shows fewer digits than this is one the trick works on.
#
# Those two numbers are a statement about PROBABILITY, and they were written for hex. An address in another alphabet
# carries more per character - a base58 character is one of 58, not one of 16 - so asking it for the same COUNT asks
# it for far more improbability than hex was ever asked for, and a Solana lookalike can be beyond doubt while still
# falling short of seven. The counts are therefore derived per chain from the hex ones, keeping the probability the
# same rather than the character count:
#
#   alphabet                each end          together
#   hex (EVM)               3  (1/4096)       7  (1 in 268 million)
#   base58 (SOL/BTC/TRX)    2  (1/3364)       5  (1 in 656 million)
#   bech32 (BTC bc1)        2  (1/1024)       6  (1 in 1.07 billion)
#
# The two bars are rounded in opposite directions, because they are doing different jobs. The COMBINED bar carries
# the whole probability claim, so it rounds UP and no chain is ever asked for less improbability than hex: the
# weakest pair that can pass is 3+4 in hex (1 in 268 million), 2+3 in base58 (1 in 656 million) and 2+4 in bech32
# (1 in 1.07 billion). The per-end bar makes no claim of its own - it only demands that the resemblance is present
# at BOTH ends, because both ends are what an abbreviation shows - so it rounds DOWN, never below two: one character
# agreeing at an end is not a match of anything, two is the least that can be called one.
#
# Rounding the per-end bar up instead is what kept a real Solana attempt out: an address agreeing on three leading
# and two trailing characters, sent 17 seconds after a genuine transfer to a wallet of the same user. Five base58
# characters is one chance in 656 million, so it was ground deliberately - which is the whole question this asks -
# and it was refused only because two characters is fewer than hex's three.
_HEX_AT_EACH_END = 3
_HEX_TOGETHER = 7
_HEX_ALPHABET = 16
_MIN_AT_EACH_END = 2         # a single agreeing character at an end is not a resemblance, however rich the alphabet
# The alphabet an address of each chain is written in. EVM addresses (and Hyperliquid's, which are EVM-shaped) are
# hex; Solana mints, Tron's 'T...' form and Bitcoin's legacy addresses are base58. A bech32 Bitcoin address is a
# 32-character alphabet and is told apart by its prefix, not by its chain - see _alphabet_of().
_BASE58 = 58
_BECH32 = 32
_HEX_CHAINS = [AssetLocation.ETH_BLOCKCHAIN, AssetLocation.ARB_BLOCKCHAIN,
               AssetLocation.HL_BLOCKCHAIN, AssetLocation.AVAX_BLOCKCHAIN]


# The size of the alphabet the given address is written in. Taken from the address itself where the chain doesn't
# settle it: Bitcoin writes both base58 ('1...', '3...') and bech32 ('bc1...') addresses, and the two are compared
# against each other only when they are the same kind anyway.
def _alphabet_of(location_id: int, address: str) -> int:
    if location_id in _HEX_CHAINS:
        return _HEX_ALPHABET
    if address[:3].lower() == 'bc1':
        return _BECH32
    return _BASE58


# The (at each end, together) thresholds for an address of the given chain - the hex pair above, restated in an
# alphabet that may carry more per character. The combined bar is never weaker than hex's; the per-end bar may be,
# and deliberately is, because the combined bar is what carries the claim (see the note above).
def _thresholds(location_id: int, address: str) -> tuple:
    alphabet = _alphabet_of(location_id, address)
    if alphabet == _HEX_ALPHABET:
        return _HEX_AT_EACH_END, _HEX_TOGETHER
    scale = log(_HEX_ALPHABET) / log(alphabet)
    return max(_MIN_AT_EACH_END, floor(_HEX_AT_EACH_END * scale)), ceil(_HEX_TOGETHER * scale)


# How many characters two addresses share at the start and at the end, as (leading, trailing).
#
# The chain prefix ('0x') is dropped first: every EVM address carries it, so counting it would credit two unrelated
# addresses with two digits of resemblance they didn't earn. Comparison is on the normalized form, since EIP-55
# capitalization is a checksum rather than part of the address, and one chain's address never resembles another's.
def address_resemblance(location_id: int, first: str, second: str) -> tuple:
    first, second = normalize_address(location_id, first), normalize_address(location_id, second)
    if first[:2] == '0x' and second[:2] == '0x':
        first, second = first[2:], second[2:]
    if not first or not second:
        return 0, 0
    shortest = min(len(first), len(second))
    leading = next((i for i in range(shortest) if first[i] != second[i]), shortest)
    trailing = next((i for i in range(shortest) if first[-1 - i] != second[-1 - i]), shortest)
    return leading, trailing


# True when 'address' is built to be mistaken for 'genuine' - see the thresholds above. An address that IS the genuine
# one is not a lookalike: it resembles itself completely, which is the one case that means nothing.
def is_lookalike(location_id: int, address: str, genuine: str) -> bool:
    if not address or not genuine:
        return False
    if normalize_address(location_id, address) == normalize_address(location_id, genuine):
        return False
    at_each_end, together = _thresholds(location_id, genuine)
    leading, trailing = address_resemblance(location_id, address, genuine)
    return leading >= at_each_end and trailing >= at_each_end and (leading + trailing) >= together


# What the given address was ground to be mistaken FOR, or None when it resembles nothing the user would recognize.
#
# The attack works on recognition, so what can be poisoned is whatever the user's eye is used to seeing in their own
# history - and that is more than their own wallets. Two sources are asked, in this order:
#
#   ACCOUNT   one of the user's own addresses. Every account is considered, not only those of this chain: an EVM
#             address is commonly registered as several accounts, one per chain, and an attacker who copies the ends
#             of an address held on Ethereum has poisoned it just as effectively on Arbitrum.
#   PROTOCOL  a contract of the protocol registry. These are the addresses a wallet deals with most often and knows
#             least well - nobody memorizes a bridge's address, which is exactly what makes imitating one work. The
#             three USDC lookalikes of the Hyperliquid Bridge2 contract that this was built from imitate no account
#             of the user's at all, and so were invisible while only accounts were asked.
#
# Accounts come first because naming one is the more useful answer ("this pretends to be your Arbitrum wallet"), and
# because an address that is both is the user's own by the stronger claim.
#
# Deliberately NOT a source: the counterparty addresses stored in 'transfers'. A settlement clears the address it
# resolved (see TransferSettlement._fill_end and _merge), so what is left there is only the addresses of legs that
# are still unsettled - which is a handful, is not the history the eye is used to, and is full of the poisoning
# addresses themselves. Comparing lookalikes against lookalikes is how a GENUINE arrival gets accused of imitating
# the fake that was ground to imitate it.
ACCOUNT = 'account'          # kinds of thing an address may have been minted to imitate
PROTOCOL = 'protocol'


def impersonated_target(location_id: int, address: str):
    if not address:
        return None
    # An address that IS the user's own or IS a contract the registry knows is the genuine article. It resembles
    # every lookalike ground to imitate it exactly as closely as they resemble it, so without this the real one
    # would be accused of impersonating the fake as soon as the fake is a candidate.
    if _is_genuine(location_id, address):
        return None
    for account in JalAccount.get_all_accounts(min_status=AccountStatus.Closed):
        if account.address() and is_lookalike(location_id, address, account.address()):
            return {'kind': ACCOUNT, 'name': account.name(), 'account': account}
    for contract, name in protocol_contracts(location_id):
        if is_lookalike(location_id, address, contract):
            return {'kind': PROTOCOL, 'name': name, 'account': None}
    return None


# Whether the address is one JAL already knows to be real - the user's own, or a registered contract
def _is_genuine(location_id: int, address: str) -> bool:
    if protocol_category(location_id, address) is not None:
        return True
    normalized = normalize_address(location_id, address)
    return any(account.address() and normalize_address(location_id, account.address()) == normalized
               for account in JalAccount.get_all_accounts(min_status=AccountStatus.Closed))
