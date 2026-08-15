import json
import logging

from PySide6.QtWidgets import QApplication

from jal.constants import AssetLocation
from jal.db.token_blacklist import normalize_address
from jal.net.route import Confidence, Route, RouteLeg, RouteResolver
from jal.net.web_request import WebRequest

# Rango has no lookup API: its JSON API is key-gated and no endpoint in it takes a transaction hash at all, so the
# only way from a hash to a route is the explorer, which redirects the search to the page of the route it belongs to.
# The redirect is followed by the request itself, so one call answers.
_EXPLORER_SEARCH = "https://explorer.rango.exchange/search"

# The explorer is a server-rendered Next.js application: the page arrives with the route data already inside it, as a
# React Server Components "flight" payload split over a series of script pushes. Each push carries a JSON-encoded
# string, and concatenating them yields the flight text with the route object in it verbatim, under this key.
_PUSH = 'self.__next_f.push([1,'
_OBJECT = '"step":'

# Rango names chains by a string of its own rather than by a numeric id, so no id table is needed - only JAL's own
# chains are mapped, and an arrival anywhere else is reported to the user rather than placed. HYPEREVM is a different
# chain from HYPERLIQUID and is absent on purpose, the same distinction lifi.py draws between LI.FI's 1337 and 999.
_CHAINS = {
    'ETH': AssetLocation.ETH_BLOCKCHAIN,
    'ARBITRUM': AssetLocation.ARB_BLOCKCHAIN,
    'BTC': AssetLocation.BTC_BLOCKCHAIN,
    'SOLANA': AssetLocation.SOL_BLOCKCHAIN,
    'TRON': AssetLocation.TRX_BLOCKCHAIN,
    'HYPERLIQUID': AssetLocation.HL_BLOCKCHAIN
}

_SUCCESS = 'success'      # the only status whose legs both exist; 'failed' and 'running' have nothing to pair
_OUTBOUND = 'Outbound'    # how the destination transaction is labelled among the route's explorer links
_HASH_LENGTH = 32         # shorter than any chain's transaction id, and long enough to reject a URL that has none

_SOURCE = "Rango"         # what the user is told an answer came from


# ----------------------------------------------------------------------------------------------------------------------
# Reads back which two transactions Rango's explorer says are the two ends of one cross-chain move - and nothing else.
#
# Rango is the only source besides LI.FI that publishes a complete arriving leg, and its coverage is genuinely
# additive: it routes chains LI.FI does not (Tron among them), and a move it handled is one LI.FI answers 404 for.
# Everything else about it is worse, and the difference is what makes it a PROPOSED source rather than a REPORTED one:
#
#   * its amounts are JSON floats - already divided, already rounded. Measured against the chain on a real route, the
#     arriving quantity was 296 wei short, and there is no integer form to fall back on. A quantity like that would
#     never compare equal to the one BridgeMatcher.reconcile_arrival() later reads off the chain.
#   * neither of its two time fields is a block time: both are moments in Rango's own workflow, off by 24 s and 138 s
#     from the transactions they describe on the same measured route.
#   * its index records what a client TOLD it, not what a chain did - a route id is created when a route is quoted and
#     the hash attached to it is self-reported, so records exist claiming transactions that were never mined.
#
# So none of its numbers are read here at all: the legs it produces carry no quantity and no timestamp, which leaves
# them unbookable by construction (RouteLeg.is_complete) on top of the tier check. What is exact is the pair of
# transaction hashes, and that is the one thing JAL cannot get anywhere else - the chain supplies everything else,
# correctly, once the counterpart transaction is known.
#
# The page format is an undocumented framework internal with no compatibility promise, and it changes whenever Rango
# redeploys. That is survivable only because of the above: when it breaks, the parse finds nothing and the answer
# becomes "Rango knows nothing about this transaction" - which is the ordinary answer anyway - rather than a wrong
# number in the ledger.
class RangoResolver(RouteResolver):
    name = _SOURCE
    confidence = Confidence.PROPOSED

    def tr(self, text):
        return QApplication.translate("RangoResolver", text)

    # The route the transaction started, or None when Rango has no usable record of it. A hash it never saw is
    # answered with HTTP 200 and a "not found" page rather than an error code, so "no answer" is a page with no route
    # object in it - which is also what a changed page format looks like, and both mean the same thing here.
    def _request(self, tx_hash: str):
        request = WebRequest(WebRequest.GET, _EXPLORER_SEARCH, params={"query": tx_hash})
        while not request.wait():
            QApplication.processEvents()   # keeps the GUI alive, like ChainFetcher._wait_for()
        page = request.data()
        if not page:
            return None
        record = self._route_object(page)
        if record is None:
            return None
        return self._validated(record, tx_hash)

    # The route object out of the page's flight payload, or None when there is none in it.
    @staticmethod
    def _route_object(page: str):
        decoder = json.JSONDecoder()
        chunks = []
        position = 0
        while True:
            found = page.find(_PUSH, position)
            if found < 0:
                break
            try:
                chunk, position = decoder.raw_decode(page, found + len(_PUSH))
            except ValueError:
                return None
            if isinstance(chunk, str):
                chunks.append(chunk)
        flight = ''.join(chunks)
        found = flight.find(_OBJECT)
        if found < 0:
            return None
        try:
            record, _ = decoder.raw_decode(flight, found + len(_OBJECT))
        except ValueError:
            return None
        return record if isinstance(record, dict) else None

    # Turns a route object into a Route, or None if it may not be used for this hash.
    #
    # The identity check is the same one LiFiResolver makes and for the same reason, although the trap it guards
    # against is a different one: a search answers about whatever route it redirected to, and only the route that
    # names the transaction asked about may be believed.
    def _validated(self, record: dict, tx_hash: str):
        hashes = [f"{x}".lower() for x in (record.get('generatedTxId') or [])]
        if tx_hash.lower() not in hashes:
            logging.warning(self.tr("Rango answered about another transaction: ") + f"{tx_hash} -> {hashes}")
            return None
        if record.get('status') != _SUCCESS:
            logging.info(self.tr("Rango route did not succeed: ") + f"{tx_hash} ({record.get('status')})")
            return None
        # A route that ended in something other than what it set out to deliver names that asset in 'outputToken'
        # instead of in 'to' - a shape no observed record has, so nothing here knows how to read it correctly.
        if record.get('outputToken') is not None:
            logging.warning(self.tr("Rango reports this route delivered another asset than it was quoted for: ")
                            + tx_hash)
            return None
        sending = self._leg(record.get('from') or {}, tx_hash)
        receiving = self._leg(record.get('to') or {}, self._destination_hash(record))
        return Route(_SOURCE, self.confidence, sending, receiving,
                     tool=(record.get('swapper') or {}).get('swapperTitle') or '', status=record.get('status') or '',
                     from_address=self._wallet(record, 'sourceWallet', sending.location_id),
                     to_address=self._wallet(record, 'destinationWallet', receiving.location_id))

    # One end of the route. Deliberately partial: the chain, the token and the transaction are read, the quantity and
    # the time are not - see the class comment.
    @staticmethod
    def _leg(token: dict, tx_hash: str) -> RouteLeg:
        chain = ((token.get('blockchainData') or {}).get('blockchain') or '').strip()
        location_id = _CHAINS.get(chain, AssetLocation.UNDEFINED)
        # A native coin has no 'address' key at all, which maps directly onto the empty address JAL keeps for it
        address = (token.get('address') or '').strip()
        return RouteLeg(chain=chain, location_id=location_id, tx_hash=tx_hash, symbol=token.get('symbol') or '',
                        address=normalize_address(location_id, address) if address else '')

    # The transaction the route delivered in. It is not a field: it exists only inside a rendered block-explorer link,
    # so it is taken from the last path segment of the one labelled 'Outbound'. That depends on the label, on the URL
    # layout of whichever explorer Rango chose for the chain, and on that explorer not being replaced - it is the
    # single most fragile thing here, and it fails by finding nothing.
    @staticmethod
    def _destination_hash(record: dict) -> str:
        for link in record.get('explorerUrls') or []:
            if link.get('description') != _OUTBOUND:
                continue
            url = (link.get('url') or '').split('?')[0].rstrip('/')
            candidate = url.rsplit('/', 1)[-1] if '/' in url else ''
            # A link that turned out to point at something other than a transaction leaves its last segment looking
            # like a hash to nothing in particular ('snowtrace.dev'), and that would be compared against the stored
            # hashes as if it were one. Every chain's transaction id is far longer than this.
            return candidate if len(candidate) >= _HASH_LENGTH else ''
        return ''

    # EVM addresses come back checksummed on some records and lower-cased on others, so they are normalized on the
    # way in rather than assumed - which is what makes them comparable with the addresses JAL keeps on its accounts.
    @staticmethod
    def _wallet(record: dict, side: str, location_id: int) -> str:
        address = ((record.get(side) or {}).get('address') or '').strip()
        return normalize_address(location_id, address) if address else ''
