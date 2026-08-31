# ----------------------------------------------------------------------------------------------------------------------
# What Aave's Safety module owes a staker, and nothing else - the module knows the protocol, not JAL's accounts.
#
# The VIEW is what must be asked, never the stored mapping beside it. Rewards accrue against an index that only
# settles when the staker interacts with the contract, so 'stakerRewardsToClaim' holds nothing but what the last
# interaction left behind - measured against a live position it was 0.003% of what the view reported, while the
# view's figure is what the dApp itself shows.
#
# Both modules in service pay AAVE, but which token that is comes from the CONTRACT rather than from here: a module
# that ever changed its reward token would otherwise be read as still paying the old one.

# The two Safety module contracts, normalized. Both answer the same views, so one reader covers them and the only
# per-contract knowledge is the address. Both are already registered in net/chain_fetchers/protocols.py as LENDING,
# which is what names them in the reports; that registration is about how a CLAIM is booked and must not be changed.
STAKED_AAVE = '0x4da27a545c0c5b758a6ba100e3a049001de870f5'   # stkAAVE - stakes AAVE and pays AAVE
STAKED_GHO = '0x1a88df1cfe15af22b3c4c783d4e6f7f9e0c1885d'    # stkGHO - stakes GHO and pays AAVE as well

SAFETY_MODULES = (STAKED_AAVE, STAKED_GHO)

# Call data of the module views - the function selector, followed by the argument for the one that takes it.
SELECTOR_REWARD_TOKEN = '0x99248ea7'     # REWARD_TOKEN() -> address
SELECTOR_TOTAL_REWARDS = '0x8dbefee2'    # getTotalRewardsBalance(address) -> uint256


# One value as abi.encode writes it: padded to a full 32-byte word. An address is 20 bytes and pads on the LEFT.
def _word(address: str) -> bytes:
    try:
        data = bytes.fromhex(address.lower().removeprefix('0x'))
    except (ValueError, AttributeError):
        return b''
    return data.rjust(32, b'\0') if len(data) <= 32 else b''


def _answer_word(answer: str) -> bytes:
    try:
        data = bytes.fromhex(answer.removeprefix('0x'))
    except (ValueError, AttributeError):
        return b''
    # An answer of a different length is not a short answer to be read leniently - it is a call that returned
    # something else entirely, and taking a slice of it would invent both the token and the figure.
    return data if len(data) == 32 else b''


# Call data of getTotalRewardsBalance(address): the selector followed by the staker as a full 32-byte word.
def rewards_call(staker: str) -> str:
    word = _word(staker)
    return SELECTOR_TOTAL_REWARDS + word.hex() if word else ''


# The address a one-word answer holds, or '' when the answer isn't one. The padding is checked as well as the length:
# a word whose top 12 bytes aren't empty is not an address, and using its tail would ask a random contract for a name.
def address_answer(answer: str) -> str:
    data = _answer_word(answer)
    if not data or any(data[:12]):
        return ''
    return '0x' + data[12:].hex()


# The quantity a one-word answer holds, or None when the answer isn't one.
def amount_answer(answer: str):
    data = _answer_word(answer)
    return int.from_bytes(data, 'big') if data else None
