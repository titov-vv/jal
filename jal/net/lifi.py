import json
import logging
from decimal import Decimal, DecimalException

from PySide6.QtWidgets import QApplication

from jal.constants import AssetLocation
from jal.db.token_blacklist import normalize_address
from jal.net.route import Confidence, Route, RouteLeg, RouteResolver
from jal.net.web_request import WebRequest

# LI.FI resolves a cross-chain move that JAL can only see one end of. Both ends are recorded by the aggregator that
# routed it, and its status endpoint returns them for a single source transaction hash - no key, no account, no
# wallet address needed.
_API_STATUS = "https://li.quest/v1/status"

# LI.FI numbers chains by their EVM chain id where there is one, and by an id of its own where there isn't (Solana,
# Bitcoin). Only the chains JAL itself knows are mapped: an arrival on any other chain is reported to the user rather
# than placed, because JAL has no account that could hold it.
#
# 1337 is Hyperliquid's spot side (LI.FI's chain key 'hpl'), which is what JAL's HL_BLOCKCHAIN account holds. LI.FI
# also lists HyperEVM separately as 999 - a different chain, and one JAL has no account type for, so it is absent
# here on purpose. Tron is not routed by LI.FI at all and therefore has no entry either.
_CHAINS = {
    1: AssetLocation.ETH_BLOCKCHAIN,
    42161: AssetLocation.ARB_BLOCKCHAIN,
    1337: AssetLocation.HL_BLOCKCHAIN,
    1151111081099710: AssetLocation.SOL_BLOCKCHAIN,
    20000000000001: AssetLocation.BTC_BLOCKCHAIN
}

# The placeholder a chain's own coin is given where a token contract address belongs. JAL stores the native coin of a
# chain with no address at all (see ChainFetcher._native_asset_id), so each of these is translated to an empty address
# and the coin is then looked up the way the fetchers create it.
_NATIVE_ADDRESSES = {
    '0x0000000000000000000000000000000000000000',   # every EVM chain
    '0x0000000000000000000000000000000000001010',   # Polygon's variant of the same placeholder
    '11111111111111111111111111111111',             # Solana system program, standing in for SOL
    'bitcoin'                                       # Bitcoin, which has no contract addresses at all
}

_DONE = 'DONE'      # the only status whose amounts are final - a route still in flight may yet deliver something else

_SOURCE = "LI.FI"   # what the user is told an answer came from


# One end of a move as LI.FI recorded it. Amounts are kept exactly as the API reports them - an integer of the token's
# smallest unit plus that token's decimals - and turned into a Decimal quantity here, which is lossless. The timestamp
# stays the true UTC epoch the chain stamped, which is what JAL stores.
def _leg(record: dict) -> RouteLeg:
    token = record.get('token') or {}
    chain_id = record.get('chainId')
    location_id = _CHAINS.get(chain_id, AssetLocation.UNDEFINED)
    return RouteLeg(chain='' if chain_id is None else f"{chain_id}", location_id=location_id,
                    tx_hash=record.get('txHash') or '', timestamp=int(record.get('timestamp') or 0),
                    symbol=token.get('symbol') or '', address=_token_address(token, location_id),
                    qty=_quantity(record.get('amount'), int(token.get('decimals') or 0)))


# The token's contract address in the form JAL stores it, or '' for the chain's own coin - see _NATIVE_ADDRESSES.
# Normalization is per chain (EVM lower-cases, Solana does not), which is what makes the address comparable with the
# identifiers JAL keeps on its symbols.
def _token_address(token: dict, location_id: int) -> str:
    address = (token.get('address') or '').strip()
    if not address or address.lower() in _NATIVE_ADDRESSES:
        return ''
    return normalize_address(location_id, address)


# The amount arrives as an integer count of the token's smallest unit, which the token's own decimals scale into a
# quantity. The scaling shifts the exponent of the value instead of dividing it: a division is performed in the
# current decimal context and would silently round an amount of more than 28 significant digits, which is exactly the
# kind of quiet loss a quantity compared against on-chain data must not suffer.
def _quantity(amount, decimals: int):
    try:
        sign, digits, exponent = Decimal(str(amount)).as_tuple()
        return Decimal((sign, digits, exponent - decimals))
    except (DecimalException, TypeError, ValueError):
        return None


# ----------------------------------------------------------------------------------------------------------------------
# Reads back what LI.FI recorded about a transaction JAL has only one end of.
#
# JAL sees a cross-chain move as two unrelated transactions on two chains, and the sending one carries nothing that
# names its counterpart - which is why an arriving leg can otherwise only be matched by hand (jal/db/bridge_matcher.py).
# The aggregator that routed the move does know both ends, and publishes them for anyone who has the source hash.
# It also settles a second ambiguity no on-chain data can: a route that sends on one chain and delivers on another
# frequently refunds unused input on the SOURCE chain, which looks exactly like a same-chain swap to the per-transaction
# classifier (see EVMFetcher._classify_transaction) - the answer here says the move was cross-chain and how much really
# arrived.
#
# Only routes LI.FI itself handled are known to it; a swap through any other router answers 404 and is simply not
# something this can say anything about.
#
# LI.FI answers from its own contracts' events, so what it states about a route it executed is a record and not a
# rendering of one: it is the REPORTED tier, and its amounts and times may be booked (see jal/net/route.py).
class LiFiResolver(RouteResolver):
    name = _SOURCE
    confidence = Confidence.REPORTED

    def tr(self, text):
        return QApplication.translate("LiFiResolver", text)

    # What LI.FI recorded for the transaction that STARTED the route, or None when it has nothing to say about it -
    # the transaction was not routed by LI.FI (a 404), the route did not complete, or the network was unreachable.
    def _request(self, tx_hash: str):
        # 404 is the answer "this transaction was not handled by LI.FI contracts", which most transactions asked about
        # will get - it is not a failure and must not be logged as one (see WebRequest.expected_errors).
        request = WebRequest(WebRequest.GET, _API_STATUS, params={"txHash": tx_hash}, expected_errors=(404,))
        while not request.wait():
            QApplication.processEvents()   # keeps the GUI alive, like ChainFetcher._wait_for()
        answer = request.data()
        if not answer:      # 404 for a transaction LI.FI never routed, or the request failed - both mean "no answer"
            return None
        try:
            data = json.loads(answer)
        except (json.JSONDecodeError, TypeError):
            logging.warning(self.tr("Unexpected answer from LI.FI: ") + f"{answer}")
            return None
        return self._validated(data, tx_hash)

    # Turns an answer into a Route, or None if it may not be trusted for this hash.
    #
    # The identity check is not a formality. The endpoint accepts either a transaction hash or LI.FI's own route id in
    # the same parameter, and a value it fails to recognize as a hash is looked up as a route id - which can answer
    # 200 with SOMEBODY ELSE'S transfer. Booking that against a JAL operation would invent a counter-leg out of an
    # unrelated wallet's money, so an answer is only used when it is about the very transaction that was asked for.
    def _validated(self, data: dict, tx_hash: str):
        route = Route(_SOURCE, self.confidence, _leg(data.get('sending') or {}), _leg(data.get('receiving') or {}),
                      tool=data.get('tool') or '', status=data.get('status') or '',
                      from_address=data.get('fromAddress') or '', to_address=data.get('toAddress') or '')
        if route.sending.tx_hash.lower() != tx_hash.lower():
            logging.warning(self.tr("LI.FI answered about another transaction: ")
                            + f"{tx_hash} -> {route.sending.tx_hash}")
            return None
        if route.status != _DONE:
            logging.info(self.tr("LI.FI route is not completed: ") + f"{tx_hash} ({route.status})")
            return None
        if not route.sending.is_complete() or not route.receiving.is_complete():
            logging.warning(self.tr("LI.FI answer is incomplete for: ") + tx_hash)
            return None
        return route
