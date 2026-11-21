from jal.constants import AssetLocation

# ----------------------------------------------------------------------------------------------------------------------
# Fluid lending: every fToken (an ERC-4626 vault) is created by the LendingFactory, whose allTokens() lists them all.
PROTOCOL = 'Fluid'    # AssetData.Protocol of an fToken

_FACTORY = '0x54b91a0d94cb471f37f949c60f7fa7935b551d03'    # same address on every chain, reported by fToken.getData()
LENDING_FACTORIES = {AssetLocation.ETH_BLOCKCHAIN: _FACTORY,
                     AssetLocation.ARB_BLOCKCHAIN: _FACTORY}

SELECTOR_ALL_TOKENS = '0x6ff97f1d'    # LendingFactory.allTokens() -> address[]
SELECTOR_SYMBOL = '0x95d89b41'        # fToken.symbol() -> string


# Protocol name of an fToken as written into operation descriptions, e.g. 'Fluid fUSDC@ARB'
def vault_name(symbol: str, chain: str) -> str:
    return f"{PROTOCOL} {symbol}@{chain}"


# The addresses an ABI-encoded address[] answer holds, lower-cased; an empty set for anything malformed
def tokens_answer(answer: str) -> set:
    try:
        data = bytes.fromhex(answer.removeprefix('0x'))
    except (ValueError, AttributeError):
        return set()
    if len(data) < 64 or len(data) % 32 or int.from_bytes(data[:32], 'big') != 32:
        return set()
    count = int.from_bytes(data[32:64], 'big')
    if len(data) != 64 + 32 * count:
        return set()
    words = [data[64 + 32 * i: 96 + 32 * i] for i in range(count)]
    if any(any(word[:12]) for word in words):
        return set()
    return {'0x' + word[12:].hex() for word in words}


# The text an ABI-encoded string answer holds, '' for anything malformed or not printable
def text_answer(answer: str) -> str:
    try:
        data = bytes.fromhex(answer.removeprefix('0x'))
    except (ValueError, AttributeError):
        return ''
    if len(data) < 64 or len(data) % 32 or int.from_bytes(data[:32], 'big') != 32:
        return ''
    length = int.from_bytes(data[32:64], 'big')
    if length > len(data) - 64:
        return ''
    try:
        text = data[64:64 + length].decode('utf-8')
    except UnicodeDecodeError:
        return ''
    return text if text.isprintable() else ''
