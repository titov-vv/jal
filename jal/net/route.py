from decimal import Decimal

from PySide6.QtCore import QObject

from jal.constants import AssetLocation


# ----------------------------------------------------------------------------------------------------------------------
# How much of what a source says about a move may be acted on.
#
# The sources JAL can ask about a cross-chain move differ not in what they describe but in how well they know it, and
# that difference has to travel with the answer: a routing aggregator that recorded both legs of the route it executed
# states quantities that can be booked, while one that only indexes what a client told it names the transactions and
# nothing more. Mixing the two would let an approximation be written into the ledger.
#
#   CHAIN     - read off the chain itself. The authority: everything else is a description OF this, and is corrected
#               by it when the chain is eventually fetched (BridgeMatcher.reconcile_arrival). No resolver has it;
#               the tier exists so that a comparison against a fetched fact ranks above every reported one.
#   REPORTED  - the service executed the route and published both of its ends. Amounts and times may be booked, and
#               may be compared against what the ledger holds. LI.FI.
#   PROPOSED  - the service knows WHICH transactions belong together and nothing else that can be trusted. It may
#               name a counterpart, never state what arrived: its amounts are rounded floats and its timestamps are
#               moments in its own workflow rather than block times (see the Rango note). Such an answer can pair two
#               things JAL already holds; it can never create one.
class Confidence:
    PROPOSED = 1
    REPORTED = 2
    CHAIN = 3


# ----------------------------------------------------------------------------------------------------------------------
# One end of a move as some source recorded it, in terms JAL can act on but without any JAL identity yet: a chain is
# still the source's own name for it, a token is still a contract address. Turning that into accounts and symbols is
# ArrivalReconciler's business, so that a new source has nothing to know about the database.
#
# 'qty' is None and 'timestamp' is 0 when the source doesn't state them, or states them in a form that may not be
# believed - a leg like that names a transaction and no more. The exactness of what IS stated is each source's own
# responsibility: an amount must reach here unrounded (see the scaling in jal/net/lifi.py), because a quantity
# compared against on-chain data must not be approximated on the way in.
class RouteLeg:
    def __init__(self, chain: str = '', location_id: int = AssetLocation.UNDEFINED, tx_hash: str = '',
                 timestamp: int = 0, symbol: str = '', address: str = '', qty: Decimal = None):
        self.chain = chain                # the source's own name of the chain, shown when JAL doesn't know it
        self.location_id = location_id    # ... and what JAL calls it, or AssetLocation.UNDEFINED
        self.tx_hash = tx_hash
        self.timestamp = timestamp        # true UTC as the chain stamped it, NOT the local-wall-clock JAL stores
        self.symbol = symbol
        self.address = address            # the token's contract address, '' for the chain's own coin
        self.qty = qty

    # True when the leg says everything needed to book it: which chain, which token, how much and when
    def is_complete(self) -> bool:
        return bool(self.tx_hash) and self.qty is not None and self.qty > Decimal('0') and self.timestamp > 0


# ----------------------------------------------------------------------------------------------------------------------
# A completed route: what left one chain and what arrived on another (or on the same one, for a plain swap routed
# through an aggregator). 'tool' is the liquidity source the route went through - 'fly', 'across', 'GasZip' and the
# like. It is NOT the contract the wallet called: the route goes through the aggregator's own contract, and the tool
# only names who provided the liquidity inside it. It is carried because it is worth showing to the user, never to
# decide anything by.
class Route:
    def __init__(self, source: str, confidence: int, sending: RouteLeg, receiving: RouteLeg, tool: str = '',
                 status: str = '', from_address: str = '', to_address: str = ''):
        self.source = source            # who said this, shown to the user - an answer is never anonymous
        self.confidence = confidence
        self.sending = sending
        self.receiving = receiving
        self.tool = tool
        self.status = status
        self.from_address = from_address
        # Where the arrival was actually delivered. It is not necessarily an address of the wallet that sent it - a
        # route may be told to deliver anywhere - so it is the only thing that says which account (if any) the
        # arriving assets belong to.
        self.to_address = to_address

    # True when the two ends are on different chains, which is what makes the move one JAL must book as two legs
    def is_cross_chain(self) -> bool:
        return self.sending.chain != self.receiving.chain

    # Whether the numbers in this route may be written into an operation. A source below REPORTED may pair what JAL
    # already holds and no more - see Confidence.
    def is_bookable(self) -> bool:
        return self.confidence >= Confidence.REPORTED


# ----------------------------------------------------------------------------------------------------------------------
# A source that can be asked "what arrived for this outgoing transaction?".
#
# That is the whole interface, and it is deliberately blind to what asked: a pending half-bridge and a pending transfer
# leg are the same question about the same transaction hash, and a resolver that knew the difference would have to be
# taught it again for every operation type JAL grows. Subclasses provide a name, a confidence and _request().
#
# The cache is here rather than in each subclass because every source has the same property: an answer about a
# transaction cannot change during a run, and the same hash is asked about repeatedly (once when a pass sweeps the
# pending legs, again when the user opens the dialog on one of them).
class RouteResolver(QObject):
    name = ''
    confidence = Confidence.PROPOSED

    def __init__(self):
        super().__init__()
        self._cache = {}     # tx hash (lower case) -> Route or None, so one hash is asked about once per run

    # What this source recorded for the transaction that STARTED the route, or None when it has nothing to say about
    # it. None is never an error the caller must handle: not knowing is the normal answer for most transactions.
    def resolve(self, tx_hash: str):
        if not tx_hash:
            return None
        key = tx_hash.lower()
        if key not in self._cache:
            self._cache[key] = self._request(tx_hash)
        return self._cache[key]

    def _request(self, tx_hash: str):
        raise NotImplementedError
